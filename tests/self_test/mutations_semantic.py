"""
CLAUDE-P16 - semantic-conflict tier mutations. Case C (paraphrase, not a
defect) is deliberately NOT here - it's baked into golden_corpus_
semantic.py's own clean baseline, since "does not manufacture semantic
conflicts" must be proven against genuinely different wording as part
of the ordinary clean run, not a separate scenario.

Each case builds its own fresh project (or, for Case E, revises the
clean baseline's own Requirement via the real Supersession-tracked
revise_requirement path) rather than hand-editing text - matching the
same real-machinery discipline as the cross-document and supersession
tiers.
"""
from __future__ import annotations

from pathlib import Path

from services.case_workspace import (
    OBJECT_KIND_REQUIREMENT,
    RELATIONSHIP_TYPE_QUALIFIES,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    SOURCE_KIND_TEXT_RECORD,
    CaseWorkspaceStore,
)

from tests.self_test.golden_corpus_semantic import AUTONOMY_RFP_TEXT
from tests.self_test.mutation_schema import DIFFICULTY_TIER_SEMANTIC, PlantedMutation

# -- Case A: individually reasonable, jointly impossible --------------------

EOC_SHUTDOWN_ON_LOSS_TEXT = (
    "All electrical equipment serving the Emergency Operations Centre shall "
    "shut down automatically upon loss of normal utility power."
)


def build_jointly_impossible_project(store: CaseWorkspaceStore, project_id: str, sources_dir: Path) -> dict:
    from tests.self_test.golden_corpus_semantic import EOC_OPERATIONAL_TEXT

    workspace = store.get_or_create(project_id)
    sources_dir.mkdir(parents=True, exist_ok=True)

    op_path = sources_dir / "opr_eoc_operational.txt"
    op_path.write_text(EOC_OPERATIONAL_TEXT, encoding="utf-8")
    op_source = store.add_source(
        workspace, name="OPR (excerpt)", file_path=str(op_path), kind=SOURCE_KIND_TEXT_RECORD, actor="self-test-lab",
    )
    operational = store.register_requirement(
        workspace, source_id=op_source["id"], original_requirement_identifier="OPR Section 5.1",
        text_reference=EOC_OPERATIONAL_TEXT, created_by="self-test-lab",
        registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    )

    shutdown_path = sources_dir / "opr_eoc_shutdown.txt"
    shutdown_path.write_text(EOC_SHUTDOWN_ON_LOSS_TEXT, encoding="utf-8")
    shutdown_source = store.add_source(
        workspace, name="OPR (excerpt)", file_path=str(shutdown_path), kind=SOURCE_KIND_TEXT_RECORD,
        actor="self-test-lab",
    )
    shutdown = store.register_requirement(
        workspace, source_id=shutdown_source["id"], original_requirement_identifier="OPR Section 5.2 (revised)",
        text_reference=EOC_SHUTDOWN_ON_LOSS_TEXT, created_by="self-test-lab",
        registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    )

    return {
        "workspace": workspace,
        "operational_id": operational["id"],
        "shutdown_id": shutdown["id"],
        "answer_key": PlantedMutation(
            mutation_id="MUT-004A-jointly-impossible", mutation_kind="jointly_impossible_obligations",
            difficulty_tier=DIFFICULTY_TIER_SEMANTIC,
            description=(
                "Two individually reasonable requirements cannot both govern as "
                "written: the EOC must remain continuously operational during "
                "utility failure, but the equipment serving it is required to shut "
                "down automatically on loss of utility power."
            ),
            location=operational["id"], secondary_location=shutdown["id"],
            expected_detection="A semantic/operational contradiction between the two Requirements, not a numeric one.",
            non_defects=[],
        ),
    }


# -- Case B: hidden qualification conflict -----------------------------------

UNRESTRICTED_ACCESS_TEXT = "The facility shall provide unrestricted 24-hour emergency access."
LOCKED_DOORS_SECURITY_TEXT = (
    "All external doors shall remain locked outside normal business hours and "
    "may only be opened by on-site security personnel."
)


def build_hidden_qualification_conflict_project(store: CaseWorkspaceStore, project_id: str, sources_dir: Path) -> dict:
    workspace = store.get_or_create(project_id)
    sources_dir.mkdir(parents=True, exist_ok=True)

    access_path = sources_dir / "rfp_unrestricted_access.txt"
    access_path.write_text(UNRESTRICTED_ACCESS_TEXT, encoding="utf-8")
    access_source = store.add_source(
        workspace, name="RFP Main Document (excerpt)", file_path=str(access_path),
        kind=SOURCE_KIND_TEXT_RECORD, actor="self-test-lab",
    )
    access = store.register_requirement(
        workspace, source_id=access_source["id"], original_requirement_identifier="RFP Section 7.1",
        text_reference=UNRESTRICTED_ACCESS_TEXT, created_by="self-test-lab",
        registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    )

    security_path = sources_dir / "security_locked_doors.txt"
    security_path.write_text(LOCKED_DOORS_SECURITY_TEXT, encoding="utf-8")
    security_source = store.add_source(
        workspace, name="Security Requirements (excerpt)", file_path=str(security_path),
        kind=SOURCE_KIND_TEXT_RECORD, actor="self-test-lab",
    )
    security = store.register_requirement(
        workspace, source_id=security_source["id"], original_requirement_identifier="Security Section 2.3",
        text_reference=LOCKED_DOORS_SECURITY_TEXT, created_by="self-test-lab",
        registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    )

    return {
        "workspace": workspace,
        "access_id": access["id"],
        "security_id": security["id"],
        "answer_key": PlantedMutation(
            mutation_id="MUT-004B-hidden-qualification-conflict", mutation_kind="hidden_qualification_conflict",
            difficulty_tier=DIFFICULTY_TIER_SEMANTIC,
            description=(
                "An 'unrestricted 24-hour emergency access' requirement is "
                "effectively narrowed by a separate security requirement locking "
                "all external doors outside business hours - the conflict emerges "
                "through operational consequence, not explicit contradiction."
            ),
            location=access["id"], secondary_location=security["id"],
            expected_detection=(
                "Recognition that the security requirement qualifies/constrains "
                "the access requirement, and a determination of whether they are "
                "compatible, ambiguous, or contradictory as written."
            ),
            non_defects=[],
        ),
    }


