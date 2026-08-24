# Page-by-Panel Template System

Status: current architectural inventory, version 1.1  
Parent inventory: [`page-surface-template-inventory.md`](page-surface-template-inventory.md)  
Panel contract: [`contracts/CIC-PANEL-v1.1.md`](contracts/CIC-PANEL-v1.1.md)

## Core model

```text
PAGE TEMPLATE
→ PANEL LAYOUT
→ PANEL
→ NESTED PAGE TEMPLATE / SURFACE
```

A page is a governed composition of panels. A nested page template is a
self-contained functional region that can be reused in more than one parent
composition. This is an inventory and classification layer; it does not
authorize a site-wide UI rewrite.

## Initial layout catalogue

Only arrangements evidenced by the current templates or immediately useful
compositions are catalogued.

| Layout ID | Configuration | Current use |
|---|---|---|
| LAY-1 | One primary content panel | Auth, landing, gateway, chooser, upload, admin/specialized pages |
| LAY-2V | Left navigation/context + right/main content | Chooser/list-oriented shells and compact application entry surfaces |
| LAY-2H | Primary content + bottom conversational/dock region | Pages where the chat dock is the only secondary work region |
| LAY-3A | Left navigation + primary work surface + right utility column | Workspace shell when the right column is treated as one utility region |
| LAY-4A | Left navigation + primary work surface + right utility column + bottom chat dock | Workspace shell with chat separated from the right utility region |
| LAY-5A | Left navigation + primary work surface + Eye + Toolbox + bottom chat dock | Full TPL-005 shell; Eye/Toolbox are independently split within the right column |
| LAY-2H-R | Right-column Eye over Toolbox | Nested right-column arrangement in TPL-005; not a whole-page layout |
| LAY-3F | Fixed compact header + ONE active work tray + persistent bottom Composer | The primary mobile frame (CLAUDE-MOBILE-FRAME-02). Not a fourth shell: the same TPL-005 panels, with one of them holding the work area at a time |

`LAY-5A` is the complete current workspace composition. `LAY-2H-R` records the
actual Eye/Toolbox vertical relationship rather than pretending every three-
panel arrangement is identical.

`LAY-3F` is the same composition under a different spatial rule rather than a
different set of panels — which is why it is one layout ID and not a second
shell. `LAY-5A` and `LAY-3F` are two states of one arrangement: LAY-5A when no
tray is active, LAY-3F when one is. Below the phone breakpoint a tray is always
active, so LAY-3F *is* the layout there; above it, either is reachable.

## Nested Page Template catalogue

| NPT ID | Nested template / surface | Reuse and current evidence |
|---|---|---|
| NPT-001 | Application Menu / Shell | Shared `base.html` / `_app_menu.html`; surrounds authenticated pages |
| NPT-002 | Project Navigation / Lists | `base.html` launcher panel; collapsible and width-resizable with menu restoration |
| NPT-003 | Primary Work Surface / Display | Workspace display divisions and document/case surface; not closable |
| NPT-004 | Chat Dock | Workspace `base.html` conversation dock and `_macros.html`; closable/collapsible/resizable/restorable |
| NPT-005 | Eye Panel | `base.html` Eye pane and `eye_pane.js`; independently focused utility surface |
| NPT-006 | Toolbox Panel | `base.html` Toolbox pane and workspace toolbox block; utility surface with restoration path |
| NPT-007 | Spin Surface | `_spin_prototype.html` and run-detail partials inside the primary work surface |
| NPT-008 | Spin History | Compact run rows/details inside Spin; disclosure state, not a separate page shell |
| NPT-009 | Developer Chat Workbench | TPL-001 bounded application Composer; reuses Composer/voice primitives and session chat lifecycle |
| NPT-010 | Project / Environment Chooser | `project_chooser.html` and gateway shell; environment/project selection region |
| NPT-011 | Document Focus | Document tabs, viewer, source context and evidence focus within TPL-005 |
| NPT-012 | Project Administration | Lifecycle/access/archive/reset forms and confirmation patterns |
| NPT-013 | Developer Tools | Protected admin/test reset surface |
| NPT-014 | Gateway Orientation | Deterministic entry/navigation surface; intentionally not model-backed conversation |
| NPT-015 | Publication / Archive Management | Publication and removed-project lifecycle surfaces |
| NPT-016 | Authentication Shell | Login, reset, and verification framing |
| NPT-017 | Project Setup / Upload | Upload, confirmation, and ingestion setup surfaces |
| NPT-018 | Search / Operations / About | Application utility pages with distinct result/status patterns |

