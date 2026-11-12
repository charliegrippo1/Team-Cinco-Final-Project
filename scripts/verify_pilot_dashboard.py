"""Exercise the pilot dashboard with Streamlit AppTest, including the firm selector."""
import csv
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def main():
    with (ROOT / "data/processed/tariff_firms.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or any(row["sample"] != "checkpoint_1_pilot" for row in rows):
        raise ValueError("This check requires the three-firm pilot. Run scripts/tariff_pilot.py first.")

    app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=90).run()
    if app.exception:
        raise RuntimeError([exc.message for exc in app.exception])
    table = app.dataframe[0].value.set_index("ticker")
    assert set(table.index) == {row["ticker"] for row in rows}
    for row in rows:
        ticker = row["ticker"]
        assert abs(float(table.at[ticker, "car_pp"]) - float(row["car_pp"])) < 1e-9, ticker
        app.selectbox[0].select(f"{ticker} — {row['company']}").run()
        if app.exception:
            raise RuntimeError([exc.message for exc in app.exception])
        metrics = {metric.label: metric.value for metric in app.metric}
        expected = f"{float(row['car_pp']):+.2f} pp"
        assert metrics["Abnormal return, Apr 3–4"] == expected, ticker
        assert any(info.value == row["exposure_evidence"] for info in app.info), ticker
        print(f"{ticker}: {expected} and filing evidence matched")


if __name__ == "__main__":
    main()
