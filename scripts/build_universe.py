"""Build the S&P 500 universe as of the April 2, 2025 event (Charlie's handoff, step 1).

Source of record: SPY's SEC Form N-PORT holdings report for the period ending
2025-03-31 (SPY fully replicates the S&P 500, so its holdings = index members).
That is a point-in-time snapshot, so firms later acquired or delisted are still in
it (no survivorship bias from using today's list).

For each holding we add:
  - cik:    matched by company name to SEC's ticker file, or from the reviewed
            data/universe/cik_overrides.csv, then double-checked against EDGAR's
            current and former company names.
  - ticker: from OpenFIGI (free CUSIP -> ticker lookup). This is TODAY's ticker,
            so it is only provisional. Step 4 confirms the April 2025 ticker from
            each firm's 10-K cover page. Blank when OpenFIGI has no record.

Run from the repository root (needs the SEC_USER_AGENT environment variable,
e.g. "Team Cinco FIN331 class project you@lehigh.edu"; SEC requires a contact):
    python scripts/build_universe.py
Raw downloads are cached in data/raw/universe/ (git-ignored) so reruns make no
new requests. Delete that folder to download a fresh copy.
"""
import csv
import hashlib
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/universe"
OUT = ROOT / "data/universe/universe_2025-04-02.csv"
SOURCES = ROOT / "data/universe/universe_sources.json"
OVERRIDES = ROOT / "data/universe/cik_overrides.csv"
DROPPED = ROOT / "data/universe/share_classes_dropped.csv"

SPY_CIK = "884394"
NPORT_ACCESSION = "0001752724-25-125179"   # SPY NPORT-P, report period 2025-03-31, filed 2025-05-28
NPORT_URL = f"https://www.sec.gov/Archives/edgar/data/{SPY_CIK}/{NPORT_ACCESSION.replace('-', '')}/primary_doc.xml"
TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
FIGI_URL = "https://api.openfigi.com/v3/mapping"
NS = "{http://www.sec.gov/edgar/nport}"


def sec_get(url, path):
    """Download url to path once (cached). SEC asks for <= 10 requests/second.
    Retries temporary errors (rate limit, server busy, network) with growing waits.
    Writes to a temporary file first, so a stopped run never leaves a half-saved file."""
    if path.exists():
        return path
    agent = os.environ.get("SEC_USER_AGENT")
    if not agent:
        raise SystemExit("Set SEC_USER_AGENT to 'Name/project contact-email' first")
    for attempt in range(5):
        try:
            with urlopen(Request(url, headers={"User-Agent": agent}), timeout=60) as r:
                data = r.read()
            break
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 4:
                raise RuntimeError(f"HTTP {exc.code} for {url}") from None
        except (URLError, TimeoutError):
            if attempt == 4:
                raise RuntimeError(f"network failed 5 times for {url}") from None
        time.sleep(2 ** attempt)   # 1, 2, 4, 8 seconds
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)
    time.sleep(0.15)  # stay well under SEC's 10 requests/second
    return path


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm(name):
    """Simplify a company name so 'Clorox Co/The' and 'CLOROX CO /DE/' compare equal."""
    s = name.upper().replace("/THE", "")
    s = re.sub(r"/[A-Z]{2,3}/?", " ", s)                 # state suffixes like /DE/
    s = re.sub(r"[&.,/'\-!]", " ", s)
    s = re.sub(r"\b(INC|CORP|CORPORATION|CO|COS|COMPANY|COMPANIES|LTD|PLC|LP|LLC|NV|N V|SA|AG|"
               r"HOLDINGS?|GROUP|THE|INCORPORATED|LIMITED|AND|DE|NEW)\b", " ", s)
    return "".join(s.split())


def read_holdings(xml_path):
    """One dict per holding in the N-PORT report."""
    root = ET.parse(xml_path).getroot()
    period = root.find(f".//{NS}repPdDate").text
    assert period == "2025-03-31", period
    rows = []
    for h in root.iter(f"{NS}invstOrSec"):
        ids = h.find(f"{NS}identifiers")
        rows.append({
            "nport_name": h.find(f"{NS}name").text,
            "cusip": h.find(f"{NS}cusip").text,
            "isin": ids.find(f"{NS}isin").get("value"),
            "lei": h.find(f"{NS}lei").text,
            "asset_category": h.find(f"{NS}assetCat").text,
            "spy_shares": h.find(f"{NS}balance").text,
            "spy_value_usd": h.find(f"{NS}valUSD").text,
            "spy_weight_pct": h.find(f"{NS}pctVal").text,
        })
    return rows


def match_ciks(holdings, tickers_path):
    """Name-match each holding to one CIK; reviewed overrides win."""
    table = json.loads(tickers_path.read_text())
    sec = [dict(zip(table["fields"], r)) for r in table["data"]]
    by_name = {}
    for r in sec:
        if r["exchange"] in ("NYSE", "Nasdaq", "CBOE"):   # skip OTC look-alikes
            by_name.setdefault(norm(r["name"]), set()).add(r["cik"])
    with OVERRIDES.open(encoding="utf-8") as f:
        overrides = {r["cusip"]: r for r in csv.DictReader(f)}
    sec_tickers = {}
    for r in sec:
        sec_tickers.setdefault(r["cik"], []).append(r["ticker"])
    for h in holdings:
        if h["cusip"] in overrides:
            h["cik"], h["cik_method"] = overrides[h["cusip"]]["cik"], "manual override"
        else:
            ciks = by_name.get(norm(h["nport_name"]), set())
            if len(ciks) != 1:
                raise SystemExit(f"No unique CIK for {h['nport_name']} ({h['cusip']}); add it to {OVERRIDES.name}")
            h["cik"], h["cik_method"] = f"{next(iter(ciks)):010d}", "SEC name match"
        h["sec_current_tickers"] = "|".join(sec_tickers.get(int(h["cik"]), []))


