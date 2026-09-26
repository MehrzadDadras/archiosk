"""
CLAUDE-COMPOSER-CONVERGENCE-01, completed by the UNIVERSAL COMPOSER INVARIANT.

Product Owner: "some pages are stable and coherent while others are drifting
like loose teeth... the user should not have to learn different interaction
rules page by page." And then: ARCHIOSK V2 has ONE canonical GO Composer that is
the permanent spine of the signed-in application.

WHAT THIS FILE IS FOR

It keeps the invariant true after today:

  - there is exactly one interactive Composer implementation
    (_macros.html conversation_dock), and exactly one place that renders it
    (base.html, on every signed-in page);
  - go_scope() changes what it SENDS - APPLICATION / PROJECT / DOCUMENT /
    INVESTIGATION / PLANNING STUDY - never whether it exists;
  - pages supply only its history (go_thread), which is display/history only;
  - nothing else in templates/ may post to a GO conversation endpoint, carry
    the Composer's markers, or grow a conversational field. A new competing
    composer fails here loudly.

THE CONTRACT (CA1 Section AC)

    Say anything to Composer. Press a button when you mean it.

  - Enter submits via an explicit binding to the named send control
    (developer_composer_input.js binds every [data-developer-composer-form]).
  - autocomplete="off", so browser autofill cannot eat the first Enter.
  - Voice through the one shared engine; Shift+Enter makes a newline.

WHAT IS DELIBERATELY *NOT* UNIFORM ACROSS SCOPES

  - ATTACHMENT: only where the receiving endpoint accepts an image and the
    evidence has a governed home (project, investigation) or the developer
    conversation. APPLICATION orientation and the DOCUMENT conversation take no
    image, so their Composer renders no + - a boundary, not drift.
  - REASONING SPINE: the project Composer reaches run_conversational_turn; the
    APPLICATION orientation reaches a rule-based classifier by recorded
    governance decision. Same Composer, different authorized endpoint.
"""
from __future__ import annotations

import io
import re
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES = _REPO_ROOT / "templates"
_MACROS = "_macros.html"
_COMPOSER_ANCHOR = 'data-ui-ref="chat.composer"'

# Markers that make a <form> Composer-like. Only the canonical macro may carry them.
_COMPOSER_MARKERS = (
    "data-developer-composer-form",
    "conversation-dock-composer",
    "gateway-orientation-form",
    "developer-home-composer-form",
)

# The GO conversation endpoints. The canonical Composer reaches them through
# go_scope() (app.py); no template may build a form that posts to one.
_GO_ENDPOINTS = (
    "workspace.quick_start",
    "workspace.post_message",
    "planning_zoning.converse_study",
    "portal.gateway_orientation",
    "portal.developer_home_composer",
)


def _read(name: str) -> str:
    return (_TEMPLATES / name).read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    return re.sub(r"\{#.*?#\}", "", text, flags=re.S)


def _form_html(text: str, anchor: str) -> str:
    i = text.index(anchor)
    start = text.rindex("<form", 0, i)
    return text[start:text.index("</form>", i) + len("</form>")]


def _open_tag(form_html: str) -> str:
    return form_html[:form_html.index(">") + 1]


def _templates():
    for path in sorted(_TEMPLATES.rglob("*.html")):
        yield path, path.read_text(encoding="utf-8")


class TheCanonicalComposerHonoursTheContract(unittest.TestCase):
    """The one Composer, checked against the contract every scope inherits."""

    def setUp(self):
        self.html = _form_html(_read(_MACROS), _COMPOSER_ANCHOR)

    def test_enter_is_bound_explicitly(self):
        self.assertIn("data-developer-composer-form", _open_tag(self.html))

    def test_its_send_control_is_a_named_submit_button(self):
        self.assertIn('data-ui-ref="chat.composer.send"', self.html)
        tag = self.html[self.html.rindex("<button", 0, self.html.index('data-ui-ref="chat.composer.send"')):]
        self.assertIn('type="submit"', tag[:tag.index(">") + 1])

    def test_browser_autofill_cannot_eat_the_first_enter(self):
        field = re.search(r"<textarea[^>]*data-developer-composer-input[^>]*>", self.html)
        self.assertIsNotNone(field)
        self.assertIn('autocomplete="off"', field.group(0))

    def test_it_is_multiline_so_shift_enter_can_work(self):
        self.assertIn("<textarea", self.html)

    def test_it_has_exactly_one_voice_button(self):
        self.assertEqual(self.html.count("voice-input-button"), 1)

    def test_the_posted_field_follows_the_endpoint_not_a_second_composer(self):
        # One textarea whose NAME is the scope's (text / message / question /
        # command_text) - the reason no page needs a composer of its own.
        self.assertIn('name="{{ input_name }}"', self.html)


