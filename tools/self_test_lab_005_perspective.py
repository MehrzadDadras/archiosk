"""
CLAUDE-P17 self-test laboratory, tier 5: perspective-sensitive risk and
opportunity.

A TEST/LAB script (same status as the prior self_test_lab_*.py scripts)
- makes REAL, billed Anthropic calls, never run automatically by the test
suite.

The question this tier answers: can Archiosk preserve ONE canonical
contractual truth while producing legitimately different risk/
opportunity interpretations depending on who the user represents. The
governed evidence given to the model is IDENTICAL for every perspective
asked about it - the only variable is the represented_party dict passed
to services/requirement_investigation.py's real, existing (CLAUDE-P12R)
extension. No test-only flag ever tells the investigator which polarity
it's "supposed" to produce; grading happens afterward, against the
model's own returned polarity/confidence fields, using tests/self_test/
golden_corpus_perspective.py's PERSPECTIVE_EXPECTATIONS.

Requires a real ANTHROPIC_API_KEY in .env - without one this honestly
reports SKIPPED rather than fabricating a result.

Case C is graded partly qualitatively: two earlier real runs against two
different drafts of its clause both surfaced a genuine, independently-
reasoned secondary risk for whichever party wasn't the "opportunity"
subject (see golden_corpus_perspective.py's own comment on this) - real
means-and-methods discretion clauses rarely produce a perfectly one-sided
outcome once examined closely, so only "DB reads as opportunity" is a
hard check; Owner's reasoning is printed for a human to judge whether any
secondary finding is independently grounded or merely mirrors DB's gain.

CLAUDE-P19: `run_tier()` is this tier's entry point for tools/self_test_
runner.py's cross-tier regression runner - see tools/self_test_lab.py's
own docstring for the convention. `main()` is a thin wrapper so
standalone hand-running is unchanged. None of this tier's grading fits
the other tiers' "caught a planted defect" shape - see run_record.py's
own docstring on why `caught` is deliberately reused generically here for
"the expected differentiated pattern held," and why Case E's honesty
check maps onto `uncertainty_handling` instead.

Run:
    venv/Scripts/python.exe tools/self_test_lab_005_perspective.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(REPO_ROOT / ".env", override=True)

from services.case_workspace import (  # noqa: E402
    KNOWN_PERSPECTIVE_POLARITIES,
    OBJECT_KIND_REQUIREMENT,
    PERSPECTIVE_ORIGIN_HUMAN,
    PERSPECTIVE_ORIGIN_MACHINE,
    PERSPECTIVE_POLARITY_RISK,
    CaseWorkspaceStore,
)
from services.requirement_investigation import INVESTIGATION_PROMPT_VERSION, investigate_requirement  # noqa: E402
from tests.self_test.golden_corpus_perspective import (  # noqa: E402
    PERSPECTIVE_EXPECTATIONS,
    build_perspective_golden_corpus,
)
from tests.self_test.mutation_schema import DIFFICULTY_TIER_PERSPECTIVE_SENSITIVE  # noqa: E402
from tests.self_test.run_record import SpecimenResult  # noqa: E402

CORPUS_VERSION = "1.0"
PRODUCTION_REASONING_PATH = "requirement_investigation.investigate_requirement"
EMPTY_EVIDENCE = {"findings": [], "relationships": [], "accepted_knowledge": []}


def ask(requirement: dict, participant: dict, question: str):
    return investigate_requirement(
        question=question, requirement=requirement, adjudication_history=[],
        evidence=EMPTY_EVIDENCE, represented_party=participant,
    )


def describe(label: str, result) -> None:
    if not result.ran:
        print(f"  {label}: SKIPPED ({result.skipped_reason})")
        return
    print(
        f"  {label}: polarity={result.risk_polarity} confidence={result.risk_confidence} "
        f"needs_human_judgment={result.needs_human_judgment}"
    )
    print(f"    reasoning: {result.risk_reasoning}")


def run_tier() -> list[SpecimenResult]:  # noqa: C901 - one lab script tier, kept linear on purpose
    specimens: list[SpecimenResult] = []
    tmp_dir = Path(tempfile.mkdtemp(prefix="self_test_lab_perspective_"))
    try:
        store = CaseWorkspaceStore(tmp_dir)
        corpus = build_perspective_golden_corpus(store, "perspective-golden", tmp_dir / "sources")
        workspace = corpus["workspace"]
        owner, db = corpus["owner"], corpus["design_builder"]
        question = "How should this be understood in terms of risk and opportunity for the party I represent?"

        def req(rid: str) -> dict:
            return next(r for r in workspace.requirements if r["id"] == rid)

        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

        def specimen(specimen_id, description, **kwargs) -> SpecimenResult:
            return SpecimenResult(
                tier_id=DIFFICULTY_TIER_PERSPECTIVE_SENSITIVE, specimen_id=specimen_id, description=description,
                production_reasoning_path=PRODUCTION_REASONING_PATH, corpus_version=CORPUS_VERSION,
                model=model, prompt_version=INVESTIGATION_PROMPT_VERSION, **kwargs,
            )

        print("=== CASE A: explicit risk transfer ===")
        r = req(corpus["risk_transfer_id"])
        start = time.perf_counter()
        result_owner_a = ask(r, owner, question)
        if not result_owner_a.ran:
            print(f"SKIPPED: {result_owner_a.skipped_reason}")
            specimens.append(specimen(
                "005A-risk-transfer", "Explicit risk transfer clause - DB accepts exposure, Owner is relieved.",
                expected_anchors=[corpus["risk_transfer_id"]], ran=False, skipped_reason=result_owner_a.skipped_reason,
            ))
            return specimens
        result_db_a = ask(r, db, question)
        elapsed = time.perf_counter() - start
        describe("Owner", result_owner_a)
        describe("Design-Builder", result_db_a)
        exp = PERSPECTIVE_EXPECTATIONS["risk_transfer"]
        ok_a = (
            result_db_a.risk_polarity == exp["design_builder_must_be"]
            and result_owner_a.risk_polarity != exp["owner_must_not_be"]
        )
        print("PASS" if ok_a else "FAIL", "- DB must be 'risk', Owner must not be 'risk'.")
        same_text = req(corpus["risk_transfer_id"])["text_reference"] == r["text_reference"]
        print(f"Same canonical text preserved across both calls: {same_text}")
        specimens.append(specimen(
            "005A-risk-transfer", "Explicit risk transfer clause - DB accepts exposure, Owner is relieved.",
            expected_anchors=[corpus["risk_transfer_id"]], caught=bool(ok_a and same_text),
            false_positives=[] if same_text else ["canonical text diverged across perspective calls"],
            model_call_count=2, latency_seconds=elapsed,
        ))

        print("\n=== CASE B: risk is not automatically zero-sum ===")
        r = req(corpus["shared_risk_id"])
        start = time.perf_counter()
        result_owner_b = ask(r, owner, question)
        result_db_b = ask(r, db, question)
        elapsed = time.perf_counter() - start
        describe("Owner", result_owner_b)
        describe("Design-Builder", result_db_b)
        exp = PERSPECTIVE_EXPECTATIONS["shared_risk"]
        ok_b = result_owner_b.risk_polarity == exp["owner_must_be"] and result_db_b.risk_polarity == exp["design_builder_must_be"]
        print("PASS" if ok_b else "FAIL", "- both parties must read as 'risk' (for different reasons).")
        specimens.append(specimen(
            "005B-shared-risk", "Genuine, non-zero-sum shared exposure for different reasons.",
            expected_anchors=[corpus["shared_risk_id"]], caught=bool(ok_b), model_call_count=2, latency_seconds=elapsed,
        ))

        print("\n=== CASE C: opportunity without corresponding harm ===")
        r = req(corpus["opportunity_id"])
        start = time.perf_counter()
        result_owner_c = ask(r, owner, question)
        result_db_c = ask(r, db, question)
        elapsed = time.perf_counter() - start
        describe("Owner", result_owner_c)
        describe("Design-Builder", result_db_c)
        exp = PERSPECTIVE_EXPECTATIONS["opportunity"]
        ok_c = result_db_c.risk_polarity != exp["design_builder_must_not_be"]
        print("PASS" if ok_c else "FAIL", "- DB must not be forced into 'risk' (hard check).")
        print(
            "NOTE: Owner's polarity here is graded QUALITATIVELY, not auto-checked - a real "
            "secondary risk finding for the Owner is legitimate if independently reasoned from "
            "the clause's own text (e.g. an oversight/control gap), illegitimate only if it is "
            "derived by mirroring the Design-Builder's opportunity ('DB benefits, so Owner must "
            "lose'). Read Owner's reasoning above and judge which one this is."
        )
        specimens.append(specimen(
            "005C-opportunity-without-harm", "DB gets means/methods flexibility; Owner's performance requirement stays protected.",
            expected_anchors=[corpus["opportunity_id"]], caught=bool(ok_c),
            qualitative_note=f"Owner read (needs human judgment - independent finding vs. zero-sum mirroring): {result_owner_c.risk_reasoning}",
            model_call_count=2, latency_seconds=elapsed,
        ))

        print("\n=== CASE D: perspective-neutral (statutory/life-safety) obligation ===")
        r = req(corpus["statutory_id"])
        start = time.perf_counter()
        result_owner_d = ask(r, owner, question)
        result_db_d = ask(r, db, question)
        elapsed = time.perf_counter() - start
        describe("Owner", result_owner_d)
        describe("Design-Builder", result_db_d)
        exp = PERSPECTIVE_EXPECTATIONS["statutory"]
        ok_d = result_owner_d.risk_polarity != exp["neither_party_may_be"] and result_db_d.risk_polarity != exp["neither_party_may_be"]
        print(
            "PASS" if ok_d else "FAIL",
            "- neither party's position may recast a life-safety obligation as a commercial 'opportunity'.",
        )
        specimens.append(specimen(
            "005D-perspective-neutral-obligation", "Statutory/life-safety obligation - must never read as commercial opportunity for either party.",
            expected_anchors=[corpus["statutory_id"]], caught=bool(ok_d), model_call_count=2, latency_seconds=elapsed,
        ))

        print("\n=== CASE E: ambiguous allocation ===")
        r = req(corpus["ambiguous_id"])
        start = time.perf_counter()
        result_owner_e = ask(r, owner, question)
        result_db_e = ask(r, db, question)
        elapsed = time.perf_counter() - start
        describe("Owner", result_owner_e)
        describe("Design-Builder", result_db_e)
        both_confident_and_opposite = (
            (result_owner_e.risk_confidence or 0) > 0.7
            and (result_db_e.risk_confidence or 0) > 0.7
            and result_owner_e.risk_polarity != result_db_e.risk_polarity
        )
        ok_e = not both_confident_and_opposite
        print(
            "PASS" if ok_e else "FAIL",
            "- must not confidently manufacture opposite answers for genuinely unresolved allocation.",
        )
        specimens.append(specimen(
            "005E-ambiguous-allocation", "Allocation genuinely unresolved by the governed evidence.",
            expected_anchors=[corpus["ambiguous_id"]], uncertainty_handling=bool(ok_e),
            model_call_count=2, latency_seconds=elapsed,
        ))

        print("\n=== CASE F: human/machine convergence and preserved disagreement ===")
        db_anchor = {"anchor_type": OBJECT_KIND_REQUIREMENT, "anchor_id": corpus["risk_transfer_id"]}
        store.record_perspective_assessment(
            workspace, anchor=db_anchor, participant_id=db["id"],
            polarity=result_db_a.risk_polarity, origin=PERSPECTIVE_ORIGIN_HUMAN,
            reasoning="Reviewed independently; concur with the machine's read of this transfer clause.",
            recorded_by="self-test-lab-reviewer",
        )
        store.record_perspective_assessment(
            workspace, anchor=db_anchor, participant_id=db["id"],
            polarity=result_db_a.risk_polarity, origin=PERSPECTIVE_ORIGIN_MACHINE,
            reasoning=result_db_a.risk_reasoning or result_db_a.assessment,
            confidence=result_db_a.risk_confidence,
        )
        convergence = store.perspective_convergence_for(workspace, OBJECT_KIND_REQUIREMENT, corpus["risk_transfer_id"], db["id"])
        print(f"Convergence (Case A, DB): agree={convergence['agree']}")
        ok_f1 = convergence["agree"] is True
        specimens.append(specimen(
            "005F1-human-machine-convergence", "Human and machine PerspectiveAssessment agree on the same anchor+participant.",
            expected_anchors=[corpus["risk_transfer_id"]], caught=bool(ok_f1), model_call_count=0,
        ))

        opposite_polarity = next(p for p in KNOWN_PERSPECTIVE_POLARITIES if p != result_db_c.risk_polarity)
        db_c_anchor = {"anchor_type": OBJECT_KIND_REQUIREMENT, "anchor_id": corpus["opportunity_id"]}
        store.record_perspective_assessment(
            workspace, anchor=db_c_anchor, participant_id=db["id"],
            polarity=opposite_polarity, origin=PERSPECTIVE_ORIGIN_HUMAN,
            reasoning="Reviewed independently; I read this differently from the machine's assessment.",
            recorded_by="self-test-lab-reviewer",
        )
        store.record_perspective_assessment(
            workspace, anchor=db_c_anchor, participant_id=db["id"],
            polarity=result_db_c.risk_polarity, origin=PERSPECTIVE_ORIGIN_MACHINE,
            reasoning=result_db_c.risk_reasoning or result_db_c.assessment,
            confidence=result_db_c.risk_confidence,
        )
        disagreement = store.perspective_convergence_for(workspace, OBJECT_KIND_REQUIREMENT, corpus["opportunity_id"], db["id"])
        print(f"Disagreement (Case C, DB): agree={disagreement['agree']}")
        records = store.perspective_assessments_for_anchor(workspace, OBJECT_KIND_REQUIREMENT, corpus["opportunity_id"], db["id"])
        both_preserved = len(records) == 2
        print(f"Both human and machine records preserved (neither overwrote the other): {both_preserved}")
        ok_f2 = disagreement["agree"] is False and both_preserved
        print("PASS" if (ok_f1 and ok_f2) else "FAIL", "- convergence and disagreement both computed honestly, no overwrite.")
        specimens.append(specimen(
            "005F2-human-machine-disagreement", "Human and machine PerspectiveAssessment genuinely disagree - both preserved, neither overwritten.",
            expected_anchors=[corpus["opportunity_id"]], caught=bool(ok_f2), model_call_count=0,
        ))

        print("\n=== PERSPECTIVE LEAKAGE: same clause, consecutive Owner then Design-Builder ===")
        r = req(corpus["risk_transfer_id"])
        text_before = r["text_reference"]
        start = time.perf_counter()
        leak_owner = ask(r, owner, question)
        leak_db = ask(r, db, question)
        elapsed = time.perf_counter() - start
        text_after = req(corpus["risk_transfer_id"])["text_reference"]
        no_leakage = (
            leak_db.risk_polarity == PERSPECTIVE_POLARITY_RISK
            and leak_owner.risk_polarity != PERSPECTIVE_POLARITY_RISK
            and text_before == text_after
        )
        print(f"Owner (run first): polarity={leak_owner.risk_polarity}")
        print(f"Design-Builder (run second, same clause): polarity={leak_db.risk_polarity}")
        print(f"Canonical text unchanged by either call: {text_before == text_after}")
        print("PASS" if no_leakage else "FAIL", "- second call must not inherit the first party's conclusion.")
        specimens.append(specimen(
            "005-leakage", "Same clause, consecutive Owner-then-Design-Builder calls - no inherited conclusions.",
            expected_anchors=[corpus["risk_transfer_id"]], caught=bool(no_leakage),
            model_call_count=2, latency_seconds=elapsed,
        ))

        return specimens
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main() -> int:
    specimens = run_tier()
    verdicts = [s.passed() for s in specimens]
    all_ok = bool(specimens) and all(v is not False for v in verdicts)
    print(f"\n=== OVERALL: {'PASS' if all_ok else 'FAIL'} ===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
