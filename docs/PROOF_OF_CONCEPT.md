# Running and understanding the proof of concept

## Run

Requires Python 3.10 or later. No third-party packages, API keys, or installation step are needed.

```powershell
python scripts/proof_of_concept.py
python scripts/verify_outputs.py
```

If Windows `python` opens the Store or fails, use an installed interpreter. The successful interpreter on the current machine was:

```powershell
& 'C:\Users\carte\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/proof_of_concept.py
& 'C:\Users\carte\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/verify_outputs.py
```

First run needs Internet access. Later runs reuse the hash-verified local cache. Add `--offline` to the pipeline to prohibit downloading. A fresh clone downloads a new source vintage and may produce slightly revised values. To reproduce this exact vintage, retain the local `data/raw` folder and its metadata files. It is excluded from Git. Published processed outputs and their manifest remain available for inspection; redistribution/access terms should be checked before publishing a raw-data archive. There is no automatic cache refresh: preserve the old cache separately before deliberately acquiring a new vintage.

## Files

- `scripts/proof_of_concept.py`: download/cache sources, align sessions, calculate returns, and validate required inputs.
- `scripts/verify_outputs.py`: separate Decimal recomputation from exported prices.
- `data/processed/event_returns.csv`: one row per meeting and sector ETF (15 rows).
- `data/processed/calculation_trace.csv`: underlying day -1, 0, +1 calculations (45 rows).
- `data/processed/adjusted_prices.csv`: downloaded adjusted closes used by the calculations.
- `data/processed/source_manifest.json`: source URLs, retrieval times, and raw-file hashes.
- `data/processed/validation.json`: coverage and key checks.
- `audits/poc_calculation_checks.md`: recomputation result and five examples to inspect.
- `STATUS.md`: checkpoint memo and unresolved instructor questions.

## Definitions and design

Sample: the final five scheduled 2024 FOMC meetings, selected before inspecting returns. XLK is technology, XLF broad financials, and XLU utilities; SPY is the benchmark. This is a pilot, not a representative sample or sector ranking. Dates and rate changes are manually curated constants verified against the linked statements. All announcements are at 14:00 Eastern, so day 0 is that session (EDT for June–September; EST for November–December). The code validates the release-time text; it does not automatically parse policy changes. The source [FOMC calendar](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) establishes meeting dates. These dates exclude minutes releases.

Return (%) = `100 * (adjusted_close_today / adjusted_close_previous_session - 1)`.
Market-adjusted return (pp) = ETF return minus SPY return. The exported `abnormal_return_pp` is this simple beta-one calculation, not an estimated market-model residual.
Three-day CAR (pp) = sum of market-adjusted returns over trading days [-1, 0, +1]. Four closes are needed, starting at day -2. It is not a compounded holding-period return difference. SPY daily-bar dates define the pilot's session sequence; every required ETF close must exist. An independent exchange-calendar reconciliation remains a full-sample task. US daytime daily-bar timestamps have the same calendar date in UTC and New York; the script rejects timestamps outside the expected daytime range.

Prices are Yahoo chart `adjclose` values, incorporating vendor corporate-action adjustments; do not adjust again. Historical adjusted levels can be revised. Missing required window prices cause a clear failure rather than forward-fill or return calculation across a gap. Missing policy surprises remain blank with a reason. Target expectations and literal target surprises stay blank because they have not been measured.

The `policy_news_surprise_pp` field uses the supplied **ME** column in the [USMPD surprise archive](https://www.frbsf.org/wp-content/uploads/monetary-policy-surprises.zip). Its README defines percentage-point units, normalized to a one-for-one effect on the one-year Treasury yield. ME covers the combined statement and press conference; it is not STMT + PC and is not a pre-announcement predictor. We use supplied outputs, not a re-estimated R factor. See the [USMPD source and methodology](https://www.frbsf.org/research-and-insights/data-and-indicators/us-monetary-policy-event-study-database/), and cite Acosta, Ajello, Bauer, Loria, and Miranda-Agrippino (2025), *Financial Market Effects of FOMC Communication: Evidence from a New Event-Study Database*, FRBSF Working Paper 2025-30. This is a different series from the separate Bauer–Swanson raw/orthogonalized surprise download.

## Audit limits

Source hashes, unique meeting–ticker keys, finite positive calculation prices, all event windows, and return arithmetic are checked. All five official statements were manually inspected. The independent arithmetic check uses the same source prices; a second vendor has not been reconciled. Five events are insufficient for inference. Daily returns contain other news, particularly around the November election. SPY also reacts to policy. Later regression uncertainty must account for shared meeting shocks rather than treating 15 rows as independent events. Published factor estimates/revisions can include information from later observations; the frozen vintage supports retrospective description, not an investable backtest. No outcomes were used to choose these five calendar-ordered events, and no best-performing strategy was selected.
