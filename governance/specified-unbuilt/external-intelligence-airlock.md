# Specified But Unbuilt — External Intelligence Airlock and Constructive Boundary Response

**Status:** Specified. **One narrowly bounded mission — Mission 01 — is now AUTHORIZED for implementation**
(`CLAUDE-AIRLOCK-AUTH-01`, 2026-08-19); everything else in this document, including the whole of Part 2,
remains NOT AUTHORIZED. See "Product Owner authorization — External Intelligence Airlock Mission 01" at the
end of this document for the exact bounded scope and the STOP boundary. As at that authorization, zero code
exists for anything in this document. Originally recorded
under `CLAUDE-CGP-02` (the cockpit gate preceding the Camel MM1–MM9 build stages) as a
planning-level record of two cross-cutting security concepts the product owner requires ARCHIOSK
to eventually carry — not a build order, and not itself part of the cockpit gate's own
accept/correct scope.

**Relationship to the rest of this governance corpus.** Both concepts below are new; neither
duplicates an existing document. `specified-unbuilt/security-policy.md` is a *customer's own*
security requirements captured as governed `Requirement` content (Domain 1, project-specific).
`specified-unbuilt/organizational-security-department.md` governs what ARCHIOSK itself is
permitted to do with a project's data, and already contains the one concrete real anchor this
document extends: `services/security_policy.py`'s `ACTION_EXTERNAL_AI_REQUEST` (currently
`DECISION_DENY` at both floor and baseline — see that file's `MANDATORY_FLOOR_DEFAULTS`/
`GOVERNED_ACTIONS`), the single existing gate on any outbound call leaving a project's boundary.
Today that gate is binary (allowed/denied); the Airlock below is what a future `ACTION_
EXTERNAL_AI_REQUEST = DECISION_ALLOW` state would need to actually *do* before ARCHIOSK is
permitted to construct such a request at all, not a replacement for the gate itself. `services/
governance.py`'s `GovernanceLog` is the existing, real, append-only audit mechanism both concepts
below assume as their internal record-keeping anchor — neither concept invents a second audit
trail.

**No implementation implied.** Nothing here authorizes writing an outbound connector, a redaction
pipeline, an inbound-content sanitizer, or a boundary-response UI. This document exists so a
future MM stage (see the mapping table below) does not have to re-derive this reasoning from
scratch, and so no future session builds a naive, unredacted outbound call or a boundary message
that leaks internal structure, for lack of a recorded design intent to consult first.

---

## Part 1 — Intelligence Airlock / External Intelligence Vestibule

Archiosk must eventually use a controlled outbound and inbound vestibule for questions requiring
public or external knowledge — genuinely distinct from `services/bhive_parser.py`'s existing
in-project AI calls, which never leave the project's own governed content. The Airlock is
specifically the boundary a request crosses when the question needs knowledge the project's own
`Source`/`Requirement`/`Finding` corpus cannot supply.

### Outbound operation must

- construct a minimum-necessary mission packet — only the fields actually required to answer the
  external question, never a raw dump of project context;
- remove project/client/person identifiers, credentials, paths, internal URLs, application code,
  prompts, schemas, security rules, metadata, comments, active content, and unrelated context;
- use approved fields and allow-listed content rather than relying only on after-the-fact
  redaction — a positive allow-list (what may leave) is the primary control, not a denylist
  patched over an unconstrained payload;
- provide a disclosure preview when sensitivity warrants it — a human-reviewable rendering of
  exactly what the mission packet contains, before it is sent;
- assign disposable external aliases and expiry to any identifier that must travel with the
  packet (a project or requirement referenced only by a short-lived, meaningless-outside-the-
  packet token, never its real internal id or name);
- retain an internal audit record while allowing the temporary mission payload to expire — the
  packet itself is not the record of what happened; the `GovernanceLog` event is.

### Inbound operation must

- treat all returned content as untrusted, unconditionally — no external response is ever treated
  as governed fact on arrival;
- strip or reject scripts, macros, trackers, executable content, unexpected attachments, and
  unsafe links;
- detect prompt-injection or instructions directed at the internal agent embedded in returned
  content, and refuse to act on them;
- separate external evidence from system authority — an external response can become a candidate
  `Finding`/`Source` with `origin_type` honestly labeled external, never a route to bypass the
  existing provisional-until-validated discipline `Finding.claim_status` already enforces;
