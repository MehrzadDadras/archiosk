# Specified But Unbuilt — Navigation & Context Operational Map

**Status:** Living reference document (not a feature spec). Created under
`CLAUDE-GO-NAVIGATION-CONTEXT-GAMES-01` (two rounds of repository-grounded
investigation, both read-only, both run as forked sub-agents) and its Product
Owner disposition approving this file. Populated only with findings the two
investigation rounds and the earlier `CLAUDE-WORKSPACE-SHELVING-ARCHITECTURE-01`
review actually established against real code — nothing here is invented or
extrapolated beyond that evidence. Every row below carries its own confidence
and provenance so a future reader (human or Claude) can tell a settled fact
from a live recommendation without re-deriving it.

**Purpose:** stop this codebase's navigation/context defects from being
independently rediscovered in future sessions (this document exists because
one already was — see the Document List/Thumbnails row below, found twice in
one session before this file existed). Read this before re-investigating
navigation/context/return-path behavior; update it when a game or a real
architectural change contradicts a row.

**Explicitly not this document's job:** duplicating `MANIFEST.md`, `UI_REFERENCE_MAP.md`,
or any other existing repository documentation; describing UI element
inventories (see `UI_REFERENCE_MAP.md` for that); prescribing an
implementation before one is proven. Keep this file's own size proportional
to what's operationally load-bearing — do not expand it "just in case."

**Freshness anchor:** every row below is accurate as of commit `48b4468`
(2026-08-16). If the referenced file/line has since changed, the row's own
confidence should be treated as stale until re-verified, not trusted at face
value.

---

## How to read this table

- **Confidence** — High (directly confirmed by reading the real code/tests),
  Medium (a reasoned recommendation, not yet implemented or PO-approved),
  Low (a hypothesis worth checking, not yet confirmed).
