"""CLAUDE-SHEET-IDENTITY-REGISTER-01 - which sheets does this project declare?

    DRAWING INDEX ENTRY -> PROJECT SHEET IDENTITY -> ACTUAL SOURCE

IDENTITY, AND NOTHING BEYOND IT. Resolving an index entry to a Source proves
that the project DECLARES a sheet identity and that a Source answers to it. It
does not prove that two disciplines conflict, that a callout points at that
sheet, that two details describe one condition, that any stated value differs,
or that any physical location is shared. Every one of those is a later family.

WHY THIS FAMILY, MEASURED RATHER THAN CHOSEN. Reconnaissance across four
extraction classes and nine real documents found the keyword-led citation family
unrecoverable - keywords survive, identifiers survive, and the two are ADJACENT
in the parser's required form ZERO times, including in perfect native text. The
bottleneck is that real drawings do not write "See Drawing A-204" in prose; the
identifier lives inside a graphical callout. No OCR improvement fixes that.

One real drawing index, by contrast, yielded 51 identifiers in exact native text
of which 48 named a real Source: 94.1% precision, 98.0% recall, no OCR involved.
This module is built on that measurement and on nothing else.

A SOURCEREFERENCE, NOT A RELATIONSHIP, and the distinction is the store's own:
`SourceReference` is "a governed record of an EXPLICIT citation found in a
Source's own text ... A Relationship may be created FROM a resolved
SourceReference, but a SourceReference is not itself a Relationship - it is
closer to Requirement (source-stated meaning) than to an analysis conclusion."
An index entry is exactly that: the document stating something, not ARCHIOSK
concluding something.

CORRECTION, CLAUDE-SHEET-IDENTITY-WIRING-01. This docstring previously claimed
the decisive consequence was RESOLUTION AT READ TIME - "an index that lists a
sheet nobody has uploaded resolves to nothing today and resolves the moment that
sheet arrives, with no mutation, no reprocessing, and no stored answer to go
stale." **THAT IS NOT TRUE OF THIS FAMILY, and it was never true.**
`extract_and_register_source_references` stores `resolution_status` and
`resolved_target_ids` at write time, and the store's one read-time re-resolver
(`resolve_source_reference_status`) re-resolves SECTION citations against
Requirements - not SHEET citations against Sources. A sheet delivered after its
index therefore stays `target_not_found`, and the idempotency key that correctly
prevents duplicate records is also what prevents that one from being upgraded.

The claim was harmless while the register had no caller. Wiring it into the
perception lifecycle makes it a live production property, so it is corrected
here rather than left to be discovered, and pinned by
`tests/test_sheet_identity_wiring_01.py::ArrivalOrder` - a MEASURED assertion
with an instruction to flip it when a read-time sheet resolver exists.

What remains true, and is still why SourceReference is the right primitive: the
record is a citation the DOCUMENT made, not a conclusion ARCHIOSK drew, and the
verbatim declaration survives non-resolution instead of being discarded. The
ordinary Document Shop path attaches every file of an examination before any
perception job runs, so an index is normally perceived with its siblings already
present - the limit bites on incremental delivery, not on the common path.

FALSE CANDIDATES ARE FILTERED BY RESOLUTION, NOT BY A THRESHOLD. The same real
index yielded `JAN18` and `JAN29` - dates from a revision block that happen to
match a sheet-identifier shape. Neither names a Source, so neither produces a
link. Nothing is scored, nothing is tuned, and the abstention is structural.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

REGISTER_METHOD = "declared_sheet_index"
#: Bump when the RULE changes, so an older registration is never silently
#: compared against a newer one's reasoning.
REGISTER_VERSION = "sheet-identity@1"

#: A sheet identifier's shape: one to three letters, an optional separator, one
#: to three digits, an optional trailing letter. Deliberately the SAME shape
#: `case_workspace._SHEET_RE` already uses for its keyword-led form - one
#: vocabulary for what a sheet number looks like, not two.
_SHEET_SHAPE = re.compile(r"^([A-Z]{1,3})[-\s]?(\d{1,3})([A-Z]?)$")

#: Words that announce a sheet list. An index page is recognised, never
#: assumed: a document with no such heading is not read as an index at all.
_INDEX_HEADING = re.compile(
    r"DRAWING\s+INDEX|SHEET\s+INDEX|SHEET\s+LIST|LIST\s+OF\s+DRAWINGS|DRAWING\s+LIST",
    re.IGNORECASE)


def recovered_pages_for(workspace, source_id: str) -> list:
    """This Source's recovered text, ONE ENTRY PER PAGE, in document order.

    CLAUDE-SHEET-INDEX-BOUNDARY-01. The page-bounded form exists because the
    whole-document form below was the wrong evidence boundary for an index:
    `DRAWING INDEX` was recognised on page 0 and candidate tokens were then
    taken from all 49 pages of a bound set. That produced 90 unresolved records
    of postal codes, detail markers and OCR garbage from sheets that had nothing
    to do with the index - and, worse, four OCR readings of one structural sheet
    identifier (`RSE37`/`RSI17`/`RSi37`/`R837`) that looked like failed index
    entries and were contamination.

        IF ARCHIOSK SAYS "THIS IS THE DRAWING INDEX", THEN SHEET-IDENTITY
        CANDIDATES MUST COME FROM THE INDEX PAGE, NOT THE REST OF THE DOCUMENT.

    PAGE-BOUNDED, NOT REGION-BOUNDED, and the distinction is recorded rather
    than blurred: the page `StructuralUnit` is an existing, reliable, governed
    boundary this repository already writes for every PDF page. Isolating the
    index RECTANGLE would need segmentation nobody has measured, and building
    it speculatively to make the boundary theoretically perfect is the trade
    this tranche declines. A page is narrow enough to remove the contamination
    that was actually observed.

    Returns `[{"unit", "text"}]` ordered by the page's own `order_index` - the
    document's order, already recorded, never re-derived from a uuid.
    """
    from services import positioned_text

    regions = {r["id"]: r for r in (getattr(workspace, "addressable_regions", None) or [])}
    units = {u["id"]: u for u in (getattr(workspace, "structural_units", None) or [])
             if u.get("source_id") == source_id and u.get("unit_type") == "page"}

    per_unit: dict = {}
    plain_by_unit: dict = {}
    for item in (getattr(workspace, "evidence_items", None) or []):
        if item.get("source_id") != source_id:
            continue
        content = (item.get("content") or "").strip()
        if not content:
            continue
        region = regions.get(item.get("region_id"))
        unit = units.get((region or {}).get("structural_unit_id"))
        if item.get("content_type") == positioned_text.POSITIONED_CONTENT_TYPE:
            # The region join is the tenant boundary, exactly as
            # `legend_detection.lines_from_workspace` uses it: a stale
            # source_id alone must not pull a line in from another Source.
            if unit is None:
                continue
            address = region.get("address") or {}
            per_unit.setdefault(unit["id"], []).append(
                (address.get("y", 0.0), address.get("x", 0.0), content))
        elif item.get("content_type") == "text":
            # A paragraph region carries its page through the same join; a
            # Source perceived before coordinates existed has no region at all
            # and cannot be page-bounded, which is reported rather than guessed.
            if unit is not None:
                plain_by_unit.setdefault(unit["id"], []).append(content)

    pages = []
    for unit in sorted(units.values(),
                       key=lambda u: (u.get("order_index") if u.get("order_index")
                                      is not None else 0)):
        lines = per_unit.get(unit["id"])
        if lines:
            lines.sort(key=lambda row: row[:2])
            text = "\n".join(row[2] for row in lines)
        else:
            text = "\n".join(plain_by_unit.get(unit["id"], []))
        pages.append({"unit": unit, "text": text})
    return pages


def recovered_text_for(workspace, source_id: str) -> str:
    """Everything this Source's perception recovered, in reading order.

    The whole-document read. Correct for a question ABOUT THE DOCUMENT; wrong
    for one about a single page, which is what `recovered_pages_for` above
    exists for and why the index no longer uses this.
    """
    return "\n".join(page["text"] for page in recovered_pages_for(workspace, source_id)
                      if page["text"])


def normalise_sheet_token(token: Optional[str]) -> str:
    """One spelling for one sheet. `A-01`, `A 01` and `A01` are one identifier.

    Matches `view_reference._normalise`'s own rule (upper, strip spaces and
    hyphens) rather than restating it differently, so the two cannot disagree
    about whether two spellings are the same sheet.
    """
    return "".join((token or "").upper().split()).replace("-", "")


def sheet_token(text: Optional[str]) -> Optional[str]:
    """The sheet identifier in one word, or None. Conservative by construction.

    Matches the WHOLE word or nothing. "A101" is a sheet token; "A101B2" is not,
    and neither is a word that merely contains one. This is the difference
    between reading an identifier and finding a substring.
    """
    candidate = (text or "").strip().upper()
    if not candidate:
        return None
    match = _SHEET_SHAPE.match(candidate)
    if not match:
        return None
    return normalise_sheet_token(candidate)


def source_sheet_tokens(source: dict) -> set:
    """Every sheet identifier this Source may legitimately answer to.

    HIGH-TRUST INPUTS ONLY: the filename and the document id - things a person
    or a system deliberately named, never an OCR token. §4's restraint is
    structural here rather than promised: this function is not given recovered
    text and so cannot infer identity from it.

    ABSTAINS ON AMBIGUITY. A filename carrying two different sheet-shaped words
    ("A101 and A102 combined.pdf") returns NOTHING rather than picking one.
    An identity that needs a guess is not an identity.
    """
    found = set()
    for value in (source.get("document_id"), source.get("name")):
        if not value:
            continue
        stem = re.sub(r"\.(pdf|png|jpe?g)$", "", str(value), flags=re.IGNORECASE)
        # The whole stem may itself be the identifier ("A-01.pdf"), or one word
        # of it may be ("212109 A101 SITE PLAN.pdf").
        whole = sheet_token(stem)
        if whole:
            found.add(whole)
            continue
        words = {sheet_token(word) for word in re.split(r"[\s_]+", stem)}
        words.discard(None)
        if len(words) == 1:
            found.add(next(iter(words)))
        elif len(words) > 1:
            logger.info("source %r carries %d sheet-shaped words; abstaining",
                        value, len(words))
    return found


def looks_like_index(text: Optional[str]) -> bool:
    """Does this text announce itself as a sheet list?"""
    return bool(_INDEX_HEADING.search(text or ""))


def index_entries(text: Optional[str]) -> list:
    """Candidate sheet identifiers declared by an index, with verbatim text.

    Reads only text that announced itself as an index. The verbatim word is
    preserved exactly as it was read - §5's rule, and the reason a later reader
    can always see what the document actually said rather than a cleaned-up
    label this module preferred.
    """
    if not looks_like_index(text):
        return []
    entries, seen = [], set()
    for word in re.split(r"[\s,;|]+", text or ""):
        verbatim = word.strip().strip(".:()[]")
        token = sheet_token(verbatim)
        if token is None or token in seen:
            continue
        seen.add(token)
        entries.append({"reference_text": verbatim, "sheet_token": token})
    return entries


def register_sheet_index(store, workspace, source_id: str, *,
                         actor: str = "system", governance_log=None,
                         dry_run: bool = False) -> dict:
    """Resolve one Source's drawing index against this project's own Sources.

    Returns a report and never raises. `dry_run` writes nothing, which is how
    the real-corpus measurement runs without touching a registry.
    """
    from services.case_workspace import (
        CaseWorkspaceError, REFERENCE_TYPE_SHEET, RESOLUTION_STATUS_RESOLVED_EXACT,
        RESOLUTION_STATUS_RESOLVED_MULTIPLE, RESOLUTION_STATUS_TARGET_NOT_FOUND,
    )
    from services import view_reference

    report = {"source_id": source_id, "method": REGISTER_METHOD,
              "version": REGISTER_VERSION, "is_index": False,
              "index_pages": [], "pages_inspected": 0, "boundary": "page",
              "candidates": 0, "resolved": [], "not_found": [], "ambiguous": [],
              "references_created": 0}

    # THE EVIDENCE BOUNDARY. Only the pages that THEMSELVES announce an index
    # contribute candidates. A sheet-shaped token on page 27 of a bound set is
    # not an index entry, and before this correction it became a governed
    # record indistinguishable from one.
    pages = recovered_pages_for(workspace, source_id)
    report["pages_inspected"] = len(pages)
    index_pages = [page for page in pages if looks_like_index(page["text"])]
    report["is_index"] = bool(index_pages)
    report["index_pages"] = [
        {"structural_unit_id": page["unit"]["id"],
         "label": page["unit"].get("label"),
         "order_index": page["unit"].get("order_index")}
        for page in index_pages
    ]
    if not index_pages:
        return report

    entries, seen = [], set()
    for page in index_pages:
        for entry in index_entries(page["text"]):
            if entry["sheet_token"] in seen:
                continue
            seen.add(entry["sheet_token"])
            # Provenance names the page this candidate came from, so a later
            # reader can always check the boundary was obeyed.
            entry["structural_unit_id"] = page["unit"]["id"]
            entry["page_label"] = page["unit"].get("label")
            entry["page_order_index"] = page["unit"].get("order_index")
            entries.append(entry)
    report["candidates"] = len(entries)
    if not entries:
        return report

    text = "\n".join(page["text"] for page in index_pages)

    # BOUNDED AND SAME-PROJECT BY CONSTRUCTION. `eligible_targets` already
    # excludes removed Sources and the index sheet itself, so a stale Source
    # cannot silently become the active identity target and a Source from
    # another project is not reachable at all.
    index: dict = {}
    for source in view_reference.eligible_targets(store, workspace,
                                                  exclude_source_id=source_id):
        for token in source_sheet_tokens(source):
            index.setdefault(token, []).append(source["id"])

    candidates, known = [], set()
    for entry in entries:
        matched = index.get(entry["sheet_token"], [])
        known.update(matched)
        candidates.append({
            "reference_text": entry["reference_text"],
            "reference_type": REFERENCE_TYPE_SHEET,
            "structural_unit_id": entry["structural_unit_id"],
            "page_label": entry["page_label"],
            # The resolver confirms ids against `known`, so the resolved
            # targets it returns are real Source ids rather than tokens.
            "candidate_targets": list(matched),
            # `list` when several Sources answer to one identifier, so the
            # store reports RESOLVED_MULTIPLE rather than quietly choosing.
            "syntactic_form": "list" if len(matched) > 1 else "single",
            "sheet_token": entry["sheet_token"],
        })

    if dry_run:
        for candidate in candidates:
            bucket = ("resolved" if len(candidate["candidate_targets"]) == 1
                      else "ambiguous" if candidate["candidate_targets"]
                      else "not_found")
            report[bucket].append(candidate)
        return report

    try:
        created = store.extract_and_register_source_references(
            workspace, source_id=source_id, text=text,
            origin_context={"origin": REGISTER_METHOD,
                            "location_type": "drawing_index",
                            # The boundary this read obeyed, named in the record
                            # rather than inferable only from the code version.
                            "boundary": "page",
                            "index_pages": report["index_pages"]},
            known_targets={REFERENCE_TYPE_SHEET: known},
            resolution_method=REGISTER_METHOD,
            resolved_target_type="source",
            extractor_version=REGISTER_VERSION,
            candidates=candidates,
            actor=actor, governance_log=governance_log)
    except CaseWorkspaceError as exc:
        report["reason"] = str(exc)
        return report

    report["references_created"] = len(created)
    for reference in created:
        status = reference.get("resolution_status")
        if status == RESOLUTION_STATUS_RESOLVED_EXACT:
            report["resolved"].append(reference)
        elif status == RESOLUTION_STATUS_RESOLVED_MULTIPLE:
            report["ambiguous"].append(reference)
        elif status == RESOLUTION_STATUS_TARGET_NOT_FOUND:
            report["not_found"].append(reference)
    return report
