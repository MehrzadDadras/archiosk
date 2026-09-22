"""CLAUDE-VERIFICATION-HANDLE-01 - how a human independently re-checks a finding.

CITATION != VERIFICATION PATH. Product Owner, 2026-09-22.

A citation says where something was found. It is an anchor, and this system
already resolves anchors well: `resolve_region_citation` turns a region id into
a human-readable label at read time, and `resolve_anchor_currentness` says
whether that anchor is still the one that applies.

Neither answers the question a reviewer actually has, which is *what do I do to
check this myself*. That needs the anchor, plus what authority the source
carries, plus whether it is still current, plus the words to search for, plus -
when any of that is missing - a truthful statement of what is missing and the
next step that would close it.

THIS IS A PROJECTION, NOT A RECORD. Nothing here is stored. Every field is
derived at read time from records that already own it, following the same
"store flat, derive structure at read time" convention `resolve_region_citation`
and Folder path resolution already use. Storing a handle would create a second
copy of an anchor that can go stale against the first, which is the failure
`resolve_region_citation`'s own docstring exists to avoid.

WHAT IT REFUSES TO DO. It never invents a page, a region, an excerpt or a
currentness. `EvidenceItem.region_id` is optional by deliberate design - "honest
absence over a fabricated anchor" - so a handle must be able to say
SOURCE_LEVEL, or UNRESOLVED, and still be useful. A handle that always looked
complete would be worse than no handle, because a reviewer would trust it.

GRANULARITY IS PART OF THE ANSWER, not a quality score. A Claim cites governed
endpoints and usually resolves to a region. A Finding carries no evidence links
at all - it reaches evidence only through its AnalysisRun's `source_ids` - so
its honest granularity is the source, and the handle says so rather than
implying a precision the record does not have.
"""

from __future__ import annotations

import re
from typing import Optional

from services.case_workspace import (
    CURRENTNESS_UNRESOLVED,
    KNOWN_DOCUMENT_AUTHORITY_LEVELS,
    OBJECT_KIND_ADDRESSABLE_REGION,
    OBJECT_KIND_CLAIM,
    OBJECT_KIND_DERIVED_OBSERVATION,
    OBJECT_KIND_EVIDENCE_ITEM,
    OBJECT_KIND_FINDING,
    OBJECT_KIND_SOURCE,
    ProjectWorkspace,
    normalise_currentness,
)

# How precisely the handle could anchor the thing being verified. Ordered most
# to least precise; the handle reports the best it actually achieved.
GRANULARITY_REGION = "region"
GRANULARITY_SOURCE = "source"
GRANULARITY_NONE = "none"

STATUS_RESOLVED = "resolved"      # every field a reviewer needs is present
STATUS_PARTIAL = "partial"        # anchored, but something material is missing
STATUS_UNRESOLVED = "unresolved"  # no usable anchor at all

# Excerpt length. Long enough to recognize the passage on the page, short enough
# that the handle is a pointer rather than a second copy of the evidence.
_EXCERPT_LIMIT = 400

# Words too common to help someone search a document. Deliberately small and
# domain-neutral: an aggressive stop list would strip the domain terms that are
# the whole point ("setback", "datum", "closure" are exactly what to search for).
_STOPWORDS = frozenset("""
a an the and or but if then than that this these those of in on at to for from
by with without as is are was were be been being it its has have had not no
must shall should may can will would could there their them they he she his her
which who whom whose what when where why how all any both each few more most
other some such only own same so too very just about into over under again
""".split())

# Starts with a letter OR a digit: "3.6m", "R2" and "A-201" are precisely the
# strings that find a clause in a long document, and an anchor-on-letter
# pattern silently drops every dimension in the statement.
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-\./]{2,}")


