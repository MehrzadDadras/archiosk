# Specified But Unbuilt — Governed Voice / Conversational Presence

**Status:** Specified, not implemented. Zero code exists for anything in this document — no
speech/audio library, no microphone permission handling, no dependency of any kind. Recorded
under `CLAUDE-FUTURE-VOICE-A1`/`CLAUDE-FUTURE-VOICE-REC1` (2026-08-07), following a
repository-grounded architecture investigation performed after the accepted Camel MM1–MM9
close-out (`d7df9a3`) and the accepted CLAUDE-POSTCAMEL-P01 pilot-readiness seal (`9b4b845`).
**GO LATER** — see Section 11 below for why, and for the smallest safe future prototype.

**Relationship to the rest of this governance corpus.** This document is new; it does not
duplicate an existing one. It assumes, and does not restate, `specified-unbuilt/
external-intelligence-airlock.md` (the one existing boundary Voice's own Level 5/external actions
must cross, never bypass) and the real, already-implemented primitives named throughout this
document (`Anchor`, the Approval Gate, `GovernanceLog`, `can_access_project`,
`ACTION_EXTERNAL_AI_REQUEST`) — see `current/kernel-object-model.md` for their ground-truth
detail. `CLAUDE-FUTURE-DT1-A1` (2026-08-07, also unimplemented, also **GO LATER**) recorded a
future read-only Engineering Observatory; Section 10 below records how the two relate. Neither
this document nor DT1's own recommendation authorizes building anything.

**No implementation implied.** Nothing here authorizes adding a speech/audio dependency,
microphone handling, a new persistence model, a new confirmation mechanism, or any UI surface.
This document exists so a future session does not have to re-derive this reasoning from scratch,
and so no future session bolts on a generic voice assistant, an ambient recorder, or a parallel
governance system for lack of a recorded design intent to consult first.

---

## 1. Architectural purpose

ARCHIOSK may later support a governed Voice / Conversational Presence layer. Voice must not
become: an ambient recorder; a generic smart-speaker assistant; a parallel governance system; an
uncontrolled command surface; a project-record generator merely because speech occurred; an
authority bypass; a cross-project memory path; or an Airlock bypass. The intended experience is
closer to **a quiet, contextually aware professional colleague whose listening state,
intervention, and authority remain legible to the user** — not a consumer smart speaker, not a
chatbot that talks constantly, not an omniscient assistant, not a voice-controlled shell.

## 2. Core principles

> **Spoken thought ≠ project record**
> **Understanding ≠ authority**
> **Awareness ≠ intervention**
> **Internal context ≠ permission to cross the Airlock**
> **Voice may make interaction easier; it must not make authority easier.**

Voice inherits the same authentication, project isolation, governance, approval, provenance, and
external-boundary restrictions as the equivalent mouse/keyboard action, at every authority level.
These principles were tested against the current repository during `CLAUDE-FUTURE-VOICE-A1` and
found sound — none needed to be modified, split, or rejected.

## 3. One interaction engine, multiple authority/behaviour profiles

**Voice-Typer**, **Ushering Agent**, and **Shoulder Counsellor** are not three separate AI engines
or duplicate code paths — they are profiles/authority ceilings over one governed interaction
engine, mirroring how `services/conversation_interpreter.py`'s `interpret_message` already
produces one intent vocabulary (`analysis`/`compare`/`rfi_intent`/`correction`/
`discussion_contribution`/`anchor_acknowledged`/`none`) rather than separate parsers per behavior.

- **Voice-Typer** (lowest authority): speech → transcription → active text/draft field → human
  review/edit → ordinary submission. Does not reinterpret dictation into project decisions or
  silently create governed artifacts. Authority ceiling ≈ Level 0–1 (Hear/Understand); the human
  still submits through the ordinary UI.
- **Ushering Agent**: contextual navigation/orientation — open a drawing, show an associated
  requirement, navigate to a finding, show/hide a panel. Limited to safe, reversible local
  actions; creates no project records. Authority ceiling ≈ Level 3.
- **Shoulder Counsellor**: an advisory/intervention *policy* layered over the same engine, not a
  fourth code path — recognizes contradictions, evidence gaps, stale evidence, unsupported claims,
  missing requirements. Never automatically modifies durable project state. Reuses ARCHIOSK's
  existing domain severity/classification (Section 10) rather than inventing an independent AI
  severity taxonomy. Preserve: **the system can be aware of something without being compelled to
  speak.**

