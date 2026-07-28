"""
CLAUDE-P15 - the supersession/Addendum tier's Golden Corpus: a real
CaseWorkspaceStore-backed project where an original RFP Requirement
(96 hours) is validly revised by a real, Supersession-tracked Addendum
(revise_requirement) to 120 hours, and a coordinated downstream Appendix
Requirement correctly reflects the CURRENT (120h) governing value from
the start.

This single builder IS the clean baseline for BOTH:
  - zero false positives generally, and
  - Case B specifically (the historical 96h RFP text is preserved in
    the record, superseded, and must not be flagged as a live conflict
    merely because both values still exist in storage) - the historical
    text is never filtered out before being shown to the model; the
    real test is whether the model correctly recognizes it as non-live.
"""
from __future__ import annotations

from pathlib import Path

from services.case_workspace import (
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    SOURCE_KIND_TEXT_RECORD,
    CaseWorkspaceStore,
)

RFP_ORIGINAL_TEXT = (
    "RFP Section 4.2 - Standby Power: Standby power systems shall provide 96 "
    "hours of autonomous operation for critical facility loads."
)
RFP_ADDENDUM_TEXT = (
    "RFP Section 4.2 (Addendum 1) - Standby Power: Standby power systems shall "
    "provide 120 hours of autonomous operation for critical facility loads."
)
APPENDIX_TEXT_CURRENT = (
    "Appendix C - Building Systems Schedule: the standby power design provides "
    "120 hours of autonomous operation for critical loads, coordinated with RFP "
    "Section 4.2 as amended by Addendum 1."
)


def build_supersession_golden_project(
    store: CaseWorkspaceStore, project_id: str, sources_dir: Path,
) -> dict:
    """
    Fresh project every call. Returns: workspace, rfp_source_id,
    appendix_source_id, original_rfp_requirement_id (superseded, frozen
    at 96h), current_rfp_requirement_id (active, 120h),
    appendix_requirement_id (active, 120h, correctly coordinated).
    """
    workspace = store.get_or_create(project_id)
    sources_dir.mkdir(parents=True, exist_ok=True)

    rfp_path = sources_dir / "rfp_excerpt.txt"
    rfp_path.write_text(RFP_ORIGINAL_TEXT, encoding="utf-8")
    appendix_path = sources_dir / "appendix_excerpt.txt"
    appendix_path.write_text(APPENDIX_TEXT_CURRENT, encoding="utf-8")

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
        authority_class="addendum",
        text_reference=RFP_ADDENDUM_TEXT,
    )

    appendix_requirement = store.register_requirement(
        workspace, source_id=appendix_source["id"], original_requirement_identifier="Appendix C",
        text_reference=APPENDIX_TEXT_CURRENT, created_by="self-test-lab",
        registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    )

    return {
        "workspace": workspace,
        "rfp_source_id": rfp_source["id"],
        "appendix_source_id": appendix_source["id"],
        "original_rfp_requirement_id": original_rfp_requirement["id"],
        "current_rfp_requirement_id": current_rfp_requirement["id"],
        "appendix_requirement_id": appendix_requirement["id"],
    }
