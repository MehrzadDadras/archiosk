"""
CLAUDE-P18 - the lifecycle-migration tier's Golden Corpus: ONE coherent
chain (the Cedar Harbour generator-autonomy story, already understood
well from real production use) followed across nine real governed
stages, using only real CaseWorkspaceStore machinery - Source,
Requirement, Supersession (via revise_requirement), Relationship,
Participant/PerspectiveAssessment, Case/Activity, and Snapshot. There is
no benchmark-only "timeline truth" object anywhere in this module -
"what was required when" and "what superseded what" are answered ONLY by
calling the real store methods (current_requirement_for,
requirement_predecessor, relationships_for) against these real records,
exactly as tools/self_test_lab_006_lifecycle.py and
tests/test_lifecycle_tier.py do.

Two PARALLEL real Supersession chains, connected by a real Relationship,
not one chain with a special case bolted on:

  Owner/contract authority chain (the governing number):
    RFP (72h) --revise--> Addendum (96h) --revise--> CR-17 (96h, contractual)

  Evidence-maturity chain (progressively better knowledge of the SAME
  physical fact - reusing Supersession for "the current best evidence"
  exactly as CLAUDE-P15 reused it for a governing-number change):
    30% Design (~90h) --revise--> 60% Calc (101h) --revise-->
    Submittal (94h, actual) --revise--> Commissioning (98h, verified)

The Design-Builder's Proposal (72h) is deliberately NEITHER chain's
member - it was never itself a governing record, so it is connected via
a plain CONTRADICTS Relationship to the Addendum (the record it disagreed
with AT THE TIME), not a Supersession. Whether Archiosk correctly walks
FORWARD from that stale relationship target to what NOW governs (CR-17)
is the specific production gap this tier's own plumbing fix (see
conversation_interpreter.py) addresses - deliberately built into the
clean chain itself, not held back for a mutation, because the ability to
follow authority across MULTIPLE lifecycle stages is this tier's entire
point.

The visible "lifecycle strip" in templates/case_workspace.html is
confirmed decorative (a hardcoded list with a hardcoded "current" stage,
never derived from any governed field) - this corpus never references it
and stage/authority here comes only from real Source/Requirement
timestamps and Relationships, per the explicit instruction not to fake
stage authority from that UI.
"""
from __future__ import annotations

from pathlib import Path

from services.case_workspace import (
    PARTICIPANT_ROLE_DESIGN_BUILDER,
    PARTICIPANT_ROLE_OWNER,
    RELATIONSHIP_TYPE_CONTRADICTS,
    RELATIONSHIP_TYPE_IMPLEMENTS,
    RELATIONSHIP_TYPE_REFERENCES,
    RELATIONSHIP_TYPE_SUPPORTS,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    SOURCE_KIND_TEXT_RECORD,
    OBJECT_KIND_REQUIREMENT,
    CaseWorkspaceStore,
)

OWNER_INTENT_TEXT = (
    "The Facility must remain operational during a prolonged utility power failure."
)
RFP_TEXT = (
    "The Facility's standby power system shall maintain full facility operation for "
    "72 hours without refueling."
)
ADDENDUM_TEXT = (
    "Addendum 3: Section 4.2's standby autonomy duration is revised from 72 hours to "
    "96 hours without refueling."
)
PROPOSAL_TEXT = (
    "The Design-Builder's proposed standby fuel system provides 72 hours of "
    "autonomous operation without refueling."
)
CR17_TEXT = (
    "CR-17: the 96-hour standby autonomy requirement established by Addendum 3 is "
    "incorporated into the Executed Agreement as a contractual obligation. The "
    "Contract Price is not adjusted as a result of this Change Request."
)
DESIGN_30_TEXT = (
    "Preliminary fuel consumption calculations at 30% design indicate approximately "
    "90 hours of standby autonomy under the specified generator load profile."
)
CALC_60_TEXT = (
    "60% design fuel consumption calculations, refined against the selected generator "
    "model, predict 101 hours of standby autonomy."
)
SUBMITTAL_TEXT = (
    "Fuel system submittal, based on the as-procured fuel storage tank's actual usable "
    "capacity, indicates 94 hours of standby autonomy."
)
COMMISSIONING_TEXT = (
    "Commissioning field test, performed after the fuel storage tank capacity "
    "correction, demonstrates a 98-hour equivalent standby autonomy."
)
CORRECTIVE_ACTION_DESCRIPTION = (
    "Fuel storage tank capacity increased following the 94-hour submittal shortfall "
    "identified against the 96-hour contractual requirement; system re-verified at "
    "commissioning."
)


def write_source(store: CaseWorkspaceStore, workspace, sources_dir: Path, filename: str, name: str, text: str) -> dict:
    path = sources_dir / filename
    path.write_text(text, encoding="utf-8")
    return store.add_source(workspace, name=name, file_path=str(path), kind=SOURCE_KIND_TEXT_RECORD, actor="self-test-lab")


