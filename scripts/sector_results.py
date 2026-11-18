"""A1 sector comparison and April 3 sensitivity on the same complete firms."""
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


def write_sector_results(firms, output, prefix):
    columns = ["ticker", "gics_sector", "exposure_score", "car_pp",
               "ret_apr3_pct", "mkt_apr3_pct"]
    data = firms[columns].copy()
    if data.isna().any().any() or not data.ticker.is_unique:
        raise ValueError("Sector analysis needs unique firms and complete analysis columns")
    numeric = columns[2:]
    if not np.isfinite(data[numeric].to_numpy(dtype=float)).all():
        raise ValueError("Nonfinite regression inputs")
    data["apr3_pp"] = data.ret_apr3_pct - data.mkt_apr3_pct
    data.to_csv(output / f"{prefix}_analysis_firms.csv", index=False, lineterminator="\n")
    estimates, comparisons = [], []
    for outcome in ("car_pp", "apr3_pp"):
        fits = {}
        for name, rhs in (("exposure", "exposure_score"), ("sector", "C(gics_sector)"),
                          ("sector_exposure", "exposure_score + C(gics_sector)")):
            base = smf.ols(f"{outcome} ~ {rhs}", data=data, missing="raise").fit()
            design = base.model.exog
            leverage = base.get_influence().hat_matrix_diag
            rank_ok = np.linalg.matrix_rank(design) == design.shape[1]
            status = "ok"
            if not rank_ok:
                status = "rank_deficient"
            elif base.df_resid <= 0 or np.any(leverage >= 1 - 1e-10):
                status = "insufficient_residual_information_for_HC3"
            robust = None
            if status == "ok":
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    robust = base.get_robustcov_results(cov_type="HC3", use_t=True)
                if not np.isfinite(robust.cov_params()).all():
                    status = "nonfinite_HC3_covariance"
                    robust = None
            fits[name] = (base, robust, status)
            for i, term in enumerate(base.params.index):
                estimates.append(dict(
                    outcome=outcome, model=name, term=term,
                    coef=float(base.params.iloc[i]) if rank_ok else None,
                    std_err_hc3=float(robust.bse[i]) if robust is not None else None,
                    p=float(robust.pvalues[i]) if robust is not None else None,
                    n=int(base.nobs), adjusted_r2=base.rsquared_adj, status=status))
        restricted, _, _ = fits["sector"]
        full, robust, status = fits["sector_exposure"]
        test = robust.f_test("exposure_score = 0") if robust is not None else None
        comparisons.append(dict(
            outcome=outcome, primary=outcome == "car_pp", n=int(full.nobs),
            delta_adjusted_r2=full.rsquared_adj - restricted.rsquared_adj,
            hc3_wald_f=float(np.asarray(test.fvalue).item()) if test is not None else None,
            p=float(np.asarray(test.pvalue).item()) if test is not None else None,
            status=status))
    pd.DataFrame(estimates).round(6).to_csv(
        output / f"{prefix}_sector_regressions.csv", index=False, lineterminator="\n")
    pd.DataFrame(comparisons).round(6).to_csv(
        output / f"{prefix}_sector_comparison.csv", index=False, lineterminator="\n")
