"""
CLAUDE-P40-VW8-QA-R2A - Smart Drawing-First Project Qualification.

Repository-grounded capability audit (recorded here, not just in the
commit message, since this module's whole shape is a direct consequence
of it):

  - PDF native-text/metadata extraction: YES, already a dependency
    (`pypdf`, used by services/bhive_parser.py). This module's real
    extraction path.
  - DOCX native-text extraction: YES, already a dependency
    (`python-docx`, same file).
  - PDF page RENDERING (page -> raster image): NOT AVAILABLE AT THE
    TIME OF THIS AUDIT (2026-08-04). No PDF-to-image library
    (pypdfium2/PyMuPDF/pdf2image+poppler) was installed, and none was
    added by this stage - see "what remains unavailable" below.
    SUPERSEDED IN PART, 2026-08-29: `pymupdf==1.28.2` is now a pinned
    dependency (added by CLAUDE-DRAWING-REFS-01 for vector geometry and
    positioned text spans, see requirements.txt's own note) and is used
    by engine/pdf_extractor.py. So the LIBRARY is present today and page
    rasterization is technically reachable. What has NOT changed is this
    module's own scope: drawing_intake.py still performs no rendering
    and still has no consumer for one. Treat the line above as the
    historical record of why this module is shaped the way it is, not as
    a current statement of what the environment can do.
  - Local OCR: NOT AVAILABLE. No `pytesseract`/OCR Python package is
    installed, AND the underlying `tesseract` OS binary is not present
    on this machine (confirmed directly: `where tesseract` finds
    nothing). Installing a Python OCR *wrapper* without the OS binary
    it shells out to would not actually work - so this isn't "add one
    safe pip package," it's "install new system software," which this
    stage treats as out of the bounded, safely-addable scope (closer
    to a deployment/infrastructure decision than a code change).
  - External-AI vision: services/bhive_parser.py's `classify`/
    `_check_consistency` already call the Anthropic API, but only ever
    with TEXT (extracted requirement strings), never an image, and
    always behind services/security_policy.py's evaluate_action gate
    (see ingestion.py's own ACTION_EXTERNAL_AI_REQUEST check). This
    module adds NO new external-AI call of any kind - sending a
    drawing's image content to a vision model would be a genuinely new
    confidentiality-relevant decision (transmitting a reviewer's
    uploaded drawing to a third-party API), which this stage's own
    scope boundary (Section 6: "stop only if completion requires...
    confidentiality decisions") treats as needing its own explicit,
    separately-authorized, opt-in stage - not something to wire in as
    an automatic pipeline step. Recorded as unavailable/future, not
    silently attempted.
  - Security-governance gates: services/security_policy.py's
    evaluate_action/ACTION_EXTERNAL_AI_REQUEST - not invoked here at
    all, since this module never calls out. Nothing to weaken.
  - Binary storage / provenance: services/ingestion.py already persists
    the original uploaded bytes (workspace_sources/<project_id>/) with
    a content hash - this module's staging area (below) follows the
    exact same "write the real bytes, hash them" pattern for the
    PENDING (not-yet-confirmed) upload.
  - Project-identity fields: services/case_workspace.py's
    ProjectWorkspace.display_title / set_project_owner /
    set_operating_environment are the real, existing fields a
    confirmed candidate ultimately feeds - this module does not
    introduce a parallel identity model, it produces plain candidate
    dicts a route then feeds into those same existing calls.

Conclusion - the smallest safe, repository-evidenced drawing-intake
pipeline this stage actually builds:

  1. Preserve the original file immediately, unconditionally (already
     true of every upload - unchanged).
  2. Extract native PDF/DOCX text (already-installed libraries only).
  3. If real text exists: apply narrow, evidenced LABEL: VALUE pattern
     matching (same technique as bhive_parser.py's own
     `_DOCUMENT_METADATA_LABEL_PATTERN`, a different, drawing-specific
     field set) to propose candidate Project/drawing identity values,
     each retaining its source page, the exact matched line as
     evidence, an extraction method, and a confidence tier.
  4. If no native text exists (image-only PDF): report that plainly
     (`text_extraction_status="no_native_text"` on the resulting
     ParsedDocument - see bhive_parser.py) rather than fabricating
     values or failing the whole upload.
  5. Never silently prefer a machine candidate over what the reviewer
     typed - a route-layer concern (routes/portal.py), not this
     module's, but the CandidateField shape below (confirmed/corrected/
     unconfirmed status) is what makes that distinction representable.

No new pip dependency, no new OS-level software, no new external
network call.
"""
from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from werkzeug.utils import secure_filename

