# GO-TRUST-SECURITY-01 — Trust Exchange — Security Policy, Client Requirements, and Recommissioning

| Field | Value |
|---|---|
| Prompt ID | GO-TRUST-SECURITY-01 |
| Title | Trust Exchange — Security Policy, Client Requirements, and Recommissioning |
| Agent | Unassigned (future trust and security-commissioning programme) |
| Status | DEFERRED |
| Purpose | Preserve a two-way, evidence-based security trust exchange in which client requirements, ARCHIOSK responses, testing, deficiencies, acceptance, and material-change recommissioning remain distinct and governed. |
| Product Owner acceptance | Confirmed future programme direction. The canonical record is concept-preservation only and explicitly NOT AUTHORIZED for design or implementation without fresh authorization. |
| Lineage | Prompt Depository anchor for [Trust Exchange & Security Commissioning](../specified-unbuilt/trust-exchange-and-security-commissioning.md), recorded under `CLAUDE-POSTCAMEL-COMM-I1`. Related authoritative layers remain distinct: implemented bounded [Organizational Security and Information Governance](../specified-unbuilt/organizational-security-department.md), specified/unbuilt [Project Security Policy](../specified-unbuilt/security-policy.md), [External Intelligence Airlock](../specified-unbuilt/external-intelligence-airlock.md), [GO-DT1-01](GO-DT1-01.md), and current [Self-Project Commissioning Readiness](../current/comm-a1-self-project-commissioning-readiness.md). |
| Superseded by | None |
| Absorbed into | None |

## Application Security and Trust surface

An Admin or other appropriately governed administrative surface should provide an authorized, read-only explanation of how security is handled in the ARCHIOSK environment. Its purpose is to remove mystery by communicating security philosophy, responsibility boundaries, governance, information-handling principles, authorization concepts, project and tenant isolation, and change or recommissioning expectations.

It must not reveal exploitable implementation detail, secrets, credentials, sensitive defensive techniques, or tenant-confidential material. The currently implemented admin Security Department and bounded security-policy machinery remain authoritative for present capability; this future Trust surface must not overstate them.

## Client and government security-policy intake

A government agency or other client should eventually have a governed place for an authorized administrator to register applicable security policies and requirements. Those requirements remain attributable to the client and project. ARCHIOSK may produce a distinct application response against them but must not silently claim compliance.

Preserve these separate states and artefacts:

- client security requirement or policy;
- ARCHIOSK response;
- evidence of implementation;
- validation and testing;
- unresolved issue;
- acceptance or commissioning state.

The existing Project Security Policy specification already establishes that client policy is project-specific governed `Requirement` content and is distinct from ARCHIOSK's own application behaviour. Do not merge the two.

## Security as commissioning

Security is something that can be commissioned, not merely documented once. A future process may include requirement intake, application response, review, testing, deficiency identification, correction, retesting, and acceptance.

A prior accepted state does not silently remain valid after material application, policy, environment, or security change. Material change may require recommissioning under renewed scope and authority.

The canonical record further preserves mutually approved testing, bounded agency-authored tests, restraint or non-retrieval as positive evidence, deficiency and retest cycles, and expiry after material change. It does not authorize unrestricted penetration testing or autonomous red-team activity.

## Trust Exchange

Security is a two-way trust exchange: the client states requirements and constraints; ARCHIOSK states its response; evidence and tests demonstrate what is implemented; gaps remain visible; and acceptance belongs to the appropriate authority.

Do not replace this with a one-sided security-certification claim or treat application response as proof of compliance.

## Relationship to project commissioning

[Self-Project Commissioning Readiness](../current/comm-a1-self-project-commissioning-readiness.md) and subsequent commissioning governance provide related lifecycle, evidence, deficiency, correction, and reassessment concepts. Security commissioning may be one commissioning domain among others, but its authorization, confidentiality, technical-safety, and legal boundaries remain distinct.

## Relationship to Admin and DT1

[GO-DT1-01](GO-DT1-01.md) remains distinct. The Trust/Security surface concerns policy, requirements, response, status, and governed evidence. DT1/Engineering Observatory concerns deeper authorized diagnostics and engineering inspection. A policy surface does not authorize disclosure of engineering detail, secrets, or unrestricted traces.

## Relationship to External Intelligence and Airlock

The [External Intelligence Airlock](../specified-unbuilt/external-intelligence-airlock.md) remains the governing future boundary for external AI or tool requests and associated data movement. Third-party interactions may be relevant to security requirements and testing, but Trust Exchange does not weaken `ACTION_EXTERNAL_AI_REQUEST`, minimum-necessary disclosure, authorization, inbound-untrusted, or human-adoption controls.

## Governance boundary

Do not claim compliance without evidence; expose secrets or security-sensitive implementation detail; allow unauthorized modification of organization or client policy; merge client policy with ARCHIOSK policy; let prior test success silently survive material change; or treat security commissioning as legal certification without explicit authorization by the responsible authority.

This record does not authorize security UI, policy intake, application-response generation, tests, commissioning workflow, recommissioning, penetration testing, or runtime changes.

## Recovery status

**RECOVERY PENDING:**

- original Trust Exchange or Security Commissioning prompt;
- exact Admin security text and policy wording;
- exact client policy-upload workflow;
- application-response format;
- commissioning and recommissioning state model;
- deficiency-closeout workflow;
- historical security examples;
- exact programme ID and sequence;
- diagrams, prototypes, or acceptance reports.

Do not invent these. Later recovered material may enrich this record while preserving the canonical programme, current security truth, authority, and historical lineage.

## Exact prompt text

```text
ARCHIOSK/GO should make its security philosophy and governance understandable to authorized users without exposing sensitive implementation techniques, while also providing a governed place for client/government security requirements to enter the project and be answered, tested, commissioned, and re-tested over time.
```

## Execution references

- Run: Concept preserved under `CLAUDE-POSTCAMEL-COMM-I1`; no Trust Exchange implementation run authorized
- Result: `governance/specified-unbuilt/trust-exchange-and-security-commissioning.md`
- Commit: Exact historical commit lineage recovery-pending
