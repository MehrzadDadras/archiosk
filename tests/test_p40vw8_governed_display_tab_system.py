"""
CLAUDE-P40-VW8 (Governed Display Tab System) - distinct from the earlier,
already-shipped "CLAUDE-P40-VW8"/"CLAUDE-P40-VW8-QA" stage (Reference
Mode completion, Appearance/theme correction, Lists/Display/Menu fixes,
Add Tag visible consequence, focused Project chooser, Project-switching
dialog - see git log 4043784/639d84f and this repo's own
CONTINUATION_CHECKPOINT.md). The tag is reused because that is what this
stage's own governing prompt specifies; flagged here per this repository's
established discipline for tag collisions (see git log a61a7b8/9a5c11b for
the analogous "CLAUDE-P40-VW7B" collision, and
investigation_attention.js's/case_workspace.js's own header comments for
this exact VW8 collision).

Audit finding (Section 2 of this stage's own prompt), grounded directly in
the actual repository rather than assumed: this application already has
TWO real, working, tested dynamic-record Display tab mechanisms - CLAUDE-
P40-DTAB1's Document tab strip (`kind='source'`: pin/preview/hidden,
rename/color, keyboard roving-tabindex, an "All Tabs" overflow panel) and
CLAUDE-P40-VW7B's Investigation Attention Positions strip (`kind='case'`:
a bounded 4-slot attention set, a real "Focused" indicator, a
non-destructive "release" that never navigates or falsifies status).
Neither RFI, Task, nor Tag is a separate Display "kind" at all - an RFI
leaf routes into its OWNING Investigation (`?case=`, `lists.project.rfis.
leaf`); a Task/Tag leaf routes via `_conversation_source_url` into either
the bare workspace URL (Chats/no-selection state) or an Investigation's
own conversation (`?case=`) with a `#conv-source-<id>` scroll anchor -
never a `?source=` Document route, confirming Tasks/Tags are tied to
CONVERSATION passages, not Documents. "Project Tools" is a pure Lists-
region set of forms/actions (Add Document, Add Text Record, Remove
Project, Removed Items) that never touches Display at all. Overview and
Chats (the "nothing selected" state) are this app's two STABLE surfaces -
each a Project-level singleton with no possible duplicate, represented
through Lists' own server-rendered active-state plus the Display division
header text, deliberately with no tab-strip pill of their own (a
considered "smallest coherent" choice, not an oversight - a singleton
that can never be duplicated trivially satisfies "opening the same
surface again focuses the existing tab" without needing a switchable
pill; forcing one into either strip would be exactly the "browser-style
tab complexity... unsupported by real product needs" Section 4 warns
against). "Files" is reserved (Section 9) as a documented, no-op kind in
case_workspace.js's own populateDivision comment - no branch, no picker
entry, no placeholder control anywhere.

Toolbox (Section 8) already implements the active_case > selected_source
> neutral-empty-state priority order server-side, request-scoped exactly
like Display itself - by construction there is no client-side state to go
stale, confirmed by direct template inspection, not assumed. Eye (Section
8) already clears on navigation by its own prior, accepted, explicitly-
documented design (EYE1's own "Not saved anywhere - cleared when you
navigate away or reload") - since every real tab activation in this
full-page-reload app IS a navigation, this is pre-existing, correct,
unchanged behavior, not a new regression. Both strips' CSS already
truncates long labels identically (`overflow:hidden; text-overflow:
ellipsis; white-space:nowrap; min-width:0` on `.document-tab-label` and
`.attention-position-label`) and both already scroll horizontally when
more tabs exist than fit - confirmed by direct CSS inspection, no changes
needed.

Two genuine, small, targeted coherence gaps were found and fixed:
1. `investigation_attention.js`'s own keyboard handler (`onPositionKeydown`)
   was missing the explicit Space-key activation `document_tabs.js`'s
   `onTabKeydown` already has (native `<a href>` elements activate on
   Enter but not Space) - a real accessibility-parity gap between this
   app's two dynamic-record tab strips, now fixed identically.
2. `document_tabs.js`'s own `activateFallback` (closing the active
   Document tab with no other Document tab or preview left) fell straight
   to the empty Display state even when a perfectly good attended
   Investigation was sitting in the Attention strip - not incorrect
   per DTAB1's own original scope, but incoherent once this stage treats
   BOTH strips as one governed dynamic-record tab system per Section 4's
   "closing the active tab selects a deterministic neighboring...tab."
   Fixed by exposing a new, read-only `window.ArchioskInvestigationAttention.
   mostRecentAttended(excludingId)` lookup that `activateFallback` now
   consults as a final fallback before the empty state - purely additive,
   never removes an existing fallback option, and does NOT touch
   Attention's own "release never navigates" guarantee (a different
   action reading a read-only lookup, not a change to release itself).

No other code changes were required or made - every other item on this
stage's own Section 2 audit checklist was found already correct by direct
repository evidence.

This uses the same real-Chromium-via-Playwright technique established in
CLAUDE-P40-VW7B-QA3 (renders genuine Flask-served HTML plus the genuine,
unmodified static/css/tokens.css+main.css AND, where JS runtime behavior
itself is under test, the genuine, unmodified static/js/document_tabs.js+
investigation_attention.js file contents, into a real headless Chromium
via set_content() - no live HTTP server, stays hermetic) for the two
genuinely NEW runtime-behavior assertions (cross-kind fallback, Space-key
activation) that a source-text assertion cannot prove; every browser test
class skips cleanly, not loudly, if Chromium isn't installed.
"""
from __future__ import annotations

