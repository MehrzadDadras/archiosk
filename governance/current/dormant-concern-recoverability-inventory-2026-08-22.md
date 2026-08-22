# Dormant-Concern Recoverability Inventory

Status: read-only repository inventory, 2026-08-22
Repository inventory SHA: `4534843528f15816c484c042c4b9339703157a9c`
Vision context: [`../vision/VIS-004.md`](../vision/VIS-004.md) · [`../vision/ANA-003.md`](../vision/ANA-003.md)
Requesting record: [`../specified-unbuilt/adaptive-attention-and-context-circulation.md`](../specified-unbuilt/adaptive-attention-and-context-circulation.md)

**NO IMPLEMENTATION AUTHORITY CREATED. NO NEW ARCHITECTURE AUTHORIZED.**

This is an evidence record. It changes no runtime behavior, route, schema, template,
test, vocabulary, or contract, and it creates no object, registry, watcher,
scheduler, event bus, or memory subsystem.

`specified-unbuilt/adaptive-attention-and-context-circulation.md` remains **NOT
AUTHORIZED** for implementation **and for further design**. That record asks that any
future gate *"start the same way every prior FUTURE-prefixed investigation in this
corpus has: a repository-grounded inventory of what already exists before proposing
anything new."* This record is that inventory step and nothing beyond it. It does not
lift, narrow, or reinterpret that status.

## Question inventoried

What existing ARCHIOSK primitives already provide toward recoverability of a
previously unresolved concern when relevant project context reappears — traced as
*episode evidence → contextual identity → persistence → unresolved state → future cue
→ current-state derivation → bounded resurfacing*.

## Verdict

**MOST SUBSTRATE ALREADY EXISTS — CONNECTIONS ARE MISSING.**

## A. Central finding

> **The system already records what would resolve a concern, and already re-derives
> current truth on context cues. It does not compare the two.**

Recorded as the smallest observed design pressure. It is **not** an implementation
requirement, and the comparison is deliberately not designed here.

## B. Existing substrate found

Primitives already carrying part of the behavior, under other names. This list is
evidence of what was inspected — **not a capability registry**, and not a component
inventory to be maintained.

| primitive | what it already provides |
|---|---|
| `services/project_clock.py` `reconcile_project()` | Context cue → current-state derivation → bounded unrequested resurfacing |
| `CaseWorkspaceStore.has_unreviewed_change` | Per-reviewer *"has this materially changed since you last reviewed it"*, derived never stored |
| `resolve_relationship_status` | Read-time status with an explicit precedence chain |
| `resolve_source_reference_status` | Re-resolves a preserved citation against current governed Requirements |
| `current_governing_requirement` | Walks the supersession chain forward from any id, current or historical |
| Persisted selection ([`ca1b-persistent-professional-context.md`](ca1b-persistent-professional-context.md)) | Project-scoped referent restored on re-entry, re-resolved every render |
| `Anchor` | Open-world *"what this was about"* pointer across many object kinds |
| `GovernanceLog` | Durable append-only event trace with `correlation_id` and `trigger` |
| `ComposerFinding.unresolved_question` | A required field — every finding durably records what remains open |
| `Claim.recommended_next_check` | What would be needed to resolve, alongside `assumptions` and `evidence_excluded` |
| `TemporalObligation` | Baseline preserved, current date derived, revision by successor not mutation |
| `ReviewThread` | Seven statuses including `RESOLVED`, `CLOSED`, `REOPENED` with `reopened_by`/`reopened_at` |
| `Task` | `COMPLETED` plus `reopen_task` |
| `candidate_referents` | Stored disambiguation candidates resolved by a later turn's context |
| Spin `prior_findings` / `changed_source_keys` | Prior understanding carried into a new pass under changed context |
| `Supersession` | Predecessor preserved; currency derived, never overwritten |

## C. True precedents found

**C-1 — Condition-triggered resurfacing already runs in production.**
`project_clock.reconcile_project()` is invoked on the workspace GET path. Its own
call-site comment records the semantics plainly: the route *"[makes] a GET request
capable of writing (a governance event, and occasionally a thin `CLOCK_INITIATED`
Analysis) where GET requests were previously pure reads… this is incidental
background work triggered by a page view, **not something the reviewer explicitly
asked for**."* That is the full chain — cue, derivation, bounded resurfacing, without
a query — implemented once, for one condition (time), on one cue (workspace entry).

**C-2 — Current truth derived from preserved history.** Four independent
implementations follow the rule the `Relationship` docstring states as governing —
*"store flat, derive at read time"*, with an explicit prohibition on storing a
second, potentially-drifting copy: `resolve_relationship_status`,
`resolve_source_reference_status`, `current_governing_requirement`, and
`has_unreviewed_change`. Present context can therefore alter interpretation **without
rewriting history**.

