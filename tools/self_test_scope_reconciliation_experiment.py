"""
CLAUDE-P25 self-test laboratory: the scope-reconciliation controlled
experiment.

A TEST/LAB script (same status as every other tools/self_test_*.py
script) - makes MANY real, billed Anthropic calls against the REAL
production consistency path (services/bhive_parser.py's BHiveParser.
_check_consistency), never run automatically by the test suite.

Runs every pair in tests/self_test/scope_reconciliation_bank.py against
the CURRENT production consistency check, N repetitions each, and
records whether RECONCILED pairs are (correctly) left unflagged and
CONFLICT pairs are (correctly) flagged - independent of, and never
reusing, the aquatic-centre candidate's own text.

Run:
    venv/Scripts/python.exe tools/self_test_scope_reconciliation_experiment.py [--label LABEL] [--reps N]
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / ".env", override=True)

from services.bhive_parser import BHiveParser, CONSISTENCY_PROMPT_VERSION  # noqa: E402
from tests.self_test.scope_reconciliation_bank import PAIRS  # noqa: E402

RESULTS_DIR = REPO_ROOT / "tests" / "self_test" / "experiments"


@dataclass
class ScopeRun:
    dimension: str
    kind: str
    repetition: int
    item_ids: list[str]
    model: str
    prompt_version: str
    raw_response_text: str
    input_tokens: int | None
    output_tokens: int | None
    latency_seconds: float | None
    checked: bool
    note: str | None
    flags: list[dict]
    correct: bool | None  # None if SKIPPED
    timestamp: str


def run_once(pair, repetition: int, parser: BHiveParser) -> ScopeRun:
    usage_sink: dict = {}
    items = [pair.item_a, pair.item_b]
    flags, checked, note = parser._check_consistency(items, usage_sink=usage_sink)  # noqa: SLF001
    flag_dicts = [
        {
            "a": f.requirement_a_id, "b": f.requirement_b_id, "explanation": f.explanation,
            "requirement_a_evidence": f.requirement_a_evidence, "requirement_b_evidence": f.requirement_b_evidence,
            "reconciliation_checked": f.reconciliation_checked,
            "requirement_a_scope": getattr(f, "requirement_a_scope", None),
            "requirement_b_scope": getattr(f, "requirement_b_scope", None),
            "scopes_overlap": getattr(f, "scopes_overlap", None),
            "scope_reconciliation_reasoning": getattr(f, "scope_reconciliation_reasoning", None),
        }
        for f in flags
    ]
    was_flagged = len(flags) > 0
    correct = None
    if checked:
        correct = (not was_flagged) if pair.kind == "reconciled" else was_flagged

    run = ScopeRun(
        dimension=pair.dimension, kind=pair.kind, repetition=repetition,
        item_ids=[i.id for i in items], model=parser.model, prompt_version=CONSISTENCY_PROMPT_VERSION,
        raw_response_text=usage_sink.get("raw_response_text", ""), input_tokens=usage_sink.get("input_tokens"),
        output_tokens=usage_sink.get("output_tokens"), latency_seconds=usage_sink.get("latency_seconds"),
        checked=checked, note=note, flags=flag_dicts, correct=correct, timestamp=datetime.now(timezone.utc).isoformat(),
    )
    label = "SKIPPED" if not checked else ("PASS" if correct else "FAIL")
    print(f"  [{pair.dimension}/{pair.kind} #{repetition}] {label} ({len(flags)} flag(s))")
    return run


def main() -> int:
    parser_args = argparse.ArgumentParser()
    parser_args.add_argument("--label", default="run")
    parser_args.add_argument("--reps", type=int, default=2)
    args = parser_args.parse_args()

    parser = BHiveParser()
    if not parser.api_key:
        print("SKIPPED: no ANTHROPIC_API_KEY configured - cannot run a real experiment.")
        return 1

    all_runs: list[ScopeRun] = []
    for pair in PAIRS:
        print(f"\n=== {pair.dimension} / {pair.kind} ===")
        for rep in range(1, args.reps + 1):
            all_runs.append(run_once(pair, rep, parser))

    out_path = RESULTS_DIR / f"scope_reconciliation_{args.label}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps([asdict(r) for r in all_runs], indent=2), encoding="utf-8")

    print(f"\n{'=' * 70}\nSUMMARY ({args.label})\n{'=' * 70}")
    by_kind: dict[str, list[bool | None]] = {"reconciled": [], "conflict": []}
    for r in all_runs:
        if r.correct is not None:
            by_kind[r.kind].append(r.correct)
    for kind, results in by_kind.items():
        total = len(results)
        passed = sum(1 for v in results if v)
        print(f"{kind}: {passed}/{total} correct")
    print(f"\nAll {len(all_runs)} runs recorded: {out_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