class ExactlyOneComposerExists(unittest.TestCase):
    """The part that keeps this true after today."""

    def test_base_html_is_the_only_caller_of_the_canonical_macro(self):
        callers = {path.name: _strip_comments(text).count("conversation_dock(")
                   for path, text in _templates() if path.name != _MACROS}
        callers = {name: n for name, n in callers.items() if n}
        self.assertEqual(callers, {"base.html": 1},
                         "Only base.html may render the Composer, exactly once.")

    def test_no_other_template_carries_composer_markers(self):
        offenders = []
        for path, text in _templates():
            if path.name == _MACROS:
                continue
            for match in re.finditer(r"<form[^>]*>", _strip_comments(text)):
                if any(marker in match.group(0) for marker in _COMPOSER_MARKERS):
                    offenders.append("%s: %s" % (path.name, match.group(0)[:120]))
        self.assertEqual(offenders, [], "A competing Composer form appeared. There is "
                         "one canonical Composer - give this page a scope in go_scope() "
                         "instead. Do not delete this assertion.")

    def test_no_template_posts_to_a_go_conversation_endpoint(self):
        offenders = []
        for path, text in _templates():
            body = _strip_comments(text)
            for endpoint in _GO_ENDPOINTS:
                if re.search(r"url_for\(['\"]%s['\"]" % re.escape(endpoint), body):
                    offenders.append("%s -> %s" % (path.name, endpoint))
        self.assertEqual(offenders, [], "Only go_scope() may point the Composer at a GO "
                         "conversation endpoint.")

    def test_the_selection_command_field_exists_only_in_the_composer(self):
        offenders = [path.name for path, text in _templates()
                     if 'name="command_text"' in _strip_comments(text)]
        self.assertEqual(offenders, [], "My Documents' Ask-GO-to-act is the canonical "
                         "Composer at APPLICATION scope, not a second input.")

    def test_retired_composers_stay_retired(self):
        for path, text in _templates():
            body = _strip_comments(text)
            with self.subTest(template=path.name):
                for retired in ("composer_shell(", 'class="ds-composer"', 'id="ds-question"',
                                "index-orientation-form", "upload-orientation-form",
                                "developer-home-composer-form", 'name="command_text"'):
                    self.assertNotIn(retired, body)
        self.assertFalse((_REPO_ROOT / "static" / "js" / "developer_composer_image.js").exists())
        self.assertFalse((_TEMPLATES / "partials" / "_master_go.html").exists())


class TheHistoryRegionIsDisplayOnly(unittest.TestCase):
    """go_thread supplies history; it never becomes a second input."""

    def test_no_history_region_contains_an_input_surface(self):
        for path, text in _templates():
            for match in re.finditer(r"\{% block go_thread %\}", text):
                body = _strip_comments(text[match.end():text.index("{% endblock %}", match.end())])
                with self.subTest(template=path.name):
                    self.assertNotIn("<textarea", body)
                    self.assertIsNone(re.search(r"<input[^>]*type=\"(text|search|file)\"", body))
                    self.assertIsNone(re.search(r"<input(?![^>]*type=)[^>]*>", body),
                                      "an untyped input is a text input")
                    for forbidden in ("voice-input-button", "composer-pen", "composer-attach",
                                      "conversation_dock", "data-developer-composer"):
                        self.assertNotIn(forbidden, body)

    def test_the_extras_region_is_gone(self):
        for path, text in _templates():
            with self.subTest(template=path.name):
                self.assertNotIn("{% block go_extras %}", text)


def _fake_parse(_self, raw, filename):
    from services.bhive_parser import ParsedDocument
    return ParsedDocument(project_id=str(uuid.uuid4()), filename=filename,
                          ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
                          text_extraction_status="no_native_text")


