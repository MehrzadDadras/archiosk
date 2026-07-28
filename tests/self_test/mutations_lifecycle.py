"""
CLAUDE-P18 - lifecycle-migration tier mutations. Cases C (interim
shortfall later corrected) and D (risk migration) are deliberately NOT
here - they reuse the CLEAN corpus's own complete chain unmodified (see
tools/self_test_lab_006_lifecycle.py), since both ask questions ABOUT a
correctly-governed history rather than requiring anything to be broken.
Case E (late evidence reversal) is also not a "mutation" in the
defect-planting sense - it uses golden_corpus_lifecycle.py's own
extend_with_* functions to build the clean chain up to a real Snapshot
point and then continues it, exercised directly in the lab script.

Each mutation here reuses golden_corpus_lifecycle.py's real setup/extend
helpers - the shared stages are never rebuilt by hand a second time - and
diverges only at the specific real governed record the mutation is
actually about.
"""
from __future__ import annotations

from pathlib import Path

from services.case_workspace import (
    RELATIONSHIP_TYPE_CONTRADICTS,
    RELATIONSHIP_TYPE_SUPPORTS,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    SOURCE_KIND_TEXT_RECORD,
    OBJECT_KIND_REQUIREMENT,
    CaseWorkspaceStore,
)
from tests.self_test.golden_corpus_lifecycle import (
    write_source,
    build_lifecycle_setup,
    extend_with_correction_and_commissioning,
    extend_with_design_and_calc,
    extend_with_submittal,
)
from tests.self_test.mutation_schema import DIFFICULTY_TIER_LIFECYCLE, PlantedMutation

# -- Case A: requirement changes, downstream design remains stale -----------

STALE_DESIGN_30_TEXT = (
    "Preliminary fuel consumption calculations at 30% design indicate approximately "
    "72 hours of standby autonomy, consistent with the original RFP requirement."
)


def build_stale_downstream_design_project(store: CaseWorkspaceStore, project_id: str, sources_dir: Path) -> dict:
    """
    The Addendum and CR-17 both establish 96 hours as governing, but the
    30% design calculation was never updated - it still assumes the
    ORIGINAL 72-hour figure. Registered as a genuinely fresh Requirement
    (not derived from the clean corpus's own 30% design record), matching
    what a real design team's oversight would actually produce: a document
    that was simply never revised to reflect the Addendum, not a
    Supersession of anything.
    """
    setup = build_lifecycle_setup(store, project_id, sources_dir)
    workspace = setup["workspace"]

    stale_source = write_source(store, workspace, sources_dir, "design_30pct_stale.txt", "30% Design Development Calculations", STALE_DESIGN_30_TEXT)
    stale_design_30 = store.register_requirement(
        workspace, source_id=stale_source["id"], original_requirement_identifier="30% DD Calc Sheet 1",
        text_reference=STALE_DESIGN_30_TEXT, created_by="self-test-lab",
        registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED, classification="design_evidence",
    )
    store.record_relationship(
        workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=stale_design_30["id"],
        to_type=OBJECT_KIND_REQUIREMENT, to_id=setup["cr17_96_id"],
        relationship_type=RELATIONSHIP_TYPE_CONTRADICTS, created_by="self-test-lab",
    )

    return {
        **setup,
        "stale_design_30_id": stale_design_30["id"],
        "answer_key": PlantedMutation(
            mutation_id="MUT-006A-stale-downstream-design", mutation_kind="stale_downstream_lifecycle_evidence",
            difficulty_tier=DIFFICULTY_TIER_LIFECYCLE,
            description=(
                "The Addendum (and CR-17, which incorporates it) established 96 hours as "
                "governing, but the 30% design calculation still assumes the original "
                "72-hour RFP figure - it was never updated to reflect the Addendum."
            ),
            location=stale_design_30["id"], secondary_location=setup["cr17_96_id"],
            expected_detection=(
                "The 30% design's 72-hour assumption is stale relative to the 96-hour "
                "governing requirement (Addendum 3 / CR-17), not a genuine independent "
                "engineering conclusion."
            ),
            non_defects=[],
        ),
    }


# -- Case B: contract resolves wording, physical evidence still fails -------

