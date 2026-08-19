# CLAUDE-PSD-FOUNDATION-01 — Establish Synthetic Project Identity and Release Path

| Field | Value |
|---|---|
| Prompt ID | CLAUDE-PSD-FOUNDATION-01 |
| Title | Establish Synthetic Project Identity and Release Path |
| Agent | Claude |
| Status | RUN |
| Purpose | Adopt **Project Smoke Detector (PSD)** as the canonical synthetic ARCHIOSK/GO test-project identity, record the synthetic-identity-without-falsified-provenance principle, restate Mission 02's Condition B against PSD, and report the existing governed project-creation path — without creating PSD or executing Mission 02. |
| Product Owner acceptance | Explicit Product Owner security/liability decision, 2026-08-19: the ARCHIOSK/GO test project used for the Ontario Building Code investigation must no longer carry the real-world project identity. |
| Lineage | Restates Condition B of the execution hold recorded in [CLAUDE-AIRLOCK-M02-HOLD](CLAUDE-AIRLOCK-M02-HOLD.md); records Condition A satisfied by the Mission 01A implementation authorized under [CLAUDE-AIRLOCK-M01A-AUTH](CLAUDE-AIRLOCK-M01A-AUTH.md). Does not alter [CLAUDE-AIRLOCK-M02-AUTH](CLAUDE-AIRLOCK-M02-AUTH.md)'s scope. Related, not absorbed: [External Intelligence Airlock](../specified-unbuilt/external-intelligence-airlock.md). |
| Superseded by | None |
| Absorbed into | None |

## Exact prompt text

<!-- Preserve verbatim. Do not summarize, normalize, or insert run results here. -->

```text
CLAUDE-PSD-FOUNDATION-01 — Establish Synthetic Project Identity and Release Path

The Product Owner has made a deliberate security/liability decision:

The ARCHIOSK/GO test project used for this investigation must no longer carry the real-world project identity.

Adopt:

Canonical synthetic project name:
Project Smoke Detector

Short form:
PSD

This is a synthetic ARCHIOSK/GO test-project identity.

Do NOT rename, alter, sanitize, or falsify original source documents.
Original evidence retains its real provenance.

The separation is:

REAL SOURCE MATERIAL
→ preserved as source evidence with provenance

ARCHIOSK TEST PROJECT IDENTITY
→ Project Smoke Detector (PSD)

==================================================
1. UPDATE THE MISSION 02 HOLD
==================================================

Find the existing authoritative Mission 02 authorization/hold location.

Do not create parallel governance.

Replace the unresolved real-project-context wording with:

Condition B — Project Smoke Detector context must be resolved before Mission 02 execution.

Condition B is satisfied only when:

- Project Smoke Detector exists through the normal ARCHIOSK project-creation mechanism;
- its canonical project ID is known;
- its project/environment identity is confirmed;
- Mission 02 has an explicit evidence destination/context.

Do not treat the prior read-only inspection of instance/registry/ as project creation.

Do not infer that PSD already exists.

==================================================
2. RECORD THE SYNTHETIC-IDENTITY PRINCIPLE
==================================================

Preserve the following principle in the appropriate existing governance/design location:

ARCHIOSK test projects derived from real-world research material may use a deliberately synthetic project identity.

Synthetic project identity must not falsify provenance.

Therefore:

- project display/name identity may be synthetic;
- original source names and provenance remain truthful;
- source evidence must not be silently rewritten as synthetic evidence;
- real owner/client/site/project identifiers should not become canonical test-project identity unless explicitly required;
- mappings between synthetic and real project identities should not be unnecessarily persisted;
- reports/prompts intended as durable ARCHIOSK test artifacts should use the synthetic project identity where the real identity is not necessary for evidence provenance.

Do not create a new governance subsystem.

==================================================
3. DO NOT CREATE PSD YET
==================================================

This prompt is governance and architecture preparation only.

Do not create Project Smoke Detector.

Instead inspect the repository and identify the EXISTING normal project-creation path.

Report:

- model/service responsible for project creation;
- required project fields;
- whether operating environment/type must be selected at creation;
- canonical project ID generation mechanism;
- whether project creation has consequential side effects;
- whether creating PSD can be done through an existing application/service path without new code;
- whether any real-world identity fields would automatically be inherited from source material.

Do not modify project-creation architecture.

==================================================
4. PSD CREATION RECOMMENDATION
==================================================

Recommend the smallest bounded next action for creating:

Project Smoke Detector

through the existing governed project-creation path.

The intended project must be synthetic.

Do not populate real:
- owner/client name;
- site address;
- project number;
- consultant names;
- user contact information;

unless a later test specifically requires one of those as source evidence.

If required fields need values, recommend neutral synthetic values rather than inventing a real-world association.

==================================================
5. MISSION 02
==================================================

Mission 02 remains:

AUTHORIZED BUT ON HOLD.

Do not execute it.

Its Airlock authorization remains intact.

Condition A is now satisfied by committed Mission 01A implementation:

22ec1ff0641c5fb45456982e517b4eebc677e5be

Condition B remains open until PSD is actually created and verified.

==================================================
6. GOVERNANCE PRESERVATION
==================================================

Search for the existing authoritative governance/design/ADR/constitution location before creating any file.

Preserve principles rather than one-off implementation detail.

Surface conflicts instead of silently overwriting them.

Do not promote an experimental observation into durable architecture unless warranted.

==================================================
7. OUTPUT
==================================================

Return:

A. governance locations updated
B. exact PSD synthetic-identity principle recorded
C. revised Condition B
D. existing project-creation path
E. required project fields
F. side effects / governance gates
G. recommended bounded PSD creation action
H. repository changes
I. commit SHA
J. HEAD / origin/main
K. working-tree state

STOP.

Do not create PSD.
Do not execute Mission 02.
Do not retrieve Code material.
```

## Execution references

- Run: Claude governance-only synthetic-identity/foundation pass, 2026-08-19; issued from synchronized `22ec1ff0641c5fb45456982e517b4eebc677e5be`. Included a read-only repository inspection of the existing project-creation path (`services/ingestion.py`'s `ingest_upload`, `routes/portal.py`'s `upload`, `routes/api.py`'s `ingest_document`). PSD was not created; Mission 02 was not executed; no Code material was retrieved; project-creation architecture was not modified.
- Result: `CLAUDE.md` (new "Synthetic test-project identity" section, placed beside the existing "Credentials given in chat" safety rule — no new governance subsystem created); `governance/specified-unbuilt/external-intelligence-airlock.md` (Condition A marked SATISFIED with the verified commit; Condition B replaced with the PSD four-part condition, carrying the explicit "the prior read-only inspection is not project creation" and "PSD must not be inferred to exist" statements; the read-only observation restated against PSD); `governance/STATUS.md` (prose pointer and authorization-table row restate the hold against PSD and record Condition A satisfied)
- Commit: recorded in the same governance-only commit that introduced this file — the commit whose parent is `22ec1ff0641c5fb45456982e517b4eebc677e5be`
