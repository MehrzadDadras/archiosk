# CLAUDE-AIRLOCK-WEB-RESEARCH-AUTH-01 — Record Product Owner Authorization for Composer Trusted Web Research (Airlock Mission 03, Slice 1)

| Field | Value |
|---|---|
| Prompt ID | CLAUDE-AIRLOCK-WEB-RESEARCH-AUTH-01 |
| Title | Record Product Owner Authorization for Composer Trusted Web Research (Airlock Mission 03, Slice 1) |
| Agent | Claude |
| Status | RUN |
| Purpose | Record the Product Owner's explicit, bounded authorization of Composer-initiated public-web research as the next Airlock proving mission — superseding the blanket `NOT AUTHORIZED` status only to the extent this slice requires — and name every clause it supersedes rather than silently overwriting them. |
| Product Owner acceptance | **Approved as written, 2026-08-24** — "Approved as written. Proceed. I accept CLAUDE-AIRLOCK-WEB-RESEARCH-AUTH-01 and the framing." The framing was accepted verbatim: *"Trusted" governs provenance and process, never content. A trusted interface to untrusted sources. Nothing becomes trustworthy by having been retrieved.* Slice 1 implemented under `CLAUDE-AIRLOCK-WEB-RESEARCH-01`. |
| Lineage | Successor to [`CLAUDE-AIRLOCK-AUTH-01`](CLAUDE-AIRLOCK-AUTH-01.md) (Mission 01), [`CLAUDE-AIRLOCK-M01A-AUTH`](CLAUDE-AIRLOCK-M01A-AUTH.md), and [`CLAUDE-AIRLOCK-M02-AUTH`](CLAUDE-AIRLOCK-M02-AUTH.md) / [`CLAUDE-AIRLOCK-M02-HOLD`](CLAUDE-AIRLOCK-M02-HOLD.md). Extends, and does not replace, [External Intelligence Airlock](../specified-unbuilt/external-intelligence-airlock.md). Related, not absorbed: [GO-EXTERNAL-VESTIBULE-01](GO-EXTERNAL-VESTIBULE-01.md), [GO-COMPOSER-01](GO-COMPOSER-01.md), [GO-TRUST-SECURITY-01](GO-TRUST-SECURITY-01.md). |
| Superseded by | None |
| Absorbed into | None |

## Exact prompt text

<!-- Preserve verbatim. Do not summarize, normalize, or insert run results here. -->