def build_lifecycle_setup(store: CaseWorkspaceStore, project_id: str, sources_dir: Path) -> dict:
    """
    Shared setup used by every variant in this tier (clean corpus and
    every mutation alike): the Case, the two real Participants, the
    Owner Intent record, and the RFP (72h) -> Addendum (96h) ->
    Design-Builder Proposal (72h, contradicting) -> CR-17 (96h,
    contractual) chain every variant shares. Nothing downstream of CR-17
    is built here - that's where the clean corpus and the mutations
    genuinely diverge.
    """
    workspace = store.get_or_create(project_id)
    sources_dir.mkdir(parents=True, exist_ok=True)
    case = store.create_case(
        workspace, title="Fuel Autonomy Lifecycle Verification",
        objective="Track the standby fuel autonomy requirement from Owner intent through commissioning.",
        created_by="self-test-lab",
    )
    owner = store.record_participant(
        workspace, name="Meridian Transit Authority", role_type=PARTICIPANT_ROLE_OWNER, created_by="self-test-lab",
    )
    design_builder = store.record_participant(
        workspace, name="Aurora Infrastructure Partners", role_type=PARTICIPANT_ROLE_DESIGN_BUILDER,
        created_by="self-test-lab",
    )

    intent_source = write_source(store, workspace, sources_dir, "owner_intent.txt", "Owner Statement of Need", OWNER_INTENT_TEXT)
    intent = store.register_requirement(
        workspace, source_id=intent_source["id"], original_requirement_identifier="Statement of Need 1.1",
        text_reference=OWNER_INTENT_TEXT, created_by="self-test-lab",
        registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED, classification="owner_intent",
    )

    rfp_source = write_source(store, workspace, sources_dir, "rfp.txt", "RFP Main Document", RFP_TEXT)
    rfp_72 = store.register_requirement(
        workspace, source_id=rfp_source["id"], original_requirement_identifier="RFP Section 4.2",
        text_reference=RFP_TEXT, created_by="self-test-lab",
        registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED, classification="performance",
    )
    store.record_relationship(
        workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=rfp_72["id"],
        to_type=OBJECT_KIND_REQUIREMENT, to_id=intent["id"],
        relationship_type=RELATIONSHIP_TYPE_IMPLEMENTS, created_by="self-test-lab",
    )

    addendum_source = write_source(store, workspace, sources_dir, "addendum_3.txt", "Addendum 3", ADDENDUM_TEXT)
    addendum_96, _ = store.revise_requirement(
        workspace, requirement_id=rfp_72["id"], actor="self-test-lab",
        reason="Addendum 3: standby autonomy duration revised from 72 to 96 hours.",
        source_id=addendum_source["id"], text_reference=ADDENDUM_TEXT,
        original_requirement_identifier="Addendum 3, Item 4.2-1",
    )

    proposal_source = write_source(store, workspace, sources_dir, "proposal.txt", "Design-Builder Technical Proposal", PROPOSAL_TEXT)
    proposal_72 = store.register_requirement(
        workspace, source_id=proposal_source["id"], original_requirement_identifier="Proposal Section 3.4",
        text_reference=PROPOSAL_TEXT, created_by="self-test-lab",
        registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED, classification="proposed_commitment",
    )
    store.record_relationship(
        workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=proposal_72["id"],
        to_type=OBJECT_KIND_REQUIREMENT, to_id=addendum_96["id"],
        relationship_type=RELATIONSHIP_TYPE_CONTRADICTS, created_by="self-test-lab",
    )

    cr17_source = write_source(store, workspace, sources_dir, "cr17.txt", "Executed Agreement - CR-17", CR17_TEXT)
    cr17_96, _ = store.revise_requirement(
        workspace, requirement_id=addendum_96["id"], actor="self-test-lab",
        reason="CR-17: Addendum 3 autonomy requirement incorporated into the Executed Agreement at no change in Contract Price.",
        source_id=cr17_source["id"], text_reference=CR17_TEXT, classification="contractual_obligation",
        original_requirement_identifier="CR-17",
    )

    return {
        "workspace": workspace, "case": case, "owner": owner, "design_builder": design_builder,
        "intent_id": intent["id"], "rfp_72_id": rfp_72["id"], "addendum_96_id": addendum_96["id"],
        "proposal_72_id": proposal_72["id"], "cr17_96_id": cr17_96["id"],
    }


