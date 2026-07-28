"""
CLAUDE-P14 - cross-document tier mutation: revises ONLY the Appendix-
linked Requirement, via the REAL, governed revise_requirement path (a
Supersession record is created) - not a silent dict edit. The RFP-linked
Requirement is never touched. This is what "preserve... each mutation
as immutable test specimens with provenance" means concretely: the
ORIGINAL Appendix wording remains reconstructable via Supersession,
exactly as a real (here, erroneous) Addendum-style revision would be.
"""
from __future__ import annotations

from services.case_workspace import CaseWorkspaceStore, ProjectWorkspace

from tests.self_test.mutation_schema import DIFFICULTY_TIER_CROSS_DOCUMENT, PlantedMutation

MUTATED_APPENDIX_TEXT = (
    "Appendix C - Building Systems Schedule: the standby power design "
    "provides 72 hours of autonomous operation for critical loads, "
    "coordinated with RFP Section 4.2."
)


def apply_cross_document_inconsistency(
    store: CaseWorkspaceStore,
    workspace: ProjectWorkspace,
    rfp_requirement_id: str,
    appendix_requirement_id: str,
) -> PlantedMutation:
    """
    Revises the Appendix Requirement ONLY (96h -> 72h) via the real
    revise_requirement path. The RFP Requirement (still 96h) is left
    exactly as registered - the two coordinated documents no longer
    agree, and only one side of the corpus knows it changed.

    revise_requirement is non-destructive: `appendix_requirement_id`
    itself becomes the SUPERSEDED predecessor (still reads 96h, frozen)
    and a NEW id is minted for the successor that actually carries the
    72h text - PlantedMutation.secondary_location is that NEW id (the
    one a fresh read of current state will actually return), not the
    original, so evaluation checks against what's really current.
    """
    new_requirement, _supersession = store.revise_requirement(
        workspace,
        requirement_id=appendix_requirement_id,
        actor="self-test-lab",
        reason="Simulated erroneous Addendum-style revision for the CLAUDE-P14 cross-document tier",
        text_reference=MUTATED_APPENDIX_TEXT,
    )
    return PlantedMutation(
        mutation_id="MUT-002-cross-document-inconsistency",
        mutation_kind="cross_document_inconsistency",
        difficulty_tier=DIFFICULTY_TIER_CROSS_DOCUMENT,
        description=(
            "The Appendix C Requirement was revised from 96 to 72 hours of "
            "autonomous operation, while the RFP Section 4.2 Requirement - a "
            "separate, real, governed Source - still states 96 hours. The two "
            "coordinated documents no longer agree."
        ),
        location=rfp_requirement_id,
        secondary_location=new_requirement["id"],
        expected_detection=(
            "A cross-Source contradiction between RFP Section 4.2 (96h) and "
            "Appendix C (72h, revised), correctly naming both real requirement ids."
        ),
        non_defects=[],
    )