## 4. Listening state and interaction profile are different dimensions

**Microphone/recognizer lifecycle** (always visibly rendered, never a state the user has to
wonder about): `OFF → LISTENING → PROCESSING → RESPONDING → ERROR`. First architecture requires:
deliberate start; immediate stop; cancellation; a visible processing state; a visible error state;
clearing/stopping on project switch; stopping on logout/session timeout; safe behavior on
tab/background. **Always-listening/ambient operation is explicitly excluded from the first
architecture.**

**Interaction profile** (Voice-Typer / Ushering / Counsellor) is a separate, independently-selected
dimension — changing the active profile must never implicitly turn the microphone on or change the
listening lifecycle.

## 5. Ephemeral → governed-record lifecycle

- **Tier 1 — Raw audio.** Never persisted by default; discarded as soon as practical after
  transcription. No repository evidence justifies a future exception to this default.
- **Tier 2 — Ephemeral transcript/spoken thought** (brainstorming, incomplete thoughts,
  self-correction, casual conversation, spoken navigation, working reasoning). Held only in
  session/in-memory state; never written to the durable project record; never enters
  `GovernanceLog` merely because it was spoken.
- **Tier 3 — Promoted governed record** (task, note, requirement annotation, finding, risk,
  investigation, Work Product entry, RFI draft, a future Presentation Obligation, or any other
  durable project object). Promotion reuses the **same** forms/routes, the **same**
  `content_class` provenance vocabulary (an AI-touched promotion stays `ai_proposed`, never
  silently `human_authored`), the **same** human review, the **same** Approval Gate, and the
  **same** `GovernanceLog` an equivalent mouse-driven action already uses. **No separate Voice
  persistence model should be created merely for convenience.**

## 6. Future Voice authority ladder

| Level | Name | Examples | Confirmation |
|---|---|---|---|
| 0 | Hear | Capture speech only while explicit listening is active | — |
| 1 | Understand | Interpret the utterance within authorized contextual scope | — |
| 2 | Suggest | Advice, questions, warnings, explanations, navigation guidance | No state change |
| 3 | Reversible local action | Navigate, open, scroll, select, show/hide, change visible focus | No durable mutation |
| 4 | Governed project mutation | Create/promote a task, update a finding, create a risk, assign a Work Product section | **Always required** — reuse the existing Approval Gate (`confirm=once|session|no`), never a Voice-specific mechanism |
| 5 | External boundary action | Read calendar, search authorized email, draft outbound correspondence, send/change external information | **Always required, plus the Airlock's own gate** |

Voice must never receive a *lower* confirmation bar than the mouse/keyboard equivalent already
requires. Levels 4 and 5 must never execute directly from speech alone, regardless of stated
confidence.

## 7. Existing ARCHIOSK primitives to reuse (found during the repository audit, not hypothetical)

- **`Anchor`** (`anchor_type`/`anchor_id`/`source_id`/`location`/`description`,
  `services/case_workspace.py`) — already used by `ConversationMessage` and `ReviewThread` to
  record "what the sender was actually looking at," already populated client-side by
  `static/js/case_workspace.js` on a "Discuss this X" click. **The strongest existing precedent
  for the future Context Envelope's active-selection tier** — not a mechanism to invent, one to
  reuse.
- **Session-scoped recent referent** — `session[f"focused_finding:{project_id}"]`, read/written by
  `_run_conversation_turn`/`interpret_message` today, is the existing precedent for short-term
  references ("this," "that," "the previous one").
- **Conversation intent interpretation** — `interpret_message`'s heuristic classification is the
  precedent for classifying Voice intent, not a reason to build a wholly separate Voice NLU
  architecture.
- **The Approval Gate** (`_require_approval`, `confirm=once|session|no`, already gating RFI issue
  and Work Product issue) — the one confirmation mechanism Level 4/5 actions must reuse.
- **`GovernanceLog`** — the one audit mechanism; no second, Voice-specific audit trail.
- **`can_access_project`/project isolation** — Voice remains subject to the same deny-by-default
  checks as every other surface.
