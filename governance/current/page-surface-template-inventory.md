# ARCHIOSK Page / Surface Template Inventory

Status: current implementation inventory; reviewed 2026-08-20

This is the authoritative implementation inventory for meaningful page and
page-level surface patterns. It is architecture knowledge, not project
evidence, and must never be ingested as a Source or EvidenceItem.

## Progressive template principle

ARCHIOSK converges toward a reusable page/template system progressively:

```text
best accepted reference
→ reuse proven primitives
→ implement the current surface
→ test parity and intentional differences
→ update this inventory and maturity
```

Before materially changing a page, review the relevant candidates here and
report the chosen reference, reused primitives, intentional differences, and
remaining parity gaps. A later accepted surface may become a better reference;
lineage is recorded rather than assumed.

## Inventory

| ID | Page / surface | Route / entry | Primary template(s) | Shared primitives | Composer / voice | Developer / CCN | Structure and badges | Coverage / maturity | Known gaps / lineage |
|---|---|---|---|---|---|---|---|---|---|
| TPL-001 | Home / project selection | `portal.index` `/` | `index.html`, `base.html` | app menu, Developer workbench, `developer_composer_input.js`, `voice_input.js` | Normal Gateway orientation: yes / yes. Developer Composer: yes / yes; compact session chat history, New Chat, governed Delete Chat. | Developer home Composer is application-scoped; `/CCN` supported; UI Reveal may expose this identity. | Project/environment content; Developer Mode, CCN, template identity and selected-context indicators. | `test_developer_home_composer_01.py`, `test_developer_ui_reveal_workbench_history_01.py`, `test_home_navigation_shell.py`; **REFERENCE** for application Composer. | Normal orientation remains deterministic; direct visual selection is future work; session-scoped Developer chat persistence remains separate from project conversations. |
| TPL-002 | Gateway orientation | `portal.gateway_orientation` `/gateway/orientation` | `index.html` (normal Home), legacy `gateway_*` family | `voice_input.js` | yes / yes; deterministic navigation/info, not model Q&A. | No. | Gateway project/environment context. | `test_voice_gateway_orientation.py`; **SPECIALIZED**. | Do not copy as a conversational-intelligence reference. |
| TPL-003 | Client / Owner project chooser | `portal.choose_project` `/projects/choose` | `project_chooser.html`, `gateway_base.html`, `gateway_shell.html` | app menu, gateway shell | No primary Composer. | No. | Environment and project identity. | project chooser/navigation lanes; **REUSABLE**. | Specialized vestibule shell. |
| TPL-004 | Design-Builder / Proponent chooser | `portal.choose_project` with environment filter | `project_chooser.html`, gateway family | same as TPL-003 | No primary Composer. | No. | Environment/project separation. | owner/proponent isolation tests; **REUSABLE**. | Must preserve project isolation. |
| TPL-005 | Project workspace | `workspace.show_workspace` `/projects/<id>/workspace` | `case_workspace.html`, `_macros.html`, `base.html` | conversation dock macro, `voice_input.js`, `developer_composer_input.js`, app menu | yes / yes; model-backed project path, Enter/Shift+Enter, IME and pending guards. | Developer workspace context and CCN-compatible route behavior. | left rail / main / Eye / Toolbox; project, source, context, status badges. | Composer, workspace, Eye/Toolbox, Spin lanes; **REFERENCE** for project interaction completeness. | Large specialized surface; continue extracting only proven primitives. |
| TPL-006 | Document workspace / source focus | workspace document views within TPL-005 | `case_workspace.html`, `_macros.html` | same dock Composer and source-context anchors | yes / yes; document context is attached to the project Composer. | Selected source context may be inspected in Developer Mode. | source/document focus, Eye and citation context. | document tabs, source/evidence, context tests; **REUSABLE**. | Not a separate independent chat system. |
| TPL-007 | Spin surface | workspace overview Spin region | `case_workspace.html`, `_spin_prototype.html`, `_spin_run_detail.html` | timestamp formatter, run-detail partial | No separate Composer; uses workspace Composer. | Developer inspection can attach Spin History. | First/Delta state, run status, finding counts. | Spin/history lanes; **SPECIALIZED**. | Analytical surface; do not use as general page template. |
| TPL-008 | Spin History / run detail | workspace overview/history state | `_spin_run_detail.html`, `case_workspace.html` | timestamp formatter, disclosure controls | No separate Composer. | Strong Developer inspection subject. | chevron rows, persisted local timestamps, run metadata. | `test_spin_history_compact_01.py`, timestamp tests; **REUSABLE**. | Keep detail inside the selected history row. |
| TPL-009 | Eye panel | embedded in TPL-005 | `case_workspace.html`, `static/js/eye_pane.js` | evidence viewer, structural regions | No separate Composer. | Inspectable application/project context. | Eye zone, selection and evidence status. | Eye lanes; **SPECIALIZED**. | Do not confuse with future Developer Terminal Eye. |
| TPL-010 | Toolbox panel | embedded in TPL-005 | `case_workspace.html` | action stack, findings, project tools | No separate Composer. | Developer inspection subject. | Toolbox zone and persistent Eye divider. | Eye/Toolbox lanes; **SPECIALIZED**. | Contents remain workspace-specific. |
| TPL-011 | Project administration | embedded in TPL-005 | `case_workspace.html`, confirmation templates | project lifecycle/access forms | No primary Composer. | Admin/Developer Tools may be reachable from app menu. | lifecycle, owner, environment, archive badges. | archive/reset/publication tests; **REUSABLE**. | Consequential actions require existing authorization/confirmation. |
| TPL-012 | Developer Tools | `portal.developer_tools` `/admin/developer-tools` | `developer_tools.html`, `base.html` | admin gate, confirmation patterns | No Composer; Developer Composer remains the primary conversational toolbox elsewhere. | Developer-only; CCN context is separate. | admin/developer status and reset state. | `test_developer_tools_reset_01.py`; **SPECIALIZED**. | Never expose as ordinary project Toolbox. |
| TPL-013 | Publication / procurement package | `workspace.publish_procurement_package_route` | `case_workspace.html`, confirmation patterns | source selection, governance log | No Composer. | Developer review may inspect publication state. | lifecycle/publication state. | publication/isolation tests; **SPECIALIZED**. | Owner/Proponent boundary is authoritative. |
| TPL-014 | Archive / removed-project management | `portal.removed_projects`, archive routes | `removed_projects.html`, `project_removed.html`, confirm templates | project lifecycle confirmations | No Composer. | Admin/project lifecycle only. | ARCHIVED / removed state. | archive/project lifecycle tests; **SPECIALIZED**. | Read-only until restore; no evidence deletion. |
| TPL-015 | Authentication | `portal.login`, password routes | `login.html`, `auth_shell.html`, reset templates | auth shell, accessible form patterns | No Composer. | No. | auth/security state. | authentication/security lanes; **REFERENCE** for auth shell only. | Not a project-page reference. |
| TPL-016 | Public landing / explore | `portal.explore` `/explore` | `explore.html`, landing family | landing voice where applicable | No authenticated Composer. | No. | public identity and access. | landing lanes; **SPECIALIZED**. | Public boundary must remain separate. |
| TPL-017 | New project / upload | `portal.upload`, folder upload and confirmation routes | `upload.html`, `upload_confirm.html`, gateway family | form/error/confirmation patterns, orientation helper | Establish-project help widget is deterministic; not the Developer Composer. | No. | project setup and environment identity. | ingestion/project-creation lanes; **REUSABLE**. | Do not conflate setup help with project conversation. |
| TPL-018 | Search / operations / about | `portal.search`, `portal.operations`, `portal.about` | `search.html`/`operations.html`/`about.html` | base/app menu, result/list patterns | No primary Composer. | Developer may inspect these as application objects. | app identity and result/status context. | respective route/UI tests; **PARTIAL**. | Candidate-specific patterns need review before reuse. |

