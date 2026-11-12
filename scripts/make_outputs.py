"""Turn the scored firms into the files people look at (last step of run_all.py).

Reads  outputs/batch_v0/tariff_firms.csv   (written by scripts/tariff_batch.py)
Writes data/processed/tariff_firms.csv     the dataset the dashboard reads (with hand scores)
       outputs/v0_hand_check.md            AI score vs blind human score, firm by firm
       outputs/v0_firms.md                 one row per firm: score, quote, return
       outputs/v0_regression.csv           CAR on exposure score, robust (HC3) errors
       outputs/v0_exposure_vs_car.png      the chart

v0 is a 10-firm smoke test, so the regression is there to show the step runs,
not to answer the question. With 8 firms it cannot.

Run from the repository root:  python scripts/make_outputs.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")                      # write files only, never open a window
import matplotlib.pyplot as plt
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "outputs/batch_v0"
OUT = ROOT / "outputs"
DASHBOARD_DATA = ROOT / "data/processed/tariff_firms.csv"
HAND_CHECK = ROOT / "audits/hand_check_v0.csv"


def write_hand_check(firms):
    """outputs/v0_hand_check.md: AI score next to the blind human score, firm by firm."""
    hc = firms.dropna(subset=["hand_score"])
    diff = hc.hand_score - hc.exposure_score
    lines = [f"Blind hand-check of the AI exposure scores ({len(hc)} complete v0 firms). "
             f"Source: `audits/hand_check_v0.csv`.", "",
             f"- Exact match: {(diff == 0).sum()} of {len(hc)}",
             f"- Within one point: {(diff.abs() <= 1).sum()} of {len(hc)}",
             f"- Mean absolute difference: {diff.abs().mean():.2f} points", "",
             "| Ticker | AI score | Hand score | Difference | Hand-checker's reason |", "|---|---:|---:|---:|---|"]
    for f, d in zip(hc.sort_values("ticker").itertuples(), diff.loc[hc.sort_values("ticker").index]):
        reason = " ".join(str(f.hand_reason).split())
        reason = reason if len(reason) <= 180 else reason[:177] + "..."
        lines.append(f"| {f.ticker} | {f.exposure_score} | {int(f.hand_score)} | {int(d):+d} | {reason} |")
    (OUT / "v0_hand_check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    firms = pd.read_csv(BATCH / "tariff_firms.csv", dtype={"cik": str})
    failures = pd.read_csv(BATCH / "failures.csv")
    attempted = len(firms) + len(failures)

    # Key facts, checked every run.
    assert firms.ticker.is_unique, "one row per firm"
    assert firms.exposure_score.between(0, 4).all(), "scores must be 0-4"
    assert (firms.tenk_filing_date < "2025-04-02").all(), "10-K must predate the event"
    # car_pp is the sum of the two daily stock-minus-SPY returns; recompute it by hand.
    by_hand = (firms.ret_apr3_pct - firms.mkt_apr3_pct) + (firms.ret_apr4_pct - firms.mkt_apr4_pct)
    assert (by_hand - firms.car_pp).abs().max() < 1e-9, "car_pp does not match its parts"

    # 1. Blind human scores (checklist item 8): a teammate scored the same 10-Ks
    #    without seeing the AI's scores. Join on ticker; each firm must match once.
    if HAND_CHECK.exists():
        hand = pd.read_csv(HAND_CHECK)
        assert hand.ticker.is_unique and hand.hand_score.between(0, 4).all(), "bad hand-check file"
        columns = list(firms.columns)
        firms = firms.drop(columns="hand_score").merge(
            hand[["ticker", "hand_score", "hand_reason"]], on="ticker", how="left", validate="one_to_one")
        write_hand_check(firms)
        firms = firms.drop(columns="hand_reason")[columns]

    # 2. The dataset the dashboard reads.
    DASHBOARD_DATA.parent.mkdir(parents=True, exist_ok=True)
    firms.to_csv(DASHBOARD_DATA, index=False, lineterminator="\n")

    # 2. Firm table (Markdown, so it reads well on GitHub).
    rows = ["| Ticker | Sector | Exposure (0-4) | Apr 3-4 return minus SPY (pp) | Evidence quoted from the 10-K |",
            "|---|---|---:|---:|---|"]
    for f in firms.sort_values("exposure_score", ascending=False).itertuples():
        quote = " ".join(str(f.exposure_evidence).split())
        quote = quote if len(quote) <= 160 else quote[:157] + "..."
        rows.append(f"| {f.ticker} | {f.gics_sector} | {f.exposure_score} | {f.car_pp:+.2f} | {quote} |")
    rows += ["", f"{len(firms)} of {attempted} firms complete. Not included:"]
    rows += [f"- {f.ticker}: {f.stage} step failed ({f.error})" for f in failures.itertuples()]
    (OUT / "v0_firms.md").write_text("\n".join(rows) + "\n", encoding="utf-8")

    # 3. Regression: CAR (pp) on exposure score, heteroskedasticity-robust (HC3) errors.
    fit = smf.ols("car_pp ~ exposure_score", data=firms).fit(cov_type="HC3")
    pd.DataFrame({"term": fit.params.index, "coef": fit.params.values, "std_err_hc3": fit.bse.values,
                  "t": fit.tvalues.values, "p": fit.pvalues.values}).assign(
        n=int(fit.nobs), r2=fit.rsquared).to_csv(OUT / "v0_regression.csv", index=False)

    # 4. Chart: each firm's exposure score against its two-day market-adjusted return.
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=150)
    ax.axhline(0, color="#999999", linewidth=0.8)
    ax.scatter(firms.exposure_score, firms.car_pp, s=40, color="#1f5f8b", zorder=3)
    for f in firms.itertuples():
        ax.annotate(f.ticker, (f.exposure_score, f.car_pp), xytext=(6, 3), textcoords="offset points", fontsize=8)
    xs = pd.Series([0, 4])
    ax.plot(xs, fit.params["Intercept"] + fit.params["exposure_score"] * xs, color="#9a4d12", linewidth=1,
            label=f"OLS fit: {fit.params['exposure_score']:+.2f} pp per point (n={int(fit.nobs)})")
    ax.set_xticks(range(5))
    ax.set_xlim(-0.4, 4.6)
    ax.set_xlabel("Import / China exposure score from the pre-event 10-K (0 = none, 4 = very high)")
    ax.set_ylabel("Apr 3-4, 2025 return minus SPY (pp)")
    ax.set_title(f"v0 sample: {len(firms)} firms (smoke test, too few to conclude anything)", fontsize=10)
    ax.legend(fontsize=8, loc="upper center", frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "v0_exposure_vs_car.png")

    print(f"{len(firms)} firms -> {DASHBOARD_DATA.relative_to(ROOT)}, outputs/v0_firms.md, "
          f"outputs/v0_regression.csv, outputs/v0_exposure_vs_car.png")


if __name__ == "__main__":
    main()
