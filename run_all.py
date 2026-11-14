"""Rebuild the whole v0 project with one command:  python run_all.py

Steps (each is a script in scripts/; this file only runs them in order):
  1. build_universe.py    S&P 500 members on 2025-04-02 (SPY's SEC holdings report)
  2. fetch_10k_text.py    each firm's last 10-K before 2025-04-02 -> Items 1, 1A, 7 as text
  3. build_manifest.py    the 10-firm v0 sample, in the columns the scorer expects
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
"""
import argparse
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
    live = parser.parse_args().live

    run("scripts/build_universe.py")
    run("scripts/fetch_10k_text.py")
    run("scripts/build_manifest.py", "--v0")
    run("scripts/validate_manifest.py")
    run("scripts/tariff_batch.py", "--backend", "parrot", "--model", MODEL,
        "--manifest", "data/universe/manifest.csv", "--output", "outputs/batch_v0",
        *([] if live else ["--offline"]), allow_firm_failures=True)
    run("scripts/make_outputs.py")
    print("\nDone. Failed firms (if any) are listed in outputs/batch_v0/failures.csv")


if __name__ == "__main__":
    main()
