# ARCHIOSK / GO Prompt Register

**Status:** Governed prospective register. This depository records future prompts and their lineage; it does not retroactively import historical prompts.

## Authority and scope

This directory is the authoritative repository location for preserved ARCHIOSK/GO prompt records. A record becomes durable project truth only when committed and pushed in accordance with `CLAUDE.md`.

Prompt records preserve Product Owner intent and execution provenance. They do not replace constitutional invariants, programme authorization in `governance/STATUS.md`, tested application behavior, or commit history.

## Preservation rules

1. A Prompt ID is permanent. Never renumber, reuse, or silently change it.
2. Preserve exact prompt text verbatim. Corrections or later direction require a new prompt record with explicit lineage.
3. Obsolete prompts remain present. Mark them `SUPERSEDED` or `ABSORBED` and identify the successor; do not delete them.
4. Prompt text and execution results remain separate. A prompt record may cite runs, results, and commits, but must not embed result content as part of the exact prompt text.
5. Use only these statuses: `DRAFT`, `APPROVED`, `RUN`, `DEFERRED`, `SUPERSEDED`, `ABSORBED`.
6. Store each future prompt as one Markdown file directly in this directory, named from its stable Prompt ID. Do not derive identity from a mutable title.
7. Add every prompt record to the register table below. Stable fields and one-record-per-file storage are the interface for a future UI; the Markdown files remain the source of record.

## Register

No broad historical prompt migration has been performed.

| Prompt ID | Title | Agent | Status | Product Owner acceptance | Record |
|---|---|---|---|---|---|
| CODEX-PROMPT-DEPOSITORY-01A-1 | Locate the Authoritative Prompt Depository Home | Codex | RUN | Accepted by subsequent Product Owner continuation | [Record](CODEX-PROMPT-DEPOSITORY-01A-1.md) |
| CODEX-PROMPT-DEPOSITORY-01B-1 | Verify the Prompt Depository Contract | Codex | RUN | Accepted by CODEX-PROMPT-DEPOSITORY-01B-2 | [Record](CODEX-PROMPT-DEPOSITORY-01B-1.md) |

## Prompt record format

Use this exact field set for future records. Use `None` where an optional relationship or reference does not exist; do not omit fields.

````markdown
# <Prompt ID> — <Title>

| Field | Value |
|---|---|
| Prompt ID | <stable identifier> |
| Title | <short descriptive title> |
| Agent | <intended or executing agent> |
| Status | DRAFT / APPROVED / RUN / DEFERRED / SUPERSEDED / ABSORBED |
| Purpose | <bounded intended outcome> |
| Product Owner acceptance | <acceptance state, date, and/or authoritative reference; or None> |
| Lineage | <predecessor, addendum, continuation, or related Prompt IDs; or None> |
| Superseded by | <Prompt ID; or None> |
| Absorbed into | <Prompt ID; or None> |

## Exact prompt text

<!-- Preserve verbatim. Do not summarize, normalize, or insert run results here. -->

```text
<exact prompt text>
```

## Execution references

- Run: <reference or None>
- Result: <reference or None>
- Commit: <hash or None>
````

The outer example fence above is illustrative. In an actual record, use a fenced `text` block for the exact prompt and keep execution references outside that block.
