"""Team Cinco dashboard: Who lost on Liberation Day?

Run locally:  streamlit run dashboard/app.py

Data: reads data/processed/tariff_firms.csv (the real pipeline output) if it
exists. Otherwise it falls back to data/toy/tariff_firms_FAKE.csv and shows a
red FAKE DATA banner. Column definitions: docs/DATA_CONTRACT.md.
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

EXPOSURE_LABELS = {0: "0 None", 1: "1 Low", 2: "2 Moderate", 3: "3 High", 4: "4 Very high"}

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
def run_regressions(df: pd.DataFrame, outcome: str) -> pd.DataFrame:
    """Three models, robust (HC3) standard errors:
    (1) CAR on exposure, (2) CAR on sector dummies only, (3) both.
    Model 3 vs 2 answers the auditor's question: does the 10-K exposure
    measure tell us anything beyond which sector a firm is in?"""
    specs = {
        "(1) Exposure only": f"{outcome} ~ exposure_score",
        "(2) Sector dummies only": f"{outcome} ~ C(gics_sector)",
        "(3) Exposure + sector dummies": f"{outcome} ~ exposure_score + C(gics_sector)",
    }
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


df_all, is_fake = load_data()

# ---------------------------------------------------------------- sidebar
st.sidebar.header("Filters")
sectors = sorted(df_all.gics_sector.unique())
picked = st.sidebar.multiselect("Sector", sectors, default=sectors)
outcome_label = st.sidebar.radio(
    "Abnormal return measure",
    ["Market-adjusted CAR (stock − SPY)", "Market-model CAR (beta-adjusted)"],
    help="Market-adjusted assumes every stock has beta = 1. The market model estimates each firm's beta from the year before.",
)
outcome = "car_pp" if outcome_label.startswith("Market-adjusted") else "car_mm_pp"
min_cap = st.sidebar.slider("Minimum market cap ($bn)", 0, 100, 0, step=5)

df = df_all[df_all.gics_sector.isin(picked) & (df_all.mktcap_usd_bn >= min_cap)].dropna(subset=[outcome])

st.sidebar.caption(f"{len(df)} of {len(df_all)} firms shown")

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
    "We ask: **did firms whose own 10-Ks reveal more dependence on imports and China fall more** over the next two trading days?"
)

tab_overview, tab_method, tab_results, tab_explore = st.tabs(
    ["Overview", "Methodology", "Results", "Explore a firm"]
)

# ---------------------------------------------------------------- overview
with tab_overview:
    if len(df) < 10:
        st.warning("Too few firms selected. Widen the filters.")
    else:
        reg = run_regressions(df, outcome)
        slope = reg.loc[0, "Exposure coef (pp per point)"]
        gap = df.loc[df.exposure_score == 4, outcome].mean() - df.loc[df.exposure_score == 0, outcome].mean()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Firms", f"{len(df)}")
        c2.metric("Avg 2-day abnormal return", f"{df[outcome].mean():.2f} pp")
        c3.metric("Each +1 exposure point", f"{slope:+.2f} pp", help="Slope from model (1) on the Results tab")
        c4.metric("Very high vs. none", f"{gap:+.2f} pp", help="Avg CAR of score-4 firms minus score-0 firms")

        st.subheader("The headline chart")
        means = (
            df.groupby("exposure_label")[outcome]
            .agg(["mean", "sem", "count"])
            .reset_index()
            .sort_values("exposure_label")
        )
        fig = go.Figure(go.Bar(
            x=[f"{lab}<br>(n={n})" for lab, n in zip(means.exposure_label, means["count"])],
            y=means["mean"],
            error_y=dict(type="data", array=1.96 * means["sem"], color="#555"),
            marker_color="#c0392b",
        ))
        fig.update_layout(
            xaxis_title="10-K tariff exposure score (LLM, 0–4)",
            yaxis_title="Avg abnormal return, Apr 3–4 (pp)",
            height=420, margin=dict(t=20),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Bars show the average; lines are 95% confidence intervals.")

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
1. **Universe:** S&P 500 members as of April 2, 2025 (not today's list, to avoid survivorship bias).
2. **10-Ks:** For each firm, the latest 10-K filed before April 2, 2025, from SEC EDGAR.
3. **Exposure score:** An LLM reads the 10-K and scores tariff exposure 0–4 with a fixed rubric (below), quoting its evidence.
4. **Hand check:** Teammates score a random sample blind; we report how often they agree with the LLM.
5. **Returns:** Daily adjusted closes from yfinance. Abnormal return = stock return − SPY return, summed over Apr 3–4.
6. **Regression:** CAR on exposure, with and without sector dummies, using robust standard errors.
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
    st.subheader("Threats to validity")
    st.markdown(
        """
