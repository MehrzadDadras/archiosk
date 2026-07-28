"""
CLAUDE-P15 self-test laboratory, tier 3: supersession / Addendum
authority.

A TEST/LAB script (same status as tools/self_test_lab.py and
tools/self_test_lab_002_cross_document.py) - makes REAL, billed
Anthropic calls, never run automatically by the test suite.

The question this tier answers is deeper than tiers 1-2: not "do these
texts differ" but "which statement currently governs, and does a
downstream reference correctly track it." This requires the
investigator to actually see governance status - a real gap in
services/requirement_investigation.py that this tier closes as a real
capability (Requirement.status is now always stated in the prompt; an
optional `related_requirements` list lets the model compare against
other real, status-tagged Requirements), not something faked for this
test alone.

Design: always investigate the CURRENT (active) RFP requirement, with
`related_requirements` = [the original superseded predecessor, the
downstream Appendix]. This single call structure tests Case A (a stale
ACTIVE downstream reference should be flagged) and Case B (the
superseded HISTORICAL predecessor must never be flagged merely for
disagreeing with what superseded it) together, in every run - including
the harder version of Case B, where something else genuinely IS wrong
and the historical record must still be correctly set aside.

Case C (partial supersession of a compound requirement) is graded
qualitatively, not by structured id-matching - "does clause (b) still
govern" is a real reasoning question, not a contradiction-detection one.

Requires a real ANTHROPIC_API_KEY in .env - without one this honestly
reports SKIPPED rather than fabricating a result.

Run:
    venv/Scripts/python.exe tools/self_test_lab_003_supersession.py
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

from services.case_workspace import CaseWorkspaceStore  # noqa: E402
from services.requirement_investigation import investigate_requirement  # noqa: E402
from tests.self_test.golden_corpus_supersession import build_supersession_golden_project  # noqa: E402
from tests.self_test.mutations_supersession import (  # noqa: E402
    build_partial_supersession_project,
    build_stale_downstream_project,
)

QUESTION = "Are all coordinated references to this Requirement's autonomy period currently consistent with what governs?"


def run_governance_check(workspace, current_id, original_id, appendix_id):
    """Investigates the CURRENT RFP requirement with the original
    (superseded) predecessor and the downstream Appendix as related
    requirements - real Requirement dicts, real status fields, fetched
    fresh each time so a re-run after a mutation sees real current state."""
    by_id = {r["id"]: r for r in workspace.requirements}
    current = by_id[current_id]

    related_requirements = [
        {
            "id": original_id, "original_requirement_identifier": by_id[original_id]["original_requirement_identifier"],
            "text_reference": by_id[original_id]["text_reference"], "status": by_id[original_id]["status"],
            "note": "the predecessor this Requirement's Addendum superseded",
        },
        {
            "id": appendix_id, "original_requirement_identifier": by_id[appendix_id]["original_requirement_identifier"],
            "text_reference": by_id[appendix_id]["text_reference"], "status": by_id[appendix_id]["status"],
            "note": "a downstream Source meant to coordinate with this Requirement",
        },
    ]

    return investigate_requirement(
        question=QUESTION, requirement=current, adjudication_history=[],
        evidence={"findings": [], "relationships": [], "accepted_knowledge": []},
        related_requirements=related_requirements,
    )


def report(label: str, result, expected_stale_ids: set[str], appendix_id: str, original_id: str) -> bool:
    print(f"\n--- {label} ---")
    if not result.ran:
        print(f"SKIPPED: {result.skipped_reason}")
        return False
    print(f"Assessment: {result.assessment}")
    print(f"Flagged as stale: {result.flagged_stale_ids}")

    ok = True
    if set(result.flagged_stale_ids) == expected_stale_ids:
        print(f"PASS: flagged_stale_ids exactly matches expected {expected_stale_ids or '{}'}.")
    else:
        print(f"FAIL: expected flagged_stale_ids={expected_stale_ids or '{}'}, got {set(result.flagged_stale_ids)}.")
        ok = False

    if original_id in result.flagged_stale_ids:
        print("FAIL: flagged the SUPERSEDED historical predecessor as a live conflict - false conflict bait not resolved.")
        ok = False
    else:
        print("PASS: did not flag the superseded historical predecessor.")

    return ok


def main() -> int:
    tmp_dir = Path(tempfile.mkdtemp(prefix="self_test_lab_supersession_"))
    all_ok = True
    try:
        store = CaseWorkspaceStore(tmp_dir)

        print("=== SCENARIO 1: clean baseline (Addendum correctly coordinated) ===")
        clean = build_supersession_golden_project(store, "supersession-clean", tmp_dir / "clean")
        result = run_governance_check(
            clean["workspace"], clean["current_rfp_requirement_id"],
            clean["original_rfp_requirement_id"], clean["appendix_requirement_id"],
        )
        if not result.ran:
            print(f"SKIPPED: {result.skipped_reason}")
            return 1
        all_ok &= report(
            "Clean baseline (expect: nothing flagged - this is Case B too)", result,
            expected_stale_ids=set(), appendix_id=clean["appendix_requirement_id"],
            original_id=clean["original_rfp_requirement_id"],
        )

        print("\n=== SCENARIO A: stale downstream reference ===")
        stale = build_stale_downstream_project(store, "supersession-stale-downstream", tmp_dir / "stale")
        result_a = run_governance_check(
            stale["workspace"], stale["current_rfp_requirement_id"],
            stale["original_rfp_requirement_id"], stale["appendix_requirement_id"],
        )
        all_ok &= report(
            "Stale downstream reference (expect: Appendix flagged, historical RFP not)", result_a,
            expected_stale_ids={stale["appendix_requirement_id"]}, appendix_id=stale["appendix_requirement_id"],
            original_id=stale["original_rfp_requirement_id"],
        )

        print("\n=== SCENARIO C: partial supersession of a compound requirement (qualitative) ===")
        partial = build_partial_supersession_project(store, "supersession-partial", tmp_dir / "partial")
        workspace = partial["workspace"]
        current_requirement = next(r for r in workspace.requirements if r["id"] == partial["current_requirement_id"])
        original_requirement = next(r for r in workspace.requirements if r["id"] == partial["original_requirement_id"])
        result_c = investigate_requirement(
            question="What changed in this revision, and does the service-life commitment still apply?",
            requirement=current_requirement, adjudication_history=[],
            evidence={"findings": [], "relationships": [], "accepted_knowledge": []},
            related_requirements=[{
                "id": original_requirement["id"],
                "original_requirement_identifier": original_requirement["original_requirement_identifier"],
                "text_reference": original_requirement["text_reference"], "status": original_requirement["status"],
                "note": "the immediate predecessor this Requirement's Addendum superseded",
            }],
        )
        if not result_c.ran:
            print(f"SKIPPED: {result_c.skipped_reason}")
        else:
            print(f"Assessment: {result_c.assessment}")
            mentions_service_life = "50-year" in result_c.assessment or "service life" in result_c.assessment.lower()
            claims_whole_thing_superseded = "no longer" in result_c.assessment.lower() and "50-year" not in result_c.assessment
            print(f"Mentions the unchanged service-life commitment: {mentions_service_life}")
            print(
                "NOTE: this is a qualitative check, not an automated pass/fail - read the "
                "assessment above and judge whether it correctly preserved clause (b)'s "
                "governance status rather than treating the whole Requirement as void."
            )
            if not mentions_service_life or claims_whole_thing_superseded:
                print("FLAG FOR HUMAN REVIEW: assessment may not have correctly handled the partial supersession.")

        print(f"\n=== OVERALL (Scenarios 1 and A, structurally graded): {'PASS' if all_ok else 'FAIL'} ===")
        return 0 if all_ok else 1
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
