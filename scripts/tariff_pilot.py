"""Rebuild Gunnar's dashboard input. Use --download to acquire a new price vintage."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from math import isfinite
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "data/pilot"
OUT = ROOT / "data/processed/tariff_firms.csv"
DATES = ("2025-04-02", "2025-04-03", "2025-04-04")


def read(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def download(tickers):
    start = int(datetime(2025, 4, 2, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2025, 4, 5, tzinfo=timezone.utc).timestamp())
    prices = []
    for ticker in tickers:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start}&period2={end}&interval=1d"
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as stream:
            payload = stream.read()
        result = json.loads(payload)["chart"]["result"][0]
        if result["meta"]["symbol"] != ticker:
            raise ValueError(f"Unexpected price response for {ticker}")
        retrieved = datetime.now(timezone.utc).isoformat()
        dates = []
        for stamp, close in zip(result["timestamp"], result["indicators"]["adjclose"][0]["adjclose"], strict=True):
            session = datetime.fromtimestamp(stamp, timezone.utc).date().isoformat()
            dates.append(session)
            if close is None or not isfinite(close) or close <= 0:
                raise ValueError(f"Invalid adjusted close for {ticker} on {session}")
            prices.append(dict(ticker=ticker, session=session, adjusted_close=close, source_url=url,
                               retrieved_utc=retrieved, response_sha256=hashlib.sha256(payload).hexdigest()))
        if tuple(dates) != DATES:
            raise ValueError(f"Unexpected trading sessions for {ticker}: {dates}")
    write(PILOT / "event_prices.csv", prices)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    firms = read(PILOT / "filing_scores.csv")
    tickers = [r["ticker"] for r in firms]
    if len(set(tickers)) != len(tickers) or len(tickers) < 3:
        raise ValueError("Pilot requires at least three unique firms")
    if args.download:
        download([*tickers, "SPY"])
    prices = read(PILOT / "event_prices.csv")
    by_key = {(r["ticker"], r["session"]): float(r["adjusted_close"]) for r in prices}
    expected = {(t, d) for t in [*tickers, "SPY"] for d in DATES}
    if set(by_key) != expected or len(prices) != len(expected):
        raise ValueError("Incomplete price snapshot or duplicate ticker/date")
    if not all(isfinite(p) and p > 0 for p in by_key.values()):
        raise ValueError("Invalid adjusted close")

    def returns(ticker):
        closes = [by_key[ticker, date] for date in DATES]
        return [100 * (current / previous - 1) for previous, current in zip(closes, closes[1:])]

    spy3, spy4 = returns("SPY")
    rows = []
    for firm in firms:
        if firm["tenk_filing_date"] >= DATES[0] or not 0 <= int(firm["exposure_score"]) <= 4:
            raise ValueError(f"Invalid filing date or score for {firm['ticker']}")
        if not firm["exposure_evidence"] or len(firm["cik"]) != 10 or float(firm["mktcap_usd_bn"]) <= 0:
            raise ValueError("Missing evidence, CIK, or capitalization")
        r3, r4 = returns(firm["ticker"])
        row = {k: v for k, v in firm.items() if k not in ("rationale", "cap_source")}
        row.update(hand_score="", ret_apr3_pct=r3, ret_apr4_pct=r4, mkt_apr3_pct=spy3,
                   mkt_apr4_pct=spy4, car_pp=(r3-spy3)+(r4-spy4), car_mm_pp="", car_pause_pp="",
                   sample="checkpoint_1_pilot")
        rows.append(row)
    write(OUT, rows)
    print(f"Wrote {len(rows)} real firm rows to {OUT.name}")


if __name__ == "__main__":
    main()
