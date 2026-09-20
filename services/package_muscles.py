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
    record_change_arrival_assessment  proposed scoped change awaiting human review

Only change_application's accepted-change path may call record_supersession.

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
from services.runtime_observation import observed

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


@observed
def inspect_view_normalization(sources, views):
    """View-normalization before contradiction: qualification, never pixel truth.

    This muscle consumes committed source/view lineage. The pixel comparator
    remains region_comparison; geometry/authority admission stays with its owners.
    A chosen display transform is not proof of equivalent physical viewpoints.
    """
    chains = []
    for source, view in zip(sources, views):
        transform = (view or {}).get('view_transform')
        chains.append(dict(source_id=source['id'], source_sha256=source['file_hash'],
            view_id=view['id'] if view else None, transform=transform or {'type': 'ORIGINAL'},
            qualification='Display normalization only; equivalent physical viewpoint remains unresolved.'))
    return dict(muscle='VIEW-NORMALIZATION BEFORE CONTRADICTION', owner='services.package_muscles.inspect_view_normalization',
        version='1', state='PARTIAL' if any(views) else 'UNRESOLVED', chains=chains,
        considered=['ORIGINAL', 'ROTATE_180', 'MIRROR', 'RECTIFIED / ALIGNED'],
        semantic_contradiction_admissible=False,
        reason='Only explicitly justified retained views are consumed. Untested alternatives are not rejected and no transform is chosen to force agreement.')


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
    """Propose exact evidence lineage. Never write authoritative supersession."""
    from services.case_workspace import EVIDENCE_CLASS_AI_GENERATED_PROPOSAL

    report = {"recorded": 0, "proposed": 0, "unresolved": 0, "assessment_ids": []}
    for candidate in supersession_candidates(workspace, source_id):
        content = json.dumps(candidate, sort_keys=True)
        evidence = next((e for e in workspace.evidence_items
                         if e.get("source_id") == source_id
                         and e.get("content_type") == SUPERSESSION_PROPOSAL_CONTENT_TYPE
                         and e.get("content") == content), None)
        if evidence is None:
            evidence = store.register_evidence_item(
                workspace, source_id=source_id,
                evidence_class=EVIDENCE_CLASS_AI_GENERATED_PROPOSAL,
                content=content, content_type=SUPERSESSION_PROPOSAL_CONTENT_TYPE,
                actor=actor, governance_log=governance_log)
        assessment = next((a for a in workspace.change_arrival_assessments
                           if a.get("supersession_proposal_id") == evidence["id"]), None)
        if assessment is None:
            assessment = store.record_change_arrival_assessment(
                workspace, incoming_source_id=source_id, target_requirement_id=None,
                change_type=("amends" if candidate["action"] == "amends" else "supersedes")
                            if candidate["certainty"] == "RECOVERED" else "review",
                evidence=candidate["directive_text"], created_by=actor,
                authority_basis=candidate["authority_basis"],
                uncertainty=candidate["uncertainty"], subject_scope=candidate["scope"],
                supersession_proposal_id=evidence["id"], governance_log=governance_log)
        report["proposed"] += 1
        report["unresolved"] += candidate["certainty"] != "RECOVERED"
        report["assessment_ids"].append(assessment["id"])
    return report


SUPERSESSION_PROPOSAL_CONTENT_TYPE = "application/vnd.archiosk.supersession-proposal+json"


