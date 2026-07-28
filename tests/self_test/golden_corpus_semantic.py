"""
CLAUDE-P16 - the semantic-conflict tier's Golden Corpus: a real
CaseWorkspaceStore-backed project where several Requirements express
compatible aspects of the same intended outcome - including a
deliberate PARAPHRASE PAIR (Case C material) baked into the clean
baseline itself, since "does not manufacture semantic conflicts" must
be tested against genuinely different wording, not just identical text
repeated.

Every Requirement here is registered via the real store.register_
requirement path (real provenance) - never a bare RequirementItem
literal - even though it is ultimately fed to bhive_parser's consistency-
check as an id/category/text shim (see tools/self_test_lab_004_semantic.py),
matching the same real-provenance discipline established in the cross-
document and supersession tiers.
"""
from __future__ import annotations

from pathlib import Path

from services.case_workspace import (
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    SOURCE_KIND_TEXT_RECORD,
    CaseWorkspaceStore,
)

EOC_OPERATIONAL_TEXT = (
    "The Emergency Operations Centre shall remain continuously operational "
    "during utility failure."
)
EOC_BACKUP_POWER_TEXT = (
    "The Emergency Operations Centre shall be served by an uninterruptible "
    "backup power supply that continues supplying EOC critical loads during "
    "utility failure."
)
RECORD_DRAWINGS_TEXT = (
    "The Contractor shall furnish record drawings reflecting as-constructed "
    "conditions within 30 days of Substantial Completion."
)
AS_BUILT_DOCUMENTATION_TEXT = (
    "The Design-Builder shall submit as-built documentation within 30 days "
    "of Substantial Completion."
)
AUTONOMY_RFP_TEXT = "The Facility shall maintain operation for 96 hours without external resupply."
AUTONOMY_SCHEDULE_TEXT_CONSISTENT = (
    "Standby systems shall maintain operation for 96 hours without external resupply."
)


def build_semantic_clean_baseline(
    store: CaseWorkspaceStore, project_id: str, sources_dir: Path,
) -> dict:
    """
    Fresh project every call. Registers four compatible pairs: EOC
    operational continuity + its own backup power provision (genuinely
    coherent, the correct version of what Case A mutates into a
    conflict); record drawings + as-built documentation (a genuine
    paraphrase pair - same obligation, different project-native
    terminology - Case C material); and the autonomy requirement stated
    consistently across two documents (the correct version of what Case
    E mutates into drift).
    """
    workspace = store.get_or_create(project_id)
    sources_dir.mkdir(parents=True, exist_ok=True)

    def _register(name: str, filename: str, identifier: str, text: str) -> dict:
        path = sources_dir / filename
        path.write_text(text, encoding="utf-8")
        source = store.add_source(
            workspace, name=name, file_path=str(path), kind=SOURCE_KIND_TEXT_RECORD, actor="self-test-lab",
        )
        return store.register_requirement(
            workspace, source_id=source["id"], original_requirement_identifier=identifier,
            text_reference=text, created_by="self-test-lab",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )

    eoc_operational = _register("OPR (excerpt)", "opr_eoc_operational.txt", "OPR Section 5.1", EOC_OPERATIONAL_TEXT)
    eoc_backup_power = _register("OPR (excerpt)", "opr_eoc_backup_power.txt", "OPR Section 5.2", EOC_BACKUP_POWER_TEXT)
    record_drawings = _register("RFP Main Document (excerpt)", "rfp_record_drawings.txt", "RFP Section 9.1", RECORD_DRAWINGS_TEXT)
    as_built = _register("Technical Submission (excerpt)", "ts_as_built.txt", "Tech. Submission Section 3.4", AS_BUILT_DOCUMENTATION_TEXT)
    autonomy_rfp = _register("RFP Main Document (excerpt)", "rfp_autonomy.txt", "RFP Section 4.2", AUTONOMY_RFP_TEXT)
    autonomy_schedule = _register(
        "Building Systems Schedule (excerpt)", "schedule_autonomy.txt", "Schedule Section 2.1",
        AUTONOMY_SCHEDULE_TEXT_CONSISTENT,
    )

    return {
        "workspace": workspace,
        "eoc_operational_id": eoc_operational["id"],
        "eoc_backup_power_id": eoc_backup_power["id"],
        "record_drawings_id": record_drawings["id"],
        "as_built_id": as_built["id"],
        "autonomy_rfp_id": autonomy_rfp["id"],
        "autonomy_schedule_id": autonomy_schedule["id"],
    }