def verify_names(holdings):
    """Check each CIK's EDGAR name (current or former) resembles the N-PORT name."""
    for h in holdings:
        path = sec_get(f"https://data.sec.gov/submissions/CIK{h['cik']}.json",
                       RAW / "submissions" / f"CIK{h['cik']}.json")
        sub = json.loads(path.read_text())
        names = [sub["name"]] + [f["name"] for f in sub.get("formerNames", [])]
        target = norm(h["nport_name"])
        # EDGAR often lists names last-first ("HORTON D R INC"), so also compare sorted letters.
        ok = any(target == norm(n) or target in norm(n) or norm(n) in target
                 or sorted(target) == sorted(norm(n)) for n in names)
        h["edgar_name"] = sub["name"]
        h["name_check"] = "ok" if ok else "REVIEW"
        # A firm in the index on 2025-04-02 must have filed with the SEC before then.
        # This catches successor companies that took over an old ticker later
        # (e.g. ExxonMobil Holdings Corp, first filing in 2026).
        dates = [sub["filings"]["recent"]["filingDate"][-1]] + [p["filingFrom"] for p in sub["filings"].get("files", [])]
        h["first_edgar_filing"] = min(dates)
    late = [(h["nport_name"], h["cik"]) for h in holdings if h["first_edgar_filing"] >= "2025-04-02"]
    if late:
        raise SystemExit(f"CIKs with no SEC filings before 2025-04-02 (wrong entity?): {late}; fix in {OVERRIDES.name}")


def figi_tickers(holdings):
    """CUSIP -> today's US ticker from OpenFIGI (cached). ISIN when the CUSIP is blank."""
    path = RAW / "openfigi_responses.json"
    if path.exists():
        answers = json.loads(path.read_text())
    else:
        jobs = [{"idType": "ID_CUSIP", "idValue": h["cusip"], "exchCode": "US"}
                if h["cusip"] != "000000000" else
                {"idType": "ID_ISIN", "idValue": h["isin"], "exchCode": "US"} for h in holdings]
        answers = []
        for k in range(0, len(jobs), 10):              # free tier: 10 jobs/request, 25 requests/minute
            body = json.dumps(jobs[k:k + 10]).encode()
            req = Request(FIGI_URL, data=body, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=60) as r:
                answers += json.load(r)
            time.sleep(2.6)
        path.write_text(json.dumps({"jobs": jobs, "answers": answers}, indent=1))
        answers = {"answers": answers}
    answers = answers["answers"]
    for h, a in zip(holdings, answers):
        data = [d for d in a.get("data", []) if d.get("securityType") == "Common Stock"] or a.get("data", [])
        tickers = sorted({d["ticker"].replace("/", ".") for d in data})
        h["ticker_figi_today"] = tickers[0] if len(tickers) == 1 else "|".join(tickers)
        h["figi_name"] = data[0]["name"] if data else ""


def main():
    retrieved = datetime.now(timezone.utc).isoformat(timespec="seconds")
    nport = sec_get(NPORT_URL, RAW / "spy_nport_2025-03-31.xml")
    tickers = sec_get(TICKERS_URL, RAW / "sec_company_tickers_exchange.json")

    holdings = read_holdings(nport)
    match_ciks(holdings, tickers)
    verify_names(holdings)
    figi_tickers(holdings)

    for h in holdings:
        h["membership_date"] = "2025-04-02"
        h["membership_source"] = f"SPY N-PORT period 2025-03-31, SEC accession {NPORT_ACCESSION}"

    # Key facts the rest of the pipeline relies on.
    assert len(holdings) == len({h["cusip"] + h["isin"] for h in holdings}), "duplicate securities"
    assert all(re.fullmatch(r"\d{10}", h["cik"]) for h in holdings), "CIK must be 10 digits"
    assert all(h["asset_category"] == "EC" for h in holdings), "non-equity holding in SPY"

    # Share-class rule (team decision, see specs_tried.md): one row per company.
    # The exposure score comes from the company's single 10-K, so two share classes
    # would count the same firm twice. Keep the class with the larger SPY weight.
    firms, dropped = {}, []
    for h in sorted(holdings, key=lambda h: -float(h["spy_weight_pct"])):
        if h["cik"] in firms:
            dropped.append(h)
        else:
            firms[h["cik"]] = h
    firms = sorted(firms.values(), key=lambda h: -float(h["spy_weight_pct"]))
    assert len({h["cik"] for h in firms}) == len(firms), "one row per company"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    for path, rows in ((OUT, firms), (DROPPED, dropped)):
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(holdings[0]))
            w.writeheader()
            w.writerows(rows)

    SOURCES.write_text(json.dumps({
        "built_utc": retrieved,
        "nport": {"url": NPORT_URL, "accession": NPORT_ACCESSION, "report_period": "2025-03-31",
                  "filed": "2025-05-28", "sha256": sha256(nport)},
        "sec_ticker_file": {"url": TICKERS_URL, "sha256": sha256(tickers),
                            "note": "today's file; used only to look up CIKs (CIKs never change)"},
        "openfigi": {"url": FIGI_URL, "note": "today's tickers; provisional until 10-K cover check"},
        "securities_in_nport": len(holdings),
        "companies_kept": len(firms),
        "share_classes_dropped": [h["ticker_figi_today"] for h in dropped],
    }, indent=2))
    print(f"{len(holdings)} securities -> {len(firms)} companies in {OUT.relative_to(ROOT)}; "
          f"{len(dropped)} extra share classes in {DROPPED.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