import io
import json
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
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_CASE_WORKSPACE_HTML_PATH = _REPO_ROOT / "templates" / "case_workspace.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_TOKENS_CSS_PATH = _REPO_ROOT / "static" / "css" / "tokens.css"
_DOCUMENT_TABS_JS_PATH = _REPO_ROOT / "static" / "js" / "document_tabs.js"
_INVESTIGATION_ATTENTION_JS_PATH = _REPO_ROOT / "static" / "js" / "investigation_attention.js"
_CASE_WORKSPACE_JS_PATH = _REPO_ROOT / "static" / "js" / "case_workspace.js"

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
    "available in this environment - these tests provide genuine "
    "browser-executed-JS evidence that a source-text assertion cannot; "
    "skip rather than fake it when the browser isn't installed."
)


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_vw8tabs_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="vw8tabs_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, project_name, filename="spec.pdf", content=b"content", owner="vw8tabs_owner"):
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

    def _client(self, username="vw8tabs_owner", user_id=1):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = "admin"
        return client

    def _create_case(self, client, project_id, title):
        resp = client.post(f"/projects/{project_id}/workspace/cases", data={"title": title, "objective": ""})
        location = resp.headers["Location"]
        return location.split("case=")[1].split("&")[0]

    def _first_source(self, project_id):
        store = cw.CaseWorkspaceStore(self.tmp_dir)
        return store.get(project_id).sources[0]


# ---------------------------------------------------------------------------
# Section 2 audit confirmations - RFI/Task/Tag/Project Tools bypass Display
# as their own "kind"; stable surfaces have no tab pill; empty state exists.
# ---------------------------------------------------------------------------