# -- candidate field patterns ------------------------------------------------
# Same LABEL: VALUE technique as services/bhive_parser.py's own
# _DOCUMENT_METADATA_LABEL_PATTERN (CLAUDE-P38/OBS-09), a genuinely
# different, drawing-title-block-specific vocabulary - pypdf's
# extract_text() returns linear reading-order text with no 2D layout
# information, so only same-line "LABEL: VALUE" / "LABEL VALUE" shapes
# are reliably recoverable; a label and its value printed in separate
# title-block cells with no shared line are honestly NOT extracted
# (never guessed from proximity).
_FIELD_PATTERNS: dict[str, list[re.Pattern]] = {
    "project_name": [
        re.compile(r"^project\s*(name|title)?\s*:\s*(?P<value>.+)$", re.IGNORECASE),
    ],
    "project_number": [
        re.compile(r"^project\s*(no\.?|number|#)\s*:\s*(?P<value>.+)$", re.IGNORECASE),
    ],
    "project_address": [
        re.compile(r"^(project\s*)?(address|site\s*(address|location)|location)\s*:\s*(?P<value>.+)$", re.IGNORECASE),
    ],
    "owner_client": [
        re.compile(r"^(owner|client|owner\s*/\s*client)\s*:\s*(?P<value>.+)$", re.IGNORECASE),
    ],
    "drawing_title": [
        re.compile(r"^drawing\s*(title|name)?\s*:\s*(?P<value>.+)$", re.IGNORECASE),
    ],
    "sheet_number": [
        re.compile(r"^sheet\s*(no\.?|number|#)?\s*:\s*(?P<value>.+)$", re.IGNORECASE),
    ],
    "discipline": [
        re.compile(r"^discipline\s*:\s*(?P<value>.+)$", re.IGNORECASE),
    ],
    "consultant": [
        re.compile(r"^(consultant|designer|architect|engineer(\s+of\s+record)?)\s*:\s*(?P<value>.+)$", re.IGNORECASE),
    ],
    "issue_date": [
        re.compile(r"^(issue(d)?\s*date|date\s*(issued)?)\s*:\s*(?P<value>.+)$", re.IGNORECASE),
    ],
    "revision": [
        re.compile(r"^rev(ision)?\s*(no\.?|number|#)?\s*:\s*(?P<value>.+)$", re.IGNORECASE),
    ],
    "scale": [
        re.compile(r"^scale\s*:\s*(?P<value>.+)$", re.IGNORECASE),
    ],
}

# Sheet-number-prefix -> discipline inference (e.g. "A-101" -> Architectural).
# Only ever applied when no explicit `discipline:` label was found, and
# always tagged "medium" confidence (inferred, not stated).
_SHEET_PREFIX_DISCIPLINE = {
    "A": "Architectural", "S": "Structural", "M": "Mechanical",
    "E": "Electrical", "C": "Civil", "P": "Plumbing", "L": "Landscape",
    "FP": "Fire Protection", "G": "General",
}
_SHEET_PREFIX_RE = re.compile(r"^(FP|[ASMECPLG])[\s\-.]?\d")

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"

STATUS_UNCONFIRMED = "unconfirmed"
STATUS_CONFIRMED = "confirmed"
STATUS_CORRECTED = "corrected"

EXTRACTION_METHOD_PDF_TEXT_PATTERN = "native_pdf_text_pattern"
EXTRACTION_METHOD_DOCX_TEXT_PATTERN = "native_docx_text_pattern"
EXTRACTION_METHOD_SHEET_INFERENCE = "sheet_number_prefix_inference"
EXTRACTION_METHOD_UNAVAILABLE = "unavailable"

