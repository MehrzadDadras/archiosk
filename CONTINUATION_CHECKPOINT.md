# Continuation checkpoint

## 2026-07-31 — CLAUDE-P40: critical co-architect review — repaired visual line-wrap fragmentation

**Commit:** `5cd337c`. Full suite: 1151 passed (was 1130).

Explicit critical-review stage: required re-deriving the P40 bottleneck
from scratch (live re-audit + a 6-candidate comparison) rather than
reflexively continuing P39's own closing recommendation. Walked the
full golden path live against the real running dev server, screen by
screen, sign-in through History. Most of it held up well under direct
inspection (Briefing, grounded Q&A, the P39 Investigation-escalation
fix, the Apply/Issue Approval Gate confirm screens, RFI export,
History) - genuinely clear, professional copy, not the source of the
worst friction. The one sharp, immediately visible break: the
Requirements screen's "Extracted, not yet governed" list showed one
real sentence ("The Design-Builder shall provide all labor,
materials, and equipment required to complete the Riverside Community
Library renovation, including structural upgrades, mechanical
replacement, and accessibility improvements.") split into **three**
separate, independently confidence-scored "requirements," with a real
instance of the SAME sentence's fragments landing in two
**contradictory categories** (technical_specification vs.
compliance_legal). This is the first substantive data screen a
reviewer sees after the Project Briefing - confirmed as the strongest
candidate across customer harm, frequency (near-universal for real
PDF/wrapped-text RFPs), severity, and downstream contamination against
five other named candidates (Zero-Founder screen comprehension broadly,
rigid conversational routing, the three-vocabulary requirement-
adjudication flow, operational readiness, RFI mechanism ambiguity).

**Root cause:** `services/bhive_parser.py`'s `_segment` did a naive
per-physical-line split with no reflow - `pypdf.extract_text()` and a
plain-text upload both reproduce the source document's own visual line
wraps, which fall mid-sentence far more often than not.

**Fix**, scoped to exactly this: `_reflow_wrapped_lines` rejoins
consecutive lines into one logical clause when the accumulated text
doesn't already look sentence-complete and the next line reads as a
genuine continuation (starts lowercase) - never crossing a numbered/
lettered clause marker or a bullet marker, which always start a fresh
item. A line ending in a hyphen directly attached to a letter (no
preceding space - an unambiguous word-break signal, unlike guessing
from spelling) gets a dedicated no-space rejoin, which also correctly
reconstructs this corpus's own most common compound term when it wraps
the same way ("Design-" / "Builder" -> "Design-Builder", never
"DesignBuilder"). `RequirementItem` gained one additive `Optional`
`source_line_end` field for traceability - `_classify`/
`_classify_with_model`/`_classify_with_rules`/`_parse_model_output`
are completely untouched; the end-line map is applied to finished
`RequirementItem`s in `parse()`, after classification.

**Architecture freeze discipline, explicit:** rejected full fragment-
array/join-reason/uncertainty-score provenance tracking as more than
the "no traceability lost" hard-stop actually requires; rejected
touching `services/case_workspace.py`'s governed `Requirement` schema
(the defect lives entirely in the pre-promotion candidate list); no
new parser dependency added (the deterministic heuristic proved
sufficient against every required test shape). Only `services/
bhive_parser.py`'s own segmentation stage changed.

**Existing projects: never touched.** Reflow only runs during a NEW
document's segmentation inside `BHiveParser.parse()` - no migration,
no re-processing, no governed Requirement ID regenerated, no
Investigation/Finding/Disposition/RFI/History record altered.

**Verified live, before/after, against the real running dev server:**
the same real document that showed 36 fragmented "requirements" (with
the exact 3-way-split sentence above) now shows 18, with that sentence
appearing whole under a single confidence score.

See this stage's own final report (delivered in-conversation) for the
full 6-candidate comparison table, the transition map, and the ranked
remaining-blockers list.

---

## 2026-07-31 — CLAUDE-P39: commercial convergence — closed the Requirement-to-Investigation dead end

**Commit:** `14a107a`. Full suite: 1130 passed (was 1127).

First business-convergence stage (governing objective: one continuous,
trustworthy, Zero-Founder-usable golden path — Upload → Briefing →
Requirements → Question → Investigation → Decision → RFI → Export →
History — over further architecture/domain expansion). Audited the
full route/template surface for the mid-to-end half of that path
(Requirements onward — the Briefing half was already known from
P38-D2) via a forked mechanical route-mapping pass plus direct live
HTTP verification against the real running dev server.

**Two real candidates found; one selected.** (1) `services/
bhive_parser.py`'s `_segment` does a naive per-physical-line split with
no paragraph reflow — confirmed live on the real P38-D2 verification
project that every PDF/hard-wrapped-TXT sentence spanning more than one
visual line gets shredded into separate `RequirementItem`s, sometimes
with **different, contradictory categories for fragments of the same
sentence** (e.g. "...as indicated on the" / "structural drawings. Any
material deviation..." split across `technical_specification` and
`compliance_legal`). Real, high-value, but doesn't block the workflow
— extraction is degraded, not broken. (2) The "Discuss this
Requirement" aperture (`templates/_macros.html`'s `aperture` macro,
already correctly wired with anchor fields) and its backend
(`_handle_investigate_requirement` in `services/
conversation_interpreter.py`) both work correctly and — verified live
with a REAL Anthropic call — produce a genuinely well-reasoned,
evidence-grounded Finding. But the escalation offer that gets a
reviewer from "described a concern" to "start an Investigation" only
fired for six hardcoded phrases ("investigate this", "check this",
etc) — a live test confirmed a natural concern ("I'm not sure this
covers electrical systems as well") got a silent, unguided dead end
instead. Selected (2): it's a total, not merely degraded, block on the
Zero-Founder Test's explicit "convert a concern into an Investigation"
requirement, and improves four ranks (Trust Core's workflow-continuity
half, Functional Workflow Completeness, Market-Ready Product, UI
Information Architecture) against (1)'s two (Trust Core's accuracy
half, Extraction). (1) is deferred, not abandoned — see this stage's
own final report's ranked gap list.

**Fix, deliberately narrow** (matching this module's own
"deterministic keyword matching, not reasoning" discipline):
`_INVESTIGATION_PHRASES` gained natural concern-expressing phrasings
found live during this stage's testing ("not sure this covers",
"doesn't mention", "seems to conflict", "unclear whether", "concerned
about", ...) — additive only, every one of the three existing tests
covering the original narrow behavior still passes unchanged.
`_describe_anchor_acknowledgment` now names working phrasing
("Investigate this", "Something is wrong here") for the residual case
no phrase list will ever fully cover, so a miss is no longer silent.
No change to what's automatically analyzed or committed — opening an
Investigation still requires an explicit human click, and the real AI
call inside `_handle_investigate_requirement` still only fires after
that click on an explicit trigger-phrase match when a Case is already
open (that narrower, cost-conscious gate was deliberately left
untouched; only the costless "offer to escalate" branch was widened).

**Other findings, explicitly deferred** (ranked in this stage's own
final report): the extraction line-fragmentation defect above;
"BEEHIVE" (an internal/legacy name never introduced to users anywhere
else) leaking into the RFI-preview flash message; raw UUIDs
(`artifact.id`/`analysis_id`/`engine_name`) rendered inline, not
behind a disclosure, on Finding cards; the `findings-empty` state's
"analyze a drawing Source" copy being the wrong medium for a text-RFP
product; two unrelated mechanisms ("governed per-Finding RFI draft"
vs. the legacy project-wide consistency-flag export) both called "RFI
export" with no UI distinction.

See this stage's own final report (delivered in-conversation) for the
full transition map, Rank 1–5 evidence table, and three-stage
commercial convergence plan.

---

## 2026-07-31 — CLAUDE-P38-D2: restore AI-first automation and repair the opening briefing pipeline

**Commits:** `c8856c1` (provenance/lifecycle fields), `14e0d7e`
(analytical-vs-consequential policy distinction + automatic lifecycle
routing), `b160897` (template UX states), `73c0b03` (semantic repairs +
source grounding), `ebd451d` (realistic fixtures + tests). Full suite:
1127 passed (was 1104 before this stage's own new tests + P38-D2's
9-test lifecycle class + the em-dash/background-prose classifier
tests).

