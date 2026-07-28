"""
CLAUDE-P14 self-test laboratory, tier 2: cross-document consistency.

A TEST/LAB script (same status as tools/self_test_lab.py and
tests/fixtures/nreocrc/ingest_nreocrc_lab.py) - makes REAL, billed
Anthropic calls, never run automatically by the test suite. Builds a
real CaseWorkspaceStore-backed project with two genuinely separate,
provenance-bearing Sources (an RFP excerpt and an Appendix/Schedule
excerpt) stating the same coordinated 96-hour autonomy requirement, runs
BEEHIVE's real consistency-check blind against the two real registered
Requirements, then revises ONLY the Appendix Requirement (96 -> 72
hours, via the real Supersession-tracked revise_requirement path) and
runs the same check again.

The investigator is given ONLY each real Requirement's id/text (via the
same RequirementItem shape tier 1 uses) - never the PlantedMutation,
never which one was revised - so it cannot "remember the exam answers."

Requires a real ANTHROPIC_API_KEY in .env - without one this honestly
reports SKIPPED rather than fabricating a result.

CLAUDE-P19: `run_tier()` is this tier's entry point for tools/self_test_
runner.py's cross-tier regression runner - see tools/self_test_lab.py's
own docstring for the convention. `main()` is a thin wrapper so
standalone hand-running is unchanged:

    venv/Scripts/python.exe tools/self_test_lab_002_cross_document.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / ".env", override=True)

from services.bhive_parser import BHiveParser, CONSISTENCY_PROMPT_VERSION, RequirementItem  # noqa: E402
from services.case_workspace import CaseWorkspaceStore  # noqa: E402
from tests.self_test.evaluator import evaluate  # noqa: E402
from tests.self_test.golden_corpus_cross_document import (  # noqa: E402
    build_cross_document_golden_project,
)
from tests.self_test.mutation_schema import DIFFICULTY_TIER_CROSS_DOCUMENT  # noqa: E402
from tests.self_test.mutations_cross_document import apply_cross_document_inconsistency  # noqa: E402
from tests.self_test.run_record import SpecimenResult  # noqa: E402

CORPUS_VERSION = "1.0"
MUTATION_VERSION = "1.0"
PRODUCTION_REASONING_PATH = "BHiveParser._check_consistency"


def as_requirement_items(workspace, requirement_ids: list[str]) -> list[RequirementItem]:
    """
    The investigator's-eye view: id + text only, re-read FRESH from the
    real workspace each time (so a post-mutation call sees the real
    post-Supersession text_reference, not a cached copy) - a placeholder
    category/confidence/source_line since the consistency prompt itself
    never uses those fields (see bhive_parser._build_consistency_prompt),
    only id/category/text.
    """
    by_id = {r["id"]: r for r in workspace.requirements}
    return [
        RequirementItem(
            id=req_id, text=by_id[req_id]["text_reference"], category="technical_specification",
            confidence=0.9, source_line=0,
        )
        for req_id in requirement_ids
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


def run_tier() -> list[SpecimenResult]:
    specimens: list[SpecimenResult] = []
    model = BHiveParser().model
    tmp_dir = Path(tempfile.mkdtemp(prefix="self_test_lab_cross_document_"))
    try:
        store = CaseWorkspaceStore(tmp_dir)
        project = build_cross_document_golden_project(
            store, project_id="cross-document-golden", sources_dir=tmp_dir / "sources",
        )
        workspace = project["workspace"]
        rfp_id = project["rfp_requirement_id"]
        appendix_id = project["appendix_requirement_id"]

        print("=== STAGE 1: clean two-Source corpus (should find nothing) ===")
        print(f"RFP requirement ({rfp_id}) <- Source {project['rfp_source_id']}")
        print(f"Appendix requirement ({appendix_id}) <- Source {project['appendix_source_id']}")
        start = time.perf_counter()
        clean_flags = run_consistency_check(as_requirement_items(workspace, [rfp_id, appendix_id]))
        elapsed = time.perf_counter() - start
        if clean_flags is None:
            specimens.append(SpecimenResult(
                tier_id=DIFFICULTY_TIER_CROSS_DOCUMENT, specimen_id="002-clean",
                description="Clean two-Source corpus (coordinated RFP + Appendix) - should find nothing.",
                production_reasoning_path=PRODUCTION_REASONING_PATH, corpus_version=CORPUS_VERSION,
                model=model, prompt_version=CONSISTENCY_PROMPT_VERSION,
                ran=False, skipped_reason="No ANTHROPIC_API_KEY configured, or consistency check did not run.",
            ))
            return specimens
        print(f"Flags raised on the clean corpus: {len(clean_flags)}")
        for flag in clean_flags:
            print(f"  - ({flag.requirement_a_id}, {flag.requirement_b_id}): {flag.explanation}")
        if clean_flags:
            print("NOTE: the corpus wasn't actually clean, or Archiosk manufactured a discrepancy - review needed.")
        else:
            print("PASS: Archiosk found the two coordinated Sources consistent.")
        specimens.append(SpecimenResult(
            tier_id=DIFFICULTY_TIER_CROSS_DOCUMENT, specimen_id="002-clean",
            description="Clean two-Source corpus (coordinated RFP + Appendix) - should find nothing.",
            production_reasoning_path=PRODUCTION_REASONING_PATH, corpus_version=CORPUS_VERSION,
            expected_anchors=[rfp_id, appendix_id], model=model, prompt_version=CONSISTENCY_PROMPT_VERSION,
            false_positives=[f.explanation for f in clean_flags],
            model_call_count=1, latency_seconds=elapsed,
        ))

        print("\n=== STAGE 2: Appendix revised 96h -> 72h (RFP untouched) ===")
        answer_key = apply_cross_document_inconsistency(store, workspace, rfp_id, appendix_id)
        workspace = store.get(workspace.project_id)  # re-fetch post-revision state
        print(f"Planted: {answer_key.mutation_id} ({answer_key.difficulty_tier}) - {answer_key.description}")
        print(
            f"Appendix requirement id changed on revision: {appendix_id} (superseded, frozen at 96h) "
            f"-> {answer_key.secondary_location} (current, 72h)"
        )

        start = time.perf_counter()
        mutated_flags = run_consistency_check(
            as_requirement_items(workspace, [rfp_id, answer_key.secondary_location])
        )
        elapsed = time.perf_counter() - start
        if mutated_flags is None:
            specimens.append(SpecimenResult(
                tier_id=DIFFICULTY_TIER_CROSS_DOCUMENT, specimen_id=answer_key.mutation_id,
                description=answer_key.description, production_reasoning_path=PRODUCTION_REASONING_PATH,
                corpus_version=CORPUS_VERSION, mutation_version=MUTATION_VERSION,
                planted_condition=answer_key.description, expected_detection_type=answer_key.mutation_kind,
                expected_anchors=[rfp_id, answer_key.secondary_location], expected_non_findings=answer_key.non_defects,
                model=model, prompt_version=CONSISTENCY_PROMPT_VERSION,
                ran=False, skipped_reason="No ANTHROPIC_API_KEY configured, or consistency check did not run.",
            ))
            return specimens

        result = evaluate(flags=mutated_flags, answer_key=[answer_key])
        print(f"Flags raised: {len(mutated_flags)}")
        for flag in mutated_flags:
            print(f"  - ({flag.requirement_a_id}, {flag.requirement_b_id}): {flag.explanation}")
        print(f"\nResult: {result.summary()}")
        if result.caught:
            print("PASS: the planted cross-document discrepancy was caught.")
        if result.both_anchors_correct:
            print("PASS: both real anchors (RFP Section 4.2 and Appendix C) were correctly named.")
        elif result.caught:
            print("PARTIAL: the discrepancy was caught, but not both anchors were correctly named.")
        if result.missed:
            print("FAIL: the planted cross-document discrepancy was missed.")
        if result.confirmed_false_positives:
            print("NOTE: raised a flag matching a declared non-defect - a real false positive.")
        if result.unplanted_and_unexplained:
            print(
                "NOTE: raised a flag with no answer-key match - needs human judgment: "
                "hallucination, or a genuine discovery this corpus's author didn't anticipate."
            )

        original_appendix = next((r for r in workspace.requirements if r["id"] == appendix_id), None)
        original_intact = (
            original_appendix is not None
            and original_appendix["status"] == "superseded"
            and "96 hours" in original_appendix["text_reference"]
        )
        print(f"\nOriginal Appendix wording (96h) still intact and reconstructable via Supersession: {original_intact}")

        specimens.append(SpecimenResult(
            tier_id=DIFFICULTY_TIER_CROSS_DOCUMENT, specimen_id=answer_key.mutation_id,
            description=answer_key.description, production_reasoning_path=PRODUCTION_REASONING_PATH,
            corpus_version=CORPUS_VERSION, mutation_version=MUTATION_VERSION,
            planted_condition=answer_key.description, expected_detection_type=answer_key.mutation_kind,
            expected_anchors=[rfp_id, answer_key.secondary_location], expected_non_findings=answer_key.non_defects,
            model=model, prompt_version=CONSISTENCY_PROMPT_VERSION,
            caught=bool(result.caught), anchor_correctness=bool(result.both_anchors_correct) if result.caught else None,
            false_positives=result.confirmed_false_positives, unexpected_valid_discoveries=result.unplanted_and_unexplained,
            model_call_count=1, latency_seconds=elapsed,
        ))
        return specimens
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main() -> int:
    specimens = run_tier()
    verdicts = [s.passed() for s in specimens]
    if not specimens or all(v is None for v in verdicts):
        return 1
    return 0 if all(v is not False for v in verdicts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