class EverySignedInPageRendersExactlyOneComposer(unittest.TestCase):
    """Proved on the rendered page, for staff and customers, across scopes."""

    PW = "Converge!2026x"

    def setUp(self):
        from app import create_app
        from models import ROLE_ADMIN, ROLE_CUSTOMER, User, db
        from werkzeug.security import generate_password_hash

        self.app = create_app("testing")
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_one_composer_"))
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        for name, role in (("conv_boss", ROLE_ADMIN), ("conv_cust", ROLE_CUSTOMER)):
            if not User.query.filter_by(username=name).first():
                user = User(username=name, role=role)
                user.password_hash = generate_password_hash(self.PW)
                db.session.add(user)
        db.session.commit()

    def tearDown(self):
        from models import db
        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def client(self, name):
        c = self.app.test_client()
        c.post("/login", data={"username": name, "password": self.PW})
        return c

    def upload(self, c):
        from PIL import Image
        from services.bhive_parser import BHiveParser
        buf = io.BytesIO()
        Image.new("RGB", (40, 30)).save(buf, "JPEG")
        with patch.object(BHiveParser, "parse", _fake_parse):
            r = c.post("/document-shop", data={"file": (io.BytesIO(buf.getvalue()), "a.jpg"),
                                               "name": "One composer " + uuid.uuid4().hex[:6]},
                       content_type="multipart/form-data")
        return r.headers["Location"].rstrip("/").split("/")[-1]

    def one_composer(self, c, url, scope, method="get"):
        r = getattr(c, method)(url)
        self.assertEqual(r.status_code, 200, url)
        html = r.get_data(as_text=True)
        self.assertEqual(html.count(_COMPOSER_ANCHOR), 1, url)
        self.assertEqual(html.count('id="dock-composer-input"'), 1, url)
        found = re.search(r'<form[^>]*data-ui-ref="chat.composer"[^>]*data-go-scope="([A-Z_]+)"', html)
        self.assertIsNotNone(found, url)
        self.assertEqual(found.group(1), scope, url)
        # The Composer sits in the one chat region, after the page's Work area.
        self.assertGreater(html.index(_COMPOSER_ANCHOR), html.index('id="chat-region"'), url)
        return html

    def test_staff_pages(self):
        boss = self.client("conv_boss")
        pid = self.upload(boss)
        from services.case_workspace import CaseWorkspaceStore
        sid = CaseWorkspaceStore(str(self.tmp)).get(pid).sources[0]["id"]
        pages = [
            ("/projects", "APPLICATION"), ("/find", "APPLICATION"), ("/help", "APPLICATION"),
            ("/upload", "APPLICATION"), ("/projects/choose", "APPLICATION"),
            ("/planning-zoning", "APPLICATION"), ("/removed-projects", "APPLICATION"),
            ("/document-shop/jobs", "APPLICATION"),
            ("/document-shop/jobs/%s" % pid, "DOCUMENT"),
            ("/document-shop/jobs/%s/analysis-history" % pid, "DOCUMENT"),
            ("/projects/%s/workspace" % pid, "PROJECT"),
            ("/projects/%s/workspace?view=overview" % pid, "PROJECT"),
            ("/projects/%s/workspace?source=%s" % (pid, sid), "SOURCE"),
        ]
        for url, scope in pages:
            with self.subTest(url=url):
                self.one_composer(boss, url, scope)
        with self.subTest(url="confirm page"):
            self.one_composer(boss, "/document-shop/jobs/%s/sources/%s/remove" % (pid, sid), "DOCUMENT", "post")

    def test_developer_mode_folds_into_the_same_composer(self):
        boss = self.client("conv_boss")
        boss.post("/developer-mode/toggle")
        html = self.one_composer(boss, "/admin/developer-tools", "APPLICATION")
        self.assertIn('action="/developer-composer"', html)
        self.assertIn('name="message"', html)
        html = self.one_composer(boss, "/projects", "APPLICATION")
        self.assertIn('action="/developer-composer"', html)

    def test_customer_pages(self):
        cust = self.client("conv_cust")
        pid = self.upload(cust)
        desk = self.one_composer(cust, "/document-shop/jobs", "APPLICATION")
        self.assertIn('data-go-selection="document-bulk"', desk)
        self.assertIn('name="command_text"', desk)
        self.assertNotIn('action="/gateway/orientation"', desk)
        doc = self.one_composer(cust, "/document-shop/jobs/%s" % pid, "DOCUMENT")
        self.assertIn('name="question"', doc)
        for url in ("/document-shop", "/help"):
            with self.subTest(url=url):
                html = self.one_composer(cust, url, "APPLICATION")
                self.assertNotIn('action="/gateway/orientation"', html,
                                 "customers use the Document Shop path, not the staff gateway")
                self.assertIn("Open My Documents and select documents", html)

    def test_attachment_only_where_the_endpoint_takes_an_image(self):
        boss = self.client("conv_boss")
        pid = self.upload(boss)
        for url, attach in (("/projects", False), ("/upload", False),
                            ("/document-shop/jobs/%s" % pid, False),
                            ("/projects/%s/workspace" % pid, True)):
            with self.subTest(url=url):
                html = boss.get(url).get_data(as_text=True)
                self.assertEqual('id="dock-composer-image"' in html, attach)