def _search_terms(*texts: Optional[str], limit: int = 6) -> list[str]:
    """Deterministic search terms from the statement and excerpt.

    NO MODEL CALL. A verification handle that needed inference to tell you what
    to search for would itself need verifying.

    The ranking is identifiers first, then longest word first, then
    alphabetically - predictable rather than clever, because a reviewer
    comparing two handles should see the same rule applied both times.
    Identifiers lead because "A-201", "3.6m" and "R2" are what actually find a
    clause in a long document. Frequency was tried as the second key and
    dropped: over one statement and one excerpt it ranked "per" above
    "setback", which is exactly backwards.
    """
    # Keyed case-INSENSITIVELY, displayed in the casing first seen. "Setback"
    # and "setback" are one search term, not two, and offering both as though
    # they were different is the kind of padding that makes a handle look
    # thorough while helping nobody.
    seen: dict[str, list] = {}
    for text in texts:
        for match in _TOKEN.finditer(text or ""):
            word = match.group(0).strip("./-")
            if len(word) < 3 or word.lower() in _STOPWORDS:
                continue
            entry = seen.setdefault(word.lower(), [word, 0])
            entry[1] += 1

    def rank(item):
        word, _count = item
        has_digit = any(ch.isdigit() for ch in word)
        return (0 if has_digit else 1, -len(word), word.lower())

    ranked = sorted((tuple(v) for v in seen.values()), key=rank)
    return [word for word, _ in ranked[:limit]]


def _authority_of(source: Optional[dict]) -> dict:
    """Document authority, stated as recorded or honestly as unrecorded."""
    if not source:
        return {"level": None, "recorded": False,
                "note": "No source record resolved; authority cannot be stated."}
    level = source.get("document_authority")
    if not level:
        return {"level": None, "recorded": False,
                "note": "This source carries no recorded document authority."}
    known = level in KNOWN_DOCUMENT_AUTHORITY_LEVELS
    return {"level": level, "recorded": True, "known_vocabulary": known,
            "note": None if known else
            f"'{level}' is not in the known document-authority vocabulary."}


def _next_step(granularity, has_excerpt, authority, currentness, region_label):
    """The single most useful next action, chosen by what is missing.

    Ordered by what blocks a reviewer soonest: you cannot check currentness of
    a source you cannot find, and you cannot read a clause you have no page
    for. The wording follows document_examination.unresolved_by_stage's own
    next_steps register - imperative, naming the artifact to obtain - because
    that register is the proven precedent here and inventing a second style
    would make two parts of the product sound like two products.
    """
    if granularity == GRANULARITY_NONE:
        return ("Identify the source this rests on and record it as evidence "
                "before relying on the statement.")
    if granularity == GRANULARITY_SOURCE:
        return ("Open the source and locate the passage; record an addressable "
                "region so this becomes checkable at a fixed location.")
    if not has_excerpt:
        return ("Open the cited region and confirm the wording; no excerpt was "
                "preserved with this evidence.")
    if not authority.get("recorded"):
        return ("Establish and record the source's document authority; the "
                "excerpt is located but its weight is unstated.")
    if currentness != "current":
        return ("Confirm the source is still the governing revision; "
                f"currentness is {currentness.upper()}.")
    return ("Read the cited region against the statement and record a reviewer "
            "validation.")


