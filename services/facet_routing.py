"""CLAUDE-FACET-ROUTING-01 - choosing what to look at next, and nothing more.

Product Owner, 2026-09-22. Three rules this module exists to keep true:

    FACET SELECTION != FINDING ACCEPTANCE
    PROJECT CREATION != AUTHORITY PROMOTION
    UNSELECTED FACETS REMAIN VISIBLE AND UNPROMOTED

A reviewer reading a broad preliminary investigation picks some of it for
deeper scrutiny. That choice is about ATTENTION - what work happens next - and
says nothing about whether any finding is true. Those are two different
questions and this system already refuses to collapse them elsewhere:
case_workspace.py's own vocabulary note says ReviewerValidation and Disposition
"answer two different questions ... and are never collapsed into one field".

SO THIS ADDS A THIRD AXIS RATHER THAN EXTENDING THE SECOND. DISPOSITIONS
("Confirmed"/"Rejected"/"Deferred"/...) answers "what should happen to this
finding". Facet routing answers "is this workstream being worked". They overlap
in words and not in meaning: a facet can be ACTIVE while every finding in it is
still Unverified, and a facet can be RESOLVED with findings that were Rejected.
Extending DISPOSITIONS with ACTIVE and MONITOR would have made both fields
ambiguous within two tranches, which is the drift the original note warns about.

ROUTING IS APPEND-ONLY. A facet moved from ACTIVE to DEFERRED appends a new
record superseding the earlier one; nothing is rewritten. Constitutional
invariant #5 - correction is non-destructive - is not optional for a record
that will be read back as "why was this not pursued".
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from services.case_workspace import (
    CaseWorkspaceError,
    CaseWorkspaceStore,
    ProjectWorkspace,
)

# The five routing states, and what each one commits the reviewer to.
FACET_ACTIVE = "ACTIVE"        # being worked now
FACET_MONITOR = "MONITOR"      # not being worked, watch for change
FACET_DEFERRED = "DEFERRED"    # not now, revisit later
FACET_DECLINED = "DECLINED"    # deliberately not pursuing
FACET_RESOLVED = "RESOLVED"    # the question this facet asked is closed

KNOWN_FACET_ROUTINGS = (
    FACET_ACTIVE, FACET_MONITOR, FACET_DEFERRED, FACET_DECLINED, FACET_RESOLVED,
)

# Only ACTIVE facets are carried into a project by create_project_from_
# investigation. Everything else stays where it is - visible, readable, and
# unpromoted. DECLINED is NOT deletion: a declined facet is a recorded decision
# not to pursue something, which is exactly the kind of thing a reviewer needs
# to find again six months later when asked "did anyone look at this?".
PROMOTABLE_ROUTINGS = (FACET_ACTIVE,)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def route_facet(store: CaseWorkspaceStore, workspace: ProjectWorkspace, *,
                investigation_ref: str, facet_key: str, routing: str, actor: str,
                rationale: Optional[str] = None, governance_log=None) -> dict:
    """Record where a facet sits in the reviewer's attention. Append-only.

    `investigation_ref` is whatever the facet belongs to - a retained planning
    study id, a Case id - deliberately not typed to one of them, because the
    same question ("are we working this?") is asked of every kind of
    investigation this product will grow.

    A routing NEVER touches any Finding, ReviewerValidation or Disposition.
    """
    if routing not in KNOWN_FACET_ROUTINGS:
        raise CaseWorkspaceError(
            f"'{routing}' is not a facet routing. Use one of: "
            f"{', '.join(KNOWN_FACET_ROUTINGS)}.")
    if not investigation_ref or not facet_key:
        raise CaseWorkspaceError(
            "A facet routing needs both an investigation reference and a facet key.")

    prior = current_routing(workspace, investigation_ref, facet_key)
    record = {
        "id": _new_id(),
        "project_id": workspace.project_id,
        "investigation_ref": investigation_ref,
        "facet_key": facet_key,
        "routing": routing,
        "rationale": rationale,
        "decided_by": actor,
        "decided_at": _now(),
        "supersedes_id": prior["id"] if prior else None,
    }
    if prior is not None:
        # The earlier decision is kept and marked, never edited away.
        for row in workspace.facet_routings:
            if row["id"] == prior["id"]:
                row["superseded_by_id"] = record["id"]
    record["superseded_by_id"] = None
    workspace.facet_routings.append(record)
    store.save(workspace)

    if governance_log is not None:
        governance_log.append(
            project_id=workspace.project_id, event_type="facet_routed",
            actor=actor, role="human",
            payload={"investigation_ref": investigation_ref, "facet_key": facet_key,
                     "routing": routing, "supersedes_id": record["supersedes_id"],
                     "note": "Attention routing. Not an acceptance of any finding."},
            correlation_id=record["id"])
    return dict(record)


def current_routing(workspace: ProjectWorkspace, investigation_ref: str,
                    facet_key: str) -> Optional[dict]:
    """The live routing for one facet, or None if it was never routed."""
    rows = [r for r in workspace.facet_routings
            if r["investigation_ref"] == investigation_ref
            and r["facet_key"] == facet_key
            and not r.get("superseded_by_id")]
    return dict(rows[-1]) if rows else None


def routing_history(workspace: ProjectWorkspace, investigation_ref: str,
                    facet_key: str) -> list[dict]:
    """Every routing this facet has had, oldest first. Why, not just what."""
    return [dict(r) for r in workspace.facet_routings
            if r["investigation_ref"] == investigation_ref
            and r["facet_key"] == facet_key]


def facets_of(workspace: ProjectWorkspace, investigation_ref: str) -> list[dict]:
    """Every facet routed under one investigation, with its live routing.

    Includes the unselected ones, always. An interface built on this cannot
    accidentally show only what was promoted, because there is no filtered
    variant of this function to reach for.
    """
    keys = []
    for row in workspace.facet_routings:
        if row["investigation_ref"] == investigation_ref and row["facet_key"] not in keys:
            keys.append(row["facet_key"])
    return [current_routing(workspace, investigation_ref, key) for key in keys]


# -- Promotion --------------------------------------------------------------

def create_project_from_investigation(
    store: CaseWorkspaceStore,
    source_workspace: ProjectWorkspace,
    *,
    investigation_ref: str,
    new_project_id: str,
    title: str,
    actor: str,
    governance_log=None,
) -> dict:
    """Open a project for the facets a human chose to pursue.

    PROJECT CREATION != AUTHORITY PROMOTION, and the mechanics are copied
    deliberately from `derive_case_from_archive`, whose own governance entry
    reads: "only title/objective (overridable) and source_ids (a reference-list
    copy, never the underlying Source documents) carry onto the derived Case;
    all historical contributions ... remain exclusively attached to the
    archived Case, never cloned."

    The same three properties hold across this boundary:

      1. ONLY ACTIVE FACETS CROSS. Each becomes an OPEN Case carrying the
         facet's own question as its objective - a place to do work, holding no
         conclusion.
      2. NOTHING OPERATIVE IS COPIED. No Finding, no ReviewerValidation, no
         Disposition, no evidence. The new project starts empty of conclusions
         and its Cases have to earn their own.
      3. THE SOURCE INVESTIGATION IS UNTOUCHED. Its facets - promoted and
         unpromoted alike - stay exactly where they are and stay readable.

    Constitutional invariant #9 requires cross-boundary movement to be
    deliberate and attributed, so this records an InvestigationPromotion on
    BOTH workspaces: the source learns what left it, the new project learns
    where it came from. Neither is inferred later from a name or a timestamp.
    """
    if not new_project_id or not title:
        raise CaseWorkspaceError("A promoted project needs an id and a title.")

    routed = [r for r in facets_of(source_workspace, investigation_ref) if r]
    if not routed:
        raise CaseWorkspaceError(
            f"Investigation {investigation_ref} has no routed facets. Route at "
            "least one facet ACTIVE before creating a project from it.")
    promotable = [r for r in routed if r["routing"] in PROMOTABLE_ROUTINGS]
    if not promotable:
        raise CaseWorkspaceError(
            "No facet is ACTIVE. Project creation follows a human's selection; "
            "it does not decide one.")

    existing = store.get(new_project_id)
    if existing is not None:
        raise CaseWorkspaceError(f"Project {new_project_id} already exists.")

    target = store.get_or_create(new_project_id)
    target.display_title = title
    promoted_at = _now()
    promotion_id = _new_id()

    created_cases = []
    for facet in promotable:
        case = store.create_case(
            target,
            title=facet["facet_key"],
            objective=(facet.get("rationale")
                       or f"Carried forward from investigation {investigation_ref} "
                          "for deeper examination. No conclusion is carried with it."),
            created_by=actor)
        created_cases.append({"facet_key": facet["facet_key"], "case_id": case["id"]})

    record = {
        "id": promotion_id,
        "investigation_ref": investigation_ref,
        "source_project_id": source_workspace.project_id,
        "target_project_id": new_project_id,
        "promoted_by": actor,
        "promoted_at": promoted_at,
        "promoted_facets": [c["facet_key"] for c in created_cases],
        # Named, not counted. "Three facets were left behind" is not something a
        # reviewer can act on; their keys are.
        "unpromoted_facets": [
            {"facet_key": r["facet_key"], "routing": r["routing"]}
            for r in routed if r["routing"] not in PROMOTABLE_ROUTINGS],
        "cases": created_cases,
        "carried": "references_and_questions_only",
        "note": ("Project creation is not authority promotion. No finding, "
                 "validation or disposition crossed this boundary."),
    }
    target.investigation_promotions.append(dict(record))
    store.save(target)
    source_workspace.investigation_promotions.append(dict(record))
    store.save(source_workspace)

    if governance_log is not None:
        for project_id in (source_workspace.project_id, new_project_id):
            governance_log.append(
                project_id=project_id, event_type="project_created_from_investigation",
                actor=actor, role="human", payload=dict(record),
                correlation_id=promotion_id)

    return {"project_id": new_project_id, "promotion": record,
            "cases": created_cases}


# -- Facet-scoped reporting -------------------------------------------------

def facet_export_document(workspace: ProjectWorkspace, investigation_ref: str,
                          facet_key: Optional[str] = None):
    """An ExportDocument for one facet, or for the whole routed investigation.

    Built through services/document_export.py's OWN ExportDocument/ExportTable,
    not a second report engine - so the .docx, .xlsx and .pdf of this cannot
    drift apart from each other or from every other export in the product.

    THE UNSELECTED FACETS ARE IN THE REPORT. A facet report that showed only
    what was pursued would quietly answer a different question from the one the
    reader asked, and the omission would be invisible. When one facet is
    requested the others appear in their own short table, so the reader can
    always see what was set aside and under which routing.
    """
    from services.document_export import ExportDocument, ExportTable

    rows = [r for r in facets_of(workspace, investigation_ref) if r]
    if facet_key is not None:
        chosen = [r for r in rows if r["facet_key"] == facet_key]
        if not chosen:
            raise CaseWorkspaceError(
                f"Facet '{facet_key}' has no routing under {investigation_ref}.")
    else:
        chosen = rows

    document = ExportDocument(
        title=(f"Facet report - {facet_key}" if facet_key
               else f"Investigation facets - {investigation_ref}"),
        subtitle=f"Investigation {investigation_ref}",
        preamble=[
            "Facet routing records where a question sits in the reviewer's "
            "attention. It is not a validation of any finding, and nothing in "
            "this report should be read as one.",
        ])

    document.tables.append(ExportTable(
        title="Facet" if facet_key else "Facets",
        headers=["Facet", "Routing", "Rationale", "Decided by", "Decided at"],
        rows=[[r["facet_key"], r["routing"], r.get("rationale") or "",
               r.get("decided_by") or "", r.get("decided_at") or ""]
              for r in chosen],
        note=None))

    if facet_key is not None:
        others = [r for r in rows if r["facet_key"] != facet_key]
        if others:
            document.tables.append(ExportTable(
                title="Not covered by this report",
                headers=["Facet", "Routing"],
                rows=[[r["facet_key"], r["routing"]] for r in others],
                note=("These facets of the same investigation were not the "
                      "subject of this report. They remain recorded and "
                      "unpromoted.")))
        else:
            document.preamble.append(
                "This investigation has no other routed facets.")

    history = [h for r in chosen
               for h in routing_history(workspace, investigation_ref, r["facet_key"])
               if h.get("supersedes_id")]
    if history:
        document.tables.append(ExportTable(
            title="Routing changes",
            headers=["Facet", "Routing", "Decided by", "Decided at"],
            rows=[[h["facet_key"], h["routing"], h.get("decided_by") or "",
                   h.get("decided_at") or ""] for h in history],
            note="Earlier routings are superseded, never removed."))

    return document
