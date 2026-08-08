# ARCHIOSK Self-Project Commissioning Readiness (CLAUDE-POSTCAMEL-COMM-A1)

**Status:** Audit complete. **READY WITH PREPARATION.** Authorized after the
POST-CAMEL canonical-root stabilization sequence closed clean (ROOT-A1,
ROOT-I1, ROOT-A2, ROOT-I2, ROOT-I3 — ending commit `a89d612`). This is
explicitly **not** a capability-build stage and **not** a continuation of
the ROOT sequence — its objective was to determine, through a real,
disposable, live experiment rather than assumption, whether ARCHIOSK's
current domain model can host **the creation of ARCHIOSK itself** as a
governed project and use that project to commission/test itself, ahead of
a separately-authored, still-in-reconciliation Owner Project Requirements
document (developed by Gemini, explicitly not ingested, fabricated, or
substituted during this gate).

This document is the canonical record of that assessment: what was
tested, what was found, what remains a residual, and the resulting
readiness recommendation. It does not restate the ROOT-A1/ROOT-A2
architecture crosswalks or the ROOT-I1–I3 implementation reports — only
what this gate's own audit added.

**Governance-corpus note on this document's own placement:** it lives in
`governance/current/` — alongside `kernel-object-model.md` and
`pilot-readiness-postcamel-p01.md` — rather than `specified-unbuilt/`,
because COMM-A1 is a readiness *audit of existing, already-authorized
capability*, not a record of a designed-but-not-yet-authorized future
capability. No new domain object, route, or capability was authorized or
built by this gate.

---

## Framing

Per this gate's own governing prompt, the finalized Owner RFP (in
reconciliation, authored separately) was **not** ingested, fabricated, or
substituted. Every finding below that depends on real Requirement/
Compliance content uses either already-sealed disposable fixtures from
prior ROOT-I gates or a fresh, small, disposable experiment created and
permanently deleted during this gate — never the Gemini document.

## A. Repository State

- `HEAD == origin/main == a89d612`, confirmed at the start of this gate.
- Working tree clean except the pre-existing untracked
  `tests/fixtures/nreocrc/_lab_instance_scratch_002/` fixture — read-only
  all session, untouched again here.
- Test baseline entering this gate: 2969 passed, 0 failures (ROOT-I3's own
  closing run).
- No repository file was changed producing the audit itself — confirmed by
  `git status --short` showing only that same pre-existing untracked
  fixture immediately before this record was written.

## B. Self-Project Feasibility

Tested adversarially rather than assumed. Every core pathway a
commissioning exercise actually needs — creating the project, registering
Requirements, adjudicating them, seeing project-level Compliance, opening
Investigations, recording Findings — was exercised live this gate against
a real, disposable project named "ARCHIOSK Application Development
Project," not reasoned about from documentation alone.

**Verdict: READY WITH MINOR PREPARATION.** No defect found blocks hosting
the self-project. Every friction point below has a workable, already-
existing accommodation — none required new code to route around during
this gate's own live test.

## C. Project Creation Findings

Created live: a real project named "ARCHIOSK Application Development
Project (COMM-A1 experiment)," Client/Owner environment, founding Source a
plain narrative note (not RFP-shaped), then permanently deleted via the
real confirm-gated delete route. Findings below are what that experiment
actually showed, not inference.

- **Project name uniqueness** is a general registry-wide mechanism with no
  construction-specific constraint — the name created without friction.
- **No mandatory field assumes RFP content** — the upload page's own copy
  already generalizes to "RFPs, RFQs, specs, contracts, reports, meeting
  minutes."
- **`Source.kind` is genuinely open-world** (`services/formatting.py`'s
  own comment: "never a closed enum") — a future Source could be tagged
  something more precise than the auto-registered default without a
  schema change.
- **The auto-registered founding Source is hard-coded to
  `rfq_rfp_document`** internally (`CaseWorkspaceStore.get_or_create`)
  regardless of actual content — but `formatting.py`'s own
  `_SOURCE_KIND_LABELS` already glosses this to the neutral "Project
  Document" at display time, confirmed live (the founding note rendered
  as "PROJECT DOCUMENT," never "RFQ/RFP"). Real internal-naming residual;
  zero user-visible impact.
