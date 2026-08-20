# Developer Mode /CCN — Contemplated Change Context

Status: ADDITIVE, bounded implementation (2026-08-20)

Developer Mode applies GO reflexively to ARCHIOSK itself. The Composer is its
primary toolbox: selected application objects are conversational context for
inspection, explanation, tracing, comparison, critique and suggestion.
Selection is never authorization to mutate.

`/CCN` is the first native Developer Mode command. It creates or enters a
Contemplated Change Notice context: current ARCHIOSK state is considered
against a contemplated intent before any implementation is authorized. The
active context is session-scoped; its identity and lifecycle are durably
traced through the existing GovernanceLog. Selected objects retain their
existing identity/provenance and are stored as contextual elements with
`KEEP`, `MOVE`, `MODIFY`, `RETIRE`, or `INVESTIGATE` analysis vocabulary (the
first vertical slice currently defaults attached elements to `INVESTIGATE`).

The initial command family is deliberately small: `/CCN`, `/CCN status`,
`/CCN show`, `/CCN compare`, `/CCN finalize`, and `/CCN cancel`. Finalizing a
CCN means ready for review only; it does not authorize implementation. Future
`CN` and `SI` instruments may formalize and authorize bounded changes while
preserving the same construction-native progression.

No CCN context is project evidence, Owner Program content, a finding, a
requirement, or a mutation capability. Developer context is project-filtered
when selected application objects carry project scope, preventing silent
cross-project leakage.
