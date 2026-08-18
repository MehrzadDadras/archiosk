# CODEX-PROMPT-DEPOSITORY-01B-1 — Verify the Prompt Depository Contract

| Field | Value |
|---|---|
| Prompt ID | CODEX-PROMPT-DEPOSITORY-01B-1 |
| Title | Verify the Prompt Depository Contract |
| Agent | Codex |
| Status | RUN |
| Purpose | Verify the prospective prompt-record contract and resolve its conflict with the earlier repository-level deferral. |
| Product Owner acceptance | Accepted by CODEX-PROMPT-DEPOSITORY-01B-2, which directs seeding under the verified contract. |
| Lineage | Continuation of CODEX-PROMPT-DEPOSITORY-01A-1 and its authorized depository-creation follow-ups. |
| Superseded by | None |
| Absorbed into | None |

## Exact prompt text

```text
Inspect the newly created:

`governance/prompt-depository/PROMPT_REGISTER.md`

and verify that the prompt-depository contract is complete and internally consistent.

Confirm it supports:

* stable permanent Prompt ID,
* title,
* intended agent,
* status,
* purpose,
* Product Owner acceptance state,
* lineage,
* exact verbatim prompt text,
* run/result/commit references,
* superseded-by / absorbed-into relationships.

Also verify that the current Product Owner authorization for prompt preservation is not left ambiguous against the older `CLAUDE.md` language that previously deferred prompt IDs/acceptance records.

Do not migrate any historical prompts yet.

Do not redesign the structure unless a genuine gap is found.

Report:

1. whether the record contract is complete,
2. any gap corrected,
3. how the old `CLAUDE.md` conflict is safely resolved or referenced,
4. validation performed.

Then STOP.
```

## Execution references

- Run: Current Codex prompt-depository sequence; no durable run identifier available
- Result: `governance/prompt-depository/PROMPT_REGISTER.md`; `CLAUDE.md`
- Commit: None
