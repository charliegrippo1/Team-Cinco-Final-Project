"""Check that the dashboard shows exactly what is in its data file.

Opens dashboard/app.py in Streamlit's test browser (AppTest), with whatever is in
data/processed/tariff_firms.csv (the v0 rows from run_all.py; previously the
three-firm pilot). For every firm it checks:
  - the Results table lists the firm with the same car_pp as the file
  - picking the firm in "Explore a firm" shows the same abnormal return and the
    same 10-K evidence quote as the file
and, when hand scores exist, that the hand-check agreement shown matches the file.

Written by Carter as verify_pilot_dashboard.py; generalized from the 3-firm pilot
to any firms in the file when the v0 data replaced the pilot (specs_tried.md #17).

Run from the repository root:  python scripts/verify_dashboard.py
"""
import csv
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def main():
    with (ROOT / "data/processed/tariff_firms.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("data/processed/tariff_firms.csv is empty. Run python run_all.py first.")
    if any(row["sample"] == "fake" for row in rows):
        raise ValueError("The dashboard data file holds fake rows.")

    app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=90).run()
    if app.exception:
        raise RuntimeError([exc.message for exc in app.exception])
    table = app.dataframe[0].value.set_index("ticker")
    assert set(table.index) == {row["ticker"] for row in rows}, "Results table firms differ from the file"
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

    hand = [row for row in rows if row.get("hand_score")]
    if hand:
        exact = sum(float(r["hand_score"]) == float(r["exposure_score"]) for r in hand) / len(hand)
        shown = " ".join(m.value for m in app.markdown)
        assert f"**{len(hand)}** hand-scored firms" in shown and f"**{exact:.0%}**" in shown, "hand-check summary"
        print(f"Hand check: {len(hand)} firms, {exact:.0%} exact agreement shown")


if __name__ == "__main__":
    main()
