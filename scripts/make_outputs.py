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

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                      # write files only, never open a window
import matplotlib.pyplot as plt
import pandas as pd
import statsmodels.formula.api as smf
from sector_results import write_sector_results

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "outputs/batch_v0"
OUT = ROOT / "outputs"
DASHBOARD_DATA = ROOT / "data/processed/tariff_firms.csv"
HAND_CHECK = ROOT / "audits/hand_check_v0.csv"


def write_hand_check(firms, prefix="v0"):
    """outputs/v0_hand_check.md: AI score next to the blind human score, firm by firm."""
    hc = firms.dropna(subset=["hand_score"])
    diff = hc.hand_score - hc.exposure_score
    lines = [f"Blind hand-check of the AI exposure scores ({len(hc)} complete {prefix} firms). "
             f"Source: `{HAND_CHECK.relative_to(ROOT).as_posix() if HAND_CHECK.is_relative_to(ROOT) else HAND_CHECK}`.", "",
             f"- Exact match: {(diff == 0).sum()} of {len(hc)}",
             f"- Within one point: {(diff.abs() <= 1).sum()} of {len(hc)}",
             f"- Mean absolute difference: {diff.abs().mean():.2f} points", "",
             "| Ticker | AI score | Hand score | Difference | Hand-checker's reason |", "|---|---:|---:|---:|---|"]
    for f, d in zip(hc.sort_values("ticker").itertuples(), diff.loc[hc.sort_values("ticker").index]):
        reason = " ".join(str(f.hand_reason).split())
        reason = reason if len(reason) <= 180 else reason[:177] + "..."
        lines.append(f"| {f.ticker} | {f.exposure_score} | {int(f.hand_score)} | {int(d):+d} | {reason} |")
    (OUT / f"{prefix}_hand_check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    global BATCH, OUT, DASHBOARD_DATA, HAND_CHECK
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=Path, default=BATCH)
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--prefix", default="v0")
    parser.add_argument("--dashboard-data", type=Path)
    parser.add_argument("--hand-check", type=Path)
    args = parser.parse_args()
    if not args.prefix.replace("_", "").isalnum():
        parser.error("--prefix must contain only letters, numbers and underscores")
    BATCH, OUT = args.batch, args.out
    DASHBOARD_DATA = args.dashboard_data or (DASHBOARD_DATA if args.prefix == "v0" else OUT / f"{args.prefix}_tariff_firms.csv")
    HAND_CHECK = args.hand_check or (HAND_CHECK if args.prefix == "v0" else None)
    OUT.mkdir(parents=True, exist_ok=True)
    firms = pd.read_csv(BATCH / "tariff_firms.csv", dtype={"cik": str})
    # The same rows as text, untouched. The dashboard file is written from these so every
    # pandas version produces the same bytes (number parsing can differ in the 16th digit).
    text_rows = pd.read_csv(BATCH / "tariff_firms.csv", dtype=str, keep_default_na=False)
    failures = pd.read_csv(BATCH / "failures.csv")
    attempted = len(firms) + len(failures)

    # Key facts, checked every run.
    assert firms.ticker.is_unique, "one row per firm"
    assert firms.exposure_score.between(0, 4).all(), "scores must be 0-4"
    assert (firms.tenk_filing_date < "2025-04-02").all(), "10-K must predate the event"
    # car_pp is the sum of the two daily stock-minus-SPY returns; recompute it by hand.
    by_hand = (firms.ret_apr3_pct - firms.mkt_apr3_pct) + (firms.ret_apr4_pct - firms.mkt_apr4_pct)
    assert (by_hand - firms.car_pp).abs().max() < 1e-9, "car_pp does not match its parts"
    write_sector_results(firms, OUT, args.prefix)

    # 1. Blind human scores (checklist item 8): a teammate scored the same 10-Ks
    #    without seeing the AI's scores. Join on ticker; each firm must match once.
    if HAND_CHECK is not None and HAND_CHECK.exists():
        hand = pd.read_csv(HAND_CHECK)
        assert hand.ticker.is_unique and hand.hand_score.between(0, 4).all(), "bad hand-check file"
        columns = list(firms.columns)
        firms = firms.drop(columns="hand_score").merge(
            hand[["ticker", "hand_score", "hand_reason"]], on="ticker", how="left", validate="one_to_one")
        write_hand_check(firms, args.prefix)
        firms = firms.drop(columns="hand_reason")[columns]

    # 2. The dataset the dashboard reads: the batch rows exactly as written, plus hand_score.
    hand_text = firms.set_index("ticker").hand_score.map(lambda v: "" if pd.isna(v) else str(int(v)))
    text_rows["hand_score"] = text_rows.ticker.map(hand_text)
    DASHBOARD_DATA.parent.mkdir(parents=True, exist_ok=True)
    text_rows.to_csv(DASHBOARD_DATA, index=False, lineterminator="\n")

    # 3. Firm table (Markdown, so it reads well on GitHub).
    rows = ["| Ticker | Sector | Exposure (0-4) | Apr 3-4 return minus SPY (pp) | Evidence quoted from the 10-K |",
            "|---|---|---:|---:|---|"]
    for f in firms.sort_values(["exposure_score", "ticker"], ascending=[False, True],
                                 kind="stable").itertuples():  # ties by ticker: same order on every computer
        quote = " ".join(str(f.exposure_evidence).split())
        quote = quote if len(quote) <= 160 else quote[:157] + "..."
        rows.append(f"| {f.ticker} | {f.gics_sector} | {f.exposure_score} | {f.car_pp:+.2f} | {quote} |")
    rows += ["", f"{len(firms)} of {attempted} firms complete. Not included:"]
    rows += [f"- {f.ticker}: {f.stage} step failed ({f.error})" for f in failures.itertuples()]
    (OUT / f"{args.prefix}_firms.md").write_text("\n".join(rows) + "\n", encoding="utf-8")

    # 4. Regression: CAR (pp) on exposure score, heteroskedasticity-robust (HC3) errors.
    fit = smf.ols("car_pp ~ exposure_score", data=firms).fit(cov_type="HC3")
    pd.DataFrame({"term": fit.params.index, "coef": fit.params.values, "std_err_hc3": fit.bse.values,
                  "t": fit.tvalues.values, "p": fit.pvalues.values}).assign(
        n=int(fit.nobs), r2=fit.rsquared).round(6).to_csv(OUT / f"{args.prefix}_regression.csv", index=False)  # 6 decimals: same file on every computer

    # 5. Chart: each firm's exposure score against its two-day market-adjusted return.
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
    ax.set_xlabel("Import / China exposure score from the pre-event 10-K (0 = none, 4 = very high)"
                  if args.prefix == "v0" else "Import / foreign production dependence from the pre-event 10-K (0-4)")
    ax.set_ylabel("Apr 3-4, 2025 return minus SPY (pp)")
    ax.set_title(f"{args.prefix} sample: {len(firms)} firms" +
                 (" (smoke test, too few to conclude anything)" if args.prefix == "v0" else ""), fontsize=10)
    ax.legend(fontsize=8, loc="upper center", frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / f"{args.prefix}_exposure_vs_car.png")

    print(f"{len(firms)} firms -> {DASHBOARD_DATA}; results in {OUT} ({args.prefix})")


if __name__ == "__main__":
    main()