- **LLM leakage:** the model may already "know" which firms fell in April 2025. We never show it dates or returns, and we re-score with company names removed to test whether that matters.
- **Is exposure just industry?** Model (3) on the Results tab tests whether exposure still matters after controlling for sector.
- **Day-0 timing:** the announcement came after the close, so April 2 returns do not include the news.
- **Other news:** China announced retaliatory tariffs on April 4, inside our window.
- **Beta = 1 assumption:** the market-adjusted CAR assumes every stock moves one-for-one with SPY. The sidebar lets you switch to a beta-adjusted version.
"""
    )
    if df_all.hand_score.notna().any():
        hc = df_all.dropna(subset=["hand_score"])
        exact = (hc.hand_score == hc.exposure_score).mean()
        within1 = ((hc.hand_score - hc.exposure_score).abs() <= 1).mean()
        st.subheader("Hand check of LLM scores")
        st.markdown(f"On **{len(hc)}** hand-scored firms, the LLM matched exactly **{exact:.0%}** of the time and was within one point **{within1:.0%}** of the time.")

# ---------------------------------------------------------------- results
with tab_results:
    if len(df) < 10:
        st.warning("Too few firms selected. Widen the filters.")
    else:
        st.subheader("Exposure vs. abnormal return")
        plot_df = df.assign(
            exposure_jitter=df.exposure_score + np.random.default_rng(0).uniform(-0.18, 0.18, len(df))
        )
        fig = px.scatter(
            plot_df, x="exposure_jitter", y=outcome, color="gics_sector",
            size="mktcap_usd_bn", size_max=28, opacity=0.75,
            color_discrete_sequence=px.colors.qualitative.Safe,
            hover_name="ticker",
            hover_data={"company": True, "exposure_score": True, outcome: ":.2f",
                        "mktcap_usd_bn": ":.1f", "exposure_jitter": False, "gics_sector": False},
            labels={"exposure_jitter": "10-K tariff exposure score (0–4, jittered)",
                    outcome: "Abnormal return, Apr 3–4 (pp)", "gics_sector": "Sector"},
            height=560,
        )
        b = np.polyfit(df.exposure_score, df[outcome], 1)
        xs = np.array([0, 4])
        fig.add_trace(go.Scatter(x=xs, y=b[1] + b[0] * xs, mode="lines", name="OLS fit",
                                 line=dict(color="black", dash="dash")))
        fig.update_xaxes(tickvals=list(EXPOSURE_LABELS), ticktext=list(EXPOSURE_LABELS.values()))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Each dot is a firm; dot size is market cap. Points are spread sideways slightly so they don't overlap.")

        st.subheader("Regressions")
        reg = run_regressions(df, outcome)
        st.dataframe(
            reg.style.format({
                "Exposure coef (pp per point)": "{:.3f}", "Std. error": "{:.3f}",
                "t-stat": "{:.2f}", "p-value": "{:.3f}", "R²": "{:.3f}",
            }, na_rep="—"),
            hide_index=True, use_container_width=True,
        )
        st.markdown(
            "**How to read this:** the exposure coefficient is the extra abnormal return (in percentage points) "
            "for each one-point step up the 0–4 scale. If model (3) has a clearly higher R² than model (2), "
            "the 10-K measure explains losses that sector alone does not."
        )

        st.subheader("By sector")
        by_sector = (
            df.groupby("gics_sector")
            .agg(firms=("ticker", "size"), avg_exposure=("exposure_score", "mean"), avg_car=(outcome, "mean"))
            .sort_values("avg_car")
            .reset_index()
        )
        fig2 = px.scatter(by_sector, x="avg_exposure", y="avg_car", size="firms", text="gics_sector",
                          labels={"avg_exposure": "Avg exposure score", "avg_car": "Avg abnormal return (pp)"},
                          height=460)
        fig2.update_traces(textposition="top center")
        st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------- explore
with tab_explore:
    st.subheader("Look up a firm")
    options = df_all.sort_values("ticker").apply(lambda r: f"{r.ticker} — {r.company}", axis=1).tolist()
    choice = st.selectbox("Firm", options)
    firm = df_all[df_all.ticker == choice.split(" — ")[0]].iloc[0]

    pct = (df_all[outcome] < firm[outcome]).mean()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Exposure score", EXPOSURE_LABELS[firm.exposure_score])
    c2.metric("Abnormal return, Apr 3–4", f"{firm[outcome]:+.2f} pp")
    c3.metric("Did worse than", f"{1 - pct:.0%} of firms")
    c4.metric("Market cap", f"${firm.mktcap_usd_bn:,.1f}bn")

    st.markdown(f"**Sector:** {firm.gics_sector}")
    st.markdown(f"**Evidence from the 10-K** (filed {firm.tenk_filing_date}):")
    st.info(firm.exposure_evidence)
    st.markdown(
        f"[Open this firm's filings on EDGAR](https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={firm.cik}&type=10-K)"
        + (" (fake CIK, link won't work)" if is_fake else "")
    )

    st.subheader("All firms")
    show = df[["ticker", "company", "gics_sector", "mktcap_usd_bn", "exposure_score", "car_pp", "car_mm_pp"]]
    st.dataframe(show.sort_values(outcome if outcome in show else "car_pp"), hide_index=True, use_container_width=True)
    st.download_button("Download filtered data (CSV)", show.to_csv(index=False), "liberation_day_firms.csv")

st.divider()
st.caption("Team Cinco · FIN 331 Fall 2026 · Code: github.com/charliegrippo1/Team-Cinco-Final-Project")
