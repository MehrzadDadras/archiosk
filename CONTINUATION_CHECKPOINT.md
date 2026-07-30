# Continuation checkpoint

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
