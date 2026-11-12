"""Team Cinco dashboard: Who lost on Liberation Day?

Run locally:  streamlit run dashboard/app.py

Data: reads data/processed/tariff_firms.csv (the real pipeline output) if it
exists. Otherwise it falls back to data/toy/tariff_firms_FAKE.csv and shows a
red FAKE DATA banner. Column definitions: docs/DATA_CONTRACT.md.

Works at any sample size. With fewer than MIN_FOR_REGRESSIONS firms it shows
every firm individually and holds back the sector-control regressions, which
need the full sample to mean anything.

scripts/verify_dashboard.py checks this file: keep the firm table as the first
st.dataframe, the firm picker as the first st.selectbox, the 10-K quote in
st.info, the "Abnormal return, Apr 3–4" metric, and the hand-check sentence.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import statsmodels.formula.api as smf
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "data" / "processed" / "tariff_firms.csv"
FAKE = ROOT / "data" / "toy" / "tariff_firms_FAKE.csv"
REPO = "https://github.com/charliegrippo1/Team-Cinco-Final-Project"

MIN_FOR_REGRESSIONS = 30   # below this, sector dummies eat the degrees of freedom
MAX_FOR_FIRM_BARS = 40     # up to this many firms, the overview shows one bar per firm

EXPOSURE_LABELS = {0: "0 None", 1: "1 Low", 2: "2 Moderate", 3: "3 High", 4: "4 Very high"}
# Grey for "none", then light-to-dark red as exposure rises
EXPOSURE_COLORS = {"0 None": "#b8bcc2", "1 Low": "#f4b6a6", "2 Moderate": "#e8806a",
                   "3 High": "#c9412f", "4 Very high": "#7f1d12"}
SECTOR_COLORS = px.colors.qualitative.Safe
TEMPLATE = "plotly_white"

st.set_page_config(page_title="Who lost on Liberation Day?", page_icon="📉", layout="wide")


# ---------------------------------------------------------------- data
@st.cache_data
def load_data() -> tuple[pd.DataFrame, bool]:
    is_fake = not REAL.exists()
    df = pd.read_csv(FAKE if is_fake else REAL, dtype={"cik": str})
    assert df.ticker.is_unique, "ticker must be unique (one row per firm)"
    df["exposure_label"] = df.exposure_score.map(EXPOSURE_LABELS)
    return df, is_fake


@st.cache_data
def run_regressions(df: pd.DataFrame, outcome: str, with_sectors: bool) -> pd.DataFrame:
    """OLS with robust (HC3) standard errors.
    (1) CAR on exposure; (2) CAR on sector dummies only; (3) both.
    Model 3 vs 2 answers the auditor's question: does the 10-K exposure
    measure tell us anything beyond which sector a firm is in?"""
    specs = {"(1) Exposure only": f"{outcome} ~ exposure_score"}
    if with_sectors:
        specs["(2) Sector dummies only"] = f"{outcome} ~ C(gics_sector)"
        specs["(3) Exposure + sector dummies"] = f"{outcome} ~ exposure_score + C(gics_sector)"
    rows = []
    for name, formula in specs.items():
        fit = smf.ols(formula, data=df).fit(cov_type="HC3")
        has_exp = "exposure_score" in fit.params
        rows.append({
            "Model": name,
            "Exposure coef (pp per point)": fit.params.get("exposure_score", np.nan),
            "Std. error": fit.bse.get("exposure_score", np.nan) if has_exp else np.nan,
            "t-stat": fit.tvalues.get("exposure_score", np.nan) if has_exp else np.nan,
            "p-value": fit.pvalues.get("exposure_score", np.nan) if has_exp else np.nan,
            "R²": fit.rsquared,
            "N": int(fit.nobs),
        })
    out = pd.DataFrame(rows)
    num = out.columns.drop("Model")
    out[num] = out[num].astype(float)
    return out


def style_fig(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(template=TEMPLATE, height=height, margin=dict(t=30, b=10, l=10, r=10),
                      font=dict(size=13), legend=dict(title=None))
    return fig


df_all, is_fake = load_data()
has_mm = "car_mm_pp" in df_all and df_all.car_mm_pp.notna().any()

# ---------------------------------------------------------------- sidebar
st.sidebar.header("Filters")
sectors = sorted(df_all.gics_sector.unique())
picked = st.sidebar.multiselect("Sector", sectors, default=[], placeholder="All sectors")
if has_mm:
    outcome_label = st.sidebar.radio(
        "Abnormal return measure",
        ["Market-adjusted (stock − SPY)", "Market model (beta-adjusted)"],
        help="Market-adjusted assumes every stock has beta = 1. The market model estimates each firm's beta from the year before.",
    )
    outcome = "car_pp" if outcome_label.startswith("Market-adjusted") else "car_mm_pp"
else:
    outcome = "car_pp"
cap_max = int(np.ceil(df_all.mktcap_usd_bn.quantile(0.9) / 10) * 10) or 100
min_cap = st.sidebar.slider("Minimum market cap ($bn)", 0, cap_max, 0, step=max(cap_max // 20, 1))

mask = df_all.mktcap_usd_bn >= min_cap
if picked:
    mask &= df_all.gics_sector.isin(picked)
df = df_all[mask].dropna(subset=[outcome])
n = len(df)

st.sidebar.caption(f"Showing **{n}** of {len(df_all)} firms")
st.sidebar.divider()
st.sidebar.markdown(
    f"**Data:** 10-Ks from SEC EDGAR, prices from Yahoo Finance.  \n"
    f"[Code and data on GitHub]({REPO})"
)

# ---------------------------------------------------------------- header
if is_fake:
    st.error(
        "**FAKE DATA.** Every firm and number on this page is randomly generated "
        "(`scripts/make_toy_data.py`) so we can build the dashboard before the real data is ready. "
        "Do not interpret any result.", icon="⚠️",
    )

st.title("Who lost on Liberation Day?")
st.markdown(
    "On **April 2, 2025**, after the market closed, the US announced sweeping new tariffs. "
    "We ask: **did firms whose own 10-Ks reveal more dependence on imports and China fall more** "
    "over the next two trading days?"
)
small = len(df_all) < MIN_FOR_REGRESSIONS
if small and not is_fake:
    st.info(
        f"**Preliminary sample: {len(df_all)} firms.** The full S&P 500 run is in progress. "
        "Until then, each firm is shown individually and the sector-control regressions are held back.",
        icon="🧪",
    )

tab_overview, tab_method, tab_results, tab_explore = st.tabs(
    ["Overview", "Methodology", "Results", "Explore a firm"]
)

if n == 0:
    for tab in (tab_overview, tab_results):
        with tab:
            st.warning("No firms match the filters. Clear the sector filter or lower the market-cap minimum.")

# ---------------------------------------------------------------- overview
with tab_overview:
    if n > 0:
        mkt_2day = ((1 + df_all.mkt_apr3_pct.iloc[0] / 100) * (1 + df_all.mkt_apr4_pct.iloc[0] / 100) - 1) * 100
        hc_all = df_all.dropna(subset=["hand_score"])
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Firms shown", f"{n}")
        c2.metric("S&P 500 (SPY), Apr 3–4", f"{mkt_2day:.1f}%", help="SPY's compounded two-day return")
        c3.metric("Avg return vs. SPY", f"{df[outcome].mean():+.2f} pp",
                  help="Average of each firm's two-day return minus SPY's, in percentage points")
        if len(hc_all):
            exact_n = int((hc_all.hand_score == hc_all.exposure_score).sum())
            c4.metric("AI score matched a human", f"{exact_n} of {len(hc_all)}",
                      help="Blind hand-check: a teammate scored these 10-Ks without seeing the AI's score")
        else:
            c4.metric("Avg exposure score", f"{df.exposure_score.mean():.1f} / 4")

        if n <= MAX_FOR_FIRM_BARS:
            st.subheader("Each firm's two-day return vs. the market")
            bars = df.sort_values(outcome)
            fig = px.bar(
                bars, x=outcome, y="ticker", orientation="h", color="exposure_label",
                color_discrete_map=EXPOSURE_COLORS,
                category_orders={"exposure_label": list(EXPOSURE_LABELS.values()), "ticker": bars.ticker.tolist()},
                hover_data={"company": True, outcome: ":.2f", "exposure_label": True, "ticker": False},
                labels={outcome: "Return relative to SPY, Apr 3–4 (percentage points)", "ticker": "",
                        "exposure_label": "10-K exposure score"},
            )
            fig.add_vline(x=0, line_color="#444", line_width=1)
            st.plotly_chart(style_fig(fig, 120 + 34 * n), width="stretch")
            st.caption("Bars to the left of zero fell more than the market. Color is the AI's 0–4 tariff-exposure score from the firm's 10-K.")
        else:
            st.subheader("Average return by exposure score")
            means = (df.groupby("exposure_label")[outcome].agg(["mean", "sem", "count"])
                     .reindex(list(EXPOSURE_LABELS.values())).dropna(subset=["count"]).reset_index())
            fig = go.Figure(go.Bar(
                x=[f"{lab}<br>(n={int(c)})" for lab, c in zip(means.exposure_label, means["count"])],
                y=means["mean"], error_y=dict(type="data", array=1.96 * means["sem"].fillna(0), color="#555"),
                marker_color=[EXPOSURE_COLORS[l] for l in means.exposure_label],
            ))
            fig.update_layout(xaxis_title="10-K tariff exposure score (AI, 0–4)",
                              yaxis_title="Avg return vs. SPY, Apr 3–4 (pp)")
            st.plotly_chart(style_fig(fig, 420), width="stretch")
            st.caption("Bars show the average; lines are 95% confidence intervals.")

        if n >= 3:
            r = df[["exposure_score", outcome]].corr().iloc[0, 1]
            st.markdown(
                f"**So far:** across these {n} firms, the correlation between exposure score and return is "
                f"**{r:+.2f}**."
                + (" With this few firms, that number can swing a lot with one firm, so it is not a finding yet."
                   if n < MIN_FOR_REGRESSIONS else "")
            )

# ---------------------------------------------------------------- methodology
with tab_method:
    st.subheader("Timeline and day 0")
    st.markdown(
        """
