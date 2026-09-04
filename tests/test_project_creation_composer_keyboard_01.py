"""
CLAUDE-ESTABLISH-COMPOSER-ENTER-01 - Enter submits the project-creation help
composer's question.

Live Product Owner report, made twice, on archiosk.com: on Establish a Project,
typing a question into "Ask Archiosk about this form" and pressing Enter did
nothing. The Ask button appeared to be the only submit path.

WHY A REAL BROWSER, AND NOT A MARKUP ASSERTION

Because the markup was already correct. Before this change the form had one
text field, one submit button, no competing earlier submit button, and correct
form association in the parsed DOM - every precondition the HTML Standard's
implicit-submission rule needs. A source-text test asserting those facts would
have passed on the broken page. The only assertion that can tell "this should
submit" apart from "this does submit" is a real key press in a real engine,
which is what the Product Owner's report is about.

So this presses a genuine Enter in a genuine Chromium, against the genuine
Flask-rendered page and the genuine, unmodified static/js file read off disk.
Following this repo's established convention (see
test_p40vw7b_qa3_header_topbar_stacking_fix.py): set_content(), no HTTP server,
hermetic, and a clean skip - never a silent pass - when the browser is absent.

WHAT IT DOES NOT CLAIM

It does not reproduce the original failure, and that was checked rather than
assumed: with the repair reverted, every browser test below still passed.
Chromium submits this form on Enter with the original markup. So these are
forward regression guards, not proof that the live defect is fixed - the
distinction matters, because a green run here is not evidence the Product
Owner's browser now behaves.

What the repair rests on instead is that the field was relying on implicit
submission, which is positional and silent and has already produced one live
defect in this codebase, plus one correlation that survived checking: both
composers that work carry autocomplete="off" and an explicit Enter binding, and
both that were reported broken had neither. See
test_browser_autofill_is_off_on_the_question_field for the mechanism.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PRIMITIVE = _REPO_ROOT / "static" / "js" / "developer_composer_input.js"

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - environment-dependent
    sync_playwright = None


def _real_chromium_available() -> bool:
    if sync_playwright is None:
        return False
    try:
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        return True
    except Exception:
        return False


_BROWSER_AVAILABLE = _real_chromium_available()
_SKIP_REASON = (
    "Real Chromium (the `playwright` package + a downloaded browser) is not "
    "available here. This test's whole value is a genuine key press; a markup "
    "assertion would have passed on the broken page, so skip rather than "
    "substitute a weaker check."
)

# Enough of a stub that the page's own fetch() never leaves the browser and the
# call is observable. The real endpoint is covered by
# tests/test_voice_gateway_orientation.py; what matters here is only whether a
# key press reaches it at all.
#
# Only calls to the orientation endpoint are recorded; anything else gets an
# inert resolved promise. Playwright drives the page through an injected
# utility script that itself probes with fetch(null), so a blanket spy records
# the harness's own traffic and inflates every count below - and delegating
# that probe to the real fetch throws, because null is not a URL.
_FETCH_STUB = """
window.__asked = [];
window.__inert = function () {
    return Promise.resolve({json: function () { return Promise.resolve({}); }});
};
window.fetch = function (url, opts) {
    var u = String(url);
    if (u.indexOf('orientation') === -1) return window.__inert();
    var body = opts && opts.body;
    var get = function (k) {
        return (body && typeof body.get === 'function') ? body.get(k) : null;
    };
    window.__asked.push({url: u, message: get('message'), context: get('context')});
    return Promise.resolve({json: function () { return Promise.resolve({text: 'stubbed reply'}); }});
};
"""

_SEND_ATTR = "data-composer-send='"


def _rendered_upload_page() -> str:
    import app as app_module
    from models import User, db

    flask_app = app_module.create_app("testing")
    with flask_app.app_context():
        db.session.add(User(username="kbd_probe",
                            password_hash=generate_password_hash("x"), role="admin"))
        db.session.commit()
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "kbd_probe"
        sess["role"] = "admin"
    return client.get("/upload").get_data(as_text=True)


def _help_form_tag(body: str) -> str:
    i = body.index('id="upload-orientation-form"')
    return body[body.rindex("<form", 0, i):body.index(">", i) + 1]


def _help_form_html(body: str) -> str:
    i = body.index('id="upload-orientation-form"')
    return body[body.rindex("<form", 0, i):body.index("</form>", i)]


class MarkupContractTests(unittest.TestCase):
    """Cheap guards for the wiring the browser test depends on."""

    def setUp(self):
        self.body = _rendered_upload_page()

    def test_the_help_form_opts_in_to_the_shared_primitive(self):
        tag = _help_form_tag(self.body)
        self.assertIn("data-developer-composer-form", tag)
        self.assertIn("data-composer-send", tag)

    def test_the_declared_send_selector_matches_a_real_enabled_submit_button(self):
        # A typo in the selector would leave Enter silently dead again - the
        # exact class of failure being repaired - and nothing else would notice.
        tag = _help_form_tag(self.body)
        selector = tag.split(_SEND_ATTR)[1].split("'")[0]
        ref = selector.split('data-ui-ref="')[1].split('"')[0]

        # Search AFTER the form's own opening tag: that tag carries the
        # selector, so the first occurrence of the ui-ref in the form HTML is
        # the attribute naming the button, not the button.
        form_html = _help_form_html(self.body)
        body_html = form_html[form_html.index(">") + 1:]
        needle = 'data-ui-ref="%s"' % ref
        self.assertIn(needle, body_html)
        open_tag = body_html[body_html.rindex("<button", 0, body_html.index(needle)):]
        open_tag = open_tag[:open_tag.index(">") + 1]
        self.assertIn('type="submit"', open_tag)
        self.assertNotIn("disabled", open_tag)

    def test_the_input_is_marked_as_the_composer_input(self):
        i = self.body.index('id="upload-orientation-input"')
        tag = self.body[self.body.rindex("<input", 0, i):self.body.index(">", i) + 1]
        self.assertIn("data-developer-composer-input", tag)

    def test_browser_autofill_is_off_on_the_question_field(self):
        # The leading hypothesis for the live report, and the only one that
        # survived checking. Both composers that work (the Workspace chat dock
        # and the Developer Composer) carry autocomplete="off"; both orientation
        # composers, the ones reported broken, did not.
        #
        # Mechanism: this field is name="message" in a GET form with no action,
        # so any native submission writes ?message=... into the URL and the
        # browser starts offering saved values for it. When that dropdown is
        # open, the first Enter dismisses or accepts the suggestion instead of
        # submitting - which looks exactly like "Enter does nothing", is
        # per-browser and per-history, and therefore does not reproduce in a
        # clean automated browser. Unproven, but it explains every observation.
        i = self.body.index('id="upload-orientation-input"')
        tag = self.body[self.body.rindex("<input", 0, i):self.body.index(">", i) + 1]
        self.assertIn('autocomplete="off"', tag)

    def test_the_send_button_is_still_there(self):
        # The repair adds a keyboard path; it removes no pointer path.
        self.assertIn('data-ui-ref="upload.help.submit"', self.body)
        self.assertIn(">Send</button>", self.body)

    def test_the_shared_primitive_still_defaults_for_forms_that_declare_nothing(self):
        # The Workspace chat dock and Developer Composer never declare a send
        # ref; generalizing the selector must not have orphaned them.
        source = _PRIMITIVE.read_text(encoding="utf-8")
        self.assertIn('data-ui-ref="chat.composer.send"', source)
        self.assertIn('data-ui-ref="developer.home.composer.send"', source)
        self.assertIn("getAttribute('data-composer-send')", source)


@unittest.skipUnless(_BROWSER_AVAILABLE, _SKIP_REASON)
class RealKeyboardSubmissionTests(unittest.TestCase):
    """A real Enter, in a real engine, on the real page."""

    @classmethod
    def setUpClass(cls):
        cls.html = _rendered_upload_page()
        cls.primitive = _PRIMITIVE.read_text(encoding="utf-8")

    def _page(self, browser):
        page = browser.new_page()
        page.set_content(self.html)
        # The page's own inline wiring already ran with set_content; the shared
        # primitive normally arrives via a <script src> at the end of base.html,
        # which set_content does not fetch. Inject the real file, unmodified.
        page.add_script_tag(content=self.primitive)
        page.evaluate("document.getElementById('upload-help').open = true")
        # Stub LAST, on purpose: add_script_tag is itself implemented with
        # fetch(), so installing the spy earlier records Playwright's own
        # internal call and every count below is off by one. Neither the page's
        # handler nor the primitive calls fetch at bind time, so nothing real
        # is missed by waiting.
        page.evaluate(_FETCH_STUB)
        return page

    def test_enter_submits_the_question(self):
        question = ("If I am the architect and the CM, what would be the right "
                    "way to register this new project?")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = self._page(browser)
            page.fill("#upload-orientation-input", question)
            page.press("#upload-orientation-input", "Enter")
            page.wait_for_function("window.__asked && window.__asked.length > 0", timeout=5000)
            asked = page.evaluate("window.__asked")
            browser.close()
        self.assertEqual(len(asked), 1)
        self.assertEqual(asked[0]["message"], question)
        # The establish-project classifier, not project navigation.
        self.assertEqual(asked[0]["context"], "establish-project")

    def test_enter_does_not_navigate_away(self):
        # The failure a user would see if the inline handler never bound:
        # native GET submission reloads the page and the typed question is
        # lost. Assert the field survives the key press.
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = self._page(browser)
            page.fill("#upload-orientation-input", "does this navigate")
            page.press("#upload-orientation-input", "Enter")
            page.wait_for_function("window.__asked && window.__asked.length > 0", timeout=5000)
            still_there = page.evaluate(
                "document.getElementById('upload-orientation-input').value")
            browser.close()
        self.assertEqual(still_there, "does this navigate")

    def test_a_second_question_also_submits(self):
        # The shared primitive latches a `submitting` flag. If it were not
        # released on a fetch-based composer - which never navigates away to
        # clear it - Enter would work exactly once and then be dead, a
        # regression indistinguishable from the original defect.
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = self._page(browser)
            for text in ["first question", "second question"]:
                page.fill("#upload-orientation-input", text)
                page.press("#upload-orientation-input", "Enter")
            page.wait_for_function("window.__asked && window.__asked.length >= 2", timeout=5000)
            asked = page.evaluate("window.__asked")
            browser.close()
        self.assertEqual([a["message"] for a in asked], ["first question", "second question"])

    def test_empty_enter_asks_nothing(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = self._page(browser)
            page.press("#upload-orientation-input", "Enter")
            page.wait_for_timeout(300)
            asked = page.evaluate("window.__asked")
            browser.close()
        self.assertEqual(asked, [])

    def test_arrow_keys_are_not_captured_without_suggestions(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = self._page(browser)
            allowed = page.eval_on_selector(
                "#upload-orientation-input",
                "el => el.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowDown', bubbles: true, cancelable: true}))",
            )
            browser.close()
        self.assertTrue(allowed)

    def test_clicking_ask_still_works(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = self._page(browser)
            page.fill("#upload-orientation-input", "clicked not typed")
            page.click('[data-ui-ref="upload.help.submit"]')
            page.wait_for_function("window.__asked && window.__asked.length > 0", timeout=5000)
            asked = page.evaluate("window.__asked")
            browser.close()
        self.assertEqual(asked[0]["message"], "clicked not typed")

    def test_the_project_creation_form_is_never_submitted_by_this(self):
        # The governed action on this page is creating a project. A question
        # typed into the conversational helper must never reach it.
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = self._page(browser)
            page.evaluate(
                "window.__projectSubmits = 0;"
                "document.getElementById('project-creation-form').addEventListener("
                "'submit', function (e) { e.preventDefault(); window.__projectSubmits++; });")
            page.fill("#upload-orientation-input", "how should I establish this project")
            page.press("#upload-orientation-input", "Enter")
            page.wait_for_function("window.__asked && window.__asked.length > 0", timeout=5000)
            submits = page.evaluate("window.__projectSubmits")
            browser.close()
        self.assertEqual(submits, 0)


if __name__ == "__main__":
    unittest.main()
