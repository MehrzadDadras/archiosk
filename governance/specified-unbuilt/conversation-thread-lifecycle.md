# Specified But Unbuilt — Conversation Thread Lifecycle

**Status:** Specified, not implemented. Produced during CLAUDE-P40-E's
Unified Document Workspace stage; deliberately excluded from that
stage's implementation because building it honestly requires a new
persisted object and careful provenance-preserving delete semantics
that stage's remaining scope did not have room to do well, not because
the underlying idea is unclear.

## 0. Why this exists

CLAUDE-P40-E asked for a compact bottom conversation dock supporting
multiple named conversation threads over time (Start New / Archive /
History / Restore / Delete), while displaying only one active thread.
That stage shipped the dock itself — the existing Case-level
`conversation` and project-level `project_conversation` message lists,
docked to the bottom of the Workspace via CSS, with draft/scroll
preservation across navigation (see `CONTINUATION_CHECKPOINT.md`'s
CLAUDE-P40-E entry) — but never introduced the thread-grouping concept
itself. This document is the honest record of what that would take,
so it isn't lost or silently reinvented differently later.

## 1. What already exists, and what's genuinely missing

`ProjectWorkspace.project_conversation: list[dict]` (a flat list of
`ConversationMessage` dicts, one project-wide stream) and each Case's
own `conversation: list[dict]` (Case-scoped, tied to that Case's own
archive/derive lifecycle already). Neither has any grouping concept
above the individual message — there is no `ConversationThread`
object, no title, no archived/active status, nothing to "start new,"
"archive," or "restore" at all. `services/case_workspace.py`'s
`add_message`/`project_conversation_for` operate on the flat list
directly.

## 2. Scope this document deliberately narrows to

Per CLAUDE-P40-E's own instruction, only **project-level** conversation
is in scope for this future work — Case-level `conversation` already
has a real lifecycle tied to the Case's own status (open/archived/
derived), and introducing a second, independently-toggleable "archive
this conversation" control on top of that would compete with, not
complement, the existing Case archival model. A Case's own archive/
derive actions remain the only lifecycle its conversation needs.

## 3. Domain model (proposed, not built)

```python
@dataclass
class ConversationThread:
    """A named, orderable grouping of project-level ConversationMessages -
    exactly one THREAD is 'active' (the one the dock currently shows) at
    any time; the rest are archived, still fully readable via History."""
    id: str
    project_id: str
    title: str
    status: str  # "active" | "archived" | "trashed" (soft-delete)
    created_by: str
    created_at: str
    last_activity_at: str
    message_ids: list[str] = field(default_factory=list)  # references into project_conversation, not a copy
```

`ProjectWorkspace.conversation_threads: list[dict]` (new field, default
`[]`). **Compatibility, not migration:** an existing project's flat
`project_conversation` list becomes thread #1 ("General") the first
time this feature loads that project — synthesized in memory at read
time (same pattern as `CaseWorkspaceStore._hydrate_legacy_cases`/
`_hydrate_legacy_reviews`, see `services/case_workspace.py`), never a
destructive rewrite of the persisted message list itself. Existing
messages keep their real `id`s; the synthesized thread's
`message_ids` just enumerates whichever messages predate this
feature's own first save.

## 4. Operations (proposed)

- `start_new_conversation_thread(workspace, title, actor)` — creates a
  new thread, makes it active (previous active thread's `status`
  becomes `"archived"` automatically — only one active thread at a
  time, per CLAUDE-P40-E's own "displaying only one active thread").
  Does **not** touch `active_case`/`selected_source` — Section F #1's
  own explicit rule ("Starting a new conversation does not change or
  close the document currently displayed in Workspace") is a route-
  layer concern, not a store-layer one, and needs no new mechanism
  beyond simply not touching those query params.
- `archive_conversation_thread(workspace, thread_id, actor)` —
  reversible, sets `status="archived"`. If it was the active thread,
  the most-recently-active OTHER thread (or a synthesized empty one)
  becomes active.
- `restore_conversation_thread(workspace, thread_id, actor)` — sets
  the selected thread `status="active"`, and the previously-active
  thread to `"archived"` (same mutual-exclusion as start-new).
- `soft_delete_conversation_thread(workspace, thread_id, actor)` —
  `status="trashed"`, reuses the confirmation-gate pattern
  `routes/workspace.py`'s `_require_approval` already establishes
  (`confirm=once|session|no`) rather than a bare POST.
- **Provenance guard, the genuinely hard part:** before soft-delete is
  permitted, check whether any message in `message_ids` is referenced
  by a Finding/RFI/Requirement adjudication/Accepted Knowledge item's
  own provenance trail. No current `ConversationMessage` field records
  "this specific message caused Finding X" directly — establishing
  that check honestly requires either (a) auditing every governed
  write path that currently reads conversation context to see which
  already capture a message id in their own provenance, and adding it
  everywhere that doesn't, or (b) a conservative, honest fallback: warn
  the reviewer and require an explicit second confirmation when a
  thread has ANY messages that predate a governed record touching the
  same Case/Finding, rather than claiming precise per-message
  traceability the current schema doesn't actually have. Whichever is
  chosen, Section F #6/#7's requirement ("permanent deletion must not
  break the provenance of a Finding, decision, RFI, accepted-knowledge
  item, or saved pattern") must be genuinely enforced, not assumed.
  **This is the specific piece that made "implement it for real this
  stage" irresponsible to attempt alongside everything else CLAUDE-P40-E
  already covered — it needs its own dedicated audit, not a rushed
  guess.**
- **True permanent deletion** (beyond soft-delete/trash) is out of
  scope entirely until the provenance guard above exists — "recoverable
  trash where repository conventions support it" (Section F #5) is the
  ceiling for this feature until then.

## 5. Route/template wiring (proposed)

`routes/workspace.py`: `start_conversation_thread`, `archive_
conversation_thread`, `restore_conversation_thread`,
`delete_conversation_thread` (all POST, all going through
`_load_workspace_or_404` — the same P32 project-authorization gate
every other workspace route already uses, per Section F #8's explicit
requirement). `case_workspace.html`: a "Conversation History" 
subdisclosure inside the dock (titles + created/last-activity dates,
per Section F #3), each entry linking to Restore.

## 6. Tests a real implementation would need

Start-new doesn't touch `?case=`/`?source=`; Archive is reversible and
message content is byte-for-byte preserved; History lists by editable
title/created/last-activity; Restore makes the selected thread the one
the dock shows; Delete requires the confirmation gate and moves to
`trashed`, never a hard delete; a thread with governed-record-linked
messages is blocked or requires the stronger warning path; every
operation 404s for a non-owner/non-allow-listed/non-admin session,
matching every existing workspace-route test's own convention.
