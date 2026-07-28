"""
CLAUDE-P23 self-test laboratory: the compounding-suspicion controlled
experiment.

A TEST/LAB script (same status as tools/self_test_lab*.py) - makes MANY
real, billed Anthropic calls against the REAL production consistency-
check path (services/bhive_parser.py's BHiveParser._check_consistency,
via its new, purely-additive `usage_sink` instrumentation hook - never a
reimplementation), never run automatically by the test suite.

The hypothesis under test: does one difficult or apparently-contradictory
requirement pair increase the model's tendency to flag UNRELATED clean
pairs in the same consistency-check batch - "compounding suspicion" -
first observed anecdotally while admission-reviewing a revised candidate
specimen in CLAUDE-P22.

Every permutation is built from tests/self_test/compounding_suspicion_
bank.py's fixed, already-validated requirement bank - never new prose -
so any classification change is attributable to NEIGHBORING CONTEXT, not
to a difference in the item's own text.

Run:
    venv/Scripts/python.exe tools/self_test_compounding_suspicion_experiment.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / ".env", override=True)

from services.bhive_parser import BHiveParser, CONSISTENCY_PROMPT_VERSION, RequirementItem  # noqa: E402
from tests.self_test.compounding_suspicion_bank import (  # noqa: E402
    ALL_ITEMS_BY_ID,
    AMBIGUOUS_ITEMS,
    BAIT_ITEMS,
    BAIT_PAIR_IDS,
    CLEAN_ITEMS,
    CONTRA_ITEMS,
    DIFFICULT_ITEMS,
)

EXPERIMENTS_DIR = REPO_ROOT / "tests" / "self_test" / "experiments"
REPS_PRIMARY = 3   # clean/bait baseline + each single-category addition + all-together
REPS_SECONDARY = 2  # order, isolation, batch-size variants


@dataclass
class RunRecord:
    permutation: str
    repetition: int
    requirement_ids_in_order: list[str]
    model: str
    prompt_version: str
    prompt: str
    raw_response_text: str
    input_tokens: int | None
    output_tokens: int | None
    latency_seconds: float | None
    flags: list[dict]  # [{"a": id, "b": id, "explanation": str}, ...]
    bait_pair_flagged: bool
    bait_pair_explanation: str | None
    checked: bool
    note: str | None
    timestamp: str


def run_once(permutation_name: str, repetition: int, items: list[RequirementItem], parser: BHiveParser) -> RunRecord:
    usage_sink: dict = {}
    flags, checked, note = parser._check_consistency(items, usage_sink=usage_sink)  # noqa: SLF001 - lab script

    flag_dicts = [
        {
            "a": f.requirement_a_id, "b": f.requirement_b_id, "explanation": f.explanation,
            "requirement_a_evidence": f.requirement_a_evidence, "requirement_b_evidence": f.requirement_b_evidence,
            "reconciliation_checked": f.reconciliation_checked,
        }
        for f in flags
    ]
    bait_flag = next(
        (f for f in flags if {f.requirement_a_id, f.requirement_b_id} == set(BAIT_PAIR_IDS)),
        None,
    )
    record = RunRecord(
        permutation=permutation_name, repetition=repetition,
        requirement_ids_in_order=[item.id for item in items],
        model=parser.model, prompt_version=CONSISTENCY_PROMPT_VERSION,
        prompt=usage_sink.get("prompt", ""), raw_response_text=usage_sink.get("raw_response_text", ""),
        input_tokens=usage_sink.get("input_tokens"), output_tokens=usage_sink.get("output_tokens"),
        latency_seconds=usage_sink.get("latency_seconds"),
        flags=flag_dicts, bait_pair_flagged=bait_flag is not None,
        bait_pair_explanation=bait_flag.explanation if bait_flag else None,
        checked=checked, note=note, timestamp=datetime.now(timezone.utc).isoformat(),
    )
    status = "SKIPPED" if not checked else ("BAIT FLAGGED" if record.bait_pair_flagged else "bait clean")
    print(f"  [{permutation_name} #{repetition}] {len(flags)} flag(s) - {status}")
    return record


def build_permutations() -> dict[str, list[RequirementItem]]:
    clean_and_bait = CLEAN_ITEMS + BAIT_ITEMS
    all_items = CLEAN_ITEMS + BAIT_ITEMS + CONTRA_ITEMS + DIFFICULT_ITEMS + AMBIGUOUS_ITEMS
    return {
        "a_clean_only": clean_and_bait,
        "b_clean_plus_contra": clean_and_bait + CONTRA_ITEMS,
        "c_clean_plus_difficult": clean_and_bait + DIFFICULT_ITEMS,
        "d_clean_plus_ambiguous": clean_and_bait + AMBIGUOUS_ITEMS,
        "e_all_together": all_items,
        "f_all_together_shuffled_order": [
            CONTRA_ITEMS[0], BAIT_ITEMS[0], DIFFICULT_ITEMS[0], CLEAN_ITEMS[0],
            AMBIGUOUS_ITEMS[0], DIFFICULT_ITEMS[1], CONTRA_ITEMS[1], CLEAN_ITEMS[1],
            DIFFICULT_ITEMS[2], AMBIGUOUS_ITEMS[1], BAIT_ITEMS[1],
        ],
        # "difficult last" reuses (c)'s own records - same item list - rather
        # than re-running an identical permutation under a new name.
        "g_difficult_first": DIFFICULT_ITEMS + clean_and_bait,
        "h_difficult_isolated_alone": DIFFICULT_ITEMS,
        "h_rest_without_difficult": clean_and_bait + CONTRA_ITEMS + AMBIGUOUS_ITEMS,
        "i_small_batch_1_clean_bait": clean_and_bait,
        "i_small_batch_2_contra_difficult_ambiguous": CONTRA_ITEMS + DIFFICULT_ITEMS + AMBIGUOUS_ITEMS,
    }


def main() -> int:
    parser = BHiveParser()
    if not parser.api_key:
        print("SKIPPED: no ANTHROPIC_API_KEY configured - cannot run a real experiment.")
        return 1

    permutations = build_permutations()
    records: list[RunRecord] = []

    for name, items in permutations.items():
        reps = REPS_PRIMARY if name in ("a_clean_only", "b_clean_plus_contra", "c_clean_plus_difficult", "d_clean_plus_ambiguous", "e_all_together") else REPS_SECONDARY
        print(f"\n=== {name} ({len(items)} items, {reps} repetition(s)) ===")
        for rep in range(1, reps + 1):
            record = run_once(name, rep, items, parser)
            records.append(record)

    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXPERIMENTS_DIR / f"compounding_suspicion_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps([asdict(r) for r in records], indent=2), encoding="utf-8")
    print(f"\nAll {len(records)} runs recorded: {out_path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
