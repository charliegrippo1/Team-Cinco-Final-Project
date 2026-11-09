"""Check published rows against the frozen prices and filing inputs using Decimal."""
import csv
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    with (ROOT / path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    prices = {(r["ticker"], r["session"]): Decimal(r["adjusted_close"])
              for r in read("data/pilot/event_prices.csv")}
    filings = {r["ticker"]: r for r in read("data/pilot/filing_scores.csv")}
    rows = read("data/processed/tariff_firms.csv")
    if len(rows) != 3 or {r["ticker"] for r in rows} != set(filings):
        raise ValueError("Expected one row per pilot firm")
    for row in rows:
        t = row["ticker"]
        if any(row[k] != filings[t][k] for k in ("cik", "tenk_filing_date", "tenk_accession", "exposure_score", "exposure_evidence")):
            raise ValueError(f"Filing join mismatch for {t}")
        car = Decimal(0)
        for day, previous in [(3, 2), (4, 3)]:
            def daily(symbol):
                today = prices[symbol, f"2025-04-0{day}"]
                prior = prices[symbol, f"2025-04-0{previous}"]
                return (today - prior) * 100 / prior
            stock, market = daily(t), daily("SPY")
            for key, expected in [(f"ret_apr{day}_pct", stock), (f"mkt_apr{day}_pct", market)]:
                if abs(expected - Decimal(row[key])) > Decimal("1e-9"):
                    raise ValueError(f"{t} {key} differs from price snapshot")
            car += stock - market
        if abs(car - Decimal(row["car_pp"])) > Decimal("1e-9"):
            raise ValueError(f"{t} two-day CAR mismatch")
        print(f"{t}: verified {car:+.4f} pp")


if __name__ == "__main__":
    main()
