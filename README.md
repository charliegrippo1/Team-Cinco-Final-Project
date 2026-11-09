# Who lost on Liberation Day?
Team Cinco · FIN 331 · Checkpoint 1

Did S&P 500 firms whose annual reports described greater dependence on imports or overseas manufacturing lose more relative to the market after the April 2, 2025 U.S. tariff announcement? Gunnar Krein built the Streamlit dashboard and defined its [firm-level data contract](docs/DATA_CONTRACT.md). This checkpoint supplies its first three real observations.

## What the pilot shows
| Firm | Filing exposure (0–4) | April 3–4 return relative to SPY |
|---|---:|---:|
| Apple (AAPL) | 4 | −5.75 pp |
| Nike (NKE) | 4 | −0.65 pp |
| Verizon (VZ) | 2 | +7.07 pp |

Apple and Nike received the same preliminary score, yet their market-adjusted returns differed by about five percentage points. The sample was selected to exercise the workflow across hardware, footwear, and communications. These three examples support checking the measurement process. Estimating the relationship across firms requires a larger sample and industry controls. [Firm rows](data/processed/tariff_firms.csv) · [Checkpoint memo](STATUS.md)

## Run the pilot and dashboard
From the repository root with Python 3.10 or later:

```bash
python scripts/tariff_pilot.py
python scripts/verify_tariff_pilot.py
python -m pip install -r requirements.txt
python -m streamlit run dashboard/app.py
```

The first two commands use only Python’s standard library and the checked-in price snapshot. The dashboard opens with these real firms. Its firm explorer links to the cited filings. To obtain a fresh Yahoo price vintage, run `python scripts/tariff_pilot.py --download` and rerun the verification command. Downloaded prices can be revised. Gunnar’s labeled synthetic dataset remains available for dashboard development.

## How one row is built

**Scaling beyond the pilot:** Carter's [batch pipeline guide](docs/CARTER_PIPELINE.md)
describes resumable LLM scoring, masked reruns, all-firm price downloads, and the
manifest expected from Charlie. The batch runner stages results separately for
review; the full-universe inputs and live scoring run are still pending.
1. **Choose the firm.** The intended universe is the S&P 500 on April 2. Apple, Nike and Verizon appear in SPY’s March 31 holdings. This nearby holdings snapshot is the pilot membership proxy. An exact event-date constituent list is a full-sample task. [SPY schedule of investments](https://www.sec.gov/Archives/edgar/data/884394/000119312525130577/d931023dn30d.htm)
2. **Read the filing.** Use a 10-K filed before April 2. Each pilot record includes its filing date, SEC accession, CIK, exact passage, sector and source link. The same input records include vendor estimates of market capitalization on March 31 in USD billions and their sources. [Filing inputs and size sources](data/pilot/filing_scores.csv)
3. **Score exposure.** Apply Gunnar’s 0–4 rubric to filing evidence before joining returns. For this pilot, Codex assigned provisional scores from selected excerpts. The frozen judgments make the output reproducible. A teammate’s blind hand score and a separate masked scoring run are still pending. [Scoring record](outputs/llm_run_log.csv)
4. **Measure the reaction.** April 2 is the baseline close. April 3 is day 0 and April 4 is day +1. For each session calculate 100 × (current adjusted close / prior adjusted close − 1). Subtract that day’s SPY return from the stock return and sum both differences. A positive value means the firm beat SPY over this measure. Other news during those two days can also affect returns. [Tariff order](https://www.whitehouse.gov/presidential-actions/2025/04/regulating-imports-with-a-reciprocal-tariff-to-rectify-trade-practices-that-contribute-to-large-and-persistent-annual-united-states-goods-trade-deficits/) · [Price snapshot and provenance](data/pilot/event_prices.csv)
5. **Scale the analysis.** Verify event-date membership, expand the filings, check inter-rater agreement, and compare exposure-only, sector-only and combined models. The optional beta-adjusted return and April 9 pause fields are blank in the pilot.

## Reviewing the checkpoint
Start with the [status memo](STATUS.md), rerun the two pilot scripts, and compare the [results](data/processed/tariff_firms.csv) with the dashboard’s **Explore a firm** tab. Gunnar’s [dashboard guide](dashboard/README.md) describes the larger-sample views.
