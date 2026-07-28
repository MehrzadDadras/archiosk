"""
CLAUDE-P24 self-test laboratory: rechecking the revised aquatic-centre
candidate (276cac42-07c8-4866-be91-b78c9798cb6e) against the CLAUDE-P23
production consistency fix (verbatim evidence + reconciliation-checked +
party/role-label guardrail).

A TEST/LAB script (same status as every other tools/self_test_*.py
script) - makes MANY real, billed Anthropic calls, never run
automatically by the test suite. Read-only with respect to every prior
record: this script NEVER writes to candidates/276cac42-...json or its
existing -admission.json - both are preserved exactly as CLAUDE-P22 left
them. Results land in a separate, new file.

The question: was the revised candidate's unstable clean baseline (found
in CLAUDE-P22, before the order/adjacency fix existed) partly an artifact
of the now-fixed defect, or does the baseline remain inherently
ambiguous even under the fixed production path? "Do not keep rewording
until it happens to pass" - this script tests the EXISTING, unmodified
candidate text only.

Eight conditions, each run multiple times to distinguish stability from
sampling variance:
  clean_natural, clean_shuffle_1, clean_shuffle_2,
  mutated_natural, mutated_shuffle_1, mutated_shuffle_2,
  isolated_pair_mutated, isolated_pair_clean

Run:
    venv/Scripts/python.exe tools/self_test_candidate_recheck_276cac42.py
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
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
from services.case_workspace import CaseWorkspaceStore  # noqa: E402
from tools.self_test_candidate_lab import as_requirement_items, materialize_clean  # noqa: E402

CANDIDATES_DIR = REPO_ROOT / "tests" / "self_test" / "candidates"
RESULTS_DIR = REPO_ROOT / "tests" / "self_test" / "candidates"
CANDIDATE_ID = "276cac42-07c8-4866-be91-b78c9798cb6e"
TARGET_IDENTIFIER = "SPEC-22-41-04"
REFERENCE_IDENTIFIER = "SPEC-22-41-06"


@dataclass
class RecheckRun:
    condition: str
    repetition: int
    identifiers_in_order: list[str]
    model: str
    prompt_version: str
    prompt: str
    raw_response_text: str
    input_tokens: int | None
    output_tokens: int | None
    latency_seconds: float | None
    checked: bool
    note: str | None
    flags: list[dict]
    timestamp: str


def run_once(condition: str, repetition: int, parser: BHiveParser, items) -> RecheckRun:
    usage_sink: dict = {}
    flags, checked, note = parser._check_consistency(items, usage_sink=usage_sink)  # noqa: SLF001
    flag_dicts = [
        {
            "a": f.requirement_a_id, "b": f.requirement_b_id, "explanation": f.explanation,
            "requirement_a_evidence": f.requirement_a_evidence, "requirement_b_evidence": f.requirement_b_evidence,
            "reconciliation_checked": f.reconciliation_checked,
        }
        for f in flags
    ]
    run = RecheckRun(
        condition=condition, repetition=repetition, identifiers_in_order=[i.id for i in items],
        model=parser.model, prompt_version=CONSISTENCY_PROMPT_VERSION,
        prompt=usage_sink.get("prompt", ""), raw_response_text=usage_sink.get("raw_response_text", ""),
        input_tokens=usage_sink.get("input_tokens"), output_tokens=usage_sink.get("output_tokens"),
        latency_seconds=usage_sink.get("latency_seconds"), checked=checked, note=note,
        flags=flag_dicts, timestamp=datetime.now(timezone.utc).isoformat(),
    )
    status = "SKIPPED" if not checked else (f"{len(flags)} flag(s)")
    print(f"  [{condition} #{repetition}] {status}")
    for f in flag_dicts:
        print(f"      {f['a']} <-> {f['b']}: {f['explanation'][:160]}")
    return run


def main() -> int:
    candidate = json.loads((CANDIDATES_DIR / f"{CANDIDATE_ID}.json").read_text(encoding="utf-8"))
    parser = BHiveParser()
    if not parser.api_key:
        print("SKIPPED: no ANTHROPIC_API_KEY configured - cannot run a real recheck.")
        return 1

    tmp_dir = Path(tempfile.mkdtemp(prefix="self_test_candidate_recheck_"))
    all_runs: list[RecheckRun] = []
    try:
        store = CaseWorkspaceStore(tmp_dir)
        workspace = store.get_or_create("candidate-276cac42-recheck-clean")
        ids_by_identifier = materialize_clean(store, workspace, tmp_dir / "sources_clean", candidate)
        workspace = store.get(workspace.project_id)
        clean_items = as_requirement_items(workspace, list(ids_by_identifier.values()))
        clean_by_id = {item.id: item for item in clean_items}

        # Mutated variant: same materialization, but the target identifier's
        # text is swapped for the candidate's own proposed_mutation text -
        # a SEPARATE project so the clean project is never touched.
        mutated_workspace = store.get_or_create("candidate-276cac42-recheck-mutated")
        mutated_candidate = json.loads(json.dumps(candidate))  # deep copy, in-memory only
        for req in mutated_candidate["requirements"]:
            if req["identifier"] == TARGET_IDENTIFIER:
                req["text"] = candidate["proposed_mutation"]["mutated_text"]
        mutated_ids_by_identifier = materialize_clean(store, mutated_workspace, tmp_dir / "sources_mutated", mutated_candidate)
        mutated_workspace = store.get(mutated_workspace.project_id)
        mutated_items = as_requirement_items(mutated_workspace, list(mutated_ids_by_identifier.values()))
        mutated_by_id = {item.id: item for item in mutated_items}

        target_clean_id = ids_by_identifier[TARGET_IDENTIFIER]
        reference_clean_id = ids_by_identifier[REFERENCE_IDENTIFIER]
        target_mutated_id = mutated_ids_by_identifier[TARGET_IDENTIFIER]
        reference_mutated_id = mutated_ids_by_identifier[REFERENCE_IDENTIFIER]

        def shuffled(items_dict: dict, order: list[str]) -> list:
            return [items_dict[i] for i in order]

        # Two distinct shuffles - deliberately move SPEC-04/SPEC-06 apart.
        shuffle_1_ids = ["SPEC-22-41-01", "SPEC-22-41-04", "SPEC-22-41-02", "SPEC-22-41-07", "SPEC-22-41-03", "SPEC-22-41-05", "SPEC-22-41-06"]
        shuffle_2_ids = ["SPEC-22-41-06", "SPEC-22-41-01", "SPEC-22-41-03", "SPEC-22-41-05", "SPEC-22-41-02", "SPEC-22-41-07", "SPEC-22-41-04"]

        conditions = [
            ("clean_natural", clean_items, 4),
            ("clean_shuffle_1", shuffled(clean_by_id, [ids_by_identifier[i] for i in shuffle_1_ids]), 2),
            ("clean_shuffle_2", shuffled(clean_by_id, [ids_by_identifier[i] for i in shuffle_2_ids]), 2),
            ("mutated_natural", mutated_items, 4),
            ("mutated_shuffle_1", shuffled(mutated_by_id, [mutated_ids_by_identifier[i] for i in shuffle_1_ids]), 2),
            ("mutated_shuffle_2", shuffled(mutated_by_id, [mutated_ids_by_identifier[i] for i in shuffle_2_ids]), 2),
            ("isolated_pair_mutated", [mutated_by_id[target_mutated_id], mutated_by_id[reference_mutated_id]], 3),
            ("isolated_pair_clean", [clean_by_id[target_clean_id], clean_by_id[reference_clean_id]], 2),
        ]

        for condition, items, reps in conditions:
            print(f"\n=== {condition} ({len(items)} items, {reps} reps) ===")
            for rep in range(1, reps + 1):
                all_runs.append(run_once(condition, rep, parser, items))

        out_path = RESULTS_DIR / f"{CANDIDATE_ID}-recheck-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        out_path.write_text(json.dumps([asdict(r) for r in all_runs], indent=2), encoding="utf-8")
        print(f"\nAll {len(all_runs)} runs recorded: {out_path.relative_to(REPO_ROOT)}")
        return 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
