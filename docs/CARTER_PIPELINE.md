# Carter: full-universe scoring and returns

The three-firm pilot remains reproducible with `scripts/tariff_pilot.py`.
`scripts/tariff_batch.py` extends that workflow to an arbitrary number of firms.
It does not claim that the full sample has been collected or scored yet.

## Charlie's handoff

Supply `data/universe/manifest.csv`, one unique ticker per row, and UTF-8 plain-text
files containing each firm's pre-event 10-K Items 1, 1A and 7. Paths are relative
to the repository root (absolute paths also work). Preserve the text verbatim;
do not send raw HTML, tables of contents alone, or hand-selected favorable quotes.
The manifest must have these columns:

```text
ticker,company,cik,gics_sector,mktcap_usd_bn,tenk_filing_date,tenk_accession,filing_url,text_path,membership_date,membership_source,cap_source,price_symbol,mask_aliases
```

- `membership_date` must be `2025-04-02`; `membership_source` must cite Charlie's
  historical constituent evidence. This is a supplied assertion, not an automatic
  independent membership check. Today's constituents are not a substitute.
- `cik` must contain ten digits; `tenk_filing_date` must be before April 2.
  Charlie must verify it is the **last** eligible 10-K, not merely an older one.
- `mktcap_usd_bn` is the March 31, 2025 market cap, with `cap_source` documenting it.
- `price_symbol` is optional: defaults to ticker with dots changed to hyphens.
  Explicitly map renamed/delisted securities and share classes; never substitute
  a different firm's price series just to fill a missing row.
- `mask_aliases` is optional, pipe-separated aliases/brands to remove along with
  company name and ticker in masked runs. Inspect masking: distinctive products
  may still identify firms. Dates inside source text are retained; no event date,
  event name, returns, sector, or capitalization is added to the scoring prompt.
- Multiple share classes can produce multiple securities per company. The runner
  enforces unique tickers; Charlie and the PM must settle the firm/share-class rule
  before treating roughly 500 securities as independent firms.

An empty header template is included at `data/universe/manifest.template.csv`.
No synthetic firm records or pilot membership proxies are presented as this universe.

## Run from the repository root

The batch code uses only the Python standard library. On Carter's Windows machine,
use `.venv\Scripts\python.exe` in place of `python` if the Windows Python alias fails.
Configure `OPENAI_API_KEY` locally, without committing it or pasting it into chat.
Set `OPENAI_MODEL` to the team's chosen Structured Outputs-capable model snapshot.
The runner has no default model; pinning one makes the scoring protocol explicit.
API scoring incurs usage charges. Start with three rows and inspect the outputs.

```powershell
python scripts/tariff_batch.py --manifest data/universe/manifest.csv --limit 3 --output outputs/batch_smoke
python scripts/tariff_batch.py --manifest data/universe/manifest.csv
```

Download all prices independently of model access:

```powershell
python scripts/tariff_batch.py --manifest data/universe/manifest.csv --stage prices --output outputs/batch_prices
```

Run a separate masked scoring pass (the PM still supplies independent human scores):

```powershell
python scripts/tariff_batch.py --manifest data/universe/manifest.csv --stage score --masked --output outputs/batch_masked
```

Repeat the same command to resume. Successful API responses and price responses
are saved under ignored `data/raw/tariff_batch/`. Score cache keys include the exact
input, model, prompt, and output schema. `--offline` rebuilds using caches without
network calls; uncached inputs are reported as failures. Preserve this directory
for reproducibility. A separate `--cache` directory starts a new data vintage.
Requests retry transient HTTP/network failures four times with bounded backoff;
ambiguous API timeouts can incur duplicate usage. Runs are sequential. Do not run
two processes against the same cache or output directory.

## Review the handoff

Each output directory contains:

- `tariff_firms.csv`: successfully scored firms with complete stock/SPY prices.
- `event_prices.csv`: adjusted closes, source URL, retrieval time and response hash.
- `llm_run_log.csv`: returned model identifier, response ID, input/request hashes,
  cache location and whether masking was used. Full response, rationale and usage
  remain in the referenced cache file.
- `failures.csv`: every failed ticker, stage and reason. The process exits nonzero
  if any firm fails; failed firms are never assigned an invented zero score.
- `summary.json`: input hash, attempted count, completed count, coverage and flags.

Stage-only commands intentionally do not produce joined firm rows. Use distinct
output directories as above; reports are replaced on every run, including empty
ones. Missing prices, invalid quotes, refusals, unsupported scores and truncated
responses require inspection. Cached invalid responses are not silently retried
with another model or prompt. Archive them and use a new cache after documenting
the correction. Oversized source text is rejected, never silently truncated.

The outcome matches the pilot: sum the two daily stock-minus-SPY returns for April
3 and April 4, using April 2 as the baseline. It is a sum of daily differences,
not a compounded buy-and-hold excess return. Missing symbols can create selection
bias; review failures against the **entire** manifest, not only successful rows.

After reviewing coverage (>95% per the data contract), membership, share classes,
model scores and exclusions, the PM can copy the joined CSV to
`data/processed/tariff_firms.csv`. The runner never publishes to the dashboard by
default. Human checks, beta-adjusted returns and the April 9 event remain blank.
Sector regressions need sufficient firms and score variation within sectors.

## Verification and current limits

```powershell
python -m unittest discover -s tests -v
python scripts/verify_tariff_pilot.py
```

All six tests passed on November 8, including a simulated 503-firm run and a
failed rerun that clears stale output. Tests cover caching, masking, unsupported
evidence, duplicate/cutoff rejection, invalid prices, the return calculation and
failed-firm reporting. Live Yahoo downloads also succeeded for SPY, AAPL, NKE and
VZ through the new runner; the original pilot's independent checks still pass.
New price vintages can differ slightly from the frozen pilot snapshot. API calls in
tests are mocks, not evidence of live LLM scoring. As of November 8, Charlie's
manifest/filings and a configured API key were unavailable; no full-universe run
or live API scoring has been completed. The existing pilot stays intact.

API format reference: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

## Scoring with Expected Parrot instead of OpenAI

The team has Expected Parrot keys, so scoring can also run through EDSL with
`--backend parrot`. The prompt, the 0-4 scale and every check are unchanged; see
`specs_tried.md` entry 11 for the differences. EDSL 1.0.x needs Python 3.10-3.13.
If your default Python is 3.14, make a separate environment with `uv`:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python edsl
read -s EXPECTED_PARROT_API_KEY && export EXPECTED_PARROT_API_KEY
.venv/bin/python scripts/tariff_batch.py --backend parrot --model <model> --manifest data/universe/manifest.csv --limit 3 --output outputs/batch_smoke
```

Each person uses their own key; never paste it into chat or a file in the repo.
