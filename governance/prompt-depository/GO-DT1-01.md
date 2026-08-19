# GO-DT1-01 — DT1 — Terminal Eye / Engineering Observatory

| Field | Value |
|---|---|
| Prompt ID | GO-DT1-01 |
| Title | DT1 — Terminal Eye / Engineering Observatory |
| Agent | Unassigned (admin/development observability programme) |
| Status | DEFERRED |
| Purpose | Preserve the future admin-only, predominantly read-only Engineering Observatory concept without turning the normal PM workspace into a developer console or implying terminal execution authority. |
| Product Owner acceptance | Confirmed programme direction; repository governance records `CLAUDE-FUTURE-DT1-A1` as GO LATER, unimplemented, and not authorized for implementation. |
| Lineage | Dedicated DT1 programme anchor. The original `CLAUDE-FUTURE-DT1-A1` conclusion is referenced by [Governed Voice / Conversational Presence](../specified-unbuilt/voice-conversational-presence.md), [Presentation Intelligence](../specified-unbuilt/presentation-intelligence.md), and [Programme Status](../STATUS.md), but no standalone authoritative DT1 document was found. Related, not equivalent: the bounded admin-only Operations/telemetry precedent and the [External Intelligence Airlock](../specified-unbuilt/external-intelligence-airlock.md). |
| Superseded by | None |
| Absorbed into | None |

## Confirmed interaction direction

- DT1 is admin-only.
- It is associated historically with the Toolbox and Eye concepts.
- It may expose deeper technical and system state.
- It remains visually and functionally subordinate to normal project work.
- It supports inspection, diagnosis, and engineering verification.
- It does not become the everyday PM interface.

## Historical UI ideas

The known design exploration included a three-dots trigger, a Terminal Eye in the lower Toolbox region, a flexible divider, an enlargable or full-screen Observatory area, and a Chat/Composer region that could shrink as the Observatory expanded. Image paste and inspection support was also discussed, together with strong admin gating.

These are preserved as historical ideas, not final UI requirements. Current governance identifies unresolved naming collisions between the existing multimodal **Eye** and future **Terminal Eye**, and between **Terminal Eye** and the future **Operational Terminal**. A later authorized design pass must resolve those collisions and reassess geometry against the implemented admin Operations-page and Instrument Rail direction.

## Engineering Observatory role

The normal user surface remains concise project work. The Engineering Observatory is a deeper technical inspection surface available only when authorized.

It may expose system state, diagnostics, governed traces and provenance, service or tool status, test and deployment evidence, governed AI or tool interactions, and technical failure information. It must not expose secrets, credentials, tenant-confidential material, or unrestricted internal reasoning.

## Investigative transparency

DT1 relates to, but remains broader and more technical than, the PM-facing principle that project investigations should be inspectable on demand through a concise “show investigation,” “why,” or provenance trace. Do not collapse these surfaces or expose private chain-of-thought.

## Security and Airlock relationship

External AI or tool requests and sensitive technical actions remain governed by existing authorization and security boundaries. The [External Intelligence Airlock](../specified-unbuilt/external-intelligence-airlock.md), admin authorization, security policy, and diagnostic controls remain authoritative where applicable. DT1 does not weaken or create a bypass around them.

The existing admin-only Operations page and `services/diagnostics.py` prove a bounded peripheral home for structurally safe telemetry. They do not implement DT1: repository/git diagnostics, orchestration detail, and terminal integration were explicitly excluded from that tranche.

## Read-only bias

DT1 should begin predominantly read-only and inspection-oriented unless a later explicitly governed prompt authorizes operational controls. The word “Terminal” does not confer shell, subprocess, mutation, or infrastructure authority.

## Recovery status

**RECOVERY PENDING:**

- original `DT1` prompt;
- exact `DT1-A1` prompt and scope;
- original Terminal Eye wording;
- exact Engineering Observatory architecture;
- Toolbox and Eye geometry;
- image-paste interaction details;
- exact Airlock relationship wording;
- historical acceptance reports;
- exact admin-security route design;
- original diagrams or mockups.

Do not reconstruct these from guesses. Recovered historical material may enrich this record while preserving source wording, programme lineage, authority, and later evolution.

## Exact prompt text

```text
DT1 is an admin/development observatory surface intended to let authorized users inspect ARCHIOSK/GO's engineering, diagnostics, state, and governed system behaviour without turning the normal PM experience into a developer console.
```

## Execution references

- Run: `CLAUDE-FUTURE-DT1-A1` architecture investigation referenced by existing governance; exact run record recovery-pending
- Result: GO LATER / unimplemented; related bounded admin telemetry exists but is not DT1
- Commit: Exact historical commit lineage recovery-pending
