# Bug Eye — Data Room Source Continuity (recorded CLAUDE-POSTCAMEL-COMM-I3B)

**Status: NOT AUTHORIZED.** Recorded as a named future programme per
`CLAUDE-POSTCAMEL-COMM-I3B` Section 6, which required the concept
preserved without implementation. This document is a concept
preservation record, not a feasibility study or a design — a bounded
repository-grounded check was performed to confirm the concept doesn't
already exist and isn't already needed (see "Why this is not authorized
now" below), but no design work toward building it was performed. No
code, route, template, or domain object may be built from this record
without a fresh, explicit authorization naming this file.

## What this names

A future watcher over the document territory and governed Source
relationships — not over users — protecting continuity when a Source's
external locator changes:

- **Confident same-document relocation** — a Source that has moved,
  been renamed, or been reorganized, where the match is confident
  enough that the locator may eventually be rerouted automatically
  while preserving the Source's own governed identity.
- **Probable but uncertain match** — requires explicit user
  authorization before any rerouting occurs.
- **Ambiguous match** — never guessed; state is preserved and a human
  is asked, rather than the system silently choosing.
- **Unavailable Source** — identity and every governed relationship
  citing it are preserved; the condition is marked as needing recovery,
  not treated as a deletion.
- **Superseding or revised document** — preserved as a distinct,
  historical Source with an explicit revision/supersession
  relationship, never collapsed into "merely relocated."
- **Destructive action** — never occurs silently; a Source that cannot
  currently be found never causes its governed relationships to be
  deleted automatically.

The governing principle behind all of the above: **a changed location
is not a changed identity; a changed document is not merely a changed
location.** ARCHIOSK should not depend on fragile filenames or physical
paths as the canonical identity of a governed Source wherever durable
identity already exists or can safely support continuity.

## Why this is not authorized now

A bounded, repository-grounded check (not a full design investigation)
was performed before recording this concept, per this repository's own
established practice of confirming a concept doesn't already exist
before naming it as future work:

- **Canonical Source identity is already id-based, not path-based**,
  confirmed directly in code, not merely asserted: the `Source`
  dataclass's own docstring states "canonical identity is this record's
  `id`, not its `file_path` or `name`... A Source retains this identity
  even if later renamed or reorganized," and every lookup path in
  `CaseWorkspaceStore` (`_find`, used uniformly for Source resolution)
  matches on `id`, never on `name` or `file_path` — confirmed by direct
  search, no exception found. Today's product already does not break
  governed relationships merely because a Source's internal storage
  path or display name changes.
- **No external Data Room / file-source connector currently exists** —
  `SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR` is already a named value in
  `KNOWN_SOURCE_ORIGIN_TYPES`, but nothing in this codebase currently
  sets it; every real Source today originates from an ordinary in-app
  upload, capture, or derivative-crop path, each fully controlled by
  ARCHIOSK's own internal, UUID-based storage — not from an externally
  reorganizable location this codebase has to track. The scenario Bug
  Eye anticipates (a document moving *outside* ARCHIOSK's control, in
  an external Data Room or synced folder ARCHIOSK doesn't own) has no
  live integration point to protect yet — this is why Bug Eye is
  correctly a future concept and not a present defect.
- **The architecture already anticipates the eventual need**: the
  `origin_type`/`origin_reference` fields (Prompt 15 #4) already exist
  specifically to record "what kind of place this Source came from,"
  including the not-yet-wired `external_connector` value — a real
  extension point Bug Eye would build on, not a gap requiring new
  schema to even begin.

No repository evidence was found of a current, present-day Source-
continuity defect. This is a forward-looking concept tied to a future
external-connector/Data Room integration (adjacent to, and narrower
than, `FPR-7` — External-source vestibule for incoming data staging —
in the adopted `GEMINI-ARCHIOSK-RFP-02B` Owner baseline), not a
correction to anything built today.

## Not authorized, explicitly, for this or any future stage without a
## fresh authorization naming this file

Filesystem watchers or background daemons of any kind; a relinking UI;
any new hashing scheme; any schema change to `Source` or any other
domain object; automatic locator rerouting; automatic missing-link
repair; any attention-scoring behavior for Bug Eye itself; any
integration with `adaptive-attention-and-context-circulation.md`
(FPR-12).

## Cross-reference

Recorded alongside `adaptive-attention-and-context-circulation.md` and
`trust-exchange-and-security-commissioning.md` (both COMM-I1) — this is
the third future-programme concept named through the commissioning
sequence rather than through a dedicated architecture-investigation
stage. Adjacent to, and should be reconciled against before any future
design work, `FPR-7` (External-source vestibule) in the adopted OPR and
this repository's own existing `Source.origin_type`/`origin_reference`
fields and `supersedes_source_id`/`superseded_by_source_id` revision
mechanism, which already cover the "superseding/revised document" case
in the list above for the ordinary in-app path.