def supersession_candidates(workspace, source_id):
    """Read-only qualification from situated paragraphs, never filename recency.

    Current support is an entire clause in one paragraph. Finer or uncertain
    scopes remain unresolved, rather than silently acquiring Source endpoints.
    """
    from services import supersession_detect as sd, change_arrival
    from services.case_workspace import EVIDENCE_CLASS_DIRECT_SOURCE
    sources = {s["id"]: s for s in workspace.sources if not s.get("removed_at")}
    if source_id not in sources:
        return []
    regions = {r["id"]: r for r in workspace.addressable_regions}
    units = {u["id"]: u for u in workspace.structural_units}
    paragraphs = []
    for e in workspace.evidence_items:
        r = regions.get(e.get("region_id"), {})
        u = units.get(r.get("structural_unit_id"), {})
        if (e.get("content_type") == "text" and r.get("region_type") == "paragraph"
                and u.get("source_id") == e.get("source_id")
                and e.get("source_id") in sources):
            paragraphs.append(e)
    result = []
    for e in paragraphs:
        if e["source_id"] != source_id:
            continue
        directive = sd.scoped_directive(e["content"])
        if directive is None:
            if not sd.has_directed_change(e["content"]):
                continue
            directive = {"scope": "unresolved", "action": "unknown"}
        scope = directive["scope"]
        if scope == "clause":
            matches = [p for p in paragraphs if p["source_id"] != source_id
                       and sd.clause_paragraph(p["content"], directive["clause"])]
            endpoints = [{"type": "evidence_item", "id": p["id"]} for p in matches]
            successor = {"type": "evidence_item", "id": e["id"]}
        elif scope == "whole_document":
            matches = [s for s in sources.values() if s["id"] != source_id
                       and s.get("name") == directive["target_name"]]
            endpoints = [{"type": "source", "id": s["id"]} for s in matches]
            successor = {"type": "source", "id": source_id}
        else:
            matches, endpoints = [], []
            successor = {"type": "evidence_item", "id": e["id"]}
        authority = change_arrival.authority_of(sources[source_id])
        proven = (len(matches) == 1 and scope != "unresolved"
                  and e.get("evidence_class") == EVIDENCE_CLASS_DIRECT_SOURCE
                  and (scope == "whole_document" or matches[0].get("evidence_class") == EVIDENCE_CLASS_DIRECT_SOURCE)
                  and change_arrival.carries_change_authority(sources[source_id]))
        import hashlib
        def proof(item):
            # Persist what was actually read, so changing text at the same id
            # cannot leave a previously accepted proposal looking current.
            region = regions.get(item.get("region_id"))
            return {"evidence_id": item["id"], "source_id": item["source_id"],
                    "region": region, "evidence_class": item.get("evidence_class"),
                    "content_sha256": hashlib.sha256(item["content"].encode("utf-8")).hexdigest()}
        result.append({**directive, "predecessor": endpoints[0] if len(endpoints) == 1 else None,
                       "predecessor_candidates": endpoints, "successor": successor,
                       "predecessor_provenance": [proof(p) for p in matches] if scope == "clause" else [],
                       "directive_provenance": proof(e),
                       "directive_evidence_id": e["id"], "directive_text": e["content"],
                       "authority_basis": authority, "certainty": "RECOVERED" if proven else "UNRESOLVED",
                       "uncertainty": None if proven else "Exact scope, unique predecessor, native evidence and declared change authority are required."})
    return result


def supersession_proposal(workspace, proposal_id):
    """Revalidate a persisted proposal against current evidence before acceptance/application."""
    item = next((e for e in workspace.evidence_items if e["id"] == proposal_id
                 and e.get("content_type") == SUPERSESSION_PROPOSAL_CONTENT_TYPE
                 and e.get("evidence_class") == "ai_generated_proposal"), None)
    if item is None:
        raise ValueError("Supersession proposal evidence not found.")
    payload = json.loads(item["content"])
    if payload not in supersession_candidates(workspace, item["source_id"]):
        raise ValueError("Supersession proposal is stale or its scope is no longer proven.")
    return item, payload


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
    try:
        return sheet_identity.register_manifest_gap_evidence(
            store, workspace, source_id, actor=actor, governance_log=governance_log)
    except Exception as exc:  # noqa: BLE001
        logger.warning("manifest gaps not registered for %s (%s: %s)",
                       source_id, type(exc).__name__, exc)
        return {"registered": 0, "missing": []}

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
