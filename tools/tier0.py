#!/usr/bin/env python
"""Tier 0 - the fast-feedback test lane.

CLAUDE-TEST-TIER0-01. `TEST_LANES.md` established Lanes A-E as hand-maintained
lists of file paths, and deliberately stopped short of a marker taxonomy. This
does not add one. It adds the one lane whose membership is a *mechanical fact
about a file* rather than a judgement about a feature: does this test need the
Flask application at all?

A test that never calls `create_app`/`test_client` cannot pay app-construction,
ingestion or store setup costs. Measured on this repository (2026-09-05, 5
runs): 52 such files, 853 tests, 663 subtests, mean 26.71s / median 25.66s /
min 23.57s / max 30.24s / stdev 2.86s - against a full suite of 25-35 minutes on a
good day and 4h35m on a bad one. That is the whole point of the lane: after a
templates/CSS/registry edit you learn in seconds whether the structural
assertions still hold, instead of choosing between "no feedback" and "the gate".

WHAT IT IS NOT

Not a replacement for any existing lane, and emphatically not for Lane E. Tier 0
cannot catch anything that needs a rendered page, an authorization decision or a
real store - the mobile-submenu defect that would have made Window > Panels
unreachable on a phone was caught by the FULL suite, not by a source scan. Read
`TEST_LANES.md`'s "Do not" section; none of it is relaxed here.

WHY THE SET IS DERIVED, NOT LISTED

The counts above are a dated observation, not a property of this tool - the
selection is derived on every run, so it grows on its own as source-scan tests
are added (49/793 when this was written, 50/803 on 2026-09-01, 52/853 now).
Run `--list` rather than trusting any of those numbers.

A hand-maintained list of paths goes stale silently: a new source-scan test
simply never joins the lane, and nothing says so. The two rules below are
checked against the files themselves on every run, so the lane grows with the
suite. `tests/test_tier0_lane_01.py` asserts the rules still select a sane set,
so a change here fails loudly rather than quietly shrinking the lane to nothing.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TESTS = _REPO_ROOT / "tests"

# Needs the Flask application - app construction, blueprints, the SQLite
# in-memory DB and (usually) a real ingestion per test. Not Tier 0 at any price.
NEEDS_APP = ("create_app", "test_client", "app_fixture")

# Heavyweight even without the app. Spawning real OS processes or a real
# Chromium is legitimate and valuable - test_storage_bridge_durable_05 is how
# the bridge_queue WinError 32 race was reproduced rather than guessed - but it
# is exactly the class of work whose timing varies with machine load, and the
# lane's contract is a stable sub-minute number. `wd_nas_bridge` names the
# deliberately-untracked NAS fixture tree, which is absent on most checkouts.
HEAVY = ("multiprocessing", "subprocess.", "sync_playwright", "wd_nas_bridge")

# A Tier 0 test asserts against source text it read itself. This is what keeps
# the lane honest: without it the set silently widens to "every test that
# happens not to mention create_app", which measured 97 files and was still
# running minutes in - real service-logic tests doing real work, correctly
# excluded. Membership is "reads files and asserts on them", not "is fast today".
SOURCE_SCAN = "read_text("

# 30s is not a guess. The two heaviest tests in this repository are a real
# headless-Chromium geometry test (5.46s) and a four-process bridge-claim race
# (2.89s), neither of which is in this lane. Every member is far below that, so
# a Tier 0 test hitting 30s is a hang, not slow work.
TIMEOUT_SECONDS = 30


def tier0_files() -> list[str]:
    """Every test file the two rules above select, repo-relative, sorted."""
    selected = []
    for path in sorted(_TESTS.glob("test_*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(marker in text for marker in NEEDS_APP):
            continue
        if any(marker in text for marker in HEAVY):
            continue
        if SOURCE_SCAN not in text:
            continue
        selected.append(f"tests/{path.name}")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true",
                        help="print the selected files and exit, running nothing")
    parser.add_argument("pytest_args", nargs="*",
                        help="extra arguments passed straight through to pytest")
    args = parser.parse_args()

    files = tier0_files()
    if args.list:
        print("\n".join(files))
        print(f"\n{len(files)} files", file=sys.stderr)
        return 0

    if not files:
        # Never silently "pass" an empty lane - a green run over zero tests is
        # the most expensive kind of false assurance this repository can buy.
        print("Tier 0 selected NO files - the selection rules are broken.",
              file=sys.stderr)
        return 2

    command = [sys.executable, "-m", "pytest", "-q",
               f"--timeout={TIMEOUT_SECONDS}", *files, *args.pytest_args]
    print(f"Tier 0: {len(files)} files, --timeout={TIMEOUT_SECONDS}\n", flush=True)
    return subprocess.call(command, cwd=_REPO_ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
