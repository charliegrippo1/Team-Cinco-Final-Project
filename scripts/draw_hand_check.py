"""Draw the firms for the v1 blind hand-check BEFORE the full scoring run.

Every firm in data/universe/manifest_full.csv that the scorer will attempt (text under
the 350,000-character limit, see specs_tried.md #23) and that was not already
hand-checked in v0 is put in a random order with a fixed seed. The order is saved to
audits/hand_check_v1_draw.csv.

Rule (fixed now, before any v1 results exist): the hand-check covers the first 20
firms in this order that end up complete in outputs/batch_v1/tariff_firms.csv
(score and prices both OK). A firm that fails is skipped, never replaced by hand.
The person scoring must not look at the AI score or evidence first.

Run from the repository root:  python scripts/draw_hand_check.py
"""
import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/universe/manifest_full.csv"
V0_SAMPLE = ROOT / "data/universe/v0_sample.csv"
OUT = ROOT / "audits/hand_check_v1_draw.csv"
SEED, LIMIT, N_CHECK = 331, 350_000, 20


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    v0 = {r["cik"] for r in read_csv(V0_SAMPLE)}
    firms = []
    for r in sorted(read_csv(MANIFEST), key=lambda r: r["cik"]):   # fixed starting order
        if r["cik"] in v0:
            continue
        if len((ROOT / r["text_path"]).read_text(encoding="utf-8-sig")) > LIMIT:
            continue
        firms.append(r)
    assert len(firms) == 444, f"expected 444 eligible firms (454 scorable - 10 v0), found {len(firms)}"
    random.Random(SEED).shuffle(firms)
    rule = (f"random.Random({SEED}).shuffle of {len(firms)} firms (scorable, not in v0), sorted by CIK first; "
            f"hand-check the first {N_CHECK} in this order that are complete after the v1 run")
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["order", "ticker", "company", "cik", "gics_sector", "how_chosen"])
        w.writeheader()
        for i, r in enumerate(firms, 1):
            w.writerow({"order": i, "ticker": r["ticker"], "company": r["company"], "cik": r["cik"],
                        "gics_sector": r["gics_sector"], "how_chosen": rule})
    print(f"{len(firms)} firms ordered -> {OUT.relative_to(ROOT)}; first {N_CHECK}: "
          + ", ".join(r["ticker"] for r in firms[:N_CHECK]))


if __name__ == "__main__":
    main()