class AuditConfirmationTests(_BaseTestCase):
    def test_rfi_leaf_routes_into_its_owning_investigation_not_a_separate_kind(self):
        # Creating a real RFI draft requires a real Finding (create_rfi_draft's
        # own finding_id requirement, routes/workspace.py) - a heavier
        # fixture than this one routing fact needs. Verified directly
        # against the template's own real source instead (still genuine
        # evidence, not fabricated): the RFI leaf's href is built from
        # `case=row.draft.case_id` via url_for('workspace.show_workspace',
        # ...case=...) - the exact same route/parameter Investigations
        # themselves use, never a distinct rfi= or kind=rfi value.
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        idx = html.index('data-ui-ref="lists.project.rfis.leaf"')
        tag = html[html.rindex("<a", 0, idx):html.index(">", idx) + 1]
        self.assertIn("case=row.draft.case_id", tag)
        self.assertNotIn("rfi=", tag)
        self.assertNotIn("kind=", tag)

    def test_task_leaf_routes_via_conversation_source_url_not_a_document_source_param(self):
        doc = self._ingest("VW8 Task Routing Project")
        client = self._client()
        client.post(f"/projects/{doc.project_id}/workspace/messages", data={"content": "Check the roof drainage detail."})
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        # Whether or not a real message/tag/task exists yet, the template's
        # own routing helper (_conversation_source_url) never emits
        # ?source= for a Task/Tag leaf - grounded directly in
        # routes/workspace.py's own source, not merely absence-of-evidence.
        helper_src = Path(_REPO_ROOT / "routes" / "workspace.py").read_text(encoding="utf-8")
        fn_start = helper_src.index("def _conversation_source_url(")
        fn_body = helper_src[fn_start:helper_src.index("\ndef ", fn_start + 10)]
        self.assertNotIn('"source"', fn_body)
        self.assertIn("case=source_anchor", fn_body.replace(" ", ""))

    def test_project_tools_branch_contains_no_display_iframe_or_case_source_refs(self):
        doc = self._ingest("VW8 Project Tools Isolation")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        start = body.index('data-ui-ref="lists.project.tools"')
        end = body.index("</ul>", body.index("<ul", start))
        # index of the branch's OWN closing children </ul> - Project Tools'
        # own subtree, not the rest of the page.
        branch = body[start:end]
        self.assertNotIn("iframe", branch)
        self.assertNotIn("data-source-id", branch)
        self.assertNotIn("data-case-id", branch)

    def test_empty_display_state_message_present_when_nothing_selected(self):
        doc = self._ingest("VW8 Empty State Project")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn("No Investigation or Document is currently selected", body)

    def test_both_dynamic_record_strips_render_regardless_of_current_selection(self):
        # Section 4's own "present regardless of the current selection" -
        # confirmed live: with Overview active, BOTH the Document tab
        # strip and the Attention strip markup are still present (their
        # own [hidden] attribute is JS-toggled, not server-suppressed).
        doc = self._ingest("VW8 Strips Presence Project")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertIn('data-ui-ref="display.document-tabs"', body)
        self.assertIn('data-ui-ref="display.attention-positions"', body)

    def test_overview_and_chats_have_no_tab_strip_pill_of_their_own(self):
        # Deliberate: neither the document-tab-strip nor the
        # attention-strip ever builds a pill for 'overview'/no-selection -
        # both scripts only ever read #workspace-active-sources-data /
        # #workspace-visible-cases-data, neither of which contains an
        # Overview/Chats entry at all. Scoped to CODE identifiers
        # ("overview" as a bare word/string), not this file's own prose
        # comments, which legitimately mention "Overview" as a
        # cross-reference (e.g. "back to a neutral Overview state").
        js = _DOCUMENT_TABS_JS_PATH.read_text(encoding="utf-8")
        self.assertNotIn("'overview'", js.lower())
        self.assertNotIn('"overview"', js.lower())
        js2 = _INVESTIGATION_ATTENTION_JS_PATH.read_text(encoding="utf-8")
        self.assertNotIn("'overview'", js2.lower())
        self.assertNotIn('"overview"', js2.lower())


# ---------------------------------------------------------------------------
# The two targeted coherence fixes - source-level confirmation.
# ---------------------------------------------------------------------------