def _anchor_for(store, workspace: ProjectWorkspace, evidence_item: Optional[dict],
                source_id: Optional[str], statement: str) -> dict:
    """One verification anchor, at the finest granularity actually available."""
    region = unit = None
    excerpt = None
    locator = None
    granularity = GRANULARITY_NONE

    if evidence_item is not None:
        excerpt = (evidence_item.get("content") or "").strip() or None
        source_id = evidence_item.get("source_id") or source_id
        region_id = evidence_item.get("region_id")
        if region_id:
            citation = store.resolve_region_citation(workspace, region_id)
            if citation.get("status") == "resolved":
                granularity = GRANULARITY_REGION
                locator = citation.get("label")
                region = {"id": region_id,
                          "region_type": citation.get("region_type"),
                          "address": citation.get("address")}
                unit_id = citation.get("structural_unit_id")
                raw_unit = next((u for u in workspace.structural_units
                                 if u["id"] == unit_id), None)
                if raw_unit is not None:
                    unit = {"id": raw_unit["id"],
                            "unit_type": raw_unit.get("unit_type"),
                            "label": raw_unit.get("label"),
                            "order_index": raw_unit.get("order_index")}
            else:
                # A broken anchor is reported, never quietly downgraded to the
                # source as though the region had never been recorded.
                locator = None
                region = {"id": region_id, "region_type": None, "address": None,
                          "broken": True}

    source = next((s for s in workspace.sources if s["id"] == source_id), None) if source_id else None
    if granularity == GRANULARITY_NONE and source is not None:
        granularity = GRANULARITY_SOURCE

    if source is not None:
        currentness = normalise_currentness(
            store.resolve_anchor_currentness(
                workspace,
                OBJECT_KIND_EVIDENCE_ITEM if evidence_item is not None else OBJECT_KIND_SOURCE,
                evidence_item["id"] if evidence_item is not None else source["id"],
            ).get("status"))
    else:
        currentness = CURRENTNESS_UNRESOLVED

    authority = _authority_of(source)
    missing = []
    if source is None:
        missing.append("source")
    if granularity != GRANULARITY_REGION:
        missing.append("region")
    if not excerpt:
        missing.append("excerpt")
    if not authority.get("recorded"):
        missing.append("authority")
    if currentness != "current":
        missing.append("currentness")

    return {
        "granularity": granularity,
        "source": ({"id": source["id"], "name": source.get("name"),
                    "kind": source.get("kind"), "revision": source.get("revision"),
                    "removed": bool(source.get("removed_at"))}
                   if source else None),
        "structural_unit": unit,
        "region": region,
        "locator_text": locator,
        "excerpt": excerpt[:_EXCERPT_LIMIT] if excerpt else None,
        "excerpt_truncated": bool(excerpt and len(excerpt) > _EXCERPT_LIMIT),
        "authority": authority,
        "currentness": currentness,
        "search_terms": _search_terms(statement, excerpt),
        "missing": missing,
        "next_verification_step": _next_step(
            granularity, bool(excerpt), authority, currentness, locator),
    }


def _evidence_item(workspace, evidence_item_id):
    return next((e for e in workspace.evidence_items if e["id"] == evidence_item_id), None)


def _links_for(workspace, object_type, object_id) -> tuple[list[dict], str, Optional[str]]:
    """(anchor seeds, statement, unresolved_reason) for a supported object.

    An anchor seed is `{"evidence_item_id"|"source_id"}` - what the record
    itself points at, never a guess about what it might have meant.
    """
    if object_type == OBJECT_KIND_CLAIM:
        claim = next((c for c in workspace.claims if c["id"] == object_id), None)
        if claim is None:
            return [], "", "Claim not found in this project."
        seeds = []
        for link in claim.get("evidence_links") or []:
            kind, ident = link.get("object_type"), link.get("object_id")
            if kind == OBJECT_KIND_EVIDENCE_ITEM:
                seeds.append({"evidence_item_id": ident})
            elif kind == OBJECT_KIND_SOURCE:
                seeds.append({"source_id": ident})
            elif kind == OBJECT_KIND_ADDRESSABLE_REGION:
                # A region cited directly: prefer evidence anchored to it, so
                # the handle can carry an excerpt. Otherwise walk the region's
                # own unit to its source - a real anchor one level coarser,
                # never a null one.
                item = next((e for e in workspace.evidence_items
                             if e.get("region_id") == ident), None)
                if item is not None:
                    seeds.append({"evidence_item_id": item["id"]})
                    continue
                region = next((r for r in workspace.addressable_regions
                               if r["id"] == ident), None)
                unit = next((u for u in workspace.structural_units
                             if region and u["id"] == region.get("structural_unit_id")), None)
                if unit is not None:
                    seeds.append({"source_id": unit.get("source_id")})
        return seeds, claim.get("statement") or "", (
            None if seeds else "This claim records no evidence links.")

    if object_type == OBJECT_KIND_DERIVED_OBSERVATION:
        obs = next((o for o in workspace.derived_observations if o["id"] == object_id), None)
        if obs is None:
            return [], "", "Observation not found in this project."
        seeds = [{"evidence_item_id": i} for i in obs.get("supporting_evidence_ids") or []]
        return seeds, obs.get("statement") or "", (
            None if seeds else "This observation records no supporting evidence.")

    if object_type == OBJECT_KIND_EVIDENCE_ITEM:
        item = _evidence_item(workspace, object_id)
        if item is None:
            return [], "", "Evidence item not found in this project."
        return [{"evidence_item_id": object_id}], item.get("content") or "", None

    if object_type == OBJECT_KIND_FINDING:
        finding = next((f for f in workspace.findings if f["id"] == object_id), None)
        if finding is None:
            return [], "", "Finding not found in this project."
        statement = finding.get("statement") or ""
        analysis = next((a for a in workspace.analyses
                         if a["id"] == finding.get("analysis_id")), None)
        source_ids = list((analysis or {}).get("source_ids") or [])
        if not source_ids:
            return [], statement, (
                "This finding reaches no source. Finding carries no evidence "
                "links of its own - it anchors through its AnalysisRun, and "
                "that run recorded no sources.")
        return [{"source_id": s} for s in source_ids], statement, None

    return [], "", f"'{object_type}' has no verification path in this model."


