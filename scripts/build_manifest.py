"""Write data/universe/manifest.csv, the file Carter's pipeline reads.

One row for every firm whose 10-K text was extracted successfully
(status "ok" in data/universe/tenk_filings.csv). Columns follow
docs/CARTER_PIPELINE.md exactly. Where each field comes from:

  ticker            the firm's ticker printed on its 10-K cover (as of the filing,
                    not today). If the cover lists several (share classes, bonds),
                    we take the one that matches the security SPY held.
  gics_sector       which Select Sector SPDR fund held the stock on 2025-03-31
                    (SEC Form N-PORT). These 11 funds split the S&P 500 by GICS sector.
  mktcap_usd_bn     v0 rule: shares outstanding on the 10-K cover (all share classes
                    added up) x the 2025-03-31 price from SPY's N-PORT
                    (value held / shares held). See specs_tried.md.
  membership_*      from data/universe/universe_2025-04-02.csv (SPY N-PORT 2025-03-31)
  price_symbol, mask_aliases   left blank for now (optional; see CARTER_PIPELINE.md)

Firms with more than one share class are listed in data/universe/manifest_review.csv
for a manual check of the market cap (e.g. Berkshire's A shares = 1,500 B shares).

Run from the repository root:
    python scripts/build_manifest.py --v0    # the 10-firm Checkpoint 2 sample only
    python scripts/build_manifest.py         # every firm with extracted text (full run)

The v0 sample is the 5 Checkpoint 1 pilot firms plus 5 drawn at random (fixed seed,
so anyone gets the same 5) from firms that are easy to run end to end; the draw and
its rules are written to data/universe/v0_sample.csv. We never pick firms by hand.
"""
import argparse
import csv
import json
import random
import re
import xml.etree.ElementTree as ET
from html import unescape

from build_universe import OUT as UNIVERSE, RAW, ROOT, sec_get

FILINGS = ROOT / "data/universe/tenk_filings.csv"
TEMPLATE = ROOT / "data/universe/manifest.template.csv"
MANIFEST = ROOT / "data/universe/manifest.csv"
REVIEW = ROOT / "data/universe/manifest_review.csv"
SAMPLE = ROOT / "data/universe/v0_sample.csv"
OVERRIDES = ROOT / "data/universe/cik_overrides.csv"
# Checkpoint 1 pilot (Apple, Verizon, Nike) plus the two energy firms added for Step 4 testing.
PILOT = ["0000320193", "0000732712", "0000320187", "0000087347", "0000004447"]
SEED, N_RANDOM = 331, 5
NS = "{http://www.sec.gov/edgar/nport}"

SECTOR_TRUST_CIK = "0001064641"   # Select Sector SPDR Trust (XLK, XLF, ... 11 funds)
FUND_TO_GICS = {                   # fund name -> official GICS sector name
    "Communication Services": "Communication Services", "Consumer Discretionary": "Consumer Discretionary",
    "Consumer Staples": "Consumer Staples", "Energy": "Energy", "Financial": "Financials",
    "Health Care": "Health Care", "Industrial": "Industrials", "Technology": "Information Technology",
    "Materials": "Materials", "Real Estate": "Real Estate", "Utilities": "Utilities",
}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sector_map():
    """CUSIP (or ISIN when CUSIP is blank) -> GICS sector, from the 11 funds' 2025-03-31 N-PORTs."""
    sub = json.loads(sec_get(f"https://data.sec.gov/submissions/CIK{SECTOR_TRUST_CIK}.json",
                             RAW / "sector" / "submissions.json").read_text())
    rec = sub["filings"]["recent"]
    accs = [a for f, a, d in zip(rec["form"], rec["accessionNumber"], rec["reportDate"])
            if f == "NPORT-P" and d == "2025-03-31"]
    assert len(accs) == 11, f"expected 11 sector funds, found {len(accs)}"
    out, sources = {}, []
    for acc in accs:
        url = f"https://www.sec.gov/Archives/edgar/data/{int(SECTOR_TRUST_CIK)}/{acc.replace('-', '')}/primary_doc.xml"
        root = ET.parse(sec_get(url, RAW / "sector" / f"{acc}.xml")).getroot()
        fund = root.find(f".//{NS}seriesName").text            # e.g. "The Energy Select Sector SPDR Fund"
        sector = FUND_TO_GICS[re.sub(r"^The | Select Sector SPDR Fund$", "", fund)]
        sources.append(f"{sector}: {acc}")
        for h in root.iter(f"{NS}invstOrSec"):
            if h.find(f"{NS}assetCat").text != "EC":
                continue
            key = h.find(f"{NS}cusip").text
            if key == "000000000":
                key = h.find(f"{NS}identifiers").find(f"{NS}isin").get("value")
            assert out.get(key, sector) == sector, f"{key} is in two sector funds"
            out[key] = sector
    return out


def cover_shares(html_path):
    """Shares outstanding per class from the 10-K cover (inline XBRL), one number per class."""
    html = html_path.read_text(encoding="utf-8", errors="replace")
    per_class = {}
    for m in re.finditer(r"<ix:nonFraction([^>]*name=\"dei:EntityCommonStockSharesOutstanding\"[^>]*)>(.*?)</ix:nonFraction>",
                         html, re.S | re.I):
        attrs, raw = m.group(1), unescape(re.sub(r"<[^>]+>", "", m.group(2)))
        context = re.search(r'contextRef="([^"]+)"', attrs).group(1)
        scale = int((re.search(r'scale="(-?\d+)"', attrs) or [0, 0])[1])
        per_class[context] = float(raw.replace(",", "")) * 10 ** scale
    if not per_class:
        raise ValueError("no shares-outstanding figure on the 10-K cover")
    return list(per_class.values())


