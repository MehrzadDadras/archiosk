"""
CLAUDE-P40-LTH1 - Persistent Left Lists and Page-Thumbnails Split.

A bounded correction, not a new build: CLAUDE-P40-VW7A-QA2 already built
a real Lists/Thumbnails split (templates/base.html's .lists-pane/
.thumbnails-pane/#lists-thumbnails-divider) - a product-owner browser
review found the Thumbnails pane and its divider were BOTH [hidden] by
default, revealed only once static/js/pdf_viewer.js decided the active
Document was a PDF. That meant NO visible split existed at all on
Overview/Investigation/Chat/non-PDF-Document pages - Lists silently
filled the whole column (the reported screenshot defect: "Project/List
records continuing uninterrupted to the bottom edge"). This stage makes
Thumbnails a PERMANENT structural pane, the exact same correction
CLAUDE-P40-EYE1 already made for Eye relative to Toolbox - content, not
visibility, now carries the "nothing to show" case.

The one genuinely NEW piece of behavior: when the current page has no
Document of its own selected (an Investigation, Chat, or Overview - see
Section 3), static/js/pdf_viewer.js attempts to populate Thumbnails
from a client-side-remembered "last-viewed PDF Document" for this
Project+reviewer (localStorage, revalidated on every load against the
SAME authorized #workspace-active-sources-data JSON island every other
client-side feature in this shell already trusts). No new backend
endpoint - routes/workspace.py only gained one new boolean field
("is_pdf") on that existing JSON island.

See tests/test_p40vw7a_qa2_thumbnails_annotations_layout.py for the
structural-split/divider tests this stage updated in place (the ones
whose assertions targeted the now-corrected hidden-by-default
behavior) - this file covers only what's new here: the always-visible
pane's empty state, the remembered-Document mechanism and its
isolation properties, and this stage's own accessibility additions.

No real browser tool exists in this environment - coverage here is
template/CSS/JS source and rendered-HTML structure, the same practical
ceiling this repo's prior stages have already established and stated
honestly rather than fabricating a walkthrough.
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
_PDF_VIEWER_JS_PATH = _REPO_ROOT / "static" / "js" / "pdf_viewer.js"
_WORKSPACE_ROUTES_PATH = _REPO_ROOT / "routes" / "workspace.py"


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
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_lth1_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="lth1_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="lth1_other", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, project_name, filename, content=b"content", owner="lth1_owner"):
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

    def _client(self, username="lth1_owner", user_id=1):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = "admin"
        return client

    def _first_source(self, project_id):
        store = cw.CaseWorkspaceStore(self.tmp_dir)
        return store.get(project_id).sources[0]


class StructuralPaneTests(_BaseTestCase):
    """Section 1: two real, always-present DOM regions - independent
    scroll containers, not thumbnails appended to Lists."""

    def test_lists_pane_and_thumbnails_pane_are_distinct_dom_regions(self):
        doc = self._ingest("LTH1 Project 1", "spec.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        lists_idx = body.index('id="lists-pane"')
        thumbs_idx = body.index('id="thumbnails-pane"')
        self.assertLess(lists_idx, thumbs_idx)
        # thumbnails-pane must not be nested INSIDE lists-pane - the
        # lists-pane's own closing </div> must appear between them.
        between = body[lists_idx:thumbs_idx]
        self.assertGreaterEqual(between.count("</div>"), 1)

    def test_thumbnails_pane_present_on_every_view_type_within_a_project(self):
        # Overview, an Investigation, and a bare workspace (Chats) all
        # render the SAME permanent pane - not just the Document route.
        doc = self._ingest("LTH1 Project 2", "spec.pdf")
        client = self._client()
        for query in ("", "?view=overview"):
            body = client.get(f"/projects/{doc.project_id}/workspace{query}").get_data(as_text=True)
            self.assertIn('id="thumbnails-pane"', body, query)
            idx = body.index('id="thumbnails-pane"')
            tag = body[body.rindex("<div", 0, idx):body.index(">", idx)]
            self.assertNotIn("hidden", tag, query)

    def test_thumbnails_pane_present_even_with_no_project_open(self):
        # Lists is reviewer-wide (every authenticated page) - Thumbnails
        # is its sibling, so it must be too (Section 1's "full-height
        # left workspace column" - this column exists app-wide already).
        self._ingest("LTH1 Project 3", "spec.pdf")
        client = self._client()
        body = client.get("/projects").get_data(as_text=True)
        self.assertIn('id="thumbnails-pane"', body)
        self.assertIn('id="lists-thumbnails-divider"', body)

    def test_lists_and_thumbnails_have_independent_scroll_css(self):
        css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        lists_body = _rule_body(css, ".lists-pane")
        self.assertIn("overflow-y: auto", lists_body)
        thumbs_list_body = _rule_body(css, ".thumbnails-list")
        self.assertIn("overflow-y: auto", thumbs_list_body)
        # The OUTER .thumbnails-pane clips instead of scrolling itself -
        # .thumbnails-list (its child) is the actual scroll region, the
        # same "outer owns layout, inner scrolls" split .lists-pane/
        # .launcher-panel already establishes.
        pane_body = _rule_body(css, ".thumbnails-pane")
        self.assertIn("overflow: hidden", pane_body)


class EmptyStateTests(_BaseTestCase):
    """Section 4: the pane must still exist with no valid Document
    context, showing a quiet compact empty state - never an
    auto-selected first Document, never unrelated Project records."""

    def test_empty_state_message_renders_by_default(self):
        doc = self._ingest("LTH1 Empty Project", "spec.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Open a Document to view its pages.", body)
        idx = body.index('id="thumbnails-empty-state"')
        tag = body[body.rindex("<p", 0, idx):body.index(">", idx)]
        self.assertNotIn("hidden", tag)

    def test_empty_state_has_its_own_ui_reference(self):
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        idx = html.index('id="thumbnails-empty-state"')
        tag = html[html.rindex("<p", 0, idx):html.index(">", idx)]
        self.assertIn('data-ui-ref="lists.thumbnails-pane.empty"', tag)

    def test_empty_state_toggled_not_the_whole_pane(self):
        js = _PDF_VIEWER_JS_PATH.read_text(encoding="utf-8")
        build_fn = js[js.index("function buildThumbnails("):js.index("function updateThumbnailCurrent(")]
        self.assertIn("thumbnailsEmptyState.hidden = true", build_fn)
        clear_fn = js[js.index("function clearThumbnails("):js.index("function buildThumbnails(")]
        self.assertIn("thumbnailsEmptyState.hidden = false", clear_fn)
        # Never sets the PANE itself hidden - Section 1's "real
        # structural pane" must survive every state, populated or not.
        self.assertNotIn("thumbnailsPane.hidden", js)

    def test_no_project_records_rendered_inside_the_empty_thumbnails_pane(self):
        doc = self._ingest("LTH1 Empty Project 2", "spec.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        pane_start = body.index('id="thumbnails-pane"')
        pane_end = body.index('</nav>', pane_start)
        pane_html = body[pane_start:pane_end]
        self.assertNotIn("tree-node", pane_html)
        self.assertNotIn(doc.project_id, pane_html)


class NoArbitraryDocumentSelectionTests(unittest.TestCase):
    """Section 3's explicit prohibition: never guess a Document merely
    because the Project has one, only the literal last-VIEWED one."""

    def setUp(self):
        self.js = _PDF_VIEWER_JS_PATH.read_text(encoding="utf-8")

    def test_remembered_source_only_set_from_a_real_mount(self):
        # rememberLastPdfSource is called exactly once, inside mount()'s
        # own successful-load path - never from buildThumbnails, never
        # from a loop over activeSourcesFromJson()'s own results.
        self.assertEqual(self.js.count("rememberLastPdfSource("), 2)  # def + 1 call site
        mount_fn = self.js[self.js.index("function mount("):self.js.index("function unmount(")]
        self.assertIn("rememberLastPdfSource(currentSourceId)", mount_fn)

    def test_remembered_lookup_never_indexes_the_sources_array_directly(self):
        # No sources[0]/sources.find(always-true)-style "just pick one"
        # shortcut anywhere in the remembered-context function.
        fn = self.js[self.js.index("function mountRememberedThumbnailsIfAny("):self.js.index("function navigateToDocumentPage(")]
        self.assertNotIn("sources[0]", fn)
        self.assertIn("sources[i].id === remembered", fn)

    def test_auto_mount_only_falls_back_to_remembered_when_nothing_is_selected(self):
        tail = self.js[self.js.index("// -------- Auto-mount"):]
        self.assertIn("hasActiveDocumentSelection", tail)
        self.assertIn("if (!hasActiveDocumentSelection)", tail)
        self.assertIn("mountRememberedThumbnailsIfAny();", tail)


class RememberedContextIsolationTests(unittest.TestCase):
    """Section 7: Project-scoped, revalidated against the authorized
    Source list, fails closed to the empty state on anything stale."""

    def setUp(self):
        self.js = _PDF_VIEWER_JS_PATH.read_text(encoding="utf-8")

    def test_remembered_key_is_scoped_by_username_and_project(self):
        fn = self.js[self.js.index("function lastPdfSourceKey("):self.js.index("function rememberLastPdfSource(")]
        self.assertIn("username", fn)
        self.assertIn("projectId", fn)
        self.assertIn("'beehive:panel:last-pdf-source:' + username + ':' + projectId", fn)

    def test_remembered_source_revalidated_against_authorized_json_island(self):
        fn = self.js[self.js.index("function mountRememberedThumbnailsIfAny("):self.js.index("function navigateToDocumentPage(")]
        self.assertIn("activeSourcesFromJson()", fn)
        self.assertIn("sources[i].is_pdf", fn)

    def test_stale_or_unauthorized_remembered_source_clears_itself(self):
        fn = self.js[self.js.index("function mountRememberedThumbnailsIfAny("):self.js.index("function navigateToDocumentPage(")]
        self.assertIn("if (!match)", fn)
        no_match_branch = fn[fn.index("if (!match)"):fn.index("if (!match)") + 300]
        self.assertIn("localStorage.removeItem(lastPdfSourceKey())", no_match_branch)

    def test_active_sources_json_never_a_second_trusted_source(self):
        fn = self.js[self.js.index("function activeSourcesFromJson("):self.js.index("function mountRememberedThumbnailsIfAny(")]
        self.assertIn("workspace-active-sources-data", fn)

    def test_load_failure_fails_closed_to_empty_state(self):
        fn = self.js[self.js.index("function mountRememberedThumbnailsIfAny("):self.js.index("function navigateToDocumentPage(")]
        self.assertIn(".catch(function ()", fn)
        catch_block = fn[fn.index(".catch(function ()"):]
        self.assertIn("thumbnailsOnlyMode = false", catch_block)
        self.assertIn("pdfDoc = null", catch_block)


class IsPdfFieldTests(_BaseTestCase):
    """The one new server-side field the whole remembered-context
    mechanism is grounded in - reuses the SAME .pdf-extension test
    templates/case_workspace.html's own Display branch already uses,
    never a second, independently-maintained rule."""

    def test_pdf_source_marked_is_pdf_true(self):
        doc = self._ingest("LTH1 IsPdf Project", "spec.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        start = body.index('id="workspace-active-sources-data"')
        script_start = body.index(">", start) + 1
        script_end = body.index("</script>", script_start)
        import json
        payload = json.loads(body[script_start:script_end])
        self.assertEqual(len(payload), 1)
        self.assertTrue(payload[0]["is_pdf"])

    def test_non_pdf_source_marked_is_pdf_false(self):
        doc = self._ingest("LTH1 IsPdf Project 2", "notes.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        start = body.index('id="workspace-active-sources-data"')
        script_start = body.index(">", start) + 1
        script_end = body.index("</script>", script_start)
        import json
        payload = json.loads(body[script_start:script_end])
        self.assertEqual(len(payload), 1)
        self.assertFalse(payload[0]["is_pdf"])

    def test_is_pdf_uses_the_same_extension_check_as_the_display_branch(self):
        routes_src = _WORKSPACE_ROUTES_PATH.read_text(encoding="utf-8")
        self.assertIn('.lower().endswith(".pdf")', routes_src)

    def test_removed_source_excluded_from_active_sources_json_entirely(self):
        # Reuses the SAME guarantee tests/test_p40e2b_flexible_workspace_
        # frame.py's DivisionAuthorizationTests already pins for this
        # island - a removed Document (therefore its is_pdf flag too)
        # can never be remembered/revalidated against, since it never
        # appears in the payload at all.
        doc = self._ingest("LTH1 IsPdf Project 3", "spec.pdf")
        source = self._first_source(doc.project_id)
        store = cw.CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(doc.project_id)
        store.remove_source(workspace, source_id=source["id"], actor="lth1_owner", actor_role="admin")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        start = body.index('id="workspace-active-sources-data"')
        script_start = body.index(">", start) + 1
        script_end = body.index("</script>", script_start)
        import json
        payload = json.loads(body[script_start:script_end])
        self.assertEqual(payload, [])


class ProjectIsolationCrossAccountTests(_BaseTestCase):
    """Section 7: restoration cannot expose another Project's or
    another reviewer's thumbnail/page state."""

    def test_active_sources_json_scoped_to_this_project_only(self):
        doc_a = self._ingest("LTH1 Isolation Project A", "a.pdf")
        doc_b = self._ingest("LTH1 Isolation Project B", "b.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc_a.project_id}/workspace").get_data(as_text=True)
        start = body.index('id="workspace-active-sources-data"')
        script_start = body.index(">", start) + 1
        script_end = body.index("</script>", script_start)
        import json
        payload = json.loads(body[script_start:script_end])
        source_b = self._first_source(doc_b.project_id)
        self.assertNotIn(source_b["id"], [entry["id"] for entry in payload])

    def test_remembered_key_shape_includes_project_id_not_just_username(self):
        js = _PDF_VIEWER_JS_PATH.read_text(encoding="utf-8")
        fn = js[js.index("function lastPdfSourceKey("):js.index("function rememberLastPdfSource(")]
        self.assertIn("data-project-id", fn)

    def test_remembered_key_shape_includes_username_not_just_project(self):
        # A shared browser (two reviewers, one machine) must not leak
        # reviewer A's remembered Document to reviewer B - same
        # cross-account guard document_tabs.js's own tab state already
        # establishes.
        js = _PDF_VIEWER_JS_PATH.read_text(encoding="utf-8")
        fn = js[js.index("function lastPdfSourceKey("):js.index("function rememberLastPdfSource(")]
        self.assertIn("workspace-user-name", fn)


