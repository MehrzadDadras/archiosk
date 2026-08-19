# CLAUDE-AIRLOCK-AUTH-01 — Record Product Owner Authorization for Mission 01

| Field | Value |
|---|---|
| Prompt ID | CLAUDE-AIRLOCK-AUTH-01 |
| Title | Record Product Owner Authorization for Mission 01 |
| Agent | Claude |
| Status | RUN |
| Purpose | Record the Product Owner's explicit, bounded authorization of External Intelligence Airlock Mission 01 in governance — superseding the blanket `NOT AUTHORIZED` status only to the extent Mission 01 requires — without implementing the Airlock. |
| Product Owner acceptance | Explicitly authorized by the Product Owner, 2026-08-19. Governance recorded, validated, committed, and pushed as `7318564c601803712f5daf31155094fece0919d3`. |
| Lineage | Issued directly after the repository-grounded architectural convergence review conducted under the Product Owner's `CLAUDE-AIRLOCK-CODE-DNA-HELIX-CHECK-01` prompt, whose conclusions this authorization preserves; that review prompt is not itself registered under this contract at preservation time. Related, not absorbed: [External Intelligence Airlock](../specified-unbuilt/external-intelligence-airlock.md), [GO-EXTERNAL-VESTIBULE-01](GO-EXTERNAL-VESTIBULE-01.md), [GO-HELIX-01](GO-HELIX-01.md), [GO-HELIX-QA-01](GO-HELIX-QA-01.md), [GO-RIVER-01](GO-RIVER-01.md), [GO-TRUST-SECURITY-01](GO-TRUST-SECURITY-01.md). |
| Superseded by | None |
| Absorbed into | None |

## Exact prompt text

<!-- Preserve verbatim. Do not summarize, normalize, or insert run results here. -->

```text
# CLAUDE-AIRLOCK-AUTH-01 — Record Product Owner Authorization for Mission 01

## Product Owner Authorization

I explicitly authorize implementation of:

> **External Intelligence Airlock — Mission 01**

for the bounded SRPC / Ontario Building Code research experiment described below.

This authorization supersedes the current `NOT AUTHORIZED` implementation status **only to the extent necessary for Mission 01**.

Do not interpret this as authorization for:

* general-purpose web browsing;
* arbitrary external URLs;
* arbitrary external documents;
* PDF/binary external ingestion;
* autonomous multi-step browsing agents;
* external tool-calling;
* automatic promotion of external evidence;
* a reusable cross-project ReferenceStandard library;
* a Project Code Profile schema;
* a Code DNA subsystem;
* a new Helix engine;
* a new relationship graph;
* or Mission 02.

## Mission 01 Authorized Scope

The authorized mission is:

> Retrieve authoritative Ontario Building Code material from a narrowly approved official Ontario source for the SRPC B1 smoke-management investigation, pass it through the governed Airlock boundary, verify its citation/provenance deterministically, retain it as externally researched and unvalidated evidence, and STOP before any promotion or project-authority transition.

## Governing Architectural Conclusions

Preserve the conclusions from `CLAUDE-AIRLOCK-CODE-DNA-HELIX-CHECK-01`:

* Spin remains GO's governed process for testing project-strand convergence.
* River remains the one persisted relationship architecture.
* Helix remains the governing convergence question / per-run assessment lens.
* Do not reify Helix into a second graph.
* Do not create a `Code DNA` subsystem.
* Do not create `EXTERNAL_CANDIDATE`.
* Do not create new persisted schema for Mission 01.
* Reuse `evidence_class=externally_researched_evidence` with `validation_status=None` for quarantined external material.
* Preserve the existing single-shot, tool-less LLM boundary.
* No agentic research loop.
* No autonomous context expansion.
* No promotion path in Mission 01.

## Governance Task

1. Locate the existing authoritative Airlock governance record.
2. Update the existing `governance/STATUS.md` Airlock row to record the Product Owner's bounded Mission 01 authorization.
3. Extend the existing Airlock governance record only as needed to record:

   * the bounded authorization;
   * Mission 01 scope;
   * STOP boundary;
   * the fact that broader Airlock functionality remains unauthorized/deferred.
4. Do not create a new competing governance file.
5. Preserve the existing distinction:

   * **Airlock = movement boundary**
   * **Vestibule = admission/authority-status boundary**

## Validation

Show me:

* exact governance files changed;
* old status;
* new bounded status;
* wording used to prevent Mission 01 authorization from becoming blanket web-access authorization;
* `git diff --check`;
* focused governance validation.

## Commit

If governance validation is clean, create and push a **governance-only authorization commit**.

Do not include any implementation code.

Do not alter `CONTINUATION_CHECKPOINT.md`.

Report:

* commit SHA;
* HEAD;
* origin/main;
* synchronization state;
* working-tree state.

# STOP

STOP after the governance authorization is committed and pushed.

Do not implement the Airlock.

Return to the Product Owner.

This prompt constitutes the Product Owner's explicit authorization for **Mission 01 only**.
```

## Execution references

- Run: Claude governance-only authorization pass, 2026-08-19; 35/35 focused governance checks passed, `git diff --check` clean, 62 passed across `tests/test_external_ai_governance.py`, `tests/test_security_assurance.py`, `tests/test_security_governance.py`, `tests/test_security_enforcement.py`
- Result: `governance/STATUS.md` (Airlock prose pointer rewritten from blanket `NOT AUTHORIZED` to a bounded Mission 01 status; new `AUTHORIZED, bounded — Mission 01 only` authorization-table row) and `governance/specified-unbuilt/external-intelligence-airlock.md` (header status amended; `## Product Owner authorization — External Intelligence Airlock Mission 01` section appended, superseding the original `Authorization status` paragraph in place rather than rewriting it)
- Commit: `7318564c601803712f5daf31155094fece0919d3`