- validate sources and mark unsupported claims — an external claim with no traceable source stays
  visibly unsupported, not silently upgraded by confident phrasing;
- prevent direct execution or automatic modification of governed records — nothing returned from
  outside the Airlock ever writes to a `Case`, `Requirement`, or any other governed object without
  passing through the same human-adjudication paths (`RequirementAdjudication`, `Disposition`,
  `ReviewerValidation`) every other AI-touched conclusion already requires;
- require human review before consequential adoption — the same "no silent AI-to-authoritative
  promotion" cross-cutting rule the Camel programme states for MM7 applies here without exception.

### Governing principle

**The temporary mission packet may self-destruct; the accountable internal record must not.**
Whatever crosses the boundary outward is minimized, aliased, and disposable; whatever is kept
internally about the fact that it happened, what was sent, and what came back is permanent,
attributable `GovernanceLog` material — the same asymmetry `constitutional-invariants.md` already
establishes between transient working state and the durable governed record, applied at a new
boundary (the edge of the deployment) rather than only within it.

---

## Part 2 — Constructive Boundary Response

When a legitimate user reaches a protected boundary, Archiosk should protect the system without
punishing curiosity. This is a UX/security-response pattern for the moment a request is refused —
distinct from the refusal decision itself (`services/security_policy.py`'s `evaluate_action`
already resolves *whether* to deny; this document is about what the user sees *when* denied, and
what gets logged about it).

An initial, low-risk response may say, for example:

> Nice try. That area is protected. Were you looking for a particular capability?

or:

> You found a boundary. Tell me what you were trying to do, and I'll show you the supported
> route.

These are illustrative tone examples, not fixed copy — the requirements below are what any actual
wording must satisfy, not the wording itself.

### Requirements

- stop the prohibited action;
- disclose no internal security rule, path, object existence, policy identifier, or defense
  mechanism — a denial must never confirm or deny the existence of something the requester
  couldn't already see (the same non-disclosure discipline `routes/`'s existing generic-404
  pattern for unauthorized project access, `services/project_access.py`, already establishes for
  a different boundary — "identical whether a project doesn't exist or the caller isn't
  authorized for it," per `governance/STATUS.md`'s CLAUDE-P32 row — extended here to security
  boundaries generally, not invented fresh);
- ask about the intended outcome;
- offer an authorized route where one exists;
- log the full technical event internally — the real mechanism, path, and payload attempted, via
  `GovernanceLog`, never surfaced to the requester, exactly as this repository already treats
  security-relevant events (see `organizational-security-department.md`'s existing security-event
  logging);
- escalate tone and containment for repeated, evasive, automated, or clearly hostile probing — a
  single curious misstep and a sustained, evasive, automated probing pattern are not the same
  event and must not receive the same response; escalation state would need to be tracked
  per-actor, not per-request, which is itself new state this document does not design.

### Governing principle

**Redirect legitimate exploration; quietly record and progressively contain hostile behaviour.**
The default posture assumes good faith (a curious, legitimate user probing an edge of the
product), while the logging and escalation path underneath that posture assumes some fraction of
attempts will not be — the same posture this repository's own prompt-injection boundary in
`services/bhive_parser.py` (CLAUDE-P27-B) already takes toward untrusted document content, applied
here to untrusted *user* interaction instead.

---

## Mapping across MM1–MM9 and security/governance records

Neither concept above is owned by one MM stage — both are cross-cutting, the same way the Camel
programme's own "Cross-cutting requirements" section and the Design-Manager integration
requirement are (`camel-multimodal-programme.md`). Mapped here so a future stage doesn't have to
re-derive where each concept becomes concrete:

| Concept facet | Where it becomes concrete |
|---|---|
| Outbound minimum-necessary packet, allow-listing, disclosure preview, aliasing/expiry | A new capability composing with `services/security_policy.py`'s existing `ACTION_EXTERNAL_AI_REQUEST` gate — not owned by any single MM stage, but first *needed* wherever an MM stage's own analysis (sharpest candidate: MM7's governed multimodal analytics, and the Design-Manager Monte Carlo case's own external-benchmark comparisons, if ever required) reaches outside the project's governed corpus |
| Inbound untrusted-content handling, prompt-injection detection on returned content | Same anchor as above; composes with `services/bhive_parser.py`'s existing prompt-injection boundary (CLAUDE-P27-B), extended to a second untrusted-content source (external responses) rather than only uploaded documents |
| External evidence honestly labeled, never silently authoritative | The same MM1 vocabulary (fact vs. measurement vs. expert judgment vs. user assumption vs. AI suggestion) gains a sixth provenance case — external evidence — enforced the same way MM7 enforces the other five |
| Human review before consequential adoption of external content | Composes with the existing `RequirementAdjudication`/`Disposition`/`ReviewerValidation` authority pattern (`current/kernel-object-model.md`) — not a new authority mechanism, the same non-authorization the Camel programme's own Design-Manager mapping table already states for AI-suggested Monte Carlo inputs |
| Constructive Boundary Response (tone, non-disclosure, logging, escalation) | Infrastructure/application-layer, not owned by any MM stage — composes with `services/security_policy.py`'s `evaluate_action` (the denial decision) and `services/governance.py`'s `GovernanceLog` (the internal record); the nearest existing precedent is `services/project_access.py`'s generic-404 non-disclosure pattern (CLAUDE-P32) and `services/project_access.py`'s access-denial path, extended from "silent generic denial" to "silent-to-the-boundary-detail but constructively worded denial" |
| MM9 consolidated validation | Whichever pieces of both concepts are eventually built would need their own real-browser proof the same way every other MM9 acceptance scenario does — not designed further here |

**Authorization status:** both concepts are **NOT AUTHORIZED** for implementation, joining
`governance/STATUS.md`'s "specified but unbuilt" list as a single pointer, the same filing pattern
already used for the Camel programme itself.

---

## Product Owner authorization — External Intelligence Airlock Mission 01

**Recorded `CLAUDE-AIRLOCK-AUTH-01` (2026-08-19).** This section supersedes the
"Authorization status" paragraph immediately above **only to the extent stated here**. That
paragraph's original wording is deliberately left intact rather than rewritten, per
`constitutional-invariants.md` #5 (correction is non-destructive — append a superseding record,
never erase) and the precedence rule in `governance-of-governance/amendment-and-ratification.md`.
Everything in Part 1 not named below, and the whole of Part 2 (Constructive Boundary Response),
remains **NOT AUTHORIZED**.

### What is authorized

The Product Owner explicitly authorizes implementation of **External Intelligence Airlock —
Mission 01**, one bounded research mission:

> Retrieve authoritative Ontario Building Code material from a narrowly approved official Ontario
> source for the SRPC B1 smoke-management investigation, pass it through the governed Airlock
> boundary, verify its citation/provenance deterministically, retain it as externally researched
> and unvalidated evidence, and **STOP** before any promotion or project-authority transition.

Concretely, and only this:

**bounded allow-listed mission packet** → **deterministic retrieval from the single approved
official Ontario source** → **interpretation through the existing single-shot, tool-less
`services/llm_gateway.py` `call_llm_json()` boundary** → **deterministic citation/provenance
integrity check** → **quarantined retention** → **STOP**.

### The STOP boundary

Mission 01 ends the moment retrieved material is retained as quarantined evidence. It does not
adjudicate, does not promote, does not produce a `Finding` carrying project authority, and does not
touch `RequirementAdjudication`/`Disposition`/`ReviewerValidation`. **No promotion path exists in
Mission 01 by any route, including a human one** — building that path is itself out of scope. This
is the checkpoint at which the Product Owner learns whether deterministic retrieval and, more
importantly, the citation/provenance integrity check actually work against real Ontario Building
Code material; promoting anything before that is known would build on unverified authority.

### Quarantine representation — reuse, do not invent

Quarantined external material is represented with primitives that already exist:
`Source.origin_type` (open-world, `normalize_open_world_value`), `EvidenceItem.evidence_class` set
to `EVIDENCE_CLASS_EXTERNALLY_RESEARCHED` with `validation_status=None` until reviewed, and a
`GovernanceLog` record of the crossing — exactly as `current/kernel-object-model.md`'s own
Security/Intelligence-Airlock compatibility note already records. **`EXTERNAL_CANDIDATE` must not
be created**: it would be a fifth quarantine vocabulary alongside `FINDING_STATUS_PROVISIONAL`,
`RELATIONSHIP_STATUS_PROPOSED`, `DOCUMENT_CONTEXT_CLAIM_STATE_PROPOSED`, and `Claim`'s own adoption
state. **No new persisted schema is authorized for Mission 01.** If a Mission 01 design proposes a
new persisted object, that is the signal to stop and re-examine, not to proceed.

