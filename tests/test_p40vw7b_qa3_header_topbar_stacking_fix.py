"""
CLAUDE-P40-VW7B-QA3 - Header Project Link Still Fails in Clean Browser Session.

A clean-session real-browser reproduction (sign out, sign in fresh, open a
Project with a Document, click the Project name once) showed the header
link did not navigate, contradicting QA2's own report. QA2's fix
(.workspace-topbar-identity's flex-shrink:0, see
test_p40vw7b_qa2_header_vestibule_link_fix.py) had ALREADY passed a
source-text assertion that the anchor exists with the right href - proof
that kind of coverage is not sufficient for this class of bug, per this
stage's own explicit instruction. This module exists specifically to close
that gap with genuine browser-computed evidence instead.

Diagnosis (via a real, installed Chromium - see this repo's own completion
report for how it was verified): main.css's own @media (max-width: 640px)
rules turn BOTH .launcher-panel (Lists) and .workspace-right-column
(Toolbox+Eye) into `position: fixed; top: 0; ... z-index: 30` overlay
drawers below that breakpoint. .workspace-topbar itself was plain
`position: static` with no z-index, so at narrow widths either drawer
painted over the ENTIRE topbar - including the Project-name link -
regardless of the link's own (correct) geometry. Confirmed directly with
document.elementFromPoint() at the link's own visible-text coordinates:
it returned `.tree-leaf.launcher-link.current-project` (Lists' own
current-Project row), not the topbar anchor, at 600px width. A real
Playwright .click() timed out there before the fix and succeeded at every
sampled width from 320px to 1920px after it.

Fix (main.css's own .workspace-topbar rule): position:relative + z-index:31
- one step above the drawers' shared ceiling of 30, the same "stack higher
than anything it could ever appear over" idiom this file already uses
elsewhere (.conv-selection-toolbar/70 above the 60-ceiling Appearance
popup). Neither drawer's own top:0/z-index:30 was touched - both still
correctly cover Display/Chat beneath the topbar, which is the drawers'
own intended behavior; only the always-persistent topbar strip itself is
now guaranteed to stay on top of them.

This uses a REAL, installed Chromium (via the `playwright` package - a
dev/test-only optional tool, not added to requirements.txt or anywhere
the deployed app imports from; every test class below skips cleanly, not
loudly, if it isn't installed). Renders the genuine Flask-served HTML and
the genuine, unmodified static/css/tokens.css + static/css/main.css file
contents (read directly off disk, never hand-copied/excerpted) into a
headless page via set_content() - no live HTTP server involved, so this
stays consistent with this repo's own hermetic-test discipline, while
still exercising real browser layout, paint order, and hit-testing rather
than a source-text pattern match.
"""
from __future__ import annotations

import io
import re
import shutil
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
_TOKENS_CSS_PATH = _REPO_ROOT / "static" / "css" / "tokens.css"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - environment-dependent, not installed
    sync_playwright = None


def _real_chromium_available() -> bool:
    if sync_playwright is None:
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        return False


_BROWSER_AVAILABLE = _real_chromium_available()
_SKIP_REASON = (
    "Real Chromium (the `playwright` package + a downloaded browser) is not "
    "available in this environment - this test provides genuine "
    "browser-computed geometry/hit-testing evidence that a source-text "
    "assertion cannot; skip rather than fake it when the browser isn't "
    "installed."
)


def _fake_parse(self_parser, raw_bytes, filename_):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename_,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
    )


