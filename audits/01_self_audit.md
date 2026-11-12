# Checkpoint 2 self-audit

November 11, 2026 · Team Cinco · Seed 5 · Pilot reviewed at `cae223c`

The three published firm rows reproduce from the checked-in inputs. The pilot measures how Apple, Nike and Verizon performed relative to SPY over April 3–4, 2025. With one firm per sector and two distinct exposure scores, it cannot estimate whether tariff exposure predicts returns within an industry.

## Trace one observation

Nike's July 25, 2024 filing predates the April 2 announcement. In Item 1, under Manufacturing, Nike reports that Vietnam, Indonesia and China accounted for about 95% of fiscal 2024 NIKE Brand footwear production in total. This supports substantial overseas manufacturing dependence. The passage measures production geography. It does not specify what fraction of that footwear entered the US or the duties Nike paid. The pilot records a preliminary exposure score of 4 on the team's 0–4 scale. [Nike 10-K](https://www.sec.gov/Archives/edgar/data/320187/000032018724000044/nke-20240531.htm) · [Scoring input](../data/pilot/filing_scores.csv)

The baseline is the April 2 close. For each of the next two sessions, divide today's adjusted close by yesterday's, subtract one and multiply by 100. Subtract SPY's daily return from Nike's daily return, then add the two differences. Calculations use the full precision in the [frozen price snapshot](../data/pilot/event_prices.csv).

| Session | NKE return | SPY return | NKE minus SPY |
| --- | ---: | ---: | ---: |
| April 3 | −14.4396% | −4.9281% | −9.5116 pp |
| April 4 | +3.0047% | −5.8543% | +8.8590 pp |

Nike underperformed SPY by **0.6526 percentage points** over both days. The small two-day difference hides a substantial reversal. April 4 includes news about Chinese retaliation, so an April 3-only result answers a different question. Retain both dates and label any one-day sensitivity check. [Published firm rows](../data/processed/tariff_firms.csv)

## Reproduce the checks

Run these commands from the repository root with Python 3.10 or later.

```sh
python scripts/tariff_pilot.py
python scripts/verify_tariff_pilot.py
git diff --exit-code -- data/processed/tariff_firms.csv
```

The rebuild produced three rows and a clean diff. It required twelve unique ticker/session prices covering the three firms and SPY, rejected missing or nonpositive prices, and checked filing dates against the event cutoff. The independent Decimal calculation matched both daily returns, both market returns and each cumulative difference within 0.000000001 percentage points. It also matched each output to its input CIK, filing date, accession, score and evidence. Results were AAPL −5.7520 pp, NKE −0.6526 pp and VZ +7.0720 pp. Both calculations use the same price source. [Pilot builder](../scripts/tariff_pilot.py) · [Independent calculation](../scripts/verify_tariff_pilot.py)

## Open findings

To exercise the dashboard, install `requirements.txt` and run `python scripts/verify_pilot_dashboard.py`. The check reads the Results table, selects each firm in the explorer, and compares its displayed return and evidence with the published CSV. The [pilot audit workflow](../.github/workflows/pilot-audit.yml) runs the rebuild, arithmetic and dashboard checks on Linux. Local Windows AppTest timed out during the initial run.

| Finding | Consequence and next check |
| --- | --- |
| The pilot replays three saved judgments from selected excerpts. The hand-score fields are empty. | A model could recognize the firms or recall their returns. Have a teammate score anonymized filing text before seeing model scores or returns. Compare the human, masked-model and original scores and keep disagreements. [Scoring log](../outputs/llm_run_log.csv) |
| The three firms were deliberately chosen across industries. Apple's and Nike's scores both equal 4, yet their returns differ by about 5.10 pp. | The pilot supports checking the workflow. Estimate the exposure relationship only after checking full-sample sector coverage and within-sector score variation. |
| Charlie reconstructed the event-date universe using March 31 SPY holdings and a check for intervening index changes. His November 9 branch records 470 successful filing extractions and 30 failures across 500 firms. | Track all 500 firms through extraction, scoring and price retrieval. Report failures by sector and check the price history for renamed or delisted tickers. A coverage percentage calculated only from the five-row manifest misses upstream exclusions. [Universe decisions](https://github.com/charliegrippo1/Team-Cinco-Final-Project/blob/bcb6ab1/specs_tried.md) |
| Nike's pilot market cap is $91.49bn. Charlie's five-firm manifest estimates $95.18bn using cover-page shares and a March 31 price, and flags Nike's two share classes. | Reconcile class conversion and share-count dates before using size as a control. This discrepancy does not enter the pilot return calculation. [Manifest review](https://github.com/charliegrippo1/Team-Cinco-Final-Project/blob/bcb6ab1/data/universe/manifest_review.csv) |
