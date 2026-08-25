# CIC-GO-CONVERSATION — GO Conversation Contract

- **CONTRACT ID:** CIC-GO-CONVERSATION
- **TITLE:** GO Conversation Contract
- **VERSION:** v1.1
- **STATUS:** CURRENT
- **SCOPE:** Conversational intent, model routing, history, context, and response salience.
- **APPLIES WHEN:** A user message, GO answer, context resolver, or model-backed route changes.
- **DOES NOT APPLY WHEN:** A deliberately deterministic navigation/form response is clearly identified as such.
- **MANDATORY INVARIANTS:** Respond to current intent first; context informs rather than dominates; greetings remain natural; active CCN is silent unless relevant; clear named concepts need no ritual selection; ambiguity is clarified conversationally; multi-turn referents persist; canned fallbacks never swallow clear questions; ordinary intelligence reaches the canonical model path.
- **OPTIONAL / CONTEXTUAL REQUIREMENTS:** Add selected, project, document, or application context only when scope is established and relevant.
- **REFERENCE IMPLEMENTATIONS:** `services/project_qa.py`, `services/llm_gateway.py`, project Composer route, application Developer Composer route.
- **REFERENCE TESTS:** `tests/test_project_qa.py`, `tests/test_developer_home_composer_01.py`, model-seam conversation lanes.
- **KNOWN LIMITATIONS:** External research is bounded to an allow-list of authoritative sources (Airlock Mission 03 Slice 1) and cannot answer general-knowledge questions outside it; it refuses in words rather than answering thinly. External material is session-only — there is no promotion path into the project record, by design, until Slice 2.
- **SUPERSEDES:** CIC-GO-CONVERSATION v1.0.
- **SEMANTIC DELTA FROM v1.0:** Two changes.

  1. **A stale limitation corrected.** v1.0's KNOWN LIMITATIONS read "Deterministic gateway orientation remains intentionally non-model-backed." That stopped being true earlier the same day, under `CLAUDE-GO-GATEWAY-COGNITION-01`/`-02`, which gave the project-less Gateway a real answering seam because a rule-based responder was returning a canned offer to open a project in reply to genuine questions. The record was not updated at the time; it is corrected here rather than left contradicting shipped behaviour.

  2. **A new answering domain.** GO now determines whether a question belongs to project evidence, ARCHIOSK/application knowledge, or public reference material, and retrieves accordingly — without the user selecting a mode. The invariant this adds: **domain and authority travel together.** External material is presented as external reference, never as project evidence, requirement, contractual authority or instruction to GO, and the transition to external retrieval is visible to the user. Retrieved content is data, never instruction — a page cannot alter GO's governing behaviour by being read.

  No v1.0 invariant is weakened. Current intent still comes first, context still informs rather than dominates, ambiguity is still clarified conversationally, and a canned fallback is still the failure it always was.
- **SUPERSEDED BY:** None.
- **LAST REVIEWED:** 2026-08-24.
- **GOVERNANCE SOURCE:** `GO-COMPOSER-01`; Developer Mode/CCN governance; project Q&A implementation.
