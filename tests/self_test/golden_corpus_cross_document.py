"""
CLAUDE-P14 - the cross-document tier's Golden Corpus: two SEPARATELY
REGISTERED, real governed Sources (an RFP excerpt and an Appendix/
Schedule excerpt) stating the same coordinated 96-hour autonomy
requirement, each in its own document's voice - genuinely two Sources
with real provenance (Requirement.source_id), not two lines in one flat
list pretending to come from different places.

Builds a REAL CaseWorkspaceStore-backed project using the same
primitives any real ingestion uses (store.add_source, store.
register_requirement) rather than bare dataclass literals - this is
what lets "preserve... as immutable test specimens with provenance"
mean something real: the untouched project state is one store.
create_snapshot call away from being frozen, and the eventual mutation
(see mutations_cross_document.py) is a real, Supersession-tracked
revision, not a silent dict edit.
"""
from __future__ import annotations

from pathlib import Path

from services.case_workspace import (
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    SOURCE_KIND_TEXT_RECORD,
    CaseWorkspaceStore,
)

RFP_TEXT = (
    "RFP Section 4.2 - Standby Power: Standby power systems shall provide "
    "96 hours of autonomous operation for critical facility loads without "
    "normal utility power."
)
APPENDIX_TEXT = (
    "Appendix C - Building Systems Schedule: the standby power design "
    "provides 96 hours of autonomous operation for critical loads, "
    "coordinated with RFP Section 4.2."
)


def build_cross_document_golden_project(
    store: CaseWorkspaceStore, project_id: str, sources_dir: Path,
) -> dict:
    """
    Returns a fresh project every call - never a shared/mutated fixture -
    with two real Sources and one real Requirement registered against
    each: {"workspace", "rfp_source_id", "appendix_source_id",
    "rfp_requirement_id", "appendix_requirement_id"}.
    """
    workspace = store.get_or_create(project_id)

    sources_dir.mkdir(parents=True, exist_ok=True)
    rfp_path = sources_dir / "rfp_excerpt.txt"
    rfp_path.write_text(RFP_TEXT, encoding="utf-8")
    appendix_path = sources_dir / "appendix_excerpt.txt"
    appendix_path.write_text(APPENDIX_TEXT, encoding="utf-8")

    rfp_source = store.add_source(
        workspace, name="RFP Main Document (excerpt)", file_path=str(rfp_path),
        kind=SOURCE_KIND_TEXT_RECORD, actor="self-test-lab",
    )
    appendix_source = store.add_source(
        workspace, name="Appendix C - Building Systems Schedule (excerpt)", file_path=str(appendix_path),
        kind=SOURCE_KIND_TEXT_RECORD, actor="self-test-lab",
    )

    rfp_requirement = store.register_requirement(
        workspace, source_id=rfp_source["id"], original_requirement_identifier="RFP Section 4.2",
        text_reference=RFP_TEXT, created_by="self-test-lab",
        registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    )
    appendix_requirement = store.register_requirement(
        workspace, source_id=appendix_source["id"], original_requirement_identifier="Appendix C",
        text_reference=APPENDIX_TEXT, created_by="self-test-lab",
        registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    )

    return {
        "workspace": workspace,
        "rfp_source_id": rfp_source["id"],
        "appendix_source_id": appendix_source["id"],
        "rfp_requirement_id": rfp_requirement["id"],
        "appendix_requirement_id": appendix_requirement["id"],
    }
