# Panel / Nested-Template Normalization Audit

Status: identification-only audit, 2026-08-20  
Parent inventory: [`page-surface-template-inventory.md`](page-surface-template-inventory.md)  
Panel vocabulary: [`panel-template-system.md`](panel-template-system.md)  
Contract reviewed: [`contracts/CIC-PANEL.md`](contracts/CIC-PANEL.md) v1.0

## Scope and method

This audit compares the documented `TPL → LAY → panel → NPT` catalogue with the
current routes, templates, JavaScript, persistence paths, and focused tests. It
identifies relationships and review candidates only. It does not alter panel
IDs, layout IDs, template structure, panel state, persistence, menus, or
production behavior.

Repository evidence reviewed included `templates/base.html`,
`templates/case_workspace.html`, `templates/index.html`, `_macros.html`,
`templates/_app_menu.html`, `static/js/case_workspace.js`,
`static/js/developer_composer_input.js`, `static/js/voice_input.js`,
`static/js/eye_pane.js`, `routes/portal.py`, `routes/workspace.py`,
`services/project_qa.py`, the page/surface inventory, panel-template-system,
and their focused test lanes.

## A. NPT relationship matrix

`R0` means no action indicated; `R1` is worth reviewing later; `R2` is a
high-value normalization candidate; `R3` indicates a possible architectural
conflict. A priority is not authorization.

| NPT | Current parent TPL(s) | Similar NPT(s) | Relationship | Shared primitives | Key differences | Priority |
|---|---|---|---|---|---|---|
| NPT-001 Application Menu / Shell | TPL-001–005, 011–018 as applicable | NPT-002, NPT-010 | SHARED PRIMITIVES — DISTINCT CONTAINERS | `base.html`, `_app_menu.html`, app-menu JS | Auth/gateway/public shells do not all use the workspace menu | R1 |
| NPT-002 Project Navigation / Lists | TPL-005, 006, 007 | NPT-010 | RELATED FAMILY — KEEP DISTINCT | launcher tree, divider, width/visibility persistence | project hierarchy and chooser have different scope and selection semantics | R1 |
| NPT-003 Primary Work Surface / Display | TPL-005, 006, 007 | NPT-011, NPT-007 | RELATED FAMILY — KEEP DISTINCT | workspace display divisions, independent scrolling | document focus and Spin are nested analytical/content states, not the whole work surface | R1 |
| NPT-004 Chat Dock | TPL-005, 006, 007 | NPT-009 | SHARED PRIMITIVES — DISTINCT CONTAINERS | conversation markup/macro, voice, keyboard, GO route conventions | project-persistent conversation, project evidence/context, dock splitter and panel state | R2 |
| NPT-005 Eye Panel | TPL-005, 009 | NPT-006 | RELATED FAMILY — KEEP DISTINCT | right-column shell, splitter, maximize/restore controls | evidence/image/document viewing and selection state are Eye-specific | R1 |
| NPT-006 Toolbox Panel | TPL-005, 010 | NPT-005, NPT-012, NPT-013 | RELATED FAMILY — KEEP DISTINCT | right-column shell, action/status chrome | project action stack and authorization differ from admin/developer tools | R1 |
| NPT-007 Spin Surface | TPL-007 | NPT-008 | RELATED FAMILY — KEEP DISTINCT | run detail partials, timestamp formatter, disclosure controls | analytical run lifecycle and model/evidence semantics | R1 |
| NPT-008 Spin History | TPL-008, nested in TPL-007 | NPT-007 | INTENTIONAL VARIANT | run-row disclosure and timestamp formatter | history is a disclosure inside Spin, not an independently restorable panel | R0 |
| NPT-009 Developer Chat Workbench | TPL-001 | NPT-004 | SHARED PRIMITIVES — DISTINCT CONTAINERS | keyboard, voice, Composer submission, CCN/context indicators | application/session scope, Developer Mode gate, separate chat lifecycle and no project dock splitter | R2 |
| NPT-010 Project / Environment Chooser | TPL-003, 004 | NPT-002, NPT-014 | INTENTIONAL VARIANT | gateway shell, project/list patterns | environment isolation and project-opening semantics | R0 |
| NPT-011 Document Focus | TPL-006 | NPT-003, NPT-007 | RELATED FAMILY — KEEP DISTINCT | tabs/viewer/context anchors | selected document/revision/evidence focus, not a page-level work surface | R1 |
| NPT-012 Project Administration | TPL-011 | NPT-013, NPT-015 | RELATED FAMILY — KEEP DISTINCT | forms, confirmation, authorization, status patterns | project lifecycle actions and project permissions | R1 |
| NPT-013 Developer Tools | TPL-012 | NPT-012 | INTENTIONAL VARIANT | protected forms and confirmation patterns | admin/developer reset scope; not ordinary Toolbox content | R0 |
| NPT-014 Gateway Orientation | TPL-001, 002 | NPT-010, NPT-017 | INTENTIONAL VARIANT | gateway input/voice and navigation | deterministic orientation, explicitly not model-backed project/developer chat | R0 |
| NPT-015 Publication / Archive Management | TPL-013, 014 | NPT-012 | RELATED FAMILY — KEEP DISTINCT | lifecycle status and confirmation patterns | publication boundary versus reversible archive/restore | R1 |
| NPT-016 Authentication Shell | TPL-015, and public access framing in TPL-016 | NPT-001 | INTENTIONAL VARIANT | accessible form framing and status/error patterns | unauthenticated security boundary; no workspace panels | R0 |
| NPT-017 Project Setup / Upload | TPL-017 | NPT-010, NPT-014 | RELATED FAMILY — KEEP DISTINCT | form, error, confirmation, voice/help primitives | ingestion/setup state and source registration | R1 |
| NPT-018 Search / Operations / About | TPL-018 | NPT-001, NPT-014 | INSUFFICIENT EVIDENCE | app menu and result/status patterns where present | three intentionally different utility routes are grouped by current inventory | R1 |

