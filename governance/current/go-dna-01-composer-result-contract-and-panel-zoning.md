# Composer Result Contract, Panel Zoning, and Finding Grammar (CLAUDE-GO-DNA-01)

**Status:** IMPLEMENTED, bounded — a Directional/DNA-Level correction, per the Product Owner's
own explicit framework for this record (`CLAUDE-GO-DNA-01`'s own governing prompt: "small
correction, large directional consequence" — marker sketches on current drawings, a wind tunnel
shaping flow). This is not a Local Implementation Instruction (spacing/wording/bounded visual
adjustment); it materially determines how future Composer/panel work organizes itself and is
recorded here as durable governance rather than left only in chat history, commit messages, or
task state, per that same governing prompt's own Section 2.

This record captures, together, three decisions that landed as one continuous architectural
thread across `CLAUDE-CA1D-COMPOSER-SPINE-01` (Stages 0–2), `CLAUDE-GO-COMPETE-01`, and
`CLAUDE-GO-RIGHT-PANEL-01` — treated as one governance record rather than three, because they are
one decision seen from three angles: Composer must be able to say something structured, not only
prose (§1); that structured material needs a durable home outside the chat stream (§2); and where
that home lives, and what it may and may not contain yet, is itself an architectural boundary
(§3, §4). `CLAUDE-CA1D-COMPOSER-SPINE-01`'s own Stage-3/governance-record requirement (noted at
that stage's own planning time, before Stage 3 wiring lands) is satisfied by this record for the
result-contract portion; Stage 3 (wiring the new `run_conversational_turn` orchestrator into
`interpret_message`'s dispatch chain) remains its own separate, not-yet-authorized step — see §5.

---

## 1. Composer result contract: structured findings, not prose-only

**The invariant:** the Composer's own result contract (`InterpretationResult` in
`services/conversation_interpreter.py`, and `ProjectQAResult` in `services/project_qa.py`) must
never be locked into `model response → string → chat bubble only`. A conversational turn may
produce, alongside its prose reply, zero or more structured objects meant to be consumed
programmatically by something other than the chat renderer.