class NoDataMutationTests(_BaseTestCase):
    """Section 7's explicit "no Project/Document/... data is modified
    merely to demonstrate the pane" - every code path here is read-only
    server-side; the client-side pieces touch only localStorage."""

    def test_thumbnails_related_routes_are_all_get_only(self):
        # workspace.py's source_file (the route thumbnails/mount() fetch
        # the PDF binary from) must remain a read-only GET, unaffected
        # by this stage.
        routes_src = _WORKSPACE_ROUTES_PATH.read_text(encoding="utf-8")
        source_file_start = routes_src.index("def source_file(")
        decorator_block = routes_src[max(0, source_file_start - 300):source_file_start]
        self.assertNotIn('methods=["POST"]', decorator_block)

    def test_viewing_a_project_with_a_pdf_does_not_mutate_the_workspace(self):
        doc = self._ingest("LTH1 NoMutation Project", "spec.pdf")
        store = cw.CaseWorkspaceStore(self.tmp_dir)
        before = store.get(doc.project_id).sources
        client = self._client()
        client.get(f"/projects/{doc.project_id}/workspace")
        client.get(f"/projects/{doc.project_id}/workspace?view=overview")
        after = store.get(doc.project_id).sources
        self.assertEqual(before, after)


class DividerAccessibilityTests(unittest.TestCase):
    """Section 6: accessible name, keyboard resizing, visible focus -
    the accessible-name/keyboard mechanics already existed (VW7A-QA2);
    this stage's own addition is the real focus-visible outline."""

    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_divider_has_accessible_name(self):
        idx = self.html.index('id="lists-thumbnails-divider"')
        tag = self.html[self.html.rindex("<div", 0, idx):self.html.index(">", idx)]
        self.assertIn('aria-label="Resize Lists/Thumbnails split"', tag)

    def test_divider_has_visible_focus_outline(self):
        start = self.css.index(".lists-thumbnails-divider:focus-visible {")
        body = self.css[start:self.css.index("}", start)]
        self.assertIn("outline: 2px solid var(--machine-blue)", body)

    def test_divider_never_hidden_so_always_keyboard_reachable(self):
        idx = self.html.index('id="lists-thumbnails-divider"')
        tag = self.html[self.html.rindex("<div", 0, idx):self.html.index(">", idx)]
        self.assertIn('tabindex="0"', tag)
        self.assertNotIn("hidden", tag)