SUPPORTED_OBJECT_TYPES = (
    OBJECT_KIND_FINDING,
    OBJECT_KIND_CLAIM,
    OBJECT_KIND_DERIVED_OBSERVATION,
    OBJECT_KIND_EVIDENCE_ITEM,
)


def verification_handle_for(store, workspace: ProjectWorkspace,
                            object_type: str, object_id: str) -> dict:
    """How to independently re-check `object_id`, derived at read time.

    Returns `{"object_type", "object_id", "status", "granularity",
    "anchors", "next_verification_step", "unresolved_reason", "search_terms"}`.

    `status` is UNRESOLVED when nothing anchors the statement, PARTIAL when
    something material is missing from every anchor, RESOLVED only when at
    least one anchor is region-level with an excerpt, a recorded authority and
    current currentness. RESOLVED means *checkable*, never *checked* - a
    reviewer validation is a separate record and this never substitutes for
    one.
    """
    seeds, statement, unresolved_reason = _links_for(workspace, object_type, object_id)

    anchors = []
    for seed in seeds:
        item = (_evidence_item(workspace, seed["evidence_item_id"])
                if seed.get("evidence_item_id") else None)
        if seed.get("evidence_item_id") and item is None:
            continue  # a link to an evidence item that no longer resolves
        anchors.append(_anchor_for(store, workspace, item,
                                   seed.get("source_id"), statement))

    if not anchors:
        return {
            "object_type": object_type, "object_id": object_id,
            "status": STATUS_UNRESOLVED,
            "granularity": GRANULARITY_NONE,
            "anchors": [],
            "search_terms": _search_terms(statement),
            "unresolved_reason": unresolved_reason or (
                "Nothing this record points at still resolves in this project."),
            "next_verification_step": _next_step(
                GRANULARITY_NONE, False, {"recorded": False},
                CURRENTNESS_UNRESOLVED, None),
        }

    best = min(anchors, key=lambda a: (
        0 if a["granularity"] == GRANULARITY_REGION else
        1 if a["granularity"] == GRANULARITY_SOURCE else 2,
        len(a["missing"])))
    status = STATUS_RESOLVED if not best["missing"] else STATUS_PARTIAL

    return {
        "object_type": object_type, "object_id": object_id,
        "status": status,
        "granularity": best["granularity"],
        "anchors": anchors,
        "search_terms": best["search_terms"],
        "unresolved_reason": None,
        "next_verification_step": best["next_verification_step"],
    }