CANDIDATE_FIELDS = tuple(_FIELD_PATTERNS.keys())

# Human-readable labels for the confirmation page (Section 3's own field
# names) - kept alongside CANDIDATE_FIELDS since both describe the same
# fixed field set, not duplicated in the template/route layer.
FIELD_LABELS: dict[str, str] = {
    "project_name": "Project name",
    "project_number": "Project number",
    "project_address": "Project address / site location",
    "owner_client": "Owner / client",
    "drawing_title": "Drawing title",
    "sheet_number": "Sheet number",
    "discipline": "Discipline",
    "consultant": "Consultant / designer",
    "issue_date": "Issue date",
    "revision": "Revision",
    "scale": "Scale",
}


@dataclass
class CandidateField:
    """One machine-proposed value, with the evidence CLAUDE-P40-VW8-QA-R2A
    Section 4 requires retained for every proposed value. `status`
    starts "unconfirmed" and is set by the route layer once the
    reviewer actually confirms or corrects it - never mutated by
    extraction itself."""
    field: str
    value: str
    source_filename: str
    source_page: Optional[int]
    evidence_snippet: str
    extraction_method: str
    confidence: str
    status: str = STATUS_UNCONFIRMED

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_candidates_from_pdf(raw_bytes: bytes, filename: str) -> list[CandidateField]:
    """CLAUDE-P40-VW8-QA-R2A Section 2/3: candidate extraction stage.
    Reuses BHiveParser.extract_pdf_pages (the one real pypdf call site)
    rather than a second, parallel PDF-reading implementation."""
    from services.bhive_parser import BHiveParser

    pages = BHiveParser.extract_pdf_pages(raw_bytes)
    return _candidates_from_pages(pages, filename)


def _candidates_from_pages(pages: list[str], filename: str) -> list[CandidateField]:
    candidates: list[CandidateField] = []
    found_fields: set[str] = set()

    for page_index, page_text in enumerate(pages, start=1):
        for line in page_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            for field_name, patterns in _FIELD_PATTERNS.items():
                if field_name in found_fields:
                    continue
                for pattern in patterns:
                    match = pattern.match(stripped)
                    if not match:
                        continue
                    value = match.group("value").strip().strip(",;")
                    if not value:
                        continue
                    confidence = CONFIDENCE_HIGH if ":" in stripped else CONFIDENCE_MEDIUM
                    candidates.append(CandidateField(
                        field=field_name, value=value, source_filename=filename,
                        source_page=page_index, evidence_snippet=stripped,
                        extraction_method=EXTRACTION_METHOD_PDF_TEXT_PATTERN,
                        confidence=confidence,
                    ))
                    found_fields.add(field_name)
                    break

    # Discipline inference from sheet_number, only if discipline itself
    # was never explicitly labeled - see _SHEET_PREFIX_DISCIPLINE's own
    # comment above.
    if "discipline" not in found_fields:
        sheet_candidate = next((c for c in candidates if c.field == "sheet_number"), None)
        if sheet_candidate is not None:
            m = _SHEET_PREFIX_RE.match(sheet_candidate.value.strip().upper())
            if m:
                discipline_name = _SHEET_PREFIX_DISCIPLINE.get(m.group(1))
                if discipline_name:
                    candidates.append(CandidateField(
                        field="discipline", value=discipline_name,
                        source_filename=filename, source_page=sheet_candidate.source_page,
                        evidence_snippet=sheet_candidate.evidence_snippet,
                        extraction_method=EXTRACTION_METHOD_SHEET_INFERENCE,
                        confidence=CONFIDENCE_MEDIUM,
                    ))

    return candidates


