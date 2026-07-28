"""
CLAUDE-P17 - the perspective-sensitive risk/opportunity tier's Golden
Corpus: a real CaseWorkspaceStore-backed project with real Participants
(Owner, Design-Builder) and five Requirements whose FACTUAL meaning is
unambiguous - the variable under test is never the governed evidence
(identical for every perspective asked about it), only which represented
party is doing the asking.

Every Requirement is registered via the real store.register_requirement
path (real provenance, real Sources) and every Participant via the real
store.record_participant path - matching the same real-machinery
discipline established in every prior tier. There is no PlantedMutation
here (mutation_schema.py's shape is built for a bhive_parser
ConsistencyFlag defect-pair, a different question from "which polarity
did the model call, from which position") - the answer key for this
tier is PERSPECTIVE_EXPECTATIONS below: what a perspective-sensitive
investigator SHOULD say (and, just as importantly, should NOT say) from
each party's own position, graded directly against the model's own
returned polarity/confidence fields, never against a test-only hint fed
to the investigator itself.
"""
from __future__ import annotations

from pathlib import Path

from services.case_workspace import (
    PARTICIPANT_ROLE_DESIGN_BUILDER,
    PARTICIPANT_ROLE_OWNER,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    SOURCE_KIND_TEXT_RECORD,
    CaseWorkspaceStore,
)

# -- Case A: explicit risk transfer -------------------------------------
RISK_TRANSFER_TEXT = (
    "The Design-Builder shall be solely responsible for the means, methods, "
    "sequencing, and safety of construction, including any risk associated "
    "with unforeseen subsurface conditions encountered during excavation; "
    "the Owner shall bear no responsibility, cost, or schedule liability "
    "for such conditions."
)

# -- Case B: risk is not automatically zero-sum --------------------------
SHARED_RISK_TEXT = (
    "The geotechnical baseline report is based on limited historical "
    "borehole data and actual subsurface conditions may differ materially. "
    "The Owner bears the cost risk of any Differing Site Conditions claim "
    "arising from such variance; the Design-Builder bears the schedule risk "
    "of any delay caused by redesign work necessitated by such conditions."
)

# -- Case C: opportunity without corresponding harm ----------------------
# CLAUDE-P17: two real, blind lab runs against two different drafts of
# this clause both surfaced a genuine, non-zero-sum-derived SECONDARY
# risk for whichever party wasn't the primary subject of "opportunity" -
# the first draft (below) gave the Owner an independently-grounded
# oversight-timing concern (cannot intervene until a breach is provable);
# adding an explicit Owner hold-point/inspection right to close that gap
# instead gave the DESIGN-BUILDER a new, equally genuine execution-risk
# concern (Owner-directed rework at hold points). Both readings were
# evidence-grounded, not manufactured by mirroring the other party's
# polarity - which is itself informative: real means-and-methods
# discretion clauses rarely produce PERFECTLY one-sided outcomes once
# examined closely enough. This tier therefore grades Case C qualitatively
# (see PERSPECTIVE_EXPECTATIONS below and tools/self_test_lab_005_
# perspective.py's printed NOTE) rather than by a hard Owner-must-not-be-
# risk invariant - the thing actually worth checking is whether a
# secondary finding is INDEPENDENTLY REASONED from the clause's own text,
# not whether one exists at all.
OPPORTUNITY_TEXT = (
    "The Design-Builder may select any structural framing system and "
    "construction sequence it deems appropriate, provided the completed "
    "Facility achieves the specified live-load capacity of 150 psf and the "
    "Substantial Completion date set forth in Schedule C."
)

# -- Case D: perspective-neutral obligation ------------------------------
STATUTORY_OBLIGATION_TEXT = (
    "The Design-Builder shall design and construct all occupied areas of "
    "the Facility to comply with the accessibility and life-safety "
    "requirements of the applicable Building Code, and shall obtain all "
    "life-safety code compliance approvals prior to occupancy."
)

# -- Case E: ambiguous allocation -----------------------------------------
AMBIGUOUS_ALLOCATION_TEXT = (
    "In the event of a change in applicable environmental regulations "
    "occurring after the Effective Date, the party responsible for "
    "achieving compliance shall be determined in accordance with the "
    "project's overall risk allocation framework."
)