| Date | What happened | Role in our study |
|---|---|---|
| Before Apr 2, 2025 | Firms file 10-Ks | Only 10-Ks filed **before** the event are scored |
| Wed Apr 2, ~4:00pm ET | Tariffs announced **after the close** | Event |
| Thu Apr 3 | First trading day after news | **Day 0** |
| Fri Apr 4 | Second day (China retaliation announced) | Day +1, end of window |
| Wed Apr 9, ~1:20pm ET | 90-day pause announced during trading | Stretch: second event |
"""
    )
    st.subheader("Pipeline")
    st.markdown(
        """
1. **Universe:** S&P 500 members as of April 2, 2025, from SPY's SEC holdings filing (not today's list, to avoid survivorship bias).
2. **10-Ks:** For each firm, the latest 10-K filed before April 2, 2025, from SEC EDGAR (Items 1, 1A and 7).
3. **Exposure score:** An AI model reads the 10-K and scores tariff exposure 0–4 with a fixed rubric (below), quoting its evidence.
4. **Hand check:** A teammate scores the same 10-Ks blind; we report how often they agree with the AI.
5. **Returns:** Daily adjusted closes. Abnormal return = stock return − SPY return, summed over Apr 3–4.
6. **Regression:** Return on exposure, with and without sector dummies, using robust standard errors.
"""
    )
    st.subheader("Exposure rubric")
    st.table(pd.DataFrame({
        "Score": list(EXPOSURE_LABELS.values()),
        "Meaning": [
            "Domestic; no meaningful imports or foreign supply chain",
            "Boilerplate mention of trade policy only",
            "Real but limited reliance on imported inputs or foreign sales",
            "Material dependence on imports or foreign manufacturing",
            "Core business built on imports, or large explicit China exposure",
        ],
    }).set_index("Score"))

    if df_all.hand_score.notna().any():
        hc = df_all.dropna(subset=["hand_score"])
        exact = (hc.hand_score == hc.exposure_score).mean()
        within1 = ((hc.hand_score - hc.exposure_score).abs() <= 1).mean()
        st.subheader("Hand check of the AI scores")
        st.markdown(f"On **{len(hc)}** hand-scored firms, the LLM matched exactly **{exact:.0%}** of the time and was within one point **{within1:.0%}** of the time.")
        st.table(
            hc.assign(**{"AI score": hc.exposure_score.astype(int), "Hand score": hc.hand_score.astype(int),
                         "Difference": (hc.hand_score - hc.exposure_score).astype(int)})
            [["ticker", "AI score", "Hand score", "Difference"]].sort_values("ticker")
            .rename(columns={"ticker": "Ticker"}).set_index("Ticker")
        )

    st.subheader("Threats to validity")
    st.markdown(
        """