def extract_candidates_from_docx(raw_bytes: bytes, filename: str) -> list[CandidateField]:
    """Same LABEL: VALUE technique, applied to a DOCX's paragraph text -
    a project-identity cover sheet/title block can arrive as a DOCX
    too, not only a PDF. No page concept in DOCX (source_page=None -
    an honest gap, never fabricated)."""
    import io
    import docx  # python-docx, already a dependency (bhive_parser.py)

    document = docx.Document(io.BytesIO(raw_bytes))
    candidates: list[CandidateField] = []
    found_fields: set[str] = set()

    for paragraph in document.paragraphs:
        stripped = paragraph.text.strip()
        if not stripped:
            continue
        for field_name, patterns in _FIELD_PATTERNS.items():
            if field_name in found_fields:
                continue
            for pattern in patterns:
                match = pattern.match(stripped)
                if not match:
                    continue
                value = match.group("value").strip().strip(",;")
                if not value:
                    continue
                confidence = CONFIDENCE_HIGH if ":" in stripped else CONFIDENCE_MEDIUM
                candidates.append(CandidateField(
                    field=field_name, value=value, source_filename=filename,
                    source_page=None, evidence_snippet=stripped,
                    extraction_method=EXTRACTION_METHOD_DOCX_TEXT_PATTERN,
                    confidence=confidence,
                ))
                found_fields.add(field_name)
                break

    return candidates


@dataclass
class DrawingIntakeResult:
    candidates: list[CandidateField] = field(default_factory=list)
    # Mirrors services/bhive_parser.py's ParsedDocument.text_extraction_status
    # exactly (same two values) - computed once here, at STAGING time,
    # from the same pypdf pass extract_candidates_from_pdf already does,
    # rather than a second pass duplicating BHiveParser.parse's own
    # later, authoritative determination.
    text_extraction_status: str = "extracted"


def analyze_upload(raw_bytes: bytes, filename: str) -> DrawingIntakeResult:
    """CLAUDE-P40-VW8-QA-R2A Section 2, steps 2-6: the STAGING-time
    analysis step - extraction/candidate-proposal ONLY, deliberately
    NOT the full BHiveParser.parse pipeline (segment/classify/
    consistency, which may call the Anthropic API - see this module's
    own header comment on external-AI). Nothing here is sent anywhere;
    it only reads bytes already sitting in memory for this one request.
    The full parse (and the real, already-governed Anthropic gate it
    goes through) runs later, only once the reviewer has actually
    confirmed proceeding - see routes/portal.py's confirm-step handler,
    which calls the existing, unchanged services.ingestion.ingest_upload.

    Dispatch by extension - .pdf/.docx only (the two formats with a
    usable native-text extraction path already installed; see this
    module's own header comment). Any other supported upload type
    (.txt/.csv/.md) returns zero candidates and "extracted" status - a
    plain-text RFP is not a drawing with a title block to mine, and
    this stage's own scope (Section 1: "smallest safe drawing-intake
    pipeline") doesn't ask for one.

    A malformed/unparseable file (corrupt PDF, a .docx that isn't
    actually a valid zip) degrades to zero candidates and "extracted"
    status here - deliberately NOT this function's job to diagnose or
    report that as an error. The real, authoritative parse
    (services.ingestion.ingest_upload -> BHiveParser.parse) still runs
    later regardless, with its own already-established error handling
    (ParserError -> UploadError, surfaced to the reviewer exactly as it
    always has been) - this staging-time analysis step is best-effort
    enrichment only, never a second place a bad-file error can
    originate from."""
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        from services.bhive_parser import BHiveParser

        try:
            pages = BHiveParser.extract_pdf_pages(raw_bytes)
        except Exception:  # noqa: BLE001 - see docstring above
            return DrawingIntakeResult(candidates=[])
        has_text = any(page.strip() for page in pages)
        candidates = _candidates_from_pages(pages, filename) if has_text else []
        return DrawingIntakeResult(
            candidates=candidates,
            text_extraction_status="extracted" if has_text else "no_native_text",
        )

    if ext == ".docx":
        try:
            return DrawingIntakeResult(candidates=extract_candidates_from_docx(raw_bytes, filename))
        except Exception:  # noqa: BLE001 - see docstring above
            return DrawingIntakeResult(candidates=[])

    return DrawingIntakeResult(candidates=[])


