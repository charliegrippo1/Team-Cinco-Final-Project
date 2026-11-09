# Data contract: the final dataset the dashboard reads

**Owner:** Gunnar (dashboard / product manager). **Last updated:** 2026-11-03.

This file says exactly what one row of our final dataset looks like, so the data pipeline (10-K scoring + returns) and the dashboard can be built in parallel. If the pipeline produces a file that matches this contract, the dashboard works with no changes.

- **Real file (pipeline writes it):** `data/processed/tariff_firms.csv`
- **Fake file (for building the app now):** `data/toy/tariff_firms_FAKE.csv`, made by `scripts/make_toy_data.py`

The app loads the real file if it exists and otherwise falls back to the fake one, with a red "FAKE DATA" banner.

## Unit of observation

**One row = one firm** in the S&P 500 as of **April 2, 2025** (the membership on the event date, not today's, to avoid survivorship bias). Key: `ticker`, which must be unique (`assert df.ticker.is_unique`).

## Event timing

| Event | Announcement | Day 0 | Window |
|---|---|---|---|
| Liberation Day tariffs | Wed Apr 2, 2025, about 4:00pm ET, **after the close** | Thu Apr 3, 2025 | Apr 3 – Apr 4 (2 trading days) |
| 90-day pause (stretch) | Wed Apr 9, 2025, about 1:20pm ET, **during trading** | Wed Apr 9, 2025 | Apr 9 only (day 0) |

## Columns

| Column | Type | Required? | Definition |
|---|---|---|---|
| `ticker` | str | yes | Ticker as of April 2025. Unique key. |
| `company` | str | yes | Company name. |
| `cik` | str | yes | SEC CIK (10-digit, zero-padded). Links to EDGAR. |
| `gics_sector` | str | yes | One of the 11 GICS sectors, as of April 2025. Used for industry controls and the dashboard filter. |
| `mktcap_usd_bn` | float | yes | Market cap in $ billions at the **Mar 31, 2025** close (before the event). |
| `tenk_filing_date` | date | yes | Filing date of the 10-K we scored. **Must be before 2025-04-02.** |
| `tenk_accession` | str | yes | EDGAR accession number of that 10-K (provenance). |
| `exposure_score` | int 0–4 | yes | LLM-scored tariff exposure from the 10-K text, using the rubric below. |
| `exposure_evidence` | str | yes | A short quote from the 10-K that justifies the score. |
| `hand_score` | int 0–4 | for the checked sample | A teammate's score for the same 10-K, done **without** looking at the LLM's score. Blank if not hand-checked. |
| `ret_apr3_pct`, `ret_apr4_pct` | float | yes | Stock daily return (%) from adjusted closes. |
| `mkt_apr3_pct`, `mkt_apr4_pct` | float | yes | Market return (%) on the same days. Benchmark: SPY. |
| `car_pp` | float | yes | **Main outcome.** Sum over Apr 3–4 of (stock return − SPY return), in percentage points. |
| `car_mm_pp` | float | nice to have | Same window, but abnormal return = stock − (alpha + beta × SPY), with alpha and beta estimated on the 250 trading days ending 2025-02-28. |
| `car_pause_pp` | float | stretch | Stock − SPY on Apr 9, 2025. |

Percentages are in percent, so −3.2 means −3.2%, not −0.032.

## Exposure rubric (0–4)

The LLM reads the 10-K (Item 1, Item 1A risk factors, Item 7 MD&A) and answers: *how much do this firm's costs or revenues depend on imported goods, foreign manufacturing, or China?*

| Score | Meaning | Example evidence |
|---|---|---|
| 0 | None: domestic services, no meaningful imports or foreign supply chain | "Substantially all of our operations are in the United States." |
| 1 | Low: some mention of trade or tariffs, only boilerplate | Generic risk factor about "changes in trade policy." |
| 2 | Moderate: real but limited reliance on imported inputs or foreign sales | "Certain components are sourced from suppliers in Asia." |
| 3 | High: material dependence on imports or foreign manufacturing | "A majority of our products are manufactured by third parties in Asia." |
| 4 | Very high: core business built on imported goods, or explicit large China exposure | "Substantially all of our products are manufactured in China." |

**LLM leakage rule.** The prompt gives the model only the 10-K text and the rubric, never the date, the word "Liberation Day," or any stock returns. We also record the model name and version in `outputs/llm_run_log.csv`. The leakage test: re-score with company names and tickers replaced by "the Company" and check that the scores barely change.

## Checks the pipeline must pass before handing off

```python
assert df.ticker.is_unique
assert (pd.to_datetime(df.tenk_filing_date) < "2025-04-02").all()
assert df.exposure_score.between(0, 4).all()
assert df.car_pp.notna().mean() > 0.95   # say why any are missing
```