- **`operating_environment` is a strict binary** (Client/Owner or
  Design-Builder/Proponent, confirmed at the Gateway itself — only two
  creation buttons exist) with no neutral "internal project" third option.
  Recommend **Client/Owner** for the self-project: matches the human
  Product Owner's real acceptance authority and Gemini's Owner-
  Requirements-steward role.
- That choice has a real, named cost: `rfi_originate` (drafting and
  issuing a question) is **only available to the Design-Builder/Proponent
  side** (`services/environment_capabilities.py`'s own capability matrix,
  `client_variant=None`). Under Client/Owner, Claude cannot formally
  "issue an RFI" asking about the OPR — workable via an ordinary
  Investigation/Discussion instead, since RFIs are optional, not required
  for Compliance to function.
- **The requirement-extraction pipeline produced 4 noisy "candidate
  requirements"** from the plain narrative founding note during this
  gate's own live test — ordinary prose sentences tagged "scope of work"
  at 85% confidence, none of which are real obligations. Never
  auto-promoted (a human must explicitly promote each candidate), so no
  incorrect governed data results — but historical/narrative Sources
  should expect noisy candidates a reviewer simply declines.

## D. Source Package Architecture

Mapped onto existing primitives — no new object type in any row.

| Category | Examples | Existing primitive |
|---|---|---|
| Governing Source | The finalized Gemini OPR, once approved | `Source` — `Source.kind` is open-world, so a future ingestion path could tag it precisely instead of relying on the generic auto-registered default |
| Supporting Evidence | CAMEL/POST-CAMEL reports, Claude implementation reports, screenshots, test evidence | `Source` (kind `text_record`/`project_document`) — proof of what was done, cited from Requirements/Findings, never rewritten |
| Historical Record | Navigation evolution, panel concepts, ROOT sequence, appearance decisions, superseded direction | Chiefly the self-project's own future `GovernanceLog` once real actions happen inside it; pre-project git history enters as ordinary read-only `Source` records, never re-run through requirement extraction |
| Working Product | A future Commissioning Report, Punch List summary, Substantial Completion record | `WorkProduct` — its existing draft → reviewed → approved → issued lifecycle is exactly what a close-out deliverable needs, already built |

The one real design decision this raises: historical/narrative material
should enter through whichever path skips machine requirement-extraction
— the noisy-candidate finding in Section C applies to any prose Source.
Confirming exactly which existing ingestion route does this is listed as
bounded prep work in Section O, not solved here.

## E. Owner RFP Ingestion Test Plan (once approved)

| Check | Already built? |
|---|---|
| 1. Ingest as the principal governing Source | Yes — ordinary `/upload` flow |
| 2. Preserve Owner identifiers (`OPR-X.X`) | Yes — `Requirement.original_requirement_identifier` |
| 3. Extract Requirements without losing source identity | Yes — every `Requirement` carries `source_id` |
| 4. Owner ID vs. ARCHIOSK internal identity, kept distinct | Yes — `original_requirement_identifier` vs. UUID `id` |
| 5. Preserve source location/provenance | Yes — `Requirement.source_location` |
| 6. Avoid duplicate Requirements | Manual — no automated dedup exists; a reviewer discipline, not a build item |
| 7. Handle amendments/refinements | Yes — `revise_requirement_route` + `Supersession` |
| 8. Expose the Requirements branch | Yes — ROOT-I1 |
| 9. Show project-level Compliance | Yes — ROOT-I2 |
| 10. Drill from Compliance to Requirement to source | Yes — ROOT-I2's `?status=` filter |

Eight of ten checks are already-built, already-tested mechanisms. The
future test is confirming they behave correctly against real OPR content
— not constructing new capability.

## F. Reference-Schedule Accuracy Test

No automated diff/scoring infrastructure exists for this today, and none
should be built now. At OPR scale (dozens to low hundreds of items, not
thousands), a manual reconciliation — open the Requirements page, walk
Gemini's structured schedule row by row, note misses/duplicates/incorrect
splits-or-merges/wrong identifiers/wrong source anchors — is genuinely
sufficient with current capability. A future Requirements CSV export
would make this faster but is a usability aid, not a prerequisite.

## G. Compliance Readiness