### Reuse lineage

- `TPL-001 → LAY-1 → NPT-009` for the bounded application Developer Chat.
- `TPL-005 → LAY-5A → NPT-002 + NPT-003 + NPT-005 + NPT-006 + NPT-004`.
- `NPT-004` is the strongest chat-panel reference for `NPT-009`; application
  scope and session chat persistence are intentional differences.
- `TPL-007 → NPT-007`; `TPL-008` is a nested disclosure within NPT-007 and
  does not create a second chat or page shell.

## Page → Layout → Panel → Nested Template matrix

Panel shorthand: `O` open by default, `C` collapsible, `X` closable, `R`
resizable, `S` restorable through existing menu or route. A dash means the
behavior is not established rather than silently assumed.

| TPL | Page / surface | Layout | Panels (position · role · NPT · default · behavior) | Intentional difference / gap |
|---|---|---|---|---|
| TPL-001 | Home / project selection | LAY-1 | Main · entry/project selection · NPT-014 · O · —; Developer workbench · NPT-009 · O · C/X/S at application scope | Normal Gateway and Developer workbench are distinct modes; no full panel shell on Home |
| TPL-002 | Gateway orientation | LAY-1 | Main · orientation/navigation · NPT-014 · O · — | Deterministic specialized surface |
| TPL-003 | Client / Owner chooser | LAY-2V | Main · chooser · NPT-010 · O · —; context · NPT-001 · O · — | Environment-specific chooser |
| TPL-004 | Design-Builder / Proponent chooser | LAY-2V | Main · chooser · NPT-010 · O · —; context · NPT-001 · O · — | Same chooser pattern with isolation boundary |
| TPL-005 | Project workspace | LAY-5A | Left · project navigation · NPT-002 · O/C · R/S; Center · primary work surface · NPT-003 · O · not closable; Right-top · Eye · NPT-005 · O/C · R/S; Right-bottom · Toolbox · NPT-006 · O/C · R/S; Bottom · Chat Dock · NPT-004 · O/C/X/R/S | Right column uses LAY-2H-R; panel state is separate from data lifecycle |
| TPL-006 | Document workspace / source focus | LAY-5A | Same parent composition as TPL-005; Center uses NPT-011 · O · not closable | Document focus is nested in the primary work surface, not a second workspace |
| TPL-007 | Spin surface | LAY-5A | Same TPL-005 shell; Center nested NPT-007 · O · not closable | Spin is an analytical nested surface |
| TPL-008 | Spin History / run detail | LAY-1 | Main · history disclosure · NPT-008 · O · collapsible rows | Nested in Spin; no independent panel state |
| TPL-009 | Eye panel | LAY-2H-R | Eye · evidence/preview utility · NPT-005 · O/C · R/S where splitter applies | Embedded right-column panel; close clears visibility, not evidence/project state |
| TPL-010 | Toolbox panel | LAY-2H-R | Toolbox · action/inspection utility · NPT-006 · O/C · R/S where splitter applies | Embedded right-column panel; contents remain workspace-specific |
| TPL-011 | Project administration | LAY-1 | Main · lifecycle/access forms · NPT-012 · O · — | Consequential actions remain confirmation/authorization governed |
| TPL-012 | Developer Tools | LAY-1 | Main · protected reset tools · NPT-013 · O · — | Admin-only and not ordinary Toolbox content |
| TPL-013 | Publication / procurement package | LAY-1 | Main · publication workflow · NPT-015 · O · — | Owner/Proponent publication boundary remains authoritative |
| TPL-014 | Archive / removed-project management | LAY-1 | Main · archive/restore list · NPT-015 · O · — | Read-only archived state until restore |
| TPL-015 | Authentication | LAY-1 | Main · auth form · NPT-016 · O · — | Auth shell is a reference only for accessibility/framing |
| TPL-016 | Public landing / explore | LAY-1 | Main · public access/landing · NPT-016 · O · — | Public boundary; no authenticated Developer panels |
| TPL-017 | New project / upload | LAY-1 | Main · setup/upload · NPT-017 · O · — | Deterministic setup helper, not project conversation |
| TPL-018 | Search / operations / about | LAY-1 | Main · utility result/status surface · NPT-018 · O · — | Candidate-specific patterns remain partial |

