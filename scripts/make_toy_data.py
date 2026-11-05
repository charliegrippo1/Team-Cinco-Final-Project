"""Make a FAKE dataset shaped exactly like docs/DATA_CONTRACT.md.

Why: the dashboard can be built and tested before the real 10-K scores and
returns exist. Every value here is randomly generated. Tickers are fake
(FK001...) so no one mistakes these numbers for real firms.

The fake data deliberately builds in a negative exposure -> CAR relationship
so the charts have something to show. That relationship is INVENTED and says
nothing about what the real data will show.

Run:  python scripts/make_toy_data.py
Out:  data/toy/tariff_firms_FAKE.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "toy" / "tariff_firms_FAKE.csv"
SEED = 331
N_FIRMS = 500

# Sector: (approx number of S&P 500 firms, mean fake exposure on the 0-4 scale)
SECTORS = {
    "Information Technology": (68, 2.6),
    "Industrials": (78, 2.2),
    "Financials": (72, 0.4),
    "Health Care": (61, 1.5),
    "Consumer Discretionary": (50, 2.9),
    "Consumer Staples": (38, 2.0),
    "Real Estate": (31, 0.3),
    "Utilities": (31, 0.6),
    "Materials": (28, 2.1),
    "Communication Services": (22, 0.9),
    "Energy": (21, 1.2),
}

EVIDENCE = {
    0: "FAKE: Substantially all of our operations and customers are in the United States.",
    1: "FAKE: Changes in trade policy could adversely affect general economic conditions.",
    2: "FAKE: Certain components are sourced from suppliers located in Asia.",
    3: "FAKE: A majority of our products are manufactured by third-party suppliers outside the U.S.",
    4: "FAKE: Substantially all of our products are manufactured in China.",
}


def main() -> None:
    rng = np.random.default_rng(SEED)
    sectors = np.repeat(list(SECTORS), [n for n, _ in SECTORS.values()])[:N_FIRMS]
    mean_exp = np.array([SECTORS[s][1] for s in sectors])
    exposure = np.clip(np.round(mean_exp + rng.normal(0, 0.9, N_FIRMS)), 0, 4).astype(int)

    # Fake market moves (roughly the size of a very bad two days)
    mkt = {"apr3": -4.8, "apr4": -6.0, "apr9": 10.5}

    sector_shock = {s: rng.normal(0, 1.0) for s in SECTORS}
    size = np.exp(rng.normal(3.6, 1.0, N_FIRMS))  # $bn, lognormal like real caps
    car = (
        -0.9 * exposure                     # invented exposure effect
        + np.array([sector_shock[s] for s in sectors])
        + rng.normal(0, 2.5, N_FIRMS)       # idiosyncratic noise
    )
    split = rng.uniform(0.3, 0.7, N_FIRMS)
    ar3, ar4 = car * split, car * (1 - split)

    df = pd.DataFrame({
        "ticker": [f"FK{i:03d}" for i in range(1, N_FIRMS + 1)],
        "company": [f"Fake Company {i}" for i in range(1, N_FIRMS + 1)],
        "cik": [f"{9_000_000 + i:010d}" for i in range(1, N_FIRMS + 1)],
        "gics_sector": sectors,
        "mktcap_usd_bn": size.round(2),
        "tenk_filing_date": (
            pd.Timestamp("2025-01-25") + pd.to_timedelta(rng.integers(0, 60, N_FIRMS), unit="D")
        ).strftime("%Y-%m-%d"),
        "tenk_accession": [f"0000000000-25-{i:06d}" for i in range(1, N_FIRMS + 1)],
        "exposure_score": exposure,
        "exposure_evidence": [EVIDENCE[e] for e in exposure],
        "hand_score": pd.array([pd.NA] * N_FIRMS, dtype="Int64"),
        "ret_apr3_pct": (mkt["apr3"] + ar3).round(4),
        "ret_apr4_pct": (mkt["apr4"] + ar4).round(4),
        "mkt_apr3_pct": mkt["apr3"],
        "mkt_apr4_pct": mkt["apr4"],
    })
    df["car_pp"] = (df.ret_apr3_pct - df.mkt_apr3_pct) + (df.ret_apr4_pct - df.mkt_apr4_pct)
    df["car_mm_pp"] = (df.car_pp + rng.normal(0, 0.6, N_FIRMS)).round(4)
    # Fake partial bounce-back on the pause day
    df["car_pause_pp"] = (0.35 * exposure + rng.normal(0, 2.0, N_FIRMS)).round(4)

    # Hand-check 50 random firms; agree with the LLM about 80% of the time
    checked = rng.choice(N_FIRMS, 50, replace=False)
    hand = exposure[checked] + rng.choice([0, 0, 0, 0, 1, -1], 50)
    df.loc[checked, "hand_score"] = np.clip(hand, 0, 4)

    # Same checks the real pipeline must pass (docs/DATA_CONTRACT.md)
    assert df.ticker.is_unique
    assert (pd.to_datetime(df.tenk_filing_date) < "2025-04-02").all()
    assert df.exposure_score.between(0, 4).all()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"Wrote {len(df)} FAKE rows to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