class SelectedPageNonColorCueTests(unittest.TestCase):
    """Section 6: "selected-page indication that does not rely on color
    alone" - a real gap in the pre-existing implementation (border/
    background color only), closed as part of this bounded correction."""

    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_current_thumbnail_has_a_border_width_change_not_just_color(self):
        body = _rule_body(self.css, '.thumbnail-row[aria-current="true"]')
        self.assertIn("border-width: 3px", body)

    def test_current_thumbnail_label_has_a_weight_or_decoration_cue(self):
        start = self.css.index('.thumbnail-row[aria-current="true"] .thumbnail-row-label {')
        body = self.css[start:self.css.index("}", start)]
        self.assertTrue("font-weight: 700" in body or "text-decoration: underline" in body)


class NarrowViewportTests(unittest.TestCase):
    """Section 5: at narrow widths, retain access to both regions
    without covering other surfaces or creating scroll traps. Grounded
    in repository evidence: .launcher-panel ALREADY becomes a real
    overlay drawer at max-width:640px (CLAUDE-P40-E2B1) - Thumbnails,
    now a permanent CHILD of that same panel, reflows inside the drawer
    automatically (the same way Toolbox+Eye already reflow together as
    one column-becomes-drawer unit at that width, per CLAUDE-P40-EYE1's
    own comment) - no separate narrow-specific mechanism was invented
    for this stage, deliberately reusing what already exists."""

    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_launcher_panel_narrow_drawer_rule_still_present_and_unmodified(self):
        start = self.css.index("@media (max-width: 640px) {\n    .launcher-panel {")
        body = self.css[start:self.css.index("}\n}", start) + 3]
        self.assertIn("position: fixed", body)

    def test_no_competing_narrow_override_hides_thumbnails_pane(self):
        # A regression guard: nothing in this file re-adds a narrow-
        # specific rule that would hide/collapse .thumbnails-pane or
        # .lists-thumbnails-divider (the vertical split is height-based,
        # orthogonal to the drawer's own width change, so none should
        # exist).
        self.assertNotIn(".thumbnails-pane { display: none", self.css)
        self.assertNotIn(".lists-thumbnails-divider { display: none", self.css)