def extend_with_design_and_calc(store: CaseWorkspaceStore, setup: dict, sources_dir: Path) -> dict:
    """Adds the 30% design (~90h) -> 60% calculation (101h) steps -
    shared by the clean corpus and by CLAUDE-P18 Case E (which needs a
    Snapshot taken at exactly this point, before the submittal exists)."""
    workspace = setup["workspace"]

    design_30_source = write_source(store, workspace, sources_dir, "design_30pct.txt", "30% Design Development Calculations", DESIGN_30_TEXT)
    design_30 = store.register_requirement(
        workspace, source_id=design_30_source["id"], original_requirement_identifier="30% DD Calc Sheet 1",
        text_reference=DESIGN_30_TEXT, created_by="self-test-lab",
        registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED, classification="design_evidence",
    )
    # Deliberately RELATIONSHIP_TYPE_REFERENCES, not SUPPORTS/CONTRADICTS -
    # a 30% estimate is too preliminary to honestly call a compliance
    # comparison against the 96-hour requirement yet.
    store.record_relationship(
        workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=design_30["id"],
        to_type=OBJECT_KIND_REQUIREMENT, to_id=setup["cr17_96_id"],
        relationship_type=RELATIONSHIP_TYPE_REFERENCES, created_by="self-test-lab",
    )

    calc_60_source = write_source(store, workspace, sources_dir, "calc_60pct.txt", "60% Design Calculations", CALC_60_TEXT)
    calc_60, _ = store.revise_requirement(
        workspace, requirement_id=design_30["id"], actor="self-test-lab",
        reason="60% design calculation refinement against the selected generator model.",
        source_id=calc_60_source["id"], text_reference=CALC_60_TEXT,
        original_requirement_identifier="60% DD Calc Sheet 1",
    )
    store.record_relationship(
        workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=calc_60["id"],
        to_type=OBJECT_KIND_REQUIREMENT, to_id=setup["cr17_96_id"],
        relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="self-test-lab",
    )

    return {**setup, "design_30_id": design_30["id"], "calc_60_id": calc_60["id"]}


def extend_with_submittal(store: CaseWorkspaceStore, corpus: dict, sources_dir: Path) -> dict:
    """Adds the Submittal (94h, actual, a real shortfall against the
    96-hour CR-17 obligation) - shared by the clean corpus and by
    CLAUDE-P18 Case B (contract-vs-physical, which stops here on
    purpose)."""
    workspace = corpus["workspace"]
    submittal_source = write_source(store, workspace, sources_dir, "submittal.txt", "Fuel System Submittal", SUBMITTAL_TEXT)
    submittal_94, _ = store.revise_requirement(
        workspace, requirement_id=corpus["calc_60_id"], actor="self-test-lab",
        reason="Fuel system submittal based on as-procured fuel storage tank capacity.",
        source_id=submittal_source["id"], text_reference=SUBMITTAL_TEXT,
        original_requirement_identifier="Fuel System Submittal Section 2",
    )
    store.record_relationship(
        workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=submittal_94["id"],
        to_type=OBJECT_KIND_REQUIREMENT, to_id=corpus["cr17_96_id"],
        relationship_type=RELATIONSHIP_TYPE_CONTRADICTS, created_by="self-test-lab",
    )
    return {**corpus, "submittal_94_id": submittal_94["id"]}


def extend_with_correction_and_commissioning(store: CaseWorkspaceStore, corpus: dict, sources_dir: Path) -> dict:
    """Adds the corrective Activity and the Commissioning (98h, verified)
    step, completing the clean chain."""
    workspace = corpus["workspace"]
    store.record_activity(
        workspace, case_id=corpus["case"]["id"], kind="corrective-action",
        description=CORRECTIVE_ACTION_DESCRIPTION, created_by="self-test-lab",
    )
    commissioning_source = write_source(store, workspace, sources_dir, "commissioning.txt", "Commissioning Report", COMMISSIONING_TEXT)
    commissioning_98, _ = store.revise_requirement(
        workspace, requirement_id=corpus["submittal_94_id"], actor="self-test-lab",
        reason="Corrective action completed (fuel storage tank capacity increased); commissioning test verifies compliance.",
        source_id=commissioning_source["id"], text_reference=COMMISSIONING_TEXT,
        original_requirement_identifier="Commissioning Report Section 2",
    )
    store.record_relationship(
        workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=commissioning_98["id"],
        to_type=OBJECT_KIND_REQUIREMENT, to_id=corpus["cr17_96_id"],
        relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="self-test-lab",
    )
    return {**corpus, "commissioning_98_id": commissioning_98["id"]}


def build_clean_lifecycle_golden_corpus(store: CaseWorkspaceStore, project_id: str, sources_dir: Path) -> dict:
    """The full, coherent nine-stage chain with every transition
    correctly governed - every transition real (Supersession/
    Relationship), nothing left stale or unresolved."""
    setup = build_lifecycle_setup(store, project_id, sources_dir)
    corpus = extend_with_design_and_calc(store, setup, sources_dir)
    corpus = extend_with_submittal(store, corpus, sources_dir)
    corpus = extend_with_correction_and_commissioning(store, corpus, sources_dir)
    return corpus
