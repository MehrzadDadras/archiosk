# CLAUDE-AIRLOCK-M01A-AUTH — Authorize One Deterministic e-Laws Content Route

| Field | Value |
|---|---|
| Prompt ID | CLAUDE-AIRLOCK-M01A-AUTH |
| Title | Authorize One Deterministic e-Laws Content Route |
| Agent | Claude |
| Status | RUN |
| Purpose | Authorize the bounded Mission 01A continuation — exactly one deterministic official Ontario e-Laws content-delivery route for the already-approved regulation, fixed in trusted code and never chosen by the model — after Mission 01 correctly stopped on finding the approved e-Laws URL served only a JavaScript application shell and no regulation text. |
| Product Owner acceptance | Explicitly authorized by the Product Owner, 2026-08-19, as a narrow continuation of the same investigation, regulation, and government authority; expressly not general web-access authorization. |
| Lineage | Direct continuation of [CLAUDE-AIRLOCK-AUTH-01](CLAUDE-AIRLOCK-AUTH-01.md), whose Mission 01 boundaries it preserves unchanged and whose governance record it extends non-destructively; that record was itself preserved under `CLAUDE-AIRLOCK-AUTH-02`. Related, not absorbed: [External Intelligence Airlock](../specified-unbuilt/external-intelligence-airlock.md), [GO-EXTERNAL-VESTIBULE-01](GO-EXTERNAL-VESTIBULE-01.md), [GO-TRUST-SECURITY-01](GO-TRUST-SECURITY-01.md). |
| Superseded by | None |
| Absorbed into | None |

## Exact prompt text

<!-- Preserve verbatim. Do not summarize, normalize, or insert run results here. -->

```text
# CLAUDE-AIRLOCK-M01A-AUTH — Authorize One Deterministic e-Laws Content Route

Begin from synchronized main:

`a1a343e87761fbfd8c76b12a77a490866ed12b64`

Mission 01 stopped correctly because the authorized Ontario e-Laws URL returned only a JavaScript application shell and no regulation text.

No Airlock implementation was retained and no canonical state changed.

## Product Owner authorization

The Product Owner now authorizes **Mission 01A only**:

> determine and use one deterministic official Ontario e-Laws content-delivery route necessary to retrieve the regulation text already represented by the previously approved e-Laws page.

This is a narrow continuation of the same investigation and same government authority.

It is not general web-access authorization.

## Allowed

Mission 01A may authorize exactly one of the following, after repository-grounded inspection identifies the real delivery mechanism:

* a deterministic official `ontario.ca` / Ontario e-Laws route that returns the legislative text;
* a fixed versioned e-Laws regulation route representing the same regulation;
* or a deterministic first-party application-data endpoint used by that official page to deliver its own legislative content.

The route must be identified and fixed by trusted code.

The LLM may not choose it.

## Still prohibited

Do not authorize:

* general web browsing;
* search-engine content as evidence;
* arbitrary URLs;
* arbitrary follow-on links;
* another jurisdiction;
* unofficial mirrors;
* blogs;
* third-party Code sites;
* PDF/binary ingestion;
* browser automation;
* agentic discovery;
* recursive fetching;
* model-selected endpoints;
* multiple alternative sources;
* Mission 02;
* promotion;
* new persisted schema.

## Important distinction

A first-party deterministic content endpoint or versioned route belonging to the same official Ontario e-Laws publication is authorized only as the delivery mechanism for the already-approved authority.

Do not treat this as permission to crawl `ontario.ca`.

## Governance task

Update the existing Airlock authorization non-destructively to record this bounded Mission 01A continuation.

Do not create a new competing Airlock governance file.

Preserve:

* Airlock = movement boundary;
* Vestibule = admission/authority boundary;
* externally researched evidence remains unvalidated;
* zero automatic promotion;
* single-shot tool-less interpretation;
* deterministic citation/provenance verification;
* STOP after one successful real evidence item.

## Validation and commit

Governance only.

Run focused governance validation and `git diff --check`.

Do not touch `CONTINUATION_CHECKPOINT.md`.

Commit and push.

Report:

* files changed;
* exact Mission 01A authorization wording;
* what remains prohibited;
* validation;
* commit SHA;
* HEAD/origin/main;
* sync state.

# STOP

Do not implement Mission 01A.
```

## Execution references

- Run: Claude governance-only Mission 01A authorization pass, 2026-08-19; issued from synchronized `a1a343e87761fbfd8c76b12a77a490866ed12b64`
- Result: `governance/specified-unbuilt/external-intelligence-airlock.md` (header status amended to name the continuation; `### Mission 01A — one deterministic e-Laws content route` subsection appended within the existing Mission 01 authorization section, non-destructively) and `governance/STATUS.md` (Airlock prose pointer and authorization-table row extended to name Mission 01A and its additional prohibitions)
- Commit: recorded in the same governance-only commit that introduced this file — the commit whose parent is `a1a343e87761fbfd8c76b12a77a490866ed12b64`
