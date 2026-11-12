"""Find each firm's last 10-K filed before April 2, 2025 and extract Items 1, 1A and 7.

For every company in data/universe/universe_2025-04-02.csv (or only the CIKs given
with --cik), this script:
  1. Reads the firm's EDGAR filing history and picks the most recent original 10-K
     (not an amendment) with a filing date strictly before 2025-04-02. Using the
     FILING date, not the fiscal-year end, is what keeps this free of look-ahead.
  2. Downloads that 10-K's main HTML document (cached in data/raw/tenk/).
  3. Converts the HTML to plain text and cuts out Item 1 (Business), Item 1A (Risk
     Factors) and Item 7 (MD&A) verbatim. No summarizing, no rewording.
  4. Reads the ticker(s) printed on the 10-K cover (inline XBRL dei:TradingSymbol),
     which is the firm's ticker as of the filing, not today's.

Outputs:
  data/universe/text/<CIK>_<accession>.txt   Items 1, 1A, 7 (git-ignored; rebuildable)
  data/universe/tenk_filings.csv             one row per firm: filing facts, word counts, status

Run from the repository root (SEC requires a contact in the User-Agent):
    SEC_USER_AGENT="Team Cinco FIN331 class project you@lehigh.edu" python scripts/fetch_10k_text.py --cik 0000320193
Whole universe in batches of 50:  python scripts/fetch_10k_text.py --limit 50   (repeat)

Resuming: progress is saved after every firm, and downloads are cached in data/raw/,
so the script can be stopped (Ctrl-C) and rerun at any time. Finished firms are
skipped; failed firms are skipped too unless --retry-failed is given. --rebuild redoes
every firm from the cached downloads (e.g. after changing the extraction rules). Every failure
keeps its reason in the "error" column of tenk_filings.csv; nothing is filled in by hand.
"""
import argparse
import csv
import json
import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from build_universe import OUT as UNIVERSE, ROOT, sec_get

CUTOFF = "2025-04-02"
RAW = ROOT / "data/raw/tenk"
SUBS = ROOT / "data/raw/universe/submissions"
TEXT = ROOT / "data/universe/text"
FILINGS = ROOT / "data/universe/tenk_filings.csv"
MARKERS = ROOT / "data/universe/section_markers.csv"   # reviewed manual boundaries
ANNUAL_FORMS = ("10-K", "10-KT")   # original annual reports; amendments (10-K/A) excluded

# Heading patterns: "Item N" at the start of a line followed by the item's standard
# title. A section runs from its heading to the next item's heading. Requiring the
# title matters: cross-references like "Item 8, Note 2" must not end a section.
# "Items 1 and 2. Business and Properties" (common for energy firms) counts as Item 1.
SEP = r"[\s.:\-–—|]*"
# Some filers put the part on the SAME line: "Part II - Item 7. ...", "Part I, Item 1".
# No line breaks allowed here, so a "PART I" line above the heading is not pulled in.
PART = r"(?:part[ \t]+i{1,3}[ \t.:,|\-–—]*)?"
MAX_WORDS = 100_000  # longest real section seen: KKR's risk factors, ~71,500 words. A mis-cut
                     # that runs into the financial statements is far longer (Entergy: ~239,000).
START = {
    "1": rf"items?{SEP}1{SEP}(?:(?:and|&){SEP}2{SEP})?(?:our\s+)?business",            # "Item 1. Our Business"
    "1A": rf"item{SEP}1A{SEP}risk\s+factors",
    "7": rf"items?{SEP}7{SEP}(?:(?:and|&){SEP}7A{SEP})?management[’']?s\s+discussion",  # "Items 7 and 7A."
}
# Used only if the titled heading finds nothing, e.g. Bank of America titles
# Item 7 "Bank of America Corporation and Subsidiaries". (?![0-9A-Za-z]) stops
# "Item 7" from matching "Item 7A".
FALLBACK_START = {"7": rf"item{SEP}7(?![0-9A-Za-z])"}
END = {
    "1": [rf"item{SEP}1A{SEP}risk\s+factors", rf"item{SEP}2{SEP}properties"],
    "1A": [rf"item{SEP}1B{SEP}unresolved", rf"item{SEP}1C{SEP}cybersecurity", rf"items?{SEP}2{SEP}properties"],
    "7": [rf"item{SEP}7A{SEP}(?:quantitative|qualitative)", rf"item{SEP}8{SEP}(?:consolidated\s+)?financial\s+statements"],
}