ROOT-I2's rollup already answers the question verbatim — Satisfied /
Partially Satisfied / Not Satisfied / Accepted Alternative / Not
Applicable / Not Yet Assessed is exactly `REQUIREMENT_ADJUDICATION_OUTCOMES`
plus the derived "not yet assessed" state, already built and tested
against a live project this session.

Gap, named honestly rather than solved: none of the five real outcomes
are phrased as construction-completion decisions. Accepted Alternative
and Not Applicable are close enough in spirit to carry "accepted
residual" and "explicitly out of scope" respectively without new
vocabulary — but this is a mapping decision for whoever runs real
commissioning, not something to invent now. No new compliance vocabulary
is recommended.

## H. Punch List Architecture Finding

A construction Punch List item is, in ARCHIOSK's own existing vocabulary,
an unresolved Finding (or an adverse Requirement adjudication) that must
be corrected before close-out — exactly the shape Needs Attention
(ROOT-A1) and the Compliance rollup (ROOT-I2) already successfully
generalized once each.

**Finding: a Punch List is a future projection over existing
`Requirement` + `RequirementAdjudication` + `Finding` + `Disposition` +
optionally a linked `Task` — the same pattern, applied a third time, not
a new canonical `PunchListItem` class.**

One real limitation worth naming: `Task` deliberately has no assignee or
due-date field (its own docstring — an earlier, explicit scope boundary).
A full construction-grade Punch List would need either accepting that
minimalism or a small, separately-authorized extension. **Not decided or
implemented here** — recommend a dedicated future architecture gate
before building the projection.

## I. Completion-State Model

| State | Represented via |
|---|---|
| Commissioning | An `Investigation` whose objective is literally "verify Requirement X is met" |
| Substantial Completion | A dated `ProjectContextEntry` recording the Product Owner's own acceptance narrative and named residuals |
| Operational Readiness / Occupancy | An observation, not an object — evidenced by real recorded usage (this session's own six ROOT-I/COMM gates already are that evidence) |
| Punch List | The Section H projection, once built (future work) |
| Accepted Residual | `RequirementAdjudication` outcome (Accepted Alternative/Not Applicable) + its own mandatory `reasoning` field |
| Future Programme | Deliberately not a Requirement at all — lives in `governance/specified-unbuilt/`, a real, already-active mechanism (15 documents) |
| Final Completion | Punch List projection empty + a terminal `ProjectContextEntry`/Decision recording final acceptance |

None of the seven completion states require a new canonical domain
object.

## J. Historical Evolution

Reconfirms ROOT-A2's own finding rather than re-deriving it: `GovernanceLog`
plus each object's own append-only sub-history (`Supersession`,
`RequirementAdjudication` chains) already form a decentralized,
non-destructive event record sufficient to reconstruct "earlier direction
→ later refinement → current accepted state." No event-sourcing rebuild
is needed for commissioning evidence, and none was attempted here.

## K. Registry/Numbering Prerequisite Decision

**Not required before commissioning — usability residual.** Owner-side
citation is already solved (`original_requirement_identifier` preserves
`OPR-X.X`). The gap Registry/Numbering would close matters more for
polished external reports than for running the commissioning process
itself, and the self-project's expected scale doesn't yet demonstrate
urgency.

## L. Risk Prerequisite Decision

