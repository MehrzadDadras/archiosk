# CIC-DEVELOPER-MODE — Developer Mode Contract

- **CONTRACT ID:** CIC-DEVELOPER-MODE
- **TITLE:** Developer Mode Contract
- **VERSION:** v1.0
- **STATUS:** CURRENT
- **SCOPE:** ARCHIOSK self-inspection, Developer Composer, UI Reveal, and application context.
- **APPLIES WHEN:** Developer Mode or application-level Developer context is touched.
- **DOES NOT APPLY WHEN:** Ordinary project use has no Developer Mode state.
- **MANDATORY INVARIANTS:** Developer Mode is admin/session governed; ARCHIOSK is inspectable context; Composer is the primary toolbox; selection is context, not authorization; Developer Mode is visually identifiable; UI Reveal is distinct from Developer Mode; application scope never fabricates a project binding.
- **OPTIONAL / CONTEXTUAL REQUIREMENTS:** UI Reveal may expose allow-listed Template-Worthy identity only when explicitly enabled.
- **REFERENCE IMPLEMENTATIONS:** `routes/portal.py`; `services/developer_ccn.py`; `services/template_identity.py`; TPL-001.
- **REFERENCE TESTS:** `tests/test_developer_mode_ccn_01.py`, `tests/test_developer_ui_reveal_workbench_history_01.py`.
- **KNOWN LIMITATIONS:** Direct visual selection/highlighting remains future work; application chat is session-scoped.
- **SUPERSEDES:** None.
- **SUPERSEDED BY:** None.
- **LAST REVIEWED:** 2026-08-20.
- **GOVERNANCE SOURCE:** `governance/current/developer-mode-ccn.md`; Page/Surface Template Inventory.