## B. Panel-contract matrix

The result reflects evidence available now; `PARTIAL` means a required field or
behavior is not uniformly established, not that it should be changed.

| NPT | CIC-PANEL result | Gaps / exact uncertainty | Evidence |
|---|---|---|---|
| NPT-001 | PARTIAL | shell identity is clear; panel-state fields do not apply uniformly to every shell | `base.html`, `_app_menu.html` |
| NPT-002 | PASS | none material for current launcher | launcher markup, `lists-divider`, localStorage visibility/width and keyboard controls in `base.html` |
| NPT-003 | PARTIAL | primary surface is intentionally non-closable; page-specific focus/restoration is distributed across workspace code | `case_workspace.html`, workspace JS |
| NPT-004 | PARTIAL | resize/lock/visibility evidence is strong; one uniform menu restoration contract for every invocation is not established by the implementation audit | `base.html`, `_macros.html`, `case_workspace.js` |
| NPT-005 | PASS | panel identity and splitter/maximize state are established; independent close semantics are not claimed | `base.html`, `eye_pane.js` |
| NPT-006 | PARTIAL | restoration and content lifecycle are established, but a single panel-state API is absent | `base.html`, toolbox block, app menu |
| NPT-007 | PARTIAL | nested analytical surface has no independent panel lifecycle; model/evidence dependencies are clear | Spin partials and workspace route |
| NPT-008 | NOT APPLICABLE | disclosure rows are not independently closable/resizable panels | Spin history partial |
| NPT-009 | PARTIAL | workbench identity/content is clear; no independent close/restore/panel persistence is established | `index.html`, `routes/portal.py`, shared JS |
| NPT-010 | PARTIAL | chooser has a composed shell but no governed panel close/resize contract | chooser/gateway templates |
| NPT-011 | PARTIAL | document focus is nested state, not an independent closable panel | workspace document tabs/viewer |
| NPT-012 | PARTIAL | form surface has confirmation/authorization but no panel-state machinery | workspace administration blocks |
| NPT-013 | PARTIAL | protected surface is clear; panel-state fields are not applicable to its current page form | `developer_tools.html`, `routes/portal.py` |
| NPT-014 | NOT APPLICABLE | deterministic orientation surface is a content/state pattern, not a closable panel | gateway/index orientation markup |
| NPT-015 | PARTIAL | lifecycle forms/list have restore semantics for projects, not a general panel-state API | archive/publication routes/templates |
| NPT-016 | NOT APPLICABLE | authentication boundary is not an in-workspace panel | auth shell/templates |
| NPT-017 | PARTIAL | setup/upload forms have lifecycle/error state, not panel restoration | upload routes/templates |
| NPT-018 | UNKNOWN | grouped utility routes have different structures; one shared panel contract cannot be proven from current evidence | search/operations/about routes/templates |

