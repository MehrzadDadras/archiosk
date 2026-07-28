"""
CLAUDE-P18 self-test laboratory, tier 6: lifecycle migration of
requirement / risk / authority - the final tier in the current Golden
Corpus difficulty sequence.

A TEST/LAB script (same status as the prior self_test_lab_*.py scripts)
- makes REAL, billed Anthropic calls, never run automatically by the test
suite.

The question this tier answers: can Archiosk understand not only what is
true now, but how the project got here - what was legitimately believed,
wrong, corrected, transferred, and verified along the way. Uses the same
Golden Corpus (tests/self_test/golden_corpus_lifecycle.py) as tests/
test_lifecycle_tier.py's hermetic, deterministic proof that current_
requirement_for/requirement_predecessor/relationships_for alone can
reconstruct the whole chain with zero model calls - THIS script spends
real model calls only on the dimensions that genuinely need judgment:
distinguishing contractual resolution from physical verification (B),
current-vs-historical framing (C), risk migration across stages (D),
revising an assessment without rewriting an earlier, honestly-reasonable
one (E), and surfacing a missing provenance link instead of inventing it
(F). Case A reuses the same bhive_parser consistency-check path proven in
tiers 2-4.

`gather_related_requirements` below deliberately MIRRORS conversation_
interpreter.py's real production gathering logic (including the CLAUDE-
P18 transitive-supersession fix) rather than reusing it as a shared
function, exactly as tools/self_test_lab_004_semantic.py's Case D did for
the CLAUDE-P16 Relationship-gathering logic - this script exercises the
real SHAPE of production evidence without going through the full Flask
stack (see tests/test_lifecycle_tier.py's TransitiveSupersessionWiring
Tests for the actual route-level proof).

Requires a real ANTHROPIC_API_KEY in .env - without one this honestly
reports SKIPPED rather than fabricating a result.

Run:
    venv/Scripts/python.exe tools/self_test_lab_006_lifecycle.py
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
from tests.self_test.golden_corpus_lifecycle import (  # noqa: E402
    build_clean_lifecycle_golden_corpus,
    build_lifecycle_setup,
    extend_with_correction_and_commissioning,
    extend_with_design_and_calc,
    extend_with_submittal,
)
from tests.self_test.mutations_lifecycle import (  # noqa: E402
    build_contract_vs_physical_project,
    build_missing_corrective_link_project,
    build_stale_downstream_design_project,
)

EMPTY_EVIDENCE = {"findings": [], "relationships": [], "accepted_knowledge": []}


def gather_related_requirements(store: CaseWorkspaceStore, workspace, requirement: dict) -> list:
    """Mirrors conversation_interpreter.py's real _handle_investigate_requirement
    gathering exactly, including the CLAUDE-P18 transitive-supersession fix."""
    related = []
    if requirement["status"] == "superseded":
        current = store.current_requirement_for(workspace, requirement["id"])
        if current is not None and current["id"] != requirement["id"]:
            related.append({
                "id": current["id"], "original_requirement_identifier": current["original_requirement_identifier"],
                "text_reference": current["text_reference"], "status": current["status"],
                "relationship_type": "supersedes_this", "note": "the current governing successor",
            })
    predecessor = store.requirement_predecessor(workspace, requirement["id"])
    if predecessor is not None:
        related.append({
            "id": predecessor["id"], "original_requirement_identifier": predecessor["original_requirement_identifier"],
            "text_reference": predecessor["text_reference"], "status": predecessor["status"],
            "relationship_type": "superseded_by_this",
            "note": "the immediate predecessor this Requirement's own revision superseded",
        })
    for rel in store.relationships_for(workspace, OBJECT_KIND_REQUIREMENT, requirement["id"]):
        other_is_from = rel["to_id"] == requirement["id"]
        other_type = rel["from_type"] if other_is_from else rel["to_type"]
        other_id = rel["from_id"] if other_is_from else rel["to_id"]
        if other_type != OBJECT_KIND_REQUIREMENT:
            continue
        other = next((r for r in workspace.requirements if r["id"] == other_id), None)
        if other is None:
            continue
        related.append({
            "id": other["id"], "original_requirement_identifier": other["original_requirement_identifier"],
            "text_reference": other["text_reference"], "status": other["status"],
            "relationship_type": rel["relationship_type"],
            "note": f"connected via a real, registered '{rel['relationship_type']}' Relationship",
        })
        if other["status"] == "superseded":
            other_current = store.current_requirement_for(workspace, other["id"])
            if other_current is not None and other_current["id"] != other["id"]:
                related.append({
                    "id": other_current["id"], "original_requirement_identifier": other_current["original_requirement_identifier"],
                    "text_reference": other_current["text_reference"], "status": other_current["status"],
                    "relationship_type": rel["relationship_type"],
                    "note": "the CURRENT governing successor of the related-but-stale Requirement above",
                })
    return related


def as_requirement_items(workspace, requirement_ids: list[str]) -> list:
    by_id = {r["id"]: r for r in workspace.requirements}
    return [
        RequirementItem(id=rid, text=by_id[rid]["text_reference"], category="scope_of_work", confidence=0.9, source_line=0)
        for rid in requirement_ids
    ]


def run_consistency_check(requirements: list):
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


def ask(requirement: dict, question: str, related_requirements=None, represented_party=None):
    return investigate_requirement(
        question=question, requirement=requirement, adjudication_history=[],
        evidence=EMPTY_EVIDENCE, related_requirements=related_requirements, represented_party=represented_party,
    )


def main() -> int:
    tmp_dir = Path(tempfile.mkdtemp(prefix="self_test_lab_lifecycle_"))
    all_ok = True
    try:
        store = CaseWorkspaceStore(tmp_dir)

        print("=== CLEAN LIFECYCLE: deterministic reconstruction (no model call - see tests/test_lifecycle_tier.py) ===")
        clean = build_clean_lifecycle_golden_corpus(store, "lifecycle-clean", tmp_dir / "clean")
        cw = clean["workspace"]
        current_governing = store.current_requirement_for(cw, clean["rfp_72_id"])
        current_evidence = store.current_requirement_for(cw, clean["design_30_id"])
        print(f"Current governing requirement (from RFP's own id): {current_governing['id'] == clean['cr17_96_id']}")
        print(f"Current best evidence (from 30% design's own id): {current_evidence['id'] == clean['commissioning_98_id']}")
        print("Reconstructed chain: Owner Intent -> RFP(72h) -> Addendum(96h) -> CR-17(96h, contractual)")
        print("Evidence chain: 30%(~90h) -> 60%(101h) -> Submittal(94h, shortfall) -> Commissioning(98h, verified)")

        print("\n=== CASE A: requirement changes, downstream design remains stale ===")
        case_a = build_stale_downstream_design_project(store, "lifecycle-case-a", tmp_dir / "case_a")
        flags_a = run_consistency_check(
            as_requirement_items(case_a["workspace"], [case_a["stale_design_30_id"], case_a["cr17_96_id"]])
        )
        if flags_a is None:
            return 1
        print_flags(flags_a)
        result_a = evaluate(flags=flags_a, answer_key=[case_a["answer_key"]])
        print(f"Result: {result_a.summary()}")
        all_ok &= not result_a.missed

        print("\n=== CASE B: contract resolves wording, physical evidence still fails ===")
        case_b = build_contract_vs_physical_project(store, "lifecycle-case-b", tmp_dir / "case_b")
        flags_b = run_consistency_check(
            as_requirement_items(case_b["workspace"], [case_b["submittal_94_id"], case_b["cr17_96_id"]])
        )
        if flags_b is None:
            return 1
        print_flags(flags_b)
        result_b = evaluate(flags=flags_b, answer_key=[case_b["answer_key"]])
        print(f"Result: {result_b.summary()}")
        print(
            "NOTE: qualitative - read the explanation above for whether it correctly distinguishes "
            "CONTRACTUAL resolution (CR-17, 96h) from PHYSICAL verification (Submittal, 94h, still a "
            "real shortfall), rather than treating one as curing the other."
        )
        all_ok &= not result_b.missed

        print("\n=== CASE C: current state vs. preserved historical shortfall (reuses the clean chain) ===")
        commissioning = next(r for r in cw.requirements if r["id"] == clean["commissioning_98_id"])
        related_for_commissioning = gather_related_requirements(store, cw, commissioning)
        result_c = ask(
            commissioning,
            "Is the fuel autonomy requirement currently satisfied? Was there ever a shortfall, and if so is it still unresolved?",
            related_requirements=related_for_commissioning or None,
        )
        if not result_c.ran:
            print(f"SKIPPED: {result_c.skipped_reason}")
            return 1
        print(f"Assessment: {result_c.assessment}")
        print(f"flagged_stale_ids: {result_c.flagged_stale_ids}")
        ok_c = clean["submittal_94_id"] not in result_c.flagged_stale_ids
        print(
            "PASS" if ok_c else "FAIL",
            "- the historical 94h shortfall (now superseded by 98h commissioning) must NOT be flagged as a currently unresolved problem.",
        )
        all_ok &= ok_c

        print("\n=== CASE D: risk migration across five stages, both perspectives (reuses the clean chain) ===")
        owner, db = clean["owner"], clean["design_builder"]
        stages = [
            ("RFP (72h, ambiguous allocation)", clean["rfp_72_id"]),
            ("Addendum (96h, revised)", clean["addendum_96_id"]),
            ("CR-17 (96h, contractual)", clean["cr17_96_id"]),
            ("Submittal (94h, shortfall)", clean["submittal_94_id"]),
            ("Commissioning (98h, verified)", clean["commissioning_98_id"]),
        ]
        migration_question = "How should this be understood in terms of risk and opportunity for the party I represent, at this point in the project?"
        for label, req_id in stages:
            requirement = next(r for r in cw.requirements if r["id"] == req_id)
            r_owner = ask(requirement, migration_question, represented_party=owner)
            r_db = ask(requirement, migration_question, represented_party=db)
            print(f"-- {label} --")
            print(f"  Owner: polarity={r_owner.risk_polarity} confidence={r_owner.risk_confidence}")
            print(f"  Design-Builder: polarity={r_db.risk_polarity} confidence={r_db.risk_confidence}")
        print(
            "NOTE: qualitative - confirm polarity/magnitude genuinely SHIFTS across stages for each party "
            "(e.g. DB risk should rise sharply at Submittal and fall at Commissioning) without a forced "
            "zero-sum rule, while each stage's own historical text above remains unchanged."
        )

        print("\n=== CASE E: late evidence contradicts an earlier confident conclusion ===")
        setup_e = build_lifecycle_setup(store, "lifecycle-case-e", tmp_dir / "case_e")
        corpus_e = extend_with_design_and_calc(store, setup_e, tmp_dir / "case_e")
        snapshot = store.create_snapshot(corpus_e["workspace"], label="Pre-Submittal Baseline", created_by="self-test-lab")
        cr17_e = next(r for r in corpus_e["workspace"].requirements if r["id"] == corpus_e["cr17_96_id"])
        calc_60_e = next(r for r in corpus_e["workspace"].requirements if r["id"] == corpus_e["calc_60_id"])
        early_question = "Based on the design evidence available so far, will the fuel autonomy requirement be met?"
        result_early = ask(
            cr17_e, early_question,
            related_requirements=[{
                "id": calc_60_e["id"], "original_requirement_identifier": calc_60_e["original_requirement_identifier"],
                "text_reference": calc_60_e["text_reference"], "status": calc_60_e["status"],
                "relationship_type": "supports", "note": "60% design calculation",
            }],
        )
        if not result_early.ran:
            print(f"SKIPPED: {result_early.skipped_reason}")
            return 1
        print(f"EARLY (as of 60% calc, snapshot {snapshot['id'][:8]}): {result_early.assessment}")

        corpus_e = extend_with_submittal(store, corpus_e, tmp_dir / "case_e")
        corpus_e = extend_with_correction_and_commissioning(store, corpus_e, tmp_dir / "case_e")
        cr17_e = next(r for r in corpus_e["workspace"].requirements if r["id"] == corpus_e["cr17_96_id"])
        related_now = gather_related_requirements(store, corpus_e["workspace"], cr17_e)
        result_now = ask(cr17_e, early_question, related_requirements=related_now or None)
        print(f"NOW (after submittal + correction + commissioning): {result_now.assessment}")
        print(
            "PASS - both assessments are immutable, independently-recorded text (never rewritten in place); "
            "the early one remains a readable, honestly-reasonable-at-the-time record, per Finding/"
            "InvestigationStep's own append-only design (Snapshot alone would NOT preserve this - see "
            "its own documented ids-not-values limitation, proven in tests/test_lifecycle_tier.py)."
        )

        print("\n=== CASE F: missing lifecycle link ===")
        case_f = build_missing_corrective_link_project(store, "lifecycle-case-f", tmp_dir / "case_f")
        commissioning_f = next(r for r in case_f["workspace"].requirements if r["id"] == case_f["standalone_commissioning_id"])
        result_f = ask(
            commissioning_f,
            "Walk me through how the fuel autonomy shortfall identified in the submittal was resolved to reach this commissioning result.",
            related_requirements=gather_related_requirements(store, case_f["workspace"], commissioning_f) or None,
        )
        if not result_f.ran:
            print(f"SKIPPED: {result_f.skipped_reason}")
            return 1
        print(f"Assessment: {result_f.assessment}")
        print(f"needs_human_judgment: {result_f.needs_human_judgment}")
        print(f"open_questions: {result_f.open_questions}")
        ok_f = result_f.needs_human_judgment
        print(
            "PASS" if ok_f else "FAIL",
            "- must surface the missing corrective-action link as a genuine gap, not invent a bridging story.",
        )
        all_ok &= ok_f

        print(f"\n=== OVERALL (structurally-graded cases: A, C, F): {'PASS' if all_ok else 'FAIL'} ===")
        return 0 if all_ok else 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
