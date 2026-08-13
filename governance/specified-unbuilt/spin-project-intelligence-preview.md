# Specified But Unbuilt — Spin: Comprehensive Project Intelligence Preview

**Status:** Named, concept-preservation only, following the same pattern already established for
`adaptive-attention-and-context-circulation.md`/`trust-exchange-and-security-commissioning.md`/
`bug-eye-data-room-source-continuity.md`. **NOT AUTHORIZED** for implementation or further design.
Recorded under `CLAUDE-GO-DNA-01` (2026-08) as a required concept-preservation entry alongside that
stage's own implemented result (`current/go-dna-01-composer-result-contract-and-panel-zoning.md`)
— a small correction ("Overview is a likely primitive ancestor of the first Spin result, do not
delete it") with a large directional consequence for how a future comprehensive-review capability
should be scoped, named here so a future session does not rebuild machinery GO already has in
rough form, and does not invent a name/shape for this concept from scratch.

## What "Spin" names

A future capability distinct from, and preceding, ordinary focused conversational Composer
turns: a **comprehensive** machine review of a project's evidence, producing a structured,
persisted set of findings — the "first Spin result" — as opposed to the narrower, question-driven
`ComposerFinding` emission `current/go-dna-01-composer-result-contract-and-panel-zoning.md`
already implements (one or a few findings, produced only in response to a specific reviewer
question, never a sweep of the whole project).

**The governing distinction, recorded verbatim from the Product Owner's own framing:**

> Comprehensive Spin precedes focused conversation. Historical Spin finding sets are preserved
> rather than overwritten. Spin discovers → Pass adjudicates → Build incorporates.

None of this is built. `ComposerFinding` (implemented) does not overwrite anything — each turn's
findings are simply appended to `workspace.composer_findings` — but there is no concept of a
"Spin run" as a distinct, dated, comprehensive event; no run-level grouping; no comparison between
one Spin's finding set and a later one; no `Pass` (adjudication) or `Build` (incorporation) stage
of any kind.

## What already exists and should be reused, not duplicated (see the full audit in
`current/go-dna-01-composer-result-contract-and-panel-zoning.md`'s own §3/§6)

- `services/project_briefing.py`'s `generate_project_briefing` — the real, existing, one-shot,
  whole-document narrative synthesis (`matters_requiring_attention` etc.), already the closest
  primitive ancestor. **Do not delete or bypass it when Spin is eventually designed** — inspect
  whether it becomes Spin's own generation step, or whether Spin generalizes past it.
- `services.case_workspace.ComposerFinding`/`add_composer_finding` — the structured-finding shape
  and the Toolbox projection seam a comprehensive Spin result would also need; a Spin-produced
  finding should very likely be the SAME object, distinguished by provenance (which turn/run
  produced it), not a second finding type.
- `REQUIREMENT_ADJUDICATION_OUTCOMES`/`ReviewerValidation`/`Disposition` — the existing closed
  human-adjudication vocabularies "Pass" would almost certainly reuse rather than reinvent.
- `WorkProduct`'s draft→review→approve→issue lifecycle — the closest existing precedent for a
  "Build incorporates" step, if that step turns out to mean producing a governed deliverable from
  adjudicated Spin findings.

## Why this is GO LATER

- The narrower, question-driven Composer-finding capability (`CLAUDE-GO-RIGHT-PANEL-01`) was
  authorized and built FIRST, deliberately, as "the smallest repository-grounded implementation
  that proves GO intelligence can leave the chat stream and become persistent, visible project
  material" — Spin's own governing prompt explicitly excluded "historical Spin sets, full Pass/
  Build adjudication, Tool Making, custom-focus management, or a major right-panel redesign."
- No run-level grouping, comparison, or "Pass"/"Build" object exists yet to build on top of —
  designing Spin properly requires first deciding whether a "Spin run" is a new object or a
  read-time grouping over existing `ComposerFinding.created_at`/provenance, which has not been
  investigated.
- `Overview`'s own relationship to a future Spin result (full replacement? a rendering surface for
  Spin's output? left as-is with Spin appearing only in the Toolbox?) is explicitly unresolved —
  named as the open question a future authorization must answer, not answered here.

## Deliberately not investigated by this record

Whether a "Spin run" needs a new domain object at all, how historical Spin sets would be compared
(a diff view? a timeline?), what "Pass" adjudication states would be beyond reusing
`REQUIREMENT_ADJUDICATION_OUTCOMES`, what "Build" incorporation concretely produces, Tool Making
of any kind, and custom-focus/discipline selectors. Each requires its own repository-grounded
investigation before authorization, following the same discipline `CLAUDE-GO-RIGHT-PANEL-01`'s own
audit-first requirement already established for adjacent work.