## C. Page composition matrix

`MATCHES INVENTORY` means the documented composition is supported at the
surface level. `PARTIAL MATCH` means global shell composition or nested scope
is shared but the inventory's panel granularity is not independently rendered.

| TPL | LAY | Documented panels/NPTs | Inventory vs implementation | Drift notes |
|---|---|---|---|---|
| TPL-001 | LAY-1 | main NPT-014; Developer workbench NPT-009 | PARTIAL MATCH | `index.html` also participates in the shared authenticated shell; normal gateway and Developer workbench are separate modes |
| TPL-002 | LAY-1 | main NPT-014 | MATCHES INVENTORY | deterministic gateway orientation |
| TPL-003 | LAY-2V | chooser NPT-010; context/shell NPT-001 | MATCHES INVENTORY | gateway shell provides the context boundary |
| TPL-004 | LAY-2V | chooser NPT-010; context/shell NPT-001 | MATCHES INVENTORY | same structure with Owner/Proponent isolation |
| TPL-005 | LAY-5A | NPT-002, 003, 005, 006, 004 | PARTIAL MATCH | all five regions are present; right Eye/Toolbox is itself LAY-2H-R and panel state is implemented through distributed inline/workspace JS rather than one panel API |
| TPL-006 | LAY-5A | TPL-005 shell + NPT-011 center | MATCHES INVENTORY | document focus is nested in primary work surface |
| TPL-007 | LAY-5A | TPL-005 shell + NPT-007 center | MATCHES INVENTORY | Spin is nested in workspace, not a second shell |
| TPL-008 | LAY-1 | NPT-008 history disclosure | MATCHES INVENTORY | disclosure rows have no independent panel state |
| TPL-009 | LAY-2H-R | NPT-005 Eye | PARTIAL MATCH | implementation is an embedded right-column pane, not a standalone routed page |
| TPL-010 | LAY-2H-R | NPT-006 Toolbox | PARTIAL MATCH | same embedded right-column qualification |
| TPL-011 | LAY-1 | NPT-012 administration | MATCHES INVENTORY | forms/confirmations are content-level |
| TPL-012 | LAY-1 | NPT-013 developer tools | MATCHES INVENTORY | protected admin page |
| TPL-013 | LAY-1 | NPT-015 publication | MATCHES INVENTORY | publication is a bounded workspace workflow |
| TPL-014 | LAY-1 | NPT-015 archive/restore | MATCHES INVENTORY | read-only archived state until restore |
| TPL-015 | LAY-1 | NPT-016 authentication | MATCHES INVENTORY | separate auth shell |
| TPL-016 | LAY-1 | NPT-016 public landing/access | MATCHES INVENTORY | public boundary, no authenticated Developer panels |
| TPL-017 | LAY-1 | NPT-017 setup/upload | MATCHES INVENTORY | deterministic setup helper |
| TPL-018 | LAY-1 | NPT-018 search/operations/about | PARTIAL MATCH | one TPL intentionally groups three utility route structures; a single panel implementation is not evidenced |

## D. Shared primitive matrix

