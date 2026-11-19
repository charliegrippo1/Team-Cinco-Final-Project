"""Check data/universe/manifest.csv before Carter's pipeline uses it.

Every check is a plain assert, so the script stops at the first broken fact and
says which firm broke it. Checks:
  1. exact column list from docs/CARTER_PIPELINE.md (manifest.template.csv)
  2. unique tickers; 10-digit CIKs; one row per company (unique CIK)
  3. every firm is in our April 2, 2025 universe; membership_date = 2025-04-02
  4. tenk_filing_date is before 2025-04-02
  5. it is the LAST eligible 10-K: re-read the firm's EDGAR filing history and
     confirm no other 10-K was filed after it and before the cutoff, and that the
     accession number really is a 10-K filed on that date
  6. the manifest ticker is printed on that 10-K's cover page, or the firm is one of the
     4 hand fixes in data/universe/ticker_fixes.csv (each with its reason)
  7. text_path exists, is not empty, is plain text (no HTML), and is under the
     pipeline's 350,000-character limit
  8. sector is one of the 11 GICS sectors; market cap is positive; sources filled in

Run from the repository root:
    python scripts/validate_manifest.py                      # v0 manifest: every check must pass
    python scripts/validate_manifest.py --full               # data/universe/manifest_full.csv
With --full, text over the 350,000-character limit is listed (and counted) instead of
stopping the check: those firms stay in the manifest and the scorer reports them in
failures.csv, until the team decides how to handle them (specs_tried.md).
Uses the cached EDGAR filing histories in data/raw/universe/submissions/ (made by
fetch_10k_text.py), so it runs offline. Older history pages are downloaded only if
a filing is not in the cached "recent" list (needs SEC_USER_AGENT then).
"""
import argparse
import csv
import json
import re
from pathlib import Path

from build_universe import OUT as UNIVERSE, ROOT, sec_get