def pick_ticker(cover, figi_today):
    """The cover ticker for the security SPY held (plain stock symbols only)."""
    stock = [t for t in cover.split("|") if t and " " not in t]       # drops bonds like "VZ 26"
    same = [t for t in stock if t.replace("-", ".") == figi_today]
    if same:
        return same[0]
    if len(stock) == 1:
        return stock[0]
    raise ValueError(f"cannot tell which cover ticker is the index security: {cover}")


def draw_v0_sample(filings, universe):
    """PILOT + N_RANDOM firms drawn with a fixed seed. A firm can be drawn only if it
    runs cleanly end to end in v0: text extracted and under the pipeline's 350,000-
    character limit, one plain cover ticker, one share class, and not a firm our
    override notes say was acquired after the event (Yahoo has no prices for those).
    The last rule uses post-event knowledge, so it is for this smoke test only; the full
    run keeps every firm. Writes the sample and the rule to data/universe/v0_sample.csv."""
    acquired = {r["cik"] for r in read_csv(OVERRIDES)
                if re.search(r"acquired|taken private|merged", r["note"], re.I)}
    eligible = []
    for f in sorted(filings, key=lambda f: f["cik"]):
        if f["status"] != "ok" or f["cik"] in PILOT or f["cik"] in acquired:
            continue
        if int(f["total_chars"]) > 350_000:
            continue
        try:
            pick_ticker(f["cover_tickers"], universe[f["cik"]]["ticker_figi_today"])
            if len(cover_shares(ROOT / "data/raw/tenk" / f["cik"] / f"{f['tenk_accession']}.htm")) != 1:
                continue
        except ValueError:
            continue
        eligible.append(f["cik"])
    drawn = random.Random(SEED).sample(eligible, N_RANDOM)
    rule = (f"random.Random({SEED}).sample of {len(eligible)} eligible firms (sorted by CIK): "
            "text ok and <= 350,000 chars, one plain cover ticker, one share class, "
            "not acquired after the event per cik_overrides.csv notes")
    with SAMPLE.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["cik", "company", "how_chosen"])
        w.writeheader()
        for cik in PILOT:
            w.writerow({"cik": cik, "company": universe[cik]["nport_name"], "how_chosen": "Checkpoint 1 pilot"})
        for cik in drawn:
            w.writerow({"cik": cik, "company": universe[cik]["nport_name"], "how_chosen": rule})
    return set(PILOT) | set(drawn)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v0", action="store_true", help="only the 10-firm Checkpoint 2 sample")
    args = parser.parse_args()
    columns = TEMPLATE.read_text(encoding="utf-8").strip().split(",")
    universe = {r["cik"]: r for r in read_csv(UNIVERSE)}
    sectors = sector_map()
    filings = read_csv(FILINGS)
    keep = draw_v0_sample(filings, universe) if args.v0 else None
    rows, review = [], []
    for f in filings:
        if f["status"] != "ok" or (keep is not None and f["cik"] not in keep):
            continue
        u = universe[f["cik"]]
        key = u["cusip"] if u["cusip"] != "000000000" else u["isin"]
        ticker = pick_ticker(f["cover_tickers"], u["ticker_figi_today"]).replace("-", ".")
        price = float(u["spy_value_usd"]) / float(u["spy_shares"])        # 2025-03-31 price
        classes = cover_shares(ROOT / "data/raw/tenk" / f["cik"] / f"{f['tenk_accession']}.htm")
        cap_bn = sum(classes) * price / 1e9
        rows.append({
            "ticker": ticker,
            "company": u["nport_name"],
            "cik": f["cik"],
            "gics_sector": sectors[key],
            "mktcap_usd_bn": round(cap_bn, 2),
            "tenk_filing_date": f["tenk_filing_date"],
            "tenk_accession": f["tenk_accession"],
            "filing_url": f["filing_url"],
            "text_path": f["text_path"],
            "membership_date": u["membership_date"],
            "membership_source": u["membership_source"],
            "cap_source": (f"v0: 10-K cover shares outstanding (accession {f['tenk_accession']}, "
                           f"{len(classes)} class(es) summed) x 2025-03-31 price ${price:.2f} "
                           f"from SPY N-PORT accession 0001752724-25-125179"),
            "price_symbol": "",
            "mask_aliases": "",
        })
        if len(classes) > 1:
            review.append({"ticker": ticker, "company": u["nport_name"], "share_classes": len(classes),
                           "shares_by_class": "|".join(f"{s:.0f}" for s in classes),
                           "price_used": round(price, 2), "mktcap_usd_bn": round(cap_bn, 2),
                           "why": "several share classes added at one price; check conversion ratios"})

    assert rows, "no firms with extracted 10-K text yet"
    assert len({r["ticker"] for r in rows}) == len(rows), "duplicate tickers"
    with MANIFEST.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)
    with REVIEW.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["ticker", "company", "share_classes", "shares_by_class",
                                           "price_used", "mktcap_usd_bn", "why"])
        w.writeheader()
        w.writerows(review)
    print(f"{len(rows)} firms -> {MANIFEST.relative_to(ROOT)}; {len(review)} need a market-cap check")


if __name__ == "__main__":
    main()