class AppearanceCoverageTests(unittest.TestCase):
    """Section 6: support all established Appearance modes. Both new
    elements (.thumbnails-empty-state, the current-thumbnail border-
    width/label cue) are token-driven, so they repaint for free via the
    SAME combined per-surface redefinition .lists-pane's own container
    (.launcher-panel, an "owned surface root") already participates in
    - no new per-Appearance override rule needed for either."""

    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_empty_state_uses_tokens_not_hardcoded_colors(self):
        body = _rule_body(self.css, ".thumbnails-empty-state")
        self.assertIn("var(--text-secondary)", body)
        self.assertNotRegex(body, r"#[0-9a-fA-F]{3,6}\b")

    def test_launcher_panel_is_an_owned_surface_root_for_all_three_dark_modes(self):
        for mode in ("appearance-dark", "appearance-tinted", "appearance-deep-forest"):
            self.assertIn(f".launcher-panel.{mode}", self.css, mode)


class RegressionGuardTests(_BaseTestCase):
    """Section 9's explicit "no regression to EYE1, BRAND1, Chat,
    Display, or existing Document navigation" - a light spot-check here;
    the full pre-existing suites for those stages were also re-run
    unmodified (this stage's commit message has the exact count) as the
    real regression gate."""

    def test_toolbox_eye_column_and_divider_untouched(self):
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('id="toolbox-eye-divider"', html)
        self.assertIn('id="eye-pane"', html)

    def test_brand_mark_still_renders_in_the_header(self):
        doc = self._ingest("LTH1 Regression Project", "spec.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('class="archiosk-mark"', body)

    def test_document_navigation_still_a_real_link_not_client_routing(self):
        doc = self._ingest("LTH1 Regression Project 2", "spec.pdf")
        source = self._first_source(doc.project_id)
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn(f'href="/projects/{doc.project_id}/workspace?source={source["id"]}"', body)

    def test_chat_region_still_renders(self):
        doc = self._ingest("LTH1 Regression Project 3", "spec.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="chat-region"', body)


if __name__ == "__main__":
    unittest.main()