**Why this is DNA, not a local choice:** every future "Composer discovers, something else holds
and organizes" capability (a right-panel projection, a future Spin result, a governed-action
proposal) depends on the result contract already being able to carry that payload. Locking the
contract to a single `reply_text` string would force every future capability to either scrape
prose (fragile, already explicitly rejected — see `CLAUDE-GO-RIGHT-PANEL-01`'s own Section 8: "the
right panel must consume the structured representation, not scrape prose from the rendered chat
message") or invent a second, parallel result path. Neither is acceptable long-term, so the
contract itself is the durable boundary.

**What is implemented today**, each following the same "the model's own signal, defensively
parsed, capped, dropped-if-malformed, empty unless genuinely warranted" discipline first
established by `river_actions` (`CLAUDE-CA1D-RIVER-PO-01`):

- `ProjectQAResult.river_actions` — ranked next-moves ("what should I do next"), unchanged by this
  record, the original precedent the rest of this pattern generalizes from.
- `ProjectQAResult.findings` (`CLAUDE-GO-RIGHT-PANEL-01`, new) — discrete project
  characterizations ("what did you notice and why does it matter"), a **separate, independently
  gated** field from `river_actions` — the two answer different questions and are never populated
  from the same model signal (see `services/project_qa.py`'s own `BEHAVIORAL_CONTRACT`: "the two
  are never the same list").
- `InterpretationResult.composer_finding_ids` — the real, persisted
  `services.case_workspace.ComposerFinding` ids created from a turn's `findings`, threaded back
  through `conversation_interpreter._handle_project_question` into whatever redirects/renders the
  page next.
- `InterpretationResult.operational_actions`/`river_actions` — the pre-existing "fourth beat"
  (Make a Task / Highlight this answer), unchanged, coexisting with the new `findings` seam rather
  than being replaced by it (a Task and a Finding remain genuinely different objects — see §3).

**Gating discipline (why this doesn't turn every reply into a wall of structured noise):** each
structured field is populated **only** when the model's own JSON explicitly signals it belongs —
never inferred from `action_taken`, never forced onto an ordinary factual answer. An ordinary
"What is the name of this RFP?" question produces an empty `findings` array and creates nothing;
Section 10.9 of `CLAUDE-GO-RIGHT-PANEL-01`'s own acceptance test ("ordinary non-finding chat does
not pollute the right panel") is enforced structurally by this gate, not by a UI-side filter —
tested directly (`tests/test_go_right_panel_01.py::ComposerFindingPromotionTests::
test_ordinary_factual_question_creates_no_findings`).

---

## 2. Panel zoning: Left = evidence territory, Center = working surface, Right = contextual intelligence

**The invariant**, stated by the Product Owner across this session and now recorded durably:

- **LEFT** (the existing "Lists" panel, `templates/base.html`) — evidence territory only: project
  name, folders, files, document hierarchy. A pure selector into what already exists.
- **CENTER** (the existing "Display" panel) — the working surface: active document, comparison,
  evidence inspection, editing/markup where supported.
- **RIGHT** (the existing "Toolbox" panel, `templates/case_workspace.html`'s `{% block toolbox %}`)
  — contextual intelligence and governed action: Spin/Composer findings, Requirements,
  Investigations, Tags, related Tasks, related RFI material, characterization, suggested next
  actions, contextual tools. **Changes with the selected project context — never a second,
  permanently-visible copy of the left navigation.**

**This is a zoning correction, not a new panel.** All three panels already existed
(`workspace-right-column`/`workspace-toolbox-panel` predate this record, `CLAUDE-P40-EYE1`). What
changes is the *rule* for what belongs in which zone, established by inspecting what the Toolbox
already does correctly (see §3) and extending that same shape, rather than by building a fourth
surface.

**Conditional projection, not wholesale relocation** (per the governing prompt's own Section 5
"Directional Correction vs Overbuilding" and its "Conditional Right-Panel Principle" — do not move
the current left navigation wholesale from left to right; project existing capabilities
contextually, under the conditions where they matter). Implemented today: the Toolbox branches
`active_case` (Investigation selected) → `selected_source` (Document selected) →
`toolbox.project-intelligence` (nothing more specific selected) — each condition showing only
what's relevant to what's actually selected, never a permanent menu of every capability at once.

**Update — the zoning correction is now structurally complete, not only the narrower
`composer_findings_view` branch this section originally described (`CLAUDE-GO-DNA-01` Part F.13,
landed after this record's own initial capture).** `templates/base.html`'s Lists panel for an open
project now renders ONLY file/evidence territory: the project self-link, the Documents tree, Files,
and file-related Project Tools (Add Documents/Add Text Record/Revise Document/Add External
Source/Removed Items). Requirements, Investigations, RFI Correspondence, Work Products,
Conversation, Tasks, Tags, and Remove Project were physically relocated out of Lists into the
Toolbox's own always-present `toolbox.project-intelligence` section (`templates/case_workspace.html`)
— reusing the exact same routes/forms/DOM ids each control already had (the Tasks/Tags live-update
JS is DOM-id-based, not position-based, so relocating the surrounding markup required zero JS
changes). Security/Operations/Project Data Management remain correctly separated, unchanged (§3's
own finding stands). `UI_REFERENCE_MAP.md` records the full retired-`lists.project.*` →
new-`toolbox.*` mapping.

---

## 3. Existing-primitive-reuse audit (methodology + findings)

Before building `ComposerFinding`, a repository-grounded reuse audit was performed of the
existing left-panel/Lists entries — per the governing prompt's own instruction: **"grab the
existing threads, not rebuild machinery GO already has in rough form."** Full per-entry findings
(reusable domain object / reusable UI projection / source-navigation & persistence behavior /
relocatable? / new seam needed, for each of Overview, Requirements, Investigations, RFI
Correspondence, Work Products, Conversation, Tasks, Tags, Project Tools, Security/Operations/
Project Data Management) were reported to the Product Owner in-session; the durable summary below
is what materially shaped `CLAUDE-GO-RIGHT-PANEL-01`'s own design:

- **Investigations already IS the target pattern, not a migration candidate.** The left-nav
  "Investigations" entry is already a pure selector (title + Archive action, no finding content);
  the Toolbox's existing `toolbox.investigation-findings` branch already does the real contextual
  projection (Finding cards, confidence, artifact thumbnail, provenance, embedded RFI drafts) —
  confirming the §2 zoning rule was already correctly implemented once, and `CLAUDE-GO-RIGHT-PANEL-
  01`'s own `toolbox.composer-findings` branch was built to match that established shape rather
  than inventing a new one.
- **Why `ComposerFinding` is a new object, not a reuse of `Finding`.** `Finding`
  (`services/case_workspace.py`) requires `case_id`/`analysis_id` — a real, opened Investigation
  with a formal Analysis behind it. A project-level Composer answer has neither. Forcing one into
  existence merely to satisfy `Finding`'s shape would be exactly the "conflating the two" this
  governing prompt's own Section 4 warns against. `ComposerFinding` is the smaller, project-scoped
  object; it does not replace `Finding`, and a future escalation path (`ComposerFinding` →
  real Investigation) is a NAMED, not-yet-built seam — see §5.
- **Why `ComposerFinding.tag` is a plain string, not a `Tag` reference.** `Tag`/`TagOccurrence`
  (`services/case_workspace.py`) is a small, reusable, colour-coded label taxonomy (Important/
  Question/Highlight plus project-scoped custom tags), meant to be applied to many different
  passages. A per-finding one-off title is a different concept; routing it through
  `create_custom_tag` would flood that taxonomy with names never reused anywhere else. The
  repository already distinguishes the two — this keeps them distinct rather than conflating them.
- **A genuine untapped foundation, named not built.** `TagOccurrence.source_anchor`
  (`ConversationSourceAnchor`) anchors only into a *conversation message's* own text today
  (`KNOWN_CONVERSATION_ANCHOR_SCOPES`) — it cannot anchor into a Source document's own page/
  paragraph. That capability already exists at a lower level (`StructuralUnit`/`AddressableRegion`/
  `EvidenceItem`, Camel MM1, populated via `register_pdf_page_structure`/
  `register_plain_text_structure`) but `Tag` is not wired to it. A future "tag the actual document
  passage, not just a chat reply" capability would extend `TagOccurrence`'s anchor scope to also
  accept an `AddressableRegion`/`EvidenceItem` id — a real, identified, **not yet authorized** seam.
- **`WorkProduct.source_finding_id`/`source_investigation_step_id` is the existing precedent for a
  finding-to-something cross-reference field.** `Task` has no equivalent field linking it back to
  the `ComposerFinding`/`Finding` that spawned it today — only the generic `Anchor` it was created
  with. A future `ComposerFinding.related_task_id` (or the reverse) would mirror `WorkProduct`'s
  already-proven shape, not invent a new cross-reference convention.
- **"Project Tools" is not a tool registry.** Confirmed by direct inspection
  (`templates/base.html`'s `lists.project.tools` branch): a fixed, hardcoded sequence of existing
  forms (Remove Project, Add Documents, Add Text Record, Revise Document, Add External Source), no
  data-driven enumeration, no plugin/registration mechanism. It is **not** a foundation for future
  Composer Tool Making as-is — recorded honestly so a future session does not mis-scope Tool Making
  as "just relocating what's there."
- **Security/Operations/Project Data Management are already correctly separated.** Distinct,
  admin-gated Blueprint routes (`security.department_home`, `operations.department_home`), reached
  via ordinary Lists links, never embedded as intelligence content. No structural change needed;
  only possible cosmetic de-emphasis from the file-explorer-shaped tree items around them remains
  open, and is not addressed by this record.

---

## 4. Finding professional grammar

**The invariant** (the intended machine/human structure a Composer-emitted finding should carry,
per the governing prompt's own Section 1 DNA list):

> Reference/Evidence → Concern → Unresolved Question → Urgency/Stage/Discipline/Focus (where
> supported) → Suggested action → PM review/edit/toggle/adjudication

**Implemented today** (`services.case_workspace.ComposerFinding`): `source_reference`, `concern`,
`unresolved_question`, plus optional `urgency`/`project_stage` — populated only when the model's
own evidence genuinely supports a specific value, left `None` otherwise (never a blank-looking
guess; `services/project_qa.py`'s own `_parse_composer_findings` enforces this). Review state is a
real, closed, extensible vocabulary today holding exactly one value —
`COMPOSER_FINDING_STATE_MACHINE_UNREVIEWED` (`"Machine Finding / Unreviewed"`) — stored as
`KNOWN_COMPOSER_FINDING_STATES`, a tuple future states are added to, not a hardcoded string
comparison, so `PM-reviewed`/`accepted`/`modified`/`dismissed` are additive vocabulary changes, not
a storage-shape migration.

**Specified, not built** — deliberately, per the governing prompt's own Section 2 ("do not invent
unsupported metadata merely to fill fields") and Section 9 ("do not overbuild"):

- `discipline`/`focus` — no field exists; nothing in the current Composer evidence path grounds a
  discipline classification honestly today.
- `suggested_action` — no field exists; distinct from, and not to be conflated with, the existing
  `operational_actions` fourth-beat mechanism (Make a Task/Highlight), which already offers a real
  action without needing a new Finding-level field.
- PM review/edit/toggle/adjudication UI — `review_state` exists and is renderable, but no route or
  control changes it from `machine_finding_unreviewed` today. This is the largest concrete gap
  between the implemented grammar and the full stated invariant.

---

## 4a. Coordinator boundary and RFI authority (`CLAUDE-GO-DNA-02` addendum)

Recorded alongside `specified-unbuilt/spin-project-intelligence-preview.md`'s own probe/echo/
Task-as-probe-vehicle addendum, which preserves the Product Owner's real Roof Scupper investigation
as a canonical example and the fuller technical/commercial concurrence model — **not built, see
that document**. This section records only what is **already true of the current, implemented
code**, so the boundary is not treated as aspirational when it is in fact already enforced in two
real places:

- **GO never creates a governed record itself — already enforced, not aspirational.**
  `services/project_qa.py`'s own `BEHAVIORAL_CONTRACT`, unchanged by this record: *"You may
  suggest that something become a governed Requirement, Finding, Task, or Decision, but you never
  create one yourself — only the human project manager does that."* This is the coordinator-not-
  designer boundary in its general form; the Roof Scupper example is the concrete, human-proven
  illustration of the same rule ("could the designer review relocating this" as a question GO may
  raise, never "move the scupper" as an instruction GO may issue).
- **An RFI is never a dry unilateral machine decision — already enforced structurally, not by
  convention.** `create_rfi_draft` (`services/case_workspace.py`) hard-requires a
  `ReviewerValidation` to already exist on the underlying Finding before a draft can be created at
  all; the draft then requires its own further human review/edit before `issue_rfi_draft` moves it
  to `RFI_STATUS_ISSUED`. A human decision point exists before both drafting and issuing.
- **What is NOT enforced today, named honestly:** the single `ReviewerValidation` gate does not
  distinguish *technical* concurrence (is this a legitimate concern) from *commercial/risk*
  concurrence (should we raise it, through what channel) — the two-party consultation
  (design-authority + Construction-Management-equivalent) the Roof Scupper example demonstrates has
  no structural representation. A future concurrence-type field is named, not built — see
  `specified-unbuilt/spin-project-intelligence-preview.md`'s own addendum for the full record.

---

## 4b. "Under the hood by default, daylight on demand" (`CLAUDE-GO-DNA-07` addendum)

Recorded following a Product Owner interaction-principle clarification: GO's investigative machinery
should operate beneath the surface by default (concise finding → evidence citation → characterization
→ suggested next step), while remaining able to expose a **professional evidence trace** — never raw
model chain-of-thought — on demand for a consequential finding. **No code changes accompany this
addendum.**

**A major finding, discovered while grounding this addendum, not assumed:** most of what this
principle asks for already exists and is live, for the Case/Investigation path — this record had
not previously credited it. `explain_investigation_answer`/`explain_evidence_trust`
(`services/case_workspace.py`, `CLAUDE-MM7` "Trustworthy Answer Contract" / "Why should I trust
this?"), wired to real GET routes (`routes/api.py`, not admin-gated, matching this corpus's own
read/write authority split) and consumed live by `static/js/drawing_image_viewer.js`'s own
investigation-answer view. Verified directly: `explain_investigation_answer` is a **pure, read-time
aggregation over an `InvestigationStep`'s own `Claim`s — no new storage** — assembling exactly the
trace shape this addendum's own governing prompt asks for: evidence used (`Claim.evidence_links`),
evidence considered but excluded (`Claim.evidence_excluded` — the concrete answer to "what else did
you check"), contradiction presence (`contradiction_relationship_ids`/`CLAIM_CLASS_CONFLICTING` —
"what contradicted this"), staleness, missing-evidence/abstention claims, recommended next checks
(`Claim.recommended_next_check` — a literal "what would test this further" field), and an
`authority_boundary` value (`informational` vs `requires_human_authority`) that is itself the
coordinator-boundary signal §4a above describes. The function's own docstring already states the
"light on first touch, deep on demand" principle this Product Owner direction asks for, independently
and earlier: *"progressive disclosure... reveals more of this SAME payload in stages, rather than
three separate endpoints that could drift apart."*

**The one precise gap, confirmed by direct comparison:** `ComposerFinding` (§1/§4 above, the newer,
project-level, Composer-Q&A-driven path this record itself introduced) has **no equivalent**. It
carries `source_reference`/`concern`/`unresolved_question`/`source_message_id` — a single flat
characterization pointing at the one conversation turn that produced it — but no `evidence_links`
list, no contradiction tracking, no "what else was checked" record, and therefore no aggregation
function `explain_investigation_answer` could generalize to. A PM asking "why did you flag this?" of
a `ComposerFinding` today has only its own four text fields to read — there is no deeper trace to
reveal even if a UI control existed to request one. This is a materially different situation from
"the trace exists but isn't exposed" (true of the MM7 path) — for `ComposerFinding`, the trace itself
was never captured at write time. **Not built by this addendum** — named as the seam a future
`ComposerFinding` generalization would need to close, and the natural place to reuse
`explain_investigation_answer`'s own assembly shape rather than inventing a second one.

**What already correctly hides machinery, named per the governing prompt's own question 8:** the
Composer's own conversational turn (`services/project_qa.py`) never surfaces its prompt construction,
retrieval steps, or raw model output to the PM — only the parsed `reply_text`/`findings`/`river_actions`
result. Nothing in the current implementation over-exposes internal machinery by default; the gap is
one-sided (under-exposure for `ComposerFinding`, not over-exposure anywhere).

**Seam classification:** CURRENT (already enforced) — the MM7 Trustworthy Answer Contract itself,
its authority-boundary signal, its progressive-disclosure documentation. NEAR-TERM ACCELERATOR (not
built) — generalizing `ComposerFinding` to carry a `Claim`-shaped evidence trail (reusing
`Claim.evidence_links`'s validated-reference discipline, per `CLAUDE-GO-DNA-05`) so
`explain_investigation_answer`'s own aggregation shape could extend to it, plus a right-panel "why"
affordance surfacing that payload. SPECIFIED-UNBUILT — any full historical Spin trace UI, any
generalized "explain any finding" endpoint spanning both `Claim` and `ComposerFinding` today.

---

## 4c. "Pre-populate, never auto-execute" — one strong continuation (`CLAUDE-GO-DNA-08` addendum)

Recorded following a Product Owner interaction-principle clarification: when GO produces a grounded
finding and one clear next step is strongly implied, Composer should prepare that continuation for
the PM to adopt, edit, redirect, or ignore — never auto-execute it. **No code changes accompany this
addendum.**

**What already exists, and why neither matches this pattern, confirmed by direct inspection:**

- `river_action_stack` (`templates/_macros.html`, backed by `ProjectQAResult.river_actions`) renders
  a **ranked list of several** actions (rank/action/rationale/consequence/uncertainty/evidence), each
  in its own read-only `<details>` disclosure — explicitly documented in its own comment as "never a
  Make-Task/Tag button per item." It is informational text, not interactive, and it is a *set* of
  candidates, not the *one strong continuation* this addendum asks for.
- `operational_action_offers` (same file, backed by `message.operational_actions`) is the opposite
  failure mode: a real `<form method=post>`/submit `<button>` per offered action (`create_task_route`/
  `add_tag_occurrence_route`) that **executes immediately on click** — appropriate for its own
  low-stakes, governed-but-provisional actions (Task/Tag creation, never overwriting anything), but
  not the "lands in an editable field, PM submits when ready" shape this addendum describes.
- **The one real precedent for the actual UI mechanic ("write text into the composer input box, PM
  edits, PM submits") already exists and works today, for a different origin**: the Voice-Typer
  (`static/js/case_workspace.js`, `composerInput.value = transcript`) writes recognized speech into
  `#dock-composer-input` without auto-submitting — proving the exact interaction shape this addendum
  needs is already implemented, just never triggered from a GO-authored suggestion.
- `ConversationalTurnResult.proposed_action` (`services/conversational_turn.py`, `CLAUDE-CA1D-
  COMPOSER-SPINE-01` Stage 2) is the closest existing **proposal-envelope** shape — a `dict`,
  populated only for consequential `intent_class` values, explicitly documented as "only envelope
  construction, never execution." This is the right shape to reuse for a future "prepared
  continuation" object. It is real code, but — confirmed again here — Stage 2 remains unreached from
  any live request; Stage 3 (wiring into `interpret_message`) is still not authorized, unchanged from
  every earlier record in this corpus that has named it.

**The smallest missing seam, precisely:** there is no path today from "GO produced a grounded finding
with one clearly implied next move" to "that move's text sits in `#dock-composer-input`, editable."
Building it needs either (a) Stage 3 wiring so `proposed_action` can ever be produced from a live
turn, or (b) a `suggested_action`-shaped field on `ComposerFinding` (named as absent, not built, in
§4 above) paired with new JS reusing the Voice-Typer's own `composerInput.value = ...` pattern. Both
paths are already-named, not-yet-authorized seams — this addendum adds no third one.

**Seam classification:** CURRENT (already enforced) — the coordinator boundary that makes this safe
regardless of how it's eventually built (`BEHAVIORAL_CONTRACT`'s "never create one yourself";
`proposed_action`'s own "never execution" discipline). NEAR-TERM ACCELERATOR (not built) — reusing
the Voice-Typer's `composerInput.value` mechanic to populate one GO-suggested continuation, once
either Stage 3 or a `ComposerFinding.suggested_action` field exists to supply the text from.
SPECIFIED-UNBUILT — everything upstream of that (Stage 3 itself; `ComposerFinding.suggested_action`;
any ranking logic for choosing "the one strong continuation" over `river_actions`' existing
multi-item shape).

---

## 5. What remains specified-unbuilt (do not treat this record as authorizing it)

This record documents what is now DNA — it does **not** authorize building any of the following.
Each remains its own separate, not-yet-authorized step:

- **`CLAUDE-CA1D-COMPOSER-SPINE-01` Stage 3** (wiring `run_conversational_turn`/the Context
  Envelope/the closed `intent_class` dispatch table into `interpret_message`'s actual dispatch
  chain) and **Stage 4** (Approval-Gate proposal envelopes for consequential intents). Stages 0–2
  are implemented (shared LLM call boundary, `content_class`/`candidate_referents` schema, the
  Context Envelope + orchestrator built but not reachable from a live request) — see the Stage 0/1/
  2 commits (`15b037f`/`cbb27d6`/`861d2b3`) for their own detail; this record does not restate it.
- **The full future Spin programme** — comprehensive Machine Spin, historical Spin-set
  preservation, Pass/Build adjudication, Tool Making, custom-focus management — see
  `specified-unbuilt/spin-project-intelligence-preview.md` for the concept-preservation entry.
- **The investigative rhythm (Load → Aim → Probe → Echo → Interpret → Re-aim), Task as a directed
  probe vehicle, compound evidence, and the "wondering note" concept** — see that same document's
  `CLAUDE-GO-DNA-02` addendum, including the preserved Roof Scupper canonical example and the
  technical/commercial concurrence distinction.
- **`ComposerFinding` → real Investigation escalation.** Not built, but a real seam is identified:
  `ComposerFinding.source_message_id` already matches what the existing `needs_case:` escalation
  route (`start_investigation_from_aperture`, `routes/workspace.py`) expects as input — a future
  "escalate this machine finding" action can reuse that route directly rather than inventing a
  second escalation path.
- **`ComposerFinding` → RFI candidate.** `create_rfi_draft` hard-requires a `case_id` and an
  existing `ReviewerValidation` — neither of which a project-scoped `ComposerFinding` has. The
  Product Owner's own framing implies escalating to a real Case/Finding first (reusing the seam
  above) is the right direction, not a parallel "RFI candidate" flag on `ComposerFinding`.
- **`Overview` → Spin 01 / Initial Comprehensive Review.** `services/project_briefing.py`'s
  `matters_requiring_attention` (a flat `list[str]`, one-shot generated) is a real, existing
  precursor of narrower shape than `ComposerFinding` — not structurally compatible as a drop-in
  promotion through `add_composer_finding` (would need real translation, a prompt-schema change),
  and not attempted by this record.

---

## 6. Lineage (recorded so future agents know these evolved, not appeared unrelated)

| Primitive today | Recognized as embryonic form of |
|---|---|
| `Overview` (`services/project_briefing.py`, one-shot narrative briefing) | Spin 01 / Initial Comprehensive Review (not built — §5) |
| `Investigations`/`Case` (`InvestigationStep`, `CaseOutcome`) | The focused machine/human probe thread — already substantially real (§3), not merely a future direction |
| `Tag`/`TagOccurrence` | Evidence anchoring for findings — currently conversation-scoped only; `AddressableRegion`/`EvidenceItem` is the untapped document-level foundation (§3) |
| `Task` | Governed action projection from findings — no cross-reference field yet (§3) |
| RFI machinery (`RFIDraft`) | Professional characterization/action grammar — already contextual-by-construction (§3), gated on Case/`ReviewerValidation` existing first |

---

## 7. Tests / structural enforcement

- `tests/test_go_right_panel_01.py` (18 tests) — `ComposerFinding` persistence/validation, the
  dual-gated `findings` promotion (populated only when genuinely warranted, never for ordinary
  chat), project isolation, Toolbox rendering priority (Investigation > Document > Composer
  Findings > empty state).
- `tests/test_p40vw7a_ui_reference_map.py::RegistryConsistencyTests::
  test_every_template_data_ref_has_a_registry_row` — structurally enforces that every new
  `data-ui-ref` (including the three new `toolbox.composer-findings*` refs this record adds) has a
  matching `UI_REFERENCE_MAP.md` row; a future refactor that silently drops a right-panel
  `data-ui-ref` fails this test, not merely a visual regression.
- `services/case_workspace.py`'s `add_composer_finding` — the closed-vocabulary validation on
  `content_class`/`review_state` is itself the structural guard against an invalid/unreviewable
  state being persisted; no separate schema-validation layer exists or is needed.
- **The panel-zoning invariant (§2) now has its own structural guard** (`CLAUDE-GO-DNA-01` Part
  F.14, closing the residual this section originally recorded): `tests/test_p40vw7a_ui_reference_map.py::
  PanelZoningInvariantTests` asserts, via a ref-prefix pattern rather than fragile markup, that no
  `lists.project.(requirements|investigations|rfis|work-products|chats|tasks|tags|
  tools.remove-project)` reference can render in Lists for an open project, and separately confirms
  each relocated category is still reachable from the Toolbox. A future regression that
  reintroduces intelligence content into Lists fails this test, not merely a visual review.

---

## 8. Live verification

Live-browser-verified against a real, disposable NREOCRC specimen project (`db305ae1-2e40-4b91-
ba77-e9eb6e469783`, ingested via the real folder-establishment path — see
`tests/fixtures/nreocrc/addenda_corpus_state_002/`): a real discrepancy question through the
Composer produced 7 genuine, distinct `ComposerFinding` records in the Toolbox
(F-001–F-007) — notably F-001 correctly identified a deliberately-planted defect in the specimen
(an unreconciled standby-power-duration amendment across two Addenda) with accurate source
citations. Click-to-expand and click-to-open-source-document both confirmed working without an
unsolicited workspace snap; a different project's Toolbox showed zero leakage; an ordinary
factual question added no findings; a fresh page reload preserved the same finding set. Full
detail and the complete 10-point acceptance walkthrough: see the `CLAUDE-GO-RIGHT-PANEL-01`
implementation commit.