### Not authorized by this record

General-purpose web browsing; arbitrary external URLs; arbitrary external documents; PDF/binary
external ingestion; autonomous or multi-step browsing agents; external tool-calling; an agentic
research loop; autonomous context expansion; re-prompting or a second model call fed from the first
call's own output; automatic promotion of external evidence; any promotion path at all; a reusable
cross-project `ReferenceStandard` library; a Project Code Profile schema; a Code DNA subsystem; a
new Helix engine; a second relationship graph; any new persisted schema; Part 2's Constructive
Boundary Response; or Mission 02.

**This is one approved source for one investigation. It is not blanket web-access authorization.**
A second source, a second jurisdiction, a second investigation, or a follow-on link encountered
inside retrieved material each require their own fresh, explicit Product Owner authorization — the
same discipline `governance/STATUS.md`'s own closing sentence already states for anything drawn
from `specified-unbuilt/`.

### Preserved architectural conclusions (`CLAUDE-AIRLOCK-CODE-DNA-HELIX-CHECK-01`)

The convergence review performed immediately before this authorization reached conclusions Mission
01 must preserve:

- **Spin** remains GO's governed process for testing project-strand convergence (`GO-HELIX-01`).
- **River** remains the one persisted relationship architecture (`Relationship`, MM6). No second
  relationship graph is created, under any name.
- **Helix** remains the governing convergence question and the bounded per-run assessment lens
  (`SpinRun.helix_assessments`, `GO-HELIX-QA-01`). It is **not** reified into a persisted
  structure.
- **No `Code DNA` subsystem.** Code-related relationships are a filtered read of River, not a
  separate graph, engine, database, or governed vocabulary item.
- **No Project Code Profile schema** in Mission 01.
- The existing **single-shot, tool-less** LLM boundary is preserved unchanged — it is what makes
  "sharply bounded consequences" structurally true rather than aspirational: a compromised external
  interpreter cannot chain a second action.

### Airlock and Vestibule remain distinct

Unchanged by this authorization, and load-bearing for it
(`prompt-depository/GO-EXTERNAL-VESTIBULE-01`):

- **Airlock** = the *movement* boundary — what leaves, what returns, whether it is executable,
  whether it carries instructions aimed at the internal agent.
- **Vestibule** = the *admission/authority-status* boundary — whether admitted material has project
  authority.

> "An Airlock response may become vestibule material, but crossing the Airlock does not confer
> project authority or complete admission."

Mission 01 authorizes one Airlock crossing. It authorizes **no** admission. The External Source
Vestibule itself remains a separate, deferred programme.

### Implementation precondition — a stale claim in this document's own preamble

This document's "Relationship to the rest of this governance corpus" paragraph states that
`services/security_policy.py`'s `ACTION_EXTERNAL_AI_REQUEST` is "currently `DECISION_DENY` at both
floor and baseline." That was checked against the real code during
`CLAUDE-AIRLOCK-CODE-DNA-HELIX-CHECK-01` and is **not accurate today**:
`MANDATORY_FLOOR_DEFAULTS[ACTION_EXTERNAL_AI_REQUEST]` is `DECISION_ALLOW`, and `DECISION_DENY`
appears only in `CLASSIFICATION_PROFILE_DECISIONS` for `CLASSIFICATION_RESTRICTED` and
`CLASSIFICATION_HIGHLY_RESTRICTED`. Per `CLAUDE.md`'s precedence rule, for
infrastructure/security behaviour the current tested code on pushed `main` governs and this
document's preamble is the stale record; the original sentence is left unedited above and this note
is the correction.

**Mission 01 must not be designed on the assumption that the security floor denies the outbound
call** — on a standard-classification project it does not. The mission-packet allow-list, the
deterministic citation/provenance integrity check, the quarantine representation, and the STOP
boundary are the actual controls.

### Inbound content is untrusted document content

Retrieved Ontario Building Code text enters the **user** prompt only — never the system prompt,
never `BEHAVIORAL_CONTRACT`. The existing prompt-injection boundary is `services/bhive_parser.py`
(CLAUDE-P27-B), written for uploaded documents; this document's own mapping table records that
inbound handling *composes with* it. That is a recorded design intent, not existing code — Mission
01 must actually apply it rather than assume it.