| Primitive | Where it exists | Reused by | Duplicated/different | Difference appears intentional? |
|---|---|---|---|---|
| Authenticated application shell/menu | `base.html`, `_app_menu.html`, `app_menu.js` | workspace and many authenticated pages | gateway/auth/public shells use variants | Yes, boundary-dependent |
| Lists visibility/width/splitter | `base.html` inline JS/CSS, `lists-divider` | TPL-005/006/007 | no second launcher implementation found | Yes, shared shell primitive |
| Eye/Toolbox splitter and maximize/lock | `base.html`, `eye_pane.js` | TPL-005/009/010 | no separate Eye/Toolbox splitter path found | Yes, shared right-column primitive |
| Chat dock resize/link/lock | `base.html`, `case_workspace.js` | NPT-004 in TPL-005/006/007 | Developer Workbench has no equivalent dock splitter | Yes, scope/container difference |
| Workspace conversation markup | `_macros.html`, `case_workspace.html` | NPT-004 | Home uses its own session-history/workbench markup | Difference is partly architectural; possible future review |
| Composer keyboard guard | `developer_composer_input.js` | Home Developer Composer and workspace Composer | Gateway orientation has its own submit handler | Yes: gateway is deterministic specialized input |
| Voice input | `voice_input.js` | home, workspace, gateway where enabled | different element IDs/initializers | Yes, same engine with scoped wiring |
| GO model submission | `services/project_qa.py`, `routes/portal.py`, workspace conversation path | project Composer and Developer Composer | gateway orientation does not call model-backed Q&A | Yes, intentional |
| CCN/context indicators | `index.html`, workspace templates/routes | NPT-009 and project Developer contexts | labels/state envelopes differ by application/project scope | Yes |
| Panel visibility persistence | `base.html` localStorage keys | Lists, Toolbox, Eye/Toolbox split, chat split | no common state API | Difference is current architectural gap |
| Menu restoration | `_app_menu.html`, `app_menu.js`, existing shell actions | workspace controls | no uniform restore item for every NPT | Partially established; review candidate |
| UI Reveal identity | `services/template_identity.py`, `_app_menu.html` | TPL-001, TPL-005, TPL-012 | no NPT mapping or panel reveal mapping | Current known gap, not fixed here |

## E. Candidate families

These are descriptive groupings, not replacement templates.

| Family | Members | Observation |
|---|---|---|
| CHAT FAMILY | NPT-004, NPT-009 | shared Composer/voice/keyboard concepts; distinct project/application containers |
| UTILITY PANEL FAMILY | NPT-005, NPT-006 | shared right-column splitter/chrome; Eye and Toolbox retain distinct semantics |
| NAVIGATION / ENTRY FAMILY | NPT-002, NPT-010, NPT-014, NPT-017 | navigation and setup patterns overlap but differ in authority and state |
| PRIMARY WORK FAMILY | NPT-003, NPT-011, NPT-007 | document/Spin surfaces are nested work states, not interchangeable panels |
| LIFECYCLE / ADMIN FAMILY | NPT-012, NPT-013, NPT-015 | confirmation/status patterns overlap; permissions and consequences differ |
| SECURITY / ACCESS FAMILY | NPT-001, NPT-016 | shell/access concerns; authenticated and unauthenticated boundaries remain distinct |
| ANALYSIS DISCLOSURE FAMILY | NPT-007, NPT-008 | Spin History is a disclosure within Spin, not a peer panel |
| UTILITY RESULTS FAMILY | NPT-018 | insufficient evidence to force Search, Operations, and About into one reusable panel |

## F. NPT-004 Chat Dock vs NPT-009 Developer Chat Workbench

### What they share

Both present a conversational GO surface and use the established Composer
interaction primitives: multiline input, Send, Enter/Shift+Enter behavior,
voice input, accessibility/status handling, contextual/CCN-aware routing, and
model-backed conversation services where their route is conversational. Their
tests protect much of the same input and context behavior.

### What differs architecturally

* **Scope:** NPT-004 is project/workspace-scoped; NPT-009 is application-level
  Developer Mode and must operate without `project_id`.
