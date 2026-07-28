"""
CLAUDE-P15 - supersession/Addendum tier mutations. Each builds its OWN
fresh project from scratch (not an edit of golden_corpus_supersession's
clean baseline) because "never updated" and "reverted" are different
real-world scenarios - a stale downstream reference was simply never
touched, not touched-then-undone, and the corpus should reflect that
honestly rather than simulating it as a second revision.

Both scenarios use the real, Supersession-tracked revise_requirement
path for the RFP-side Addendum - the only thing that differs from the
golden baseline is whether/how the DOWNSTREAM Appendix or compound
clause was (or wasn't) correspondingly updated.
"""
from __future__ import annotations

from pathlib import Path

from services.case_workspace import (
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    SOURCE_KIND_TEXT_RECORD,
    CaseWorkspaceStore,
)

from tests.self_test.golden_corpus_supersession import RFP_ADDENDUM_TEXT, RFP_ORIGINAL_TEXT
from tests.self_test.mutation_schema import DIFFICULTY_TIER_SUPERSESSION, PlantedMutation

# -- Mutation A: stale downstream reference ----------------------------------

APPENDIX_TEXT_STALE = (
    "Appendix C - Building Systems Schedule: the standby power design provides "
    "96 hours of autonomous operation for critical loads, coordinated with RFP "
    "Section 4.2."
)


def build_stale_downstream_project(
    store: CaseWorkspaceStore, project_id: str, sources_dir: Path,
) -> dict:
    """
    Mutation A: the RFP Addendum still validly revises 96 -> 120 hours,
    real Supersession and all - but the Appendix was simply never
    updated to match. Returns the same shape as build_supersession_
    golden_project, plus a PlantedMutation answer key.
    """
    workspace = store.get_or_create(project_id)
    sources_dir.mkdir(parents=True, exist_ok=True)

    rfp_path = sources_dir / "rfp_excerpt.txt"
    rfp_path.write_text(RFP_ORIGINAL_TEXT, encoding="utf-8")
    appendix_path = sources_dir / "appendix_excerpt.txt"
    appendix_path.write_text(APPENDIX_TEXT_STALE, encoding="utf-8")

    rfp_source = store.add_source(
        workspace, name="RFP Main Document (excerpt)", file_path=str(rfp_path),
        kind=SOURCE_KIND_TEXT_RECORD, actor="self-test-lab",
    )
    appendix_source = store.add_source(
        workspace, name="Appendix C - Building Systems Schedule (excerpt)", file_path=str(appendix_path),
        kind=SOURCE_KIND_TEXT_RECORD, actor="self-test-lab",
    )

    original_rfp_requirement = store.register_requirement(
        workspace, source_id=rfp_source["id"], original_requirement_identifier="RFP Section 4.2",
        text_reference=RFP_ORIGINAL_TEXT, created_by="self-test-lab",
        registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    )
    current_rfp_requirement, _supersession = store.revise_requirement(
        workspace, requirement_id=original_rfp_requirement["id"], actor="self-test-lab",
        reason="Addendum 1 - autonomy period increased from 96 to 120 hours",
        authority_class="addendum", text_reference=RFP_ADDENDUM_TEXT,
    )

    appendix_requirement = store.register_requirement(
        workspace, source_id=appendix_source["id"], original_requirement_identifier="Appendix C",
        text_reference=APPENDIX_TEXT_STALE, created_by="self-test-lab",
        registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    )

    answer_key = PlantedMutation(
        mutation_id="MUT-003A-stale-downstream-reference",
        mutation_kind="stale_downstream_reference",
        difficulty_tier=DIFFICULTY_TIER_SUPERSESSION,
        description=(
            "RFP Section 4.2 was validly amended by Addendum 1 (96 -> 120 hours), "
            "but Appendix C was never updated and still states 96 hours - it is "
            "now stale relative to what currently governs."
        ),
        location=current_rfp_requirement["id"],
        secondary_location=appendix_requirement["id"],
        expected_detection=(
            "Appendix C (active, 96h) does not match the currently-governing RFP "
            "Section 4.2 as amended (active, 120h) - a real, live inconsistency, "
            "not merely a historical record."
        ),
        non_defects=[
            "The original (superseded) RFP Section 4.2 text stating 96 hours is "
            "expected historical record and must not itself be flagged.",
        ],
    )

    return {
        "workspace": workspace,
        "rfp_source_id": rfp_source["id"],
        "appendix_source_id": appendix_source["id"],
        "original_rfp_requirement_id": original_rfp_requirement["id"],
        "current_rfp_requirement_id": current_rfp_requirement["id"],
        "appendix_requirement_id": appendix_requirement["id"],
        "answer_key": answer_key,
    }


# -- Mutation C: partial supersession of a compound requirement --------------

COMPOUND_ORIGINAL_TEXT = (
    "RFP Section 6.1 - Facility Standards: (a) Standby power systems shall "
    "provide 96 hours of autonomous operation for critical facility loads; and "
    "(b) the Facility shall be designed for a minimum 50-year structural "
    "service life."
)
COMPOUND_REVISED_TEXT = (
    "RFP Section 6.1 (Addendum 1) - Facility Standards: (a) Standby power "
    "systems shall provide 120 hours of autonomous operation for critical "
    "facility loads; and (b) the Facility shall be designed for a minimum "
    "50-year structural service life."
)


def build_partial_supersession_project(
    store: CaseWorkspaceStore, project_id: str, sources_dir: Path,
) -> dict:
    """
    Mutation C: a compound Requirement (autonomy clause (a) + service-life
    clause (b)) is revised, but the Addendum changes ONLY clause (a)'s
    figure - clause (b) is carried forward verbatim, unchanged, into the
    successor's own text. There is no PlantedMutation here in the usual
    sense (nothing is "wrong") - this scenario tests whether Archiosk
    correctly recognizes clause (b) is STILL governed by the current
    (successor) Requirement, not treat the whole parent as dead just
    because SOME of it was revised. Graded qualitatively (see the lab
    script), not by ConsistencyFlag matching.
    """
    workspace = store.get_or_create(project_id)
    sources_dir.mkdir(parents=True, exist_ok=True)

    source_path = sources_dir / "rfp_section_6_1.txt"
    source_path.write_text(COMPOUND_ORIGINAL_TEXT, encoding="utf-8")
    source = store.add_source(
        workspace, name="RFP Main Document (excerpt)", file_path=str(source_path),
        kind=SOURCE_KIND_TEXT_RECORD, actor="self-test-lab",
    )

    original_requirement = store.register_requirement(
        workspace, source_id=source["id"], original_requirement_identifier="RFP Section 6.1",
        text_reference=COMPOUND_ORIGINAL_TEXT, created_by="self-test-lab",
        registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    )
    current_requirement, _supersession = store.revise_requirement(
        workspace, requirement_id=original_requirement["id"], actor="self-test-lab",
        reason="Addendum 1 - autonomy period increased from 96 to 120 hours; service life unaffected",
        authority_class="addendum", text_reference=COMPOUND_REVISED_TEXT,
    )

    return {
        "workspace": workspace,
        "source_id": source["id"],
        "original_requirement_id": original_requirement["id"],
        "current_requirement_id": current_requirement["id"],
    }