# -- pending-upload staging ---------------------------------------------------
# CLAUDE-P40-VW8-QA-R2A Section 2, steps 7-8: "present candidates to the
# user for confirmation... create the Project from confirmed
# information" - a genuine two-request flow (GET the confirmation page,
# POST the confirmed values), which needs somewhere to hold the raw
# bytes + candidates between those two requests. Flat-JSON + a sibling
# raw-bytes file, the exact same pattern services/ingestion.py already
# uses for a CONFIRMED project's own original_file_path - never a
# database table, matching this repository's established storage
# discipline (see tools/dependency_fit.py). Deliberately NOT reusing
# Flask's session for the raw bytes themselves - a multi-MB file has no
# business round-tripping through a signed cookie.
_STAGING_SUBDIR = "pending_uploads"
_STAGING_TTL_SECONDS = 24 * 60 * 60


class PendingUploadStore:
    def __init__(self, store_path: str | Path):
        self.dir = Path(store_path) / _STAGING_SUBDIR
        self.dir.mkdir(parents=True, exist_ok=True)

    def create(
        self, raw_bytes: bytes, filename: str, candidates: list[CandidateField],
        text_extraction_status: str, operating_environment: str, owner: str,
        actor: Optional[str], role: Optional[str], entered_project_name: Optional[str],
        # CLAUDE-PERSPECTIVE-GATE-04: carried through staging so a project
        # created via the confirm step establishes the same declared working
        # position as one created directly. Optional and defaulted, so a
        # manifest staged before this existed still loads and still ingests -
        # it simply has no declared perspective, which is an honest state.
        entry_choice: Optional[str] = None,
        retained_by: Optional[str] = None,
        source_domain: Optional[str] = None,
    ) -> str:
        self._sweep_expired()
        staging_id = uuid.uuid4().hex
        safe_name = secure_filename(filename)
        raw_path = self.dir / f"{staging_id}_{safe_name}"
        raw_path.write_bytes(raw_bytes)

        manifest = {
            "staging_id": staging_id,
            "filename": filename,
            "raw_path": str(raw_path),
            "created_at": time.time(),
            "candidates": [c.to_dict() for c in candidates],
            "text_extraction_status": text_extraction_status,
            "operating_environment": operating_environment,
            "owner": owner,
            "actor": actor,
            "role": role,
            "entered_project_name": entered_project_name,
            "entry_choice": entry_choice,
            "retained_by": retained_by,
            "source_domain": source_domain,
        }
        self._manifest_path(staging_id).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return staging_id

    def get(self, staging_id: str) -> Optional[dict]:
        path = self._manifest_path(staging_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def get_raw_bytes(self, staging_id: str) -> Optional[bytes]:
        manifest = self.get(staging_id)
        if manifest is None:
            return None
        raw_path = Path(manifest["raw_path"])
        if not raw_path.exists():
            return None
        return raw_path.read_bytes()

    def discard(self, staging_id: str) -> None:
        manifest = self.get(staging_id)
        if manifest is None:
            return
        raw_path = Path(manifest["raw_path"])
        raw_path.unlink(missing_ok=True)
        self._manifest_path(staging_id).unlink(missing_ok=True)

    def _manifest_path(self, staging_id: str) -> Path:
        # staging_id is always our own uuid4().hex output (never taken
        # from a request path segment without validation upstream) -
        # still defensively confined via secure_filename, same
        # discipline as every other on-disk path this codebase builds
        # from caller-influenced input.
        return self.dir / f"{secure_filename(staging_id)}.json"

    def _sweep_expired(self) -> None:
        """Best-effort cleanup of abandoned staging entries (a
        reviewer who uploaded but never confirmed) - runs opportunistically
        on the next create(), not a background worker/cron (this
        codebase deliberately has none - see tools/dependency_fit.py).
        An entry surviving past its TTL is a harmless a few-KB/MB of
        disk, not a correctness or security issue, so best-effort is
        genuinely sufficient here."""
        now = time.time()
        for manifest_path in self.dir.glob("*.json"):
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                if now - data.get("created_at", now) > _STAGING_TTL_SECONDS:
                    Path(data["raw_path"]).unlink(missing_ok=True)
                    manifest_path.unlink(missing_ok=True)
            except (OSError, ValueError, KeyError):
                continue