* **Persistence:** NPT-004 conversation is project workspace/case data and is
  rendered from the project conversation path. NPT-009 uses a session-scoped
  Developer chat envelope with current chat, titles, timestamps, New Chat, and
  governed Delete Chat.
* **Panel state:** NPT-004 is a real bottom dock with resize/link/lock and
  workspace visibility/splitter state. NPT-009 is a bounded workbench on Home;
  its chat lifecycle controls are not equivalent to closing/restoring a dock.
* **Context:** NPT-004 receives project/source/document/evidence context and
  project conversation history. NPT-009 receives Developer Mode, application
  selection, application-level CCN, and no fabricated project binding.
* **UI/container:** NPT-004 is shell-owned in `base.html` and populated through
  `_macros.html`/`case_workspace.html`; NPT-009 is rendered in `index.html`.
* **Lifecycle:** closing a project dock must not delete project conversation or
  evidence; deleting a Developer chat is an explicit, separately authorized
  chat lifecycle action and does not delete its CCN.

### Classification

**SHARED PRIMITIVES — DISTINCT CONTAINERS.** There is enough common behavior to
justify future review of a shared Composer primitive, but the persistence,
scope, context envelope, panel-state, and authorization differences are
architectural. The current evidence does not justify merging NPT-004 and
NPT-009, renaming either, or treating one as a drop-in replacement.

### Theoretical sharing versus Product Owner decision

Theoretically shareable: input row/macro, voice initialization contract,
keyboard/IME guard, pending-submit behavior, accessible status treatment, and
possibly a context-indicator presentation primitive. Not safe to merge without
decision: conversation storage, chat identity/history lifecycle, panel
visibility/resize/restore state, project-versus-application scope, and route
authorization/context assembly.

### Review priority

`R2 — HIGH-VALUE NORMALIZATION CANDIDATE` for a future bounded shared-primitive
review; not an approved unification.

## G. UI Reveal identity audit

Current `services/template_identity.py` provides a governed allowlist for the
known page identities TPL-001 Home, TPL-005 Project Workspace, and TPL-012
Developer Tools. `_app_menu.html` renders a page identity when Developer Mode
and UI Reveal are enabled, and the identity can be attached as Developer
context.

The current gap is that no governed NPT/LAY mapping is exposed by UI Reveal for
embedded panels. A future inspection could need contextual `LAY-*` and `NPT-*`
identity for Chat Dock, Developer Workbench, Eye, Toolbox, and Spin History.
This audit does not add those labels or guess mappings beyond the existing
inventory.

## H. Possible future changes requiring Product Owner decision

1. Whether to extract a shared Composer-row primitive for NPT-004/NPT-009 while
   keeping their containers, scope, and persistence distinct.
2. Whether to define a common panel-state API for visibility, resize, restore,
   and menu restoration, or retain the current shell-specific state paths.
3. Whether the Developer Chat Workbench should gain an independent close/
   restore state, or remain a Home workbench that is always present in Developer
   Mode.
4. Whether UI Reveal should expose contextual LAY/NPT identities and, if so,
   which selection/inspection event is authoritative.
5. Whether TPL-018 should remain a grouped utility entry or be decomposed only
   after the three routes are reviewed as separate surfaces.
6. Whether the current right-column Eye/Toolbox arrangement warrants separate
   layout lineage beyond `LAY-2H-R`.
7. Whether any panel's existing persistence should be moved from localStorage
   into a governed user/session preference model.

## I. Validation and change boundary

The existing panel-template governance test lane and page/panel inventory
checks were used as the audit baseline. No production code, template, route,
panel behavior, persistence, menu, project data, or conversation data was
modified for this audit.

NO PANEL/NPT WAS REMOVED, MERGED, RENAMED, SUPERSEDED, NORMALIZED OR
BEHAVIORALLY MODIFIED.

GOVERNANCE DELTA: ADDITIVE — this report records an identification-only audit
without changing the existing panel contract or inventory classifications.