# -- Case D: exception that resolves the apparent contradiction --------------

GATES_UNLOCKED_TEXT = "All perimeter gates shall remain unlocked at all times to allow emergency vehicle access."
GATES_LOCKED_SECURITY_TEXT = (
    "All perimeter gates shall be secured and locked outside of normal "
    "operating hours for site security."
)
GATES_EXCEPTION_TEXT = (
    "Notwithstanding the site security requirement, perimeter gates shall be "
    "equipped with an emergency-override lock mechanism (knox-box or "
    "equivalent) providing immediate emergency-vehicle access at all times, "
    "including outside normal operating hours - this satisfies both the "
    "security-lockdown and emergency-access requirements."
)


def build_exception_resolves_conflict_project(store: CaseWorkspaceStore, project_id: str, sources_dir: Path) -> dict:
    """
    Registers the two apparently-conflicting gate requirements plus a
    THIRD, authoritative exception clause, and records TWO real
    Relationships ("qualifies", from the exception to each of the other
    two) via store.record_relationship - not a test-only hint, the exact
    same primitive a real reviewer would use to connect them.
    """
    workspace = store.get_or_create(project_id)
    sources_dir.mkdir(parents=True, exist_ok=True)

    def _register(filename: str, identifier: str, text: str) -> dict:
        path = sources_dir / filename
        path.write_text(text, encoding="utf-8")
        source = store.add_source(
            workspace, name="OPR (excerpt)", file_path=str(path), kind=SOURCE_KIND_TEXT_RECORD, actor="self-test-lab",
        )
        return store.register_requirement(
            workspace, source_id=source["id"], original_requirement_identifier=identifier,
            text_reference=text, created_by="self-test-lab",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )

    unlocked = _register("opr_gates_unlocked.txt", "OPR Section 5.3", GATES_UNLOCKED_TEXT)
    locked = _register("opr_gates_locked.txt", "OPR Section 8.4", GATES_LOCKED_SECURITY_TEXT)
    exception = _register("opr_gates_exception.txt", "OPR Section 8.5", GATES_EXCEPTION_TEXT)

    store.record_relationship(
        workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=exception["id"],
        to_type=OBJECT_KIND_REQUIREMENT, to_id=unlocked["id"],
        relationship_type=RELATIONSHIP_TYPE_QUALIFIES, created_by="self-test-lab",
    )
    store.record_relationship(
        workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=exception["id"],
        to_type=OBJECT_KIND_REQUIREMENT, to_id=locked["id"],
        relationship_type=RELATIONSHIP_TYPE_QUALIFIES, created_by="self-test-lab",
    )

    return {
        "workspace": workspace,
        "unlocked_id": unlocked["id"],
        "locked_id": locked["id"],
        "exception_id": exception["id"],
    }


# -- Case E: semantic drift across documents ----------------------------------

AUTONOMY_SCHEDULE_TEXT_DRIFTED = "Provide fuel-storage capacity nominally equivalent to 96 hours."


def apply_semantic_drift(
    store: CaseWorkspaceStore, workspace, autonomy_rfp_id: str, autonomy_schedule_id: str,
) -> PlantedMutation:
    """
    Revises the Schedule's autonomy Requirement (via the real, Supersession-
    tracked revise_requirement path) from a genuine PERFORMANCE obligation
    ("maintain operation for 96 hours") to a DESIGN-BASIS estimate ("fuel-
    storage capacity nominally equivalent to 96 hours") - same number,
    same subject, materially different obligation. The RFP's own autonomy
    Requirement (`autonomy_rfp_id`) is never touched.
    """
    new_requirement, _supersession = store.revise_requirement(
        workspace, requirement_id=autonomy_schedule_id, actor="self-test-lab",
        reason="Simulated semantic drift for the CLAUDE-P16 tier - wording revised without a real basis-of-design change",
        text_reference=AUTONOMY_SCHEDULE_TEXT_DRIFTED,
    )
    return PlantedMutation(
        mutation_id="MUT-004E-semantic-drift", mutation_kind="semantic_drift",
        difficulty_tier=DIFFICULTY_TIER_SEMANTIC,
        description=(
            "The Schedule's autonomy requirement was reworded from a performance "
            "obligation ('maintain operation for 96 hours') to a design-basis "
            "estimate ('fuel-storage capacity nominally equivalent to 96 hours') "
            "- the number and subject are unchanged, but the actual obligation "
            "has changed from demonstrated performance to notional capacity."
        ),
        location=autonomy_rfp_id, secondary_location=new_requirement["id"],
        expected_detection=(
            "A semantic drift between the RFP's performance obligation (96h "
            "operation) and the Schedule's design-basis estimate (96h-equivalent "
            "capacity) - not equivalence, despite sharing the same figure."
        ),
        non_defects=[],
    )
