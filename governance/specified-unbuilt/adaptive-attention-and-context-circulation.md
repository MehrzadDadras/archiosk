# Adaptive Attention & Context Circulation (recorded CLAUDE-POSTCAMEL-COMM-I1)

**Status: NOT AUTHORIZED.** Recorded as a named future programme per
`CLAUDE-POSTCAMEL-COMM-I1` Part K, which required the programme record to
preserve these concepts without implementing them. This document is a
concept preservation record, not a feasibility study or a design — no
repository-grounded investigation of these concepts has been performed.
No code, route, template, or domain object may be built from this record
without a fresh, explicit authorization naming this file.

## What this names

A future model for how ARCHIOSK might manage attention and context across
many concurrent or historical Investigations, rather than treating every
open Investigation/Requirement/Finding as equally salient at all times:

- **Hierarchy / change velocity** — some governed objects change fast and
  need frequent attention (an active Investigation); others are stable
  and need almost none (a long-settled, Satisfied Requirement). A future
  attention model would let salience reflect that difference rather than
  treating all objects uniformly.
- **Compound-eye passive/active attention** — many simultaneous low-
  resolution "facets" of awareness (passive) versus one or few high-
  resolution focused views (active), by analogy to a compound eye rather
  than a single foveal viewpoint.
- **Attention survival through handoff** — a reviewer's focus/context
  surviving being handed off (to another reviewer, another session, or
  resumed later) rather than being lost when a session ends.
- **Bounded Investigation "beads" connected by intent/evidence/
  dependency** — Investigations as discrete, bounded units strung
  together by real relationships (shared intent, shared evidence, a
  dependency between them), rather than an unbounded, undifferentiated
  pool.
- **Selective context circulation** — relevant context moving to where
  it's needed (a related Investigation, a related Requirement) without
  requiring a reviewer to manually re-gather it each time.
- **Contextual defence against unrelated retrieval** — a mechanism
  preventing irrelevant material from being pulled into a context window
  or answer merely because it exists somewhere in the project.
- **Human authority over significance** — whatever attention/salience
  model exists, a human's own judgment of what matters remains
  authoritative; the mechanism assists, it does not override.

## Why this is not authorized now

No repository evidence has been gathered for how these concepts would map
onto ARCHIOSK's existing primitives (`InvestigationStep`, `Relationship`,
`GovernanceLog`, `Anchor`, the session-scoped `focused_finding` pattern,
or others). Per COMM-I1's own explicit boundary, this remains outside the
current commissioning baseline. A future architecture gate, if pursued,
should start the same way every prior FUTURE-prefixed investigation in
this corpus has: a repository-grounded inventory of what already exists
before proposing anything new.

## Cross-reference

Recorded alongside `trust-exchange-and-security-commissioning.md` (also
COMM-I1) and the existing `voice-conversational-presence.md` and
`presentation-intelligence.md` records, which similarly found that
several of ARCHIOSK's existing primitives already do more of the work
a "new" mechanism would need than is obvious without looking.