def build_contract_vs_physical_project(store: CaseWorkspaceStore, project_id: str, sources_dir: Path) -> dict:
    """
    Stops deliberately at the Submittal - no correction, no commissioning
    - so the ONLY question left is whether Archiosk can distinguish
    "contractually resolved" (CR-17 establishes 96 hours) from
    "physically demonstrated" (the Submittal shows only 94 hours, a real,
    still-unresolved shortfall as of the latest evidence).
    """
    setup = build_lifecycle_setup(store, project_id, sources_dir)
    corpus = extend_with_design_and_calc(store, setup, sources_dir)
    corpus = extend_with_submittal(store, corpus, sources_dir)
    return {
        **corpus,
        "answer_key": PlantedMutation(
            mutation_id="MUT-006B-contract-vs-physical", mutation_kind="contractual_vs_demonstrated_performance",
            difficulty_tier=DIFFICULTY_TIER_LIFECYCLE,
            description=(
                "CR-17 makes 96 hours a contractual obligation, but the most recent "
                "physical evidence (the Submittal) demonstrates only 94 hours - a real "
                "shortfall against the CONTRACTUAL figure, with no correction or "
                "commissioning yet on record."
            ),
            location=corpus["submittal_94_id"], secondary_location=corpus["cr17_96_id"],
            expected_detection=(
                "The requirement is contractually resolved (96 hours, CR-17) but NOT yet "
                "physically verified - the Submittal's 94 hours is a genuine, currently "
                "unresolved shortfall, not something the contractual resolution already "
                "cured."
            ),
            non_defects=[],
        ),
    }


# -- Case F: missing lifecycle link -----------------------------------------

STANDALONE_COMMISSIONING_TEXT = (
    "Commissioning field test demonstrates a 98-hour equivalent standby autonomy."
)


def build_missing_corrective_link_project(store: CaseWorkspaceStore, project_id: str, sources_dir: Path) -> dict:
    """
    The contractual 96-hour obligation exists and a Commissioning report
    later shows 98 hours (satisfying it) - but NO governed record (no
    Supersession, no Relationship, no Activity) explains how the
    Submittal's 94-hour shortfall became the Commissioning's 98-hour
    result. The Commissioning record is registered as a wholly
    freestanding Requirement - deliberately never derived from the
    Submittal via revise_requirement, and no corrective-action Activity is
    recorded - so the only link back to governing authority is a single
    SUPPORTS Relationship to CR-17 itself. A real investigator asked to
    walk through how the shortfall was resolved should surface the gap
    honestly rather than inventing the missing corrective story (which it
    was never given).
    """
    setup = build_lifecycle_setup(store, project_id, sources_dir)
    corpus = extend_with_design_and_calc(store, setup, sources_dir)
    corpus = extend_with_submittal(store, corpus, sources_dir)
    workspace = corpus["workspace"]

    commissioning_source = write_source(
        store, workspace, sources_dir, "commissioning_standalone.txt", "Commissioning Report", STANDALONE_COMMISSIONING_TEXT,
    )
    commissioning_98 = store.register_requirement(
        workspace, source_id=commissioning_source["id"], original_requirement_identifier="Commissioning Report Section 2",
        text_reference=STANDALONE_COMMISSIONING_TEXT, created_by="self-test-lab",
        registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED, classification="verification_evidence",
    )
    store.record_relationship(
        workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=commissioning_98["id"],
        to_type=OBJECT_KIND_REQUIREMENT, to_id=corpus["cr17_96_id"],
        relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="self-test-lab",
    )

    return {
        **corpus,
        "standalone_commissioning_id": commissioning_98["id"],
        "answer_key": PlantedMutation(
            mutation_id="MUT-006F-missing-corrective-link", mutation_kind="missing_lifecycle_link",
            difficulty_tier=DIFFICULTY_TIER_LIFECYCLE,
            description=(
                "Commissioning demonstrates 98 hours (satisfying the 96-hour CR-17 "
                "obligation), but no governed record - no Supersession, Relationship, "
                "or Activity - explains how the Submittal's 94-hour shortfall was "
                "actually resolved."
            ),
            location=corpus["submittal_94_id"], secondary_location=commissioning_98["id"],
            expected_detection=(
                "A genuine provenance/evidence gap between the Submittal's shortfall "
                "and the Commissioning's success - the investigator should say so "
                "plainly rather than fabricating a corrective-action narrative it was "
                "never given."
            ),
            non_defects=[],
        ),
    }