- **`services/security_policy.py`'s `ACTION_EXTERNAL_AI_REQUEST`** (currently `DECISION_DENY` at
  floor and baseline) — the one existing gate on anything leaving a project's own governed
  content; the future Airlock is what a later `DECISION_ALLOW` state would need to do before such
  a request could be constructed at all. Voice must cross exactly this gate, never a
  Voice-specific outbound path.

No new governance primitive is needed to reach a first prototype — only new orchestration wiring
these together.

## 8. Context envelope

A governed Context Envelope should resolve by **narrowest-first order**, never by unrestricted
availability:

**active selection / `Anchor`** → **active document or current view** → **current project** →
**broader authorized project corpus**

Never broaden into another project merely because a conversational reference is ambiguous.
Possible future contents: current project; active document; page/sheet/worksheet/future slide;
active selected object or region; active requirement; investigation/finding; current Work
Product; visible comparison surfaces; recent relevant project-scoped conversational reference;
actions the current user is permitted to perform. The envelope is an authorization-aware
contextual *view*, not unrestricted memory.

## 9. Referent resolution and abstention

If context yields one clear referent, resolve normally. If more than one plausible referent
exists, present the candidates or ask a short clarification (mirroring the Reviewer Validation
gate's own "Needs Evidence" option, not a guess). If no reasonable referent exists, **abstain
explicitly**, reusing ARCHIOSK's existing honest-abstention tone (already live-verified during
CLAUDE-POSTCAMEL-P01: "not covered by this project's extracted evidence... treat this as a
starting point, not a complete answer") rather than a more confident invented Voice persona.
**Ambiguous references must never silently execute a consequential project mutation.**

## 10. Intervention model

Provisional ladder, subject to later validation: **Silent → Passive indicator → Non-blocking
suggestion → Spoken interruption → Governed blocking warning.** Severity should be driven by
vocabulary the domain model already has — a genuine `contradicts` relationship (MM6) or a
`stale_evidence`/`conflicting` claim state (MM7) is already a classified signal that can map to
"non-blocking suggestion" or above; a merely-novel observation with no such classification should
default to "passive indicator." Avoid a separate, generic AI "importance score" unless later
evidence justifies one. The Counsellor should not repeat an issue the user has already
acknowledged (checkable against existing Reviewer Validation/`ReviewThread` state). Preserve:
**the system can be aware of something without being compelled to speak.**

## 11. Human-factors boundary

Designed for a professional Design-Build environment, not a consumer smart speaker. Concerns to
design against: excessive talking; interruption fatigue; background conversation; accidental
commands; mid-sentence corrections; partial utterances; speech-recognition error; technical
terminology; noisy site/meeting conditions; privacy; perceived surveillance. First implementation
should require an explicit end-of-utterance or equivalent deliberate completion signal before
interpreting any consequential command, and should rate-limit spoken interruptions per session
(reusing the existing `flask-limiter` infrastructure's own pattern as precedent for "same
mechanism shape, new bucket," not a new throttling system).

## 12. Spoken output

**Text-only response for the first architecture.** Spoken output should later be optional,
independently controlled from listening state (never automatically active merely because the
microphone is enabled), and suitable for shared-room/meeting/headset use. Nothing in the
repository's own product identity argues for defaulting spoken replies on.

## 13. Meeting/multi-person boundary

Strong separation, preserved for the first architecture:

- **Single-user Voice interaction** — current future scope.
- **Meeting capture/transcription** — explicitly **not** part of the first architecture.
- **Multi-speaker conversational intelligence** — a separate, materially higher-risk future
  architecture, if ever pursued at all.

Voice-Typer/Counsellor development must never silently become a meeting-recording system. The
`LISTENING` state model in Section 4 (deliberate start required) already structurally prevents
ambient capture; no additional speaker-distinguishing mechanism should be built for the first
architecture.

## 14. Airlock/authorized external sources

Future pipeline: **voice utterance → intent → ARCHIOSK authorization → authorized context →
Airlock → authorized external connector → sanitized result → ARCHIOSK response.** Voice never
directly reaches email/calendar/other external systems — it adds an intent-classification step
*before* the existing `ACTION_EXTERNAL_AI_REQUEST` gate, never a parallel path around it. At least
three separate future authority classes, not one "external access" flag:

- **Read** ("what's on my calendar tomorrow?")
- **Draft** ("draft an email to the structural consultant" — not sent)
- **External mutation/send** ("move the meeting," "send that email")

A read and a send are not equivalent-consequence actions and must not share one permission.
**Internal contextual awareness is not authorization to cross the Airlock.**

## 15. Engineering Observatory relationship

`CLAUDE-FUTURE-DT1-A1` recommended **GO LATER** for a future read-only Engineering Observatory —
not implemented, not authorized here either. Such an Observatory could later surface discrete,
already-classified Voice state (never private chain-of-thought): mic/listening state, recognizer
state, current context envelope, resolved referent, classified intent, authority level,
intervention level, promotion target, Airlock decision, and timing/error state. Every item listed
is a discrete state value (e.g. `action_taken`, `confidence`, `content_class`), not free-text
reasoning — this is what makes it safe to expose to a future Observatory at all.

## 16. Multimodal compatibility

Voice should eventually reference currently-visible multimodal objects (a PDF page/region, a
drawing sheet/region, an image, a spreadsheet worksheet/cell/range) via the **existing** stable
MM1–MM9 evidence/object identifiers (`AddressableRegion`/`EvidenceItem`/`Source`) — "what is this
dimension" resolves against the current drawing's active region exactly as `Anchor` already
resolves conversational references today. **No Voice-specific duplicate object-identity model
should be created.**

## 17. Future Presentation/PowerPoint compatibility

A separate future Presentation architecture has been identified but not designed or authorized.
Voice should eventually generalize to slide-level context ("this slide," "the previous client
slide," "compare this client briefing statement with our current presentation") the same way it
generalizes to drawings/spreadsheets today. **Gap found, not filled**: no per-slide addressable
unit currently exists; the same `StructuralUnit`/`AddressableRegion` pattern MM2–MM5 already
established would likely generalize to slides without a new kernel primitive, but this is a note
for whoever eventually scopes that programme, not something designed or built here.

## 18. Provisional implementation sequence (not started)

**VOICE-1** (Voice-Typer/push-to-dictate into an existing composer field — no new project
authority; validates microphone/recognizer/browser/platform/latency/vocabulary/privacy questions)
→ **VOICE-2** (contextual Ushering/navigation — validates referent resolution below the durable-
mutation line) → **VOICE-3** (ephemeral conversational interaction) → **VOICE-4** (Shoulder
Counsellor) → **VOICE-5** (governed local actions via existing governance/approval mechanisms) →
**VOICE-6** (governed promotion into durable record) → **VOICE-7** (optional spoken output) →
**VOICE-8** (Airlock-connected external awareness/actions). Numbering and staging remain
provisional until real implementation planning begins; `CLAUDE-FUTURE-VOICE-A1`'s own analysis
noted that Ushering (VOICE-2) may be safer to build before general ephemeral conversation
(VOICE-3), since Ushering stays below the durable-mutation line while open conversation
immediately raises the referent-resolution and intervention questions above.

## 19. Unresolved technical decision (for later dependency-fit investigation)

The first major question for any later prototype is the **speech-recognition architecture**:
browser-native, local/on-device, server-side, external/cloud, or hybrid. A later investigation
must run this through `tools/dependency_fit.py` and separately consider: browser support
(Windows/Chrome/Edge); privacy; audio transport; latency; offline operation; transcription
confidence; Design-Build terminology; language/accent handling; security; and **whether sending
audio to an external speech provider itself constitutes an Airlock-controlled boundary crossing**
— not resolved here; flagged as the first question any prototype must answer. No vendor or
technology is selected by this document.

## 20. Current programme decision

**GO LATER.** This does not mean the Voice concept was rejected — the architecture is coherent
with existing ARCHIOSK governance, and unusually many required primitives (Section 7) already
exist, tested, ready to reuse. Implementation is deferred because: no speech dependency/platform
approach has been vetted (Section 19); the Engineering Observatory that would help develop and
explain Voice remains itself GO LATER/unbuilt (Section 15); `CLAUDE-POSTCAMEL-P01` has just
established a pilot-ready baseline; and Voice would introduce a new user-interface surface and a
new browser capability (microphone access) immediately before independent pilot evidence exists.
The smallest safe future prototype remains **VOICE-1 — explicit push-to-dictate into an existing
text/composer field**, which requires no new authority model, no context envelope, and no
intervention logic.
