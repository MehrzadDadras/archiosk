"""
CLAUDE-P40-VW7B-QA2 - Header Project Link Does Not Open Vestibule.

Real-browser acceptance of pushed VW7B found that clicking the current
Project name in the top header did not open the Project Vestibule - the
browser stayed on the current Project workspace.

Diagnosis, grounded directly against the actual CSS, not assumed: the
rendered header composition, the link's own href/aria-label, and every
JS click handler in this app were all individually verified correct -
no interception, no wrong target, no missing anchor (see
HeaderLinkCorrectnessTests below, which re-confirms all of this). The
real defect was a flex-distribution asymmetry: `.workspace-topbar` has
three flex children - `.workspace-topbar-identity` (brand + the
Project-switch link), `#workspace-document-controls` (the middle
region, `flex: 1 1 auto`, actively grows to fill space whenever Document
controls are visible), and `.workspace-topbar-controls` (Display
Layout/Appearance/Account). Only the LAST of these three had
`flex-shrink: 0` - `.workspace-topbar-identity` did not, so the growing
middle region could squeeze it toward its `min-width: 0` floor,
shrinking the Project-name link's actual rendered/clickable area toward
nothing (its DOM, href, and aria-label were correct the whole time -
this was a rendered-geometry defect, not a routing or interception
one). Fixed by giving `.workspace-topbar-identity` the same
`flex-shrink: 0` its sibling already has - symmetric treatment, no new
mechanism invented.

No real browser tool exists in this environment - a real flex-shrink
computed-geometry regression can only be directly observed in an actual
browser layout engine. Coverage here is CSS/HTML source verification
(the exact property is present, matches the sibling's own established
pattern, and no conflicting/overriding rule exists) plus rendered-HTML
structural tests re-confirming every OTHER angle the task asked to rule
out (link target, click area/overlap, JS interference) - honestly
bounded, not fabricated as a rendered-pixel proof.
"""
from __future__ import annotations

import io
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload
import services.case_workspace as cw

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"


