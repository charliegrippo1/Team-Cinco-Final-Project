# Instructor audit: Team Cinco, Checkpoint 3

**Repo:** charliegrippo1/Team-Cinco-Final-Project · **Audited commit:** `243cda2` (2026-11-19, `main`, merge of PR #10 after PR #13) · **Seed:** 5, tariff exposure: who lost on Liberation Day? · **CP2 audit:** `audits/02_instructor_audit.md` (commit `3cd284d`)

> Note from your human teacher: This review is generated with minimal supervision from Opus 5.5-high. It is thorough, but can be too generous at times and doesn't know my taste for what is "good". Grades it and I would assign are correlated, but noisy, ok? If you want additional feedback from _me_, you need to find me before/after/during class or during office hours for a guaranteed speedy reply. I will try to respond to emails and issues, but can not respond to student inquiries around the clock across the final weeks of class. Response times will be unpredictable, though during Thanksgiving week, I will do my best to respond quickly virtually, as in person options will be nil.

## Summary

This is a full-sample v1 that reproduces. All three CP2 findings are fixed, with evidence that checks out.
- From your committed model answers and price cache, `make_outputs.py` rebuilds every v1 table identically, and `masked_agreement.py` rebuilds the masked-name check identically.
- My own code reproduces the returns (15 random firms, from a fresh yfinance pull), the primary regression and its Wald test, every cached score (408 of 408), and the v1 hand check.
- The sector test was specified before the run, as CP2 asked.

The one thing that matters most before Dec 1 is B1. Your outcome is market-adjusted (beta = 1) on a day SPY fell 10.5%, and high-exposure firms have higher betas. With a market-model return, which is your own planned `car_mm_pp`, the within-sector slope falls from −0.98 to about −0.37 (p ≈ 0.06–0.08). You disclosed the beta = 1 assumption. The result now depends on it, so it needs to be front and center.

## Follow-up on your Checkpoint 2 audit

Response file: `audits/03_audit_response.md` found (on `main`).

| CP2 finding | Status | Evidence |
|---|---|---|
| A1 · Exposure vs industry dummies not specified | fixed | `specs_tried.md` #22 (dated 2026-11-17, in commit `0d28753`, 11:50 −0500) predates the full-run commit `c151b27` (2026-11-18 22:47). `scripts/sector_results.py` writes `outputs/v1/v1_sector_regressions.csv` and `v1_sector_comparison.csv`, and both regenerate identically. My own OLS + HC3: exposure −0.9784 (SE 0.2086), adjusted R² 0.3198 → 0.3544 (Δ 0.03462), HC3 Wald F = 21.998, p = 3.8e-6, the same as `v1_sector_comparison.csv` |
| A2 · Masked-name pass not run | fixed | `outputs/batch_masked/summary.json` has `"masked": true` (10 firms). `python scripts/masked_agreement.py` regenerates `outputs/v1/v1_masked_agreement.{csv,md}` byte for byte: 8 of 9 exact, 9 of 9 within one, MAD 0.11, against a bar fixed in `specs_tried.md` #28 before the full results |
| A3 · Pin versions; mark planned columns | fixed | `requirements.txt` pins all 47 packages with `==`, and a venv built from it ran every step. `docs/DATA_CONTRACT.md:41-42,53-54` mark `car_mm_pp` and `car_pause_pp` as "empty for now" |

**3 of 3 fixed, 0 still open.**

## Checkpoint 3 checks

| Check | Result |
|---|---|
| Reruns from scratch (full sample) | ✅ steps 5 (price stage) and 6 rerun from the committed caches: all v1 and v0 tables identical. Steps 1–4 and the scoring part of step 5 need SEC 10-K text (see below) |
| Inputs have provenance | ✅ N-PORT accession, a 10-K URL and accession per firm, hashes on every model request and price response |
| Keys unique, merges validated | ✅ my own merge of the run log onto the firm table (`validate="1:1"`) is clean, and you assert ticker and CIK |
| No look-ahead / survivorship | ✅ 2025-03-31 holdings, 10-Ks filed before 2025-04-02. The 16 acquired-after firms with no prices are disclosed (`README.md:16-20`) |
| LLM leakage handled | ✅ masked pass passed its pre-set bar (audited from the cached answers; LLM steps can't be rerun live here) |
| `specs_tried.md` complete | ✅ 29 entries. #22, #27 and #28 are dated before the results they govern |
| Magnitudes discussed | ⚠️ "about a 1 percentage point larger" loss per point (`README.md:33`). How much of it is beta isn't shown (B1) |
| Hand checks | ✅ v1 blind hand check, 20 firms drawn before scoring: 10 exact, 18 within one, MAD 0.65 (I recomputed this from `audits/hand_check_v1.csv`) |
| Threats to validity | ✅ README threats, including "Beta = 1" (`README.md:156-157`) |
| Every number traces to `outputs/` | ✅ the README results table (`README.md:26-31`) matches `v1_sector_regressions.csv` and `v1_sector_comparison.csv` |
| Dashboard matches `outputs/` | ✅ "408 of 408 firms" and "correlation … −0.12" (`v1_tariff_firms.csv`: −0.1204) |

Steps not rerun by design: `build_universe.py`, `fetch_10k_text.py`, `build_manifest.py` and `validate_manifest.py` (SEC EDGAR), and the scoring half of `tariff_batch.py`, which reads the 10-K text those steps download (the run failed on `data/universe/text/*.txt`, which is not in git). The audit makes no SEC requests. These are not counted against you.

## Getting ready for Dec 1

Presentations run only from URLs, with a hard cutoff at 9 minutes (10:45 section) or 10 minutes (12:10 section). Put your URL(s) in column G of the Team Projects sheet.

| Check | Result |
|---|---|
| Dashboard launches from a clean clone | ✅ `streamlit run dashboard/app.py --server.headless true --server.port 8601` on a clean export of `243cda2`: `/_stcore/health` returned `ok` after 2 s. A headless browser clicked all 4 tabs, with no exceptions on the page or in the log. `scripts/verify_dashboard.py` also passes (exit 0) |
| Dashboard shows the v1 numbers from `outputs/` | ✅ it reads `outputs/v1/v1_tariff_firms.csv` (`dashboard/app.py:29`). It shows 408 firms, the coverage note and the −0.12 correlation |
| README links the live URL(s) | ✅ `README.md:3` links team-cinco-liberation-day.streamlit.app (the live site itself wasn't checked). The app has no separate requirements file, so Streamlit Cloud uses the pinned root `requirements.txt` (`streamlit==1.62.0`) |

**Core story for 9–10 minutes:** the 10-K exposure score and its checks (hand check, masked pass); the primary within-sector result **next to its beta-adjusted version** (B1); then the scatter. Coverage and the quote rule can be one slide.

## What holds up

- **Reproduction.** From the committed caches, `tariff_batch.py --stage prices --offline` reproduces all 1,227 rows of `batch_v1/event_prices.csv` exactly. `make_outputs.py` (v1 and v0) and `masked_agreement.py` rebuild every CSV and markdown table in `outputs/` identically (the PNG charts differ only in bytes). `python -m unittest discover -s tests` ran 16 tests: OK, 1 skipped.
- **Independent returns.** A fresh yfinance pull gives `car_pp` for 15 randomly drawn firms (seed 331) within 3.5e-5 pp, e.g. RL −5.6265 and ZBH +6.2024. SPY's two-day return compounds to −10.49%, matching "fell 10.5%" (`README.md:11`).
- **The LLM step, audited from the cache.** All 424 entries in `batch_v1/llm_run_log.csv` have a saved answer. Every one was requested from and returned by `gpt-4.1-mini` (status `completed`). The saved score equals the log and `v1_tariff_firms.csv` for all 408 complete firms.
- **The quote rule (#29) doesn't drive the result.** Using only the 380 firms whose quote matched exactly, the primary coefficient is −0.980 (SE 0.214), against −0.978 on all 408.
- **Seed 5 items.** The exposure measure does beat industry dummies, as pre-specified (A1). The masked pass checks leakage (A2). Day 0 is April 3 for an after-close announcement.

## New findings

### B1 · Major · The exposure effect shrinks by more than half with a market-model return

**Evidence:** `car_pp` is stock − SPY (`README.md:10`, `docs/DATA_CONTRACT.md`), which assumes beta = 1, over two days when SPY lost 10.5%. I estimated each firm's beta with the team's planned definition of `car_mm_pp` (`docs/DATA_CONTRACT.md:41`: 250 trading days ending 2025-02-28, vs SPY, yfinance adjusted closes) and rebuilt the April 3–4 abnormal return as stock − (α + β·SPY). On the same 408 firms, with HC3 errors:

| Outcome | Exposure only | Exposure + sector dummies (primary) |
|---|---|---|
| `car_pp` (yours, beta = 1) | −0.520 (SE 0.217, p 0.017) | **−0.978** (SE 0.209, p < 0.001) |
| Market-model CAR (auditor) | +0.279 (SE 0.202, p 0.17) | **−0.374** (SE 0.211, p 0.077) |
| `car_pp`, controlling for beta | | −0.652 (SE 0.186); beta −5.91 (SE 0.64) |

Mean beta by exposure score: 0.68 (score 0, n = 152), 0.80 (score 3, n = 160), **1.37** (score 4, n = 23). corr(beta, exposure) = 0.18. With a window ending 2025-03-31 instead, the primary-spec coefficient is −0.377 (p 0.058).

**Why it matters:** On a −10.5% market day, a beta of 1.37 alone predicts a return about 3.9 pp below SPY. Your high-exposure firms are high-beta firms (hardware, autos, retail), so part of what the regression credits to the 10-K score is market sensitivity. You flagged "Beta = 1" as a threat (`README.md:156-157`). The test now says it matters for the headline.

**Fix:** Fill `car_mm_pp` with the definition already in your data contract. Log it in `specs_tried.md` as a robustness row, labeled as added after the primary result. Report it next to the primary in the README table and on the dashboard. Consider also a beta control, or a market model on the Fama–French factors. A short paragraph on why beta and exposure are correlated would help readers interpret both numbers.

**How to show it's fixed:** `car_mm_pp` is filled in `v1_tariff_firms.csv`, and `v1_sector_regressions.csv` has the market-model rows. I will recompute the betas and compare.

### B2 · Minor · Non-random coverage: say what it could do to the slope

**Evidence:** 92 of 500 firms are missing (`outputs/batch_v1/failures.csv`): 46 over the length limit (mostly Financials, now 64% covered per the dashboard's coverage note), 27 quote failures, 3 unscored, and 16 with no prices (acquired after the event). The dashboard says "These losses are not random", which is honest. Nothing yet shows which way they could bias the slope.

**Fix:** Report the primary regression without Financials (the least-covered sector), and compare the dropped firms' sector mix with the kept firms'. Two lines in the README are enough.

**How to show it's fixed:** A logged robustness row in `specs_tried.md`, with its output file.

## How to respond

This audit is `audits/04_instructor_audit.md` in your repo. Fix what you can, then add `audits/05_audit_response.md`, replying to each **B** finding (no CP2 findings are still open): fixed (the commit), disputed (why), or disclosed as a limitation (where).

There's no separate deadline for this response. Keep working through these until your final deliverables are due: the final repo is audited again then.
