# Specified But Unbuilt — Per-Item Attention/Review State Model

**Status:** Investigated (CLAUDE-CA1D-ATTENTION-STATE-01, follow-up check
CLAUDE-CA1D-ATTENTION-STATE-01A), **not implemented**. This is the prerequisite
`governance/specified-unbuilt/peripheral-activity-dots.md`'s own close-out addendum named as
blocking that feature: *"GO may only express a sensitive surface when the underlying project state
can support that signal truthfully."* **Unconditional GO** (see L) — the one named prerequisite
check (the `ReviewThread`/`Attention` mechanism, below) has now been read directly and confirmed
not to overlap with the model this document specifies. No code was written under either tranche;
repository inspection and read-only queries only.

## A0. Follow-up check (CLAUDE-CA1D-ATTENTION-STATE-01A) — the named prerequisite, resolved

The original investigation flagged `review_thread_created/resolved/reopened` and
`review_attention_requested`/`attention_responded` as unread GovernanceLog event types that might
already solve part of this problem. Read directly this pass — `ReviewThread`/`ReviewMessage`/
`Attention` (`services/case_workspace.py:2536-2620`, lifecycle methods ~10289-10635) is a real,
fully wired, **rendered** feature (`templates/case_workspace.html:944-1070`) — not dormant, not
UI-less. It is Investigation-scoped human discussion: a `ReviewThread` anchors to a Case or a
Finding (`create_thread` route only ever sets `anchor_type` to `case`/`finding`, though the
underlying `Anchor`/`KNOWN_OBJECT_KINDS` vocabulary is generic enough to support more); anyone can
reply; anyone can explicitly **request Attention** from one specific named person
(`intended_actor`, constrained to real known usernames by the UI's own `<select>{% for username in
known_usernames %}`, even though the dataclass field itself is technically unvalidated free text);
the requesting user's own template already renders `{% if attention.intended_actor ==
session.username %} (you) {% endif %}` — a direct, reusable precedent for "does this concern the
current user" comparisons. Clearing an Attention requires posting a real reply message — a
substantive act, not a lightweight acknowledgment. **`acknowledged_at`/`ATTENTION_STATUS_ACKNOWLEDGED`
exist in the vocabulary but no method anywhere ever sets them** — this codebase already tried once
to build a lighter "I saw this" concept and left it unfinished, a real cautionary precedent for how
non-trivial "meaningful acknowledgment" semantics turn out to be in practice.

**This does not overlap with the ambient "changed since last seen" problem `item_reviewed_at` (D,
below) solves.** `ReviewThread`/`Attention` is explicit and opt-in — someone must deliberately start
a discussion and deliberately address it to a named person. It fires as a side effect of nothing:
ingestion, Source revision, Requirement adjudication, Finding disposition, and Task
creation/completion never create a `ReviewThread`/`Attention` automatically anywhere in this
codebase. Most Findings/Requirements/Sources/Tasks will never have one at all. It genuinely,
fully solves the narrow "attention needed" slice of the six-state model (B, below) for
explicitly-flagged Case/Finding discussions specifically — and is domain-specific/unsuitable as a
general substrate for the ambient case the rest of this document addresses. **Verdict: partially
solves one state (attention-needed, for explicit Case/Finding escalation only); keep separate as
the primary mechanism for everything else; reuse only its GovernanceLog event stream (already
planned) and its `(you)`-comparison UI idiom (informs a later UI tranche, not this one) — do not
extend `ReviewThread`/`Attention` itself to cover ambient per-item change detection, which would
conflate an explicit escalation with an ordinary, undirected change.**

## A. Existing mechanisms discovered

- **`last_viewed_by`** (`ProjectWorkspace`, `services/case_workspace.py:3812`) — `dict[username, ISO
  timestamp]`, per-**project**, per-reviewer, updated by `record_last_viewed` (lines 4724-4788) on
  every Project Home GET. `since_last_visit`/`new_event_count` (`routes/workspace.py:968-988`)
  derives "N updates since you last looked" **at read time** by filtering `GovernanceLog.read(project_id)`
  for `created_at > previous_visit_at` — real, working, but project-granularity, not per-item.
- **`GovernanceLog`** (`services/governance.py`) — `GovernanceEvent{id, project_id, event_type,
  actor, role, payload, predecessor_id, created_at, +optional envelope fields}`, append-only, one
  `.jsonl` per project. **~80 distinct `event_type` values already fire** across nearly every
  domain object (`document_ingested`, `source_revised`, `finding_reviewed`, `requirement_adjudicated`,
  `rfi_draft_created/issued/answered`, `review_thread_created/resolved/reopened/outcome_linked`,
  `review_attention_requested`, `attention_responded`, `temporal_obligation_created`, and more) —
  already the closest thing to a general per-project change-event feed in the app.
- **Finding review/disposition** (`services/case_workspace.py:1626` on) — `Finding` itself carries
  no reviewer/timestamp; review is a **separate, append-only record**: `ReviewerValidation`
  (`{id, finding_id, validation, reviewer, validated_at, correction_note}`, states
  Correct/Incorrect/Partial/Needs Evidence/Not Applicable) and `Disposition` (`{id, finding_id,
  disposition, reviewer, recorded_at}`, states Confirmed/Rejected/Deferred/Known Pending
  Acceptance/Known Accepted — "this, not validation accuracy, is what Apply actually checks").
  Both write a `finding_reviewed` `GovernanceEvent`. **The richest existing "someone made a real
  disposition" pattern in the codebase.**
- **`RequirementAdjudication`** (line 1663) — the requirement-grain analog: append-only,
  `{outcome, adjudicator, adjudicated_at, reasoning, evidence_finding_ids, evidence_relationship_ids,
  attribution}` — `attribution` explicitly distinguishes a real human judgment from an
  agent/automation's.
- **`Requirement`** itself (line 1308) has **no `updated_at`/`modified_at` field at all**; `status`
  is lifecycle-only, never a compliance result (per its own docstring). Revision goes through the
  shared `Supersession` primitive, same as Source.
- **`Source`** revision creates a **new sibling record**, never a mutation — no `revised_at` field
  exists on `Source` itself; the actual "this changed" signal today is a `Supersession` record plus
  a Case-level `RevisionNotice` (its own `created_at`).
- **`Task`** (line 1476) — real `created_at`/`completed_at`/`reopened_at` on the object itself, but
  **not observed** in the ~80-entry `GovernanceLog` `event_type` taxonomy gathered this pass (not
  confirmed absent by an exhaustive grep — flagged as needing direct confirmation, not assumed).
- **`ConversationMessage`** (line 1501) — zero delivered/read/seen concept. Confirmed by two
  explicit in-code comments naming notification fields as **not built/unauthorized**
  (`services/case_workspace.py:1372,1480`).
- **No "notification" concept exists anywhere in Archiosk's own domain model** (confirmed by grep;
  the only hits are the unrelated Claude-Code-harness bridge from a prior tranche).
- **Concurrency**: `CaseWorkspaceStore.save()` (lines 4677-4722) has real optimistic concurrency — a
  `version` counter, `ConcurrentModificationError` on mismatch — but **no route anywhere catches
  that exception**; it would surface as an unhandled 500 today. `record_last_viewed` deliberately
  **bypasses** this versioned path entirely for exactly this reason, instead patching the raw
  on-disk JSON for just `last_viewed_by[reviewer]` under the same `_save_lock`
  (`threading.Lock`, same-process only — a documented, accepted gap for personal/display-only
  metadata, not a structural write).
- **Migration precedent**: no formal migration system for the flat-JSON store at all. The entire
  idiom, proven repeatedly (`tags`/`tasks`/`folders`/`version` itself), is: additive
  `field(default_factory=...)` + defensive `.get(key, default)` on read. A real Alembic/Flask-Migrate
  scaffold (`migrations/`) exists for the separate SQL `User` table, exercised exactly once
  (CLAUDE-P27-B baseline) — available but essentially unproven as a path for this feature.
- **Per-user-per-item state**: no existing precedent anywhere in `services/case_workspace.py`.
  Every existing per-reviewer field (`last_viewed_by`, `starred`, `represented_party_by`) is flat —
  keyed by username only, never `dict[username, dict[object_id, value]]`. A per-item review field
  would be a genuinely new shape, but one that follows the same additive-field idiom every other
  field already established, with a direct write-path template to copy (`record_last_viewed`'s raw
  patch, not `save()`'s versioned path).

## B. Semantic gaps (against the six requested states)

| State | Exists today? |
|---|---|
| Selected | Yes — `.launcher-link.active`/`.current-project` CSS + session `selected_object:` |
| Changed | Partial, per entity — GovernanceLog covers most mutations; no uniform per-object "current revision" field (Source/Requirement both lack one) |
| Unreviewed/unseen change | **No — the actual gap.** Only project-granularity (`last_viewed_by`) exists |
| Attention needed | Not as a distinct concept — but `review_attention_requested`/`attention_responded` GovernanceLog event types exist and were **not** drilled into this pass (see K/L) |
| Blocker/adverse | No generic cross-entity concept; `Disposition`'s "Rejected"/`ReviewerValidation`'s "Incorrect" are the closest entity-specific analogs |
| Resolved/acknowledged | `Disposition` is the closest real "resolved" concept, entity-specific to Findings |

## C. Candidate architectures, ranked

Ranked against the stated commercial priority hierarchy (MVP speed → safety/governance →
reliable first expert user → maintainability/concurrency where it accelerates delivery → future
extensibility → elegance):

1. **Derived-only over existing `GovernanceLog` + finer-grained `last_viewed_by`** — no new
   persisted "reviewed" field; extend `last_viewed_by` itself to per-item. Doesn't actually work
   alone: a single per-project timestamp can't distinguish "visited the project" from "reviewed
   this specific item" without becoming per-item anyway — this candidate collapses into #2.
2. **New `item_reviewed_at: dict[username, dict[object_id, timestamp]]`**, written via
   `record_last_viewed`'s exact raw-patch-under-`_save_lock` pattern (not `save()`); "changed"
   derived at read time by comparing against the item's latest relevant `GovernanceLog` event
   (already proven for `since_last_visit`) — **no new write-side bookkeeping for "changed" at all,
   only for "reviewed."**
3. **Per-object revision counters + per-user reviewed-revision counters** — more robust against
   clock-skew than timestamps, but requires adding a revision counter to entities that don't have
   one (Requirement, Source) — a bigger, more invasive lift for a robustness gain this app's
   existing microsecond-precision ISO timestamps likely don't need in practice.
4. **A new generic append-only "attention events" log**, mirroring `GovernanceLog`'s own shape.
   Architecturally the most elegant (matches this codebase's own repeated preference for
   append-only actor+timestamp records), the heaviest lift, and the highest risk of blurring the
   line between "personal/display-only metadata" and "governed audit trail" that this codebase has
   otherwise been careful to keep separate (`GovernanceLog`'s own `actor`/`role` are explicitly "an
   audit label, not verified identity" — a second log with a similar shape but different meaning
   invites confusion).
5. **Entity-specific acknowledgment records**, no generic mechanism at all — mirror
   `Disposition`/`ReviewerValidation` exactly, per entity type, one at a time. Cheapest per entity,
   doesn't generalize without repeating the pattern.

**Ranked: 2, then 5, then 3, then 4, then 1 (collapses into 2).** Recommended shape is **2**, built
with **5's minimalism of scope** — one shared field, populated/consumed for one entity type first,
not a premature generic subsystem (4).

## D. Recommended minimum viable model

- New field: `item_reviewed_at: dict[str, dict[str, str]] = field(default_factory=dict)` on
  `ProjectWorkspace` — outer key username, inner key object id, value ISO timestamp.
- Write path: `CaseWorkspaceStore.record_item_reviewed(workspace, reviewer, object_id)` — mirrors
  `record_last_viewed` exactly (raw JSON patch under `_save_lock`, never the versioned `save()`
  path — this is personal/display-only metadata, not a structural write, same category as
  `last_viewed_by`/`starred`).
- Read-side derivation (pure function, no new persistence for "changed" itself):
  `has_unreviewed_change(workspace, governance_log, reviewer, object_id) -> bool` — compares
  `item_reviewed_at.get(reviewer, {}).get(object_id)` against the latest relevant `GovernanceLog`
  event's `created_at` for that object id. **Defaults to `True` (unreviewed) whenever no record
  exists** — never a false "already reviewed," matching the same conservative-default discipline
  `services/dev_session_status.py` already established this session for a different bridge.
- This directly solves the named failure mode ("user reviews object → object changes again →
  system still thinks it's reviewed"): a later `GovernanceLog` event for the same object id after
  the stored review timestamp reverts the derivation to `True` automatically — no synthetic
  revision-ID scheme needed, because `GovernanceLog` is already a reliable, monotonic, append-only
  timeline per object.

## E. Recommended first entity type(s) for proof

**Findings.** Richest existing disposition mechanism already in place (`ReviewerValidation`/
`Disposition`), already logs `finding_reviewed` events, already has dedicated per-item UI real
estate (Toolbox findings list). Tasks are the plausible second candidate (real timestamps exist)
but their lifecycle events were not confirmed present in `GovernanceLog`'s taxonomy this pass —
proving the mechanism on Findings first, where the derivation is already end-to-end grounded, is
lower-risk than starting with an entity whose "changed" signal may need a different derivation path.

## F. Review/acknowledgment semantics

No dwell-time threshold — none exists as a precedent anywhere in this codebase, and inventing one
now would be exactly the "fake precision" this investigation was told to avoid. Hover explicitly
never counts (per instruction). Recommended default: **recording a real `Disposition`/
`ReviewerValidation` for a Finding counts as review by construction** — it's the strongest possible
signal (an actual judgment was made) and requires zero new UI trigger, since it's already an
existing action. For entity types without an existing disposition mechanism (Tasks), the smallest
defensible fallback is explicit navigation to the item's own detail view — not scroll-past, not
hover, not merely appearing in a list.

## G. Project/user isolation implications

`item_reviewed_at` is keyed by the same real authenticated username every other per-user field
already uses, read/written through the exact same `_load_workspace_or_404`/`can_access_project`
gate as everything else — no new authorization surface. **A read path must filter to the requesting
user's own key only** (`.get(session["username"])`), matching how `last_viewed_by` is already only
ever read via `.get(_reviewer())`, never enumerated wholesale — one user's review state must never
be exposed to another, even though the underlying dict technically holds every user's entries.

## H. Migration and concurrency implications

Zero formal migration: pure additive field, safe default, defensive read — proven repeatedly by
`tags`/`tasks`/`folders`/`version` itself. No backward-compat break; a legacy on-disk record simply
lacks the key. Concurrency: use `record_last_viewed`'s raw-patch pattern, not `save()`'s versioned
path, sidestepping the disclosed, currently-unhandled `ConcurrentModificationError` risk entirely.
Two different users reviewing the same item concurrently is not actually a write conflict (different
dict keys); the only real race — the same user's browser firing two near-simultaneous review calls —
already has the same accepted, disclosed same-process-only lock gap `last_viewed_by` already has.
Rollback is trivial (an unused additive field). Not written to `GovernanceLog` — deliberately, same
"personal, non-governed" category as `last_viewed_by`.

## I. How this could later drive peripheral activity dots

Directly. `governance/specified-unbuilt/peripheral-activity-dots.md`'s own Open Question 1 — the
per-project-only granularity of `last_viewed_by` — is exactly what `item_reviewed_at` (D) resolves.
Trailing-edge dot placement (already recommended in that document) plus `--machine-blue` for the
ordinary "changed, not yet reviewed" case becomes directly implementable once this field exists;
nothing in this model conflicts with that document's other open questions.

## J. How this could later feed a PM Situational Gauge roll-up

The same per-item derived boolean, aggregated (count/percentage of items with unreviewed changes,
grouped by project or section), becomes the gauge's number — "the gauge summarizes; the drill-down
explains" maps directly onto "aggregate the derivation" vs. "show the same Lists tree with dots."
No composite "project health" score is invented; it's a count over already-truthful per-item state.

## K. Risks / counterarguments

- **Resolved by CLAUDE-CA1D-ATTENTION-STATE-01A (A0, above)**: the `ReviewThread`/`Attention`
  mechanism was read directly and confirmed to be a real, fully-wired, rendered feature — but a
  narrow, explicit/opt-in Case-and-Finding-scoped discussion-escalation tool, not a general
  ambient-change substrate. It does not overlap with, and does not need to be integrated into, the
  model in D. No redesign required.
- Task's `GovernanceLog` coverage is still unconfirmed, not confirmed-absent — a direct grep should
  precede designing Task's own derivation path.
- **A genuinely smaller alternative exists for Findings specifically**: since `ReviewerValidation`/
  `Disposition` already record `reviewer` + a timestamp whenever a human engages with a Finding, an
  even smaller MVP could derive "reviewed" for Findings as "the current disposition's own reviewer
  is this user" — **zero new persisted field at all** for that one entity type. This is real,
  already-existing, free signal, and should be weighed against D before writing any new code — the
  tradeoff is that it means "reviewed" = "made a judgment call," not "merely looked at it," which
  the Product Owner has not yet chosen between (both are named as valid options in the original
  request).
- Notification-infrastructure-debt risk: low for the recommended model (a bounded dict field, no
  new subsystem, no background jobs) — the risk is concentrated in Candidate 4, which is why it's
  ranked last.
- The `--seal-red`/`--failure-red` color-collision risk already named in the activity-dots document
  remains open and unresolved by this investigation — correctly out of scope here, not a new gap.

## L. GO / NO-GO recommendation

**Unconditional GO.** Implementation-ready in every dimension investigated (D through J); the one
named prerequisite (A0) has been read directly and confirmed not to require any redesign of this
document's own model. Still awaiting separate Product Owner authorization to actually begin
implementation — this document specifies readiness, not authorization.

**Smallest bounded implementation tranche:**

1. `item_reviewed_at: dict[str, dict[str, str]] = field(default_factory=dict)` on `ProjectWorkspace`.
2. `CaseWorkspaceStore.record_item_reviewed(workspace, reviewer, object_id)` — mirrors
   `record_last_viewed`'s write pattern exactly.
3. A pure `has_unreviewed_change(...)` read-side derivation function — no new persistence for
   "changed" itself.
4. Wire exactly one call site: recording a real Finding `Disposition`/`ReviewerValidation` also
   calls `record_item_reviewed` for that finding.
5. **No UI changes in this tranche** — no dot, no colored name — proving the derivation alone first,
   the same discipline `CLAUDE-CA1D-LIVE-BRIDGE-01` already used for the session-state bridge.

**Acceptance tests (synthetic fixtures):**
- No `item_reviewed_at` key at all → `has_unreviewed_change` → `True` (conservative default).
- Finding created, no disposition yet → `True`.
- Disposition recorded by user A → `False` for A, still `True` for user B (per-user isolation).
- A second disposition/validation recorded after the first review → reverts to `True` (the named
  failure mode, actually exercised).
- A legacy on-disk workspace missing the field entirely → loads without error.
- Two different users recording review for the same item near-simultaneously → both entries persist
  (no lost update — different dict keys).

**If the prerequisite check instead finds substantial overlap**, the correct prerequisite is:
re-derive Section D against whatever `review_thread`/`attention_requested` actually is, not build a
second, parallel mechanism next to it.
