# Template-First Context Audit

Status: identification / architecture audit only, 2026-08-21  
Starting accepted panel-audit lineage: `15b6c4f50cc7beff16f91b6dcb2606594ecf6b9a`  
Current repository audit SHA: `a481fcdd348f3904b4491cf6c2965c06197a66eb`

This record extends the existing Page/Surface Template Inventory and
panel-template system. It does not replace either record and does not change
runtime behavior, route behavior, Composer context assembly, panel behavior, or
project evidence boundaries.

## A. Starting state

Repository root: `C:/Archiosk/Research/archiosk`  
Branch: `main`  
Current SHA: `a481fcdd348f3904b4491cf6c2965c06197a66eb`

Preserved unrelated working-tree changes:

- `CONTINUATION_CHECKPOINT.md`
- `routes/api.py`
- `tests/test_api_authentication.py`
- `tests/test_psd_spin_source_diag_01.py`

No application or project data was changed for this audit.

## B. Existing TPL architecture

The authoritative page identity record is
`governance/current/page-surface-template-inventory.md`. Its companion
`governance/current/panel-template-system.md` supplies LAY and NPT composition;
`governance/current/contracts/CIC-PANEL.md` supplies panel-state rules. These
are architecture records, not project evidence.

The inventory currently contains TPL-001 through TPL-018:

| TPL | Governed name | Current route/entry and implementation | Current identity status |
|---|---|---|---|
| TPL-001 | Home / project selection | `portal.index`; `templates/index.html`, `base.html` | Explicit runtime mapping; UI Reveal supports it |
| TPL-002 | Gateway orientation | `portal.gateway_orientation`; gateway/index orientation surfaces | Inventory identity only; same Home template serves normal orientation |
| TPL-003 | Client / Owner chooser | `portal.choose_project` with environment filter; chooser/gateway templates | Inventory identity; variant is route data, not a separate endpoint |
| TPL-004 | Design-Builder / Proponent chooser | `portal.choose_project` with Proponent filter | Inventory identity; variant is route data, not a separate endpoint |
| TPL-005 | Project workspace | `workspace.show_workspace`; `case_workspace.html`, `base.html`, macros | Explicit runtime mapping; UI Reveal supports it |
| TPL-006 | Document workspace / source focus | workspace views within `workspace.show_workspace` | Inventory identity nested under TPL-005; no separate runtime TPL mapping |
| TPL-007 | Spin surface | workspace Spin view and Spin partials | Inventory identity nested under TPL-005; no separate runtime mapping |
| TPL-008 | Spin History / run detail | Spin history partials/disclosure within workspace | Inventory identity nested under TPL-007; no separate runtime mapping |
| TPL-009 | Eye panel | embedded `base.html`/`eye_pane.js` surface | NPT/panel inventory identity; no separate runtime TPL mapping |
| TPL-010 | Toolbox panel | embedded `base.html` and workspace Toolbox block | NPT/panel inventory identity; no separate runtime TPL mapping |
| TPL-011 | Project administration | workspace administration blocks and confirmations | Inventory identity; no separate runtime TPL mapping |
| TPL-012 | Developer Tools | `portal.developer_tools`; `developer_tools.html` | Explicit runtime mapping; UI Reveal supports it |
| TPL-013 | Publication / procurement package | workspace publication route and forms | Inventory identity; no separate runtime TPL mapping |
| TPL-014 | Archive / removed-project management | `portal.removed_projects` and archive routes/templates | Inventory identity; no separate runtime TPL mapping |
| TPL-015 | Authentication | `portal.login` and auth/reset routes/templates | Inventory identity; auth shell is separate from authenticated base shell |
| TPL-016 | Public landing / explore | `portal.explore`; `explore.html`/landing family | Inventory identity; no separate runtime TPL mapping |
| TPL-017 | New project / upload | upload and confirmation routes/templates | Inventory identity; no separate runtime TPL mapping |
| TPL-018 | Search / operations / about | `portal.search`, `operations.operations`, `portal.about` | Inventory grouping; no runtime TPL mapping |

The existing explicit runtime projection is
`services/template_identity.py::TEMPLATE_SURFACES`:

```text
portal.index             → TPL-001 Home
workspace.show_workspace → TPL-005 Project Workspace
portal.developer_tools   → TPL-012 Developer Tools
```

