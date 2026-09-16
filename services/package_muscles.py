"""CLAUDE-MUSCLE-ACTIVATION-01 - one governed route for five existing muscles.

    THE GAP WAS NEVER CAPABILITY. IT WAS A DOOR.

F1 (bind confidence), F2 (sheet identity and discipline), F3 (subject keys),
F4 (supersession detection) and F5 (declared-but-absent) all worked in
isolation and three of them were already built before this tranche started.
What none of them had was a production caller on a real package path.

This module is that caller, and it is deliberately NOT a new ingestion
service. It owns no storage, no parsing and no vocabulary. Every write goes
through a primitive that already existed:

    register_evidence_item        subject keys, manifest gaps
    record_evidence_relationship  same_subject_as between two evidence items
    record_supersession           an addendum clause replacing a base clause

WHY IT LIVES HERE AND NOT IN THE WORKER. The natural home is
`services/perception_worker.py`, where sheet indexes are already registered
and `not_found` is already computed and then discarded into a log count. That
file's bytes are PINNED by docs/records/datum-lifecycle-transition-01.json and
editing it breaks the Operational Flight Deck digest guard, which is not a
thing to do as a side effect of wiring. So the hook is called from
`visual_classification.examine_source`, which is the other end of the same
examination and is not pinned. The constraint is stated rather than worked
around.

EVERYTHING IT WRITES IS A PROPOSAL. Subject keys, supersessions and manifest
gaps are all registered as `ai_generated_proposal` evidence or as provisional
relationships. A detector that promoted its own reading to governed fact would
be the exact silent promotion this application exists to prevent - and the
supersession case is the sharpest, because a wrongly-recorded supersession
makes a requirement that still governs disappear from a reader's view.

NEVER RAISES. Activation runs at the end of an examination that has already
succeeded. A malformed clause, an unreadable index or a storage collision must
degrade to "this muscle found nothing on this source", never to a failed
examination - the reading is worth more than the enrichment.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

ACTIVATION_VERSION = "package-muscles@1"

#: Content types for what this hook registers. Distinct so a reader can ask for
#: one without parsing the others, and so neither is confused with a reading.
SUBJECT_CONTENT_TYPE = "application/vnd.archiosk.subject-keys+json"
MANIFEST_GAP_CONTENT_TYPE = "application/vnd.archiosk.manifest-gap+json"

#: How many subjects one source may contribute. A schedule sheet legitimately
#: names dozens; a bound specification could name thousands, and an unbounded
#: registration would turn one upload into a write storm.
MAX_SUBJECTS_PER_SOURCE = 200


def _text_for(workspace, source_id: str) -> str:
    """Everything recovered from this source, as one string.

    Reuses `sheet_identity.recovered_pages_for`, which is the existing reader
    for recovered page text and is already wired. No second extraction path.
    """
    from services import sheet_identity

    parts = []
    for page in sheet_identity.recovered_pages_for(workspace, source_id):
        text = page.get("text") if isinstance(page, dict) else page
        if text:
            parts.append(str(text))
    return "\n".join(parts)


def register_subject_keys(store, workspace, source_id: str, *,
                          extra_text: str = "", actor: str = "system",
                          governance_log=None) -> dict:
    """F3. The normalised subjects this source names, stored once.

    `extra_text` carries anything the caller holds that is not in recovered
    page text - a visual reading's own observations, for instance, which is how
    a subject printed on a drawing reaches the same key as one written in a
    specification.

    Registered as ONE evidence item holding the whole set rather than one per
    subject: the claim being recorded is "this source names these subjects",
    and splitting it would multiply rows without adding a fact.
    """
    from services import subject_tags
    from services.case_workspace import EVIDENCE_CLASS_AI_GENERATED_PROPOSAL

    body = "\n".join(p for p in (_text_for(workspace, source_id), extra_text) if p)
    subjects = subject_tags.subjects_in(body)[:MAX_SUBJECTS_PER_SOURCE]
    if not subjects:
        return {"registered": 0, "subjects": []}

    try:
        store.register_evidence_item(
            workspace, source_id=source_id,
            evidence_class=EVIDENCE_CLASS_AI_GENERATED_PROPOSAL,
            content=json.dumps({"subjects": subjects,
                                "version": ACTIVATION_VERSION},
                               sort_keys=True),
            content_type=SUBJECT_CONTENT_TYPE,
            extractor_version=subject_tags.SUBJECT_VERSION,
            actor=actor, governance_log=governance_log)
    except Exception as exc:  # noqa: BLE001 - see module docstring
        logger.warning("subject keys not registered for %s (%s: %s)",
                       source_id, type(exc).__name__, exc)
        return {"registered": 0, "subjects": []}

    return {"registered": len(subjects),
            "subjects": [s["key"] for s in subjects]}


def subject_records_of(workspace, source_id: str) -> list:
    """The full subject records for one source, newest registration wins.

    Each carries the verbatim that produced it, which is what a reader needs to
    see what the document actually said rather than what normalisation decided.
    """
    rows = [e for e in (getattr(workspace, "evidence_items", None) or [])
            if e.get("source_id") == source_id
            and e.get("content_type") == SUBJECT_CONTENT_TYPE]
    for row in reversed(rows):
        try:
            payload = json.loads(row.get("content") or "")
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            return payload.get("subjects") or []
    return []


def subjects_of(workspace, source_id: str) -> list:
    """Just the KEYS, which is what comparison needs.

    Returning records here once cost a real defect: `link_shared_subjects` did
    `set(subjects_of(...))` and raised "unhashable type: dict", which the
    activation hook then swallowed as "this muscle found nothing". The bridge
    silently did nothing at all while every isolated test still passed - the
    exact shape of failure this application keeps producing, one layer in.
    """
    return [s.get("key") for s in subject_records_of(workspace, source_id)
            if isinstance(s, dict) and s.get("key")]


def link_shared_subjects(store, workspace, source_id: str, *,
                         actor: str = "system", governance_log=None) -> dict:
    """F3's bridge. Relate this source to others naming the same subject.

    THE RELATIONSHIP ALREADY EXISTS. `same_subject_as` is in `case_workspace`'s
    vocabulary and needed no addition - what was missing was a shared KEY for
    two pieces of evidence to agree on, which is the whole of F3. This function
    only records the agreement, provisionally, between the two evidence items
    that carry the keys.
    """
    from services.case_workspace import (
        OBJECT_KIND_EVIDENCE_ITEM, RELATIONSHIP_TYPE_SAME_SUBJECT_AS,
    )

    mine = set(subjects_of(workspace, source_id))
    if not mine:
        return {"links": 0, "shared": []}

    my_row = _subject_row_id(workspace, source_id)
    if not my_row:
        return {"links": 0, "shared": []}

    links, shared = 0, []
    for other in (getattr(workspace, "sources", None) or []):
        other_id = other.get("id")
        if other_id == source_id or other.get("removed_at"):
            continue
        overlap = mine & set(subjects_of(workspace, other_id))
        if not overlap:
            continue
        other_row = _subject_row_id(workspace, other_id)
        if not other_row:
            continue
        try:
            store.record_evidence_relationship(
                workspace,
                from_type=OBJECT_KIND_EVIDENCE_ITEM, from_id=my_row,
                to_type=OBJECT_KIND_EVIDENCE_ITEM, to_id=other_row,
                relationship_type=RELATIONSHIP_TYPE_SAME_SUBJECT_AS,
                reason="both name %s" % ", ".join(sorted(overlap)[:5]),
                created_by=actor, provisional=True,
                governance_log=governance_log)
            links += 1
            shared.extend(sorted(overlap))
        except Exception as exc:  # noqa: BLE001
            logger.warning("subject link not recorded (%s: %s)",
                           type(exc).__name__, exc)
    return {"links": links, "shared": sorted(set(shared))}


def _subject_row_id(workspace, source_id: str) -> Optional[str]:
    rows = [e for e in (getattr(workspace, "evidence_items", None) or [])
            if e.get("source_id") == source_id
            and e.get("content_type") == SUBJECT_CONTENT_TYPE]
    return rows[-1].get("id") if rows else None


def register_supersessions(store, workspace, source_id: str, *,
                           actor: str = "system", governance_log=None) -> dict:
    """F4. Record what an addendum actually replaces - and only that.

    A clause that amends or deletes an earlier one creates a governed
    Supersession through `record_supersession`, the primitive that has existed
    for this since Section 15. A clause that merely refers to an earlier one
    creates NOTHING, and that restraint is the point: claiming a supersession
    that did not happen removes a requirement that still governs from every
    later reader's view.

    The predecessor is the SOURCE the clause belongs to, not the clause itself.
    Clause-level objects do not exist in this application yet, and inventing
    one here to be precise about the target would be a new primitive smuggled
    in as a detail - the honest record is "this addendum supersedes something
    in that source, at clause 2.4", with the clause named in the reason.
    """
    from services import supersession_detect
    from services.case_workspace import OBJECT_KIND_SOURCE

    text = _text_for(workspace, source_id)
    entries = supersession_detect.detect(text)
    superseding = [e for e in entries if e["supersedes"]]
    if not superseding:
        return {"recorded": 0, "clauses": [],
                "mentions": [e["clause"] for e in entries]}

    predecessor = _earlier_source_naming(workspace, source_id,
                                         [e["clause"] for e in superseding])
    if predecessor is None:
        return {"recorded": 0, "clauses": [],
                "mentions": [e["clause"] for e in entries],
                "note": "no earlier source in this project states those clauses"}

    recorded = []
    for entry in superseding:
        try:
            store.record_supersession(
                workspace,
                predecessor_type=OBJECT_KIND_SOURCE, predecessor_id=predecessor,
                successor_type=OBJECT_KIND_SOURCE, successor_id=source_id,
                actor=actor,
                reason="clause %s is %s by this document (%s)"
                       % (entry["clause"], entry["action"],
                          entry["reference_text"]))
            recorded.append(entry["clause"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("supersession not recorded for %s clause %s (%s: %s)",
                           source_id, entry["clause"], type(exc).__name__, exc)
    return {"recorded": len(recorded), "clauses": recorded,
            "predecessor_source_id": predecessor,
            "mentions": [e["clause"] for e in entries if not e["supersedes"]]}


def _earlier_source_naming(workspace, source_id: str, clauses: list):
    """The earlier source that actually states one of these clauses.

    Required so that a supersession points at something real. An addendum
    naming Section 2.4 supersedes the document that CONTAINS Section 2.4, and
    if this project holds no such document there is nothing to supersede - in
    which case none is recorded, rather than one being attached to the nearest
    plausible source.
    """
    from services import supersession_detect

    wanted = set(clauses)
    for other in (getattr(workspace, "sources", None) or []):
        other_id = other.get("id")
        if other_id == source_id or other.get("removed_at"):
            continue
        text = _text_for(workspace, other_id)
        if not text:
            continue
        stated = {r["clause"] for r in supersession_detect.clause_references(text)}
        if wanted & stated:
            return other_id
    return None


def register_manifest_gaps(store, workspace, source_id: str, *,
                           actor: str = "system", governance_log=None) -> dict:
    """F5. Sheets this package declared and did not deliver, recorded.

    `register_sheet_index` has computed this as `not_found` since
    CLAUDE-SHEET-IDENTITY-WIRING-01 and `perception_worker` has reduced it to a
    COUNT in a log line ever since. The detection was never missing; the record
    was. Each gap is stored as evidence of an ABSENCE and states nothing about
    what the missing sheet would have contained.
    """
    from services import sheet_identity
    from services.case_workspace import EVIDENCE_CLASS_AI_GENERATED_PROPOSAL

    gaps = sheet_identity.declared_but_absent(workspace, source_id)
    if not gaps:
        return {"registered": 0, "missing": []}

    try:
        store.register_evidence_item(
            workspace, source_id=source_id,
            evidence_class=EVIDENCE_CLASS_AI_GENERATED_PROPOSAL,
            content=json.dumps({"missing": gaps,
                                "version": ACTIVATION_VERSION},
                               sort_keys=True),
            content_type=MANIFEST_GAP_CONTENT_TYPE,
            extractor_version=sheet_identity.REGISTER_VERSION,
            actor=actor, governance_log=governance_log)
    except Exception as exc:  # noqa: BLE001
        logger.warning("manifest gaps not registered for %s (%s: %s)",
                       source_id, type(exc).__name__, exc)
        return {"registered": 0, "missing": []}

    return {"registered": len(gaps),
            "missing": [g["sheet_token"] for g in gaps]}


def activate(store, workspace, source_id: str, *, extra_text: str = "",
             actor: str = "package-muscles", governance_log=None) -> dict:
    """Run every activated muscle over one source. NEVER RAISES.

    Called at the end of an examination that has already succeeded, so every
    step degrades to "found nothing" rather than failing the reading that
    earned it.
    """
    report = {"source_id": source_id, "version": ACTIVATION_VERSION}
    for name, run in (
        ("subjects", lambda ws: register_subject_keys(
            store, ws, source_id, extra_text=extra_text, actor=actor,
            governance_log=governance_log)),
        ("subject_links", lambda ws: link_shared_subjects(
            store, ws, source_id, actor=actor, governance_log=governance_log)),
        ("supersessions", lambda ws: register_supersessions(
            store, ws, source_id, actor=actor, governance_log=governance_log)),
        ("manifest_gaps", lambda ws: register_manifest_gaps(
            store, ws, source_id, actor=actor, governance_log=governance_log)),
    ):
        try:
            # Re-read between steps: each one writes, and a stale workspace
            # would make the next step reason about a record that no longer
            # matches what is stored.
            fresh = store.get(workspace.project_id) or workspace
            report[name] = run(fresh)
        except Exception as exc:  # noqa: BLE001
            logger.warning("muscle %s failed for %s (%s: %s)",
                           name, source_id, type(exc).__name__, exc)
            report[name] = {"error": type(exc).__name__}
    return report
