# Dashboard: Who lost on Liberation Day?

Owner: Gunnar Krein (product manager / dashboard)

## Run it

```bash
pip install -r requirements.txt
python scripts/make_toy_data.py      # only needed until the real data exists
streamlit run dashboard/app.py
```

## Where the data comes from

| File | What it is |
|---|---|
| `data/processed/tariff_firms.csv` | **Real** final dataset, written by the pipeline. If it exists, the app uses it. |
| `data/toy/tariff_firms_FAKE.csv` | **Fake** data from `scripts/make_toy_data.py`, used until the real file exists. The app shows a red banner when it's using this. |

Both files follow `docs/DATA_CONTRACT.md`. To switch to real data, the pipeline writes `data/processed/tariff_firms.csv` with those columns, and nothing in the app changes.

## Pages (as the project rubric requires)

1. **Overview:** headline numbers and the main chart (average abnormal return by exposure score).
2. **Methodology:** timeline and day 0, the pipeline steps, the exposure rubric, threats to validity, and LLM hand-check agreement.
3. **Results:** exposure vs. CAR scatter (filter by sector in the sidebar), three regressions, and a sector-level view.
4. **Explore a firm:** look up any firm and see its score, its 10-K evidence quote and its return, plus a downloadable table.

## How the regressions work

`run_regressions()` fits three OLS models with robust (HC3) standard errors:

- (1) `CAR ~ exposure_score`
- (2) `CAR ~ sector dummies`
- (3) `CAR ~ exposure_score + sector dummies`

Comparing (3) to (2) answers the auditor question "does the 10-K measure beat simple industry dummies?"

## To do before the final version

- [ ] Point the app at the real data once the pipeline produces it.
- [ ] Move the regression into an analysis script that saves `outputs/regressions.csv`, and have the app read that file (the rubric says every number on the dashboard should trace to `outputs/`).
- [ ] Add the April 9 pause view (`car_pause_pp`) if we do the stretch goal.
- [ ] Deploy on Streamlit Community Cloud and put the link in the main README.
