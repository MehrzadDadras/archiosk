# CIC-PANEL — Panel / Nested Template Contract

- **CONTRACT ID:** CIC-PANEL
- **TITLE:** Panel and Nested Page Template Contract
- **VERSION:** v1.0
- **STATUS:** CURRENT
- **SCOPE:** Governed page composition, panel state, and reusable nested templates.
- **APPLIES WHEN:** A page layout, panel, dock, nested surface, or panel visibility/restoration behavior is materially changed.
- **DOES NOT APPLY WHEN:** A fixed content edit has no panel or nested-template effect.
- **MANDATORY INVARIANTS:** A panel defines identity, role, parent page, nested template, default visibility, close/collapse/resize capabilities, restore path, state persistence, focus/keyboard expectations, accessibility, and dependencies. Panel visibility is not data lifecycle; closing never deletes data, ends conversation, cancels CCN, or clears evidence. Menus are the canonical machinery/restoration path where available.
- **OPTIONAL / CONTEXTUAL REQUIREMENTS:** Use a distinct layout ID when arrangements differ; use NPT IDs for reusable functional regions, not tiny controls.
- **REFERENCE IMPLEMENTATIONS:** `templates/base.html` launcher/display/right-column/chat shell; `static/js/case_workspace.js`; `governance/current/panel-template-system.md`.
- **REFERENCE TESTS:** Workspace panel, Eye/Toolbox, Composer, and layout persistence lanes.
- **KNOWN LIMITATIONS:** There is no common panel-state API or direct visual-selection system yet; non-workspace pages remain mostly single-panel.
- **SUPERSEDES:** None.
- **SUPERSEDED BY:** None.
- **LAST REVIEWED:** 2026-08-20.
- **GOVERNANCE SOURCE:** Page/Surface Template Inventory and panel-template-system.md.