def build_perspective_golden_corpus(store: CaseWorkspaceStore, project_id: str, sources_dir: Path) -> dict:
    """
    Fresh project every call. Registers the Owner and Design-Builder as
    real Participants, then five Requirements (Cases A-E), each from its
    own real Source. Case F (human/machine convergence + disagreement)
    intentionally reuses Cases A and C's real machine output rather than
    registering a sixth Requirement - see tools/self_test_lab_005_
    perspective.py.
    """
    workspace = store.get_or_create(project_id)
    sources_dir.mkdir(parents=True, exist_ok=True)

    owner = store.record_participant(
        workspace, name="Meridian Transit Authority", role_type=PARTICIPANT_ROLE_OWNER,
        created_by="self-test-lab",
    )
    design_builder = store.record_participant(
        workspace, name="Aurora Infrastructure Partners", role_type=PARTICIPANT_ROLE_DESIGN_BUILDER,
        created_by="self-test-lab",
    )

    def _register(filename: str, identifier: str, text: str) -> dict:
        path = sources_dir / filename
        path.write_text(text, encoding="utf-8")
        source = store.add_source(
            workspace, name="Design-Build Agreement (excerpt)", file_path=str(path),
            kind=SOURCE_KIND_TEXT_RECORD, actor="self-test-lab",
        )
        return store.register_requirement(
            workspace, source_id=source["id"], original_requirement_identifier=identifier,
            text_reference=text, created_by="self-test-lab",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )

    risk_transfer = _register("dba_risk_transfer.txt", "DBA Section 4.1", RISK_TRANSFER_TEXT)
    shared_risk = _register("dba_shared_risk.txt", "DBA Section 4.2", SHARED_RISK_TEXT)
    opportunity = _register("dba_opportunity.txt", "DBA Section 6.3", OPPORTUNITY_TEXT)
    statutory = _register("dba_statutory.txt", "DBA Section 9.1", STATUTORY_OBLIGATION_TEXT)
    ambiguous = _register("dba_ambiguous.txt", "DBA Section 11.4", AMBIGUOUS_ALLOCATION_TEXT)

    return {
        "workspace": workspace,
        "owner": owner,
        "design_builder": design_builder,
        "risk_transfer_id": risk_transfer["id"],
        "shared_risk_id": shared_risk["id"],
        "opportunity_id": opportunity["id"],
        "statutory_id": statutory["id"],
        "ambiguous_id": ambiguous["id"],
    }


# The hidden answer key for this tier: what a perspective-sensitive
# investigator SHOULD say (hard, objectively-checkable invariants) from
# each party's own position - never fed to the investigator itself, only
# used by tools/self_test_lab_005_perspective.py to grade its real,
# blind output afterward.
PERSPECTIVE_EXPECTATIONS = {
    "risk_transfer": {
        "description": "Explicit risk transfer: DB accepts subsurface-conditions exposure, Owner is relieved of it.",
        "design_builder_must_be": "risk",
        "owner_must_not_be": "risk",
    },
    "shared_risk": {
        "description": "Genuine, non-zero-sum shared exposure: Owner bears cost risk, DB bears schedule risk.",
        "design_builder_must_be": "risk",
        "owner_must_be": "risk",
    },
    "opportunity": {
        "description": (
            "DB gets means/methods flexibility while Owner's performance requirement stays "
            "protected. DB reading as opportunity is a hard check. Owner's polarity is graded "
            "QUALITATIVELY, not by a hard invariant - a secondary risk finding for the Owner is "
            "legitimate here IF independently grounded in the clause's own text, illegitimate "
            "only if it is derived by mirroring the Design-Builder's opportunity."
        ),
        "design_builder_must_not_be": "risk",
    },
    "statutory": {
        "description": "A life-safety/code-compliance obligation - perspective may change who manages it, never who profits from it.",
        "neither_party_may_be": "opportunity",
    },
    "ambiguous": {
        "description": "Allocation genuinely unresolved by the governed evidence - expect honest uncertainty, not confident opposite answers.",
        "forbid_confident_disagreement": True,
    },
}
