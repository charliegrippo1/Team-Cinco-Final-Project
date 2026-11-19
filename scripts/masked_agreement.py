"""Audit A2: compare each v0 firm's v1 score with names hidden (masked) and shown.

Reads  outputs/batch_masked/llm_run_log.csv   (tariff_batch.py --masked --stage score)
       outputs/batch_v1/llm_run_log.csv       (the full run, names shown)
Writes outputs/v1/v1_masked_agreement.csv     one row per firm with both scores
       outputs/v1/v1_masked_agreement.md      summary against the pass bar in specs_tried.md #28

Pass bar (#28, fixed before any full-sample result): at least 80% of firms within one
point AND mean absolute difference at most 0.75.

Run from the repository root:  python scripts/masked_agreement.py
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASKED = ROOT / "outputs/batch_masked"
NORMAL = ROOT / "outputs/batch_v1"
OUT = ROOT / "outputs/v1"


def scores(batch, masked):
    """ticker -> score from a batch's run log; every row must have the expected masked flag."""
    out = {}
    with (batch / "llm_run_log.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            assert r["masked"] == str(masked), f"{batch.name}: {r['ticker']} masked={r['masked']}"
            assert r["ticker"] not in out, f"{batch.name}: {r['ticker']} twice"
            out[r["ticker"]] = int(r["score"])
    return out


def main():
    summary = json.loads((MASKED / "summary.json").read_text(encoding="utf-8"))
    assert summary["masked"] is True and summary["rubric"] == "v1", "masked batch must be masked, v1 rubric"
    masked, normal = scores(MASKED, True), scores(NORMAL, False)
    both = sorted(set(masked) & set(normal))
    assert both, "no firm has both a masked and a normal score"
    rows = [{"ticker": t, "score_names_shown": normal[t], "score_names_hidden": masked[t],
             "difference": masked[t] - normal[t]} for t in both]
    diffs = [abs(r["difference"]) for r in rows]
    exact, within1, mad = sum(d == 0 for d in diffs), sum(d <= 1 for d in diffs), sum(diffs) / len(diffs)
    passed = within1 / len(rows) >= 0.80 and mad <= 0.75

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "v1_masked_agreement.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    # The normal batch holds all 500 firms; only the masked (v0) firms matter here.
    missing = sorted(set(masked) - set(normal))
    lines = [f"Masked-name test (audit A2, plan in `specs_tried.md` #28): {len(rows)} v0 firms scored "
             "with the v1 rubric, once with names shown and once hidden.", "",
             f"- Exact match: {exact} of {len(rows)}",
             f"- Within one point: {within1} of {len(rows)} ({within1 / len(rows):.0%}; bar: at least 80%)",
             f"- Mean absolute difference: {mad:.2f} points (bar: at most 0.75)",
             f"- **{'Passed' if passed else 'Did not pass'}** the bar set before the full run.", ""]
    if missing:
        lines.append(f"Scored on one side only (not compared): {', '.join(missing)}.")
        lines.append("")
    lines += ["| Firm | Names shown | Names hidden | Difference |", "|---|---|---|---|"]
    lines += [f"| {r['ticker']} | {r['score_names_shown']} | {r['score_names_hidden']} | {r['difference']:+d} |"
              for r in rows]
    (OUT / "v1_masked_agreement.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:6]))


if __name__ == "__main__":
    main()