class RecordedExceptions(unittest.TestCase):
    """Surfaces that look adjacent but are deliberately NOT composers."""

    def test_signin_voice_is_navigation_not_conversation(self):
        text = _read("login.html")
        self.assertIn('data-ui-ref="auth.signin.voice"', text)
        self.assertNotIn("data-developer-composer-form", text)
        self.assertNotIn("composer-attach", text)

    def test_calm_lake_is_retired_not_excepted(self):
        """The admin Calm Lake prototype was a standalone shell with no canonical
        Composer. V2 allows no zero-Composer active page and no standalone-shell
        exception, and its capabilities are superseded in the product (Eye pane,
        evidence basis, Approval Gate, Composer voice), so it is RETIRED: no
        route, no template, no stylesheet, no script, no registration."""
        root = Path(__file__).resolve().parent.parent
        for rel in ("routes/calm_lake_prototype.py", "templates/calm_lake_prototype.html",
                    "templates/_calm_lake_plan.html", "static/css/calm_lake.css",
                    "static/js/calm_lake.js"):
            with self.subTest(file=rel):
                self.assertFalse((root / rel).exists(), rel)
        app_py = (root / "app.py").read_text(encoding="utf-8")
        self.assertNotIn("calm_lake", app_py)
        from app import create_app
        app = create_app("testing")
        self.assertFalse([r.rule for r in app.url_map.iter_rules() if "calm" in r.rule])
        self.assertNotIn("calm_lake", app.blueprints)

    def test_nipigon_is_retired_not_excepted(self):
        """The admin Nipigon desk was the last standalone signed-in shell with
        no canonical Composer. Its capabilities are superseded on governed
        Sources (services/detail_callout.py, services/sheet_identity.py, the
        Eye pane, Source provenance) or were prototype-only, so it is RETIRED:
        no route, template, stylesheet, script, renderer or preferences file."""
        root = Path(__file__).resolve().parent.parent
        for rel in ("routes/nipigon_coordination.py", "templates/nipigon_coordination.html",
                    "static/css/nipigon.css", "static/js/nipigon.js",
                    "tools/render_nipigon_assets.py", "config/engine_preferences.json"):
            with self.subTest(file=rel):
                self.assertFalse((root / rel).exists(), rel)
        self.assertNotIn("nipigon", (root / "app.py").read_text(encoding="utf-8"))
        from app import create_app
        app = create_app("testing")
        self.assertFalse([r.rule for r in app.url_map.iter_rules() if "nipigon" in r.rule])
        self.assertNotIn("nipigon", app.blueprints)

    def test_task_forms_are_not_labelled_as_go_composers(self):
        for template, retired, current in (
                ("planning_zoning_result.html", "Ask GO to review", "Submit for review"),
                ("survey_evaluation.html", "Ask GO about this evaluation", "Run evaluation question")):
            with self.subTest(template=template):
                text = _read(template)
                self.assertNotIn(retired, text)
                self.assertIn(current, text)


if __name__ == "__main__":
    unittest.main()