@unittest.skipUnless(_BROWSER_AVAILABLE, _SKIP_REASON)
class HeaderProjectLinkRealBrowserGeometryTests(unittest.TestCase):
    """Genuine browser evidence that the Project-name link is the element
    that actually receives clicks, at both a narrow (drawer-breakpoint)
    and a normal desktop width, with a real Document open (the exact
    reported scenario - Document controls populate the header's middle
    region)."""

    @classmethod
    def setUpClass(cls):
        import app as app_module
        from models import User, db
        cls.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_vw7bqa3_"))
        cls.flask_app = app_module.create_app("testing")
        cls.flask_app.config["REGISTRY_STORE_PATH"] = str(cls.tmp_dir)
        with cls.flask_app.app_context():
            db.session.add(User(
                username="vw7bqa3_owner",
                password_hash=generate_password_hash("x"),
                role="admin",
            ))
            db.session.commit()

        with patch.object(BHiveParser, "parse", _fake_parse):
            with cls.flask_app.app_context():
                fs = FileStorage(stream=io.BytesIO(b"%PDF-1.4 fake content"), filename="spec.pdf")
                doc = ingest_upload(
                    fs, cls.flask_app, operating_environment=CLIENT_OWNER,
                    owner="vw7bqa3_owner", project_name="QA3 Header Stacking Regression Project",
                )
        cls.project_id = doc.project_id
        store = cw.CaseWorkspaceStore(cls.tmp_dir)
        cls.source_id = store.get(cls.project_id).sources[0]["id"]
        cls.tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        cls.main_css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp_dir, ignore_errors=True)

    def _client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "vw7bqa3_owner"
            sess["role"] = "admin"
        return client

    def _standalone_document_with_document_open(self) -> str:
        """The real, server-rendered workspace HTML (Document open, so
        #workspace-document-controls is populated - the exact reported
        scenario), with its two real stylesheet <link>s replaced by one
        inlined <style> of those SAME files' real, current disk contents.
        set_content() has no live server to fetch /static/... from - this
        is the hermetic substitute for that fetch, not a rewritten copy.
        External <script src="..."> tags are stripped for the same reason
        (no live server to fetch them from, and this test's evidence -
        real CSS layout and hit-testing - has no dependency on any of
        them actually running); inline <script> blocks are left alone,
        they're harmless (a pre-paint localStorage read that no-ops
        against an empty store here)."""
        client = self._client()
        body_html = client.get(
            f"/projects/{self.project_id}/workspace?source={self.source_id}"
        ).get_data(as_text=True)
        combined_style = f"<style>{self.tokens_css}\n{self.main_css}</style>"
        # A replacement FUNCTION (not a string) - main.css's own content
        # includes literal backslash-digit sequences (e.g. CSS content:
        # "\2022" escapes) that re.subn would otherwise try to parse as
        # backreferences in a string replacement.
        html, n = re.subn(
            r'<link[^>]*href="[^"]*tokens\.css[^"]*"[^>]*>\s*'
            r'<link[^>]*href="[^"]*main\.css[^"]*"[^>]*>',
            lambda _match: combined_style,
            body_html,
            count=1,
        )
        assert n == 1, "expected exactly one tokens.css+main.css <link> pair to inline"
        html = re.sub(r'<script[^>]+src="[^"]*"[^>]*></script>', "", html)
        return html

    def _assert_project_link_receives_its_own_click(self, width: int) -> None:
        html = self._standalone_document_with_document_open()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": width, "height": 900})
                page.set_content(html, wait_until="load")

                anchor = page.query_selector(".workspace-topbar-project")
                self.assertIsNotNone(anchor, "the Project-name anchor must exist in the real rendered DOM")
                box = anchor.bounding_box()
                self.assertIsNotNone(box)
                cx = box["x"] + box["width"] / 2
                cy = box["y"] + box["height"] / 2
                hit_class = page.evaluate(
                    "([x, y]) => { const el = document.elementFromPoint(x, y); "
                    "return el ? el.className : null; }",
                    [cx, cy],
                )
                self.assertIn(
                    "workspace-topbar-project", hit_class or "",
                    f"at width={width}px, document.elementFromPoint at the visible "
                    f"Project-name text returned {hit_class!r}, not the link itself "
                    "- this is exactly the class of overlap QA2's source-text-only "
                    "coverage could not catch.",
                )
                # Playwright's own click() refuses to click an element that is
                # obscured by something else at the point it would click -
                # the strongest available proxy for "a real user's click
                # actually lands here" without a live server to navigate.
                anchor.click(timeout=5000)
            finally:
                browser.close()

    def test_narrow_width_project_link_receives_the_click_not_the_drawer(self):
        # 500px: below the 640px drawer breakpoint, WITH a Document open
        # (Document controls populate the header's middle region) - the
        # exact combination the real user's own report reproduced.
        self._assert_project_link_receives_its_own_click(500)

    def test_wide_width_project_link_still_works_no_regression(self):
        self._assert_project_link_receives_its_own_click(1400)

    def test_topbar_z_index_exceeds_the_narrow_drawer_ceiling(self):
        # Structural guard, independent of any specific viewport: whatever
        # the drawers' own z-index is (currently 30 for BOTH .launcher-panel
        # and .workspace-right-column - see main.css's own two
        # @media (max-width: 640px) rules), the topbar must always be
        # numerically higher, or a future edit to either side could
        # silently reopen this exact bug with nothing catching it.
        html = self._standalone_document_with_document_open()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 500, "height": 900})
                page.set_content(html, wait_until="load")
                topbar_z = page.evaluate(
                    "() => getComputedStyle(document.querySelector('.workspace-topbar')).zIndex"
                )
                drawer_z = page.evaluate(
                    "() => getComputedStyle(document.querySelector('.launcher-panel')).zIndex"
                )
                self.assertNotEqual(topbar_z, "auto", "topbar must establish a real stacking context")
                self.assertGreater(int(topbar_z), int(drawer_z))
            finally:
                browser.close()


if __name__ == "__main__":
    unittest.main()
