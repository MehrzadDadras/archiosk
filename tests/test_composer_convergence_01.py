"""
CLAUDE-COMPOSER-CONVERGENCE-01 - one application, one interaction language.

Product Owner: "some pages are stable and coherent while others are drifting
like loose teeth... the user should not have to learn different interaction
rules page by page."

WHAT THIS FILE IS FOR

The audit that produced it is a snapshot; this file is the part that keeps
being true. It declares the interaction contract every Composer-like surface
must satisfy, checks each known surface against it, and - the part that
actually stops drift - fails when a NEW Composer-like surface appears in
templates/ without being declared here. Every previous convergence pass in this
repo could be undone by the next person adding one more box; this one cannot be
undone quietly.

THE CONTRACT (CA1 Section AC, and the Product Owner's own statement of it)

    Say anything to Composer. Press a button when you mean it.

Mechanically, for every surface that presents itself as conversational:

  - Enter submits, via an explicit binding to a named send control - never via
    the browser's implicit submission, which is positional and silent and has
    produced two live defects here already (18cac57, and
    CLAUDE-ESTABLISH-COMPOSER-ENTER-01).
  - autocomplete="off", so browser autofill cannot eat the first Enter.
  - Voice where the surface supports it, through the one shared engine.
  - Shift+Enter inserts a newline wherever the field is multiline.

WHAT IS DELIBERATELY *NOT* ASSERTED UNIFORM

Two axes genuinely differ between surfaces, and flattening them would be wrong
rather than consistent:

  - ATTACHMENT. Only the Workspace dock Composer has a + control, because only
    it sits inside a project where attached evidence has a governed home. The
    project-less surfaces cannot accept evidence without crossing what
    governance/STATUS.md keeps unauthorized. Absence of + there is a boundary,
    not drift.
  - REASONING SPINE. The dock Composer reaches run_conversational_turn; the two
    orientation surfaces reach rule-based classifiers by explicit governance
    decision (STATUS.md's Voice/Conversational Presence entry: "a new
    rule-based, non-interpret_message orientation endpoint... that never opens
    a CaseWorkspaceStore"). That difference is authorized and recorded. It is
    also the single largest remaining inconsistency the user can feel, and it
    is reported rather than silently patched.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES = _REPO_ROOT / "templates"

# Every Composer-like surface in the application, and what it is.
#   key -> (template, anchor identifying its <form>, multiline?, expects_attach?)
SURFACES = {
    "workspace-dock": ("_macros.html", 'data-ui-ref="chat.composer"', True, True),
    # CLAUDE-DEVELOPER-COMPOSER-IMAGE-01: was False. The Product Owner reached
    # for paste-a-screenshot here and found nothing - a surface that looked like
    # Composer and accepted less, which is exactly the drift this file exists to
    # catch. It now attaches.
    "developer-home": ("developer_tools.html", 'data-ui-ref="developer.home.composer.form"', True, True),
    # CLAUDE-HOME-UNIFY-01: moved to projects.html with the home destination
    # itself. This registry existing is exactly why the move could not go
    # unnoticed - test_the_registry_does_not_rot failed on the stale path.
    "home-orientation": ("projects.html", 'id="index-orientation-form"', False, False),
    "establish-project": ("upload.html", 'id="upload-orientation-form"', False, False),
}

# Markers that make a <form> Composer-like. A form carrying any of these is
# making a conversational promise to the user and owes the contract above.
_COMPOSER_MARKERS = (
    "data-developer-composer-form",
    "conversation-dock-composer",
    "gateway-orientation-form",
    "developer-home-composer-form",
)


def _form_html(text: str, anchor: str) -> str:
    i = text.index(anchor)
    start = text.rindex("<form", 0, i)
    return text[start:text.index("</form>", i) + len("</form>")]


def _open_tag(form_html: str) -> str:
    return form_html[:form_html.index(">") + 1]


def _read(name: str) -> str:
    return (_TEMPLATES / name).read_text(encoding="utf-8")


class EveryComposerSurfaceHonoursTheContract(unittest.TestCase):
    """One rule, checked the same way on every surface."""

    def _each(self):
        for key, (template, anchor, multiline, attach) in SURFACES.items():
            html = _form_html(_read(template), anchor)
            yield key, html, multiline, attach

    def test_enter_is_bound_explicitly_everywhere(self):
        for key, html, _, _ in self._each():
            with self.subTest(surface=key):
                self.assertIn("data-developer-composer-form", _open_tag(html))

    def test_every_surface_names_its_own_send_control(self):
        # The shared primitive falls back to two hardcoded refs. A surface that
        # matches neither and declares nothing would bind Enter to nothing at
        # all - silently, which is how this class of defect always arrives.
        default_refs = ('data-ui-ref="chat.composer.send"',
                        'data-ui-ref="developer.home.composer.send"')
        for key, html, _, _ in self._each():
            with self.subTest(surface=key):
                declared = "data-composer-send=" in _open_tag(html)
                matches_default = any(ref in html for ref in default_refs)
                self.assertTrue(declared or matches_default,
                                "%s binds Enter to no resolvable control" % key)

    def test_the_declared_send_control_exists_and_is_a_submit_button(self):
        for key, html, _, _ in self._each():
            open_tag = _open_tag(html)
            if "data-composer-send=" not in open_tag:
                continue
            with self.subTest(surface=key):
                ref = open_tag.split("data-composer-send='")[1].split("'")[0]
                ref = ref.split('data-ui-ref="')[1].split('"')[0]
                # Search the form BODY - the opening tag carries the selector.
                body = html[html.index(">") + 1:]
                needle = 'data-ui-ref="%s"' % ref
                self.assertIn(needle, body, "%s names a control it does not contain" % key)
                tag = body[body.rindex("<button", 0, body.index(needle)):]
                self.assertIn('type="submit"', tag[:tag.index(">") + 1])

    def test_browser_autofill_cannot_eat_the_first_enter(self):
        for key, html, _, _ in self._each():
            with self.subTest(surface=key):
                field = re.search(r"<(input|textarea)[^>]*data-developer-composer-input[^>]*>", html)
                self.assertIsNotNone(field, "%s has no composer input" % key)
                self.assertIn('autocomplete="off"', field.group(0))

    def test_multiline_surfaces_use_a_textarea_so_shift_enter_can_work(self):
        # Shift+Enter is meaningful only where a newline can exist. The shared
        # primitive already passes Shift+Enter through untouched, so this is the
        # only thing left to assert per surface.
        for key, html, multiline, _ in self._each():
            with self.subTest(surface=key):
                self.assertEqual("<textarea" in html, multiline)

    def test_attachment_is_present_exactly_where_evidence_has_a_home(self):
        for key, html, _, attach in self._each():
            with self.subTest(surface=key):
                self.assertEqual("composer-attach" in html, attach)


class NoNewSurfaceCanDriftInSilently(unittest.TestCase):
    """The part that keeps this true after today."""

    def test_every_composer_like_form_in_templates_is_declared_above(self):
        declared_anchors = [a for _, a, _, _ in SURFACES.values()]
        undeclared = []
        for path in sorted(_TEMPLATES.rglob("*.html")):
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"<form[^>]*>", text):
                tag = match.group(0)
                if not any(marker in tag for marker in _COMPOSER_MARKERS):
                    continue
                if any(anchor in tag for anchor in declared_anchors):
                    continue
                undeclared.append("%s: %s" % (path.name, tag[:120]))
        self.assertEqual(undeclared, [],
                         "A Composer-like form is not declared in SURFACES. Add it "
                         "and make it satisfy the contract, or give it a recorded "
                         "exception - do not delete this assertion.")

    def test_the_registry_does_not_rot(self):
        # A declared surface that no longer exists would make every contract
        # assertion above vacuous for it.
        for key, (template, anchor, _, _) in SURFACES.items():
            with self.subTest(surface=key):
                self.assertIn(anchor, _read(template))


class VoiceWiringIsScopedToItsOwnComposer(unittest.TestCase):
    """A regression guard for a trap this convergence created."""

    def test_the_developer_composer_voice_targets_its_own_form(self):
        # index.html renders two composers, orientation first. The Developer
        # Composer's voice wiring used a document-wide querySelector for
        # '[data-developer-composer-form] [data-developer-composer-input]',
        # which was harmless only while the orientation form lacked those
        # attributes. Converging it turned that selector into a live
        # cross-wiring bug: the Developer Composer's microphone would have
        # typed into the orientation field.
        text = _read("index.html")
        self.assertNotIn(
            "querySelector('[data-developer-composer-form] [data-developer-composer-input]')",
            text)
        self.assertIn(".developer-home-composer-form [data-developer-composer-input]",
                      text)

    def test_each_composer_still_has_exactly_one_voice_button(self):
        for key, (template, anchor, _, _) in SURFACES.items():
            html = _form_html(_read(template), anchor)
            with self.subTest(surface=key):
                self.assertEqual(html.count("voice-input-button"), 1)


class RecordedExceptions(unittest.TestCase):
    """Surfaces that look adjacent but are deliberately NOT composers."""

    def test_signin_voice_is_navigation_not_conversation(self):
        # login.html has a voice button and no conversational field. It steers;
        # it never converses. Asserting this keeps a future reader from
        # "converging" a sign-in page into a chat surface.
        text = _read("login.html")
        self.assertIn('data-ui-ref="auth.signin.voice"', text)
        self.assertNotIn("data-developer-composer-form", text)
        self.assertNotIn("composer-attach", text)


if __name__ == "__main__":
    unittest.main()
