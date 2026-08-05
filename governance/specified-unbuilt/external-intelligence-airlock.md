# Specified But Unbuilt — External Intelligence Airlock and Constructive Boundary Response

**Status:** Specified, not implemented. Zero code exists for anything in this document. Recorded
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
