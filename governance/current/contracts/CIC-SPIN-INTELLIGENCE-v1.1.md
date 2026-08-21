# CIC-SPIN-INTELLIGENCE — Spin Intelligence Contract

- **CONTRACT ID:** CIC-SPIN-INTELLIGENCE
- **TITLE:** Spin Intelligence Contract
- **VERSION:** v1.1
- **STATUS:** CURRENT
- **SCOPE:** Spin evidence selection, assembly, model invocation, findings, provenance, and Helix / Progressive Project Convergence assessment.
- **APPLIES WHEN:** Project/document Spin, evidence-to-model plumbing, prompts, findings, run history, or Helix assessment governance is touched.
- **DOES NOT APPLY WHEN:** A purely presentational Spin timestamp/history change does not alter analytical behavior.
- **GOVERNING PRINCIPLE:** A project consists of independently evolving but interdependent consequential strands moving toward delivery; coordination quality is demonstrated by how well those strands progressively mesh at the maturity actually being claimed; Spin is GO's governed process for testing that mesh.
- **MANDATORY INVARIANTS:** Spin is genuinely model-backed; governed project evidence reaches the model; source scope and baseline/current provenance are truthful; no Teacher/Oracle leakage; no PSD/smoke-specific production steering; no model-memory authority; truncation and selection are known/testable; findings are grounded in supplied evidence; strands may progress at different velocities; individual strand maturity alone does not prove coordination; claimed maturity comes from project evidence rather than universal stage assumptions; a mature strand can still fail to mesh with dependent strands; Helix is an investigative/convergence model, not a universal scoring system; Helix must not silently become a coordination percentage, health score, universal LOD/percentage mapping, universal tolerance table, hard-coded trade hierarchy, project-wide uniform-maturity assumption, or automatic engineering/design correction mechanism; expectation, observation, consequence, and evidence sufficiency remain distinct; non-convergence does not automatically equal noncompliance without evidence and authority context.
- **OPTIONAL / CONTEXTUAL REQUIREMENTS:** Add dry-run/model-boundary diagnostics without persisting sensitive payloads.
- **REFERENCE IMPLEMENTATIONS:** `services/spin.py::_parse_helix_assessments`; `SpinRun.helix_assessments`; `SpinResult.helix_assessments`; `services/llm_gateway.py`; `services/ingestion.py`; evidence registration paths.
- **REFERENCE TESTS:** `tests/test_helix_qa_absorption_01.py`; Spin, evidence-readability, and source-scope lanes.
- **KNOWN LIMITATIONS:** External authority remains governed by the Airlock; no hidden Oracle is project evidence; Helix is not a universal scoring or correction engine.
- **SUPERSEDES:** [CIC-SPIN-INTELLIGENCE v1.0](CIC-SPIN-INTELLIGENCE.md) — adds explicit Helix / Progressive Project Convergence lineage and the already-tested closed-vocabulary / anti-scoring invariant; all v1.0 invariants remain in force.
- **SUPERSEDED BY:** None.
- **LAST REVIEWED:** 2026-08-21 (Helix authority reconciliation maintenance).
- **GOVERNANCE SOURCE:** [GO-HELIX-01](../../prompt-depository/GO-HELIX-01.md); [GO-HELIX-QA-01](../../prompt-depository/GO-HELIX-QA-01.md); Spin governance, Airlock governance, and MM evidence contract.