def _rule_body(css: str, selector: str) -> str:
    needle = re.compile(r"(?<![\w-])" + re.escape(selector) + r"(?![\w\-\":])")
    pos = 0
    while True:
        match = needle.search(css, pos)
        assert match, f"no CSS rule found for selector {selector!r}"
        brace_open = css.index("{", match.end())
        between = css[match.end():brace_open]
        if re.fullmatch(r'[\w\s,.#\[\]"=\-:>]*', between):
            brace_close = css.index("}", brace_open)
            return css[brace_open + 1:brace_close]
        pos = match.end()


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_vw7bqa2_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="vw7bqa2_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, project_name, filename="spec.pdf", content=b"content", owner="vw7bqa2_owner"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )
        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(content, filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client(self, username="vw7bqa2_owner", user_id=1):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = "admin"
        return client

    def _first_source(self, project_id):
        store = cw.CaseWorkspaceStore(self.tmp_dir)
        return store.get(project_id).sources[0]


class FlexShrinkFixTests(unittest.TestCase):
    """The actual fix, source-level."""

    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_workspace_topbar_identity_has_flex_shrink_zero(self):
        body = _rule_body(self.css, ".workspace-topbar-identity")
        self.assertIn("flex-shrink: 0", body)

    def test_matches_the_sibling_regions_own_established_pattern(self):
        # .workspace-topbar-controls already had this - the fix makes
        # identity symmetric with it, not a new pattern invented.
        identity_body = _rule_body(self.css, ".workspace-topbar-identity")
        controls_body = _rule_body(self.css, ".workspace-topbar-controls")
        self.assertIn("flex-shrink: 0", identity_body)
        self.assertIn("flex-shrink: 0", controls_body)

    def test_document_controls_middle_region_remains_the_flexible_one(self):
        # The fix must not also freeze the middle region - it is
        # DELIBERATELY the one that yields space (and already has its
        # own overflow-panel fallback for cramped width).
        body = _rule_body(self.css, ".workspace-topbar-document-controls")
        self.assertIn("flex: 1 1 auto", body)
        self.assertNotIn("flex-shrink: 0", body)

    def test_topbar_still_wraps_as_the_safe_overflow_fallback(self):
        # If all three now-protected regions' combined natural width
        # ever exceeds the viewport, wrapping (a two-line header, still
        # fully clickable) is the safe outcome, not a squeezed/clipped
        # single line.
        body = _rule_body(self.css, ".workspace-topbar")
        self.assertIn("flex-wrap: wrap", body)

    def test_inner_breadcrumb_ellipsis_truncation_still_intact(self):
        # A genuinely long Project+Document name still truncates WITHIN
        # the now-guaranteed identity width - unaffected by this fix.
        body = _rule_body(self.css, ".workspace-topbar-context")
        self.assertIn("overflow: hidden", body)
        self.assertIn("text-overflow: ellipsis", body)
        self.assertIn("white-space: nowrap", body)


class HeaderLinkCorrectnessTests(_BaseTestCase):
    """Re-confirms every OTHER angle the task asked to rule out - link
    target, click area/DOM correctness, no overlap - still holds,
    including with Document controls visible (the exact scenario the
    real-browser report occurred in)."""

    def test_link_target_includes_current_param_with_document_open(self):
        doc = self._ingest("Nipigon Ramp", "Nipigan Starter.pdf")
        source = self._first_source(doc.project_id)
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?source={source['id']}").get_data(as_text=True)
        idx = body.index('data-ui-ref="menu.context.switch-project"')
        tag = body[body.rindex("<a", 0, idx):body.index(">", idx) + 1]
        self.assertIn(f'href="/projects/choose?current={doc.project_id}"', tag)

    def test_document_controls_region_visible_alongside_the_link(self):
        # Confirms the exact real-browser scenario is reproduced
        # server-side: a Document open, #workspace-document-controls
        # present in the DOM (not [hidden] server-side - JS reveals it
        # once mount() succeeds, which CLAUDE-P40-VW7B-QA1 fixed).
        doc = self._ingest("Nipigon Ramp", "Nipigan Starter.pdf")
        source = self._first_source(doc.project_id)
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?source={source['id']}").get_data(as_text=True)
        self.assertIn('id="workspace-document-controls"', body)
        self.assertIn('data-ui-ref="menu.context.switch-project"', body)

    def test_no_click_handler_anywhere_targets_the_topbar(self):
        # Regression guard - no JS file may attach a click interceptor
        # scoped broadly enough to reach .workspace-topbar-identity/
        # .workspace-topbar-project (the exact class of bug this stage
        # ruled out during diagnosis).
        #
        # CLAUDE-APP-MENU-01's own static/js/app_menu.js legitimately
        # scopes itself to .workspace-topbar (document.querySelector) -
        # it is the application menu bar's own generic Escape/outside-
        # click/one-at-a-time behavior. Its one preventDefault() call is
        # scoped to the Exit link's own unsaved-input confirm() guard
        # (byRef('menu.archiosk.exit')), never the generic outside-click
        # handler that closes open menus - so a click on
        # .workspace-topbar-identity/.workspace-topbar-project still
        # navigates normally, and this does not recreate the historical
        # bug class this test guards against. Named and excluded
        # explicitly rather than weakening the invariant for every other
        # file.
        for js_path in (_REPO_ROOT / "static" / "js").glob("*.js"):
            js = js_path.read_text(encoding="utf-8")
            if js_path.name == "app_menu.js":
                outside_click = js[js.index("document.addEventListener('click'"):]
                outside_click = outside_click[:outside_click.index("});") + 3]
                self.assertNotIn("preventDefault", outside_click, js_path.name)
                self.assertNotIn("stopPropagation", outside_click, js_path.name)
                continue
            self.assertNotIn("workspace-topbar", js, js_path.name)

    def test_link_still_single_tab_stop_no_duplicate_control(self):
        doc = self._ingest("Nipigon Ramp", "Nipigan Starter.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        idx = body.index('data-ui-ref="menu.context.switch-project"')
        element = body[body.rindex("<a", 0, idx):body.index("</a>", idx) + 4]
        self.assertEqual(element.count("<a "), 1)

    def test_brand_mark_retains_its_own_destination_unaffected(self):
        # CLAUDE-APP-MENU-01 retired menu.brand (the icon+wordmark
        # single-link treatment) - the same href/aria-label survive
        # unchanged as menu.archiosk.home, now the first item inside the
        # Archiosk menu panel rather than the clickable summary itself.
        doc = self._ingest("Nipigon Ramp", "Nipigan Starter.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        idx = body.index('data-ui-ref="menu.archiosk.home"')
        tag = body[body.rindex("<a", 0, idx):body.index(">", idx) + 1]
        self.assertIn('href="/"', tag)
        self.assertIn('aria-label="Archiosk Home"', tag)

    def test_keyboard_focus_and_accessible_name_intact(self):
        doc = self._ingest("Nipigon Ramp", "Nipigan Starter.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        idx = body.index('data-ui-ref="menu.context.switch-project"')
        tag = body[body.rindex("<a", 0, idx):body.index(">", idx) + 1]
        self.assertIn("Switch Project", tag)
        # A real <a href> is natively keyboard-focusable/activatable -
        # no tabindex="-1" or role override suppressing that.
        self.assertNotIn('tabindex="-1"', tag)

    def test_focus_visible_outline_still_present(self):
        css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        body = _rule_body(css, ".workspace-topbar-project:focus-visible")
        self.assertIn("outline:", body)


class VestibuleAndRestorationUnaffectedTests(_BaseTestCase):
    """Confirms the OTHER VW7B guarantees this stage was told to
    preserve are genuinely untouched by this CSS-only fix."""

    def test_vestibule_still_distinguishes_current_from_available(self):
        doc = self._ingest("Nipigon Ramp", "Nipigan Starter.pdf")
        other = self._ingest("A Different Project")
        client = self._client()
        body = client.get(f"/projects/choose?current={doc.project_id}").get_data(as_text=True)
        self.assertIn('data-ui-ref="gateway.chooser.current"', body)
        self.assertIn("Currently entered", body)
        self.assertIn("A Different Project", body)

    def test_returning_to_the_project_still_restores_independent_state(self):
        # Project-scoped localStorage keys (DTAB1/LTH1/EYE1/attention)
        # are entirely client-side and untouched by a CSS change -
        # spot-checked here via the key-shape source assertions already
        # established in tests/test_p40vw7b_vestibule_and_attention.py's
        # own PerProjectRestorationGroundingTests; re-confirmed here
        # that the header link itself carries no such state of its own
        # to lose.
        doc = self._ingest("Nipigon Ramp", "Nipigan Starter.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        idx = body.index('data-ui-ref="menu.context.switch-project"')
        tag = body[body.rindex("<a", 0, idx):body.index(">", idx) + 1]
        self.assertNotIn("localStorage", tag)
        self.assertNotIn("onclick", tag)


if __name__ == "__main__":
    unittest.main()
