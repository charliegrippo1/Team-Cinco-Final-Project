# v0 fact sheet (raw material for PROPOSAL.md)

> **Carter: finish the blind hand-check (`audits/hand_check_v0_instructions.md`) before
> reading this file.** Sections 2 and 3 show the AI's scores.

Facts only, so each of us can write our proposal section in our own words. Every
number below comes from a file in this repo (path given). **Do not paste from this
file into PROPOSAL.md.** HW8 is checked with Pangram, and the professor wants our
own argument. Numbers as of the v0 run on 2026-11-11 (commit on `charlie/checkpoint-2`).

---

## 1. The question (Gunnar)

- Question as the README states it today: did S&P 500 firms whose annual reports described greater dependence on imports or overseas manufacturing lose more relative to the market after the April 2, 2025 U.S. tariff announcement?
- Event: tariff announcement after the U.S. market close on Wed **April 2, 2025** ("Liberation Day"). China announced retaliatory tariffs on **April 4**. Pause on most tariffs announced **April 9**.
- Who might pay (ideas to pick from or replace): portfolio managers sizing tariff risk; sell-side equity research; corporate risk/treasury teams benchmarking peers; index or ETF providers building "tariff-exposure" tilts; trade-policy analysts.

## 2. The data (Charlie)

### Unit of observation
One row = one S&P 500 company as of April 2, 2025 (one row per company, not per share class).
Key: `ticker` (unique, asserted in code); `cik` also unique.

### Columns (file: `data/processed/tariff_firms.csv`; definitions: `docs/DATA_CONTRACT.md`)

| Column | Meaning | Must-have? |
|---|---|---|
| ticker, company, cik | Identifiers (ticker as printed on the 10-K cover) | Must |
| gics_sector | GICS sector, from the Select Sector SPDR holdings on 2025-03-31 | Must |
| mktcap_usd_bn | Market cap, $bn: 10-K cover shares x 2025-03-31 price | Must |
| tenk_filing_date, tenk_accession, filing_url | The last 10-K filed before 2025-04-02 | Must |
| exposure_score | 0-4 import/China exposure from the 10-K text (LLM) | Must |
| exposure_evidence | Exact quote from the 10-K supporting the score | Must |
| ret_apr3_pct, ret_apr4_pct | Stock daily returns, April 3 and 4 (%) | Must |
| mkt_apr3_pct, mkt_apr4_pct | SPY daily returns, same days (%) | Must |
| car_pp | Sum of the two daily stock-minus-SPY returns (percentage points) | Must |
| hand_score | Blind human 0-4 score (Carter's hand-check) | Nice-to-have (planned) |
| car_mm_pp | Beta-adjusted (market model) abnormal return | Nice-to-have (blank) |
| car_pause_pp | Abnormal return on the April 9 pause | Nice-to-have (blank) |
| masked score | Score with company names hidden (leakage check) | Nice-to-have (planned) |

### Real example rows (v0, `data/processed/tariff_firms.csv`)

| ticker | sector | mktcap $bn | 10-K filed | score | stock Apr 3 / Apr 4 % | SPY Apr 3 / Apr 4 % | car_pp |
|---|---|---:|---|---:|---|---|---:|
| AAPL | Information Technology | 3,357.68 | 2024-11-01 | 4 | -9.25 / -7.29 | -4.93 / -5.85 | -5.75 |
| TJX | Consumer Discretionary | 138.00 | 2024-04-03 | 3 | +0.40 / -2.61 | -4.93 / -5.85 | +8.58 |
| VZ | Communication Services | 190.95 | 2025-02-12 | 1 | +1.97 / -5.68 | -4.93 / -5.85 | +7.07 |
| ADSK | Information Technology | 55.76 | 2025-03-06 | 0 | -4.02 / -4.53 | -4.93 / -5.85 | +2.23 |

Evidence quotes for these rows are in `outputs/v0_firms.md`.

### Sample and conditions
- Universe: **500 companies** in SPY's SEC Form N-PORT holdings for 2025-03-31 (SPY fully replicates the S&P 500). 503 securities; GOOG, FOX and NWS dropped as second share classes. Files: `data/universe/universe_2025-04-02.csv`, `data/universe/share_classes_dropped.csv`.
- Firms acquired or delisted after April 2025 stay in the universe (e.g., Hess, Discover, Juniper, ANSYS, Walgreens).
- 10-K rule: the **last original 10-K filed before 2025-04-02** (by filing date, not fiscal year end; amendments excluded). Filing dates range 2024-02-26 to 2025-04-01.
- Text: Items 1 (Business), 1A (Risk Factors), 7 (MD&A), extracted verbatim for **470 of 500** firms. 30 are pending hand-written section markers (mostly banks and utilities). Log: `data/universe/tenk_filings.csv`.
- 39 of the 470 texts are longer than the scorer's 350,000-character limit (mostly financials).
- Event window: April 2 close (base) to April 4 close.
- v0 = **10 firms** (5 pilot + 5 random, seed 331; `data/universe/v0_sample.csv`); **8 complete**. NKE: model's quote not exact; HES: no Yahoo prices after its acquisition by Chevron.

### Raw inputs

| Input | Source | How we get it | Where it lives |
|---|---|---|---|
| S&P 500 members on 2025-03-31 | SPY Form N-PORT, SEC EDGAR (accession 0001752724-25-125179) | `scripts/build_universe.py` | raw: `data/raw/universe/` (cached, not in git); output: `data/universe/universe_2025-04-02.csv` |
| Company IDs (CIK) | SEC `company_tickers_exchange.json` + EDGAR company names | `scripts/build_universe.py` | `data/universe/cik_overrides.csv` (25 hand-checked fixes) |
| Tickers | OpenFIGI CUSIP lookup, confirmed against the 10-K cover | `build_universe.py`, `build_manifest.py` | `data/raw/universe/openfigi_responses.json` |
| 10-K filings | SEC EDGAR filing histories and documents | `scripts/fetch_10k_text.py` | raw: `data/raw/tenk/`; text: `data/universe/text/` (rebuilt, not in git) |
| GICS sectors | 11 Select Sector SPDR N-PORTs, 2025-03-31, SEC EDGAR | `scripts/build_manifest.py` | `data/raw/universe/sector/` |
| Prices | Yahoo Finance daily adjusted closes, Apr 2-4, 2025 | `scripts/tariff_batch.py` | `data/raw/tariff_batch/prices/` (in git); `outputs/batch_v0/event_prices.csv` |
| Exposure scores | gpt-4.1-mini via Expected Parrot (EDSL) | `scripts/tariff_batch.py --backend parrot` | `data/raw/tariff_batch/scores/` (in git); `outputs/batch_v0/llm_run_log.csv` |

## 3. The method (Carter)

### Pipeline (`python run_all.py` runs these in order)
1. `scripts/build_universe.py`: universe from SPY N-PORT, CIKs, name checks
2. `scripts/fetch_10k_text.py`: last pre-event 10-K, Items 1, 1A, 7 as plain text
3. `scripts/build_manifest.py --v0`: sample, ticker, sector, market cap
4. `scripts/validate_manifest.py`: rechecks every manifest fact against EDGAR
5. `scripts/tariff_batch.py`: LLM exposure score + prices, then returns
6. `scripts/make_outputs.py`: dashboard data, firm table, regression, chart

### Scoring
- Rubric (from `scripts/tariff_batch.py`): 0 domestic services, no meaningful imports; 1 generic trade-policy boilerplate only; 2 real but limited imported inputs or foreign sales; 3 material dependence on imports or foreign manufacturing; 4 core business built on imports or explicit large China exposure.
- Input is the full text of Items 1, 1A and 7, not hand-picked passages. Temperature 0.
- The model must return an exact quote; the code rejects any quote that is not word for word in the 10-K (this rejected NKE).
- gpt-4.1-mini's training data reportedly ends in mid-2024, before the event (verify in OpenAI's model docs before citing).

