# Response to the instructor audit (Checkpoint 2)

Replies to `audits/02_instructor_audit.md` (audited commit `3cd284d`). Each finding is
marked **fixed** (with the commit), **disputed** (with the reason) or **disclosed** (with
where). Entries in `specs_tried.md` are cited by number; each is dated, so the order in
which decisions and results happened can be checked.

All numbers below are copied from the committed files in `outputs/v1/` (full run of
2026-11-18: 500 firms attempted, 408 complete; failures in `outputs/batch_v1/failures.csv`).

## A1 · Major · Does exposure beat industry dummies? **Fixed**

- **Specified before the full run:** `specs_tried.md` #22 (2026-11-17), committed in
  `0d28753` and merged in `e9e475f`, before any full-sample score existed (the first full-sample score was made on
  2026-11-18 in the evening).
  - (a) `car_pp ~ C(gics_sector)`
  - (b) `car_pp ~ exposure_score + C(gics_sector)` (**primary specification**)
  - (c) the within-sector coefficient on `exposure_score`, the change in adjusted R²,
    and an HC3 robust Wald F-test of adding exposure to the sector model
  - Both models are fit on the identical set of complete firms, with HC3 errors. The
    April 3-only return is the pre-named secondary outcome.
- **Code:** `scripts/sector_results.py` with tests in `tests/test_sector_results.py`
  (`0d28753`).
- **Outputs:** `outputs/v1/v1_sector_regressions.csv`, `outputs/v1/v1_sector_comparison.csv`.
- **Result (n = 408):** within sectors, each exposure point is associated with a
  **-0.98 pp** cumulative April 3-4 abnormal return (HC3 SE 0.21, p < 0.001). Adjusted R²
  rises from 0.320 (sector only) to 0.354 (sector + exposure), a change of 0.035; HC3 Wald
  F = 22.0, p < 0.001. So exposure explains returns beyond industry composition. Without
  sector dummies the slope is -0.52 pp (SE 0.22, p = 0.017), so sectors were hiding part of
  the effect, not creating it. Pre-named secondary (April 3 only): -0.85 pp (SE 0.18,
  p < 0.001), adjusted R² change 0.038.

## A2 · Minor · Masked-name leakage test. **Fixed**

- **Plan and pass bar fixed before any full-sample result was assembled:** `specs_tried.md`
  #28 (2026-11-18). The 10 v0 firms are scored again with names hidden (company name, ticker and
  the short names each filing uses, `data/universe/mask_aliases.csv`), with the v1 rubric and the same
  model. Pass: at least 80% within one point and mean absolute difference at most 0.75.
- **Result: passed.** `outputs/batch_masked/summary.json` (`masked: true`, rubric v1);
  table in `outputs/v1/v1_masked_agreement.md`. Of the 9 firms with both scores: 8 exact,
  9 within one point (100%), mean absolute difference 0.11 (Roper 1 shown vs 0 hidden).
  Nike was scored masked but its unmasked quote failed the check, so it is not compared.
- Store brands (TJ Maxx, iPhone) are not hidden, so the test is a lower bound on how
  much the model could recognize a firm. Disclosed in the README's threats section.

## A3 · Minor · Pin versions, mark the planned columns. **Fixed**

- **Pinned versions:** `requirements.txt` pins every package exactly (generated with
  `uv pip compile --universal --python-version 3.12`), `specs_tried.md` #20, commit
  `fc4d8fb`. Checked in a clean Python 3.12 environment: tests pass, pilot and v0
  outputs rebuild byte for byte.
- **Planned columns:** `docs/DATA_CONTRACT.md` now states that `car_mm_pp` and
  `car_pause_pp` are empty until filled, and explains the `sample` column (commit
  `455d100`, PR #12).
- `car_mm_pp` and `car_pause_pp` are still empty in v1, as documented.

## Other changes since the audit

- All 500 firms now have 10-K text (the 30 failures fixed with section markers,
  `specs_tried.md` #18). 46 filings over the 350,000-character limit are excluded and
  disclosed, never truncated (#23).
- New v1 rubric that scores import and foreign-production dependence only (#21),
  fixed before the full run.
- Full-sample manifest checks found and fixed wrong cover tickers and market caps
  (#24, #25); prices were verified against SPY's N-PORT before scoring (#26), which
  caught Paramount's reused ticker.
- The v1 hand-check firms were drawn before scoring (#27).
- Quote rule for v1, decided during the run before any result was viewed (#29): quotes
  with the same words but different spacing or quote marks, and quotes stitched from
  several exact pieces, count; any word not in the filing still fails.