**Not required before commissioning.** Confirmed with stronger evidence
than ROOT-A2 had: a Risk register is already creatable today as an
ordinary `WorkProduct` — `artifact_type="risk_register"` is a real,
already-present option in the existing "+ New Work Product" form
(observed directly during this session's ROOT-I3 walkthrough). A
dedicated canonical Risk object remains a legitimate future question, but
its absence blocks nothing.

## M. First-Run Testing Decision

**Useful commissioning aid, not required.** The manual throwaway-admin-
account + disposable-project + real-delete-gate pattern this session used
across six independent gates has already proven itself a reliable
substitute. A one-click Preview would be nicer but its absence has not
obstructed a single walkthrough.

## N. Zero-Founder Commissioning Plan

- **A — Create/Open Self-Project:** testable now — done live, this gate.
- **B — Governing RFP:** blocked until the approved Owner RFP lands.
- **C — Requirements (structure):** testable now; real-OPR-content flavor
  waits on B.
- **D — Compliance:** testable now — ROOT-I2 already proven.
- **E — Evidence:** testable now.
- **F — Deficiency:** testable now — proven repeatedly this session.
- **G — Accepted Residual:** the underlying distinction is testable now;
  the dedicated Punch List surface is future work.
- **H — Future Programme:** testable now — `governance/specified-unbuilt/`
  already real and populated.
- **I — Return Path:** testable now — proven identically across every
  ROOT-I walkthrough.
- **J — Project Isolation:** testable now — explicitly proven.

Eight of ten scenarios are already testable today. Only Scenario B, and
the real-content flavor of C, wait on the approved Owner RFP.

## O. Minimum Preparatory Work (ordered)

1. Decide the operating environment — record Client/Owner as the
   self-project's choice.
2. Create the real self-project — once a sensible founding Source is
   chosen (a short charter note, never the unfinished Gemini draft).
3. Confirm the extraction-skipping ingestion path — verify which existing
   route avoids the noisy-candidate behaviour found in Section C before
   bulk-loading history.
4. Populate Supporting Evidence and Historical Record — CAMEL/
   POST-CAMEL/ROOT reports, via the path confirmed in step 3.
5. Run the Owner RFP Ingestion Test Plan (Section E) — once Gemini's OPR
   is approved.
6. Manually reconcile against Gemini's structured schedule (Section F) —
   at least once, before relying on Compliance for real decisions.
7. Begin real Investigation/Finding/Compliance-driven commissioning —
   only after steps 1-6.

Registry/Numbering, the Punch List projection, a canonical Risk object,
and a First-Run Preview are explicitly not on this list.

## P. Current Baseline Boundary

None of the following were promoted into baseline by any finding in this
gate: Venue/Director programme, artist mode, bee/nature-research mode,
education/math mode, animation/movie mode, Project Memory / Re-Entry
Briefing, Terminal Eye, PowerPoint/presentation expansion, Surface Trust,
Ushering Agent, Project Object Registry/Numbering (Section K), new
canonical Risk architecture (Section L), merged event/history view,
speculative local-only/air-gapped architecture, enterprise clusters,
Opportunity Radar, or any other unratified future idea.

## Q. Recommendation

**READY WITH PREPARATION.**

The building can host its own commissioning process. Every friction point
found this gate — the binary operating environment, the RFI-origination
gap, the noisy extraction on non-RFP prose, the internal
`rfq_rfp_document` naming residual — was tested live, confirmed workable
without new code, and is smaller than the self-project idea's own
attractiveness might have suggested. Complete the bounded, RFP-
independent preparatory steps (Section O, 1-4) now; begin real
Requirement/Compliance-driven commissioning once the approved Owner RFP
lands. Registry/Numbering, Risk architecture, the Punch List projection,
and First-Run Preview are **not** begun automatically by this record —
each remains its own future decision requiring its own authorization.

No repository files were changed by the audit itself; the throwaway
experiment project ("ARCHIOSK Application Development Project (COMM-A1
experiment)") and its throwaway admin account were both created and
permanently deleted through the ordinary product, via the real
confirm-gated delete route, during this gate.

## Record-Keeping Note

This document was committed to `governance/current/` following an
explicit product-owner instruction that substantial programme-gate
reports, architecture audits, commissioning reports, acceptance reports,
punch-list records, and close-out findings are durable project records by
default, not disposable scratch analysis, and must not be left solely in
a temporary session scratchpad or an external artifact link. Temporary
working copies (Markdown/HTML) may still exist outside the repository
during drafting; this file is the authoritative copy of record.

**Observed but not acted on in this pass:** the ROOT-A1 → ROOT-A2 →
ROOT-I1 → ROOT-I2 → ROOT-I3 sequence that preceded COMM-A1 was delivered
via Artifact links during those sessions and was not, at the time,
separately committed into `governance/STATUS.md`'s own programme table or
`governance/current/`. This document's own STATUS.md row (below) is the
first point at which that sequence is referenced from the governance
corpus. Whether to retroactively backfill dedicated STATUS.md rows/
`governance/current/` records for ROOT-A1 through ROOT-I3 individually is
a separate decision, not undertaken here to avoid starting a new,
unrequested programme.
