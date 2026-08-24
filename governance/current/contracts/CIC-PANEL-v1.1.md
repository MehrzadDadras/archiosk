# CIC-PANEL — Panel / Nested Template Contract

- **CONTRACT ID:** CIC-PANEL
- **TITLE:** Panel and Nested Page Template Contract
- **VERSION:** v1.1
- **STATUS:** CURRENT
- **SCOPE:** Governed page composition, panel state, reusable nested templates, and the primary mobile workspace frame.
- **APPLIES WHEN:** A page layout, panel, dock, nested surface, panel visibility/restoration behavior, or the relationship between the active work surface and the Composer is materially changed.
- **DOES NOT APPLY WHEN:** A fixed content edit has no panel or nested-template effect.
- **MANDATORY INVARIANTS:** A panel defines identity, role, parent page, nested template, default visibility, close/collapse/resize capabilities, restore path, state persistence, focus/keyboard expectations, accessibility, and dependencies. Panel visibility is not data lifecycle; closing never deletes data, ends conversation, cancels CCN, or clears evidence. Menus are the canonical machinery/restoration path where available. **ARCHIOSK is mobile-first for primary operation: the phone frame is a fixed compact context/navigation layer, ONE flexible active work tray, and a persistent bottom Composer, with portrait as the primary operating orientation. A surface may become the active work tray without any change to its semantic authority. Composer is a zone, not a tray — it is never something the reviewer must navigate away from the work to reach. Larger screens progressively reveal more simultaneous workspace using the same primitives; they do not define a separate interaction architecture, and no separate mobile application is created.**
- **OPTIONAL / CONTEXTUAL REQUIREMENTS:** Use a distinct layout ID when arrangements differ; use NPT IDs for reusable functional regions, not tiny controls. Active-tray state is presentation state and persists as a reviewer preference, never as a project record.
- **REFERENCE IMPLEMENTATIONS:** `templates/base.html` launcher/display/right-column/chat shell and tray switcher; `static/js/workspace_trays.js` (the common panel-state API); `static/js/case_workspace.js` (the single `--chat-height` write point); `governance/current/panel-template-system.md`.
- **REFERENCE TESTS:** Workspace panel, Eye/Toolbox, Composer, and layout persistence lanes; `tests/test_mobile_frame_02.py`.
- **KNOWN LIMITATIONS:** Direct visual-selection/highlighting is still absent. Non-workspace pages remain mostly single-panel and do not yet expose panel restoration machinery. Tray geometry is asserted in tests as properties of the CSS rules, not as measured pixels — this repository has no browser-layout harness, so real geometry is established by physical-device review, not by the suite.
- **SUPERSEDES:** CIC-PANEL v1.0.
- **SEMANTIC DELTA FROM v1.0:** Two changes, one of them a reversal of a stated limitation.

  1. **The common panel-state API now exists.** v1.0's KNOWN LIMITATIONS recorded "There is no common panel-state API or direct visual-selection system yet", and `panel-template-system.md`'s own audit summary named the same gap. `static/js/workspace_trays.js` closes the panel-state half of it: one state (`data-tray-focus` on `<html>`) naming which surface owns the work area, applied at every width. It extends rather than replaces the mechanisms that already worked — collapse remains `html.launcher-hidden`/`html.toolbox-hidden`, sizing remains `window.__chatSplitter`'s single `--chat-height` write point, and the Eye/Toolbox maximize controls remain intra-column proportion controls. Direct visual selection/highlighting remains open.

  2. **Mobile-first becomes an invariant, not an absent consideration.** v1.0 was silent on viewport; `pilot-readiness-postcamel-p01.md` recorded "no claim of mobile/narrow-viewport" and nothing in the corpus claimed otherwise. The Product Owner's direction — the phone is the primary ARCHIOSK access surface — makes the three-zone frame governing, and makes desktop the progressive expansion of it rather than its definition.

  No v1.0 invariant is weakened. Panel visibility is still not data lifecycle; the new active-tray state is explicitly presentation state and cannot reach a route.
- **SUPERSEDED BY:** None.
- **ACCEPTANCE STATUS:** The **principle** above is governing on entry. The **visual treatment** that expresses it (switcher placement, the grabber, drawer styling, rest positions) is recorded as implemented-but-not-yet-accepted, pending Product Owner physical-device review on iPhone — the same posture `CLAUDE.md` already applies to the Bauhaus/Constructivist experiment. Do not cite the specific visual details as settled until that acceptance is recorded.
- **LAST REVIEWED:** 2026-08-23.
- **GOVERNANCE SOURCE:** Page/Surface Template Inventory, panel-template-system.md, and the Product Owner's mobile-first workspace direction (CLAUDE-MOBILE-FRAME-02).
