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

    def parrot_reply(self, text):
        return dict(status='completed', model='test', id='', output_text=text)

    def test_parrot_backend_scores_caches_and_keeps_separate_cache(self):
        reply = '```json\n' + json.dumps(dict(score=4, evidence='imports most of its goods from China.',
                                               rationale='Substantial import dependence.')) + '\n```'
        with patch.dict(batch.os.environ, {'EXPECTED_PARROT_API_KEY': 'test-only'}), patch.object(
                batch, 'parrot_request', return_value=self.parrot_reply(reply)) as api:
            result, log = batch.score(self.firm, self.root, 'test', backend='parrot')
            self.assertEqual(result['score'], 4)
            batch.score(self.firm, self.root, 'test', offline=True, backend='parrot')
            self.assertEqual(api.call_count, 1)          # second call came from the cache
            self.assertIn('Reply with only a JSON object', api.call_args.args[0])
        # The OpenAI and Expected Parrot answers never share a cache file.
        with self.assertRaisesRegex(ValueError, 'No cached score'):
            batch.score(self.firm, self.root, 'test', offline=True)

    def test_parrot_backend_rejects_bad_json_and_fabricated_quote(self):
        with patch.dict(batch.os.environ, {'EXPECTED_PARROT_API_KEY': 'test-only'}):
            with patch.object(batch, 'parrot_request', return_value=self.parrot_reply('Score: 4')):
                with self.assertRaisesRegex(ValueError, 'not valid JSON'):
                    batch.score(self.firm, self.root, 'a', backend='parrot')
            fake = json.dumps(dict(score=4, evidence='not in the filing', rationale='x'))
            with patch.object(batch, 'parrot_request', return_value=self.parrot_reply(fake)):
                with self.assertRaisesRegex(ValueError, 'exact quote'):
                    batch.score(self.firm, self.root, 'b', backend='parrot')

    def test_parrot_request_with_real_edsl_offline_model(self):
        # Runs the real EDSL code path with EDSL's built-in offline "test" model (no API call,
        # no credits). Skipped when edsl is not installed (it needs Python 3.10-3.13).
        try:
            from edsl import Model
        except ImportError:
            self.skipTest('edsl not installed')
        text = self.text.read_text(encoding='utf-8')
        reply = json.dumps(dict(score=4, evidence='imports most of its goods from China.', rationale='r'))
        out = batch.parrot_request('Score it.', text, 'unused',
                                   edsl_model=Model('test', canned_response=reply))
        self.assertEqual(out['status'], 'completed')
        self.assertEqual(batch.parse_reply(out['output_text'])['score'], 4)
        with self.assertRaisesRegex(ValueError, 'changed the filing text'):
            batch.parrot_request('Score it.', 'A {{template}} in a filing', 'unused',
                                 edsl_model=Model('test', canned_response=reply))

    def test_wrapping_quote_marks_dropped_but_stitched_quotes_rejected(self):
        self.text.write_text('Example Corp imports most of its goods from China. '
                             'It also sells in Europe.', encoding='utf-8')
        with patch.dict(batch.os.environ, {'EXPECTED_PARROT_API_KEY': 'test-only'}):
            wrapped = json.dumps(dict(score=4, evidence='“imports most of its goods from China.”',
                                      rationale='r'))
            with patch.object(batch, 'parrot_request', return_value=self.parrot_reply(wrapped)):
                result, _ = batch.score(self.firm, self.root, 'a', backend='parrot')
                self.assertEqual(result['evidence'], 'imports most of its goods from China.')
            stitched = json.dumps(dict(score=4, evidence='"imports most of its goods... sells in Europe."',
                                       rationale='r'))
            with patch.object(batch, 'parrot_request', return_value=self.parrot_reply(stitched)):
                with self.assertRaisesRegex(ValueError, 'exact quote'):
                    batch.score(self.firm, self.root, 'b', backend='parrot')

    def test_parrot_backend_needs_its_own_key(self):
        with patch.dict(batch.os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'EXPECTED_PARROT_API_KEY'):
                batch.score(self.firm, self.root, 'test', backend='parrot')


if __name__ == '__main__':
    unittest.main()