```text
# CLAUDE-AIRLOCK-WEB-RESEARCH-AUTH-01 — Composer Trusted Web Research, Slice 1

## Product Owner Authorization

I explicitly authorize implementation of:

> **External Intelligence Airlock — Mission 03, Slice 1: Composer Trusted Web Research**

This authorization supersedes the current `NOT AUTHORIZED` implementation status
**only to the extent this slice requires**, and only for the scope named below.

## Purpose

Prove whether GO can act as a trusted public-web research interface inside the
existing Composer — deciding for itself which information domain a question
belongs to — while preserving ARCHIOSK's evidence and authority boundaries.

"Trusted" governs PROVENANCE AND PROCESS, never content. This is a trusted
interface to untrusted sources. No retrieved material becomes trustworthy by
having been retrieved.

## What is authorized

1. **Automatic domain routing.** GO determines whether a question belongs to
   project evidence, ARCHIOSK/application knowledge, public-web knowledge, or a
   combination, and retrieves accordingly. The user does not select a "web
   mode". Routing is carried by a new `INTENT_CLASS_EXTERNAL_RESEARCH` entry in
   the EXISTING closed intent table (`services/conversational_turn.py`),
   classified SAFE because it is read-only.

2. **Allow-listed retrieval only.** Retrieval is restricted to an explicit
   allow-list of authoritative/primary domains, reusing and generalizing
   Mission 01's own `_validate_route` from a single pinned URL to that list.
   HTTPS only, no redirects, size-capped, content-type checked.

3. **Untrusted-input screening** on returned content BEFORE it reaches any
   prompt, and an explicit contract statement that retrieved text is data and
   never instruction.

4. **One single-shot synthesis call** through the existing
   `services/llm_gateway.py` `call_llm_json()` boundary, answering only from
   retrieved text, citing every claim or dropping it.

5. **Visible domain state.** The user can always tell whether GO is reasoning
   from project material, explaining ARCHIOSK, searching the public web, or
   combining project and external research. Reuses the existing activity
   indicator rather than introducing a second one.

6. **Mixed answers.** An answer may synthesize across project evidence and
   external reference, provided the two remain distinguishable in provenance
   and presentation and are never collapsed into one authority class.

## What is NOT authorized by this record

- The External Intelligence Airlock as an unrestricted general capability.
- Arbitrary open-web browsing beyond the allow-list.
- A search-provider API, or any second required cloud dependency.
- External tool-calling, agentic or multi-step browsing, or a second model call
  fed from the first call's own output.
- PDF/binary external ingestion.
- Any promotion path from external reference into the project record — see the
  STOP boundary below.
- Part 2 Constructive Boundary Response, or any Mission beyond this slice.

## The STOP boundary

Slice 1 ends when a cited external answer has been shown to the user.

Nothing retrieved is persisted. No `Source`, no `EvidenceItem`, no `Finding`,
no adjudication, no `GovernanceLog` promotion record. External material is
session-only, which makes "external material must not silently become project
evidence" true BY CONSTRUCTION rather than by discipline.

The Finding-may-reference-external-material behaviour, and the deliberate
governed action that imports external material into the project record, are
**Slice 2** and are not authorized by this record. They become authorizable
once retrieval, citation integrity and injection containment are shown to work
against real sources — the same sequencing Mission 01 used, and for the same
reason: promoting anything before that would build on unverified authority.

## Clauses this record supersedes, named explicitly

From `governance/specified-unbuilt/external-intelligence-airlock.md`:

1. "Mission 03 and beyond are not authorized." — superseded for this slice only.
2. "General-purpose web browsing; arbitrary external URLs" in Mission 01's "Not
   authorized by this record" list — superseded ONLY to the extent of the
   allow-listed domains named above. Arbitrary URLs remain unauthorized.
3. "autonomous context expansion" — superseded only insofar as GO may decide,
   from the user's own question, that public-web retrieval is the appropriate
   domain. It gains no authority to expand scope beyond the question asked, and
   no second retrieval fed from a first result.

Mission 01's STOP boundary, its "no new persisted schema" constraint, and its
quarantine-representation rule are NOT superseded — Slice 1 persists nothing at
all, so they are honoured trivially.

## Reconciliation required before implementation

- `governance/STATUS.md` — add the authorization row; the table governs.
- `governance/current/contracts/CIC-GO-CONVERSATION` — its APPLIES WHEN is
  triggered ("a model-backed route changes"). Its KNOWN LIMITATIONS entry
  "Deterministic gateway orientation remains intentionally non-model-backed" is
  ALREADY STALE, having been overtaken by CLAUDE-GO-GATEWAY-COGNITION-01/02;
  correct it in the same version rather than leaving a record that contradicts
  shipped behaviour.
- `services/question_scope.py` — its declared status
  `ADVISORY_NON_AUTHORIZING_NOT_ROUTING` is to be PRESERVED, not amended.
  EXTERNAL is a refinement of the existing `UNKNOWN` classification and remains
  advisory; routing is carried by the intent table, which is already an
  authorized router. If an implementation proposes making question_scope a
  router, that is the signal to stop and re-examine.

## Proving set

The Product Owner must be able to test, on phone and desktop through the same
Composer:

1. an ordinary general question;
2. an explicit current-web question;
3. a project-only question;
4. a mixed project + web question;
5. visible web-search state;
6. external source citations;
7. clear separation between external and project sources;
8. prompt-injection / untrusted-content containment;
9. no silent external-to-project promotion;
10. natural behaviour on both surfaces.

## Constraints of method

Bounded lanes during design convergence. Lane E at the deployment gate, since
this changes an authority boundary and is therefore high-risk by the Product
Owner's own cadence directive.

Report what was retrieved, what was refused, and what was NOT built, as
importantly as what was.
```

## Notes

- Filed as `DRAFT` when written; **approved as written by the Product Owner on
  2026-08-24** and implemented as Slice 1 the same day.
- The Prompt ID names the mission, not a title, so it stays stable if the
  title changes.
- `dependency_fit.py` returns PASS for a search-provider API. That PASS is
  **unearned** — the tool matches keywords and cannot see that a search API
  would be a second REQUIRED cloud dependency against this project's settled
  one-optional-dependency constraint. Slice 1 therefore takes the allow-listed
  route and adds no dependency at all, which is also why it can honour
  "allow-listing over after-the-fact redaction" from the Airlock's own Part 1.
