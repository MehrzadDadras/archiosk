# Foundational Integrity Developmental Commissioning (CLAUDE-POSTCAMEL-COMM-I4)

**Status: FOUNDATIONAL INTEGRITY COMMISSIONING ASSESSED — PRODUCT OWNER
REVIEW REQUIRED.** Authorized following COMM-I3B's sealed authority
model (`governance/current/comm-i3b-product-owner-authority-seal-and-scale-readiness.md`,
commit `1bcab22`). Assesses eight Current Baseline Requirements
(OPR-1.1, OPR-1.2, OPR-1.3, OPR-2.1, OPR-2.2, OPR-2.4, OPR-2.5, OPR-5.4)
on both axes. **Per this stage's own explicit instruction and
COMM-I3B's own standing rule, NO new `RequirementAdjudication` record
was created for any of the eight — every outcome below is an agent
assessment awaiting Product Owner review, not a governed adjudication.**

---

## Governing-input check

`HEAD == origin/main == 1bcab22` confirmed before this stage began;
working tree clean except the pre-existing untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/` fixture. The real
commissioning specimen was re-confirmed unchanged: 34 governed
Requirements, 4 `RequirementAdjudication` records (all `Satisfied`,
`archiosk_commissioning`), 13 unpromoted candidates — **no new
adjudication was added by this stage.**

---

## B. OPR-1.1 — Project Creation

**AGENT ASSESSMENT — PRODUCT OWNER REVIEW REQUIRED: Satisfied.**
`services/ingestion.py`'s own comment states project creation "always
generates a brand-new project_id" [DIRECT]. Live-verified this stage:
five distinct, real, pre-existing projects in this deployment each
carry their own unique UUID (`0b743d80-...`, `0afa4891-...`,
`494cb8af-...`, `b4a5adde-...`, `052bcc0d-...`), confirmed on the real
Projects list, not fabricated for this test [DIRECT].

**Developmental finding — Early-and-Sound Conception [DIRECT].**
UUID-based `project_id` is the only format found anywhere in this
session's repeated direct registry inspection — no legacy non-UUID
format was ever encountered. No relevant decision needed correction;
no deviation found; every governed dataclass depends on this identity
holding.

**RFP translation:** *Does the Owner require projects to be creatable
and independently identifiable before any other system integration is
designed around a single, fixed project?*

## C. OPR-1.2 — Project Isolation

**AGENT ASSESSMENT — PRODUCT OWNER REVIEW REQUIRED: Satisfied**, with
one requirement-text/product-scope mismatch honestly noted (see below).

**Special scrutiny finding — two different kinds of isolation must not
be conflated:**

1. **Data partitioning (storage-level isolation): Early-and-Sound
   Conception [DIRECT].** Every governed dataclass (`Source`,
   `Requirement`, `RequirementAdjudication`, etc.) carries `project_id`
   as a required, non-optional field from its own class definition, and
   `CaseWorkspaceStore.get`/`save` resolve to one physical file per
   `project_id` (`self._path_for(project_id)`) — structural partitioning
   present since this method's earliest observable form, not layered on
   top of shared storage. Live-verified this stage: switching from the
   real commissioning project to a real, independent, pre-existing
   project ("Nipigon Ramp") showed completely disjoint document/
   requirement/conversation counts with zero leakage in either
   direction, then switching back showed the original project's full
   state (34 governed Requirements, 4 adjudications, 13 candidates)
   completely intact.
2. **Access authorization (who may open a project at all): Timely
   Correction, not Early-and-Sound [DIRECT for the fact of the gap;
   REASONABLE INFERENCE for its timeliness].** `governance/STATUS.md`'s
   own CLAUDE-P32 row states this row's own reason for existing: it
   "closes the P27-review-flagged gap that any authenticated user could
   open any project by knowing/guessing its `project_id`" — meaning a
   real, admitted period existed where data partitioning alone did not
   prevent an authenticated user from opening someone else's project.
   This was found via this repository's own internal review process
   (P27) and closed at P32, not discovered by an external incident
   report — DIRECT for that sequence, but no exact elapsed-time record
   exists to confirm how quickly the gap was closed relative to when it
   was introduced, so "timely" (versus "late") is REASONABLE INFERENCE,
   not directly evidenced.

**Requirement-text/product-scope mismatch, honestly noted:** OPR-1.2's
text names "vector embeddings" as something requiring per-project
isolation. `services/learning_governance.py`'s own docstring states
directly: *"this repository has no shared-learning, model-training, or
cross-customer corpus mechanism of any kind. No fine-tuning pipeline,
no embedding index shared across projects... confirmed by repository
inspection"* [DIRECT]. No vector-embedding system exists anywhere in
this codebase. Isolation trivially holds for a capability that was
never built — this is not a deficiency, but it is the same shape of
finding as OPR-1.4/OPR-7.4 in COMM-I3: the OPR's own text assumes a
broader capability than the product actually has.

**RFP translation:** *Which specific categories of data does the
Owner's own compliance regime require strictly separated, and does the
Owner's definition of "isolation" include who may access a project, not
only where its data physically lives?*

## D. OPR-1.3 — Project Switching

**AGENT ASSESSMENT — PRODUCT OWNER REVIEW REQUIRED: Satisfied.**
Live-verified this stage, not merely inferred from OPR-3.6's own prior
"Persistence" evidence: a real round-trip switch (commissioning
project → Nipigon Ramp → back) left the commissioning project's full
state (34 Requirements, 4 adjudications, 13 candidates, 4 Documents)
byte-identical to before the switch [DIRECT].

**Developmental finding — Early-and-Sound Conception [DIRECT].**
Rests on the same per-project file-store persistence as OPR-1.2's data
partitioning; no separate mechanism, no deviation found.

**RFP translation:** *Will the Owner's users work across multiple
concurrent projects, and if so, what state must survive a switch (open
document, active filters, unsent draft text)?*

## E. OPR-2.1 — Multi-Format Ingestion

**AGENT ASSESSMENT — PRODUCT OWNER REVIEW REQUIRED: Satisfied.**
`governance/STATUS.md`'s Camel Multimodal Programme row: PDF (MM2),
spreadsheets (MM3), drawings (MM4), images (MM5) are each
**IMPLEMENTED, bounded**, with prior live-browser verification already
on record (MM9's own real-PDF/real-.xlsx round trip) [DIRECT]. Not
re-verified live this stage — no new claim is being made beyond what
MM1–MM9's own already-committed record already establishes.

**Developmental finding — Early-and-Sound Conception [DIRECT].** MM1's
evidence contract (`StructuralUnit`/`AddressableRegion`/`EvidenceItem`)
was designed once and extended per modality (MM2–MM5) without rework —
`governance/STATUS.md`'s own sequential MM-row structure is the direct
evidence. No modality required a prior modality's design to be
corrected.

**RFP translation:** *What document formats will this Owner/discipline
actually submit, and does that list match what's supported today before
a procurement commitment is made on the strength of it?*

## F. OPR-2.2 — Source Identity

**AGENT ASSESSMENT — PRODUCT OWNER REVIEW REQUIRED: Satisfied.**
`Source.id` is assigned once via `_new_id()` at creation and never
reassigned by any code path found in this session's repeated direct
inspection; `Source`'s own docstring states "canonical identity is this
record's `id`, not its `file_path` or `name`... retains this identity
even if later renamed or reorganized" [DIRECT]. Confirmed further this
stage: no rename mutator exists for `Source.name` at all —
`update_source_identity` never touches `name`/`file_path` — so a
Source's display name is immutable today by omission of any mutator,
not merely by a tested guarantee. Worth distinguishing honestly: this
makes renaming-breaks-identity a non-issue because renaming isn't
offered, not because it was exercised and proven safe under load.

**Developmental finding — Early-and-Sound Conception [DIRECT].** Same
foundational discipline OPR-3.5 (COMM-I3) already found for canonical
ownership generally — this Requirement reinforces, rather than
duplicates, that finding at the Source-identity grain specifically.

**RFP translation:** *Does the Owner need documents renamed or
relocated (e.g. a Data Room reorganization) without breaking internal
references, and by when must that be proven rather than assumed?*

## G. OPR-2.4 — Provenance Maintenance

**AGENT ASSESSMENT — PRODUCT OWNER REVIEW REQUIRED: Satisfied**, for
the MM1-onward baseline.

**Developmental finding — Early-and-Sound Conception for MM1 onward
[DIRECT]; Insufficient Evidence for anything before it.** MM1's own
`governance/STATUS.md` row describes the citation resolver
(`resolve_region_citation`, evidence sachets) as designed into the
evidence contract from MM1's own outset, not retrofitted later. As
already found in COMM-I2/COMM-I3, the Requirement Schedule's own
"Supersedes/Refines" column notes OPR-2.4 "Refines OPR-4.2 (Rev 0)" —
Rev 0's actual text was never supplied to this session, so nothing
about what changed or why can be characterized beyond the fact that a
change occurred. Not re-litigated further here; carried forward as the
same open item.

**RFP translation:** *What is the smallest unit of evidence (a page, a
clause, a cell) the Owner will actually cite in a dispute, and is that
the granularity this system's citation anchors actually use?*

## H. OPR-2.5 — Revision Tracking

**AGENT ASSESSMENT — PRODUCT OWNER REVIEW REQUIRED: Partially
Satisfied.** This is the one substantive gap this tranche found.

**Same Source moved/renamed vs. new revision/superseding Source
(required distinction, Section 8):**

- **Moved/renamed:** as OPR-2.2 already found, no rename/move mutator
  exists for `Source.name`/`file_path` at all — the case cannot
  currently occur through the product, so it cannot currently break
  identity either.
- **New revision/superseding Source:** `CaseWorkspaceStore.register_source_revision`
  creates a genuinely NEW `Source` (new `id`), links it via
  `supersedes_source_id`/`superseded_by_source_id` plus an authoritative
  `Supersession` record, and never mutates or deletes the original —
  confirmed directly in code [DIRECT]. This is real, correct, and
  exactly matches the "a changed document is not merely a changed
  location" principle **for the case it covers.**

**The gap:** `register_source_revision` is hardcoded to
`kind=SOURCE_KIND_DRAWING` — confirmed by direct repository-wide search
that it is the **only** call site anywhere that ever sets
`supersedes_source_id` [DIRECT]. There is currently no product path to
formally register a revision or addendum for any non-drawing Source —
a revised PDF, a revised text record, or a future revision of the
adopted OPR document itself would have to be added as a brand-new,
structurally disconnected Source with no supersession relationship
recorded. This is not a new discovery: MM2's own `governance/STATUS.md`
row already states this exact limitation in its own words — *"though
only via the existing drawings-scoped `register_source_revision`, not a
general PDF/document revision path"* [DIRECT] — meaning this gap has
been known and self-documented since MM2 shipped, and no later stage
(including COMM-A1 through COMM-I3B) had assessed it against OPR-2.5
specifically until now.

**Developmental finding — Unresolved Developmental Deficiency
[DIRECT].**

1. **Conception window [DIRECT]:** MM1 (the general evidence contract)
   or MM2 (the first document-modality stage) — either was a natural
   point to generalize `register_source_revision` beyond drawings.
2. **First evidenced recognition [DIRECT]:** MM2's own STATUS.md row,
   at the time MM2 shipped — this was self-disclosed, not discovered by
   a later audit.
3. **Relevant decision [DIRECT]:** MM2 scoped its own citation
   staleness-awareness to reuse `Source.superseded_by_source_id` as a
   read-time signal, without building the general write-time
   registration path itself.
4. **Earliest detectable deviation [DIRECT]:** present since MM2's own
   ship date — the gap was named, not hidden, but never subsequently
   closed.
5. **Prevention opportunity [INSUFFICIENT EVIDENCE]:** no record
   explains why a fast-follow never happened; nothing supports
   speculating whether it was deliberately deferred or simply not
   revisited.
6. **Downstream dependents [DIRECT]:** the adopted OPR document itself,
   the founding charter, and both curated text records are all
   non-drawing Sources with no available supersession path — if the
   Product Owner ever issues a "Revision 0.2B" of the OPR, ARCHIOSK
   itself would have no way to formally link it to Revision 0.2A the
   way it already can for two drawing revisions.
7. **Consequence of delayed recognition [INSUFFICIENT EVIDENCE for
   cost]:** no rework has occurred (nothing was ever built assuming the
   general case existed), so no cost is attributable; the exposure is
   presently live and concrete (item 6), not merely historical.
8. **Present implementation condition:** partially satisfies OPR-2.5 —
   real for drawings, absent for every other Source kind.
9. **Verification evidence:** direct repository search (this stage) plus
   MM2's own STATUS.md text (prior stage, self-disclosed).
10. **Remaining disposition:** a genuine open item for the Product
    Owner — see the decision package below. **Not fixed this stage**,
    per this stage's own explicit "do not build new features merely to
    make a Requirement pass" boundary.

**RFP translation:** *Will the Owner issue formal addenda or revisions
to non-drawing documents (specifications, schedules, the RFP itself),
and does the system's revision-tracking need to cover that case
specifically, not only drawings?*

## I. OPR-5.4 — Isolation Enforcement

**AGENT ASSESSMENT — PRODUCT OWNER REVIEW REQUIRED: Satisfied.**
`services/project_qa.py`'s `answer_project_question` — this codebase's
representative AI-facing, evidence-grounded function — takes explicit,
caller-supplied lists (`candidate_requirements`, `governed_requirements`,
`milestones`) as plain parameters; it has no `project_id` argument and
no means to fetch data from any project other than whatever its caller
already loaded via the single-project `_load_workspace_or_404` pathway
[DIRECT]. Reinforced by OPR-1.2's own finding: no shared embedding index
or cross-project corpus exists for an AI call to draw on even if it
wanted to (`learning_governance.py`'s own confirmation) [DIRECT]. P31's
`ACTION_EXTERNAL_AI_REQUEST` gate (`ai_calls_disabled` kill switch) adds
a further, separate control over any outbound AI call generally.

**Special scrutiny answer:** no code path was found where a single AI
request assembles evidence spanning more than one `project_id` — this
is a structural absence (no function offers a cross-project fetch
primitive to misuse), not merely an absence of any code that happens to
call one.

**Developmental finding — Early-and-Sound Conception [DIRECT].** No
dedicated cross-project AI boundary needed to be retrofitted, because
the AI-facing functions were never given the means to reach across
projects in the first place.

**RFP translation:** *Does the Owner require a demonstrable guarantee
that AI-assisted answers never draw on another client's or another
project's data, and can that guarantee be shown structurally rather
than asserted by policy alone?*

---

## J. Cross-case formative lessons

- **"Isolation" is not one thing.** OPR-1.2's plain-language text
  ("prevented from crossing project boundaries") bundles storage-level
  data partitioning (early-and-sound, structural) with access-level
  authorization (a real, later-corrected gap, P32) as if they were the
  same guarantee. Future OPR drafting and future commissioning passes
  should keep these explicitly separate, the same way COMM-I3 already
  learned to separate implementation-side from requirements-drafting-
  side corrections.
- **OPR-2.5 is this tranche's genuine finding, not a restatement of a
  known-and-closed item.** It is the first Unresolved Developmental
  Deficiency found across the twelve Requirements examined so far
  (COMM-I3's four plus this tranche's eight) — a real, live, currently
  unaddressed scope gap, self-disclosed by MM2 but never assessed
  against its governing OPR requirement until this stage.
- **ID-based reference, never path/name-based, is this codebase's single
  most consistently early-and-sound architectural decision.** OPR-3.5
  (COMM-I3), OPR-2.2, OPR-1.1, OPR-1.2's data layer, and OPR-5.4 all
  trace back to the same underlying discipline, independently confirmed
  five separate times now rather than assumed to generalize from one.
- **Requirement-text/product-scope mismatches are a recurring, usually
  harmless pattern**, not a one-off: OPR-1.4 and OPR-7.4 (COMM-I3) and
  now OPR-1.2's "vector embeddings" reference all name a broader
  capability than the product actually has. None of the three caused
  real harm (nothing was built to the wrong assumption in any case),
  but the pattern itself — an OPR describing more than exists — is now
  evidenced three times, not once, and is worth naming as its own
  lesson for future OPR drafting/review.

## K. Ordinary RFP/project translation

See each Requirement's own translation note above. Together they
confirm the same lighter-touch pattern COMM-I3 found: a short, specific
question asked once at pursuit/early-design time, not an exhaustive
retrospective investigation, is what this doctrine translates to for an
ordinary project.

## L. Deficiencies/residuals discovered

- **OPR-2.5: non-drawing Sources have no formal revision/supersession
  path.** Real, live, self-disclosed since MM2, unresolved. See the
  Product Owner decision package below. Not fixed this stage.
- **OPR-1.2: a real, historical access-authorization gap existed before
  P32** (data partitioning was never at risk; who could open a project
  at all, was). Already closed; recorded here as a developmental
  finding, not a present deficiency.
- No other deficiency was found among the eight Requirements.

## M. Product limitations

None newly discovered this stage beyond OPR-2.5's own finding (which is
a scope limitation of `register_source_revision`, already named,
covered under L). No attempt was made to represent any of these eight
as product-level adjudications, per this stage's own explicit
instruction and COMM-I3B's standing rule.

## N. Product Owner decision package

| Owner ID | Agent assessment | Developmental classification | Strongest evidence | Tier | Deficiency/residual | Claude recommendation | PO decision required |
|---|---|---|---|---|---|---|---|
| OPR-1.1 | Satisfied | Early-and-Sound Conception | `ingestion.py`: "always generates a brand-new project_id"; 5 live distinct UUID projects | DIRECT | None | No action needed | Confirm or override |
| OPR-1.2 | Satisfied (data isolation); real historical access-gap noted | Data: Early-and-Sound; Access: Timely Correction (P32) | Per-project file storage since earliest `get()`; P32's own "P27-flagged gap" text; live cross-project switch test | DIRECT (gap); INFERENCE (timeliness) | Requirement text names "vector embeddings," which don't exist (harmless) | No action needed; note the text/product mismatch | Confirm or override |
| OPR-1.3 | Satisfied | Early-and-Sound Conception | Live round-trip switch test, zero state loss | DIRECT | None | No action needed | Confirm or override |
| OPR-2.1 | Satisfied | Early-and-Sound Conception | MM1–MM9 `STATUS.md` record, prior live verification | DIRECT | None | No action needed | Confirm or override |
| OPR-2.2 | Satisfied | Early-and-Sound Conception | `Source.id`/`_new_id()`; docstring; no rename mutator exists | DIRECT | None | No action needed | Confirm or override |
| OPR-2.4 | Satisfied (MM1-onward) | Early-and-Sound (MM1+); pre-MM1 lineage unclear | MM1 evidence contract, citation resolver | DIRECT (MM1+); INSUFFICIENT (pre-MM1 "Refines OPR-4.2 Rev 0") | Pre-MM1 lineage undocumented (carried forward, not new) | No action needed | Confirm or override |
| **OPR-2.5** | **Partially Satisfied** | **Unresolved Developmental Deficiency** | `register_source_revision` hardcoded to `SOURCE_KIND_DRAWING`; MM2's own self-disclosed `STATUS.md` text | DIRECT | **Real: no supersession path for non-drawing Sources, including the adopted OPR itself** | Recommend a Product Owner decision: accept as a residual, or authorize a future tranche to extend `register_source_revision` to non-drawing kinds | **Decision needed: Accept Residual / Do Not Accept / Insufficient Evidence** |
| OPR-5.4 | Satisfied | Early-and-Sound Conception | `answer_project_question`'s narrow signature; no shared embedding index; P31 kill switch | DIRECT | None | No action needed | Confirm or override |

**No Product Owner decision was made by this stage.** OPR-2.5 is the
one item genuinely requiring a choice; the other seven are presented
for confirmation or override, not because a decision is structurally
required the way OPR-7.4's residual was.

## O. Tests / live verification

No application code was modified. Live-browser verification performed
this stage: real cross-project switch (commissioning project ↔ Nipigon
Ramp) confirming both isolation and state-preservation directly, not by
inference from prior stages' evidence alone. All other evidence was
gathered by direct repository inspection (grep/read against
`services/case_workspace.py`, `services/ingestion.py`,
`services/project_qa.py`, `services/learning_governance.py`,
`routes/portal.py`) and by citing this repository's own already-
committed `governance/STATUS.md` record where a claim was already
proven live in a prior stage (MM1–MM9, P32). No `RequirementAdjudication`
was created. The full regression suite was not re-run — no code
changed, and this stage's own instruction was explicit that ceremony-
only re-runs are not required; the last confirmed baseline (2969
passed, 0 failures) remains accurate.

## P. Commits / HEAD / origin/main / working tree

See the final chat report for exact values — recorded after this
document and the `STATUS.md` row are committed together.

## Recommendation

**FOUNDATIONAL INTEGRITY COMMISSIONING ASSESSED — PRODUCT OWNER REVIEW
REQUIRED.** Seven of eight Requirements are agent-assessed Satisfied
with no action needed beyond ordinary Product Owner confirmation.
OPR-2.5 is a genuine, evidence-grounded Partially Satisfied finding
requiring an actual Product Owner decision, structurally identical in
shape to OPR-7.4's own residual in COMM-I3/COMM-I3A/COMM-I3B. No new
`RequirementAdjudication` was persisted for any of the eight, per this
stage's own explicit instruction and COMM-I3B's standing human-authority
rule.
