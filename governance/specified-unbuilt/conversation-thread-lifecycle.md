# Specified But Unbuilt — Conversation Thread Lifecycle

**Status: SUPERSEDED, 2026-09-04 — will not be built.** Superseded by
the Disposable Project Workspace model (Section 7 below), on explicit
Product Owner decision. The specification is preserved unchanged beneath
this line because it remains the accurate record of what was designed and
why; nothing in Sections 0-6 has been edited, and none of it governs.

**Prior status, which no longer governs:** Specified, not implemented.
Produced during CLAUDE-P40-E's Unified Document Workspace stage;
deliberately excluded from that stage's implementation because building it
honestly requires a new persisted object and careful provenance-preserving
delete semantics that stage's remaining scope did not have room to do
well, not because the underlying idea is unclear.

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

---

## 7. Supersession — the Disposable Project Workspace model (2026-09-04)

**Decision.** Product Owner, 2026-09-04: Actions 16, 17 and the
thread-bearing remainder of Action 18 are **dropped from scope**. No
`ConversationThread` / `ProjectChatThread` object will be built, no
per-thread pin/hide state, no granular message deletion, and no cascade
or linkage-check rules. Sections 0-6 above stop governing and are
retained as the record of what was designed.

### Root cause, and why it dissolves the requirement

The need for conversation deletion did not come from production practice.
It came from **developer-mode testing and scratchpad trails** accumulated
while refining Codex and Data Room documents — sandbox mess, not a
governed-record problem.

That distinction is the whole decision. A multi-thread management system
with provenance-preserving delete semantics is a large, permanent
mechanism aimed at a temporary condition. The condition has a cheaper
solution at a different level of the system.

### The model that replaces it

- **Projects are disposable test containers.** Developer trials use
  dedicated sandbox projects, deleted or reset wholesale through the
  Project deletion and Reset paths that already exist. Mess is discarded
  at the container, never pruned message by message.
- **Production workspaces retain the single, linear conversation model** —
  `ProjectWorkspace.project_conversation`, one project-wide stream, plus
  each Case's own `conversation` tied to that Case's existing lifecycle.
  No grouping concept above the individual message.
- **`CaseRecord` remains unbloated.** It is not extended to carry chat
  containers, and no lightweight parallel container is introduced beside
  it.

### What this preserves, deliberately

- `CLAUDE-ONE-COMPOSER-01` and `CLAUDE-MOBILE-PRIMARY-RESET-01` remain
  **fully intact and unreversed**. Neither is amended, narrowed, or
  reinterpreted. Conversation history stays where
  `CLAUDE-MOBILE-PRIMARY-RESET-01` put it — the context bar
  (`shell.context.identity`), not a rail beside the composer — on its own
  reasoning, that "which conversations exist is a question that belongs to
  context, not to composing."
- **Section 4's provenance guard is retired unbuilt, not weakened.** It was
  the correct concern: `ComposerFinding.source_message_id` and
  `source_anchor.message_id` are real durable references into
  `project_conversation`, and deleting messages beneath them would orphan
  the provenance of a governed record against
  `constitutional-invariants.md` #3. Not building deletion means that
  hazard is never created. This is the strongest argument for the
  supersession, and it is an argument from safety rather than from cost.
- No deletion of a conversation container exists in the domain model
  today — there is `archive_case` and no `delete_case`. That absence is
  now a deliberate, recorded property rather than an unexamined gap.

### Known deviation, recorded rather than resolved

`routes/workspace.py:start_new_conversation` currently creates a full
`CaseRecord` per "New" click (`create_case(title="New conversation",
objective="Started from the Composer.")`), which is how the context bar's
conversation list is populated today.

This sits in tension with "production workspaces retain the single, linear
conversation model" and with "`CaseRecord` remains unbloated": each new
chat does mint a governed investigative object carrying `status`,
`visibility`, `finding_ids`, `analysis_ids`, `artifact_ids` and archive
authority.

It is recorded here, unresolved and unauthorized for change, because under
the disposable-project model the consequence is bounded — sandbox
accumulation is discarded with the project. **No code change is authorized
by this record.** If Case-per-chat later proves a problem in a production
workspace, that is a separate decision requiring its own authorization,
and this paragraph is the starting evidence for it.

### Lineage

- **Supersedes:** Sections 0-6 of this document (CLAUDE-P40-E, Section F).
- **Supersedes in scope:** Actions 16, 17 and the thread-bearing part of
  Action 18 of the 2026-09-04 New Project / shared Composer tranche.
- **Leaves intact:** `CLAUDE-ONE-COMPOSER-01`,
  `CLAUDE-MOBILE-PRIMARY-RESET-01`, `CaseRecord` and its archive
  lifecycle, `ProjectWorkspace.project_conversation`, and the shared
  Composer shell delivered in `718011c`, which presupposes no thread
  architecture.
- **Authority:** Product Owner decision, 2026-09-04, recorded on the same
  day it was given.