class TextMaker(HTMLParser):
    """HTML -> plain text. Block tags become line breaks; hidden XBRL blocks are skipped."""
    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section"}
    VOID = {"br", "img", "hr", "meta", "link", "input", "col", "area", "base", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.stack, self.hidden_depth = [], [], 0

    def handle_starttag(self, tag, attrs):
        style = (dict(attrs).get("style") or "").replace(" ", "").lower()
        hide = tag in ("ix:header", "script", "style") or "display:none" in style
        if tag not in self.VOID:
            self.stack.append(hide)
            self.hidden_depth += hide
        if tag in self.BLOCK:
            self.parts.append("\n")
        elif tag in ("td", "th"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in self.VOID or not self.stack:
            return
        self.hidden_depth -= self.stack.pop()
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.hidden_depth == 0:
            self.parts.append(data)

    def text(self):
        t = "".join(self.parts).replace("\xa0", " ").replace("​", "")
        t = re.sub(r"[ \t\r\f\v]+", " ", t)
        t = re.sub(r" *\n *", "\n", t)
        return re.sub(r"\n{3,}", "\n\n", t).strip()


def last_10k_before_cutoff(cik):
    """Return (best filing, number of 10-K/A amendments filed in the year before the cutoff)."""
    sub = json.loads(sec_get(f"https://data.sec.gov/submissions/CIK{cik}.json", SUBS / f"CIK{cik}.json").read_text())
    pages = [sub["filings"]["recent"]]

    def candidates():
        out = []
        for p in pages:
            for i, form in enumerate(p["form"]):
                out.append({k: p[k][i] for k in ("form", "filingDate", "reportDate", "accessionNumber", "primaryDocument")})
        return out

    eligible = [f for f in candidates() if f["form"] in ANNUAL_FORMS and f["filingDate"] < CUTOFF]
    # Heavy filers (big banks) have older filings in extra pages, newest page first.
    # Skip pages that lie entirely after the cutoff and stop at the first page with a
    # pre-cutoff 10-K: because pages run newest to oldest, that one is the latest.
    for extra in sub["filings"].get("files", []):
        if eligible:
            break
        if extra["filingFrom"] >= CUTOFF:
            continue
        pages.append(json.loads(sec_get(f"https://data.sec.gov/submissions/{extra['name']}",
                                        SUBS / extra["name"]).read_text()))
        eligible = [f for f in candidates() if f["form"] in ANNUAL_FORMS and f["filingDate"] < CUTOFF]
    if not eligible:
        raise ValueError("no 10-K filed before 2025-04-02")
    best = max(eligible, key=lambda f: f["filingDate"])
    amendments = sum(1 for f in candidates() if f["form"] == "10-K/A" and "2024-04-02" <= f["filingDate"] < CUTOFF)
    return best, amendments


def cut_section(text, item):
    """Longest span from an item heading to the next item heading.
    Taking the LONGEST span skips the short table-of-contents entries.
    If the titled heading finds nothing usable, try the fallback heading (if any).
    If still nothing, the firm fails loudly instead of getting wrong text."""
    for start_pattern in (START[item], FALLBACK_START.get(item)):
        if start_pattern is None:
            continue
        best = ""
        for start in re.finditer(r"^" + PART + start_pattern, text, re.I | re.M):
            ends = [m.start() for pat in END[item]
                    for m in re.finditer(r"^" + PART + pat, text[start.end():], re.I | re.M)]
            if ends:
                span = text[start.start(): start.end() + min(ends)].strip()
                if len(span) > len(best):
                    best = span
        if len(best.split()) > MAX_WORDS:
            raise ValueError(f"Item {item} suspiciously long ({len(best.split())} words); likely a mis-cut")
        if len(best.split()) >= 200:
            return best
    raise ValueError(f"could not find Item {item} (best match {len(best.split())} words)")


def cover_tickers(html):
    """Ticker(s) tagged on the 10-K cover page (inline XBRL)."""
    found = re.findall(r'name="dei:TradingSymbol"[^>]*>(.*?)</ix:nonNumeric>', html, re.S | re.I)
    clean = [unescape(re.sub(r"<[^>]+>", "", t)).strip() for t in found]
    return list(dict.fromkeys(t for t in clean if t))


def html_to_text(path):
    maker = TextMaker()
    maker.feed(path.read_bytes().decode("utf-8", errors="replace"))
    return maker.text()


def exhibit13_text(cik, acc):
    """Text of the filing's Exhibit 13 (annual report to shareholders), where some
    firms put their MD&A or risk factors 'by reference'. Found via the filing index."""
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}"
    index = sec_get(f"{base}/{acc}-index.htm", RAW / cik / f"{acc}-index.htm").read_text(errors="replace")
    docs = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", index, re.S):
        cells = [unescape(re.sub(r"<[^>]+>", " ", c)).split() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) >= 4 and cells[3] and cells[3][0].upper().startswith("EX-13"):
            docs.append(cells[2][0])
    if not docs:
        raise ValueError("marker says Exhibit 13, but the filing has no EX-13 document")
    return "\n\n".join(html_to_text(sec_get(f"{base}/{d}", RAW / cik / f"{acc}_{d}")) for d in docs)


def read_markers():
    """Reviewed manual section boundaries: (cik, item) -> row. See data/universe/section_markers.csv."""
    if not MARKERS.exists():
        return {}
    with MARKERS.open(encoding="utf-8") as f:
        return {(r["cik"], r["item"]): r for r in csv.DictReader(f)}


def cut_by_marker(text, marker):
    """Verbatim text from start_text through end_text. Both are copied exactly from the
    filing; only spacing may differ (line breaks can be typed as single spaces). The
    start must appear exactly once, so the cut is unambiguous."""
    def pattern(s):   # words must match exactly; any run of whitespace matches any run
        return r"\s+".join(re.escape(w) for w in s.split())
    starts = list(re.finditer(pattern(marker["start_text"]), text))
    if len(starts) != 1:
        raise ValueError(f"marker start_text for Item {marker['item']} found {len(starts)} times (need exactly 1)")
    end = re.compile(pattern(marker["end_text"])).search(text, starts[0].end())
    if not end:
        raise ValueError(f"marker end_text for Item {marker['item']} not found after start_text")
    section = text[starts[0].start(): end.end()].strip()
    if not 200 <= len(section.split()) <= MAX_WORDS:
        raise ValueError(f"marker section for Item {marker['item']} has {len(section.split())} words")
    return section


def process(firm, markers):
    cik = firm["cik"]
    filing, amendments = last_10k_before_cutoff(cik)
    acc = filing["accessionNumber"]
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{filing['primaryDocument']}"
    html = sec_get(url, RAW / cik / f"{acc}.htm").read_bytes().decode("utf-8", errors="replace")
    text = html_to_text(RAW / cik / f"{acc}.htm")
    sources = {"main": text}
    sections, methods = {}, []
    for item in ("1", "1A", "7"):
        marker = markers.get((cik, item))
        if marker:
            if marker["source"] not in sources:          # only "ex13" is fetched on demand
                assert marker["source"] == "ex13", f"unknown marker source {marker['source']}"
                sources["ex13"] = exhibit13_text(cik, acc)
            sections[item] = cut_by_marker(sources[marker["source"]], marker)
            methods.append(f"{item}:marker-{marker['source']}")
        else:
            sections[item] = cut_section(text, item)
            methods.append(f"{item}:auto")
    out = TEXT / f"{cik}_{acc}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n\n".join(sections.values()) + "\n", encoding="utf-8")
    return {
        "cik": cik, "company": firm["nport_name"], "ticker_figi_today": firm["ticker_figi_today"],
        "cover_tickers": "|".join(cover_tickers(html)),
        "form": filing["form"], "tenk_filing_date": filing["filingDate"], "tenk_report_date": filing["reportDate"],
        "tenk_accession": acc, "filing_url": url, "amendments_in_prior_year": amendments,
        "item1_words": len(sections["1"].split()), "item1a_words": len(sections["1A"].split()),
        "item7_words": len(sections["7"].split()), "total_chars": out.stat().st_size,
        "text_path": str(out.relative_to(ROOT)), "section_method": "|".join(methods),
        "status": "ok", "error": "",
    }