**C-3 — Context restoration on re-entry.** Persisted selection survives refresh,
route round-trip and application restart; does not survive sign-out; is re-resolved
against the real workspace on every render so a deleted object never renders as
selected; per-project keys are independent by construction.

**C-4 — Non-destructive release.** `ReviewThread` resolve/close/reopen (both
judgments retained on the record), `Task` complete/reopen, Case archive/restore,
Source remove/restore, and Supersession all release without deleting.

## D. Genuine gaps found

Recorded as audit findings. **No solution is proposed for any of them.**

1. **Cue vocabulary is narrow.** The only implemented cue precedent is effectively
   time-on-workspace-entry. Selection change, Source revision, Requirement
   registration, supersession and relationship confirmation all already occur; none
   is a cue for anything previously set aside.
2. **No unified episode identity.** `correlation_id`, `spin_run_id`, `case_id` and
   `Anchor` each bind a portion of a concern. No current object binds question +
   evidence + context + release reason as one addressable episode.
3. **Recorded resolution conditions are inert.** `recommended_next_check` and
   `unresolved_question` preserve what remains unresolved; nothing compares those
   recorded conditions against newly arriving context or evidence.
4. **`ComposerFinding` lacks release semantics.** `KNOWN_COMPOSER_FINDING_STATES` is
   a deliberately one-member closed set (`machine_finding_unreviewed`). Its own
   comment already anticipates *"a future PM-reviewed/accepted/modified/dismissed
   state"* as a vocabulary addition. Release exists for threads, tasks, cases and
   sources — not for the object Spin and the Composer actually produce.

## E. What is already sufficient

**No new memory subsystem is justified by this inventory.** Existing substrate was
found for every stage of the traced chain: episode evidence (`InvestigationStep`,
`Claim` with validated `evidence_links`, `ComposerFinding`, `SpinRun`); contextual
identity (`Anchor`, `correlation_id`, `case_id`, `origin_context`); durable
persistence; unresolved-state representation; read-time current-state derivation;
bounded resurfacing; release; and authority containment.

Future work in this area should first attempt composition of existing primitives
before proposing new infrastructure.

## F. Relationship to existing records

- **[`VIS-004`](../vision/VIS-004.md) / [`ANA-003`](../vision/ANA-003.md)** — this
  record is repository evidence *underneath* that vision, not a new vision principle.
  Broad cognition / selective attention / narrow authority, reinstatement by
  condition, attention release, and human-facing coherence versus internal
  serialization are stated there and are **not restated here**.
- **`specified-unbuilt/adaptive-attention-and-context-circulation.md`** — **NOT
  AUTHORIZED**, unchanged. This inventory fulfils only its own requested
  repository-grounded inventory step.
- **[`GO-PROJECT-MEMORY-01`](../prompt-depository/GO-PROJECT-MEMORY-01.md)**
  (DEFERRED) — already covers episode memory and human-initiated closure/re-entry as
  programme intent. This inventory found **no implemented condition-triggered episode
  reinstatement**. The programme is not expanded.
- **[`GO-HELIX-01`](../prompt-depository/GO-HELIX-01.md) /
  [`CIC-SPIN-INTELLIGENCE`](contracts/CIC-SPIN-INTELLIGENCE-v1.1.md) v1.1** — Spin
  already carries `prior_findings` and `changed_source_keys` into a new run and
  evaluates what materially changed. That is a bounded precedent for re-evaluating
  prior understanding under changed context. **Spin is not redefined.**
- **[`GOV-P-001`](../records/GOV-P-001.md) v1.0** — governs throughout. Every
  primitive above is read-only or writes an audit event; none authorizes mutation.

## G. Authority

> **Context may make a concern relevant again. That does not authorize mutation.**

This is an application of `GOV-P-001` — selection is context, not authorization — not
a new principle. Approval, publication, external communication and canonical project
change remain governed by `_require_approval` and the existing authority boundaries,
none of which is reachable from any primitive listed above.

## H. Vocabulary

No new production terms were introduced. Specifically **not** created:
`DormantEpisode`, `CognitiveEpisode`, `ReinstatementTrigger`, `AttentionState`,
`ContextHook`, subscription objects, watchers, cognitive schedulers, episode buses,
or memory engines. The terminology used above is the terminology already present in
the repository.

## I. Method and limits

Read-only inspection of `services/`, `routes/`, `templates/`, and the governance
corpus at the SHA above. No project state was read or written; no store was opened
for write; no test was run against a live external boundary.

The inventory traced capability rather than naming — primitives were included because
of what they do, not because they are called memory, attention, or dormancy. Absence
of evidence is reported as such: where no precedent was found, none is claimed.