### Outcome and regression
- car_pp = (stock − SPY, Apr 3) + (stock − SPY, Apr 4), in percentage points; base is the April 2 close.
- Dashboard models (HC3 robust errors): (1) car_pp on exposure_score; (2) car_pp on sector dummies; (3) both. Model 3 vs 2 asks whether exposure adds anything beyond sector.
- v0 result (one run, logged): slope −0.32 pp per point, SE 2.00, p = 0.87, n = 8 (`outputs/v0_regression.csv`). Too few firms to mean anything.

### Cost
- v0 scoring cost about $0.20 in Expected Parrot credits in total. Full run estimate: roughly $5-8 per pass for ~430 firms (based on v0's actual cost per firm).

## 4. Threats and checks (Carter)

| Threat | What we do now | Status |
|---|---|---|
| Look-ahead | 10-K filing date must be before 2025-04-02 (asserted; validated against EDGAR, including "no later pre-event 10-K") | Done |
| Survivorship | Universe from the 2025-03-31 holdings, not today's list; acquired firms kept | Done in universe; 14 acquired firms lack Yahoo prices (open) |
| LLM leakage | Pre-event-cutoff model; full text, not chosen excerpts; prompt says use only the text | Masked-name pass planned |
| LLM errors / made-up evidence | Exact-quote check; blind human hand-check | Hand-check Thursday |
| Merges / keys | One row per company (asserted); CIK 10 digits; tickers unique | Done |
| Sample selection | 30 firms without text are not random (banks, utilities); v0 sample drawn with fixed seed | Open: markers for the 30 |
| p-hacking | `specs_tried.md` logs every choice (15 entries), including the single v0 regression | Ongoing |
| Event overlap | China's retaliation on April 4 falls inside the window | Open: report April 3 alone too? |
| Beta | car_pp assumes beta = 1 | Market-model CAR planned |

Existing audit: `audits/01_self_audit.md` (Gunnar).

## 5. Dashboard (Gunnar)
- Streamlit app, `dashboard/app.py`. Tabs: Overview, Methodology, Results, Explore a firm.
- Reads `data/processed/tariff_firms.csv` (now the v0 rows).
- Live link: to come (Thursday).
