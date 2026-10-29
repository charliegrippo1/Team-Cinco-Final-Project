"""Five-event retrospective study. Python 3.10+; standard library only.

Run from any directory. Downloads are cached; --offline requires verified cache.
No trading strategy, fitted predictive model, or causal estimate is produced.
"""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw'
OUT = ROOT / 'data/processed'
EVENTS = [('2024-06-12', 0.0), ('2024-07-31', 0.0),
          ('2024-09-18', -0.5), ('2024-11-07', -0.25), ('2024-12-18', -0.25)]
SECTORS = {'XLK': 'Technology', 'XLF': 'Financials', 'XLU': 'Utilities'}
SURPRISE_URL = 'https://www.frbsf.org/wp-content/uploads/monetary-policy-surprises.zip'


def download(name, url, offline):
    path = RAW / name
    metadata = RAW / (name + '.metadata.json')
    if not path.exists():
        if offline:
            raise RuntimeError(f'Missing cached source: {name}; run without --offline first')
        print(f'Downloading {name}', flush=True)
        with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60) as response:
            body = response.read()
        path.write_bytes(body)
        metadata.write_text(json.dumps({'url': url, 'retrieved_utc': datetime.now(timezone.utc).isoformat(),
                                       'sha256': hashlib.sha256(body).hexdigest()}, indent=2))
    meta = json.loads(metadata.read_text())
    if meta['url'] != url or meta['sha256'] != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError(f'Cache provenance mismatch: {name}')
    return path.read_bytes(), meta


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def percent_return(current, previous):
    if not all(math.isfinite(p) and p > 0 for p in (current, previous)):
        raise ValueError('Nonpositive or nonfinite price')
    return 100 * (current / previous - 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for date, _ in EVENTS:
        url = f'https://www.federalreserve.gov/newsevents/pressreleases/monetary{date.replace("-", "")}a.htm'
        body, meta = download(f'statement_{date}.html', url, args.offline)
        if '2:00 p.m.' not in body.decode('utf-8'):
            raise ValueError(f'Unexpected statement release time: {date}')
        manifest.append(dict(file=f'statement_{date}.html', **meta))
    body, meta = download('monetary-policy-surprises.zip', SURPRISE_URL, args.offline)
    manifest.append(dict(file='monetary-policy-surprises.zip', **meta))
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        names = [n for n in archive.namelist() if n.endswith('mps.csv')]
        if len(names) != 1:
            raise ValueError(f'Ambiguous surprise CSV: {names}')
        records = list(csv.DictReader(io.StringIO(archive.read(names[0]).decode('utf-8-sig'))))
    surprises = {r['Date']: r for r in records}
    if len(surprises) != len(records):
        raise ValueError('Duplicate surprise dates')
    vintage = meta['retrieved_utc']
    prices = {}
    price_rows = []
    start = int(datetime(2024, 6, 1, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp())
    for ticker in [*SECTORS, 'SPY']:
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1={start}&period2={end}&interval=1d'
        body, meta = download(f'{ticker}.json', url, args.offline)
        manifest.append(dict(file=f'{ticker}.json', **meta))
        result = json.loads(body)['chart']['result'][0]
        values = result['indicators']['adjclose'][0]['adjclose']
        prices[ticker] = {}
        for stamp, price in zip(result['timestamp'], values, strict=True):
            # US regular-session daily bars are daytime UTC; UTC and NY calendar dates agree.
            moment = datetime.fromtimestamp(stamp, timezone.utc)
            if not 13 <= moment.hour <= 21:
                raise ValueError('Unexpected daily-bar timestamp; review session alignment')
            date = moment.date().isoformat()
            if date in prices[ticker]:
                raise ValueError(f'Duplicate session: {ticker} {date}')
            prices[ticker][date] = price
            price_rows.append({'date': date, 'ticker': ticker, 'adjusted_close_usd': price})
    sessions = sorted(prices['SPY'])
    rows, trace = [], []
    for date, change in EVENTS:
        i = sessions.index(date)
        if i < 2 or i + 1 >= len(sessions):
            raise ValueError('Incomplete event window')
        window = sessions[i-2:i+2]
        for ticker, sector in SECTORS.items():
            differences = []
            for j in range(1, 4):
                previous, current = window[j-1:j+1]
                needed = [prices[t].get(d) for t in (ticker, 'SPY') for d in (previous, current)]
                if any(p is None for p in needed):
                    raise ValueError(f'Missing price in window: {date} {ticker}; no imputation permitted')
                etf_return = percent_return(prices[ticker][current], prices[ticker][previous])
                market_return = percent_return(prices['SPY'][current], prices['SPY'][previous])
                differences.append(etf_return - market_return)
                trace.append({'meeting_date': date, 'ticker': ticker, 'relative_day': j-2,
                              'previous_session': previous, 'session': current,
                              'etf_previous_close': prices[ticker][previous], 'etf_close': prices[ticker][current],
                              'spy_previous_close': prices['SPY'][previous], 'spy_close': prices['SPY'][current],
                              'etf_return_pct': etf_return, 'spy_return_pct': market_return,
                              'market_adjusted_return_pp': etf_return-market_return})
                if j == 2:
                    day0 = (etf_return, market_return)
            shock = surprises.get(date, {}).get('ME', '')
            shock_value = float(shock) if shock and shock != 'NA' else None
            if shock_value is not None and not math.isfinite(shock_value):
                raise ValueError('Nonfinite surprise')
            rows.append({'meeting_date': date, 'announcement_time_et': '14:00', 'scheduled': True,
                         'ticker': ticker, 'sector': sector, 'fed_rate_change_pp': change,
                         'expected_target_change_pp': '', 'target_surprise_pp': '',
                         'policy_news_surprise_pp': shock_value,
                         'surprise_missing_reason': '' if shock_value is not None else 'USMPD ME unavailable',
                         'surprise_measure': 'USMPD published ME factor',
                         'surprise_window': 'statement and press conference', 'source_vintage_utc': vintage,
                         'day0_return_pct': day0[0], 'market_return_pct': day0[1],
                         'abnormal_return_pp': differences[1], 'car_3d_pp': sum(differences),
                         'window_start': window[1], 'window_end': window[3]})
    if len(rows) != 15 or len({(r['meeting_date'], r['ticker']) for r in rows}) != 15:
        raise ValueError('Unexpected final row count or duplicate keys')
    write_csv(OUT / 'event_returns.csv', rows)
    write_csv(OUT / 'calculation_trace.csv', trace)
    write_csv(OUT / 'adjusted_prices.csv', price_rows)
    (OUT / 'source_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    summary = {'events': len(EVENTS), 'sector_etfs': len(SECTORS), 'final_rows': len(rows),
               'trace_rows': len(trace), 'missing_policy_surprises': sum(r['policy_news_surprise_pp'] is None for r in rows),
               'duplicate_keys': 0, 'missing_required_window_prices': 0,
               'sample_selection': 'Last five scheduled FOMC meetings of 2024; feasibility only'}
    (OUT / 'validation.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
