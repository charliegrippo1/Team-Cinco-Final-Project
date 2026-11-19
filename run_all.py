"""Rebuild the project with one command.
    python run_all.py               v0: the 10-firm Checkpoint 2 sample -> outputs/batch_v0
    python run_all.py --full        v1: every firm with 10-K text (500) -> outputs/batch_v1

Steps (each is a script in scripts/; this file only runs them in order):
  1. build_universe.py    S&P 500 members on 2025-04-02 (SPY's SEC holdings report)
  2. fetch_10k_text.py    each firm's last 10-K before 2025-04-02 -> Items 1, 1A, 7 as text
  3. build_manifest.py    the firms to score, in the columns the scorer expects
                          (v0: data/universe/manifest.csv; --full: manifest_full.csv)
  4. validate_manifest.py checks every manifest fact against EDGAR (stops on any problem)
  5. tariff_batch.py      exposure score (0-4) for each firm + April 2-4 prices -> returns
  6. make_outputs.py      dashboard data, firm table, regression, chart in outputs/

Downloads are cached under data/raw/, so a rerun makes no new requests.
  - Steps 1-2 need the SEC_USER_AGENT environment variable the first time
    (e.g. "Team Cinco FIN331 class project you@school.edu"); SEC requires a contact.
  - Step 5 reads saved model answers from data/raw/tariff_batch/ (kept in git), so it
    needs no API key and costs nothing. Use  python run_all.py --live  to also score
    firms that have no saved answer; that needs edsl (Python 3.10-3.13) and the
    EXPECTED_PARROT_API_KEY environment variable, and it uses Expected Parrot credits.
  - v0 replays the original rubric wording (--rubric v0); --full scores with the v1
    rubric and writes the full-sample tables, including the A1 sector regressions,
    to outputs/v1/ (staging: the dashboard still reads the v0 data until it is switched).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL = "gpt-4.1-mini"          # chosen for Checkpoint 2; see specs_tried.md entries 11-14


def run(*args, allow_firm_failures=False):
    print(f"\n=== {' '.join(args)}", flush=True)
    code = subprocess.run([sys.executable, *args], cwd=ROOT).returncode
    # tariff_batch.py exits 1 when some firms fail (they are listed in failures.csv,
    # never filled in), so that one step may continue; anything else stops the run.
    if code != 0 and not (allow_firm_failures and code == 1):
        sys.exit(f"Stopped: {args[0]} failed (exit code {code})")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="call Expected Parrot for firms without a saved answer")
    parser.add_argument("--full", action="store_true", help="score every firm with 10-K text (v1), not the v0 sample")
    args = parser.parse_args()
    manifest, output = (("data/universe/manifest_full.csv", "outputs/batch_v1") if args.full
                        else ("data/universe/manifest.csv", "outputs/batch_v0"))

    run("scripts/build_universe.py")
    run("scripts/fetch_10k_text.py")
    run("scripts/build_manifest.py", *([] if args.full else ["--v0"]))
    run("scripts/validate_manifest.py", *(["--full"] if args.full else []))
    # v0 replays the frozen Checkpoint 2 wording; the full sample is scored with the
    # v1 rubric (specs_tried.md #21), including the ten firms scored in v0.
    run("scripts/tariff_batch.py", "--backend", "parrot", "--model", MODEL,
        "--rubric", "v1" if args.full else "v0", "--manifest", manifest, "--output", output,
        *([] if args.live else ["--offline"]), allow_firm_failures=True)
    completed = json.loads((ROOT / output / "summary.json").read_text())["completed_rows"]
    if args.full and completed == 0:
        sys.exit("Stopped: no firm has a v1 score yet. Run  python run_all.py --full --live  to score them.")
    if args.full:
        # The 20 blind hand scores drawn before scoring (specs_tried.md #27).
        run("scripts/make_outputs.py", "--batch", output, "--prefix", "v1", "--out", "outputs/v1",
            "--hand-check", "audits/hand_check_v1.csv")
    else:
        run("scripts/make_outputs.py")
    print(f"\nDone. Failed firms (if any) are listed in {output}/failures.csv")


if __name__ == "__main__":
    main()