## Tray state model (CLAUDE-MOBILE-FRAME-02)

The panel states this inventory already recorded — open, collapsible, closable,
resizable, restorable — described what one panel could do to itself. They could
not express which panel currently owns the work area, which is the question a
phone forces. That state is now explicit:

| State | Meaning | Mechanism |
|---|---|---|
| NORMAL | The panel participates in the ordinary composition | LAY-5A; no active-tray state set |
| COLLAPSED | Hidden, identity and restore path preserved | `html.launcher-hidden` / `html.toolbox-hidden`, driven by the panel dividers — unchanged, and deliberately not reimplemented |
| ACTIVE | This surface owns the work area | `data-tray-focus="<key>"` on `<html>` |

Three properties make this governable rather than decorative:

- **One value, structurally.** The state is an attribute, which holds exactly
  one value. "One active work tray" cannot drift the way four independent
  booleans could.
- **Eligible trays are existing NPTs, not new functions.** `lists`=NPT-002,
  `display`=NPT-003, `eye`=NPT-005, `toolbox`=NPT-006. Documents, Spin,
  Findings, Project Context and the photo tray are *contents* of those
  surfaces and remain so; nothing was duplicated to make the frame work.
- **NPT-004 (Chat Dock) is deliberately not eligible.** Composer is a zone,
  not a tray. It is the bottom of the frame at all times, which is what makes
  "work above, talk to GO below" true rather than aspirational — and why a
  future photo flow needs no handoff step to reach it.

Activation is presentation only. It persists as a reviewer preference
(`beehive:tray:focus`, `localStorage`, alongside the existing `beehive:panel:*`
entries), never as a project record, and the module that owns it has no path to
a route at all. A surface that becomes the active tray gains screen area and no
authority whatsoever: selection is still not authorization, and presentation
state is still not project state.

## Panel behavior principles

- Closing hides a panel only. It does not delete data, end a conversation,
  cancel a CCN, remove project context, or clear evidence.
- Restoring uses the existing menu/route machinery where available; panels do
  not grow scattered reopen buttons merely to compensate for missing inventory.
- Primary work surfaces are not closable. Utility panels may be collapsible,
  resizable, and restorable where the current implementation establishes it.
- User visibility preferences are UI state; governed project/chat/evidence
  state remains separate.
- Mobile is the primary operating surface, and portrait its normal posture.
  A larger screen reveals more simultaneous workspace through the same
  primitives; it never becomes a second interaction architecture, and the
  phone is never served by compressing a desktop composition into it.

## Current audit summary

The 18 TPL entries are now classified above. The principal inconsistency is not
the existence of multiple shells; it is that panel state and nested surface
identity are not yet represented uniformly outside TPL-005.

**Updated 2026-08-23 (CLAUDE-MOBILE-FRAME-02):** the common panel-state API
this summary listed as future work now exists — see the tray state model above
and `static/js/workspace_trays.js`. Direct visual selection/highlighting
remains future work, unchanged. The uniformity gap outside TPL-005 also
remains: LAY-3F is reachable from any authenticated page, but the non-workspace
pages it can frame are still mostly single-panel surfaces with no restoration
machinery of their own, so the frame gives them a header and a Composer-less
work area rather than making them fully governed compositions.

## Reference selection

**REFERENCE CANDIDATES REVIEWED:** TPL-005 Project Workspace, TPL-001 Home,
TPL-008 Spin History, TPL-009 Eye, and TPL-010 Toolbox.

**BEST PANEL REFERENCE:** TPL-005 / NPT-004 Chat Dock, with the adjacent
Eye/Toolbox split as the strongest current panel arrangement.

**WHY:** It has real independent scroll regions, persisted visibility/splitter
state, keyboard-accessible controls, Composer parity, and menu/shell wiring.

**KNOWN LIMITATIONS:** Home's Developer Workbench is application-scoped and
session-persistent rather than project-persistent; several non-workspace pages
use a single content surface and do not yet expose panel restoration machinery.