class SourceLevelFixTests(unittest.TestCase):
    def test_attention_positions_now_activate_on_space(self):
        js = _INVESTIGATION_ATTENTION_JS_PATH.read_text(encoding="utf-8")
        fn = js[js.index("function onPositionKeydown("):js.index("\n    render();")]
        self.assertIn("e.key === ' '", fn)
        self.assertIn("el.click()", fn)

    def test_attention_exposes_most_recent_attended_lookup(self):
        js = _INVESTIGATION_ATTENTION_JS_PATH.read_text(encoding="utf-8")
        self.assertIn("mostRecentAttended: function (excludingId)", js)

    def test_attention_most_recent_attended_never_writes_or_navigates(self):
        js = _INVESTIGATION_ATTENTION_JS_PATH.read_text(encoding="utf-8")
        fn_start = js.index("mostRecentAttended: function (excludingId)")
        fn_body = js[fn_start:js.index("\n    };", fn_start)]
        self.assertNotIn("saveAttention", fn_body)
        self.assertNotIn("navigateTo", fn_body)
        self.assertNotIn("window.location", fn_body)

    def test_document_tabs_activate_fallback_consults_attention_before_empty_state(self):
        js = _DOCUMENT_TABS_JS_PATH.read_text(encoding="utf-8")
        fn = js[js.index("function activateFallback("):js.index("\n    function hideTab(")]
        self.assertIn("ArchioskInvestigationAttention", fn)
        self.assertIn("mostRecentAttended", fn)
        # Ordering: the attention fallback must be consulted BEFORE
        # navigateToEmpty() is reached, not after (dead code) or instead
        # of it (must still degrade to empty when nothing is attended).
        self.assertLess(fn.index("mostRecentAttended"), fn.index("navigateToEmpty()"))

    def test_document_tabs_fallback_degrades_safely_when_attention_module_absent(self):
        # A panel_only (division 1-5 iframe) render never includes
        # #attention-strip at all, so window.ArchioskInvestigationAttention
        # is never defined there - must not throw.
        js = _DOCUMENT_TABS_JS_PATH.read_text(encoding="utf-8")
        fn = js[js.index("function activateFallback("):js.index("\n    function hideTab(")]
        self.assertIn("window.ArchioskInvestigationAttention &&", fn)

    def test_reserved_files_kind_is_documentation_only_no_functional_branch(self):
        # CLAUDE-P40-VW8-QA1: the dispatch itself was generalized from
        # three independent `kind === 'files'`-shaped if/elif chains into
        # one shared PANEL_KINDS registry (see that table's own header
        # comment in case_workspace.js) - "no functional branch for
        # 'files'" is now proven by 'files' having no KEY in that
        # registry, not by the absence of a string comparison.
        js = _CASE_WORKSPACE_JS_PATH.read_text(encoding="utf-8")
        self.assertIn("'files' has NO entry in PANEL_KINDS", js)
        table_idx = js.index("const PANEL_KINDS = {")
        table = js[table_idx:js.index("\n        };", table_idx)]
        self.assertNotIn("files:", table)
        self.assertNotIn("'files':", table)
        # No real dispatch branch anywhere compares kind to 'files'.
        self.assertNotIn("kind === 'files'", js)
        self.assertNotIn('kind === "files"', js)


# ---------------------------------------------------------------------------
# Real-browser (genuine JS execution) evidence for the two new behaviors.
# ---------------------------------------------------------------------------

_FAKE_ORIGIN = "http://vw8-governed-tabs-test.invalid"