- **AI already knowing the outcome:** the model may know which firms fell in April 2025. It sees only 10-K text and the rubric, and a re-run with company names hidden tests whether that changes the scores.
- **Is exposure just industry?** The sector-dummy regressions test whether exposure still matters after controlling for sector.
- **Missing firms:** firms whose 10-K text could not be extracted are not random (several big industrials are among them).
- **Day-0 timing:** the announcement came after the close, so April 2 returns do not include the news.
- **Other news:** China announced retaliatory tariffs on April 4, inside our window.
- **Beta = 1 assumption:** the market-adjusted return assumes every stock moves one-for-one with SPY.
"""
    )

# ---------------------------------------------------------------- results
with tab_results:
    if n > 0:
        st.subheader("Exposure vs. return")
        plot_df = df.assign(
            exposure_jitter=df.exposure_score + np.random.default_rng(0).uniform(-0.15, 0.15, n),
            # log scale so a $3 trillion firm doesn't hide a $10 billion one
            dot_size=np.log10(df.mktcap_usd_bn.clip(lower=1)) + 0.5,
        )
        fig = px.scatter(
            plot_df, x="exposure_jitter", y=outcome, color="gics_sector",
            size="dot_size", size_max=30 if n <= MAX_FOR_FIRM_BARS else 16, opacity=0.85,
            color_discrete_sequence=SECTOR_COLORS,
            text="ticker" if n <= MAX_FOR_FIRM_BARS else None,
            hover_name="ticker",
            hover_data={"company": True, "exposure_score": True, outcome: ":.2f",
                        "mktcap_usd_bn": ":.1f", "exposure_jitter": False, "gics_sector": False, "dot_size": False},
            labels={"exposure_jitter": "10-K tariff exposure score (AI, 0–4)",
                    outcome: "Return vs. SPY, Apr 3–4 (pp)", "gics_sector": "Sector",
                    "mktcap_usd_bn": "Market cap ($bn)"},
        )
        if n <= MAX_FOR_FIRM_BARS:
            fig.update_traces(textposition="top center", textfont_size=12, selector=dict(mode="markers+text"))
        if n >= 3 and df.exposure_score.nunique() > 1:
            b = np.polyfit(df.exposure_score, df[outcome], 1)
            xs = np.array([-0.3, 4.3])
            fig.add_trace(go.Scatter(x=xs, y=b[1] + b[0] * xs, mode="lines", name="Best-fit line",
                                     line=dict(color="#333", dash="dash", width=1.5)))
        fig.add_hline(y=0, line_color="#999", line_width=1)
        fig.update_xaxes(range=[-0.5, 4.5], tickvals=list(EXPOSURE_LABELS), ticktext=list(EXPOSURE_LABELS.values()))
        st.plotly_chart(style_fig(fig, 540), width="stretch")
        st.caption("Each dot is a firm; bigger dots are bigger companies (log scale). Points are nudged sideways slightly so they don't overlap.")

        st.subheader("Firm table")
        table = df[["ticker", "company", "gics_sector", "exposure_score", "hand_score", outcome]].sort_values(outcome)
        if outcome != "car_pp":
            table = table.join(df[["car_pp"]])
        st.dataframe(
            table, hide_index=True, width="stretch",
            column_config={
                "ticker": "Ticker", "company": "Company", "gics_sector": "Sector",
                "exposure_score": st.column_config.NumberColumn("AI score", format="%d"),
                "hand_score": st.column_config.NumberColumn("Hand score", format="%d"),
                "car_pp": st.column_config.NumberColumn("Return vs. SPY (pp)", format="%+.2f"),
                "car_mm_pp": st.column_config.NumberColumn("Beta-adjusted (pp)", format="%+.2f"),
            },
        )
        st.download_button("Download this table (CSV)", table.to_csv(index=False), "liberation_day_firms.csv")

        st.subheader("Regressions")
        if n < 3:
            st.info("Need at least 3 firms for a regression.")
        else:
            reg = run_regressions(df, outcome, with_sectors=n >= MIN_FOR_REGRESSIONS)
            st.dataframe(
                reg.style.format({
                    "Exposure coef (pp per point)": "{:+.3f}", "Std. error": "{:.3f}",
                    "t-stat": "{:.2f}", "p-value": "{:.3f}", "R²": "{:.3f}", "N": "{:.0f}",
                }, na_rep="—"),
                hide_index=True, width="stretch",
            )
            if n < MIN_FOR_REGRESSIONS:
                st.caption(
                    f"Only the simple regression is shown: with {n} firms there are too few to add sector dummies, "
                    f"and the slope is far from significant. Models with sector controls appear once there are "
                    f"{MIN_FOR_REGRESSIONS}+ firms."
                )
            else:
                st.markdown(
                    "**How to read this:** the exposure coefficient is the extra return (in percentage points) "
                    "for each one-point step up the 0–4 scale. If model (3) has a clearly higher R² than model (2), "
                    "the 10-K measure explains losses that sector alone does not."
                )

        if n >= MIN_FOR_REGRESSIONS:
            st.subheader("By sector")
            by_sector = (df.groupby("gics_sector")
                         .agg(firms=("ticker", "size"), avg_exposure=("exposure_score", "mean"), avg_car=(outcome, "mean"))
                         .reset_index())
            fig2 = px.scatter(by_sector, x="avg_exposure", y="avg_car", size="firms", text="gics_sector",
                              labels={"avg_exposure": "Avg exposure score", "avg_car": "Avg return vs. SPY (pp)"})
            fig2.update_traces(textposition="top center", marker_color="#c9412f")
            st.plotly_chart(style_fig(fig2, 460), width="stretch")

# ---------------------------------------------------------------- explore
with tab_explore:
    st.subheader("Look up a firm")
    options = df_all.sort_values("ticker").apply(lambda r: f"{r.ticker} — {r.company}", axis=1).tolist()
    choice = st.selectbox("Firm", options)
    firm = df_all[df_all.ticker == choice.split(" — ")[0]].iloc[0]

    others = df_all[outcome].dropna()
    pct = (others > firm[outcome]).sum() / max(len(others) - 1, 1)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Exposure score", EXPOSURE_LABELS[firm.exposure_score])
    c2.metric("Abnormal return, Apr 3–4", f"{firm[outcome]:+.2f} pp")
    c3.metric("Peers with higher return", f"{pct:.0%}")
    c4.metric("Market cap", f"${firm.mktcap_usd_bn:,.1f}bn")

    hand = firm.get("hand_score")
    st.markdown(
        f"**Sector:** {firm.gics_sector}"
        + (f" · **Hand score:** {int(hand)}" if pd.notna(hand) else "")
    )
    st.markdown(f"**Evidence from the 10-K** (filed {firm.tenk_filing_date}):")
    st.info(firm.exposure_evidence)
    if "filing_url" in firm and pd.notna(firm.filing_url):
        st.markdown(f"[Read the cited 10-K on SEC EDGAR]({firm.filing_url})")
    else:
        st.markdown(
            f"[Open this firm's filings on EDGAR](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={firm.cik}&type=10-K)"
            + (" (fake CIK, link won't work)" if is_fake else "")
        )

st.divider()
st.caption(f"Team Cinco · FIN 331 Fall 2026 · [Code and data]({REPO})")
