# Specified But Unbuilt — Voice Output / Read-Aloud

**Status: NOT AUTHORIZED. Studio Voice (third-party speech egress) is
shelved INDEFINITELY, 2026-09-04, by Product Owner decision. Device Voice
(browser-local) is not authorized either, and may return only as an
isolated, policy-gated increment with narrowed guards — never by reviving
the shelved work wholesale.**

Working code exists and is preserved in `git stash` (`stash@{0}`, base
commit `a8cfc0b`, 10 files). It is provisional, not project truth: this
record is what governs.

## 0. What was built, and why it is not in the tree

A dual-mode read-aloud controller for workspace briefings and findings:

- **Device Voice** — `window.speechSynthesis`, entirely local, no network,
  no dependency, click-triggered, opt-in, persisted in `localStorage`,
  defaulting to browser mode.
- **Studio Voice** — `POST /projects/<id>/tts` → `services/tts.py` →
  OpenAI `audio.speech.create` (`tts-1`, voice `onyx`), returning MP3.

The two share a UI but have completely different risk profiles, and are
**not to be revived together**.

## 1. Why it was shelved, in order of seriousness

1. **Evidence egress.** The route sent governed project text — briefings
   and findings — to a third party under `@login_required` +
   `_load_workspace_or_404` alone. It referenced
   `ACTION_EXTERNAL_AI_REQUEST` zero times, where every other external
   call in this codebase is policy-gated through
   `_external_ai_status`/`evaluate_action`.
2. **A third provider outside the one shared boundary.**
   `services/tts.py` constructed an OpenAI client directly, bypassing
   `services/llm_gateway.py` — documented as "the one shared model call
   boundary", whose `KNOWN_PROVIDERS` is Anthropic + Gemini.
3. **An undeclared dependency.** `openai==1.109.1` was added without
   running `tools/dependency_fit.py`, which `CLAUDE.md` requires before
   proposing one.
4. **A user-facing honesty claim would have become false.**
   `services/capability_registry.py`'s `voice_input` entry tells users
   ARCHIOSK "cannot speak its own replies aloud" and records voice OUTPUT
   as "a separate, unimplemented capability". Shipping read-aloud without
   updating that entry would have made the product misdescribe itself.

## 2. What this is NOT

It is **not** a violation of `CLAUDE-MOBILE-Q-TRIAL-01`'s speech
prohibition in substance, and that distinction is preserved deliberately
so a future reader does not repeal the wrong rule.

That prohibition is about **automatic brand speech** — the Product Owner's
words were "do not play an automatic welcome sound. Do not automatically
speak ARCHIOSK. The current brand pronunciation is not accepted and wrong
pronunciation creates distrust. Voice must remain opt-in." The shelved
code is click-triggered only, never speaks the brand or a welcome, and
defaults to the local mode. It tripped the guard's **wording**, not the
Product Owner's **concern**.

Repealing the speech prohibition to admit read-aloud would therefore be
repealing the wrong rule, and would re-admit the auto-welcome that was
actually rejected.

## 3. The guard blind spot this exposed, now closed

`test_no_static_script_can_produce_speech` and
`test_no_file_anywhere_still_holds_a_synthesis_seam` scan `static/js` for
`speechSynthesis`/`SpeechSynthesisUtterance`. They caught Device Voice —
the fully local, network-free half — and were **silent on Studio Voice**,
which contains neither string and shipped project text to OpenAI.

The guard caught the harmless half and missed the dangerous one. Deleting
`browserSpeak` alone would have turned the suite green with the egress
still in place.

Closed by `tests/test_external_provider_boundary_01.py`, which guards what
those tests could not see: outbound audio/speech-synthesis endpoints in
server-side code, and provider-SDK imports outside a declared allowlist.

## 4. Conditions for any future Device Voice increment

Not a design, and not authorization. If read-aloud is revisited:

- **Device Voice only**, as its own increment. Local synthesis, no
  network, no new dependency, no provider.
- **The guard is narrowed, not removed** — from "no synthesis anywhere" to
  "no automatic speech, no brand speech", matching the Product Owner's
  original words. Automatic playback and brand pronunciation stay
  prohibited.
- **`capability_registry.py`'s `voice_input` entry is updated in the same
  change**, so the product never claims a capability boundary it no longer
  has.
- **Studio Voice remains out.** Any third-party speech egress requires its
  own authorization, `tools/dependency_fit.py`, integration through
  `llm_gateway.py` or a recorded exception, and
  `ACTION_EXTERNAL_AI_REQUEST` gating — the same gate every other external
  call already passes.

## 5. Lineage

- **Authority:** Product Owner decision, 2026-09-04, recorded the same day.
- **Preserved work:** `git stash@{0}`, base `a8cfc0b` — provisional, never
  citable as project truth.
- **Related:** `CLAUDE-MOBILE-Q-TRIAL-01` Section 6 (unamended and still
  governing), `services/llm_gateway.py`, `ACTION_EXTERNAL_AI_REQUEST`,
  `services/capability_registry.py`'s `voice_input`.