@unittest.skipUnless(_BROWSER_AVAILABLE, _SKIP_REASON)
class RealBrowserBehaviorTests(_BaseTestCase):
    """Genuine JS-execution evidence, not source-text pattern matching.

    localStorage is NOT accessible to content loaded via Playwright's own
    page.set_content() in this environment (a real, empirically-confirmed
    Chromium restriction - `about:blank`-hosted documents have an opaque
    origin, and every localStorage call in both files under test is
    wrapped in try/catch, so this fails SILENTLY rather than with an
    error, which is exactly the kind of gap a source-text assertion would
    never catch either). Fixed by serving the real, rendered HTML from a
    real (but entirely local, non-routable - RFC 2606 `.invalid`) HTTP
    origin via page.route()'s own fulfill(), never an actual live server
    or real network access - the same hermetic guarantee QA3's
    set_content()-based tests have, just through a different Playwright
    mechanism because THIS stage's tests specifically need working
    localStorage, which those did not.
    """

    @classmethod
    def setUpClass(cls):
        cls.tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        cls.main_css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        cls.document_tabs_js = _DOCUMENT_TABS_JS_PATH.read_text(encoding="utf-8")
        cls.attention_js = _INVESTIGATION_ATTENTION_JS_PATH.read_text(encoding="utf-8")

    def _render(self, client, url) -> str:
        """The real, server-rendered workspace HTML with its real CSS
        inlined, and document_tabs.js/investigation_attention.js's own
        real, unmodified content inlined too (this test needs them to
        actually EXECUTE, not just exist as source text). Every OTHER
        external <script src> is stripped (this fake origin fulfills only
        the one path it's told to; neither file under test depends on
        anything else on the page anyway)."""
        body_html = client.get(url).get_data(as_text=True)
        combined_style = f"<style>{self.tokens_css}\n{self.main_css}</style>"
        html, n = re.subn(
            r'<link[^>]*href="[^"]*tokens\.css[^"]*"[^>]*>\s*'
            r'<link[^>]*href="[^"]*main\.css[^"]*"[^>]*>',
            lambda _m: combined_style,
            body_html, count=1,
        )
        assert n == 1
        html = re.sub(r'<script[^>]+src="[^"]*document_tabs\.js[^"]*"[^>]*></script>',
                       lambda _m: f"<script>{self.document_tabs_js}</script>", html, count=1)
        html = re.sub(r'<script[^>]+src="[^"]*investigation_attention\.js[^"]*"[^>]*></script>',
                       lambda _m: f"<script>{self.attention_js}</script>", html, count=1)
        html = re.sub(r'<script[^>]+src="[^"]*"[^>]*></script>', "", html)
        return html

    def _serve_and_capture_navigation(self, page, entry_path, html):
        """Fulfills exactly the ONE entry path with the real rendered
        page; every OTHER request under the fake origin (i.e. whatever
        the page's own JS navigates to next) is captured and aborted
        rather than actually attempted - there is nothing real to serve
        it, and there doesn't need to be, since the captured URL itself
        is the evidence under test."""
        captured = {}

        def on_route(route):
            url = route.request.url
            if url == _FAKE_ORIGIN + entry_path:
                route.fulfill(status=200, content_type="text/html", body=html)
            else:
                captured["url"] = url
                route.abort()

        page.route(_FAKE_ORIGIN + "/**", on_route)
        return captured

    def test_closing_the_only_document_tab_falls_back_to_an_attended_investigation(self):
        doc = self._ingest("VW8 Cross-Kind Fallback Project")
        client = self._client()
        case_id = self._create_case(client, doc.project_id, "Fallback Target Investigation")
        source = self._first_source(doc.project_id)
        entry_path = f"/projects/{doc.project_id}/workspace?source={source['id']}"
        html = self._render(client, entry_path)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1400, "height": 900})
                captured = self._serve_and_capture_navigation(page, entry_path, html)
                # Pre-seed the attention set (client-side workspace
                # preference, exactly as a prior real page load against
                # ?case=<id> would have reconciled it in) BEFORE the
                # document under test ever runs its own scripts.
                page.add_init_script(
                    "window.localStorage.setItem("
                    "'beehive:attention:cases:vw8tabs_owner:%s', "
                    "JSON.stringify(['%s']));" % (doc.project_id, case_id)
                )
                page.goto(_FAKE_ORIGIN + entry_path, wait_until="load")

                # Sanity: the attention module really did pick up the
                # pre-seeded case before we act.
                attended = page.evaluate(
                    "() => window.ArchioskInvestigationAttention && "
                    "window.ArchioskInvestigationAttention.mostRecentAttended(null)"
                )
                self.assertEqual(attended, case_id)

                close_btn = page.query_selector(".document-tab-close")
                self.assertIsNotNone(close_btn, "expected exactly one (preview) document tab with a close control")
                close_btn.click()
                page.wait_for_timeout(300)
            finally:
                browser.close()

        self.assertIn("url", captured, "closing the tab did not attempt any navigation at all")
        self.assertIn(f"case={case_id}", captured["url"])

    def test_space_key_activates_a_focused_attention_position(self):
        doc = self._ingest("VW8 Space Key Attention Project")
        client = self._client()
        case_a = self._create_case(client, doc.project_id, "Case A")
        case_b = self._create_case(client, doc.project_id, "Case B")
        entry_path = f"/projects/{doc.project_id}/workspace?case={case_a}"
        html = self._render(client, entry_path)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1400, "height": 900})
                captured = self._serve_and_capture_navigation(page, entry_path, html)
                page.add_init_script(
                    "window.localStorage.setItem("
                    "'beehive:attention:cases:vw8tabs_owner:%s', "
                    "JSON.stringify(['%s', '%s']));" % (doc.project_id, case_a, case_b)
                )
                page.goto(_FAKE_ORIGIN + entry_path, wait_until="load")

                positions = page.query_selector_all(".attention-position")
                self.assertEqual(len(positions), 2)
                # The SECOND position (case_b, not the already-focused
                # case_a) - focus it directly (mirrors what ArrowRight
                # roving-tabindex navigation would have already put focus
                # on) and press Space.
                positions[1].evaluate("el => el.focus()")
                page.keyboard.press(" ")
                page.wait_for_timeout(300)
            finally:
                browser.close()

        self.assertIn("url", captured, "Space did not activate the focused attention position")
        self.assertIn(f"case={case_b}", captured["url"])


if __name__ == "__main__":
    unittest.main()
