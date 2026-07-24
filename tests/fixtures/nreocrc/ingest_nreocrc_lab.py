"""
NREOCRC corpus ingestion lab (Prompt 13).

This is a TEST/LAB script, not production code. It exercises BEEHIVE's
existing capabilities (BHiveParser, CaseWorkspaceStore, GovernanceLog,
the Batch B Relationship substrate, the Batch E Expected Information
Profile / Maturity / sufficiency evaluator) against a real synthetic
document corpus, and honestly separates:

  - what was actually run through existing machine ingestion (BHiveParser),
  - from what required manual, hand-curated structured registration
    because no dedicated extraction/schema capability exists yet.

It writes its derived output to a scratch instance directory (regenerable,
not committed) and a snapshot artifact (committed, for later comparison/
adversarial review) under baseline_snapshot_001/.

Run:
    venv/Scripts/python.exe tests/fixtures/nreocrc/ingest_nreocrc_lab.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(r"C:\Archiosk\Research\archiosk")
FIXTURE_DIR = Path(__file__).parent
CORPUS_DIR = FIXTURE_DIR / "immutable_original"
SNAPSHOT_DIR = FIXTURE_DIR / "baseline_snapshot_001"
LAB_INSTANCE_DIR = FIXTURE_DIR / "_lab_instance_scratch"  # regenerable, not committed

sys.path.insert(0, str(REPO_ROOT))

import os
os.environ["FLASK_ENV"] = "development"
os.environ["REGISTRY_STORE_PATH"] = str(LAB_INSTANCE_DIR)

from services.case_workspace import (  # noqa: E402
    CaseWorkspaceStore,
    Source,
    Relationship,
    OBJECT_KIND_SOURCE,
    OBJECT_KIND_PROJECT,
    OBJECT_KIND_REQUIREMENT,
    RELATIONSHIP_TYPE_CORRESPONDS_TO,
    RELATIONSHIP_TYPE_QUALIFIES,
    RELATIONSHIP_TYPE_REFERENCES,
    EXPECTATION_BINDINGNESS_MANDATORY,
    EXPECTATION_BINDINGNESS_EXPECTED,
    EXPECTATION_BINDINGNESS_INFERRED,
    evaluate_information_sufficiency,
)
from services.governance import GovernanceLog  # noqa: E402
from services.bhive_parser import BHiveParser, ParserError  # noqa: E402
from dataclasses import asdict  # noqa: E402

PROJECT_ID = "nreocrc"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    report: dict = {
        "generated_at": now(),
        "bhive_parser_capability_test": {},
        "gaps": [],
        "manual_registration_note": (
            "Requirement records below are HAND-CURATED, TEST-FIXTURE "
            "registrations transcribed directly from the immutable original "
            "by a human/LLM reviewer reading the source document. They are "
            "NOT the output of automated extraction. No dedicated "
            "'Requirement' domain object exists in BEEHIVE yet (see gaps) "
            "so these are held only in this reconstruction artifact, "
            "referenced by Relationships via an id scheme "
            "('OPR-001§<clause>'), not persisted into any CaseWorkspaceStore "
            "list."
        ),
    }

    if LAB_INSTANCE_DIR.exists():
        shutil.rmtree(LAB_INSTANCE_DIR)

    store = CaseWorkspaceStore(LAB_INSTANCE_DIR)
    gov = GovernanceLog(LAB_INSTANCE_DIR)
    workspace = store.get_or_create(PROJECT_ID)

    # ============================================================
    # STEP 1 — Actual BHiveParser capability test (honest, not assumed)
    # ============================================================
    md_path = CORPUS_DIR / "NREOCRC-OPR-001.md"
    raw_bytes = md_path.read_bytes()
    parser = BHiveParser(anthropic_api_key=None)  # no API key configured in this environment - confirmed

    # 1a. Real filename, real extension -> test the actual extraction gate.
    try:
        parser._extract(raw_bytes, "NREOCRC-OPR-001.md")
        report["bhive_parser_capability_test"]["md_extension_direct"] = "supported"
    except ParserError as exc:
        report["bhive_parser_capability_test"]["md_extension_direct"] = f"UNSUPPORTED: {exc}"
        report["gaps"].append({
            "gap": "BHiveParser._extract has no .md handler",
            "condition": "NREOCRC-OPR-001.md is UTF-8 markdown text, structurally readable as plain text",
            "current_behavior": "ParserError raised for unsupported extension; ingestion refuses to start",
            "preferable_behavior": "treat .md as plain text (same path as .txt), since its content is plain-text-decodable",
            "affected_architecture": "services/bhive_parser.py:_extract",
        })

    # 1b. Deliberate TEST-ONLY bypass (relabel as .txt) to separately assess
    # segment/classify quality on this document's actual structure, isolated
    # from the extension-gate finding above. Clearly a test probe, not a
    # claim that BEEHIVE ingests .md files today.
    parsed_document = None
    try:
        parsed_document = parser.parse(raw_bytes, "NREOCRC-OPR-001-test-probe.txt")
        report["bhive_parser_capability_test"]["content_extraction_via_txt_bypass"] = "succeeded"
        report["bhive_parser_capability_test"]["requirement_count"] = len(parsed_document.requirements)
        report["bhive_parser_capability_test"]["milestone_count"] = len(parsed_document.milestones)
        report["bhive_parser_capability_test"]["consistency_checked"] = parsed_document.consistency_checked
        report["bhive_parser_capability_test"]["consistency_note"] = parsed_document.consistency_note
        category_counts: dict[str, int] = {}
        for r in parsed_document.requirements:
            category_counts[r.category] = category_counts.get(r.category, 0) + 1
        report["bhive_parser_capability_test"]["category_distribution"] = category_counts
        # Sample a handful of extracted "requirements" verbatim so quality is
        # visible, not just counted.
        report["bhive_parser_capability_test"]["sample_extracted_lines"] = [
            {"line": r.source_line, "category": r.category, "confidence": r.confidence, "text": r.text[:140]}
            for r in parsed_document.requirements[:12]
        ]
        # Specifically check what happened to a table row from Appendix OPR-1.
        table_row_hits = [r for r in parsed_document.requirements if r.text.strip().startswith("|") and "EOC Operations Room" in r.text]
        report["bhive_parser_capability_test"]["functional_program_table_row_sample"] = (
            {"text": table_row_hits[0].text, "category": table_row_hits[0].category, "confidence": table_row_hits[0].confidence}
            if table_row_hits else "no matching row found in extracted output"
        )
    except ParserError as exc:
        report["bhive_parser_capability_test"]["content_extraction_via_txt_bypass"] = f"FAILED: {exc}"

    if parsed_document is not None:
        report["gaps"].append({
            "gap": "BHiveParser._segment/_classify have no table-aware handling",
            "condition": "Appendix OPR-1 is a 42-row markdown table (Functional Program) with columns for area/adjacency/security level/etc.",
            "current_behavior": "each table row is segmented as one raw pipe-delimited text line and classified by keyword matching tuned for RFP prose, not tabular data - column semantics (which cell is area vs adjacency vs security level) are entirely lost",
            "preferable_behavior": "a table-aware extraction stage that parses markdown/real tables into structured rows with named columns",
            "affected_architecture": "services/bhive_parser.py:_segment, :_classify_with_rules",
        })

    # ============================================================
    # STEP 2 — Source registration (real CaseWorkspaceStore mechanism,
    # constructed directly since neither add_drawing_source (PIL-based,
    # no SVG support) nor the RFQ/RFP auto-registration path (would
    # mislabel this document's kind) fit honestly).
    # ============================================================
    gap_source_schema_logged = False

    def register_source(name: str, path: Path, kind: str, width, height, provenance: dict) -> dict:
        nonlocal gap_source_schema_logged
        note_parts = [f"{k}={v}" for k, v in provenance.items()]
        source = Source(
            id=__import__("uuid").uuid4().hex,
            project_id=workspace.project_id,
            kind=kind,
            name=name,
            added_at=now(),
            file_path=str(path),
            width=width,
            height=height,
            note="; ".join(note_parts),
        )
        workspace.sources.append(asdict(source))
        if not gap_source_schema_logged:
            report["gaps"].append({
                "gap": "Source has no first-class fields for document_id/revision/issue_date/issuer/authority-status/file_hash",
                "condition": "NREOCRC-OPR-001 carries real, stated values for all of these (Document ID, Rev. 0, Issue Date, Issuer, Status)",
                "current_behavior": "these facts were packed into Source.note as an ad hoc 'key=value; key=value' string - functional but not queryable/structured",
                "preferable_behavior": "dedicated fields (or a small embedded provenance dict) on Source for document identity/revision/issuer/authority/hash",
                "affected_architecture": "services/case_workspace.py:Source",
            })
            gap_source_schema_logged = True
        return asdict(source)

    opr_source = register_source(
        "NREOCRC-OPR-001.md", CORPUS_DIR / "NREOCRC-OPR-001.md", kind="owner_project_requirements",
        width=None, height=None,
        provenance={
            "document_id": "NREOCRC-OPR-001", "revision": "0", "issue_date": "2026-12-08",
            "issuer": "North River Infrastructure Corporation",
            "status": "ISSUED WITH RFP — CONTRACTUAL DOCUMENT",
            "sha256": sha256_of(CORPUS_DIR / "NREOCRC-OPR-001.md"),
        },
    )
    fig1_source = register_source(
        "NREOCRC-OPR-001-FIG-2-1-Security-Zoning.svg", CORPUS_DIR / "figures" / "NREOCRC-OPR-001-FIG-2-1-Security-Zoning.svg",
        kind="drawing", width=900, height=620,  # from the SVG's own viewBox, read directly, not fabricated
        provenance={
            "document_id": "NREOCRC-OPR-001 / Figure OPR-2.1", "revision": "0", "issue_date": "2026-12-08",
            "issuer": "North River Infrastructure Corporation",
            "status": "Schematic/indicative of required relationships and separations; not final room locations/dimensions except where expressly designated Mandatory",
            "sha256": sha256_of(CORPUS_DIR / "figures" / "NREOCRC-OPR-001-FIG-2-1-Security-Zoning.svg"),
        },
    )
    fig2_source = register_source(
        "NREOCRC-OPR-001-FIG-2-2-Functional-Adjacency.svg", CORPUS_DIR / "figures" / "NREOCRC-OPR-001-FIG-2-2-Functional-Adjacency.svg",
        kind="drawing", width=900, height=640,
        provenance={
            "document_id": "NREOCRC-OPR-001 / Figure OPR-2.2", "revision": "0", "issue_date": "2026-12-08",
            "issuer": "North River Infrastructure Corporation", "status": "Schematic only, not to scale",
            "sha256": sha256_of(CORPUS_DIR / "figures" / "NREOCRC-OPR-001-FIG-2-2-Functional-Adjacency.svg"),
        },
    )
    store.save(workspace)
    gov.append(project_id=PROJECT_ID, event_type="source_registered", actor="nreocrc-ingestion-lab", role="system",
               payload={"count": 3, "note": "manual structured registration - see gaps log"})

    # ============================================================
    # STEP 3 — Hand-curated representative requirements (NOT machine-
    # extracted; see manual_registration_note above). A representative
    # sample across the document's stated authority vocabulary, not
    # exhaustive (Prompt 13 #34: keep ingestion small).
    # ============================================================
    requirements = [
        {"id": "OPR-001§2.2", "section": "2.2", "authority": "STATED HIERARCHY (provisional)",
         "text": "Order of precedence, highest to lowest: Project Agreement > Addenda (latest governing) > this OPR > Functional Program > RFP main document (technical gaps only) > Accepted Proposal Commitments (bounded) > Indicative Design Package (indicative only) > Data Room (reference/informational).",
         "note": "Explicitly stated as 'the Owner's current statement of intent... will be restated and finalized in the Project Agreement' - PROVISIONAL, not final."},
        {"id": "OPR-001§4.1", "section": "4.1", "authority": "MANDATORY",
         "text": "Physically separated vehicular access for public, staff, EOC emergency vehicles, and service/delivery/fuel vehicles."},
        {"id": "OPR-001§4.3", "section": "4.3", "authority": "MANDATORY",
         "text": "Site shall accommodate the Future Expansion Area (Section 18) without requiring demolition/relocation of primary structure, standby power, or site servicing."},
        {"id": "OPR-001§4.6", "section": "4.6", "authority": "INDICATIVE",
         "text": "Three preliminary site/building placement concepts (Options A/B/C) in the Indicative Design Package illustrate Owner thinking; Design-Builder not required to adopt any Option.",
         "note": "References NREOCRC-IDP-001, which is 'to be issued' - not present in this corpus state."},
        {"id": "OPR-001§5.2", "section": "5.2", "authority": "MANDATORY",
         "text": "Interior organization shall reflect zoning principles in Section 8, illustrated in Figure OPR-2.1, such that movement between zones occurs only at defined transition points."},
        {"id": "OPR-001§5.3", "section": "5.3", "authority": "INFORMATIONAL",
         "text": "EOC Operations Room approximate primary operations floor area 'in the order of 250 m²'; governing net area requirement is set out in the Functional Program (Appendix OPR-1)."},
        {"id": "OPR-001§8.1", "section": "8.1", "authority": "STATED (general)",
         "text": "Facility organized into three security zones (Public/Controlled/Secure) per Figure OPR-2.1; functional adjacencies per Figure OPR-2.2."},
        {"id": "OPR-001§8.2", "section": "8.2", "authority": "MANDATORY",
         "text": "Full Functional Program (Appendix OPR-1) forms a Contractual Document."},
        {"id": "OPR-001§8.5", "section": "8.5", "authority": "MANDATORY",
         "text": "Net areas in Appendix OPR-1 are minimum net areas unless expressly maximum/nominal."},
        {"id": "OPR-001§Appendix-OPR-1-Row14", "section": "Appendix OPR-1, Row 14", "authority": "MANDATORY",
         "text": "EOC Operations Room: 280 m² net area (minimum), Secure zone. Notes: 'See Section 5.3 regarding approximate area referenced in prose.'"},
        {"id": "OPR-001§12.1", "section": "12.1", "authority": "MANDATORY",
         "text": "Standby power generation for full EOC-activated load for a continuous period of no less than 96 hours without refuelling."},
        {"id": "OPR-001§12.2", "section": "12.2 (table)", "authority": "INFORMATIONAL (labelled 'for Design-Builder planning purposes')",
         "text": "Estimated EOC-activated critical load 850-1,050 kW (Class D estimate); fuel storage sized to municipal bylaw minimum of 72 hours with 24-hour bulk refuelling arrangement; fuel type diesel (assumed)."},
        {"id": "OPR-001§12.3", "section": "12.3", "authority": "MANDATORY",
         "text": "Standby power system, including fuel storage, shall not be rendered inoperable by the same event conditions the Facility must remain operational through, including flood conditions per Section 4.5.",
         "note": "Explicitly cross-references Section 4.5 (site floodplain)."},
        {"id": "OPR-001§12.4", "section": "12.4", "authority": "RATED",
         "text": "Standby power duration/redundancy/fuel resupply exceeding 12.1-12.3 viewed favourably."},
        {"id": "OPR-001§15.1", "section": "15.1", "authority": "MANDATORY",
         "text": "Recognized sustainability certification required; resilience/standby-power requirements may create tension with energy-efficiency strategies - where tension exists, Sections 9-14 (resilience/continuity) govern.",
         "note": "The document resolves this tension explicitly itself - not an unresolved conflict."},
        {"id": "OPR-001§18.1", "section": "18.1", "authority": "MANDATORY",
         "text": "Protect a Future Expansion Area for ~1,500-2,000 m² EOC surge-capacity addition without relocating primary structure/standby power/Secure Zone."},
        {"id": "OPR-001§18.3", "section": "18.3", "authority": "INDICATIVE",
         "text": "Future Expansion Area is NOT part of current contracted scope and will not be constructed under this Project Agreement."},
        {"id": "OPR-001§20.2", "section": "20.2", "authority": "MANDATORY (procedural)",
         "text": "Items stated to be confirmed later (6.1, 12.4, 14.3, 15.1, 19.3) will be issued by Addendum prior to Proposal Submission Deadline.",
         "note": "No specific date is given anywhere in this document for the Proposal Submission Deadline - it is referenced, not dated, in the current corpus state."},
    ]
    report["requirements_registered"] = requirements

    # ============================================================
    # STEP 4 — Cross-modal Relationships (Batch B substrate, real store calls)
    # ============================================================
    relationships_created = []

    def rel(from_type, from_id, to_type, to_id, rtype, confidence, note):
        r = store.record_relationship(
            workspace, from_type=from_type, from_id=from_id, to_type=to_type, to_id=to_id,
            relationship_type=rtype, created_by="nreocrc-ingestion-lab", provisional=True, confidence=confidence,
        )
        relationships_created.append({"relationship": r, "note": note})
        return r

    rel(OBJECT_KIND_REQUIREMENT, "OPR-001§5.2", OBJECT_KIND_SOURCE, fig1_source["id"],
        RELATIONSHIP_TYPE_CORRESPONDS_TO, 0.95,
        "Explicit textual reference: '...illustrated in Figure OPR-2.1...'")
    rel(OBJECT_KIND_REQUIREMENT, "OPR-001§8.1", OBJECT_KIND_SOURCE, fig1_source["id"],
        RELATIONSHIP_TYPE_CORRESPONDS_TO, 0.95,
        "Explicit textual reference to Figure OPR-2.1 (Security Zoning).")
    rel(OBJECT_KIND_REQUIREMENT, "OPR-001§8.1", OBJECT_KIND_SOURCE, fig2_source["id"],
        RELATIONSHIP_TYPE_CORRESPONDS_TO, 0.95,
        "Explicit textual reference to Figure OPR-2.2 (Functional Adjacency).")
    rel(OBJECT_KIND_REQUIREMENT, "OPR-001§Appendix-OPR-1-Row14", OBJECT_KIND_REQUIREMENT, "OPR-001§5.3",
        RELATIONSHIP_TYPE_QUALIFIES, 0.9,
        "280 m² Mandatory table value qualifies/governs the 250 m² Informational prose approximation - "
        "per Section 2.3 (Informational carries no contractual obligation) and Section 2.4 (more specific/"
        "recent statement governs). Document resolves this itself: COMPATIBLE, one governs - not a conflict.")
    rel(OBJECT_KIND_REQUIREMENT, "OPR-001§12.3", OBJECT_KIND_REQUIREMENT, "OPR-001§4.3",
        RELATIONSHIP_TYPE_REFERENCES, 0.9,
        "Section 12.3 explicitly cross-references the Section 4.5 floodplain condition (via Section 4 generally, "
        "linked here to the Section 4 site-planning cluster of requirements).")
    rel(OBJECT_KIND_REQUIREMENT, "OPR-001§18.1", OBJECT_KIND_REQUIREMENT, "OPR-001§4.3",
        RELATIONSHIP_TYPE_REFERENCES, 0.9,
        "Section 4.3 (site siting) and Section 18.1 (future expansion area) describe the same requirement "
        "from two different sections - site planning and future-expansion chapters cross-reference each other.")
    # Genuinely novel real-world relationship semantics - open-world extension type, not coerced into a known one.
    rel(OBJECT_KIND_REQUIREMENT, "OPR-001§2.2", OBJECT_KIND_REQUIREMENT, "OPR-001§4.6",
        "takes_precedence_over", 0.85,
        "Section 2.2's stated hierarchy places the OPR itself above the (not-yet-issued) Indicative Design "
        "Package, which Section 4.6 confirms is non-mandatory. Modeled as an open-world extension "
        "relationship type ('takes_precedence_over') since no canonical KNOWN_RELATIONSHIP_TYPES value "
        "captures document-hierarchy precedence, and 'supersedes' is reserved exclusively for lineage.")

    report["relationships_created"] = [
        {"from": f"{r['relationship']['from_type']}:{r['relationship']['from_id']}",
         "to": f"{r['relationship']['to_type']}:{r['relationship']['to_id']}",
         "type": r["relationship"]["relationship_type"], "confidence": r["relationship"]["confidence"],
         "note": r["note"]}
        for r in relationships_created
    ]

    # ============================================================
    # STEP 5 — Design/Estimate Maturity (honest, open-world - RFP/pre-
    # Proposal stage does not fit any of KNOWN_DESIGN_MATURITY_STAGES)
    # ============================================================
    maturity = store.record_design_maturity(
        workspace, scope_type=OBJECT_KIND_PROJECT, scope_id=PROJECT_ID,
        value="rfp_pre_proposal", created_by="nreocrc-ingestion-lab",
    )
    report["maturity_recorded"] = maturity
    report["maturity_note"] = (
        "No canonical KNOWN_DESIGN_MATURITY_STAGES value fits an RFP/pre-Proposal stage "
        "(the canonical set starts at 'concept'). 'rfp_pre_proposal' is preserved verbatim "
        "as an open-world extension value, not forced into a known stage - an authentic, "
        "unplanned demonstration of Test R's behavior on real project data."
    )

    # ============================================================
    # STEP 6 — Expected Information Profile for RFP-stage referenced-but-
    # unissued documents, and the sufficiency evaluator run honestly
    # (including where its raw output would be misleading if taken at
    # face value - see false-confidence audit in the report).
    # ============================================================
    profile = store.create_expected_information_profile(
        workspace, title="RFP-stage referenced documents (per NREOCRC-OPR-001 Sections 1.2/3)",
        scope_type=OBJECT_KIND_PROJECT, scope_id=PROJECT_ID, created_by="nreocrc-ingestion-lab",
        governance_log=gov,
    )
    expectation_items = []
    for kind_desc, doc_id, authority_src in [
        ("Indicative Design Package (Options A/B/C)", "NREOCRC-IDP-001", "OPR-001 Section 1.2/3.6/4.6"),
        ("Procurement and Milestone Schedule", "NREOCRC-SCH-001", "OPR-001 Section 1.2/3/20.1"),
        ("Data Room Document Register", "NREOCRC-DR-001", "OPR-001 Section 1.2/3"),
        ("Draft Project Agreement", "NREOCRC-PA-001 (Draft)", "OPR-001 Section 3"),
    ]:
        item = store.add_expectation_item(
            workspace, profile_id=profile["id"], expected_kind="document",
            description=f"{kind_desc} ({doc_id})", created_by="nreocrc-ingestion-lab",
            bindingness=EXPECTATION_BINDINGNESS_EXPECTED,
            authority_source=authority_src,
            applicability="Explicitly referenced by NREOCRC-OPR-001 as 'to be issued' - no date stated in current corpus.",
        )
        expectation_items.append(item)

        raw_eval = evaluate_information_sufficiency(item, observed=[])
        expectation_items[-1] = {
            **item,
            "raw_evaluator_outcome": raw_eval["outcome"],
            "raw_evaluator_detail": raw_eval["detail"],
            "human_layer_override": (
                "EXPECTED LATER (undated) - NOT a deficiency. The raw evaluator outcome above "
                "(expected_not_found) would overstate confidence if reported as-is: no milestone "
                "date exists in the current corpus to gate this as NOT_EXPECTED_YET, but the "
                "source document explicitly and unambiguously states this document is forthcoming. "
                "See false-confidence audit."
            ),
        }
    report["expected_information_profile"] = profile
    report["expectation_items"] = expectation_items
    report["gaps"].append({
        "gap": "evaluate_information_sufficiency has no outcome for 'explicitly deferred, no date stated'",
        "condition": "NREOCRC-OPR-001 explicitly defers IDP-001/SCH-001/DR-001/PA-001 with no date - only a milestone_condition of NOT_YET_DUE (requiring a dated TemporalObligation) currently suppresses EXPECTED_NOT_FOUND",
        "current_behavior": "the evaluator returns EXPECTED_NOT_FOUND for these items when called without a milestone_condition, which is misleading on its own",
        "preferable_behavior": "a distinct outcome (e.g. EXPECTED_LATER_UNDATED) for items explicitly and textually deferred without a stated trigger date",
        "affected_architecture": "services/case_workspace.py:evaluate_information_sufficiency, SUFFICIENCY_* vocabulary",
    })

    # Now a case that CAN be legitimately, honestly evaluated: the
    # Functional Program itself, which IS present.
    functional_program_item = store.add_expectation_item(
        workspace, profile_id=profile["id"], expected_kind="information_within_document",
        description="Room-by-room Functional Program with net areas, adjacencies, security levels (Appendix OPR-1)",
        created_by="nreocrc-ingestion-lab", bindingness=EXPECTATION_BINDINGNESS_MANDATORY,
        authority_source="OPR-001 Section 8.2",
    )
    fp_eval = evaluate_information_sufficiency(
        functional_program_item,
        observed=[{"object_type": "source", "object_id": opr_source["id"], "accessible": True, "authority_confidence": "confirmed"}],
    )
    report["functional_program_sufficiency_check"] = {"item": functional_program_item, "result": fp_eval}

    store.save(workspace)

    # ============================================================
    # STEP 7 — Freeze Snapshot 001 (Freeze/Snapshot region isn't built
    # yet - Prompt 6/7 named it, never implemented. This snapshot is
    # therefore an EXTERNAL, manually-assembled reference artifact, not
    # a first-class stored Snapshot object. Reported as a gap.)
    # ============================================================
    final_workspace = store.get(PROJECT_ID)
    snapshot = {
        "snapshot_id": "NREOCRC-BASELINE-INGESTION-SNAPSHOT-001",
        "frozen_at": now(),
        "project_id": PROJECT_ID,
        "project_state_version": final_workspace.version,
        "corpus_manifest_reference": "tests/fixtures/nreocrc/manifest.json",
        "sources": final_workspace.sources,
        "relationships": final_workspace.relationships,
        "expected_information_profiles": final_workspace.expected_information_profiles,
        "maturity_records": final_workspace.maturity_records,
        "findings": final_workspace.findings,
        "review_threads": final_workspace.review_threads,
        "governance_event_count": len(gov.read(PROJECT_ID)),
    }
    report["snapshot_001"] = {
        "snapshot_id": snapshot["snapshot_id"],
        "project_state_version": snapshot["project_state_version"],
        "source_count": len(snapshot["sources"]),
        "relationship_count": len(snapshot["relationships"]),
        "profile_count": len(snapshot["expected_information_profiles"]),
        "finding_count": len(snapshot["findings"]),
        "review_thread_count": len(snapshot["review_threads"]),
    }
    report["gaps"].append({
        "gap": "No first-class Freeze/Snapshot object exists",
        "condition": "Prompt 6/7 named Freeze/Snapshot as a needed region; never implemented through Batch E",
        "current_behavior": "Snapshot 001 here is an externally-assembled JSON artifact (this script's own output), referencing project_state_version but not a governed, stored, queryable Snapshot record",
        "preferable_behavior": "a real Snapshot primitive (per Prompt 6 L's design: project_clock_timestamp + version-references, not duplicated content)",
        "affected_architecture": "services/case_workspace.py (no Snapshot dataclass exists)",
    })

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    (SNAPSHOT_DIR / "snapshot_001.json").write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
    (SNAPSHOT_DIR / "reconstruction_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(json.dumps(report, indent=2, default=str))
    print(f"\nWrote snapshot to {SNAPSHOT_DIR / 'snapshot_001.json'}")
    print(f"Wrote reconstruction report to {SNAPSHOT_DIR / 'reconstruction_report.json'}")


if __name__ == "__main__":
    main()
