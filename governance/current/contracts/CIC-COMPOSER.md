# CIC-COMPOSER — Canonical Composer Contract

- **CONTRACT ID:** CIC-COMPOSER
- **TITLE:** Canonical Composer Contract
- **VERSION:** v1.0
- **STATUS:** CURRENT
- **SCOPE:** All Composer-bearing surfaces and shared input behavior.
- **APPLIES WHEN:** A Composer, input, voice, send, or conversation surface is touched.
- **DOES NOT APPLY WHEN:** A non-conversational form is unrelated to Composer primitives.
- **MANDATORY INVARIANTS:** One primary Composer; multiline input; microphone where the reference supports it; Send; Enter sends; Shift+Enter newline; IME and pending/duplicate protection; accessible controls; canonical submission path; continuity/context; model-backed behavior where intelligence is implied.
- **OPTIONAL / CONTEXTUAL REQUIREMENTS:** Voice may be unavailable where the browser or surface has no authorized audio path; explain the boundary honestly.
- **REFERENCE IMPLEMENTATIONS:** TPL-005 workspace Composer; TPL-001 Developer Home Composer; `templates/_macros.html`; `static/js/developer_composer_input.js`; `static/js/voice_input.js`.
- **REFERENCE TESTS:** `tests/test_developer_home_composer_01.py`, Composer and voice lanes.
- **KNOWN LIMITATIONS:** Home and workspace persistence envelopes remain intentionally distinct.
- **SUPERSEDES:** None.
- **SUPERSEDED BY:** None.
- **LAST REVIEWED:** 2026-08-20.
- **GOVERNANCE SOURCE:** Page/Surface Template Inventory; `GO-COMPOSER-01`; Developer Composer implementation.