## Current reference candidates

- Project interaction reference: **TPL-005 Project workspace**. It has the
  strongest complete Composer, voice, keyboard, pending/error, context, panel,
  and accessibility coverage.
- Application-level Composer reference: **TPL-001 Home / project selection**.
  It uses the same model-backed Developer Composer route and now the same
  voice primitive as TPL-005, while correctly carrying no `project_id`.
- Authenticated shell reference: **TPL-015 Authentication**, limited to auth
  framing and form accessibility, not project interaction.
- Gateway/reference navigation: **TPL-002** is intentionally specialized and
  is not a model-conversation reference.

## Composer parity matrix

| Surface | Input | Mic | Send | Enter / Shift+Enter | IME / pending | Model path | History / context | Accessibility / errors |
|---|---|---:|---:|---|---|---|---|---|
| Home Developer Composer (TPL-001) | multiline `textarea` | Yes | Yes | shared `developer_composer_input.js` | shared input guard; route redirect/error fallback | `answer_application_question` → `call_llm_json` | session history + CCN + selected application object; no project binding | shared voice status/ARIA; model-unavailable honest fallback |
| Workspace project Composer (TPL-005) | multiline `textarea` | Yes | Yes | shared `developer_composer_input.js` | shared input guard plus workspace pending state | `interpret_message` → `answer_project_question` → `call_llm_json` for ordinary Q&A | project/case history + evidence + source/UI context | shared voice status/ARIA; route/model error handling |
| Developer workspace Composer | same workspace dock | Yes | Yes | same shared handler | same | workspace route with Developer context where applicable | project-scoped context; no cross-project leakage | same |
| Gateway orientation (TPL-002) | single-line text input | Yes | Ask | form submit; not shared Developer Composer | deterministic `/gateway/orientation` | no project conversation history; navigation scope only | browser voice status and accessible controls |
| Establish-project helper (TPL-017) | page-local input | implementation-specific | page-local | page-local | page-local | deterministic field-help classifier | no project evidence | specialized form behavior |

## Required implementation report fields

Future material page work must state: `REFERENCE CANDIDATES REVIEWED`, `BEST
TEMPLATE-WORTHY REFERENCE`, `WHY IT WAS CHOSEN`, `REUSED PRIMITIVES`,
`INTENTIONAL DIFFERENCES`, `KNOWN PARITY GAPS`, and `TEMPLATE INVENTORY STATUS
CHANGE`.

## Current gaps

- Home and workspace still have different persistence envelopes by scope;
  this is intentional, but the distinction must remain explicit.
- Gateway orientation remains deterministic navigation rather than model-backed
  conversation.
- Direct visual selection/highlighting is not yet a common primitive.
- No full component framework or site-wide page rewrite is authorized.

## Page-by-panel extension

This inventory's page identities are decomposed into governed layouts, panels,
and nested templates in [`panel-template-system.md`](panel-template-system.md).
That companion record is the authoritative composition extension and records a
`LAY-*` plus panel count/configuration for every TPL entry, the `NPT-*` catalogue,
panel behavior, reuse lineage, and the current 18-page audit. It deliberately
does not duplicate page prose or authorize a broad UI refactor.
