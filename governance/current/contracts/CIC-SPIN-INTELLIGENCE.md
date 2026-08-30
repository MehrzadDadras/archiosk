# CIC-SPIN-INTELLIGENCE — Spin Intelligence Contract

- **CONTRACT ID:** CIC-SPIN-INTELLIGENCE
- **TITLE:** Spin Intelligence Contract
- **VERSION:** v1.0
- **STATUS:** SUPERSEDED
- **SCOPE:** Spin evidence selection, assembly, model invocation, findings, and provenance.
- **APPLIES WHEN:** Project/document Spin, evidence-to-model plumbing, prompts, findings, or run history is touched.
- **DOES NOT APPLY WHEN:** A purely presentational Spin timestamp/history change does not alter analytical behavior.
- **MANDATORY INVARIANTS:** Spin is genuinely model-backed; governed project evidence reaches the model; source scope and baseline/current provenance are truthful; no Teacher/Oracle leakage; no PSD/smoke-specific production steering; no model-memory authority; truncation and selection are known/testable; findings are grounded in supplied evidence.
- **OPTIONAL / CONTEXTUAL REQUIREMENTS:** Add dry-run/model-boundary diagnostics without persisting sensitive payloads.
- **REFERENCE IMPLEMENTATIONS:** `services/spin.py`, `services/llm_gateway.py`, `services/ingestion.py`, evidence registration paths.
- **REFERENCE TESTS:** Spin, evidence-readability, and source-scope lanes.
- **KNOWN LIMITATIONS:** External authority remains governed by the Airlock; no hidden Oracle is project evidence.
- **SUPERSEDES:** None.
- **SUPERSEDED BY:** [CIC-SPIN-INTELLIGENCE v1.1](CIC-SPIN-INTELLIGENCE-v1.1.md).
- **LAST REVIEWED:** 2026-08-20.
- **GOVERNANCE SOURCE:** Spin governance, Airlock governance, and MM evidence contract.
