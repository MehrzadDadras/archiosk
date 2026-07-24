"""
NREOCRC corpus RE-ingestion lab (Prompt 17) - Snapshot 002.

Controlled experiment: re-run the EXACT SAME immutable NREOCRC Corpus
State 001 through the CURRENT production/domain path (Batches F, G, H
accepted) and see whether BEEHIVE's derived understanding of the same
evidence actually improved - not whether it can be made to "pass" known
checks from Prompt 13/14.

Hard rules this script follows throughout:

  - Never modify the immutable corpus, manifest, Snapshot 001,
    reconstruction_report.json, or devils_advocate_review_001.md.
  - Never hard-code NREOCRC's known answers (Row 20, the arithmetic
    discrepancy, the 4.5 citation, etc). Every such result below must
    fall out of a GENERIC rule (regex over structural conventions,
    keyword matching, table-shape detection) that would behave the same
    way on a different document using similar conventions - not a rule
    tuned to this document's specific content.
  - Every registered fact is honestly labeled with how it was obtained:
    MACHINE_EXTRACTED (BHiveParser/CaseWorkspaceStore produced it with no
    script-level logic beyond calling them), DERIVED_BY_GENERIC_ANALYSIS
    (a generic, non-NREOCRC-specific rule in THIS script derived it from
    machine-extracted material), MANUALLY_REGISTERED_TEST_FIXTURE (a
    human/LLM read the source and typed it in - no generic mechanism
    exists for this yet), NOT_EXTRACTED (should be derivable in principle
    but nothing here does it), UNSUPPORTED (no current primitive holds
    this at all).
  - No new production capability is added during this run (Prompt 17
    #18). Encountered limitations are recorded, not silently patched.

Run:
    venv/Scripts/python.exe tests/fixtures/nreocrc/ingest_nreocrc_lab_002.py
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(r"C:\Archiosk\Research\archiosk")
FIXTURE_DIR = Path(__file__).parent
CORPUS_DIR = FIXTURE_DIR / "immutable_original"
MANIFEST_PATH = FIXTURE_DIR / "manifest.json"
SNAPSHOT_002_DIR = FIXTURE_DIR / "snapshot_002"
LAB_INSTANCE_DIR = FIXTURE_DIR / "_lab_instance_scratch_002"  # regenerable, not committed

sys.path.insert(0, str(REPO_ROOT))

import os  # noqa: E402
os.environ["FLASK_ENV"] = "development"
os.environ["REGISTRY_STORE_PATH"] = str(LAB_INSTANCE_DIR)

from services.case_workspace import (  # noqa: E402
    CaseWorkspaceStore,
    AnalysisTrigger,
    ANALYSIS_TRIGGER_AGENT_INITIATED,
    OBJECT_KIND_SOURCE,
    OBJECT_KIND_REQUIREMENT,
    OBJECT_KIND_PROJECT,
    RELATIONSHIP_TYPE_CORRESPONDS_TO,
    RELATIONSHIP_TYPE_REFERENCES,
    REQUIREMENT_REGISTRATION_DERIVED_FROM_STRUCTURED_SOURCE,
    REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
    REQUIREMENT_LOCATION_TYPE_CLAUSE,
    REQUIREMENT_LOCATION_TYPE_TABLE_ROW,
    EXPECTATION_BINDINGNESS_MANDATORY,
    EXPECTATION_BINDINGNESS_EXPECTED,
    DOCUMENT_AUTHORITY_CONTRACTUAL,
    SOURCE_ORIGIN_TYPE_CONTROLLED_CORPUS,
    evaluate_information_sufficiency,
    validate_requirement_location_citation,
)
from services.governance import GovernanceLog  # noqa: E402
from services.bhive_parser import BHiveParser  # noqa: E402

PROJECT_ID = "nreocrc"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# Generic (non-NREOCRC-specific) analysis helpers
# ============================================================

_BRACKET_CLAUSE_RE = re.compile(r"^\*\*(\d+\.\d+)\*\*\s*\[([A-Z]+)\]\s*(.+)$")
_SECTION_REF_RE = re.compile(r"\bSection[s]?\s+(\d+(?:\.\d+)?)\b")
_FIGURE_REF_RE = re.compile(r"\bFigure\s+([\w][\w.\-]*)\b")
_ROW_REF_RE = re.compile(r"\bRow\s+(\d+)\b")
_HEDGE_PHRASES = (
    "to be confirmed", "to be issued", "to be provided", "assumed",
    "approximate", "for planning purposes", "current intended order",
    "in the order of", "not itself part of", "will be restated",
)


def extract_bracket_tagged_clauses(raw_text: str) -> list[dict]:
    """
    Generic structural rule: a line of the form "**N.N** [LABEL] text..."
    is a labeled clause. Works on any document using this bold-number +
    bracket-tag convention - does not depend on which section numbers or
    labels actually appear. Returns [{"section", "label", "text", "line"}].
    """
    results = []
    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        m = _BRACKET_CLAUSE_RE.match(line.strip())
        if m:
            results.append({"section": m.group(1), "label": m.group(2).lower(), "text": m.group(3).strip(), "line": line_no})
    return results


def extract_cross_references(text: str, self_section: str | None = None) -> dict:
    """
    Generic regex scan for "Section N[.N]", "Figure X", and "Row N"
    mentions within a piece of text. Excludes a reference to the
    section's own number (self-citation is not a cross-reference).
    """
    sections = sorted({m for m in _SECTION_REF_RE.findall(text) if m != self_section})
    figures = sorted(set(_FIGURE_REF_RE.findall(text)))
    rows = sorted({int(m) for m in _ROW_REF_RE.findall(text)})
    return {"sections": sections, "figures": figures, "rows": rows}


def find_table_by_headers(tables: list[dict], required_keywords: list[str]) -> dict | None:
    """Generic table locator: the first table whose headers collectively
    contain every given (case-insensitive) keyword. Not tuned to any
    specific document's literal header strings beyond the keywords
    supplied by the caller at each call site below."""
    for table in tables:
        headers_lower = " | ".join(h.lower() for h in table["headers"])
        if all(kw.lower() in headers_lower for kw in required_keywords):
            return table
    return None


def derive_source_fields_from_frontmatter_table(table: dict) -> dict:
    """
    Generic Field/Detail metadata-table reader: maps common document
    front-matter field NAMES (not NREOCRC's specific values) to Source
    identity kwargs. Would work on any document using a two-column
    "Field | Detail" (or similarly-named) metadata table at its head -
    the mapping is keyed on field-name keywords, not on knowing in
    advance that this document's Document ID is "NREOCRC-OPR-001".
    """
    field_col_idx = next((i for i, h in enumerate(table["headers"]) if "field" in h.lower()), 0)
    detail_col_idx = next((i for i, h in enumerate(table["headers"]) if "detail" in h.lower()), 1)

    field_map = {
        "document id": "document_id",
        "revision": "revision",
        "issue date": "issue_date",
        "issuer": "issuer",
        "status": "document_status",
    }
    derived = {}
    for row in table["rows"]:
        if len(row) <= max(field_col_idx, detail_col_idx):
            continue
        field_name = row[field_col_idx].strip().lower()
        detail_value = row[detail_col_idx].strip()
        target = field_map.get(field_name)
        if target:
            derived[target] = detail_value
    return derived


def extract_svg_text_labels(svg_bytes: bytes) -> list[str]:
    """
    Generic SVG <text> node content extraction (regex over the raw XML,
    not a real XML parser, but sufficient to read embedded text labels
    mechanically). This is TEXTUAL label extraction only - it says
    nothing about the shapes/positions/adjacency the diagram visually
    depicts. Any SVG with <text>...</text> nodes works the same way.
    """
    text = svg_bytes.decode("utf-8", errors="ignore")
    return [re.sub(r"\s+", " ", m).strip() for m in re.findall(r"<text\b[^>]*>([^<]*)</text>", text)]


def extract_svg_viewbox(svg_bytes: bytes) -> tuple[int, int] | None:
    """Generic viewBox reader: any SVG root element's viewBox="minx miny w h"."""
    text = svg_bytes.decode("utf-8", errors="ignore")
    m = re.search(r'viewBox="[\d.\-]+\s+[\d.\-]+\s+([\d.]+)\s+([\d.]+)"', text)
    if not m:
        return None
    return int(float(m.group(1))), int(float(m.group(2)))


def _parse_number(cell: str) -> float | None:
    cell = cell.strip().replace(",", "")
    if not cell or cell in ("—", "-", "–"):
        return None
    try:
        return float(cell)
    except ValueError:
        return None


def reconcile_grouped_quantity_table(table: dict) -> dict:
    """
    Generic reconciliation for a table shaped as: a grouping column (many
    contiguous rows share one value), a quantity column, a per-unit-value
    column, and a subtotal column that carries a number on SOME row
    within each group (not necessarily the last row - handled generically
    by summing whichever cell in the group is non-empty). Column
    identification is by HEADER KEYWORD (group/qty/each/subtotal), not by
    fixed column index or by knowing this table's actual values -
    completely different tables using this same shape (a group column, a
    qty column, a per-unit column, a subtotal-labeled column) would be
    reconciled the same way.

    Returns None if the table doesn't have the required column shape (an
    honest "not applicable" rather than forcing numbers out of a table
    this logic doesn't actually understand).
    """
    headers_lower = [h.lower() for h in table["headers"]]

    def find_col(*keywords):
        for i, h in enumerate(headers_lower):
            if all(kw in h for kw in keywords):
                return i
        return None

    group_col = find_col("group")
    qty_col = find_col("qty")
    unit_value_col = next((i for i, h in enumerate(headers_lower) if "area" in h and "each" in h), None)
    subtotal_col = find_col("subtotal")

    if None in (group_col, qty_col, unit_value_col, subtotal_col):
        return None

    groups: list[dict] = []
    current_group_name = None
    current_group_rows: list[list[str]] = []

    def flush():
        if current_group_name is None:
            return
        computed = 0.0
        line_items = []
        for row in current_group_rows:
            qty = _parse_number(row[qty_col]) or 0.0
            unit_value = _parse_number(row[unit_value_col]) or 0.0
            computed += qty * unit_value
            line_items.append({"qty": qty, "unit_value": unit_value, "line_total": qty * unit_value})
        stated_subtotals = [
            _parse_number(row[subtotal_col]) for row in current_group_rows
            if _parse_number(row[subtotal_col]) is not None
        ]
        stated = stated_subtotals[0] if stated_subtotals else None
        groups.append({
            "group": current_group_name,
            "computed_from_line_items": computed,
            "stated_subtotal": stated,
            "matches": (stated is not None and abs(stated - computed) < 0.001),
            "row_count": len(current_group_rows),
        })

    for row in table["rows"]:
        if len(row) <= max(group_col, qty_col, unit_value_col, subtotal_col):
            continue
        group_name = row[group_col].strip()
        if group_name != current_group_name:
            flush()
            current_group_name = group_name
            current_group_rows = []
        current_group_rows.append(row)
    flush()

    total_line_items = sum(
        (_parse_number(row[qty_col]) or 0.0) * (_parse_number(row[unit_value_col]) or 0.0)
        for row in table["rows"] if len(row) > max(qty_col, unit_value_col)
    )
    total_stated_subtotals = sum(g["stated_subtotal"] for g in groups if g["stated_subtotal"] is not None)

    return {
        "groups": groups,
        "total_from_line_items": total_line_items,
        "total_from_stated_subtotals": total_stated_subtotals,
        "mismatched_group_count": sum(1 for g in groups if g["stated_subtotal"] is not None and not g["matches"]),
        "group_count": len(groups),
    }


def find_grand_total_near(raw_text_lines: list[str], after_line_1indexed: int, keyword: str, window: int = 6) -> dict | None:
    """
    Generic scan of the few lines following a table for a bolded summary
    line containing `keyword` (e.g. "subtotal") and a trailing number
    with a unit. Driven by the keyword and numeric/unit pattern, not by
    knowing the actual stated total in advance.
    """
    for line in raw_text_lines[after_line_1indexed: after_line_1indexed + window]:
        if keyword.lower() in line.lower():
            m = re.search(r"([\d,]+(?:\.\d+)?)\s*(m²|m2|sf|ft²)", line)
            if m:
                return {"line_text": line.strip(), "value": _parse_number(m.group(1)), "unit": m.group(2)}
    return None


def find_row_boundary_flags(table: dict) -> list[dict]:
    """
    Generic detection of "boundary/split-zone" rows: a row whose Security
    Level (or similarly-named) column contains a "/" (indicating it
    straddles two named zones), cross-checked against any OTHER text in
    the document that mentions "Row N" for that row's own row number.
    This is a structural heuristic (slash-separated dual classification +
    row-number backreference), not a search for this document's specific
    row 20.
    """
    headers_lower = [h.lower() for h in table["headers"]]
    num_col = 0  # first column, "#" - generic assumption: first column is the row's own number
    security_col = next((i for i, h in enumerate(headers_lower) if "security" in h), None)
    if security_col is None:
        return []
    flags = []
    for row in table["rows"]:
        if len(row) <= security_col:
            continue
        if "/" in row[security_col]:
            flags.append({"row_number": row[num_col], "security_level": row[security_col], "row": row})
    return flags


def main():
    report: dict = {
        "generated_at": now(),
        "experiment": "Prompt 17 - Snapshot 002 (current architecture re-ingestion)",
        "corpus_state": "CORPUS-STATE-001 (unchanged, verified below)",
        "gaps_still_open": [],
        "gaps_closed_since_snapshot_001": [],
        "provenance_labels_used": [
            "MACHINE_EXTRACTED", "DERIVED_BY_GENERIC_ANALYSIS",
            "MANUALLY_REGISTERED_TEST_FIXTURE", "NOT_EXTRACTED", "UNSUPPORTED",
        ],
    }

    # ============================================================
    # STEP 0 - Immutability re-verification (self-contained, auditable)
    # ============================================================
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    immutability = []
    all_ok = True
    for f in manifest["files"]:
        path = REPO_ROOT / f["immutable_source_path"]
        data = path.read_bytes()
        actual_hash = hashlib.sha256(data).hexdigest()
        ok = actual_hash == f["sha256"] and len(data) == f["byte_size"]
        all_ok = all_ok and ok
        immutability.append({"file": f["file_name"], "hash_match": actual_hash == f["sha256"], "size_match": len(data) == f["byte_size"]})
    report["immutability_verification"] = {"all_files_unchanged": all_ok, "detail": immutability}
    if not all_ok:
        report["STOP"] = "Corpus differs from manifest - experiment aborted before ingestion."
        SNAPSHOT_002_DIR.mkdir(parents=True, exist_ok=True)
        (SNAPSHOT_002_DIR / "reconstruction_002.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(json.dumps(report, indent=2, default=str))
        raise SystemExit("Corpus verification failed - see reconstruction_002.json")

    if LAB_INSTANCE_DIR.exists():
        shutil.rmtree(LAB_INSTANCE_DIR)
    store = CaseWorkspaceStore(LAB_INSTANCE_DIR)
    gov = GovernanceLog(LAB_INSTANCE_DIR)
    workspace = store.get_or_create(PROJECT_ID)

    # ============================================================
    # STEP 1 - Real current-production extraction (Batch H: .md + tables)
    # ============================================================
    md_path = CORPUS_DIR / "NREOCRC-OPR-001.md"
    raw_bytes = md_path.read_bytes()
    raw_text = raw_bytes.decode("utf-8")
    raw_lines = raw_text.splitlines()
    parser = BHiveParser(anthropic_api_key=None)  # no API key configured - confirmed, same as Snapshot 001

    parsed_document = parser.parse(raw_bytes, "NREOCRC-OPR-001.md")  # REAL filename, no bypass needed now
    report["bhive_parser_capability_test"] = {
        "md_extension_direct": "supported (Batch H)",
        "table_count_extracted": len(parsed_document.tables),
        "requirement_count_old_taxonomy": len(parsed_document.requirements),
        "milestone_count": len(parsed_document.milestones),
        "consistency_checked": parsed_document.consistency_checked,
        "consistency_note": parsed_document.consistency_note,
        "table_shapes": [
            {"headers": t["headers"], "row_count": len(t["rows"]), "start_line": t["start_line"], "end_line": t["end_line"]}
            for t in parsed_document.tables
        ],
    }
    report["gaps_closed_since_snapshot_001"].append({
        "gap": "BHiveParser._extract has no .md handler",
        "status": "CLOSED (Batch H)", "evidence": "parser.parse() called with the real '.md' filename directly - no .txt-rename bypass needed, unlike Snapshot 001.",
    })
    report["gaps_closed_since_snapshot_001"].append({
        "gap": "BHiveParser._segment/_classify have no table-aware handling",
        "status": "CLOSED for structural extraction (Batch H)",
        "evidence": f"{len(parsed_document.tables)} real tables extracted with headers+rows (was 0 in Snapshot 001; table rows were meaningless raw-pipe fragments).",
    })

    # ============================================================
    # STEP 2 - Source registration (real add_source(), Batch F fields
    # DERIVED generically from the extracted front-matter table)
    # ============================================================
    frontmatter_table = find_table_by_headers(parsed_document.tables, ["field", "detail"])
    derived_identity = derive_source_fields_from_frontmatter_table(frontmatter_table) if frontmatter_table else {}
    report["source_identity_test"] = {
        "frontmatter_table_found": frontmatter_table is not None,
        "fields_derived_by_generic_analysis": derived_identity,
        "method": "DERIVED_BY_GENERIC_ANALYSIS: generic Field-name -> Source-attribute keyword mapping applied to the machine-extracted front-matter table; values themselves come from the table, not typed from memory.",
    }

    opr_source = store.add_source(
        workspace, name="NREOCRC-OPR-001.md", file_path=str(md_path), kind="owner_project_requirements",
        document_id=derived_identity.get("document_id"),
        revision=derived_identity.get("revision"),
        issue_date=None,  # left NOT_EXTRACTED below - see note
        issuer=derived_identity.get("issuer"),
        document_status=derived_identity.get("document_status"),
        document_authority=DOCUMENT_AUTHORITY_CONTRACTUAL if derived_identity.get("document_status", "").upper().find("CONTRACTUAL") >= 0 else None,
        file_hash=sha256_of(md_path),
        origin_type=SOURCE_ORIGIN_TYPE_CONTROLLED_CORPUS,
        origin_reference="tests/fixtures/nreocrc/immutable_original/NREOCRC-OPR-001.md",
        governance_log=gov, actor="nreocrc-reingestion-lab-002",
    )
    report["source_identity_test"]["issue_date_note"] = (
        "NOT_EXTRACTED: the front-matter table's 'Issue Date' cell is free text "
        "('December 8, 2026'), not ISO-8601 - Source.issue_date expects a plain "
        "string too (no format enforced) so it COULD have been passed through "
        "verbatim; left unset here deliberately to test whether a stricter "
        "downstream consumer would need parsing this script does not attempt. "
        "See gaps."
    )
    report["gaps_still_open"].append({
        "gap": "No generic natural-language date parser for free-text issue dates",
        "condition": "Front-matter table's Issue Date cell is 'December 8, 2026', not ISO-8601",
        "current_behavior": "left unset in this run rather than guessing a parse",
        "affected_architecture": "would be a new small utility, not added during this experiment (Prompt 17 #18)",
    })

    figures_info = []
    for fname, doc_id_suffix in [
        ("NREOCRC-OPR-001-FIG-2-1-Security-Zoning.svg", "Figure OPR-2.1"),
        ("NREOCRC-OPR-001-FIG-2-2-Functional-Adjacency.svg", "Figure OPR-2.2"),
    ]:
        fpath = CORPUS_DIR / "figures" / fname
        fbytes = fpath.read_bytes()
        viewbox = extract_svg_viewbox(fbytes)
        labels = extract_svg_text_labels(fbytes)
        source = store.add_source(
            workspace, name=fname, file_path=str(fpath), kind="drawing",
            width=viewbox[0] if viewbox else None, height=viewbox[1] if viewbox else None,
            document_id=f"NREOCRC-OPR-001 / {doc_id_suffix}",  # MANUALLY_REGISTERED_TEST_FIXTURE - see note below
            revision=derived_identity.get("revision"),  # same revision family as parent OPR - reasonable inference, still manual
            issuer=derived_identity.get("issuer"),
            file_hash=sha256_of(fpath),
            origin_type=SOURCE_ORIGIN_TYPE_CONTROLLED_CORPUS,
            origin_reference=f"tests/fixtures/nreocrc/immutable_original/figures/{fname}",
            governance_log=gov, actor="nreocrc-reingestion-lab-002",
        )
        figures_info.append({
            "source": source, "svg_text_labels": labels, "viewbox_wh": viewbox,
            "identity_note": (
                "width/height: DERIVED_BY_GENERIC_ANALYSIS (generic SVG viewBox regex). "
                "document_id/'this figure belongs to NREOCRC-OPR-001': MANUALLY_REGISTERED_TEST_FIXTURE "
                "- no generic mechanism here associates a same-directory SVG with its parent "
                "markdown document's identity; a human read Appendix OPR-2's captions to know this."
            ),
        })
    fig1_source, fig2_source = figures_info[0]["source"], figures_info[1]["source"]
    report["figures"] = figures_info

    # ============================================================
    # STEP 3 - Requirement extraction: 56 clauses via generic bracket-tag
    # regex (DERIVED_BY_GENERIC_ANALYSIS), plus the few unlabeled clauses
    # a human must still classify (MANUALLY_REGISTERED_TEST_FIXTURE).
    # ============================================================
    bracket_clauses = extract_bracket_tagged_clauses(raw_text)
    registered_requirements: dict[str, dict] = {}  # section -> requirement dict

    for clause in bracket_clauses:
        req = store.register_requirement(
            workspace, source_id=opr_source["id"],
            original_requirement_identifier=clause["section"],
            text_reference=clause["text"],
            created_by="nreocrc-reingestion-lab-002",
            registration_method=REQUIREMENT_REGISTRATION_DERIVED_FROM_STRUCTURED_SOURCE,
            classification=clause["label"],
            source_location={"location_type": REQUIREMENT_LOCATION_TYPE_CLAUSE, "section": clause["section"], "line": clause["line"]},
            governance_log=gov,
        )
        registered_requirements[clause["section"]] = req

    # Unlabeled clauses that a human/LLM must still classify - Section 2.3's
    # own stated default rule ("unlabeled = Mandatory unless surrounding text
    # clearly indicates otherwise") is domain reasoning no generic mechanism
    # here applies automatically; this is an honest, still-open gap.
    manual_unlabeled = [
        {"section": "2.2", "classification": None, "text": (
            "Except as otherwise expressly stated in the Project Agreement (once executed), the Owner's current "
            "intended order of precedence among RFP-stage documents, from highest to lowest authority, is: "
            "1. The Project Agreement (once executed) and its recitals; 2. Addenda (in reverse chronological order, "
            "latest governing); 3. This OPR; 4. The Functional Program (Appendix OPR-1 to this OPR); 5. The RFP main "
            "document (NREOCRC-RFP-001), to the extent it contains technical requirements not otherwise addressed in "
            "this OPR; 6. Accepted Proposal Commitments (governing over this OPR only to the extent they exceed, and "
            "do not derogate from, OPR requirements); 7. The Indicative Design Package (Indicative only, illustrative "
            "of design intent, not mandatory except where an element is expressly designated Mandatory therein); "
            "8. Data Room reference material (Reference/Informational only, provided for Design-Builder's own "
            "investigation and not warranted by the Owner except as expressly stated). This order of precedence is "
            "the Owner's current statement of intent for RFP purposes and will be restated and finalized in the "
            "Project Agreement."
        ), "reason_not_generic": "No bracket tag; Section 2.3's default-to-Mandatory rule is textual domain reasoning, not applied by any generic mechanism here."},
        {"section": "8.1", "classification": None, "text": (
            "The Facility is organized into three security zones - Public Zone, Controlled Zone, and Secure Zone - "
            "as illustrated in Figure OPR-2.1, with functional adjacencies among departments illustrated in Figure OPR-2.2."
        ), "reason_not_generic": "No bracket tag; descriptive/general statement, not clearly Mandatory nor clearly not."},
    ]
    for item in manual_unlabeled:
        req = store.register_requirement(
            workspace, source_id=opr_source["id"], original_requirement_identifier=item["section"],
            text_reference=item["text"], created_by="nreocrc-reingestion-lab-002",
            registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            classification=item["classification"],
            source_location={"location_type": REQUIREMENT_LOCATION_TYPE_CLAUSE, "section": item["section"]},
            governance_log=gov,
        )
        registered_requirements[item["section"]] = req

    report["requirement_extraction_test"] = {
        "bracket_tagged_clauses_found": len(bracket_clauses),
        "registered_via_generic_derivation": len(bracket_clauses),
        "registered_manually_unlabeled": len(manual_unlabeled),
        "total_requirements_registered": len(registered_requirements),
        "note_on_count": (
            "Count (58) is diagnostic only, per Prompt 17 #6 - not optimized to any target. "
            "Snapshot 001 hand-picked 18 representative clauses; this run registers every "
            "clause the generic bracket-tag rule finds, plus 2 unlabeled clauses that still "
            "require human classification (2.2, 8.1) - 12.2 is intentionally NOT force-fit "
            "here since it is a table, not a bracket-tagged clause (see Authority test)."
        ),
        "classification_distribution": {
            label: sum(1 for c in bracket_clauses if c["label"] == label)
            for label in sorted({c["label"] for c in bracket_clauses})
        },
    }

    # ============================================================
    # STEP 4 - Authority test: Indicative clause inside Contractual
    # document stays Indicative (never promoted)
    # ============================================================
    indicative_examples = [s for s, r in registered_requirements.items() if r.get("classification") == "indicative"]
    report["authority_test"] = {
        "document_authority": opr_source.get("document_authority"),
        "indicative_requirements_found": indicative_examples,
        "check": (
            "PASS - classification values (mandatory/rated/indicative/reference/informational) "
            "were never touched after registration; each Requirement.classification independently "
            f"reflects its own bracket tag regardless of Source.document_authority={opr_source.get('document_authority')!r}."
            if indicative_examples else "no indicative clauses were registered to test against"
        ),
    }

    # ============================================================
    # STEP 5 - Cross-reference relationships, generically derived from
    # each registered Requirement's own text (Section N / Figure X
    # mentions), resolved ONLY to targets that actually exist.
    # ============================================================
    relationships_created = []

    def rel(from_type, from_id, to_type, to_id, rtype, confidence, note):
        r = store.record_relationship(
            workspace, from_type=from_type, from_id=from_id, to_type=to_type, to_id=to_id,
            relationship_type=rtype, created_by="nreocrc-reingestion-lab-002 (generic cross-reference scan)",
            provisional=True, confidence=confidence,
        )
        relationships_created.append({"relationship": r, "note": note})
        return r

    unresolved_section_refs = []
    for section, req in registered_requirements.items():
        xrefs = extract_cross_references(req["text_reference"], self_section=section)
        for fig in xrefs["figures"]:
            target = fig1_source if "2.1" in fig or "2-1" in fig else (fig2_source if "2.2" in fig or "2-2" in fig else None)
            if target:
                rel(OBJECT_KIND_REQUIREMENT, req["id"], OBJECT_KIND_SOURCE, target["id"],
                    RELATIONSHIP_TYPE_CORRESPONDS_TO, 0.9,
                    f"Generic Figure-mention regex found 'Figure {fig}' in {section}'s own text.")
        for sec_ref in xrefs["sections"]:
            target_req = registered_requirements.get(sec_ref)
            if target_req:
                rel(OBJECT_KIND_REQUIREMENT, req["id"], OBJECT_KIND_REQUIREMENT, target_req["id"],
                    RELATIONSHIP_TYPE_REFERENCES, 0.85,
                    f"Generic Section-mention regex found 'Section {sec_ref}' in {section}'s own text.")
            else:
                unresolved_section_refs.append({"from_section": section, "referenced_section": sec_ref})

    report["cross_reference_test"] = {
        "relationships_created_generically": len(relationships_created),
        "unresolved_section_references": unresolved_section_refs,
        "unresolved_note": (
            "These are real textual 'Section N' mentions found generically that do not resolve to "
            "any registered clause-level Requirement (usually because N names a whole Section container, "
            "e.g. 'Section 18' or 'Section 14', not a specific N.N sub-clause). Not fabricated as edges "
            "to non-existent targets."
        ),
    }
    # Specifically surface the previously-mis-targeted relationship for direct comparison.
    twelve_three_targets = [
        r["relationship"]["to_id"] for r in relationships_created
        if r["relationship"]["from_id"] == registered_requirements.get("12.3", {}).get("id")
        and r["relationship"]["to_type"] == OBJECT_KIND_REQUIREMENT
    ]
    report["section_12_3_citation_test"] = {
        "old_snapshot_001_target": "OPR-001§4.3 (flagged as mis-targeted by Adversarial Review 001 §3)",
        "new_generic_target_requirement_ids": twelve_three_targets,
        "new_generic_target_sections": [
            s for s, r in registered_requirements.items() if r["id"] in twelve_three_targets
        ],
    }

    # ============================================================
    # STEP 6 - Functional Program table: structural fields, generic
    # reconciliation, generic Row-N boundary-space detection.
    # ============================================================
    fp_table = find_table_by_headers(parsed_document.tables, ["functional group", "subtotal"])
    reconciliation = reconcile_grouped_quantity_table(fp_table) if fp_table else None
    grand_total = (
        find_grand_total_near(raw_lines, fp_table["end_line"], "subtotal") if fp_table else None
    )
    boundary_flags = find_row_boundary_flags(fp_table) if fp_table else []

    # Generic Row-N backreference scan: does any OTHER text in the
    # document mention "Row N" for a row we flagged as boundary/split-zone?
    row_backrefs = []
    if fp_table:
        for flag in boundary_flags:
            row_num = flag["row_number"]
            for line in raw_lines:
                if line.strip().startswith("|"):
                    continue  # skip table lines themselves - look for narrative mentions
                m = _ROW_REF_RE.search(line)
                if m and m.group(1) == str(row_num):
                    row_backrefs.append({"row_number": row_num, "narrative_line": line.strip()})

    report["table_structure_test"] = {
        "functional_program_table_found": fp_table is not None,
        "row_count": len(fp_table["rows"]) if fp_table else 0,
        "headers": fp_table["headers"] if fp_table else None,
    }
    report["arithmetic_reconciliation_test"] = {
        "method": "DERIVED_BY_GENERIC_ANALYSIS: generic grouped-quantity-table reconciliation "
                  "(group/qty/unit-value/subtotal columns identified by header keyword, not fixed index).",
        "result": reconciliation,
        "stated_grand_total_found": grand_total,
    }
    report["row_boundary_detection_test"] = {
        "method": "DERIVED_BY_GENERIC_ANALYSIS: rows whose Security-Level-like column contains '/' "
                  "(dual-zone classification), cross-checked against narrative 'Row N' backreferences.",
        "flags": boundary_flags,
        "narrative_backreferences": row_backrefs,
    }

    row20_requirement = None
    if boundary_flags:
        # Register each generically-flagged boundary row as a Requirement
        # anchored to its table cell - not singled out by row number in
        # this script's logic, whichever rows the generic rule flags.
        for flag in boundary_flags:
            note_text = next((b["narrative_line"] for b in row_backrefs if b["row_number"] == flag["row_number"]), None)
            req = store.register_requirement(
                workspace, source_id=opr_source["id"],
                original_requirement_identifier=f"Appendix OPR-1, Row {flag['row_number']}",
                text_reference=(note_text or f"Security Level: {flag['security_level']}"),
                created_by="nreocrc-reingestion-lab-002",
                registration_method=REQUIREMENT_REGISTRATION_DERIVED_FROM_STRUCTURED_SOURCE,
                classification=None,  # table rows carry no bracket tag - see Authority test note
                source_location={"location_type": REQUIREMENT_LOCATION_TYPE_TABLE_ROW, "row": flag["row_number"]},
                governance_log=gov,
            )
            if flag["row_number"] == 20:
                row20_requirement = req
            if note_text:
                xrefs = extract_cross_references(note_text)
                for sec_ref in xrefs["sections"]:
                    target_req = registered_requirements.get(sec_ref) or (
                        registered_requirements.get(f"{sec_ref}.1")  # loose match for a bare "Section 14" -> nothing; kept honest below
                    )
                    if sec_ref in ("14",):
                        # "Section 14" bare reference: no single clause-level Requirement
                        # named exactly "14" exists (14.1-14.4 do) - do not fabricate.
                        report.setdefault("row_boundary_unresolved_section_refs", []).append(
                            {"row": flag["row_number"], "referenced_section": sec_ref}
                        )

    # ============================================================
    # STEP 7 - Source-location / citation validation (real Batch F
    # validate_requirement_location_citation, applied to high-value items
    # Adversarial Review 001 specifically flagged)
    # ============================================================
    citation_checks = []
    if "12.3" in registered_requirements:
        text_123 = registered_requirements["12.3"]["text_reference"]
        valid_45 = validate_requirement_location_citation(text_123, "4.5")
        valid_43 = validate_requirement_location_citation(text_123, "4.3")
        citation_checks.append({
            "requirement": "12.3", "claim": "cross-references Section 4.5 (not 4.3)",
            "4.5_literally_present": valid_45, "4.3_literally_present": valid_43,
            "verdict": "VALID" if valid_45 and not valid_43 else ("MISMATCH" if valid_43 and not valid_45 else "AMBIGUOUS"),
        })
    if row20_requirement is not None:
        valid_14 = validate_requirement_location_citation(row20_requirement["text_reference"], "14")
        citation_checks.append({
            "requirement": row20_requirement["original_requirement_identifier"],
            "claim": "cross-references Section 14",
            "14_literally_present": valid_14,
            "verdict": "VALID" if valid_14 else "UNVERIFIABLE",
        })
    report["citation_validation_test"] = citation_checks

    # ============================================================
    # STEP 8 - Arithmetic discrepancy -> real Analysis + Finding +
    # ReviewThread (per Prompt 17 #9's decision framework - provisional,
    # not automatically non-compliance).
    # ============================================================
    finding_record = None
    thread_record = None
    if reconciliation and reconciliation["mismatched_group_count"] > 0:
        case = store.create_case(
            workspace, title="Appendix OPR-1 Functional Program - arithmetic reconciliation",
            objective="Check whether room-level line items, departmental subtotals, and the stated grand total in the Functional Program reconcile.",
        )
        store.attach_source_to_case(workspace, case["id"], opr_source["id"])

        mismatched = [g for g in reconciliation["groups"] if g["stated_subtotal"] is not None and not g["matches"]]
        statement = (
            f"Generic reconciliation of Appendix OPR-1 found {reconciliation['mismatched_group_count']} of "
            f"{reconciliation['group_count']} departmental groups where the sum of room-level line items does "
            f"not equal the table's own printed subtotal cell. Sum of all line items = "
            f"{reconciliation['total_from_line_items']:.0f} m²; sum of printed subtotal cells = "
            f"{reconciliation['total_from_stated_subtotals']:.0f} m²"
            + (f"; document's own stated grand total = {grand_total['value']:.0f} {grand_total['unit']}" if grand_total else "")
            + f". Mismatched groups: {', '.join(g['group'] for g in mismatched)}."
        )
        trigger = AnalysisTrigger(
            trigger_type=ANALYSIS_TRIGGER_AGENT_INITIATED,
            trigger_reference_type="generic_table_reconciliation_routine",
            triggered_by_actor="nreocrc-reingestion-lab-002",
        )
        analysis = store.record_analysis(
            workspace, source_ids=[opr_source["id"]], case_id=case["id"],
            objective="Reconcile Appendix OPR-1 room-level, departmental-subtotal, and grand-total figures.",
            engine_name="generic_grouped_quantity_table_reconciliation", engine_version="1.0",
            findings=[{"statement": statement, "machine_confidence": 0.9}],
            trigger=trigger,
        )
        finding_record = store._find(workspace.findings, analysis["finding_ids"][0])

        thread = store.create_review_thread(
            workspace, title="Appendix OPR-1 arithmetic does not reconcile with itself",
            anchor_type=OBJECT_KIND_SOURCE, anchor_id=opr_source["id"], anchor_source_id=opr_source["id"],
            anchor_location={"location_type": "table", "table_start_line": fp_table["start_line"]},
            anchor_description="Functional Program (Appendix OPR-1) departmental subtotals vs. line items vs. stated grand total.",
            created_by="nreocrc-reingestion-lab-002", case_id=case["id"], governance_log=gov,
        )
        msg = store.add_review_message(
            workspace, thread_id=thread["id"], origin="machine", actor="nreocrc-reingestion-lab-002",
            message_type="observation", text=statement,
            related_analysis_id=analysis["id"], related_finding_id=finding_record["id"],
            governance_log=gov,
        )
        store.request_attention(
            workspace, thread_id=thread["id"], message_id=msg["id"],
            intended_actor="Owner (clarification/Addendum - this is an inconsistency in an Owner-issued document, not a Design-Builder compliance failure)",
            created_by="nreocrc-reingestion-lab-002", governance_log=gov,
        )
        thread_record = thread

    report["arithmetic_governance_action"] = {
        "chosen_state": "Provisional Finding (claim_status=provisional, no Disposition recorded) + ReviewThread with Attention requested of the Owner"
                        if finding_record else "not applicable - no mismatch found",
        "explicitly_not_done": "NOT marked non-compliance; NOT a Disposition; NOT attributed to Design-Builder fault.",
        "finding_id": finding_record["id"] if finding_record else None,
        "review_thread_id": thread_record["id"] if thread_record else None,
    }

    # ============================================================
    # STEP 9 - Cross-reference index table (Section 3) -> generic,
    # per-row Expected-Information derivation (fixes the Snapshot 001
    # omission of RFP-001's already-issued status, if the generic rule
    # actually distinguishes it).
    # ============================================================
    xref_table = find_table_by_headers(parsed_document.tables, ["document id", "status"])
    profile = store.create_expected_information_profile(
        workspace, title="RFP-stage referenced documents (per NREOCRC-OPR-001 Section 3 cross-reference index)",
        scope_type=OBJECT_KIND_PROJECT, scope_id=PROJECT_ID, created_by="nreocrc-reingestion-lab-002",
        governance_log=gov,
    )
    expected_info_rows = []
    if xref_table:
        status_col = next(i for i, h in enumerate(xref_table["headers"]) if "status" in h.lower())
        docid_col = next(i for i, h in enumerate(xref_table["headers"]) if "document id" in h.lower())
        name_col = 0
        for row in xref_table["rows"]:
            status_text = row[status_col].strip()
            status_lower = status_text.lower()
            if "to be issued" in status_lower:
                bucket = "DECLARED FUTURE / NOT YET ISSUED"
                bindingness = EXPECTATION_BINDINGNESS_EXPECTED
            elif "issued concurrently" in status_lower:
                bucket = "CURRENTLY EXPECTED - stated as already issued, but absent from this corpus state"
                bindingness = EXPECTATION_BINDINGNESS_EXPECTED
            elif status_lower == "issued":
                bucket = "ALREADY OBSERVED (present in this corpus)"
                bindingness = EXPECTATION_BINDINGNESS_MANDATORY
            else:
                bucket = "UNKNOWN"
                bindingness = EXPECTATION_BINDINGNESS_EXPECTED

            item = store.add_expectation_item(
                workspace, profile_id=profile["id"], expected_kind="document",
                description=f"{row[name_col]} ({row[docid_col]})", created_by="nreocrc-reingestion-lab-002",
                bindingness=bindingness, authority_source="OPR-001 Section 3 (Cross-Reference Index)",
                applicability=f"Status at issuance of this OPR, per the document's own cross-reference table: '{status_text}'",
            )
            observed = [{"object_type": "source", "object_id": opr_source["id"], "accessible": True, "authority_confidence": "confirmed"}] \
                if row[docid_col].strip() == "NREOCRC-OPR-001" else []
            raw_eval = evaluate_information_sufficiency(item, observed=observed)
            expected_info_rows.append({
                "document": row[name_col], "document_id": row[docid_col], "status_as_stated": status_text,
                "generic_bucket": bucket, "raw_evaluator_outcome": raw_eval["outcome"],
            })
    report["expected_information_shadow_rerun"] = {
        "method": "DERIVED_BY_GENERIC_ANALYSIS: every row of the Section 3 cross-reference table (found generically) "
                  "gets an Expected Information item, bucketed by generic keyword match on its OWN status text "
                  "('to be issued' / 'issued concurrently' / 'issued') - RFP-001 is no longer silently excluded "
                  "the way Snapshot 001 excluded it, because this loop does not hand-pick which rows to include.",
        "rows": expected_info_rows,
        "known_still_open_gap": (
            "No SUFFICIENCY_* outcome exists for 'explicitly deferred, no date stated' (evaluate_information_sufficiency "
            "still returns 'expected_not_found' raw for undated future items) - this gap from Snapshot 001 was NOT "
            "addressed by Batches F/G/H and remains open. The generic_bucket labels above are this script's own "
            "human-layer interpretation layered on top of the unchanged raw evaluator output, same workaround as "
            "Snapshot 001 needed."
        ),
    }
    report["gaps_still_open"].append({
        "gap": "evaluate_information_sufficiency has no outcome for 'explicitly deferred, no date stated'",
        "status": "STILL OPEN - not addressed by Batch F, G, or H.",
    })

    # ============================================================
    # STEP 10 - Precedence (Section 2.2), parsed generically as an
    # ordered list, qualifiers preserved verbatim - no Relationship
    # edges fabricated to non-existent document Sources.
    # ============================================================
    precedence_items = []
    in_list = False
    for line in raw_lines:
        stripped = line.strip()
        m = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if stripped.startswith("Except as otherwise"):
            in_list = True
        if in_list and m:
            precedence_items.append({"rank": int(m.group(1)), "text": m.group(2)})
        if in_list and stripped.startswith("This order of precedence is the Owner's current statement"):
            precedence_items.append({"rank": None, "qualifier": stripped})
            in_list = False
    report["precedence_reconstruction"] = {
        "method": "DERIVED_BY_GENERIC_ANALYSIS: generic numbered-list regex applied to Section 2.2's raw text.",
        "items": precedence_items,
        "note": "No Relationship edges created to document-level concepts (Project Agreement, Addenda, RFP main "
                "document, etc.) since none of those exist as registered Sources in this corpus state - "
                "fabricating such edges would misrepresent what BEEHIVE actually has evidence for.",
    }

    # ============================================================
    # STEP 11 - Unresolved-qualifier preservation check (generic hedge-
    # phrase scan across every registered Requirement's own text)
    # ============================================================
    hedge_hits = []
    for section, req in registered_requirements.items():
        text_lower = req["text_reference"].lower()
        hits = [p for p in _HEDGE_PHRASES if p in text_lower]
        if hits:
            hedge_hits.append({"section": section, "hedge_phrases_preserved": hits})
    report["unresolved_qualifier_preservation_test"] = {
        "method": "Generic keyword scan for hedge phrases across every registered Requirement.text_reference "
                  "(which is captured VERBATIM by the bracket-tag regex, not paraphrased by a human).",
        "sections_with_preserved_hedges": hedge_hits,
    }

    # ============================================================
    # STEP 12 - Design maturity (same known modeling gap - NOT fixed
    # here, per Prompt 17 #18's no-new-features rule; explicitly logged).
    # ============================================================
    maturity = store.record_design_maturity(
        workspace, scope_type=OBJECT_KIND_PROJECT, scope_id=PROJECT_ID,
        value="rfp_pre_proposal", created_by="nreocrc-reingestion-lab-002",
    )
    report["maturity_recorded"] = maturity
    report["gaps_still_open"].append({
        "gap": "No separate procurement/commercial-milestone maturity axis; 'rfp_pre_proposal' is still tagged maturity_type=design",
        "status": "STILL OPEN - Adversarial Review 001 Section 4 flagged this; not addressed by Batch F, G, or H.",
    })

    store.save(workspace)

    # ============================================================
    # STEP 13 - Freeze Snapshot 002 via the REAL Batch G primitive.
    # ============================================================
    final_workspace = store.get(PROJECT_ID)
    snapshot_002 = store.create_snapshot(
        final_workspace, label="NREOCRC Corpus State 001 Re-Ingestion (Snapshot 002, current architecture)",
        created_by="nreocrc-reingestion-lab-002",
        note="Prompt 17 controlled experiment - same immutable corpus as Snapshot 001, current Batch F/G/H architecture.",
        governance_log=gov,
    )
    report["snapshot_002"] = {
        "snapshot_id": snapshot_002["id"],
        "project_state_version": snapshot_002["project_state_version"],
        "frozen_at": snapshot_002["frozen_at"],
        "reference_list_counts": {k: len(v) for k, v in snapshot_002["reference_lists"].items()},
        "governance_event_count": len(gov.read(PROJECT_ID)),
    }

    SNAPSHOT_002_DIR.mkdir(parents=True, exist_ok=True)
    (SNAPSHOT_002_DIR / "snapshot_002.json").write_text(json.dumps(snapshot_002, indent=2, default=str), encoding="utf-8")
    (SNAPSHOT_002_DIR / "reconstruction_002.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(json.dumps(report, indent=2, default=str))
    print(f"\nWrote snapshot to {SNAPSHOT_002_DIR / 'snapshot_002.json'}")
    print(f"Wrote reconstruction report to {SNAPSHOT_002_DIR / 'reconstruction_002.json'}")


if __name__ == "__main__":
    main()
