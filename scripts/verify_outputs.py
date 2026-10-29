"""Independently recompute exported results with decimal arithmetic."""
import csv
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/processed'


def read(name):
    with (DATA / name).open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


def main():
    prices = {(r['ticker'], r['date']): Decimal(r['adjusted_close_usd'])
              for r in read('adjusted_prices.csv')}
    rows = read('event_returns.csv')
    sessions = sorted(d for t, d in prices if t == 'SPY')
    assert len(rows) == 15
    examples = []
    for row in rows:
        date, ticker = row['meeting_date'], row['ticker']
        i = sessions.index(date)
        differences = []
        for k in (i-1, i, i+1):
            today, yesterday = sessions[k], sessions[k-1]
            etf = 100 * (prices[ticker, today] / prices[ticker, yesterday] - 1)
            spy = 100 * (prices['SPY', today] / prices['SPY', yesterday] - 1)
            differences.append(etf-spy)
            if k == i:
                assert abs(etf-Decimal(row['day0_return_pct'])) < Decimal('1e-9')
                assert abs(spy-Decimal(row['market_return_pct'])) < Decimal('1e-9')
        assert abs(differences[1]-Decimal(row['abnormal_return_pp'])) < Decimal('1e-9')
        assert abs(sum(differences)-Decimal(row['car_3d_pp'])) < Decimal('1e-9')
        if ticker == 'XLK':
            examples.append(f"| {date} | {prices[ticker, sessions[i-1]]:.8f} | {prices[ticker, date]:.8f} | {Decimal(row['day0_return_pct']):.6f} | {Decimal(row['market_return_pct']):.6f} | {differences[1]:.6f} |")
    audit = ROOT / 'audits'
    audit.mkdir(exist_ok=True)
    (audit / 'poc_calculation_checks.md').write_text(
        '# Proof-of-concept calculation checks\n\n'
        'All 15 rows independently recomputed from exported adjusted prices using Decimal arithmetic. '
        'Day-0 ETF returns, benchmark returns, return differences, and three-session sums agree to within 1e-9 percentage points. '
        'This checks arithmetic and window selection, not independent vendor accuracy.\n\n'
        'Five XLK examples for manual inspection; values below are rounded only for display.\n\n'
        '| Meeting | Previous adjusted close | Event adjusted close | ETF return (%) | SPY return (%) | Difference (pp) |\n'
        '|---|---:|---:|---:|---:|---:|\n' + '\n'.join(examples) + '\n', encoding='utf-8')
    print('PASS: 15 observations independently recomputed; audit table written.')


if __name__ == '__main__':
    main()
