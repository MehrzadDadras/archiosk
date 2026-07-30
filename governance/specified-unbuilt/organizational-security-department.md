# Specified But Unbuilt — Organizational Security and Information Governance (full target)

**Status:** Bounded foundation implemented (CLAUDE-P31); the full enterprise target below is
specified, not implemented. Distinct from `specified-unbuilt/security-policy.md`'s "Project
Security Policy" (a customer's own security requirements captured as governed `Requirement`
content inside their project — Domain 1, application-layer-neutral). This document is the
opposite direction: it governs **ARCHIOSK's own application behavior** — what ARCHIOSK itself is
permitted to do with a project's data — an infrastructure/application-layer concern (see
`CLAUDE.md`'s "current tested code on pushed main is authoritative" precedence rule for this
category), not a kernel/domain-model concept, and not something `governance/STATUS.md`'s
domain-model authorization table governs.

## What's actually implemented (CLAUDE-P31)

- `services/security_policy.py` — `GOVERNED_ACTIONS` (8 actions), `MANDATORY_FLOOR_DEFAULTS`,
  `evaluate_action` (the centralized floor → baseline → profile → exception resolver,
  most-restrictive-wins, exception ceiling capped at `DECISION_ALLOW`), `INFORMATION_
  CLASSIFICATIONS` + `CLASSIFICATION_PROFILE_DECISIONS` (explicit control-bundle meaning per
  classification), `SECURITY_CLAIMS_REGISTRY`.
- `services/security_governance.py` — `SecurityGovernanceStore`: one **global, deployment-wide**
  record (`SourcePolicy`, `PolicyStatement`, `ProposedControl`, `QAEntry`, `BaselineVersion`,
  `SecurityException`), full draft → under-review → approved → active → superseded/withdrawn
  baseline lifecycle, capability-impact acknowledgement gating activation.
- `services/case_workspace.py` — `ProjectWorkspace.security_profile` (+`_set_by`/`_set_at`),
  `set_project_security_profile` (re-settable, unlike `operating_environment`, but every change
  logged).
- `services/ingestion.py` — the one real enforcement point: `ACTION_EXTERNAL_AI_REQUEST` is
  evaluated before every new project's classification, wired into `BHiveParser`'s pre-existing
  `ai_calls_disabled` kill switch (CLAUDE-P27-B) — no changes inside `bhive_parser.py` itself.
- `routes/workspace.py` — `ACTION_EXPORT` gates both RFI export routes.
- `services/diagnostics.py` — `TechnicalTelemetry` (structurally content-free) vs.
  `SupportPackage` (requires an ALLOW-shaped `SecurityDecision` to construct at all).
- `services/learning_governance.py` — `LearningContributionRequest`: governed **approval-tracking
  only**, zero data movement (no shared-learning pipeline exists to move data into).
- `services/security_assurance.py` — `aggregate_security_activity` (cross-project, activity-level
  only, read-side over existing `GovernanceLog` files), `run_security_self_check` (5 representative
  checks).
- `routes/security.py` + `templates/security_department.html` — the admin-only workspace.
- 80 tests across `tests/test_security_policy_engine.py`, `test_security_governance.py`,
  `test_learning_governance.py`, `test_security_enforcement.py`, `test_security_assurance.py`.

## Deliberately not built this stage, and why

- **AI-assisted policy clause extraction.** Statements/control proposals are human-entered only.
  No new prompt was written against `services/bhive_parser.py`'s already-fragile, adversarially-
  tuned prompt surface (see that module's own CLAUDE-P16/P22/P23/P25/P26 history) or anywhere
  else. Extraction remaining fully human keeps "do not allow machine extraction to activate
  controls automatically" true by construction, not by a runtime check.
- **A real shared-learning/training pipeline.** Nothing in this repository persists prompts,
  outputs, or embeddings anywhere but a single project's own governed record. `learning_
  governance.py` records *intent and approval state*; reaching `contribution_approved` causes
  zero data transfer, because there is nowhere for Zone 3 to receive it. See `security_policy.py`'s
  `SECURITY_CLAIMS_REGISTRY["shared cross-customer learning pipeline"]` = `specified_but_unbuilt`.
- **Multi-organization tenancy.** `SecurityGovernanceStore` manages ONE global record, not one per
  tenant — see `specified-unbuilt/tenancy-and-project-authorization.md`, still unimplemented.
  Every "organization baseline" claim in this codebase today means "this deployment's one
  configuration," never "this customer's isolated configuration."
- **Content-level assurance viewer.** `aggregate_security_activity` and the workspace's own
  Assurance section surface actor/project/action-category/decision only — never Requirement/
  Finding text. No route exists to view raw project content through the security lens at all.
- **AI-generated exception/Q&A recommendations, security-officer role distinct from admin,
  organization-scoped RBAC, cryptographic audit integrity, regional processing controls.**

## Full target architecture (specified here, not built)

- **AI-assisted extraction with mandatory human confirmation** — `PolicyStatement`/`ProposedControl`
  generation assisted by a dedicated, narrowly-scoped prompt (never `bhive_parser.py`'s own),
  every output landing in the existing `requires_confirmation`-gated proposal state, never
  auto-activating.
- **Real learning-zone data movement** — an actual mechanism to move sanitized/minimized signal
  from Zone 1 (project-private) → Zone 2 (organization-private) → Zone 3 (shared ARCHIOSK
  improvement), with `LearningContributionRequest.decided_by == contribution_approved` as the one
  and only trigger, never inferred from a quality rating.
- **True multi-organization isolation** — `SecurityGovernanceStore` scoped per `Organization`
  (once `tenancy-and-project-authorization.md` ships), each organization's baseline genuinely
  invisible to every other organization, not merely one shared global file.
- **Content-level assurance with recorded purpose** — a governed "view actual content for this
  investigation" act, itself logged as its own audit event, gated behind materially stronger
  authority than activity-level visibility.
- **Cryptographic/tamper-evident audit** — hash-chaining or an external write-once store backing
  `GovernanceLog`, closing the honesty gap `SECURITY_CLAIMS_REGISTRY["tamper-proof logs"]` =
  `prohibited_from_claiming` currently reflects.
- **Regional/data-residency processing controls** — genuinely routing external AI calls through a
  region-pinned endpoint, closing `SECURITY_CLAIMS_REGISTRY["regional/data-residency processing
  control"]` = `unsupported`.
- **A dedicated Security Officer role**, distinct from `admin`, once real customer organizations
  with their own internal security staff exist as a concept this codebase can represent at all
  (blocked on tenancy for the same reason `classify_operating_environment`/this stage's own routes
  use `admin_required` — no finer-grained role exists yet).

## Explicitly not designed here

Infrastructure/tenant hosting isolation (separate encryption keys, separate physical/cloud
tenancy) remains the distinct, unsolved operational-security layer named in
`specified-unbuilt/security-policy.md` and `deferred-reserved/reservations.md` — out of scope for
this document exactly as it was for that one.
