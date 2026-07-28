"""
CLAUDE-P19 - Golden Laboratory Suite v1's common runner.

The thinnest possible cross-tier entry point: reads tests/self_test/
manifest.py to find which lab module implements which tier, imports it,
calls its own run_tier() (see each tools/self_test_lab*.py's own
docstring for why that function's internals stay tier-specific), and
persists the combined result as one comparable SuiteRun record under
tests/self_test/runs/ - small enough to commit, so historical runs
survive to be diffed later (before a production change vs. after it),
per the tier's own explicit requirement.

Deliberately does NOT reduce a run to one score. print_summary() prints
every dimension from SuiteRun.dimension_summary() separately, plus a
per-specimen PASS/FAIL/QUALITATIVE line - an improvement in one dimension
can never silently hide a regression in another, because there is no
single number a regression could hide behind.

Real, billed Anthropic calls happen when the underlying tier scripts run
- same status as every tools/self_test_lab*.py this wraps. Never invoked
by the automated test suite.

Run the full suite:
    venv/Scripts/python.exe tools/self_test_runner.py

Run a subset (cheaper, e.g. after a change that only plausibly touched
one tier's evidence path):
    venv/Scripts/python.exe tools/self_test_runner.py --tiers semantic lifecycle

Compare two historical runs (both already committed under tests/
self_test/runs/) by hand - this script does not diff for you, since a
meaningful diff is a human reading two dimension_summary() blocks side by
side, not a mechanical subtraction.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / ".env", override=True)

from tests.self_test.manifest import TIERS  # noqa: E402
from tests.self_test.run_record import SUITE_VERSION, SpecimenResult, SuiteRun  # noqa: E402

RUNS_DIR = REPO_ROOT / "tests" / "self_test" / "runs"


def run_suite(tier_ids: list[str] | None = None, notes: str | None = None) -> SuiteRun:
    selected = [t for t in TIERS if tier_ids is None or t.tier_id in tier_ids]
    if not selected:
        raise ValueError(f"No registered tier matches {tier_ids!r} - see tests/self_test/manifest.py.")

    started_at = datetime.now(timezone.utc).isoformat()
    specimens: list[dict] = []
    for tier in selected:
        print(f"\n{'=' * 70}\nRUNNING TIER: {tier.name} ({tier.tier_id})\n{'=' * 70}")
        module = importlib.import_module(tier.lab_module)
        tier_specimens = module.run_tier()
        specimens.extend(asdict(s) for s in tier_specimens)
    completed_at = datetime.now(timezone.utc).isoformat()

    return SuiteRun(
        run_id=str(uuid.uuid4()), suite_version=SUITE_VERSION, started_at=started_at, completed_at=completed_at,
        tiers_executed=[t.tier_id for t in selected],
        app_model_default=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        specimens=specimens, notes=notes,
    )


def persist_run(run: SuiteRun) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    safe_started_at = run.started_at.replace(":", "").replace(".", "")
    path = RUNS_DIR / f"{safe_started_at}_{run.run_id[:8]}.json"
    path.write_text(json.dumps(run.to_dict(), indent=2), encoding="utf-8")
    return path


def print_summary(run: SuiteRun) -> None:
    print(f"\n{'=' * 70}\nGOLDEN LABORATORY SUITE v1 - RUN SUMMARY\n{'=' * 70}")
    print(f"run_id: {run.run_id}")
    print(f"suite_version: {run.suite_version}")
    print(f"started_at: {run.started_at}")
    print(f"completed_at: {run.completed_at}")
    print(f"app_model_default: {run.app_model_default}")
    print(f"tiers_executed: {', '.join(run.tiers_executed)}")
    print(f"specimen_count: {len(run.specimens)}")

    print("\n-- Per-dimension counts (never collapsed into one score) --")
    for dim, value in run.dimension_summary().items():
        print(f"  {dim}: {value}")

    print("\n-- Per-specimen detail --")
    for tier_id in run.tiers_executed:
        tier_specimens = run.specimens_for_tier(tier_id)
        print(f"\n  [{tier_id}] {len(tier_specimens)} specimen(s)")
        for s in tier_specimens:
            verdict = SpecimenResult(**s).passed()
            verdict_label = "QUALITATIVE" if verdict is None else ("PASS" if verdict else "FAIL")
            latency = f"{s['latency_seconds']:.1f}s" if s["latency_seconds"] is not None else "n/a"
            print(f"    [{verdict_label}] {s['specimen_id']} (calls={s['model_call_count']}, latency={latency}): {s['description']}")
            if s["false_positives"]:
                print(f"        false_positives: {s['false_positives']}")
            if s["unexpected_valid_discoveries"]:
                print(f"        unexpected_valid_discoveries: {s['unexpected_valid_discoveries']}")
            if not s["ran"]:
                print(f"        SKIPPED: {s['skipped_reason']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Golden Laboratory Suite v1 tiers and persist a comparable, historical run record.",
    )
    parser.add_argument(
        "--tiers", nargs="*", default=None,
        help="Tier ids to run (default: all six). See tests/self_test/manifest.py for valid ids.",
    )
    parser.add_argument("--notes", default=None, help="Free-text note attached to this run (e.g. what production change prompted it).")
    args = parser.parse_args()

    try:
        run = run_suite(tier_ids=args.tiers, notes=args.notes)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    path = persist_run(run)
    print_summary(run)
    print(f"\nRun persisted: {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