`app.py` resolves the current endpoint through
`template_identity_for_endpoint()` and injects the result into the server
template context. `_app_menu.html` and `index.html` render the identity only
when the authenticated Developer Mode and UI Reveal session gates are active.
The mapping is allow-listed and cannot be supplied by an arbitrary client
parameter.

For the remaining TPLs, the relationship is presently explicit in governance
prose and route/template naming, but not in a universal runtime object. Some
entries are nested states (TPL-006–010), and TPL-003/TPL-004 share one endpoint
with an environment variant. Those facts make blind endpoint-name inference
unsafe.

## C. Template-first viability

**VIABLE WITH CONDITIONS.**

Evidence supporting viability:

1. The repository already has a stable TPL catalogue with purpose, route/entry,
   implementation sources, LAY/NPT relationships, capabilities, and maturity.
2. Three major pages already use an explicit endpoint-to-TPL allowlist rather
   than reverse-engineering DOM/CSS.
3. The existing UI Reveal path demonstrates a small, governed projection that
   survives presentation changes better than selector inference.
4. LAY/NPT and shared primitives already have a subordinate relationship in the
   panel governance model.

Conditions:

- TPL metadata must remain a semantic contract, not a DOM schema.
- All major routed pages need an explicit mapping or an explicit documented
  reason for being a nested state/variant.
- Variant-bearing endpoints (for example Owner versus Proponent chooser) need
  a governed variant decision, not a guessed second TPL.
- Application knowledge must be injected as a separate application context;
  it must not be inserted into project Source/EvidenceItem material.
- Runtime identity expansion requires Product Owner approval because it affects
  context routing and UI Reveal scope.

## D. Recommended hierarchy

The repository-grounded model is:

```text
PAGE INSTANCE
  → TPL (semantic page/template identity)
    → LAY (significant region arrangement, where applicable)
      → NPT / governed region (functional container or surface)
        → shared primitives (Composer, voice, keyboard, CCN/context, etc.)
```

Identity levels remain distinct:

| Level | Question answered | Current repository meaning |
|---|---|---|
| TPL | “What kind of ARCHIOSK page/surface is this?” | The authoritative semantic page identity in the Page/Surface Inventory |
| LAY | “How are significant regions arranged?” | The documented layout catalogue in `panel-template-system.md` |
| NPT | “What functional panel/container is this?” | The governed nested surface catalogue; NPT-004 and NPT-009 remain distinct |
| Shared primitive | “What reusable capability is used here?” | Existing Composer, voice, keyboard, CCN/context, accessibility, and model-routing implementations |

GO should receive TPL first. It should descend to LAY/NPT only when the
question actually requires region or panel detail. This preserves the existing
panel governance without making every NPT a first-order conversational token.

## E. Runtime identity recommendation

The smallest reliable future mechanism is an expanded, governed version of the
existing endpoint allowlist, resolved server-side and placed in the existing
template/application context object:

```text
current_template = { template_id, name, purpose, capabilities, layout_id? }
```

The route/template adapter should declare the TPL explicitly for each major
page. Nested states should reference their parent TPL and only provide a
region/NPT detail when needed. A variant field can distinguish Owner/Proponent
chooser context without inventing an endpoint-derived identity.

This is a recommendation, not an implementation in this pass. No universal
metadata framework is justified by current evidence. The existing
`template_identity_for_endpoint()` path is the appropriate proof-of-concept;
future work should extend it deliberately rather than infer identities from
HTML, CSS, filenames, or pixels.

## F. GO contextual use and evidence boundary

Template identity can supply application-self-knowledge through a separate
context envelope:

```text
user message
+ current TPL semantic contract
+ optional LAY/NPT detail
+ selected application object, if any
+ project/document context, if explicitly in scope
→ scope classification
→ appropriate GO path
```

The TPL contract may describe page purpose, major regions, supported modes,
capabilities, and authorization boundaries. It must not become a second
constitution or silently grant mutation authority. Selection remains context,
not authorization.

Expected scope behavior:

| Question | Primary context | Correct boundary |
|---|---|---|
| “What does the RFP require for smoke control?” | project/document evidence | project Q&A; TPL is only location/context metadata |
| “How do I create an empty panel on the left side of this page?” | ARCHIOSK application/template knowledge | application-aware Developer path; do not answer from project evidence |
| “Can I put the smoke findings into a panel beside this document?” | application/template + project context | combine both explicitly; do not imply application knowledge is project evidence |

## G. Screenshot failure analysis

