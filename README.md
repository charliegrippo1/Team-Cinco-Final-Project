# Data Science & AI for Finance — Final Project Kickoff

> **Status:** Proposal and limited feasibility check only; no production pipeline or dashboard has been built. Research checked October 15, 2026.

## Table of contents

- [Recommendation and ranking](#recommendation-and-ranking)
- [Shared conventions](#shared-conventions)
- [Idea 1 — Federal Reserve Decisions and Sector Stock Returns](#idea-1--federal-reserve-decisions-and-sector-stock-returns)
- [Idea 2 — Earnings Surprises and Abnormal Stock Returns](#idea-2--earnings-surprises-and-abnormal-stock-returns)
- [Idea 3 — SEC 10-K Risk Factor Changes and Future Stock Risk](#idea-3--sec-10-k-risk-factor-changes-and-future-stock-risk)
- [Fed feasibility proof of concept — actual downloaded data](#fed-feasibility-proof-of-concept--actual-downloaded-data)

## Recommendation and ranking

**Recommend Idea 1: Federal Reserve Decisions and Sector Stock Returns.** It combines a clear finance question, a small ETF universe, public announcement records, obtainable daily prices, and a compelling dashboard. A one-meeting check succeeded, and a public Fed surprise-data download was verified. The main challenge is interpretation, not basic price collection. Start as a retrospective event study; do not present it as a causal estimate or a tradable prediction system.

Ratings are our project-planning judgments, not measured benchmarks. Availability, interview value, and feasibility: 5 = strongest. Difficulty: 5 = hardest. Rank 1 is the preferred overall choice.

| Rank | Idea | Data availability | Coding difficulty | Methodological difficulty | Interview value | Overall feasibility |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Fed decisions and sector returns | 4/5 | 2/5 | 4/5 | 5/5 | 4/5 |
| 2 | Earnings surprises and returns | 3/5 | 3/5 | 4/5 | 4/5 | 3/5 |
| 3 | 10-K risk changes and future risk | 4/5 | 5/5 | 5/5 | 5/5 | 2/5 |

The earnings project has an intuitive statistical design but depends on trustworthy historical analyst estimates and release times. SEC filings are public, but extracting comparable risk sections and validating semantic changes makes Idea 3 substantially larger. If the class requires an LLM component, Idea 3 fits most directly; otherwise, Idea 1 offers the best balance of scope, auditability, and interview discussion. Confirm the course rubric before final selection.

## Shared conventions

All nine example rows below are **fictional schema illustrations**, including their dates and values; they are not observations or claims about named securities. Only the separate proof-of-concept section reports downloaded market data.

- Rate changes and return differences use percentage points (pp); 1 pp = 100 basis points (bp). A rate cut from 5.50% to 5.00% is -0.50 pp.
- Returns are percentages. `abnormal_return = day0_return - market_return`, expressed in pp. This is a simple market-adjusted return, not a beta-adjusted estimate.
- Day 0 is the trading session receiving the announcement. For after-close/nontrading-day releases, use the next trading session; record the actual timestamp and timezone.
- `abnormal_return_3d` means the sum of daily ETF/stock-minus-SPY returns over trading days [-1, 0, +1], a three-session cumulative abnormal return (CAR), not a compounded holding-period return difference.
- Preserve missing observations as missing with a reason; never replace missing expectations with zero.

## Idea 1 — Federal Reserve Decisions and Sector Stock Returns

**Research question:** Which stock market sectors react the most to unexpected Federal Reserve interest-rate decisions?

Universe: Technology (XLK), Financials (XLF), Real Estate/REITs (XLRE), Utilities (XLU), Consumer Discretionary (XLY), Industrials (XLI), and Small-cap stocks (IWM). XLF represents broad financials, not banks alone; IWM is a size segment, not a sector. Label these distinctions in the dashboard. Use SPY as the benchmark.

### Example final dataset — fictional

One row per meeting and ETF. `expected_change` is the pre-announcement probability-weighted expected target change, and `surprise = fed_rate_change - expected_change` only when both are available on a consistent basis.

| meeting_date | sector | ticker | fed_rate_change (pp) | expected_change (pp) | surprise (pp) | day0_return (%) | market_return (%) | abnormal_return (pp) | abnormal_return_3d (pp) |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024-09-18 | Technology | XLK | -0.50 | -0.35 | -0.15 | 1.70 | 0.80 | 0.90 | 2.20 |
| 2024-09-18 | Financials | XLF | -0.50 | -0.35 | -0.15 | 0.20 | 0.80 | -0.60 | -0.40 |
| 2024-09-18 | Real Estate | XLRE | -0.50 | -0.35 | -0.15 | 2.10 | 0.80 | 1.30 | 1.60 |

These fictional values intentionally do not describe the real event reported below.

### Required raw data and possible sources

| Raw input | Possible source | Availability / caveat |
| --- | --- | --- |
| Announcement dates, timestamps, policy statements, scheduled/emergency flags | [Federal Reserve FOMC calendar and archives](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) | Public; use statement release, not minutes publication or the first meeting day. |
| Target range before/after each decision | Statements; FRED [DFEDTARU](https://fred.stlouisfed.org/series/DFEDTARU) and [DFEDTARL](https://fred.stlouisfed.org/series/DFEDTARL) | Daily policy settings; reconcile effective dates with announcement dates. Effective funds rates are not the announced target or an expectation. |
| ETF and SPY daily closes, adjusted closes, distributions/splits | Yahoo Finance historical prices; institutional market-data provider if available | XLK and SPY retrieval succeeded; bulk coverage, reliability and permitted use still need checking. |
| Pre-meeting expected target changes and observation times | [CME FedWatch](https://www.cmegroup.com/fedwatch), historical futures snapshots, or a licensed data service | Historical point-in-time access was not demonstrated. Current probabilities cannot substitute for historical snapshots. |
| Alternative high-frequency surprise measure | [SF Fed USMPD](https://www.frbsf.org/research-and-insights/data-and-indicators/us-monetary-policy-event-study-database/) and [Bauer–Swanson series](https://www.frbsf.org/research-and-insights/data-and-indicators/monetary-policy-surprises/) | Public research data; USMPD surprise archive successfully downloaded. Distinguish current-target news from broader policy-path news. |
| Trading sessions, ETF inception dates and classifications | Exchange calendar and fund issuer documentation | Use common coverage; do not backfill an ETF before inception. |

### Main visualization/dashboard

A meeting selector displays announcement time, actual policy change, the chosen surprise definition, and a ranked bar chart of sector abnormal returns. A second chart shows average sector reactions across meetings, with sample counts and uncertainty intervals. Allow separate views of tightening/easing surprises and absolute reaction magnitude; signed averages alone can cancel large opposite reactions. Include a three-day view and visible missing-data flags.

### First auditor challenge

**Did you use the actual announcement timestamp and a valid surprise measure, or simply relabel the announced rate change as unexpected?** Pre-meeting expectations must have been recorded before the announcement. A high-frequency surprise is measured across the announcement and is an explanatory event-study variable, not a predictor available beforehand.

Daily returns also include other news and the press conference. SPY subtraction assumes beta one and measures relative performance; SPY itself responds to the Fed. It does not identify the total causal effect of monetary policy. A later robustness check could estimate a market model using only pre-event observations. Use meeting-level uncertainty/clustering because ETF observations from one meeting are dependent; report multiple-comparison limitations and modest event counts.

### Expectations strategy and defensible fallback

1. **Preferred exact target decomposition:** obtain timestamped probabilities over target outcomes before each meeting. Compute expected change as the probability-weighted post-meeting target midpoint minus the existing midpoint. Subtract from actual midpoint change. Futures-based reconstruction requires within-month day weighting and attention to effective-rate versus target-rate differences; a futures price is not directly an expected meeting change.
2. **Practical research alternative:** evaluate USMPD current-target inputs and documentation; alternatively use its published policy-news factor with a revised question: **Which sectors react most to unexpected FOMC policy news?** Store `surprise_measure`, `surprise_window`, `surprise_units`, and `source_vintage`. Keep literal `expected_change` and target `surprise` missing unless independently supported; do not back them out from a path factor.
3. **Descriptive fallback:** if no defensible surprise series can be aligned, study **sector market-adjusted returns around FOMC announcements**, grouped descriptively by cut/hold/hike. Remove claims about unexpected decisions and causal effects. Never assume every decision was unanticipated.

Published factors can use full-sample estimation and later revisions. Freeze the downloaded vintage for retrospective analysis, disclose that it was unavailable in that form at the historical event, and use expanding/pre-event estimation if making out-of-sample predictive claims. Do not use subsequent ETF returns to construct the surprise score.

## Idea 2 — Earnings Surprises and Abnormal Stock Returns

**Research question:** Do companies that beat analyst EPS expectations earn higher abnormal returns, and does earnings-surprise size predict the size of the stock reaction?

### Example final dataset — fictional

| ticker | announcement_date | announcement_time (ET) | eps_actual (USD/share) | eps_estimate (USD/share) | surprise_pct (%) | day0_return (%) | market_return (%) | abnormal_return (pp) | abnormal_return_3d (pp) |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MSFT | 2024-07-30 | 16:05 after close | 3.70 | 3.55 | 4.23 | 1.80 | 0.60 | 1.20 | 2.10 |
| JPM | 2024-07-12 | 07:00 before open | 4.20 | 4.00 | 5.00 | 0.90 | 0.30 | 0.60 | 0.80 |
| CAT | 2024-08-06 | 06:30 before open | 5.00 | 5.20 | -3.85 | -2.00 | -0.50 | -1.50 | -1.90 |

Define `surprise_pct = 100 * (eps_actual - eps_estimate) / abs(eps_estimate)`; flag zero/near-zero estimates and report dollar surprise separately. Actual and estimated EPS must use matching GAAP/adjusted definitions, share bases, currencies, and fiscal periods.

### Required raw data and possible sources

- **Historical release dates and precise times:** company investor-relations releases plus a historical earnings provider.
- **Actual EPS and pre-release consensus EPS with fiscal period and estimate timestamp:** [Alpha Vantage earnings documentation](https://www.alphavantage.co/documentation/) is a candidate; institutional LSEG or FactSet access could help. API credentials, historical coverage, estimate vintages, and entitlements remain unverified.
- **Adjusted stock and SPY prices, corporate actions, sector labels, and trading calendar:** Yahoo Finance or an institutional market-data provider. Keep a documented universe to assess survivorship bias.

### Main visualization/dashboard

Scatterplot of EPS surprise versus abnormal return, with sector, year, company, and beat/miss filters. Show sample counts, fitted relationships, uncertainty, and outliers. Include a table linking observations to source releases.

### First auditor challenge

**Was Day 0 aligned to the actual release time, and was the consensus estimate genuinely available before the release?** After-close releases generally map to the next trading day. Ambiguous timestamps should be flagged or excluded. Guidance and revenue surprises confound EPS effects; extreme ratios and selection of surviving companies can distort results. Split training/testing chronologically if claiming predictive performance.

## Idea 3 — SEC 10-K Risk Factor Changes and Future Stock Risk

**Research question:** Do major changes in a company's annual 10-K Risk Factors section predict higher subsequent stock volatility or weaker stock performance?

### Example final dataset — fictional

| ticker | filing_date | previous_filing_date | new_risks | removed_risks | risk_change_score | future_90d_return (%) | future_90d_volatility (%) |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| TSLA | 2024-01-29 | 2023-01-30 | 9 | 2 | 0.51 | -12.10 | 46.40 |
| MSFT | 2024-07-30 | 2023-07-27 | 3 | 1 | 0.18 | 4.20 | 21.80 |
| JPM | 2024-02-16 | 2023-02-21 | 6 | 3 | 0.37 | -3.60 | 28.10 |

The proposed score ranges from 0 to 1, with larger values indicating more substantive risk change; its scoring rubric must be defined and validated before use. Define 90d as **90 trading sessions**: enter at the first close strictly after public acceptance, then measure close-to-close returns over the following 90 sessions. Volatility is sample standard deviation of daily log returns times sqrt(252), expressed as a percent. Record the exact start/end dates and leave incomplete future windows missing.

### Required raw data and possible sources

- **Consecutive annual 10-K filings, accession IDs, CIK/ticker mapping, and public acceptance timestamps:** [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) and original filing HTML. Follow [SEC developer access guidance](https://www.sec.gov/about/developer-resources).
- **Extracted Item 1A sections and stable text/paragraph IDs:** derive from original filings; handle tables of contents, formatting changes, amendments, and missing sections explicitly.
- **Stock and SPY adjusted prices, corporate actions, trading calendar, and historical universe:** Yahoo Finance or institutional market data.
- **Derived features:** added/removed risk units, section-length change, liquidity/debt, competition, litigation/regulation and cybersecurity language, plus an optional text-model score.

### Main visualization/dashboard

Company selector with side-by-side annual Risk Factors text, highlighted additions/removals, and evidence excerpts for each scored change. A second view plots risk-change score against future volatility or return, with year/sector filters and sample sizes.

### First auditor challenge

**Could future outcomes or a model's later knowledge influence the risk score?** Use only the two filings available by the current acceptance timestamp, fixed prompts/rules, and source-grounded evidence. Restricting an LLM prompt does not guarantee removal of pretrained future knowledge. Prefer deterministic text-difference features as the baseline; validate any LLM judgments on blinded samples and retain prompts/model versions. Semantic rewording is not automatically a new risk. Overlapping outcomes require careful evaluation, and the future-risk window must start after publication, not the fiscal year end.

## Fed feasibility proof of concept — actual downloaded data

### Event and limited scope

The [official September 18, 2024 FOMC statement](https://www.federalreserve.gov/newsevents/pressreleases/monetary20240918a.htm) was released at **14:00 EDT**, during the regular trading session. It lowered the target range by **0.50 pp** to **4.75%–5.00%**. Day 0 is September 18; the prior trading close is September 17. This check uses just XLK and SPY and does not estimate a sector-wide relationship.

### Retrieval and observed prices

Yahoo Finance chart responses were downloaded on October 15, 2026 for September 16–19, 2024. Both requests returned HTTP 200 after network access was granted:

- [XLK query](https://query1.finance.yahoo.com/v8/finance/chart/XLK?period1=1726444800&period2=1726790400&interval=1d)
- [SPY query](https://query1.finance.yahoo.com/v8/finance/chart/SPY?period1=1726444800&period2=1726790400&interval=1d)

Use `chart.result[0].timestamp` to identify sessions and `indicators.adjclose[0].adjclose` for calculations. The query bounds are UTC; interpret daily bar dates using the exchange timezone America/New_York. These are vendor-adjusted historical values as retrieved, not contemporaneous unadjusted quotes. Corporate actions can change historical price levels.

| Session | XLK adjusted close (USD) | SPY adjusted close (USD) |
| --- | ---: | ---: |
| 2024-09-16 | 108.35556030 | 548.46191406 |
| 2024-09-17 | 108.14338684 | 548.68603516 |
| 2024-09-18 | 107.15652466 | 547.05871582 |
| 2024-09-19 | 110.33910370 | 556.39398193 |

Using full precision from the responses:

```text
XLK return = 100 * (107.15652465820312 / 108.14338684082031 - 1)
           = -0.9125497281%
SPY return = 100 * (547.0587158203125 / 548.68603515625 - 1)
           = -0.2965847920%
Simple abnormal return = -0.9125497281 - (-0.2965847920)
                       = -0.6159649362 percentage points
```

XLK underperformed SPY by approximately **0.6160 pp** that day. This demonstrates retrieval, alignment, and arithmetic only. It does not establish that the rate decision caused the difference. The full daily window includes pre-announcement trading and subsequent communications.

### Surprise-data feasibility check

The [SF Fed surprise ZIP](https://www.frbsf.org/wp-content/uploads/monetary-policy-surprises.zip) downloaded successfully. Its `mps.csv` contains `Date, STMT, PC, ME`; the inspected file runs from February 4, 1994 to September 16, 2026, with coverage/missingness still to be audited. The September 18, 2024 row is:

| Date | STMT | PC | ME |
| --- | ---: | ---: | ---: |
| 2024-09-18 | -0.07294959222202342 | 0.03727099083235889 | -0.04632248430544967 |

The archive documentation specifies percentage-point units and normalization to a one-for-one effect on the one-year Treasury yield. These published factors concern statement, press-conference, and combined monetary-event policy news respectively. They are **not literal expected target changes**, and the combined factor should not be assumed to equal the sum of the other two. The provided code uses full-sample factor estimation by default. No R model was run in this proof of concept; these are supplied published outputs. Historical pre-announcement target expectations remain unverified and missing.

### What worked, what failed, and what remains

| Status | Finding |
| --- | --- |
| Worked | Verified the announcement date, time, and actual target cut from the Federal Reserve. |
| Worked | Retrieved XLK and SPY adjusted prices around the event and calculated both returns and their difference. |
| Worked | Downloaded and inspected a public surprise archive with a matching event row. |
| Initial failure, resolved | The first Yahoo request failed DNS resolution under restricted network access; it succeeded after network permission was granted. |
| Viewer failure, resolved by download | Browser research could not render Fed binary download links; direct ZIP retrieval and local inspection succeeded. |
| Not established | Historical point-in-time expected target changes, validated MP1/current-target construction, and an independent second price-source reconciliation. |
| Repository inspection | The supplied GitHub repository was cloned and found to contain no commits, README, or project instructions. This README is the initial project document. |

### Next steps before scaling

- [ ] Agree on a fixed sample period (a candidate is 2016–2025, subject to common coverage).
- [ ] Audit the FOMC event calendar, including holds and emergency meetings.
- [ ] Validate all seven ETFs and SPY across common sessions.
- [ ] Document corporate-action treatment.
- [ ] Inspect missing surprise observations and units.
- [ ] Obtain timestamped expectations, or select and label a defensible published shock proxy.
- [ ] Record source URLs, retrieval dates, versions, and missing-data reasons.
- [ ] Check access terms/rate limits and retain source snapshots.
- [ ] Validate event windows on a small manually reviewed sample before broader data collection.

The one-event check supports **conditional feasibility**, not readiness for production. The next decision is the surprise definition. No production pipeline, fitted prediction model, or dashboard has been built.
