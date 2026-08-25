# CIC-GO-CONVERSATION — GO Conversation Contract

- **CONTRACT ID:** CIC-GO-CONVERSATION
- **TITLE:** GO Conversation Contract
- **VERSION:** v1.0
- **STATUS:** CURRENT
- **SCOPE:** Conversational intent, model routing, history, context, and response salience.
- **APPLIES WHEN:** A user message, GO answer, context resolver, or model-backed route changes.
- **DOES NOT APPLY WHEN:** A deliberately deterministic navigation/form response is clearly identified as such.
- **MANDATORY INVARIANTS:** Respond to current intent first; context informs rather than dominates; greetings remain natural; active CCN is silent unless relevant; clear named concepts need no ritual selection; ambiguity is clarified conversationally; multi-turn referents persist; canned fallbacks never swallow clear questions; ordinary intelligence reaches the canonical model path.
- **OPTIONAL / CONTEXTUAL REQUIREMENTS:** Add selected, project, document, or application context only when scope is established and relevant.
- **REFERENCE IMPLEMENTATIONS:** `services/project_qa.py`, `services/llm_gateway.py`, project Composer route, application Developer Composer route.
- **REFERENCE TESTS:** `tests/test_project_qa.py`, `tests/test_developer_home_composer_01.py`, model-seam conversation lanes.
- **KNOWN LIMITATIONS:** Deterministic gateway orientation remains intentionally non-model-backed.
- **SUPERSEDES:** None.
- **SUPERSEDED BY:** CIC-GO-CONVERSATION v1.1 (`CIC-GO-CONVERSATION-v1.1.md`) — external research became an answering domain, and this record's own KNOWN LIMITATIONS about non-model-backed gateway orientation had already been overtaken by `CLAUDE-GO-GATEWAY-COGNITION-01`/`-02`.
- **LAST REVIEWED:** 2026-08-20.
- **GOVERNANCE SOURCE:** `GO-COMPOSER-01`; Developer Mode/CCN governance; project Q&A implementation.
