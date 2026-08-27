"""
CLAUDE-UNIFIED-READ-EXPERIMENT-01 - one conversation, read across the
containers that already hold it.

STATUS: EXPERIMENT. Nothing in the product calls this yet.

THE QUESTION IT EXISTS TO ANSWER

A user in one project today has 1 + N conversations: `project_conversation`,
plus one `Case.conversation` per Case. `start_new_conversation` literally
creates a Case to hold a conversation. So the thread forks per object, and the
user experiences containers as separate chats.

The proposal is that they should experience ONE continuous conversation with GO,
while governance keeps the containers exactly as they are. This module tests
whether that read is possible without changing a single write.

WHY THIS IS SAFE TO TRY

It is derived, never persisted - the same discipline recent_anchors_for already
states for itself: "read straight from ConversationMessage records that already
exist for other reasons, so this can never drift from what actually happened or
become an opaque second source of truth."

That method is also the precedent for the hard part. It already reads across
every visible Case conversation plus the project conversation for one reviewer,
filtered by visible case ids. Cross-container, visibility-correct reading is not
new here; this promotes it from a "where did I leave off" trail to the primary
read.

WHAT IT DELIBERATELY DOES NOT DO

- It writes nothing. No new field, no new file, no migration.
- It never merges the Developer Mode conversation. Those turns live in the
  session and must never enter a project record; keeping them physically apart
  is the whole reason a scope TAG was judged insufficient. A unified READ over
  project containers does not require them, so this experiment does not touch
  them.
- It never bypasses Case privacy. Visibility comes from
  CaseWorkspaceStore.visible_cases_for - the single ratified enforcement point -
  and never from filtering workspace.cases directly. That exact shortcut caused
  a real cross-user title disclosure in this codebase; it is not repeated here.
"""
from __future__ import annotations

from typing import Iterable, Optional

SCOPE_PROJECT = "project"
SCOPE_CASE = "case"


def _entry(message: dict, scope: str, case_id: Optional[str], case_title: Optional[str]) -> dict:
    """One turn, carrying where it came from.

    The message itself is copied, never mutated: this is a read, and a read that
    edits its source is not a read.
    """
    entry = dict(message)
    entry["scope"] = scope
    entry["case_id"] = case_id
    entry["case_title"] = case_title
    return entry


def read_unified_conversation(
    store, workspace, reviewer: str, limit: Optional[int] = None,
) -> list[dict]:
    """This reviewer's whole project conversation, in the order it happened.

    Merges the project-level conversation with every Case conversation the
    reviewer may actually see, newest LAST so it reads like a thread rather than
    a feed. Each turn carries `scope` and, for Case turns, `case_id`/`case_title`
    so a caller can still tell where a turn belongs without the user having to
    change rooms to read it.

    `limit` trims to the most recent N turns while preserving order.
    """
    visible = store.visible_cases_for(workspace, reviewer)
    merged: list[dict] = []

    for message in (workspace.project_conversation or []):
        merged.append(_entry(message, SCOPE_PROJECT, None, None))

    for case in visible:
        title = case.get("title")
        for message in (case.get("conversation") or []):
            merged.append(_entry(message, SCOPE_CASE, case.get("id"), title))

    # created_at is an ISO timestamp, so lexical order is chronological order.
    # Ties keep a stable order by id rather than by whichever container was
    # walked first - two turns in the same second must not reshuffle per call.
    merged.sort(key=lambda m: (m.get("created_at") or "", m.get("id") or ""))

    if limit is not None and limit >= 0:
        merged = merged[-limit:] if limit else []
    return merged


def scopes_present(entries: Iterable[dict]) -> set:
    return {entry.get("scope") for entry in entries}


def case_ids_present(entries: Iterable[dict]) -> set:
    return {entry.get("case_id") for entry in entries if entry.get("case_id")}


def continuity_report(entries: list[dict]) -> dict:
    """The measurement this experiment exists to produce.

    Does the merged stream actually read as one conversation? The honest proxy:
    how often it crosses between containers. A thread that alternates freely
    between project-level and Case turns is one conversation the containers were
    slicing; a thread that never alternates was genuinely separate work and the
    merge bought nothing.
    """
    crossings = 0
    previous = None
    for entry in entries:
        key = (entry.get("scope"), entry.get("case_id"))
        if previous is not None and key != previous:
            crossings += 1
        previous = key
    return {
        "turns": len(entries),
        "containers": len(case_ids_present(entries)) + (
            1 if SCOPE_PROJECT in scopes_present(entries) else 0),
        "container_crossings": crossings,
        "reads_as_one_thread": crossings > 0,
    }
