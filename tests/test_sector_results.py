import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sector_results import write_sector_results


class SectorTests(unittest.TestCase):
    def test_sector_comparison_and_april3_use_same_sample(self):
        rng = np.random.default_rng(331)
        scores = np.tile(np.arange(5), 12)
        sectors = np.repeat(['A', 'B', 'C'], 20)
        data = pd.DataFrame(dict(ticker=[f'X{i}' for i in range(60)],
                                 gics_sector=sectors, exposure_score=scores,
                                 car_pp=2 * scores + (sectors == 'B') * 5 + rng.normal(size=60),
                                 ret_apr3_pct=rng.normal(size=60), mkt_apr3_pct=-2.0))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            write_sector_results(data, out, 'test')
            comparison = pd.read_csv(out / 'test_sector_comparison.csv').set_index('outcome')
            estimates = pd.read_csv(out / 'test_sector_regressions.csv')
            full = smf.ols('car_pp ~ exposure_score + C(gics_sector)', data).fit(cov_type='HC3', use_t=True)
            sector = smf.ols('car_pp ~ C(gics_sector)', data).fit()
            self.assertAlmostEqual(comparison.loc['car_pp', 'delta_adjusted_r2'],
                                   full.rsquared_adj - sector.rsquared_adj, places=6)
            self.assertAlmostEqual(comparison.loc['car_pp', 'hc3_wald_f'],
                                   float(full.f_test('exposure_score = 0').fvalue), places=6)
            self.assertTrue((estimates.n == 60).all())
            analysis = pd.read_csv(out / 'test_analysis_firms.csv')
            np.testing.assert_allclose(analysis.apr3_pp, data.ret_apr3_pct + 2)

    def test_collinear_sector_score_does_not_report_significance(self):
        data = pd.DataFrame(dict(ticker=['A', 'B', 'C', 'D'], gics_sector=['X', 'X', 'Y', 'Y'],
                                 exposure_score=[0, 0, 4, 4], car_pp=[1, 2, 3, 4],
                                 ret_apr3_pct=[1, 1, 2, 2], mkt_apr3_pct=[0] * 4))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            write_sector_results(data, out, 'test')
            comparison = pd.read_csv(out / 'test_sector_comparison.csv')
            self.assertTrue((comparison.status == 'rank_deficient').all())
            self.assertTrue(comparison.p.isna().all())


if __name__ == '__main__':
    unittest.main()
