"""
CLAUDE-P16 self-test laboratory, tier 4: semantic inconsistency /
incompatible obligations.

A TEST/LAB script (same status as the prior self_test_lab_*.py scripts)
- makes REAL, billed Anthropic calls, never run automatically by the
test suite.

The question this tier answers: can Archiosk understand incompatibility
of MEANING, not just difference of text. Cases A/B/C/E use BEEHIVE's
real, existing consistency-check (services/bhive_parser.py -
_build_consistency_prompt was extended for this tier to reason about
semantic/operational conflicts, paraphrase, and drift - a real
production fix, not a benchmark-only prompt). Case D uses
requirement_investigation.py's real related_requirements/relationship_
type extension (CLAUDE-P16) to test whether a REAL, registered
"qualifies" Relationship changes the outcome - run once WITHOUT it and
once WITH it, to demonstrate the plumbing fix actually matters, not just
exists.

The investigator receives ONLY the same governed evidence it would see
in production - no PlantedMutation, no test-only hint that two clauses
are "supposed" to conflict.

Requires a real ANTHROPIC_API_KEY in .env - without one this honestly
reports SKIPPED rather than fabricating a result.

Run:
    venv/Scripts/python.exe tools/self_test_lab_004_semantic.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / ".env", override=True)

from services.bhive_parser import BHiveParser, RequirementItem  # noqa: E402
from services.case_workspace import CaseWorkspaceStore, OBJECT_KIND_REQUIREMENT  # noqa: E402
from services.requirement_investigation import investigate_requirement  # noqa: E402
from tests.self_test.evaluator import evaluate  # noqa: E402
from tests.self_test.golden_corpus_semantic import build_semantic_clean_baseline  # noqa: E402
from tests.self_test.mutations_semantic import (  # noqa: E402
    apply_semantic_drift,
    build_exception_resolves_conflict_project,
    build_hidden_qualification_conflict_project,
    build_jointly_impossible_project,
)


def as_requirement_items(workspace, requirement_ids: list[str]) -> list[RequirementItem]:
    by_id = {r["id"]: r for r in workspace.requirements}
    return [
        RequirementItem(id=rid, text=by_id[rid]["text_reference"], category="scope_of_work", confidence=0.9, source_line=0)
        for rid in requirement_ids
    ]


def run_consistency_check(requirements: list[RequirementItem]):
    parser = BHiveParser()
    if not parser.api_key:
        print("SKIPPED: no ANTHROPIC_API_KEY configured - cannot run a real blind test.")
        return None
    flags, checked, note = parser._check_consistency(requirements)  # noqa: SLF001 - lab script, not production
    if not checked:
        print(f"SKIPPED: consistency check did not actually run ({note}).")
        return None
    return flags


def print_flags(flags) -> None:
    print(f"Flags raised: {len(flags)}")
    for flag in flags:
        print(f"  - ({flag.requirement_a_id}, {flag.requirement_b_id}): {flag.explanation}")


def main() -> int:
    tmp_dir = Path(tempfile.mkdtemp(prefix="self_test_lab_semantic_"))
    all_ok = True
    try:
        store = CaseWorkspaceStore(tmp_dir)

        print("=== CLEAN BASELINE (compatible pairs + Case C paraphrase - expect nothing) ===")
        clean = build_semantic_clean_baseline(store, "semantic-clean", tmp_dir / "clean")
        clean_ids = [
            clean["eoc_operational_id"], clean["eoc_backup_power_id"],
            clean["record_drawings_id"], clean["as_built_id"],
            clean["autonomy_rfp_id"], clean["autonomy_schedule_id"],
        ]
        clean_flags = run_consistency_check(as_requirement_items(clean["workspace"], clean_ids))
        if clean_flags is None:
            return 1
        print_flags(clean_flags)
        if clean_flags:
            print("FAIL: the clean, coherent corpus was not left alone - manufactured or genuinely found something.")
            all_ok = False
        else:
            print("PASS: no semantic conflicts manufactured, and the paraphrase pair was not falsely flagged.")

        print("\n=== CASE A: individually reasonable, jointly impossible ===")
        case_a = build_jointly_impossible_project(store, "semantic-case-a", tmp_dir / "case_a")
        flags_a = run_consistency_check(
            as_requirement_items(case_a["workspace"], [case_a["operational_id"], case_a["shutdown_id"]])
        )
        if flags_a is None:
            return 1
        print_flags(flags_a)
        result_a = evaluate(flags=flags_a, answer_key=[case_a["answer_key"]])
        print(f"Result: {result_a.summary()}")
        all_ok &= not result_a.missed

        print("\n=== CASE B: hidden qualification conflict ===")
        case_b = build_hidden_qualification_conflict_project(store, "semantic-case-b", tmp_dir / "case_b")
        flags_b = run_consistency_check(
            as_requirement_items(case_b["workspace"], [case_b["access_id"], case_b["security_id"]])
        )
        if flags_b is None:
            return 1
        print_flags(flags_b)
        result_b = evaluate(flags=flags_b, answer_key=[case_b["answer_key"]])
        print(f"Result: {result_b.summary()}")
        print(
            "NOTE: 'compatible / ambiguous / contradictory' is a qualitative "
            "determination - read the explanation above for whether it correctly "
            "frames this as a qualification/constraint relationship, not just "
            "whether a flag was raised."
        )
        all_ok &= not result_b.missed

        print("\n=== CASE D: exception resolves apparent contradiction (before/after the Relationship fix) ===")
        case_d = build_exception_resolves_conflict_project(store, "semantic-case-d", tmp_dir / "case_d")
        workspace_d = case_d["workspace"]
        unlocked = next(r for r in workspace_d.requirements if r["id"] == case_d["unlocked_id"])

        print("-- WITHOUT the exception surfaced (no related_requirements) --")
        result_without = investigate_requirement(
            question="Is this compatible with the site's security requirements, or does it create a conflict?",
            requirement=unlocked, adjudication_history=[],
            evidence={"findings": [], "relationships": [], "accepted_knowledge": []},
        )
        if not result_without.ran:
            print(f"SKIPPED: {result_without.skipped_reason}")
            return 1
        print(f"Assessment: {result_without.assessment}")
        print(f"needs_human_judgment: {result_without.needs_human_judgment}, confidence: {result_without.confidence}")

        print("\n-- WITH the real registered exception Relationship surfaced --")
        store_instance = CaseWorkspaceStore(tmp_dir)
        related_requirements = []
        for rel in store_instance.relationships_for(workspace_d, OBJECT_KIND_REQUIREMENT, case_d["unlocked_id"]):
            other_id = rel["from_id"] if rel["to_id"] == case_d["unlocked_id"] else rel["to_id"]
            other = next((r for r in workspace_d.requirements if r["id"] == other_id), None)
            if other:
                related_requirements.append({
                    "id": other["id"], "original_requirement_identifier": other["original_requirement_identifier"],
                    "text_reference": other["text_reference"], "status": other["status"],
                    "relationship_type": rel["relationship_type"],
                })
        # Also surface the locked-doors requirement itself as context, same as
        # a real investigation would via relationships_for on each side.
        locked = next(r for r in workspace_d.requirements if r["id"] == case_d["locked_id"])
        related_requirements.append({
            "id": locked["id"], "original_requirement_identifier": locked["original_requirement_identifier"],
            "text_reference": locked["text_reference"], "status": locked["status"],
            "note": "the apparently-conflicting security requirement",
        })
        result_with = investigate_requirement(
            question="Is this compatible with the site's security requirements, or does it create a conflict?",
            requirement=unlocked, adjudication_history=[],
            evidence={"findings": [], "relationships": [], "accepted_knowledge": []},
            related_requirements=related_requirements,
        )
        print(f"Assessment: {result_with.assessment}")
        print(f"needs_human_judgment: {result_with.needs_human_judgment}, confidence: {result_with.confidence}")
        print(
            "\nNOTE: compare the two assessments above - WITH the real 'qualifies' "
            "Relationship surfaced, the assessment should recognize the exception "
            "resolves the apparent conflict rather than stopping at the first "
            "pairwise contradiction. Qualitative judgment, not auto-graded."
        )

        print("\n=== CASE E: semantic drift across documents ===")
        drift_ids = [clean["autonomy_rfp_id"], clean["autonomy_schedule_id"]]
        pre_drift_flags = run_consistency_check(as_requirement_items(clean["workspace"], drift_ids))
        if pre_drift_flags is None:
            return 1
        print(f"Before drift (should already be 0, reusing the clean baseline pair): {len(pre_drift_flags)} flags")

        drift_answer_key = apply_semantic_drift(
            store, clean["workspace"], clean["autonomy_rfp_id"], clean["autonomy_schedule_id"],
        )
        workspace_after = store.get(clean["workspace"].project_id)
        flags_e = run_consistency_check(
            as_requirement_items(workspace_after, [clean["autonomy_rfp_id"], drift_answer_key.secondary_location])
        )
        if flags_e is None:
            return 1
        print_flags(flags_e)
        result_e = evaluate(flags=flags_e, answer_key=[drift_answer_key])
        print(f"Result: {result_e.summary()}")
        all_ok &= not result_e.missed

        print(f"\n=== OVERALL (structurally-graded cases: clean, A, B, E): {'PASS' if all_ok else 'FAIL'} ===")
        return 0 if all_ok else 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