The workspace Composer enters `routes/workspace.py::_run_conversation_turn()`,
which calls `services/conversation_interpreter.py::interpret_message()` for
ordinary messages. Its project-question handler assembles governed project
evidence and calls `answer_project_question()`.

The project behavioral contract in `services/project_qa.py` explicitly states
that the prompt is about the Project only and that an application-capability
question routed there is a category error. Therefore the response rejecting the
left-panel question was not evidence leakage; it was a truthful consequence of
the current route having project evidence and no explicit application-template
context.

Template awareness could solve the routing weakness by making the active
`TPL-005 Project Workspace` available to a scope classifier or Developer-aware
branch. It must not be solved by adding application facts to the project
evidence prompt. The eventual route should distinguish an application/template
question from a project question, and should preserve project authorization and
evidence isolation for mixed questions.

## H. UI Reveal recommendation

Default Reveal should remain compact:

```text
Template: TPL-005 — Project Workspace
```

LAY and NPT should be drill-down/contextual only:

```text
Layout: LAY-5A
Region/panel: NPT-004 — Chat Dock
```

This follows the Product Owner's simplification and the existing UI Reveal
allowlist. Do not show every panel identity simultaneously. The visible TPL
identity should be attachable as Developer context; deeper identities should
appear only when a user is inspecting a relevant region.

## I. TPL-018 classification

**B — ONE GOVERNED TEMPLATE FAMILY WITH EXPLICIT CHILD/VARIANT IDENTITIES** is
the best current classification, with no split or re-ID in this pass.

Evidence:

- Search, Operations, and About are three distinct routes/templates with
  different purposes and result/status structures.
- They share application utility framing and the app menu, which explains the
  current family grouping.
- The existing inventory already marks TPL-018 `PARTIAL`, indicating that the
  grouping is not a claim that the three pages are identical.

Recommendation: retain TPL-018 as the governed utility-family identity for now;
record child/variant identities only if a future implementation needs distinct
runtime semantics and the Product Owner approves that expansion. This is not an
accidental grouping requiring immediate separation, but it is also not one
uniform page composition.

## J. Identity gaps

1. TPL-002, TPL-003, TPL-004, TPL-006–011, and TPL-013–018 have no explicit
   runtime TPL mapping in `services/template_identity.py`.
2. TPL-003 and TPL-004 share `portal.choose_project`; environment/variant data
   must be resolved explicitly if runtime identity is added.
3. TPL-006–010 are nested views/panels within TPL-005 rather than independent
   endpoints; their parent TPL is knowable, but their finer identity is not
   currently a universal runtime context object.
4. TPL-018 contains three utility routes without child runtime identities.
5. LAY/NPT identity is inventory/governance knowledge today, not a general GO
   context envelope.

## K. Governance conflicts

No direct conflict was found with the existing page inventory, panel contract,
Developer Mode, Composer, CCN, or project-evidence governance.

The only ambiguity is architectural granularity: the inventory groups nested
surfaces and TPL-018 variants while runtime identity currently exposes only
three page endpoints. That is an identity-coverage gap, not contradictory
authority.

## L. R1 / R2 boundary

### Safe organizational / identity work for a later bounded slice (R1)

- extend the existing allowlist with explicit mappings for selected major
  routed pages;
- define a small semantic TPL context object using inventory fields only;
- document parent TPL for nested states without exposing every NPT by default;
- add tests that an endpoint cannot fabricate a template identity;
- add TPL identity to the existing Developer context envelope without adding
  project evidence.

### Architecture requiring Product Owner approval (R2)

- routing ordinary workspace questions between project and application model
  paths using TPL context;
- adding variant/child identities for TPL-018 or chooser pages;
- changing the project prompt/context contract;
- exposing LAY/NPT drill-down identities through UI Reveal;
- adding a universal page-context or template registry runtime service.

## M. Files changed

One additive governance audit artifact:

`governance/current/template-first-context-audit-2026-08-21.md`

No production code, route, template, Composer context assembly, panel behavior,
project data, evidence, or deployment was changed.

## N. Validation

Repository root, branch, HEAD, status, and `git diff --check` were verified
before the audit. Existing governance/template tests remain the relevant lane;
the audit artifact does not add runtime behavior or brittle prose assertions.

No deployment was performed.

**GOVERNANCE DELTA: ADDITIVE** — this records a template-first contextual
recommendation and identity audit; it does not silently establish a new runtime
rule or alter existing doctrine.