CLAUDE-P38-C/P38-D1 had left a manual-only Generate button and no way
to tell an approval-required policy state from an outright denial.
This stage restores the original governing intent ("automatic
analytical AI where policy permits; human authorization required only
for consequential actions") without adding a new governed action or
weakening the mandatory floor: `_project_briefing_ai_status()`
(`routes/workspace.py`) turns the existing `evaluate_action()` result
into three states the route now actually branches on
(allow/require_approval/denied) instead of collapsing everything
non-ALLOW into one generic path.

**Automatic lifecycle:** `/upload` now redirects through a real,
visible "Preparing your Project Briefing…" interstitial
(`preparing_project_briefing` route + template) that auto-submits the
real generation request — not a hidden background job.
`tools/dependency_fit.py --requires-background-worker` confirmed this
deployment has no queue/worker infra and no async runtime, which is
what ruled out every alternative except synchronous generation behind
a visible waiting page. A duplicate-call guard
(`generation_in_progress_for`, keyed off a timestamp that treats
anything older than 90s as abandoned) prevents a second real, billed
call while one is in flight.

**Bug found and fixed during this stage's own build:** the
interstitial's original "is there a Source to brief from" gate checked
`workspace.sources`, but the originally-ingested document never gets
its own `Source` record (only later manually-added material does) —
that gate would have skipped automatic generation on every real
upload. Now checks `document.requirements`/`milestones`/
`workspace.sources` together.

**Semantic repairs** (`services/project_briefing.py`):
`_looks_like_bare_heading` rewritten to a two-step prefix+verb check so
em-dash/en-dash/colon/semicolon/no-punctuation schedule headings are
excluded regardless of punctuation, not just a plain ASCII hyphen; a
new `_BACKGROUND_PROSE_PATTERNS` excludes descriptive present/perfect-
tense prose that shares topic vocabulary with a real requirement but
isn't one; `_TECHNICAL_INCLUSION_SIGNALS` tightened to require an
actual obligation-shaped phrase, not a bare topic noun.

**Trust record:** `ProjectBriefingResult.grounded_in` — a small set of
verbatim-quoted excerpts from the same extracted evidence, never
invented. `set_project_briefing` now preserves exactly one prior
version (`project_briefing_previous`) instead of overwriting it, shown
via a compact history disclosure. Provider/model/generated-by/source-
signature are now all displayed.

**UX states** (`templates/case_workspace.html`): distinct copy and a
`data-briefing-state` attribute for preparing / ready / stale-
regenerable / stale-approval-required / stale-denied / approval-
required / denied / failed-with-retry / no-source — never one generic
flash regardless of what's actually happening.

**Verification, reported by category (see this stage's own final
report for the full breakdown):** unit/integration (1127 passed, incl.
57 in `tests/test_project_briefing.py`); mocked-AI (the 9-test
`ProjectBriefingLifecycleTests` class, real Flask route/template stack
with only the Anthropic SDK call mocked); real-provider (multiple real,
non-mocked Anthropic calls against the actual running dev server —
automatic ALLOW-path generation, an explicit `confirm=once` approval-
gated generation, ~20s each — via a throwaway `*.invalid` admin account
created and suspended again in-process, never touching the real user's
credentials); live policy-state verification (DENY and
REQUIRE_APPROVAL both exercised against the real running server by
temporarily changing the deployment-wide `SecurityGovernanceStore`
baseline, then explicitly restored to `allow`/baseline afterward —
confirmed via the app's own resolver post-restore). No pixel-level
responsive/viewport verification was done (no screenshot tool in this
environment, same stated gap as CLAUDE-P38-C).

**Explicitly not built:** a debounce mechanism for "excessive repeated
calls during multi-file ingestion" — the app only ever ingests one file
per upload request (`request.files.get('file')`, singular) and a stale
briefing requires an explicit click to regenerate (never automatic), so
the scenario the debounce would guard against doesn't exist in this
codebase's current architecture. No P39 work began.

See this stage's own final report (delivered in-conversation) for the
full policy-state/failure-state matrices and exact browser-retest
steps.

---

## 2026-07-31 — CLAUDE-P38-C: Project Briefing semantic repair and controlled workspace simplification

**Commits:** `5817977` (semantic classification + compact previews),
`0786fb5` (page hierarchy, composer clarity, management-control
grouping). Full suite: 1104 passed (1086 + 18 new).

Browser retest of CLAUDE-P38-B found three real defects: (1) Technical/
Financial/Key Dates previews included unrelated clauses (privacy
prose, material-deviation language, proposal-preparation costs, bare
stage-title headings) because `RequirementItem.category` is a coarse
bucket never designed for this precision; (2) raw extraction lists
rendered directly on the landing page, burying the Generate button;
(3) two unlabeled composers and a fully-expanded Lifecycle/Layers block
competed with the opening briefing for viewport space.

**Fixed via a bounded exclusion/inclusion filter** layered on top of
the existing categories (`_qualifies_as_technical`/`_qualifies_as_
financial`/`_qualifies_as_key_date` in `services/project_briefing.py`)
— same discipline as CLAUDE-P38 OBS-09's cover-page-metadata filter,
not a classifier rewrite. Exclusion always wins; an uncertain item is
left out of the preview, never guessed in, but never deleted from the
full register. **Two additional false positives found live** (not in
the original prompt) during this stage's own verification against a
real running instance — a bare "Section 3 - Financial Submission"
heading satisfied its own inclusion signal, and a bare "following"
matched ordinary prose as if it were relative-milestone timing — both
fixed and regression-tested before sealing.

**Page hierarchy:** Generate/Regenerate now appears before any
deterministic list; each preview capped at 5 items with a real
qualifying count and an explicit "Open X" link; the two composers kept
as explicitly labeled, distinct controls (acceptable-fallback option —
unifying them would mean teaching `quick_start`'s unconditional
always-creates-a-Case behavior to route conditionally, a real
behavioral change to an existing tested route, not a labeling fix);
Lifecycle/Display Layers moved inside one collapsed "Project
Management & Settings" disclosure; two permanent prose paragraphs
moved behind a collapsed "What is Project State?" disclosure.

**Visual verification:** no browser/screenshot tool is available in
this environment. Verified instead via real HTTP requests against the
actual running dev server (same pattern as CLAUDE-P36) — uploaded a
purpose-built synthetic document exercising every prompt-given
inclusion/exclusion example, inspected the real rendered HTML structure
and content before/after each fix. This confirms content, order, and
absence/presence with certainty; it does **not** confirm pixel-level
responsive layout at wide/medium/narrow viewports — that gap is stated
plainly in this stage's own final report, not glossed over.

See this stage's own final report (delivered in-conversation) for the
full classification rule tables and browser retest checklist.

---

## 2026-07-31 — CLAUDE-P38-B: narrative-first project opening

**Commit:** `c5ecf52`. Full suite: 1086 passed (1070 + 16 new).

Adds a Project Briefing as the first substantial content on Project
Home, ahead of the quick-start composer and every downstream register,
per the explicit governing objective: verify sources → read Executive
Summary/Project Brief → understand objectives/scope/Technical &
Financial submission routes → follow reading guidance → ask grounded
questions → begin detailed review.

**Two deliberately separate layers.** (1) `services/project_briefing.
py`'s `deterministic_sections` — Technical Submission, Financial
Submission, Key Dates, Suggested Reading Path, all grouped from
already-extracted `RequirementItem.category` values and `document.
milestones` (CLAUDE-P38 OBS-11). No AI call, always available, never
says more than the extraction already says — an empty Financial
Submission section states plainly nothing was found, never fabricates
one. (2) `generate_project_briefing` — a real, grounded narrative
synthesis (Executive Summary, Objectives, Project Brief/"Basis of
Understanding" — explicitly labelled a machine-assisted draft, never
an approved Project Charter, Procurement Route, Matters Requiring
Early Attention), mirroring `project_qa.py`/`requirement_
investigation.py`'s established pattern exactly, gated through the
same `ACTION_EXTERNAL_AI_REQUEST` policy check (third real external-AI
site in this app). Never generated automatically on page load — only
on explicit action, cached on `ProjectWorkspace.project_briefing` with
a source-set signature (`source_signature_for`/`set_project_briefing`)
so a stale briefing is honestly flagged, not silently served.

**Explicitly not implemented, per this stage's own scope:** the
accordion-launched closable-working-tab architecture (remains a
separate future evaluation — no work began on it); a full three-tier
reorganization of every existing sidebar section into Primary/
Secondary/Management groups (the briefing is inserted first; P38's
already-tested section order elsewhere is unchanged, avoiding
unnecessary layout regression risk); estimating/ETCO/spreadsheet/
bidder-scoring functionality; date arithmetic (fixed/relative wording
shown verbatim, never calculated into an actual date).

See this stage's own final report (delivered in-conversation) for the
full capability assessment and browser retest steps.

---

## 2026-07-31 — CLAUDE-P38: browser-walkthrough defect closure and workspace usability repair

**Commits:** `413c545` (project Q&A), `f3f004d` (requirement over-
extraction + pipeline visibility), `585407d` (Key Dates + RFI
register), `d97b65a` (participant/instructions/Go-No-Go/lifecycle
authority), `02e5e8c` (Accepted Knowledge/Sources/History UX + two
regression-test fixes). Full suite: 1070 passed, 0 failed.

Fourteen browser-observed defects (OBS-01 through OBS-14) from the
product owner's own hands-on walkthrough of the Case Workspace, closed
in priority order. **No P37-A scope (pharmaceutical/ETCO/bidder-
scoring/spreadsheet-ingestion domain) was implemented** — that prompt
referenced files and terminology that don't exist in this repository
and was explicitly disregarded per the product owner's own
instruction; P38 stayed bounded to the real, existing construction
Design-Build RFQ/RFP workflow throughout.

**Priority 1 — core usability:**
- **OBS-01:** "Talk to this Project…" rejected ordinary questions
  ("What are the objectives of this RFP?") because `discuss_object`
  always posts with no anchor, so the message could never reach the
  Requirement-investigation path. New `services/project_qa.py` (mirrors
  `requirement_investigation.py`'s Anthropic pattern exactly) answers
  ordinary project questions grounded only in already-extracted
  evidence — never the model's world knowledge — with the same
  honest-degrade discipline, gated through the identical
  `ACTION_EXTERNAL_AI_REQUEST` policy check CLAUDE-P36 established.
  Bounded to messages that look like questions, so a stray message
  never triggers a real model call.
- **OBS-09:** cover-page/header metadata (RFP number, version, issue
  date, issuing organization, document status) was classified as a
  requirement candidate exactly like real text — neither classifier's
  schema has a "not a requirement" option. Fixed with a narrow
  pre-filter (`_is_document_metadata_line`) on the label:value shape
  cover pages use, applied before classification, not a change to
  either classifier's prompt.
- **OBS-07/OBS-10:** Requirement Compliance showed only "No
  Requirements... yet" with no indication candidates existed elsewhere
  (Sources reported 1,404, this section showed nothing). Now surfaces
  the already-computed candidate count with a direct link.
- **OBS-11:** Key Dates only showed manually-created dates, ignoring
  `document.milestones` (already extracted by `BHiveParser.
  _derive_milestones`, never surfaced anywhere). Now shown as a
  clearly separate, unconfirmed "From the source document" list.
- **OBS-08:** "RFI Export" implied RFIs only originate from flagged
  contradictions and that export was the whole feature. Renamed "RFIs"
  and rebuilt as a genuine project-wide register
  (`rfi_drafts_view`, filtered to `visible_cases` — same Case-privacy
  discipline the Findings section already applies).

**Priority 2 — governance and authority:**
- **OBS-04:** `record_go_no_go` was `@login_required` only — any
  authenticated participant, including `read_only`, could record the
  real decision. Now admin-only, enforced server-side in the route
  body. `GoNoGoAssessment` gained optional `decided_by_role`.
- **OBS-05:** same gap for Project Instructions — added
  `operating_instructions_updated_by_role`; the permanent governance
  explanation is now behind a collapsed disclosure.
- **OBS-03:** "Register a Participant" read like creating a login for
  someone else. Traced the actual mechanism and confirmed no
  impersonation exists — every governed write already records the real
  authenticated actor (added a test asserting this explicitly).
  Renamed to "Add a Project Party" with copy stating plainly it's a
  directory entry, not a login.
- **OBS-14:** the Lifecycle strip was fully static — "current" was
  hardcoded to RFP regardless of any real project state (no
  lifecycle-phase field exists anywhere in the domain model). Removed
  the false claim and "Historic Record" from the phase list rather
  than inventing a governed phase-transition mechanism with no
  evidence to design correctly; labeled "reference only — not tracked
  by this project."

**Priority 3 — workspace clarity:**
- **OBS-02:** Accepted Knowledge's permanent explanation paragraph is
  now behind a disclosure; the empty state shows real Finding counts
  (awaiting/applied) instead.
- **OBS-06:** source cards now show upload date. The exact quoted
  defect ("...already extracted by the Extract/Segment/Classify/
  Assemble pipeline") wasn't found verbatim anywhere in the current
  templates — likely already addressed by OBS-07/09/10's fixes, or was
  a summarized impression; not fixed as a literal string that doesn't
  exist.
- **OBS-12:** History defaulted to an always-expanded full list. Now a
  compact summary by default; "Show full history" persists via
  localStorage, same pattern as the existing Layers risk toggle. The
  complete audit record is unaffected either way.
- **OBS-13:** Layers renamed "Display Layers"; the checkbox label
  reframed as "viewing as X" rather than looking like the control
  belongs to that person.

**Deferred, explicitly not attempted this stage** (each judged to
require inventing real new architecture the walkthrough evidence
doesn't yet justify — recorded here so they aren't silently lost):
a full separate Go/No-Go "Recommendation" object distinct from the
decision itself (OBS-04's fuller vision); typed Project Instruction
categories/scope/expiry/history (OBS-05's fuller vision); RFI lifecycle
states beyond the existing draft/issued/answered (Candidate/Ready-for-
Review/Approved-for-Issue/Withdrawn, OBS-08's fuller vision); a real
governed project lifecycle-phase field and transition mechanism
(OBS-14's fuller vision); History's per-category filters (Human/
System/Access/Instructions/etc., OBS-12's fuller vision); fixed vs.
relative vs. conditional date-type classification for extracted
milestones (OBS-11's fuller vision, since no date-parsing exists at
all yet). None of these block the core workflow; all are legitimate
future work, not silently abandoned.

See this stage's own final report (delivered in-conversation) for the
full per-observation findings, browser re-test checklist, and seal
statement.

---

## 2026-07-30 — CLAUDE-P37: first marketable product slice and browser-walkthrough package

**Commit:** `c2f85dc` (hardened the two real market-critical choke
points). Full suite: 1030 passed (1028 + 2 new).

**Product slice defined** (full detail in this stage's own final
report, delivered in-conversation): first user = Design-Build proposal/
preconstruction reviewer; job = review an RFP/RFQ, adjudicate governed
Requirements, investigate ambiguity with governed AI assistance, and
issue traceable RFIs back to the client. Refines the originally-proposed
market proposition by making explicit that "AI-assisted investigation"
means the real, Anthropic-backed Requirement-investigation path only --
never the drawing-analysis path, which remains an explicit mock/
prototype and must not be presented as production capability in the
first release.

**Legacy-compatibility inspection (Part 6) found the real, previously-
unaddressed risk.** The unsafe `ProjectWorkspace(**data)` construction
is centralized in exactly one place (`CaseWorkspaceStore.get()`), but
defenses against it were duplicated ad hoc and incompletely applied.
CLAUDE-P36 had fixed two peripheral pages; this stage found the two
routines that actually matter most -- `routes/workspace.py`'s
`_load_workspace_or_404` (47+ routes: Case Workspace, Findings, RFI --
the entire market-critical surface) and `services/project_access.py`'s
`load_authorized_project_or_none` (every `routes/api.py` JSON route) --
were still unguarded, meaning the real, already-known corrupted legacy
project would 500 instead of 404 for anyone (authorized or not) who
reached its URL directly. Fixed both (same three-line pattern, sixth
occurrence of this defect class), with two new regression tests.

**Browser walkthrough package prepared, not yet performed.** A new
synthetic test document (`p37_walkthrough_document.txt`, session
scratchpad -- 5 clauses covering one clear investigable requirement,
one deliberately ambiguous one, a schedule pair a reviewer should
notice looks inconsistent, and a missing-referenced-document RFI-worthy
gap) and a single continuous numbered procedure were handed to the
product owner in this stage's final report. This is the first genuine
ask for the product owner's OWN hands-on browser session -- distinct
from, and not satisfied by, CLAUDE-P36's live-but-HTTP-driven
verification.

See this stage's own final report for the full product-slice boundary
(included/optional/excluded), claims register, and legacy-compatibility
Go-Now verdict.

---

## 2026-07-30 — CLAUDE-P36 Case 1/Case 2 walkthrough: performed live, by Claude, against the running app

**Commit:** `6dd1695`. Full suite: 1028 passed (1026 + 2 new).

**What actually happened.** The product owner asked Claude to perform
the Case 1 (denied) / Case 2 (permitted) walkthrough directly, rather
than waiting for a human browser session. No browser-automation tool is
available in this environment, so it was performed the closest honest
substitute: real HTTP requests (Python stdlib `urllib` + a real session
cookie, CSRF token extracted from each page like a browser's JS would)
against the actual running dev server (`restart-app`-cleaned, one
process), using a synthetic test document and a dedicated, suspended-
after-use test account (`p36_walkthrough`) — never the pytest test
client, never a mocked Anthropic call. **This is real live-app
verification, not a substitute for the product owner's own hands-on
browser session** — that distinction stays open regardless.

**Both cases passed.** Case 1 (project security profile set to
`restricted`): Discuss-this-Requirement → Start-an-Investigation
correctly refused with *"not permitted by this project's security
policy (controlling layer: profile)"*, zero Findings created, zero
provider calls. Case 2 (profile reset to `standard`): the same flow
made one real, ~14s Anthropic API call and produced a genuine,
appropriately-hedged provisional Finding (confidence 30%, correctly
flagged insufficient evidence rather than guessing) — carried through
ReviewerValidation → Confirmed Disposition → Apply → RFI draft → issue
→ `.docx` export, all verified with real content. Logged out and back
in: Applied badge, Finding, and issued RFI status all persisted.

**Two real defects found live, not by any prior test:** `GET /security/`
(the Security Department page, needed to set a project's profile for
Case 1) 500'd the instant a real project existed alongside the already-
known corrupted legacy workspace file — a third and fourth occurrence
of the CLAUDE-P32-documented `reviews`-key incompatibility, in
`routes/security.py::department_home` and `services/security_
assurance.py::run_security_self_check`, neither previously covered by
any test (this route had zero HTTP-level test coverage before this).
Both fixed (fail-closed to exclude for the former, matching existing
precedent; reported as an anomaly finding for the latter, since that
function's whole purpose is surfacing anomalies) — this is exactly the
kind of gap a real walkthrough is supposed to catch that a mocked test
suite cannot, even a thorough one.

**Cleanup performed:** the synthetic test project was deleted via the
real `/projects/<id>/delete` route; the `p36_walkthrough` test account
was suspended (not deleted) via `tools/create_credentials.py --suspend`.

**Standing caveats, unchanged:** this was a synthetic document, not a
real confidential one — success here does not prove confidential-client
deployment readiness (per the product owner's own explicit instruction).
The pre-ingestion external-AI selection/disclosure requirement remains
a deferred release-stage item, not implemented, per instruction.

---

## 2026-07-30 — CLAUDE-P36: external-AI governance, confidentiality, and provider-portability gate

**Commits:** `2fd949e` (enforcement + provider-portability fields),
`74a1735` (18-item focused test suite). Full suite: 1026 passed, 0
failed (1017 from CLAUDE-P35 + 9 new in
`tests/test_external_ai_governance.py`).

**What this closes.** P35 surfaced that `services/security_policy.py`'s
`ACTION_EXTERNAL_AI_REQUEST` governed action existed but was never
evaluated before the real requirement-investigation Anthropic call
(`_handle_investigate_requirement` -> `requirement_investigation.
investigate_requirement`) — a DENY baseline already blocked the export
route and the ingestion-time classify/consistency calls, but this one
real-time call site was unguarded. `_handle_investigate_requirement`
now resolves that action through the SAME resolver (`evaluate_action`)
already used by `routes/workspace.py`'s `_evaluate_security_action`
(export gate) and `services/ingestion.py`'s ingestion-time gate —
mandatory floor -> active organization baseline -> this project's own
`security_profile` classification -> any active exception — before any
evidence is gathered or a prompt is built. A denial stops the call
entirely, records an honest `InvestigationStep` (`ran=False`, a
policy-specific `skipped_reason`), and replies naming the controlling
policy layer, distinct from the pre-existing "no API key" / "provider
failed" messages.

**Provider portability (Limited Concession).** `RequirementInvestigationResult`
now carries `provider`/`model`/`requested_at` (set only when `ran=True`);
the caller persists `engine_name`/`engine_version` from what the
provider boundary actually used, instead of independently re-reading
`ANTHROPIC_MODEL` from the environment. No second provider was
implemented — this only removes one small, real Anthropic-specific
assumption from the caller, per P36's own explicit scope restraint.

**Call-site inventory (complete, 3 total):** `bhive_parser.py`'s
`_classify_with_model` and `_check_consistency` were already gated —
both keyed off `parser.ai_calls_disabled`, itself set by
`ingestion.py`'s own pre-existing `evaluate_action` call at ingestion
time (org-wide baseline/exception only; no project exists yet at that
point, an honest, already-documented limitation). `requirement_
investigation.py`'s `investigate_requirement` was the sole real
bypass, now closed. `services/drawing_analysis.py` makes no external
call at all (confirmed mock engine, CLAUDE-P35's own finding) — nothing
to gate there.

**Data minimization (reviewed, no code change).** The investigation
prompt sends: this Requirement's own text/classification/status, its
full adjudication history (including adjudicator usernames), linked
Findings/Relationships/AcceptedKnowledge, supersession/relationship
neighbors, and (opt-in only) the reviewer's represented-party name. It
does NOT send the source document's full text, unrelated Requirements,
project/client metadata, or pricing/contact information. One item
flagged for a future stage, not acted on here: adjudicator usernames
appear verbatim in the prompt — acceptable today (this deployment's
usernames aren't confirmed to be real-name-bearing), but worth revisiting
if a future deployment's usernames do carry real identity.

**Confidential real-document walkthrough gate:** now clear to proceed,
subject to the product owner performing the two-case (denied/permitted)
walkthrough in this stage's own final report before any actual
confidential document is used.

See this stage's own final report (delivered in-conversation) for the
full call-site inventory (Part A), root-cause explanation (Part B), and
the updated two-case walkthrough (Part I).

---

## 2026-07-30 — CLAUDE-P35: complete the first marketable investigation loop

**Commit:** `cf3865c` (golden-path test correction). Full suite: 1017
passed, 0 failed (unchanged count — this stage corrected an existing
test's mechanism, added no new test method).

**Governing context:** accepts CLAUDE-P34 as a successful automated
validation stage, with one central qualification the product owner
raised — the human walkthrough it prepared validated ingestion,
promotion, adjudication, Go/No-Go, access, and persistence, but never
the investigative path from a document to a Finding, Disposition, RFI,
and export. P35's mandate was to close that gap in the actual
application before asking the product owner to attempt the real-
document walkthrough.

**The central finding: P34's own "no UI path exists" claim was based
on incomplete investigation, not a real product gap.** P34 checked
only `_handle_analyze` (the "Analyze this..." trigger, genuinely
drawing-only) and concluded no text-to-Finding path existed at all.
Full investigation of `conversation_interpreter.py`'s dispatch tree
found a second, separate, real, Anthropic-API-backed path was already
fully wired: **"Discuss this Requirement"** (an aperture rendered next
to every governed Requirement, `templates/_macros.html`) posts a
project-level message; an investigation-shaped question is honestly
declined with a `needs_case` offer (no Case open yet, and a Finding
needs one to live in); accepting that offer via the **"Start an
Investigation from this"** button opens a real Case and re-runs the
same question, this time reaching `_handle_investigate_requirement` →
`services/requirement_investigation.py`'s real `investigate_requirement`
→ a genuine provisional Finding via the same `record_analysis` every
other Finding path uses. Verified end-to-end through real HTTP routes
(not just service-layer calls) before any file was changed.

Separately, `services/drawing_analysis.py`'s `analyze_drawing` (the
engine behind `_handle_analyze`) was confirmed to be an explicit
mock/prototype (`ENGINE_NAME = "beehive-mock-vision"`, a hardcoded
4-item finding library) — not real AI. So the ONE real reasoning path
in this product today is the text/Requirement one, not the drawing
one — the opposite of what P34's framing implied.

**Part 4 (bounded correction) resolved to no source change.** Since
the real mechanism already existed, worked, and was already reachable
through ordinary UI navigation, the smallest safe correction was to
`tests/test_market_critical_golden_path.py` itself: its docstring's
false claim was removed, and its Finding-creation step was rewritten
from a direct `store.record_analysis` stand-in to the real two-step
HTTP flow (`discuss_object` → `start_investigation_from_aperture`),
mocking only the one Anthropic API boundary
(`services.conversation_interpreter.investigate_requirement`), so the
composed test now proves the SAME route a real reviewer uses, not a
substitute for it.

**One real gap surfaced, not acted on (belongs to a later stage):**
`services/security_policy.py` already models `ACTION_EXTERNAL_AI_REQUEST`
as a governable action, but neither `discuss_object` nor
`start_investigation_from_aperture` calls `evaluate_action` before the
real Anthropic call runs — a DENY baseline on that action would not
currently block it. Flagged as evidence for CLAUDE-P40 (Security and
Confidentiality Release Gate); out of P35's bounded scope to fix.

**Scanned/image-only PDF:** confirmed no OCR anywhere in this codebase
— `pypdf`'s `extract_text()` returns `""` per image-only page, so
ingestion succeeds but yields zero/near-zero `RequirementItem`s,
silently starving the rest of the chain of anything to promote. Not a
crash; a real capability gap worth surfacing to the product owner
before they attempt a real-document walkthrough with a scanned file.

**Layer B still not performed.** The corrected, single-numbered-
sequence walkthrough (now describing the real Discuss→Start-
Investigation flow) was handed to the product owner in this stage's
final report. Completion requires the product owner's own attempt —
not claimed here.

See this stage's own final report (delivered in-conversation) for the
full source-type map, product decision, forensic/poetic integrity
checkpoint, and market-readiness assessment.

---

## 2026-07-30 — CLAUDE-P34: market-critical golden-path MVP validation

**Commit:** `d533fbc` (composed golden-path test, Layer A). Full suite:
1017 passed, 0 failed (1014 from CLAUDE-P32 + 3 new). Layer B (human
walkthrough) prepared and handed off, not yet performed by the product
owner — see the walkthrough package in this stage's own final report.

**Governing context:** CLAUDE-P33-GATE (architecture reassessment) and
CLAUDE-P33-CORRECTION (market-critical-path rule, medical/second-domain
direction ruled No-Go/Defer) both preceded this stage. P34 is validation
work under that correction — no new capability was authorized, so no
`governance/STATUS.md` row was added this stage.

**What was proven.** One continuous project, walked through real routes
end to end: ingest → operating-environment lock → project ownership/
access (grant, revoke, unauthorized denial) → Go/No-Go → Case creation
→ requirement promotion → adjudication → Finding/ReviewerValidation/
Disposition/Apply → RFI directionality (draft/issue) → per-Finding and
project-wide RFI export → close-and-reopen persistence (a fresh
`CaseWorkspaceStore` instance, not the same in-memory object) →
unauthorized-user isolation still holding afterward. A second test
proves the CLAUDE-P31 security-export gate and the CLAUDE-P32
project-access gate compose independently (a DENY baseline blocks even
the project's own owner). A third is regression coverage for the real
`instance/registry/` `'reviews'`-key incompatibility.

**The single most important product finding.** `services/
conversation_interpreter.py`'s `_handle_analyze` — the only user-facing
"Analyze this..." trigger — accepts only a drawing/image Source. There
is currently **no UI path from a text-ingested RFP/RFQ (this product's
primary document type, per every existing test fixture) to a Finding.**
`CaseWorkspaceStore.record_analysis` is itself source-kind-agnostic, so
the Finding/Disposition/Apply/RFI-directionality chain is proven to
compose correctly — but only reachable for a text document via a direct
service-layer call standing in for a UI trigger that does not exist.
Classified MVP-significant in this stage's own final report; not fixed
this stage (would expand scope beyond validation).

**Pre-existing `reviews`-key incompatibility (`instance/registry/
eece5c88-7288-4373-843a-0fde061c8fe0`):** identified, dated
(2026-07-24, `workspacetester`, `sample_rfp.txt`, no `version` field —
predates that field's introduction), confirmed disposable dev/test
scratch data referenced by no automated test. Chosen treatment:
**excluded from the golden-path specimen, left untouched on disk**
(already covered by CLAUDE-P32's fail-closed handling, now with its
own regression test). No migration, no deletion, no modification.

**Layer B not yet performed.** The walkthrough package (startup
commands, URL, test account, approved document, numbered steps,
expected results, failure/recovery guidance, evidence to return) was
produced and handed to the product owner in this stage's final report.
Completion requires the product owner's own usability judgment — not
claimed here.

See this stage's own final report (delivered in-conversation) for the
full market-critical product map, defect classification, three separate
compartmentalization verdicts (semantic/development/operational — all
No-Go/Defer or Limited-Concession, none Go-Now, for lack of a
demonstrated current bottleneck), and market-readiness assessment.

---

## 2026-07-30 — CLAUDE-P32: project-level access control and isolation gate

**Commits:** `61b0bf5` (domain/service-layer access-control model),
`7262c67` (route/UI wiring and bypass closures), `fdd708a` (existing
test-fixture updates), `831fe4b` (41 new tests), `e83ac25` (governance
amendment + CLAUDE.md hermetic-test note + MANIFEST). Full suite: 1014
passed, 0 failed (973 from CLAUDE-P31 + 41 new in
`tests/test_project_access_control.py`).

**Preceded by a repository reassessment (accepted as the working
scope), then a hard-stop.** Investigation confirmed CLAUDE-P27's own
flagged gap -- any authenticated user could open any project by
guessing its `project_id` -- was still open after P29/P30/P31 each
built locked-environment/capability/security-governance machinery on
top of it. Before writing code, `tests/test_case_privacy.py`'s
`CasePrivacyRouteTests` and `tests/test_route_authorization_hardening.py`
were found to be built on two genuinely different authenticated
sessions both reaching the *same* project (Case-level privacy, not
project-level access, is what each actually verifies) -- a deny-by-
default owner/allow-list model would flip dozens of their assertions.
Presented as a real product decision rather than resolved unilaterally;
the user chose deny-by-default with the two ratified suites' fixtures
(not assertions) updated to grant both sessions access first.

**What was built.** `services/project_access.py`'s `can_access_project`
is the single centralized decision (admin always passes; otherwise
`owner == username` or `username in access_allow_list`; `owner is None`
fails **closed**, admin-only -- the deliberate opposite of every other
None-means-ungated field in this codebase, since no project-level
check existed before this tranche to preserve compatibility with).
Enforced at `routes/workspace.py`'s `_load_workspace_or_404` (AST-
verified 47 of 50 routes already funneled through it; `export_rfi`,
the one exception, was refactored to use it too), `routes/api.py`'s
new `_load_authorized_project_or_404` (6 routes) plus a filtered
`GET /documents`, and `routes/portal.py`'s `_accessible_documents`/
`_require_project_access_or_404` (`/`, `/projects`, `/search`,
`/dashboard/<id>`, `/projects/<id>/delete`).

**A genuinely new bypass found mid-implementation, not on the original
list.** `app.py`'s `_nav_recent_projects` -- the side-rail's project
list, rendered on **every** authenticated page including error pages
via the global `inject_globals` context processor -- listed every
project's display name completely unfiltered. Confirmed live: a denied
project's own name was still visible in the nav rail on the very 404
page proving access to it was denied. Fixed, and filtered before its
display cap so the sidebar isn't under-filled by capping first.

**Owner/allow-list, explicitly not tenancy.** `ProjectWorkspace.owner`/
`access_allow_list` (new fields). `owner` is deliberately re-settable
(admin-only, unlike `operating_environment`'s hard lock -- a wrong
backfill must be recoverable). `grant_project_access`/
`revoke_project_access` reuse `archive_case`/`derive_case`'s own
owner-or-admin authority pattern exactly. `services/ingestion.py`'s
`ingest_upload` gained a required `owner` parameter, deliberately
separate from the pre-existing free-text `actor` field -- confirmed by
real repository evidence (`actor` values like `"Mehrzad Dadras, Design
Manager"`, never validated against any account) that reusing `actor`
would have been a real spoofing vector. `owner` is sourced from
`session['username']` at both real call sites, never user-suppliable
form data -- verified through the real `/upload` route with a
deliberately mismatched `actor` field to prove the two stay separate.

**Legacy-project backfill, deterministic only.** A pre-P32 project's
own first `document_ingested` event's `actor` is checked for an EXACT
match against a real `models.User.username`. Checked against this
repository's own real local `instance/registry/` data: 3 of 6 existing
projects were ingested by the real `workspacetester` account
(backfillable); the other 3 have free-text actors (`"agent1"`,
`"agent2"`, a human display name) with no matching account and stay
unowned/admin-only rather than guessed.

**A real, pre-existing, unrelated defect surfaced, not introduced, by
this stage's own verification.** At least one project in this
repository's actual local `instance/registry/` has an on-disk workspace
JSON with a `'reviews'` key `ProjectWorkspace(**data)` no longer
accepts -- invisible before this stage because nothing previously
iterated every project's workspace on every page load. `app.py` and
`routes/portal.py`'s new listing-filter code now fail closed (exclude,
don't crash) on this, restoring `_nav_recent_projects`'s own pre-
existing defensive-degradation guarantee, which a first pass at the
filtering fix had briefly dropped before the full suite caught it.

**Manual two-user, two-project isolation check: passed.** Reproduced
live (not only via the automated suite): two real sessions, two real
projects, direct HTTP requests -- owner opens their own project (200),
a second unauthorized user is denied (404) on the workspace page, the
API, and export; the same denial applies to a directly guessed real
`project_id`; grant/revoke toggles access live; admin opens both
regardless of ownership.

**Deliberately not built this stage:** separate read/write project-
level permissions (the existing `admin`/`read_only` role axis is
unchanged and still governs in-project actions -- exceeding this would
have gone beyond the bounded objective); any `services/case_workspace.py`
decomposition (P32's own additions were kept as small, clearly-tagged
insertions specifically so a future decomposition isn't made harder);
an ownership-transfer UI beyond the existing admin reassignment route;
anything resembling `Organization`/`OrganizationMembership` (still
unimplemented, still a distinct future stage).

**Security claims boundary.** Now supportable: "authenticated project
access is restricted to explicitly authorized users within this
deployment." Still not claimed: multi-organization tenant isolation,
complete organization isolation -- unchanged from CLAUDE-P31's
`SECURITY_CLAIMS_REGISTRY`, this stage added no new claim rows, only
made the existing "project authorization vs. tenancy" distinction
concretely true in code rather than aspirational.

---

## 2026-07-30 — CLAUDE-P31: organizational security and information governance (bounded foundation)

**Commits:** `7aa1bea` (domain/service-layer security governance foundation),
`16056dd` (external-AI + export enforcement wiring), `8114c2e` (Security
Department routes/UI), `edacee0` (80 new tests), `d577f29` (governance
amendment + MANIFEST). Full suite: 973 passed, 0 failed (893 from
CLAUDE-P30 + 80 new across five new test files).

**What was built.** A real, bounded, tested foundation for the eighteen
completion-condition questions this stage posed — not enterprise theatre.
`services/security_policy.py`'s `evaluate_action` is the single centralized
resolver: mandatory floor → organization baseline → project security
profile → exception, most-restrictive-wins, an exception's loosening
structurally capped at `DECISION_ALLOW`. The floor is unweakenable
because there is no governed action anywhere in `GOVERNED_ACTIONS` for
disabling authentication/CSRF/rate-limiting/audit — not a runtime check
that could be bypassed. `INFORMATION_CLASSIFICATIONS` (standard/
confidential/restricted/highly_restricted) each resolve to an explicit
control bundle (`CLASSIFICATION_PROFILE_DECISIONS`), never a bare label.

**Honesty boundary, load-bearing for the whole stage:** this repository
has no multi-organization/tenancy model (`specified-unbuilt/tenancy-
and-project-authorization.md` remains unimplemented). `services/
security_governance.py`'s `SecurityGovernanceStore` therefore manages
**one global, deployment-wide record** — every "organization baseline"
in this codebase today means one shared configuration, never an
isolated per-customer one. Stated directly in the module's own
docstring, and in `SECURITY_CLAIMS_REGISTRY` (`"multi-organization
tenant isolation"` = `specified_but_unbuilt`, `"complete organization
isolation"` = `prohibited_from_claiming`), not left implicit anywhere.

**Policy ingestion and provenance.** `SourcePolicy` → `PolicyStatement`
→ `ProposedControl` → governed `QAEntry` (6-state authority model) →
`BaselineVersion` (draft → under_review → approved → active →
superseded/withdrawn, `acknowledge_capability_impact` required before
`activate_baseline` will accept it) preserves "Original Written Policy
≠ Machine Interpretation ≠ Proposed Application Controls ≠ Ratified
Executable Security Baseline" end to end — every control decision
carries required source provenance, never disguising an ARCHIOSK
recommendation as a customer policy requirement. Deliberately **no
AI-assisted extraction** this stage — statements/proposals are
human-entered only, extending this codebase's standing caution about
`services/bhive_parser.py`'s fragile prompts to "write no new prompt at
all" for this pipeline rather than a narrower gate.

**Real enforcement, at two representative points.** `services/
ingestion.py` evaluates `external_ai_request` before every new
project's classification and wires the decision straight into
`BHiveParser`'s own pre-existing, already-tested `ai_calls_disabled`
kill switch (CLAUDE-P27-B) — zero lines changed inside
`bhive_parser.py` itself. `routes/workspace.py` gates `export` on both
RFI export routes, consulting the project's own `security_profile`
alongside the active baseline, naming the controlling policy layer in
its denial message. A `security_decision` audit event is recorded for
every ingestion-time evaluation regardless of outcome.

**Learning boundaries, honestly scoped.** `services/
learning_governance.py`'s `LearningContributionRequest` models the
three zones and a required five-stage review sequence before approval
(self-approval prohibited for shared-improvement targets) — but **moves
zero data**, because no shared-learning/training pipeline exists
anywhere in this repository to move data into. Confirmed both
structurally (no import edge to/from `case_workspace.py`'s quality
machinery) and behaviorally (a "Correct" `ReviewerValidation` creates no
contribution request).

**Assurance, activity-level only.** `services/security_assurance.py`'s
`aggregate_security_activity` is a pure read-side aggregation over every
project's existing `GovernanceLog` — no new audit substrate. Content-
level inspection remains impossible through this mechanism structurally
(no field on `SecurityActivityEntry` could hold project content), not
merely policy-forbidden. `run_security_self_check` independently
re-verifies five invariants rather than trusting their own writers.
Honesty maintained explicitly: `GovernanceLog`'s append-only guarantee
is by convention, not cryptographic — `"tamper-proof logs"` is
`prohibited_from_claiming`, stated plainly rather than omitted.

**Workspace.** `routes/security.py` + `templates/security_department.html`
— admin-only (no dedicated Security Officer role exists yet), reachable
via a new nav link in `templates/base.html`.

**Verification.** 80 new tests. One real incident during this stage: an
early draft of `tests/test_security_enforcement.py` called
`ingest_upload` directly (not through a parse-spy) in several tests, and
one full-suite run took **8.5 hours** because that path made a live,
apparently-hung Anthropic API call in this sandbox. Fixed by routing
every ingestion call in every new P31 test file through a `BHiveParser.
parse` spy that never invokes the real classify/consistency-check
pipeline — confirmed fully hermetic afterward (full suite back to ~193s).
This was a test-authoring mistake in this stage's own new files, not a
defect in `services/ingestion.py`'s actual (correct) security-gate logic,
which the spy-based tests verify directly.

**Independent critique (required section), key findings:** "Security
Department" was kept as the product term (matches the user's own
prompt framing; no better repository-grounded alternative surfaced).
Security and information governance were kept as one workspace, not
split — the volume of real content (policy/Q&A/baseline/assurance)
didn't yet justify two surfaces. The repository genuinely cannot support
*organization-level* policy before tenancy — hence the single-
deployment scoping stated everywhere above. Audit visibility was kept
strictly activity-level specifically to avoid the employee-surveillance
risk the prompt itself named — security administrators do **not** see
content by default, and no route exists to change that this stage.
Strongest-rule-wins was kept as the precedence model; a security
administrator CAN create exceptions (the only loosening path, capped at
`DECISION_ALLOW`); policy changes take effect only at explicit baseline
activation (an `effective_date`), never immediately on Q&A/statement
entry alone.

**Remaining hard-stop-adjacent items, none blocking, all explicitly
out of scope for this stage per its own instructions:** no tenancy
migration was performed or attempted; no legal/regulatory obligation
was invented (the model has a place — `SourcePolicy.jurisdiction`/
`approving_authority` — for an externally-established one to be
recorded, nothing more); no technical security property was promised
that the current system cannot enforce (`SECURITY_CLAIMS_REGISTRY` is
the explicit record of this); no irreversible security-policy
transformation occurred without rollback (baseline supersession
preserves every prior version, never deletes).

---

## 2026-07-30 — CLAUDE-P30: environment capability architecture + contractual tool directionality

**Commits:** `e5a494f` (domain/service layer -- capability grammar, RFI
directionality, Go/No-Go), `e9a1e12` (route/template/UI wiring), `d1490dd`
(39 new tests), `28b2f75` (governance + MANIFEST update). Full suite: 893
passed, 0 failed (854 from CLAUDE-P29 + 39 new in
`tests/test_capability_architecture.py`).

**What was built.** The locked Project Operating Environment (CLAUDE-P29)
went from "one gated field" (participant-role selection) to an actual
capability architecture with two representative, genuinely-enforced
environment-specific workflows.

**Centralized resolution, not scattered branches.** `services/
environment_capabilities.py` gained `CAPABILITY_REGISTRY` (a plain dict of
small `CapabilityDefinition` entries — deliberately not a plugin framework)
classified into a 7-value grammar (`CAPABILITY_NEUTRAL`/`_COUNTERPART`/
`_PARALLEL`/`_CLIENT_ONLY`/`_PROPONENT_ONLY`/`_COMPARATIVE_BOUNDED`/
`_FUTURE_NOT_AUTHORIZED`). `capability_availability`/`capability_denial_
reason` are the single functions every route/template/export calls into —
`routes/workspace.py`'s new `_require_capability` helper (mirrors the
existing `_require_visible_case` shape) is the one enforcement point for
routes. A legacy/unclassified project (`operating_environment is None`) is
ungated for every capability except `CAPABILITY_FUTURE_NOT_AUTHORIZED`,
matching P29's own `allowed_participant_roles` precedent — **except**
Go/No-Go, which has no sensible fallback vocabulary and is a hard refusal
for an unclassified project (a deliberate, tested exception, not an
inconsistency).

**RFI/clarification directionality.** `rfi_originate` (Design-Builder/
Proponent — draft, revise, issue) and `rfi_respond` (Client/Owner — record
the authoritative response to an issued RFI) are registered as
`CAPABILITY_COUNTERPART`, not a bare exclusive label, because each has a
real counterpart on the other side. `RFIDraft` gained `response_text`/
`responded_at`/`responded_by` and a new terminal status,
`RFI_STATUS_ANSWERED`; `CaseWorkspaceStore.respond_to_rfi_draft` requires
`RFI_STATUS_ISSUED` first (a response follows issuance) and refuses a
second response, the same one-way-transition shape `issue_rfi_draft`
already used. Both RFI exporters (`build_rfi_docx`/`build_rfi_draft_docx`)
now stamp workflow direction; `routes/api.py`'s own RFI export was
unstamped as a CLAUDE-P29-noted scope limitation and is now stamped too.

**Go/No-Go — one shared record, two genuinely different vocabularies.** New
primitive `GoNoGoAssessment` (`workspace.go_no_go_assessments`):
`CaseWorkspaceStore.record_go_no_go_decision` validates `decision_stage`
against whichever of `CLIENT_OWNER_DECISION_STAGES` (procurement-oriented:
release RFQ/RFP, shortlist, award, ...) or `DESIGN_BUILDER_PROPONENT_
DECISION_STAGES` (pursuit-oriented: bid, accept commercial terms, submit
final proposal, ...) applies to the project's own locked environment — a
Client project attempting a Proponent-only stage is rejected at both the
route and service layers (tested). `decision` itself (`go`/`no_go`/
`conditional_go`) is closed and shared; `anomalies` is open-world free
text, deliberately not a closed enum (the list of things that could
justify a No-Go is large, environment-specific, and expected to grow).

**Reviewer-perspective boundary confirmed, not newly built.**
`capability_availability` takes only `operating_environment` as an
argument — `represented_party_by`, session role, and Case visibility are
structurally incapable of reaching it. Tested directly: representing a
Design-Builder participant inside a Client/Owner project does not unlock
RFI origination.

**Deliberately not done this stage, and why.** No `services/bhive_parser.py`
prompt received `operating_environment` context — documented as a
deliberate deferral (not an oversight) in `environment_capabilities.py`'s
own module docstring, consistent with this codebase's standing multi-
session caution around that module's adversarially-tuned prompts. No
`CAPABILITY_CLIENT_ONLY`/`CAPABILITY_PROPONENT_ONLY` registry entries were
registered — every genuinely single-sided capability found on inspection
had a real counterpart, so `CAPABILITY_COUNTERPART` was the honest
classification instead of manufacturing a bare "exclusive" label. No third
Operating Environment value, no multi-tenancy, no organizational security
architecture (explicitly reserved for a separate future stage per the
user's own instruction).

**Independent critique (Part XI), recorded findings:** the current RFI
exchange happens within a single project's own `workspace.rfi_drafts` list
— origination and response are two capability-gated actions on the *same*
record inside the *same* project, not a real cross-organization document
exchange between two separate projects/tenants. This is an honest
simplification consistent with "tenancy remains designed but unimplemented"
(unchanged this stage) — a true two-party RFI exchange (Proponent's project
sends, Client's separate project receives) is blocked on tenancy, not on
anything this stage could resolve alone, and is flagged as a real
architectural gap for whichever future stage takes up cross-project/
cross-tenant document exchange.

---

## 2026-07-30 — CLAUDE-P29: locked Project Operating Environment types

**Commits:** `d339d1c` (domain/service layer), `02a3ed3` (route/template/UI
wiring), `486d61f` (29 new tests + P28 test-file fixup), `d684e80`
(governance amendment + MANIFEST.md). Full suite: 854 passed, 0 failed.

**What was built.** A locked, immutable, project-creation-time
classification — Client/Owner vs. Design-Builder/Proponent — answering
"which side of a procurement/delivery relationship is this project's
*workspace itself* structurally configured to serve." `services/
environment_capabilities.py` (new): a closed two-value enum, a strict
validator (`is_valid_operating_environment` — rejects rather than
open-world-preserves an unrecognized value, a deliberate deviation from
this codebase's dominant `normalize_open_world_value` pattern, since a
closed/gated field needs the opposite shape), and one concrete capability
mapping (`allowed_participant_roles`). `ProjectWorkspace.operating_
environment`/`_set_by`/`_set_at` (new fields, default `None`).
`CaseWorkspaceStore.set_operating_environment` is the single write gate
for the field — raises the new `OperatingEnvironmentAlreadySetError` on
any second call, so there is exactly one place immutability could fail,
and it's tested directly at both the service and route layers (direct
call, forged route submission, same-value resubmission).

**Explicitly distinct from the existing Perspective mechanisms, not a
reopening of CLAUDE-P28's finding.** `represented_party_by`/
`PerspectiveAssessment` (CLAUDE-P12R/P17) is mutable, per-reviewer, and
answers "whose eyes am I reading this Finding through today" — untouched
by this stage, confirmed by test (`RoleAndPerspectiveIndependenceTests`)
that neither it nor a reviewer's session role can reach `operating_
environment`. The governed, still-**NOT AUTHORIZED** "Perspective"
object in `governance/specified-unbuilt/perspective-and-contract-
dna.md` remains not authorized — this stage's user-provided reasoning
for why Operating Environment is a *different*, narrower, bounded
concept (immutable/project-wide/creation-time vs. mutable/per-reviewer/
default-emphasis-only) was independently evaluated and accepted as
substantively sound, not just a rationalization, and is recorded as such
in `governance/STATUS.md`'s new authorization row — which explicitly
does not touch the pre-existing Perspective/Contract-DNA NOT AUTHORIZED
row directly above it.

**Creation path.** `ingest_upload()` now requires `operating_environment`
(no default — same "no inference path" discipline as `promote_
requirement_item`'s `source_id`), validated before any parsing begins;
the `ProjectWorkspace` is now always created eagerly (previously only
when `project_name` was given) so the environment locks atomically at
project birth — no project can transiently exist unclassified.
`templates/gateway.html` offers two creation entrances instead of one
generic card; `templates/upload.html` requires an explicit environment
selection (server-side allowlist is the real enforcement; the UI
checkbox is cosmetic).

**Legacy projects.** A pre-P29 workspace loads with `operating_
environment=None` — never inferred or backfilled. `routes/workspace.py`'s
new `classify_operating_environment` (`@admin_required`, matching the
authority level of project creation itself) is the one-time path to
establish it, through the identical write gate — refused the same way
on any second attempt. `allowed_participant_roles(None)` returns `None`
(no gating), so every pre-existing legacy project's Participant
functionality is unchanged until explicitly classified.

**Environment-dependent behavior, kept narrow.** The one implemented
differentiation is which `Participant.role_type` values are selectable
per locked environment (`register_participant_route`). No new AI-prompt
content was written — `services/bhive_parser.py`'s adversarially-tuned
prompts were deliberately left untouched, consistent with this
project's standing caution around that module. RFI export
(`build_rfi_docx`/`build_rfi_draft_docx`) stamps the environment label
when available; `routes/api.py`'s own RFI export route was deliberately
left unstamped this stage (no `CaseWorkspaceStore` access there — an
explicit, noted scope limitation, not an oversight).

**Deferred, not done this stage:** general environment-gated analysis
content, `routes/api.py` RFI-export environment stamping, and any
environment value beyond the two authorized here — all remain **NOT
AUTHORIZED** pending their own fresh authorization, per the new
`governance/STATUS.md` row.

---

## 2026-07-29 — CLAUDE-P28: project operating perspective + historical/forward-ingestion review

**Commit:** `295d148`. Full suite: 825 passed, 0 failed.

**Part I — the premise was significantly wrong; investigated and corrected, not implemented as asked.**
Repository-grounded investigation (not assumption) found: project
creation and document ingestion are the same atomic operation
(`services/ingestion.py`'s `ingest_upload()` — there is no separate
"New Project" step anywhere in the app, so several of the placement
options this stage was asked to evaluate don't match real architecture).
More importantly: a real, tested, working comparative-perspective
mechanism **already exists** — `Participant`/`PerspectiveAssessment`/
`ProjectWorkspace.represented_party_by` (`services/case_workspace.py`,
CLAUDE-P12R/P17), explicitly documented in its own code as *"a personal
setting... not a governed fact"*, per-reviewer and per-project, feeding
real perspective-aware analysis in
`services/requirement_investigation.py`, tested in
`tests/test_perspective_tier.py`. This already correctly separates
"comparative analytical perspective" from anything project-governing,
exactly the distinction this stage asked for.

What's actually missing — a **project-level governing** perspective
("whose interests this whole project is configured to serve", set
near creation, distinct from any one reviewer's personal setting) —
has **no code anywhere**, but also has an existing, ratified
specification: `governance/specified-unbuilt/perspective-and-contract-
dna.md`'s "Create-Project/Pursuit UX flow" (Perspective as step 2),
with an explicit guardrail that Perspective *"must never be stored as
a field on governed data... first-class only at the
application/authorization layer."* `governance/STATUS.md`'s
authorization table marks this whole layer **NOT AUTHORIZED — specified
only**. Implementing the governed version this stage's prompt described
would mean building something this repository's own governance process
has explicitly withheld authorization for — the same situation as the
tenancy design work in CLAUDE-P27-B, handled the same way: documented,
not implemented, pending a deliberate ratification act this session
doesn't have standing to perform on the user's behalf. No new UI was
added either — the existing "not represented yet" messaging
(`templates/case_workspace.html`) was found adequate on inspection, not
worth adding a redundant banner alongside.

**Part II — several claimed historical-data gaps do not exist; the
premise (a body of legacy data needing an advancement pipeline) does
not match repository reality.** `tests/fixtures/nreocrc/` is a
synthetic QA/capability-probe lab (same category as `tests/self_test/`),
not historical customer data. Cedar Harbour is the one real local
project and it's already on the current schema (its `workspace.json`
already has `represented_party_by`/`perspective_assessments` as native
keys). Specific claimed gaps checked directly against code and lab
records: Markdown support — **resolved**
(`services/bhive_parser.py`, code comment cites and resolves the exact
concern); table-aware segmentation — **implemented and current**
("Batch H", contradicts the claim it's absent); OPR-1 Row 20 — **already
resolved**, independently re-confirmed in the lab's own adversarial
comparison; `expected_provider` null — **not a defect**, just an unset
optional field in a test script. One claimed gap **is** real and still
open, confirmed directly against the lab record: **Row 14 ↔ 5.3
cross-reference is missed** by the generic detector's design (only
inspects a row's Notes column when Security Level also contains "/").
Deliberately **not fixed this session** — this is the same fragile,
adversarially-tuned consistency-check code this whole extended session
has treated with extreme caution (CLAUDE-P16/P22/P23/P25/P26's own
history shows small changes here need dedicated golden-suite validation,
not a same-session fix folded into an unrelated stage). "Restricted
Communications Sub-Zone" — searched, present in source material, not
flagged as a gap anywhere in the lab's own exhaustive adversarial
review; no evidence of a missed relationship.

Given no concrete body of historical data actually needs migration
right now, a full speculative historical-advancement pipeline
(compatibility classes, quarantine states, lifecycle machinery) was
**not built** — this would be exactly the kind of premature complexity
`tools/dependency_fit.py`'s stance and this repository's demonstrated
practice (see the tenancy precedent again) argue against building
before a real admission queue exists.

**What was implemented** (`295d148`, 6 new tests, all bounded and
directly evidence-justified): `BHIVE_PARSER_VERSION` stamped on every
new `ParsedDocument` (a confirmed real gap — nothing was ever
versioned), following this file's own existing
`CONSISTENCY_PROMPT_VERSION`/`INVESTIGATION_PROMPT_VERSION` convention;
duplicate-content detection using `original_file_hash` (already
computed on every ingestion, never actually checked against anything
until now) — informational only, recorded in the governance log, not a
hard block; the first dedicated test for `_reject_if_name_taken`
(confirmed real and enforced, previously untested).

**Next stage entry point:** none of this blocks anything. The tenancy
design package remains the natural next stage pending its four open
product decisions (unchanged from CLAUDE-P27-D). If perspective work is
wanted next, the actual next step is a deliberate authorization
decision on `governance/specified-unbuilt/perspective-and-contract-
dna.md` (the same kind of decision the four tenancy questions need),
not further investigation — the investigation is complete.

---

## 2026-07-29 — CLAUDE-P27-D: system of record and AI collaboration route

Governance/collaboration stage, not further hardening — no runtime code
changed. Established, in `CLAUDE.md`'s new "System of record and AI
collaboration route" section (read it there for the full model, not
duplicated here): pushed `origin/main` is the authoritative durable
record for everything except `.env`/secrets (never in git, by design)
and the sibling `archiosk-explorer` repo's own governance corpus
(cross-referenced, never duplicated); conversational AI output
(including this session, and external tools like ChatGPT) is
provisional until it lands in a pushed commit; `governance/constitutional-
invariants.md`'s authority is scoped to the BEEHIVE domain-object model
only, not infrastructure/security, where current tested code on `main`
governs instead; direct-to-`main` commits (no feature branches/PRs/
issues) remain the right model at this project's current scale, revisit
if a second human contributor joins.

Also fixed, as directly in-scope for "system of record integrity":
`MANIFEST.md` had gone stale during the P27-B session (20 new files
never catalogued) and, separately, already contained a now-materially-
false claim predating this session (`routes/api.py` "unaffected"/"out
of scope" for auth — false since commit `c2db13f`) — both corrected.
`MANIFEST.md` also flags, but does not attempt to fix, a much larger
pre-existing staleness (it predates the multi-user auth system and the
entire Case Workspace subsystem) as separate future work.

**Next stage entry point (CLAUDE-P28):** per this checkpoint's own P27-B
section below, the tenancy design package
(`governance/specified-unbuilt/tenancy-and-project-authorization.md`)
is implementation-ready pending its four open product decisions — that
remains the most natural next stage if no other priority intervenes.

---

## 2026-07-29 — CLAUDE-P27/P27-A/P27-B: security review, Hardened Starter Baseline, SMTP finalization

Supersedes the CaseWorkspaceStore-era section below as the current state
summary; that section is retained unmodified as historical record, not
because it's still current.

**Current commit state:** local `HEAD` and `origin/main` both at `279dd8a`,
in sync, working tree clean except the pre-existing untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/`. Full test suite: 819
passed, 0 failed as of the last full run this session.

**CLAUDE-P27** — full repository-grounded security/architecture review
(five parallel read-only inspection forks: identity/auth, tenant/
authorization/IDOR, storage/Snapshot, self-protection/AI, deployment/
audit/tests). Found the repository had no project-level tenancy/
authorization model (any authenticated user could open any project) and a
fully unauthenticated `/api/v1/*` JSON API. **CLAUDE-P27-A** restructured
the findings around natural continuation + a named Hardened Starter
Baseline rather than jumping straight to beta/subscription features.

**CLAUDE-P27-B** — the Hardened Starter Baseline, implemented as 10
reviewed, tested, individually-committed blocks (`c2db13f` through
`adccbd6`, see `git log --oneline bfa99d7..adccbd6` for the full list):
`/api/v1` authentication, a tenancy/project-authorization **design
package** (`governance/specified-unbuilt/tenancy-and-project-
authorization.md` — specified, deliberately **not implemented**, four
open product decisions block execution), `BaseConfig.validate()` boot
enforcement, `User.is_active` + suspension, security-event logging,
`ProxyFix`, rate limiting (Flask-Limiter), CSRF protection (Flask-WTF),
a prompt-injection boundary + AI kill switch in `services/bhive_parser.py`,
backup/restore tooling (a real backup + verified restore drill was run
against live data during the session), and Flask-Migrate/Alembic
adoption for the next schema change (the live database was `stamp`-ed to
the new baseline revision, not migrated through it).

**SMTP finalization (commit `279dd8a` for the credential-independent
code; real delivery verified live, not via a commit):**
- Implicit-TLS (`SMTP_USE_SSL`, `smtplib.SMTP_SSL`) support added
  alongside the pre-existing STARTTLS path in `services/email.py` —
  previously only STARTTLS existed at all.
- Boot-time SMTP configuration warnings added to `app.py`'s existing
  production validation (never hard-fails, matching the graceful-
  degradation philosophy already established for `ANTHROPIC_API_KEY`).
- Verified structurally that no reset token/URL is ever logged outside
  the dev-only fallback.
- **Real end-to-end delivery to `architect@rogers.com` via Netfirms is
  now fully verified**: SMTP connects, authenticates, and delivers;
  the reset link worked once and was correctly rejected on reuse; the
  dev-only fallback did not fire; no token or secret was exposed in
  the process (one earlier mistake mid-session — a dev-fallback-logged
  token was briefly echoed into the conversation transcript during
  diagnosis — was caught, the token was immediately invalidated via a
  direct DB write, and the log file was scrubbed; no repository
  content was affected).
- Working production config: `SMTP_HOST=smtp.netfirms.com`,
  `SMTP_PORT=465`, implicit SSL (`SMTP_USE_SSL=true`,
  `SMTP_USE_TLS=false`), full mailbox address as `SMTP_USERNAME`. The
  mailbox password required one reset on Netfirms' side before AUTH
  would succeed — the original password authenticated fine via
  webmail/IMAP but was rejected (clean SMTP `535`, not a connection
  drop) specifically for SMTP AUTH; resetting it resolved this.
- **Netfirms support case E-567913**: opened during diagnosis (the
  earlier STARTTLS/implicit-SSL AUTH-disconnect investigation surfaced
  a genuine, independently-confirmed TLS certificate hostname mismatch
  for `smtp.netfirms.com`, reported to Netfirms alongside the AUTH
  symptom). **Status: open, kept open only until Netfirms support
  confirms or closes it.** Whoever closes it should note: the
  practical blocking issue (SMTP AUTH rejection) was resolved by
  resetting the mailbox password, not by a Netfirms-side change — the
  certificate hostname-mismatch finding is a separate, still-
  unconfirmed report to Netfirms and may still be worth their fixing
  independent of this case's resolution.

**Not started this session, explicitly deferred, no new authorization
implied:** tenancy migration execution, `Invitation`/entitlement/
subscription models, further `CaseWorkspaceStore` route wiring (per
P27-A's own reasoning: wiring more routes before the tenancy work lands
would just add more surface inheriting the same still-open isolation
gap), dependency version-staleness remediation.

**Recommended next prompt**, if none of the above is what's wanted next:
resolve the four open product decisions in
`governance/specified-unbuilt/tenancy-and-project-authorization.md`
(personal-org default, project-to-org cardinality, project-name
uniqueness scope, admin-bypass semantics) — that design package is
otherwise implementation-ready.

---

## Historical: CaseWorkspaceStore backlog checkpoint (superseded above)

Written on explicit request, after a read-only investigation into the
`CaseWorkspaceStore` backlog item. **Not committed or pushed** — this file
is currently untracked, left for the user to review/commit/discard as they
choose. Session was stopped here deliberately so it can be cleared.

## Current commit state

- Local `HEAD`: `a79adf489c841c43b21f4e9e0dea53ad38b6c833`
- `origin/main`: `a79adf489c841c43b21f4e9e0dea53ad38b6c833`
- Both in sync. Working tree clean except the pre-existing untracked
  `tests/fixtures/nreocrc/_lab_instance_scratch_002/` directory, present
  since before this session started.

## P25 / P26 results (recap)

**CLAUDE-P25 — commit `686eaa2`.** Root cause: the consistency investigator
could focus on differing numeric thresholds while failing to credit
explicit temporal/operational/spatial/conditional scope stated *within* the
same two clauses — isolated to **clause density** (a long clause bundling a
numeric obligation with a protocol/condition description), not any one
scope dimension. Fix: `ConsistencyFlag` gained `requirement_a/b_obligation`,
`requirement_a/b_scope`, `scopes_overlap`, `scope_reconciliation_reasoning`;
prompt requires an explicit 4-step scope check; `_check_consistency`
deterministically drops any flag lacking scope reasoning or whose own
`scopes_overlap=False` contradicts inclusion. Results: 38/39 on the full
scope-reconciliation matrix post-fix; Golden Suite 30/31 clean (1 transient,
unrelated model-call error); full pytest 706 passed.

**CLAUDE-P26 — commit `833187c`.** Investigated P25's own recheck runs
showing ~50% malformed output specifically on the isolated two-clause
condition (valid JSON, then self-correction prose, sometimes a second,
differing JSON array). Did not reproduce in a fresh 57-call sample, but
real evidence from P25 confirms it happens intermittently. Tested and
**rejected** Anthropic tool-use (schema-enforced structured output) as a
fix: it fixed formatting 100% but got the one genuinely hard specimen wrong
3/6 times (each miss a bare ~33-token "no conflict" call vs. ~700–800
tokens of real reasoning in every correct run) — forcing structured output
let the model skip its own reasoning on the hard case. Adopted fix:
parsing-only, no new model-call shape. `services/consistency_response_
parser.py` classifies a response into 7 categories; the first four (single
valid JSON / valid JSON + harmless prose / multiple equivalent blocks /
malformed-but-repairable) are accepted immediately; only a genuinely
unresolvable response (conflicting blocks, or unusable) triggers exactly
one bounded retry before falling back to the prior graceful skip. Results:
real rerun of the exact previously-failing condition — 6/6 valid, all
correctly clean (2 recovered via the bounded retry). Full pytest 730
passed. Golden Suite fully clean (0 malformed, 0 false positives, 0
did-not-run).

**Candidate `276cac42` (aquatic-centre):** still quarantined, not promoted.
Clean baseline improved across both fixes (7/10 false positives in P24 →
0/8 after P25 → 6/6 correctly clean after P26), but per standing
instruction this is not grounds for promotion on its own.

Full detail: `tests/self_test/CHECKPOINT.md` (committed at `a79adf4`).

## Contents of commit a79adf4

One file changed vs. its parent `833187c`: `tests/self_test/CHECKPOINT.md`,
96 insertions, 0 deletions (pure addition). Commit message: "Add P25/P26
continuation checkpoint for the self-test regression lab" — concise
handoff covering `686eaa2` and `833187c`: what each found, what was fixed,
test results, the aquatic-centre candidate's still-quarantined status, and
the queued `CaseWorkspaceStore` backlog item (not started at that point).

## CaseWorkspaceStore backlog — read-only inventory (this session)

Produced by a forked, read-only investigation cross-referencing every
public method in `services/case_workspace.py` against `routes/workspace.py`,
the two intermediary services that also call into the store on already-
reachable production paths (`services/conversation_interpreter.py`,
`services/project_clock.py`), and `governance/STATUS.md`/`kernel-object-
model.md`'s authorization table. No code was written or changed.

The user's five requested categories don't cover every case found —
several subsystems are simply unwired, tested, and authorized with no
blocking concern. That's called out below as an extra, unrequested bucket
rather than force-fit into one of the five.

### 1. Genuinely required by current routes (not actually a gap)
Reachable today via `conversation_interpreter.interpret_message` (called
from `routes/workspace.py:1580`) or `project_clock.open_project` (called
from `routes/workspace.py:262`): `record_analysis`,
`can_open_autonomous_case_for`, `create_autonomous_case`,
`current_requirement_for`, `record_investigation_step`,
`requirement_predecessor`, `corrections_for_case`.

### 2. Intentionally dormant / future-facing
- `record_supersession`, `supersessions_for` — own docstring: "reserved for
  Experience/Knowledge revision," only used internally today.
- `record_activity` — zero callers anywhere (test or production), excluded
  from the collaboration-threshold set pending an authorship-convention
  decision that hasn't been made.

### 3. Duplicate or superseded
- `requirements_for_source` (→ `requirements_for_project`)
- `latest_requirement_adjudication_for` (→ `requirement_adjudication_state`)
- `case_outcomes_for`, `latest_case_outcome_for` (→ `case_outcome_state`)
- `dispositions_for_finding` (→ `latest_disposition`)
- `perspective_assessments_for_anchor` (→ `perspective_convergence_for`)
- `set_review_thread_status` (internal helper behind `resolve_review_thread`
  / `reopen_review_thread`)

### 4. Unsafe or unauthorized to expose
- `update_source_identity` — real write method, **zero test coverage found
  anywhere** in the suite. Wiring a route to it would be the first real
  exercise of this code path in production.

(Nothing found corresponds to a `governance/STATUS.md` **NOT AUTHORIZED**
item — those have no store methods written at all yet. No conflict between
this inventory and the authorization table.)

### 5. Uncertain and requiring architectural review
- `confirm_relationship` — `kernel-object-model.md` flags a known
  consistency gap (in-place mutation, not append-only). Wiring a route now
  would surface that gap to real users rather than resolve it first.
- `record_relationship` — standalone write entry point; unclear whether
  it's meant to be human-invoked or stay machine/internal-only.
- `link_thread_outcome` — combines thread-resolution + relationship-
  confirmation; needs a UX decision, and inherits `confirm_relationship`'s
  open question.
- `revise_temporal_obligation` — write path with no route; unlike
  `create_temporal_obligation` (wired), its revision/authority semantics at
  the route layer haven't been decided.

### 6. (Unrequested bucket) Ready to wire — tested, authorized, no blocker
- **Structured Tabular Evidence + Source-Reference resolution** (Foundation
  Batch J, newest subsystem): `register_table_evidence`,
  `tables_for_source`, `get_table`, `rows_for_table`, `get_table_row`,
  `resolve_table_cell`, `reconcile_table`,
  `extract_and_register_source_references`, `source_references_for_source`,
  `get_source_reference`, `source_references_to_target`. Well-tested
  (`tests/test_foundation_batch_j.py`); zero route or trigger point
  anywhere — even the write side isn't invoked during ingestion today.
- **Snapshot read-side** (write side `create_snapshot` already wired):
  `snapshots_for_project`, `get_snapshot`, `resolve_snapshot_objects`,
  `compare_snapshots`. A Snapshot can be created but never listed, opened,
  or diffed.
- **Expected Information Profile** (whole subsystem unwired):
  `create_expected_information_profile`, `add_expectation_item`,
  `set_expectation_item_status`, `profiles_for_scope`,
  `profiles_for_project`, `revise_expected_information_profile`. Tested in
  `test_foundation_batch_e.py`.
- **Design/Estimate Maturity** (whole subsystem unwired):
  `record_design_maturity`, `record_estimate_maturity`, `maturity_for_scope`,
  `revise_maturity`. Tested in `test_foundation_batch_e.py`.
- `set_requirement_status` — real write path, hard denylist against
  compliance-shaped values, IMPLEMENTED per `STATUS.md`. No route today.
- `derived_cases_of`, `carried_forward_adoptions_for_case` — read-only
  reverse-lookup queries behind already-wired, tested writes; lineage can't
  currently be displayed.
- `threads_for_project`, `threads_for_anchor` — low-priority read-side gaps.

### Smallest coherent wiring seams (identified, NOT implemented)
1. **Snapshot listing + compare** — smallest true seam; zero new write
   logic, purely additive read-side display, no architectural ambiguity.
2. **`set_requirement_status` route** — one small write route, directly
   analogous to already-wired patterns (`share_case`/`archive_case`).
3. **Foundation Batch J display** — larger seam; even the write side has no
   current trigger point, so wiring it coherently means first deciding
   where those writes should fire (ingestion pipeline vs. a manual action).

## Unresolved decisions
- Which wiring seam to start with first, if any (Snapshot read-side,
  `set_requirement_status`, Batch J, or Expected Info Profile/Maturity).
- Whether `confirm_relationship`'s known append-only gap should be fixed
  before any route wiring, or documented as an accepted limitation.
- Whether `update_source_identity` needs tests written first, independent
  of any route-wiring decision.
- Whether `record_activity`'s authorship convention should be decided now
  or left dormant.
- `governance/current/kernel-object-model.md` is stale (self-reports 393
  tests; suite is now 730) — separate documentation-debt observation, not
  acted on here.

## Recommended next prompt
"Wire the Snapshot read-side (list/open/compare) as the first
CaseWorkspaceStore seam: smallest, zero write-path risk, existing create
route already live." (Alternatives: `set_requirement_status`, or Expected
Information Profile if a larger single subsystem is preferred first.)