- **Status** — `settled fact` (safe to assume without re-verifying),
  `open defect` (real, confirmed, not yet fixed), `dispositioned` (Product
  Owner has already ruled on it — don't re-litigate), `recommendation`
  (proposed, awaiting or partially through approval), `piloting` (an
  approved, bounded experiment is in progress — see its own section below).

| # | Finding | Confidence | Status | Provenance |
|---|---|---|---|---|
| 1 | Every route resolves objects by UUID first (`project_id`, `source_id`, `case_id`, `finding_id`); display name/filename is presentation-only, never a lookup key. Similarly-named objects never collide. | High | settled fact | Navigation Games Round 1, Game F1 — confirmed at `routes/portal.py` `_project_summary`/`app.py` `menu_open_project_choices` |
| 2 | `operating_environment` is a project-owned, locked-once-at-creation field (`services/case_workspace.py`). It is never a per-account/per-User field, and `is_admin()` has zero coupling to it. | High | settled fact | This session's Option C implementation + earlier plan-mode audit, cross-checked in both Games rounds |
| 3 | **Split-state defect**: the "current document" a user is viewing has two independent authorities — server truth (`?source=` on `workspace.show_workspace`) and a client-only `localStorage` "remembered last PDF" (`static/js/pdf_viewer.js`) — that can disagree with **no visual signal** distinguishing them on the Document List. | High | open defect (fix approved, not yet implemented) | Found independently twice in one session: Workspace Shelving review (Addendum B) and Navigation Games Round 1 (Game H2) — same root cause, two different investigative framings. Product Owner approved a fix (independent row-level indicator on the Document List; do not repurpose Mark/X, Keep-on-Main, Eye, or Gear) |
| 4 | **Exactly one** "return to where I came from" mechanism exists anywhere in this codebase: a `document.referrer`/`history.back()` heuristic on `templates/project_chooser.html`'s own back link. It is not reused by any other page. | High | settled fact | Navigation Games Round 1, direct code read |
| 5 | **No internal link carries origin/purpose state.** Every navigation link (Composer hotlinks, breadcrumbs, cross-object references) is built as a plain `url_for(...)` with forward-only state (destination), never backward state (why the user is going, what to return to) — with one deliberate exception (#6). This is the single largest, most generalizable navigation defect found. | High | open defect | Navigation Games Round 1, Cluster 1 (Games A1, D1, G2) — e.g. `app.py`'s `render_conversation_hotlinks` builds hotlink URLs with only `source_id`, no return context |
| 6 | **Working exception to #5**: the `?case=&preview_finding_id=` redirect (`routes/workspace.py`, RFI-preview flow) is a real, deliberate, working example of purpose surviving a redirect. Proves the pattern is cheap to build when done on purpose. | High | settled fact (reference pattern) | Navigation Games Round 1, Game C1 |
| 7 | `InvestigationStep.question` (the reviewer's own real purpose, verbatim) + `evidence_examined_ids` (real record ids, never text copies) are already linked in one record at the data layer — but this linkage is never surfaced anywhere as a UI return path. | High | settled fact (data layer) / open gap (UI layer) | Navigation Games Round 1, Game B1 — `services/case_workspace.py` `InvestigationStep` |
| 8 | `RFIDraft.reference_snapshot` is a deliberate point-in-time copy of the Case/Finding/Artifact/Source reference chain, specifically so a draft survives the source later being renamed, moved, or superseded. This is the correct, proven pattern for "acquired evidence must survive the source object changing later." | High | settled fact (reference pattern) | Navigation Games Round 1, Game G1 — `services/case_workspace.py` `RFIDraft` |
| 9 | Nothing in this codebase corrupts an object's canonical shelf/home based on where it was opened from — Investigations, Documents, etc. always re-derive their shelf membership fresh from stable project-scoped state, never from navigation history. | High | settled fact | Navigation Games Round 1, Game I1; Workspace Shelving review |
| 10 | Compare's on/off state and second-document selection are held in a plain in-memory JS variable (`static/js/eye_pane.js`) with **no persistence** — any navigation or refresh silently resets it. | High | dispositioned | Navigation Games Round 1, Game H1. Product Owner has already ruled this is intentional: "current-state evidence, not a future product decision." A timestamped Comparison Report remains a separate, outstanding, unrelated question — do not conflate the two. |
| 11 | `Anchor` (`services/case_workspace.py`) is a generic, already-reused, open-world "what this is about" pointer (`anchor_type`, `anchor_id`, `source_id`, `location`, `description`) — the closest existing primitive to an origin/target pointer for a future excursion mechanism. | High | settled fact | Navigation Games Round 1, Section A |
| 12 | The following governance-sounding names, referenced across both rounds of the Navigation Games prompts, are confirmed **absent** from both `governance/` and code — purely aspirational vocabulary in the prompts themselves, not descriptions of an existing mechanism: `CLAUDE-GO-TRAJECTORY-RECALL-01`, `CLAUDE-GO-CONTEXT-AWARENESS-01`, `CLAUDE-GO-USHERING-AGENT-01`, `CLAUDE-GO-WORK-PATH-NAVIGATION-01`, `CLAUDE-SURFACE-QUIET-CAPABILITY-01`, `CLAUDE-GATEKEEPER-01`, `CLAUDE-AGENT-ORCHESTRATION-GOVERNOR-01`, `CLAUDE-VALIDATION-ISOLATION-01`, `CLAUDE-CAPABILITY-RELOCATION-INTEGRITY-01`. The closest real, formal record of an attention/context model is `governance/specified-unbuilt/adaptive-attention-and-context-circulation.md` (status: **NOT AUTHORIZED**), which independently names the same primitives (`InvestigationStep`, `Relationship`, `GovernanceLog`, `Anchor`) as this document's own findings. | High | settled fact | Navigation Games Rounds 1 and 2, exhaustive repo-wide grep both times |
| 13 | Smallest generalized fix for #5: an `Anchor`-shaped `origin_kind`/`origin_id`/`purpose` parameter set any "go look at something" link could carry, resolved server-side into a small, quiet, optional "Return to [origin]" affordance — composition of #6 and #11's existing shapes, not a new subsystem. | Medium | piloting | Navigation Games Round 1, Section G. Product Owner approved a bounded, reversible pilot scoped to Composer hotlinks only (see "Active pilot" below) — not yet generalized. |

---

## Reusable organized understanding (do not re-derive)

Rows 1, 2, 9, and 11 above are settled facts a future task can cite directly
rather than re-verifying. Row 3 and row 10 are each already the subject of a
specific Product Owner disposition — future work should implement/respect
those dispositions, not re-open the question of whether they're real or
correct.

## Known contamination boundary

An unverified fork/agent finding must not be treated as canonical until
checked against real evidence (a test run, a direct file read, an explicit
Product Owner ruling) — this file's own rows are labeled with confidence
specifically so a `Medium`/`recommendation` row is never read as already
decided.

---

## Active pilot — Composer hotlink origin pointer

**Approved scope (Product Owner, 2026-08-16):** test row 13's approach on
Composer hotlinks only (`app.py`'s `render_conversation_hotlinks` /
`services/case_workspace.py`'s `resolve_conversation_hotlinks`) — the
highest-frequency real "go look at something" action in the app (Navigation
Games Round 1, Games A1/G2). Explicit purpose: **prove or disprove** whether
purpose-aware return can be achieved by composing existing primitives
(`Anchor`'s shape, the `?case=&preview_finding_id=` redirect precedent)
rather than building a new navigation framework — not to ship a finished
feature. Report the pilot's result here (and to the Product Owner) before
widening it to any other surface (breadcrumbs, other cross-object links).

**Result:** *(pending — implementation not yet started as of this entry)*