MANIFEST = ROOT / "data/universe/manifest.csv"
MANIFEST_FULL = ROOT / "data/universe/manifest_full.csv"
TEMPLATE = ROOT / "data/universe/manifest.template.csv"
FILINGS = ROOT / "data/universe/tenk_filings.csv"
TICKER_FIXES = ROOT / "data/universe/ticker_fixes.csv"
SUBS = ROOT / "data/raw/universe/submissions"
CUTOFF = "2025-04-02"
SECTORS = {"Communication Services", "Consumer Discretionary", "Consumer Staples", "Energy",
           "Financials", "Health Care", "Industrials", "Information Technology", "Materials",
           "Real Estate", "Utilities"}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def filing_history(cik):
    """All filings for a CIK as (form, filingDate, accession), newest first."""
    sub = json.loads((SUBS / f"CIK{cik}.json").read_text())
    pages = [sub["filings"]["recent"]]
    rows = lambda: [(f, d, a) for p in pages for f, d, a in zip(p["form"], p["filingDate"], p["accessionNumber"])]
    return sub, pages, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--full", "--allow-oversize", dest="full", action="store_true",
                        help="check manifest_full.csv; report long filings for batch exclusion instead of stopping")
    full = parser.parse_args().full
    manifest = MANIFEST_FULL if full else MANIFEST
    too_long = []
    template_cols = TEMPLATE.read_text(encoding="utf-8").strip().split(",")
    with manifest.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == template_cols, f"columns differ from template: {reader.fieldnames}"
        rows = list(reader)
    assert rows, "manifest is empty"

    universe = {r["cik"] for r in read_csv(UNIVERSE)}
    # Same cleanup as build_manifest.pick_ticker: drop quotes and an exchange note like "(NYSE)".
    covers = {r["cik"]: [re.sub(r"\s*\(\w+\)$", "", c).strip(' "\u201c\u201d') for c in r["cover_tickers"].split("|")]
              for r in read_csv(FILINGS) if r["status"] == "ok"}
    fixes = {r["cik"]: r for r in read_csv(TICKER_FIXES)}
    assert all(r["why"].strip() for r in fixes.values()), "every ticker fix needs a reason"

    tickers = [r["ticker"] for r in rows]
    ciks = [r["cik"] for r in rows]
    assert len(tickers) == len(set(tickers)), "duplicate tickers"
    assert len(ciks) == len(set(ciks)), "duplicate CIKs (one row per company)"

    for r in rows:
        t, cik = r["ticker"], r["cik"]
        # 2-3: identifiers and membership
        assert re.fullmatch(r"[A-Z0-9.\-]+", t), f"{t}: bad ticker format"
        assert re.fullmatch(r"\d{10}", cik), f"{t}: CIK must be 10 digits"
        assert cik in universe, f"{t}: not in the April 2, 2025 universe"
        assert r["membership_date"] == CUTOFF, f"{t}: membership_date must be {CUTOFF}"
        assert r["membership_source"].strip(), f"{t}: membership_source missing"

        # 4-5: the 10-K is before the cutoff, and it is the last one before the cutoff
        assert r["tenk_filing_date"] < CUTOFF, f"{t}: 10-K filed on/after the event"
        sub, pages, history = filing_history(cik)
        if r["tenk_accession"] not in {a for _, _, a in history()}:
            # Older pages, only if needed: every page whose dates overlap
            # [10-K filing date, cutoff), so a later 10-K in that gap cannot hide.
            for extra in sub["filings"].get("files", []):
                if extra["filingTo"] >= r["tenk_filing_date"] and extra["filingFrom"] < CUTOFF:
                    pages.append(json.loads(sec_get(f"https://data.sec.gov/submissions/{extra['name']}",
                                                    SUBS / extra["name"]).read_text()))
        match = [(f, d) for f, d, a in history() if a == r["tenk_accession"]]
        assert match, f"{t}: accession {r['tenk_accession']} not in EDGAR history"
        assert match[0][0] in ("10-K", "10-KT"), f"{t}: accession is a {match[0][0]}, not a 10-K"
        assert match[0][1] == r["tenk_filing_date"], f"{t}: filing date differs from EDGAR"
        later = [(f, d) for f, d, _ in history()
                 if f in ("10-K", "10-KT") and r["tenk_filing_date"] < d < CUTOFF]
        assert not later, f"{t}: a later pre-event 10-K exists {later}"
        assert r["tenk_accession"].replace("-", "") in r["filing_url"], f"{t}: filing_url/accession mismatch"

        # 6: ticker as printed on that 10-K's cover
        if cik in fixes:
            assert t == fixes[cik]["ticker"], f"{t}: differs from ticker_fixes.csv"
        else:
            assert t in covers.get(cik, []), f"{t}: not among cover tickers {covers.get(cik)}"

        # 7: the text file Carter's pipeline will score
        path = Path(r["text_path"]) if Path(r["text_path"]).is_absolute() else ROOT / r["text_path"]
        assert path.is_file(), f"{t}: text file missing {path}"
        text = path.read_text(encoding="utf-8-sig")
        assert text.strip(), f"{t}: text file is empty"
        if len(text) > 350_000:
            assert full, f"{t}: text over 350,000 characters ({len(text)})"
            print(f"EXCLUDED FROM SCORING: {t}, {len(text)} characters (limit 350000)")
            too_long.append(t)
        assert not re.search(r"<(?:html|body|div|table|span)\b", text, re.I), f"{t}: HTML left in text"

        # 8: controls and their sources
        assert r["gics_sector"] in SECTORS, f"{t}: unknown sector {r['gics_sector']!r}"
        assert float(r["mktcap_usd_bn"]) > 0, f"{t}: market cap must be positive"
        assert r["cap_source"].strip(), f"{t}: cap_source missing"

    print(f"OK: {len(rows)} rows in {manifest.relative_to(ROOT)} passed all checks")
    if too_long:
        print(f"{len(too_long)} firms are over the scorer's 350,000-character limit; they stay in the "
              f"manifest and the batch records them as excluded_oversize (specs_tried.md #23)")


if __name__ == "__main__":
    main()
