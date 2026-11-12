# Self-audit 01: Checkpoint 2 (v0, end to end)

**Date:** 2026-11-11
**Commit audited:** `c71fa5f` (main, after merging PR #5)
**Prepared by:** Gunnar Krein, with an AI skeptical review (Claude) as the course instructs. Every check below was rerun on a fresh clone; nothing is taken from the docs on trust.

We went through the 10-point auditor checklist from `00_PROJECT_SEEDS`, plus the three things the Seed 5 description says auditors will poke at: LLM leakage, whether exposure beats industry dummies, and day-0 timing.

## Summary

| Severity | # | Finding | Owner |
|---|---|---|---|
| High | 1 | Pilot exposure scores came from a model trained after April 2025, using hand-picked excerpts | Carter |
| High | 2 | 30 of 500 firms have no 10-K text yet, and they are not random (big banks, utilities, and tariff-exposed industrials) | Charlie |
| High | 3 | No blind human scores yet, so the LLM scores are unvalidated | Gunnar |
| Medium | 4 | No single "run everything" path; the README still describes Checkpoint 1 | Gunnar |
| Medium | 5 | Two different market-cap numbers for the same firms | Charlie + Carter |
| Medium | 6 | Full manifest (sector, size for all 470+ firms) not built yet | Charlie |
| Medium | 7 | No "threats to validity" section in the README | Gunnar |
| Low | 8 | `specs_tried.md` only logs Charlie's choices so far | All |
| Low | 9 | Tickers come from today's OpenFIGI lookup, not April 2025 | Charlie |
| Low | 10 | Rerunning the pilot rewrites the CSV with different line endings | Carter |

## What passed

- **The pilot reproduces exactly.** On a fresh clone, `python scripts/tariff_pilot.py` rebuilt `data/processed/tariff_firms.csv` with identical values, and `python scripts/verify_tariff_pilot.py` recomputed all three CARs independently: AAPL −5.7520, NKE −0.6526, VZ +7.0720 pp. All 6 unit tests in `tests/` pass.
- **Price provenance is complete.** Every price in `data/pilot/event_prices.csv` has its source URL, retrieval time, and a hash of the raw response.
- **No survivorship in the universe.** `data/universe/universe_2025-04-02.csv` comes from SPY's SEC N-PORT filing for 2025-03-31, so firms that were later acquired or delisted are kept. `specs_tried.md` #2 checks that there were no index changes between March 24 and April 2. 500 firms, and CIK is unique (checked).
- **No look-ahead in the filings.** All 470 extracted 10-Ks were filed between 2024-02-26 and 2025-04-01, so none was filed on or after the event (checked on `tenk_filings.csv`). Filing date is used, not fiscal year end, and amendments are excluded.
- **Day-0 timing is right.** The announcement came after the close on April 2, so April 2 is the baseline close, April 3 is day 0 and April 4 is day +1.
- **Keys are enforced in code.** `build_manifest.py` asserts unique tickers, and `tariff_batch.py` rejects duplicate tickers and duplicate price sessions.
- **The batch LLM prompt is leakage-aware.** It gives the model only filing text plus the rubric, tells it not to use outside knowledge, has a masked mode that strips company names, and logs the model, response ID and input hashes.
- **A choices log exists.** `specs_tried.md` records 10 decisions, including the ones we rejected and why.

## Findings

### 1. High: pilot scores are exposed to LLM leakage
`outputs/llm_run_log.csv` shows the three pilot scores came from "Codex GPT-6", a model trained well after April 2025, so it knows Apple fell. The scores were also based on "selected filing passages" picked by hand, by people who already knew the outcome.
**Fix:** treat the pilot scores as placeholders. For the full run, score the full extracted Items 1, 1A and 7 (not hand-picked passages), run both the normal and masked versions, and report how often they agree. If the scores barely change with names hidden, that is our evidence that leakage doesn't drive results. Also ask the professor whether masking is enough (this was one of our STATUS questions).

### 2. High: the 30 missing firms are not random
`tenk_filings.csv` has 30 firms with `status = failed`, including JPMorgan, Wells Fargo, Citigroup, Southern, Exelon (banks and utilities, which have hard-to-parse 10-Ks), but also **Deere, Intel, GE, Honeywell, Eaton, Halliburton, Clorox, Mosaic and PulteGroup**, which are exactly the kind of import-exposed firms our question is about. Dropping them could bias the result toward zero.
**Fix:** finish the manual section markers for all 30 (Charlie's `section_markers.csv` approach already recovered Exxon and IBM). If any can't be fixed, list them in the README and rerun the main regression with and without them.

### 3. High: no human check of the LLM scores yet
`hand_score` is blank for every firm. The data contract and Seed 5 both require a hand-checked sample.
**Fix:** Gunnar scores a random sample of about 50 firms from the 10-K text using the rubric in `docs/DATA_CONTRACT.md`, without seeing the LLM's score, and we report exact agreement and within-one-point agreement. The random sample should be drawn with a fixed seed and saved before scoring.

### 4. Medium: no single reproduction path
The checklist expects one `run_all.py` (or README steps) that rebuilds everything. Right now there are separate steps (`build_universe.py` → `fetch_10k_text.py` → `build_manifest.py` → `tariff_batch.py`), and the README only covers the 3-firm pilot and still says "Checkpoint 1". `validate_manifest.py` also fails on a fresh clone because it expects raw SEC downloads that are git-ignored; the README should say to run the download scripts first (and that they need `SEC_USER_AGENT` set).
**Fix:** update the README with the full pipeline in order, and add `run_all.py` once the full sample works.

### 5. Medium: two market caps for the same firm
`data/processed/tariff_firms.csv` (pilot) uses vendor estimates: AAPL 3,326.84, NKE 91.49, VZ 191.25. `data/universe/manifest.csv` (Charlie) computes them from 10-K shares × the March 31 price: AAPL 3,357.68, NKE 95.18, VZ 190.95.
**Fix:** use Charlie's reproducible method everywhere and drop the vendor numbers. `specs_tried.md` #6 already says to pick v0 or v1 **before** seeing full-sample results.

### 6. Medium: full manifest not built
`manifest.csv` has 5 pilot firms. Sector and market cap for the other firms don't exist in a single file yet, so the industry-control regression can't run.
**Fix:** build the full manifest for the 470 (then 500) firms. This is the main blocker for the Nov 19 full-sample checkpoint.

### 7. Medium: no threats-to-validity section in the README
The dashboard's Methodology tab has one, but the README doesn't.
**Fix:** add one covering at least: LLM leakage (#1), the non-random missing firms (#2), China's retaliation on April 4 being inside our window, the beta = 1 assumption in market-adjusted CARs, and share counts up to 12 months old in market cap.

### 8. Low: the choices log is one-sided
`specs_tried.md` has Charlie's 10 entries but none of the earlier choices: the 2-day window, the SPY benchmark, the market-adjusted CAR, the 0–4 rubric, the Items 1/1A/7 scope.
**Fix:** each of us adds the choices we made.

### 9. Low: tickers are today's, not April 2025's
`ticker_figi_today` comes from a current OpenFIGI lookup, and 20 firms have no ticker yet. If a firm changed its ticker since April 2025, the price download could pull the wrong series or nothing.
**Fix:** confirm each ticker from the 10-K cover page (already planned, see `specs_tried.md` #4), and assert every firm gets prices for April 2, 3 and 4.

### 10. Low: rerunning the pilot changes line endings
After a rerun, git shows `tariff_firms.csv` as modified even though every value is identical (Windows vs. Mac/Linux line endings).
**Fix:** write CSVs with `newline=""` / `lineterminator="\n"`, or add a `.gitattributes` file.

## Not yet testable

- **Magnitudes and "exposure beats industry dummies."** These need the full sample. The dashboard already runs exposure-only, sector-only and combined models, so the comparison is ready once data exists.
- **Beta-adjusted CAR and the April 9 pause.** Optional fields, still blank.

## Next audit
Before Checkpoint 4 (Nov 19), rerun this checklist on the full sample and mark each finding above fixed or still open.

## November 11 follow-up on the three-firm pilot

**Finding 10.** The CSV writer now emits LF line endings explicitly. To repeat the byte check, run `python scripts/tariff_pilot.py` and compare `git hash-object --no-filters data/processed/tariff_firms.csv` with `git rev-parse HEAD:data/processed/tariff_firms.csv`. Both commands should print the same hash.

**Dashboard check.** After the rebuild, run `python scripts/verify_tariff_pilot.py` and `python scripts/verify_pilot_dashboard.py` with the dashboard requirements installed. The first independently recomputes daily returns from adjusted closes. The second reads the Results table and selects each firm in the Streamlit explorer. On Windows, the explorer displayed AAPL −5.75 pp, NKE −0.65 pp and VZ +7.07 pp, each with the evidence from its own filing row. The successful run used the bundled Python numerical libraries after the project virtual environment timed out. [Dashboard check](../scripts/verify_pilot_dashboard.py) · [Linux workflow](../.github/workflows/pilot-audit.yml)

**Nike illustrates the event-window risk.** Nike trailed SPY by 9.5116 percentage points on April 3 and beat it by 8.8590 points on April 4. The two-day sum was −0.6526 points. Its 2024 filing attributes about 95% of NIKE Brand footwear production to Vietnam, Indonesia and China combined. That passage supports the pilot's high overseas-manufacturing score, but the production shares alone cannot establish US tariff costs or explain the second day's reversal. [Nike 10-K, Item 1](https://www.sec.gov/Archives/edgar/data/320187/000032018724000044/nke-20240531.htm) · [Pilot inputs](../data/pilot/event_prices.csv)
