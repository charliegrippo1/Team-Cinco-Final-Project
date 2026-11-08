import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import tariff_batch as batch


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.text = self.root / 'filing.txt'
        self.text.write_text('Example Corp imports most of its goods from China.', encoding='utf-8')
        self.firm = dict(ticker='EXM', company='Example Corp', cik='0000000001',
                         gics_sector='Industrials', mktcap_usd_bn='10',
                         tenk_filing_date='2025-02-01', tenk_accession='test', filing_url='https://example.com',
                         text_path=str(self.text), membership_date='2025-04-02',
                         membership_source='fixture', cap_source='fixture')

    def response(self, evidence='imports most of its goods from China.'):
        return dict(status='completed', model='test-snapshot', id='test-id',
                    output=[dict(content=[dict(type='output_text', text=json.dumps(
                        dict(score=4, evidence=evidence, rationale='Substantial import dependence.')))])])

    def test_score_resume_and_masked_cache_separation(self):
        with patch.dict(batch.os.environ, {'OPENAI_API_KEY': 'test-only'}), patch.object(
                batch, 'request_json', return_value=self.response()) as api:
            batch.score(self.firm, self.root, 'test')
            batch.score(self.firm, self.root, 'test', offline=True)
            self.assertEqual(api.call_count, 1)
            batch.score(self.firm, self.root, 'test', masked=True)
            self.assertEqual(api.call_count, 2)
            body = api.call_args.args[1]
            self.assertNotIn('Example Corp', body['input'])
            self.assertNotIn('2025-04-02', json.dumps(body))

    def test_fabricated_quote_rejected(self):
        with patch.dict(batch.os.environ, {'OPENAI_API_KEY': 'test-only'}), patch.object(
                batch, 'request_json', return_value=self.response('not in the filing')):
            with self.assertRaisesRegex(ValueError, 'exact quote'):
                batch.score(self.firm, self.root, 'test')

    def test_price_sessions_and_missing_close(self):
        data = dict(meta=dict(symbol='EXM'), timestamp=[1743638400, 1743724800, 1743811200],
                    indicators=dict(adjclose=[dict(adjclose=[100, 90, 81])]))
        # Generate timestamps explicitly for the three expected UTC dates.
        data['timestamp'] = [int(batch.datetime.fromisoformat(d).replace(tzinfo=batch.timezone.utc).timestamp())
                             for d in batch.DATES]
        with patch.object(batch, 'request_json', return_value={'chart': {'result': [data]}}):
            closes, _ = batch.prices('EXM', self.root)
            self.assertAlmostEqual(batch.daily(closes)[0], -10)
        cache = self.root / 'prices' / (batch.digest('EXM') + '.json')
        record = json.loads(cache.read_text())
        record['response']['chart']['result'][0]['indicators']['adjclose'][0]['adjclose'][1] = None
        batch.save(cache, record)
        with self.assertRaisesRegex(ValueError, 'Invalid adjusted'):
            batch.prices('EXM', self.root, offline=True)

    def test_manifest_cutoff_and_duplicates(self):
        path = self.root / 'manifest.csv'
        batch.write(path, [self.firm, self.firm])
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            batch.manifest(path)
        batch.write(path, [dict(self.firm, tenk_filing_date='2025-04-02')])
        with self.assertRaisesRegex(ValueError, 'Post-cutoff'):
            batch.manifest(path)

    def test_all_stage_reports_failed_firm_without_hiding_it(self):
        path = self.root / 'manifest.csv'
        batch.write(path, [self.firm, dict(self.firm, ticker='FAIL')])
        args = SimpleNamespace(manifest=path, limit=None, cache=self.root, model='test',
                               masked=False, offline=True, stage='all', output=self.root / 'out')
        def scoring(firm, *a):
            if firm['ticker'] == 'FAIL':
                raise ValueError('Missing text')
            return dict(score=4, evidence='quote'), dict(ticker=firm['ticker'])
        def pricing(symbol, *a):
            return ([100, 95, 95] if symbol == 'SPY' else [100, 90, 81]), dict(
                url='fixture', retrieved_utc='fixture', response={})
        with patch.object(batch, 'score', side_effect=scoring), patch.object(batch, 'prices', side_effect=pricing):
            self.assertEqual(batch.run(args), 1)
        rows = batch.read(args.output / 'tariff_firms.csv')
        self.assertAlmostEqual(float(rows[0]['car_pp']), -15)
        self.assertEqual(batch.read(args.output / 'failures.csv')[0]['ticker'], 'FAIL')
        self.assertEqual(json.loads((args.output / 'summary.json').read_text())['coverage'], .5)

    def test_503_firms_then_failed_rerun_clears_stale_rows(self):
        path = self.root / 'manifest.csv'
        batch.write(path, [dict(self.firm, ticker=f'X{i}') for i in range(503)])
        args = SimpleNamespace(manifest=path, limit=None, cache=self.root, model='test',
                               masked=False, offline=True, stage='all', output=self.root / 'out')
        with patch.object(batch, 'score', return_value=(dict(score=4, evidence='quote'), dict(model='fixture'))), \
                patch.object(batch, 'prices', return_value=([100, 99, 98], dict(url='fixture', retrieved_utc='fixture', response={}))), \
                patch('builtins.print'):
            self.assertEqual(batch.run(args), 0)
        self.assertEqual(len(batch.read(args.output / 'tariff_firms.csv')), 503)
        with patch.object(batch, 'score', side_effect=ValueError('No cache')), patch('builtins.print'):
            self.assertEqual(batch.run(args), 1)
        self.assertEqual(batch.read(args.output / 'tariff_firms.csv'), [])
        self.assertEqual(len(batch.read(args.output / 'failures.csv')), 503)


if __name__ == '__main__':
    unittest.main()