FIELDS = ["cik", "company", "ticker_figi_today", "cover_tickers", "form", "tenk_filing_date",
          "tenk_report_date", "tenk_accession", "filing_url", "amendments_in_prior_year",
          "item1_words", "item1a_words", "item7_words", "total_chars", "text_path",
          "section_method", "status", "error"]


def save_log(done):
    """Rewrite tenk_filings.csv (via a temp file, so a stop mid-write can't corrupt it)."""
    tmp = FILINGS.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, restval="")
        w.writeheader()
        w.writerows(done.values())
    tmp.replace(FILINGS)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cik", nargs="*", help="only these 10-digit CIKs (default: whole universe)")
    parser.add_argument("--limit", type=int, help="process at most this many unfinished firms (run in batches)")
    parser.add_argument("--retry-failed", action="store_true", help="also retry firms that failed before")
    parser.add_argument("--rebuild", action="store_true",
                        help="reprocess every firm from the cached downloads (no new SEC requests for cached files)")
    args = parser.parse_args()
    with UNIVERSE.open(encoding="utf-8") as f:
        firms = list(csv.DictReader(f))
    if args.cik:
        firms = [f for f in firms if f["cik"] in set(args.cik)]
        assert len(firms) == len(set(args.cik)), "some --cik values are not in the universe"

    done = {}
    if FILINGS.exists():
        in_universe = {f["cik"] for f in firms} if not args.cik else None
        with FILINGS.open(encoding="utf-8") as f:
            # drop log rows for CIKs no longer in the universe (e.g. a corrected CIK)
            done = {r["cik"]: r for r in csv.DictReader(f)
                    if in_universe is None or r["cik"] in in_universe}

    # Resume: skip firms already finished (text file present) and, unless asked, earlier failures.
    def finished(cik):
        if args.rebuild:
            return False
        old = done.get(cik)
        if not old:
            return False
        if old["status"] == "ok":
            return (ROOT / old["text_path"]).exists()
        return not args.retry_failed
    markers = read_markers()
    todo = [f for f in firms if not finished(f["cik"])][: args.limit]
    print(f"{len(firms) - len(todo)} already done or skipped; processing {len(todo)}", flush=True)

    for n, firm in enumerate(todo, 1):
        try:
            done[firm["cik"]] = process(firm, markers)
        except Exception as exc:   # record the reason and keep going; nothing is invented
            done[firm["cik"]] = {"cik": firm["cik"], "company": firm["nport_name"],
                                 "ticker_figi_today": firm["ticker_figi_today"],
                                 "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        save_log(done)             # progress is saved after every firm
        r = done[firm["cik"]]
        print(f"[{n}/{len(todo)}] {r['cik']} {r['company'][:30]:30} {r['status']} {r.get('error', '')}", flush=True)

    selected = [done[f["cik"]] for f in firms if f["cik"] in done]   # only the firms asked for
    ok = sum(r["status"] == "ok" for r in selected)
    failed = [r for r in selected if r["status"] == "failed"]
    print(f"\nSummary: {ok} ok, {len(failed)} failed, {len(firms) - ok - len(failed)} not attempted yet "
          f"(details in {FILINGS.relative_to(ROOT)})")
    for r in failed:
        print(f"  FAILED {r['company'][:35]:35} {r['error']}")


if __name__ == "__main__":
    main()
