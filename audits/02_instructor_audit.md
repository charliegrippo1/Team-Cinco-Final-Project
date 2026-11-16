# Instructor audit: Team Cinco, Checkpoint 2

**Repo:** charliegrippo1/Team-Cinco-Final-Project · **Audited commit:** `3cd284d` (2026-11-14, `main`) · **Seed:** 5, tariff exposure: who lost on Liberation Day?

> Note from your human teacher: This review is generated with minimal supervision from Opus 5.5-high. It is thorough, but can be too generous at times and doesn't know my taste for what is "good". Grades it and I would assign are correlated, but noisy, ok? If you want additional feedback from _me_, you need to find me before/after/during class or during office hours for a guaranteed speedy reply. I will try to respond to emails and issues, but can not respond to student inquiries around the clock across the final weeks of class. Response times will be unpredictable, though during Thanksgiving week, I will do my best to respond quickly virtually, as in person options will be nil.

## Summary

This is one of the most careful v0s in the class:
- a point-in-time universe from SPY's N-PORT filing;
- 10-Ks chosen by filing date;
- a logged extraction-rule history;
- saved model answers with hashes;
- a blind hand check of the AI scores;
- CI that rebuilds the outputs byte for byte.

Your quick-check path reproduces every committed v0 table byte for byte. My own code reproduces all 8 returns, the HC3 regression and every cached model answer. The full rebuild needs SEC downloads the audit environment can't make (not your bug). What remains is mostly design work to settle **before** the full-sample run:
1. Specify the test of whether exposure beats industry dummies (A1).
2. Run the masked leakage pass (A2).

| Check | Result |
|---|---|
| Reruns from scratch | ⚠️ quick check (tests, `make_outputs.py`, `verify_dashboard.py`, `verify_tariff_pilot.py`): all pass, outputs identical. `run_all.py` stopped at step 1: SEC refused the audit environment's request (403) |
| Inputs have provenance | ✅ N-PORT accession, EDGAR URLs, hashes on every model answer |
| Keys unique, merges validated | ✅ ticker and CIK asserted, `validate="one_to_one"` |
| No look-ahead / survivorship | ✅ 2025-03-31 holdings and filing dates before 2025-04-02. Today's tickers are noted (your finding 9) |
| LLM leakage handled | ⚠️ pre-event model, but the masked pass isn't run yet (A2). Audited from the cached outputs, since LLM steps can't be rerun live here |
| `specs_tried.md` complete | ✅ 17 entries, including rejected rules |
| Magnitudes discussed | ⚠️ not yet (8 firms) |
| Hand checks | ✅ blind hand scores, `car_pp` recomputed in two scripts |
| Threats to validity | ✅ README section |
| Every number traces to `outputs/` | ✅ the README table and slope match `outputs/` |

## What holds up

- **Returns recomputed independently.** From a fresh yfinance pull, (stock − SPY) on April 3 plus April 4, 2025, with the April 2 close as base, matches `car_pp` for all 8 firms to 0.0000 pp (e.g. AAPL −5.7520, TJX +8.5756).
- **Regression recomputed.** My own OLS with HC3 gives slope −0.317574 (SE 2.002975), identical to `outputs/v0_regression.csv`.
- **LLM step, audited from the cache.** For all 9 entries in `outputs/batch_v0/llm_run_log.csv`, the saved response in `data/raw/tariff_batch/scores/` is from `gpt-4.1-mini` (both requested and returned). Its score equals the log's, and for the 8 completed firms both the score and the evidence quote equal `outputs/batch_v0/tariff_firms.csv`.
- **Seed 5, day-0 timing:** the announcement came after the close on April 2, so April 3 is day 0. The window and the April 4 retaliation are disclosed.
- **Seed 5, hand-checked sample:** the blind scores are a real check: 5 of 8 exact, mean absolute difference 0.75, with the non-blind pilot firms disclosed.

## Findings

### A1 · Major · The "does exposure beat industry dummies" test isn't specified yet

**Evidence:**
- This seed's audit list asks "whether the exposure measure beats simple industry dummies".
- Your self-audit's introduction names it (`audits/01_self_audit.md:7`), but no entry in `specs_tried.md`, no README section and no code (`scripts/make_outputs.py`) defines the comparison.
- `gics_sector` is in the data (`specs_tried.md` #5), and the only regression run is `car_pp ~ exposure_score` (#15).

**Why it matters:** Tariff exposure is concentrated by industry (retail, autos, hardware). If sector dummies explain the April 3–4 returns as well as the 10-K score, the LLM measure adds nothing. This is the result most likely to change the conclusion. Deciding the test after seeing results is a specification search.

**Fix:** Before the full run, log in `specs_tried.md`:
- (a) `car_pp ~ C(gics_sector)`;
- (b) `car_pp ~ exposure_score + C(gics_sector)`;
- (c) the comparison: the within-sector coefficient on `exposure_score`, plus the increase in adjusted R² and its significance (an F-test).

Use HC3 errors as now, and name the primary specification.

**How to show it's fixed:** `specs_tried.md` has the dated entry before the full-sample results, and `outputs/` has the (a)/(b) table.

### A2 · Minor · The masked-name leakage test is planned but not run

**Evidence:**
- README threat 1 and self-audit finding 1 (High, open): `gpt-4.1-mini` has a pre-event cutoff, and a second pass with company names hidden is planned.
- `outputs/batch_v0/summary.json` shows `"masked": false`. No masked run exists.

**Why it matters:** "LLM leakage" is the first item on this seed's audit list. A model can recognize Apple from its 10-K even without a cutoff problem, and its general knowledge of which firms are "China-exposed" is not the same as reading the filing.

**Fix:** Run the masked pass on the v0 firms now (it's cheap at 8–10 firms). Report score agreement between masked and unmasked (exact, within 1), and commit the masked answers to the cache. Decide in `specs_tried.md` what agreement level you'll accept before the full run.

**How to show it's fixed:** A `masked: true` batch summary and an agreement table in `outputs/`.

### A3 · Minor · Pin versions, and mark the planned columns

**Evidence:**
- `requirements.txt` uses minimums only (`pandas>=2.0`, …). Your own log (`specs_tried.md` #17) records a pandas 3.0 vs 3.1 difference that broke the byte-for-byte check.
- `car_mm_pp` and `car_pause_pp` are empty in `outputs/batch_v0/tariff_firms.csv` and `data/processed/tariff_firms.csv` (planned v1 columns).

**Fix:** Pin the versions CI uses (`pip freeze`). Either fill the planned columns or note in `docs/DATA_CONTRACT.md` that they are empty until v1.

**How to show it's fixed:** Pinned `requirements.txt`, and the data contract states the column status.

## How to respond

This audit is `audits/02_instructor_audit.md` in your repo. Fix what you can, then add `audits/03_audit_response.md`, replying to each finding ID: fixed (the commit), disputed (why), or disclosed as a limitation (where).

**Deadline: Saturday, November 21, 2026.**
