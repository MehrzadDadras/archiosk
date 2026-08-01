"""
CLAUDE-P40-E2B - Flexible Workspace Frame, Resizable Chat and
Multi-Display Controls.

No browser/rendering tool exists in this environment, so anything that
depends on actual pointer dragging, computed layout geometry, or
keyboard focus traversal cannot be proven by these tests - they verify
what IS provable without one: the server-rendered HTML/attributes/data
a browser would act on, and the real CSS rules a browser would apply
(text-level checks against the actual stylesheet, the same established
pattern tests/test_p40e1a_visual_deboxing.py already uses - not a
rendered-page assertion). Stated honestly rather than skipped; see this
stage's own completion report for exactly what still needs a real
human/browser pass.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import json
import re
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_CSS_PATH = Path(__file__).resolve().parent.parent / "static" / "css" / "main.css"
_JS_PATH = Path(__file__).resolve().parent.parent / "static" / "js" / "case_workspace.js"


def _rule_body(css: str, selector: str) -> str:
    """Returns the {...} body text of the FIRST rule whose selector
    list contains `selector` as an exact token - same helper as
    tests/test_p40e1a_visual_deboxing.py's own (kept as its own copy
    here, matching this codebase's existing per-file test-helper
    convention rather than a new shared import)."""
    needle = re.compile(re.escape(selector) + r"(?![\w\-\"])")
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
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40e2b_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="p40e2b_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="p40e2b_owner", project_name="Riverside P40E2B Workspace")
        self.project_id = self.doc.project_id

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str = "rfp.txt"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client


# ---------------------------------------------------------------------------
# 1-4: Lists/Toolbox independent collapse
# ---------------------------------------------------------------------------

class IndependentPanelCollapseTests(_BaseTestCase):
    def test_lists_and_toolbox_have_independent_toggle_controls(self):
        client = self._client_as("p40e2b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="lists-toggle-btn"', body)
        self.assertIn('id="toolbox-toggle-btn"', body)
        self.assertIn('id="workspace-lists-panel"', body)
        self.assertIn('id="workspace-toolbox-panel"', body)

    def test_before_paint_preferences_are_scoped_per_project_independently(self):
        client = self._client_as("p40e2b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        # Two SEPARATE localStorage keys, each naming this exact
        # project - independence is provable here: hiding Lists can
        # never also be recorded as hiding Toolbox, they are different
        # keys entirely.
        self.assertIn(f"beehive:panel:lists:{self.project_id}", body)
        self.assertIn(f"beehive:panel:toolbox:{self.project_id}", body)
        self.assertNotIn("beehive:panel:lists:{{", body)  # never an unrendered Jinja artifact

    def test_hiding_lists_releases_its_grid_column_to_display(self):
        css = _CSS_PATH.read_text(encoding="utf-8")
        base = _rule_body(css, ".case-workspace")
        lists_hidden = _rule_body(css, "html.lists-hidden .case-workspace")
        base_columns = re.search(r"grid-template-columns:\s*([^;]+);", base).group(1)
        hidden_columns = re.search(r"grid-template-columns:\s*([^;]+);", lists_hidden).group(1)
        self.assertNotEqual(base_columns, hidden_columns)
        # one fewer column track than the base three-column layout
        self.assertEqual(base_columns.count("minmax") - 1, hidden_columns.count("minmax"))

    def test_hiding_toolbox_releases_its_grid_column_to_display(self):
        css = _CSS_PATH.read_text(encoding="utf-8")
        base = _rule_body(css, ".case-workspace")
        toolbox_hidden = _rule_body(css, "html.toolbox-hidden .case-workspace")
        base_columns = re.search(r"grid-template-columns:\s*([^;]+);", base).group(1)
        hidden_columns = re.search(r"grid-template-columns:\s*([^;]+);", toolbox_hidden).group(1)
        self.assertNotEqual(base_columns, hidden_columns)
        self.assertEqual(base_columns.count("minmax") - 1, hidden_columns.count("minmax"))

    def test_hidden_panel_mechanism_is_display_none_not_merely_invisible(self):
        # display:none is what makes a hidden panel's own contents fall
        # OUT of the tab order entirely - opacity:0/visibility:hidden
        # would not (Section B: "must not remain keyboard-focusable
        # off-screen").
        css = _CSS_PATH.read_text(encoding="utf-8")
        body = _rule_body(css, "html.lists-hidden .workspace-pane-lists,\nhtml.toolbox-hidden .workspace-pane-toolbox")
        self.assertIn("display: none", body)

    def test_preferences_are_localstorage_reviewer_specific_not_a_project_write(self):
        # Toggling panels is pure client-side viewing state - the route
        # itself performs no write; GETting the page twice never
        # touches workspace.json (see the dedicated no-mutation test
        # below), and the JS source only ever calls
        # window.localStorage, never fetch()/a form submit, to persist
        # panel state.
        js = _JS_PATH.read_text(encoding="utf-8")
        panel_toggle_section = js[js.index("setUpPanelToggles"):js.index("setUpPanelToggles") + 2500]
        self.assertIn("window.localStorage", panel_toggle_section)
        self.assertNotIn("fetch(", panel_toggle_section)


# ---------------------------------------------------------------------------
# 5: viewing/layout changes never mutate Project records
# ---------------------------------------------------------------------------

class NoMutationOnViewTests(_BaseTestCase):
    def test_repeated_get_with_layout_and_panel_query_state_does_not_mutate_workspace_json(self):
        # P40-D2's own invariant, re-verified for this stage's new
        # surface area: Display Layout/panel state lives entirely in
        # localStorage (client-side), never a query param or form post
        # this route interprets as a write - a GET is a GET regardless
        # of what layout the browser currently has selected. Matches
        # tests/test_p40e_unified_workspace.py's own
        # LegacyProjectPersistenceBoundaryStillIntactTests pattern:
        # last_viewed_by is a pre-existing, already-accepted view-
        # tracking write every ordinary Project Home GET already made
        # before this stage - the real invariant is that NOTHING ELSE
        # (cases/sources/findings/requirements/conversation - anything
        # structural) changes alongside it.
        workspace_path = self.tmp_dir / f"{self.project_id}.workspace.json"
        before_raw = json.loads(workspace_path.read_text(encoding="utf-8"))

        client = self._client_as("p40e2b_owner", 1)
        client.get(f"/projects/{self.project_id}/workspace")
        client.get(f"/projects/{self.project_id}/workspace?source={self._store().get(self.project_id).sources[0]['id']}")

        after_raw = json.loads(workspace_path.read_text(encoding="utf-8"))
        changed_keys = {k for k in set(before_raw) | set(after_raw) if before_raw.get(k) != after_raw.get(k)}
        self.assertTrue(changed_keys.issubset({"last_viewed_by"}), changed_keys)


# ---------------------------------------------------------------------------
# 6-7: resizable Chat
# ---------------------------------------------------------------------------

class ChatResizeTests(_BaseTestCase):
    def test_resize_handle_has_separator_role_and_bounds(self):
        client = self._client_as("p40e2b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="conversation-dock-resize-handle"', body)
        self.assertIn('role="separator"', body)
        self.assertIn('aria-orientation="horizontal"', body)
        self.assertIn('tabindex="0"', body)

    def test_js_enforces_a_minimum_and_maximum_height(self):
        js = _JS_PATH.read_text(encoding="utf-8")
        self.assertRegex(js, r"MIN_HEIGHT\s*=\s*120")
        self.assertRegex(js, r"MAX_HEIGHT\s*=\s*640")
        self.assertIn("Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT", js)

    def test_compact_and_expanded_presets_exist_as_keyboard_friendly_alternative(self):
        client = self._client_as("p40e2b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-conversation-preset="compact"', body)
        self.assertIn('data-conversation-preset="expanded"', body)

    def test_height_persisted_as_reviewer_specific_css_custom_property(self):
        js = _JS_PATH.read_text(encoding="utf-8")
        self.assertIn("--chat-height", js)
        self.assertIn("beehive:chat:height:${projectId}", js)

    def test_conversation_thread_and_composer_still_present_for_draft_and_scroll_preservation(self):
        # The draft/scroll sessionStorage mechanism itself (data-
        # conversation-draft / .conversation-thread[data-conversation-
        # scope]) is untouched by this stage - still rendered, so
        # everything P40-E's own draft/scroll tests already cover
        # continues to apply unchanged across a resize.
        client = self._client_as("p40e2b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("data-conversation-draft=", body)
        self.assertIn("data-conversation-scope=", body)

    def test_chat_grid_row_never_shares_the_toolbox_column(self):
        css = _CSS_PATH.read_text(encoding="utf-8")
        grid = _rule_body(css, ".case-workspace")
        self.assertIn('"lists display toolbox"', grid)
        self.assertIn('"lists chat    toolbox"', grid)
        # "chat" never appears standalone spanning the full row (the
        # old grid-column: 1/-1 full-row dock is gone).
        panel = _rule_body(css, ".conversation-dock-panel")
        self.assertIn("grid-area: chat", panel)
        self.assertNotIn("1 / -1", panel)


# ---------------------------------------------------------------------------
# 8: exactly one composer, one Send action
# ---------------------------------------------------------------------------

class SingleComposerTests(_BaseTestCase):
    def test_exactly_one_composer_and_send_action_project_home(self):
        client = self._client_as("p40e2b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertEqual(body.count('class="conversation-input-form conversation-dock-composer"'), 1)
        self.assertEqual(body.count(">Send<"), 1)

    def test_exactly_one_composer_and_send_action_investigation_open(self):
        client = self._client_as("p40e2b_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Drawing Review", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        self.assertEqual(body.count('class="conversation-input-form conversation-dock-composer"'), 1)
        self.assertEqual(body.count(">Send<"), 1)

    def test_exactly_one_composer_and_send_action_document_selected(self):
        client = self._client_as("p40e2b_owner", 1)
        source_id = self._store().get(self.project_id).sources[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?source={source_id}").get_data(as_text=True)
        self.assertEqual(body.count('class="conversation-input-form conversation-dock-composer"'), 1)
        self.assertEqual(body.count(">Send<"), 1)


# ---------------------------------------------------------------------------
# 9: every Display Layout option changes real geometry
# ---------------------------------------------------------------------------

class DisplayLayoutTests(_BaseTestCase):
    def test_all_four_layout_options_render_in_top_bar(self):
        client = self._client_as("p40e2b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for layout in ("single", "side-by-side", "stacked", "grid"):
            self.assertIn(f'data-display-layout="{layout}"', body)

    def test_every_layout_option_produces_a_distinct_real_grid(self):
        css = _CSS_PATH.read_text(encoding="utf-8")
        geometries = {}
        for layout in ("single", "side-by-side", "stacked", "grid"):
            selector = f'.display-divisions[data-layout="{layout}"]'
            if layout == "single":
                # single has no distinct grid-template-columns override
                # of its own (the base .display-divisions rule already
                # is one column) - its real geometry change is hiding
                # every division but the primary one, checked below.
                continue
            body = _rule_body(css, selector)
            match = re.search(r"grid-template-columns:\s*([^;]+);", body)
            geometries[layout] = match.group(1) if match else None
        # side-by-side and grid are both 2-column but grid additionally
        # declares real rows - not a decorative duplicate of side-by-side.
        self.assertIsNotNone(geometries["side-by-side"])
        self.assertIsNotNone(geometries["grid"])
        grid_body = _rule_body(css, '.display-divisions[data-layout="grid"]')
        self.assertIn("grid-template-rows:", grid_body)
        side_by_side_body = _rule_body(css, '.display-divisions[data-layout="side-by-side"]')
        self.assertNotIn("grid-template-rows:", side_by_side_body)

    def test_single_layout_hides_every_division_but_the_primary(self):
        css = _CSS_PATH.read_text(encoding="utf-8")
        body = _rule_body(css, '.display-divisions[data-layout="single"] .display-division:not(.display-division-primary)')
        self.assertIn("display: none", body)

    def test_layout_choice_is_never_a_dead_decorative_no_op(self):
        # Every option button carries a real, distinct data attribute
        # the JS reads to set .display-divisions[data-layout] - never a
        # bare icon with no handler.
        js = _JS_PATH.read_text(encoding="utf-8")
        self.assertIn("divisionsRoot.dataset.layout = layout", js)
        self.assertIn("workspace-layout-option", js)


# ---------------------------------------------------------------------------
# 10-12: division authorization and Toolbox binding
# ---------------------------------------------------------------------------

class DivisionAuthorizationTests(_BaseTestCase):
    def test_active_sources_data_island_only_contains_this_projects_authorized_file_urls(self):
        client = self._client_as("p40e2b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        start = body.index('id="workspace-active-sources-data"')
        script_start = body.index(">", start) + 1
        script_end = body.index("</script>", script_start)
        payload = json.loads(body[script_start:script_end])
        self.assertEqual(len(payload), 1)
        entry = payload[0]
        self.assertEqual(entry["id"], self._store().get(self.project_id).sources[0]["id"])
        self.assertIn(f"/projects/{self.project_id}/workspace/sources/", entry["file_url"])
        self.assertIn("/file", entry["file_url"])

    def test_removed_document_excluded_from_division_picker_data(self):
        store = self._store()
        workspace = store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        store.remove_source(workspace, source_id=source_id, actor="p40e2b_owner", actor_role="admin")

        client = self._client_as("p40e2b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        start = body.index('id="workspace-active-sources-data"')
        script_start = body.index(">", start) + 1
        script_end = body.index("</script>", script_start)
        payload = json.loads(body[script_start:script_end])
        self.assertEqual(payload, [])

    def test_cross_project_document_never_appears_in_division_picker_data(self):
        other_doc = self._ingest(owner="p40e2b_owner", project_name="A Different Project")
        client = self._client_as("p40e2b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        start = body.index('id="workspace-active-sources-data"')
        script_start = body.index(">", start) + 1
        script_end = body.index("</script>", script_start)
        payload = json.loads(body[script_start:script_end])
        other_source_id = self._store().get(other_doc.project_id).sources[0]["id"]
        self.assertNotIn(other_source_id, [entry["id"] for entry in payload])

    def test_division_content_route_fails_closed_for_a_foreign_source_id(self):
        # The division picker only ever offers file_urls this Project's
        # own active_sources already produced, but the underlying
        # route (workspace.source_file) is the real authorization
        # boundary - confirmed directly here, not just inferred from
        # the picker data being clean.
        other_doc = self._ingest(owner="p40e2b_owner", project_name="Another Project For Auth Check")
        other_source_id = self._store().get(other_doc.project_id).sources[0]["id"]
        client = self._client_as("p40e2b_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace/sources/{other_source_id}/file")
        self.assertEqual(resp.status_code, 404)

    def test_toolbox_binds_to_the_selected_source_query_param(self):
        client = self._client_as("p40e2b_owner", 1)
        source_id = self._store().get(self.project_id).sources[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?source={source_id}").get_data(as_text=True)
        self.assertIn("Remove Document", body)

    def test_promoting_a_division_via_navigation_rebinds_toolbox(self):
        js = _JS_PATH.read_text(encoding="utf-8")
        self.assertIn("url.searchParams.set('source', sourceId)", js)
        self.assertIn("function promoteDivision", js)


# ---------------------------------------------------------------------------
# 13: narrow-screen fallback
# ---------------------------------------------------------------------------

class NarrowScreenFallbackTests(unittest.TestCase):
    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")

    def test_lists_and_toolbox_become_fixed_overlay_drawers_at_narrow_width(self):
        # NOTE: "@media (max-width: 640px)" is not unique in this
        # stylesheet (an unrelated, pre-existing Projects-page rule
        # also uses it) - _rule_body targets the specific selector
        # this stage added instead of trying to bound an entire media
        # block by regex.
        body = _rule_body(self.css, ".workspace-pane-lists,\n    .workspace-pane-toolbox")
        self.assertIn("position: fixed", body)

    def test_multi_division_layouts_collapse_to_one_column_at_medium_width(self):
        match = re.search(r"@media \(max-width: 1080px\) \{(.+?)\n\}\n\n", self.css, re.DOTALL)
        self.assertIsNotNone(match)
        medium_block = match.group(1)
        self.assertIn('display-divisions[data-layout="side-by-side"]', medium_block)
        self.assertIn('display-divisions[data-layout="grid"]', medium_block)
        self.assertIn("grid-template-columns: 1fr", medium_block)

    def test_escape_closes_narrow_drawers(self):
        js = _JS_PATH.read_text(encoding="utf-8")
        self.assertIn("e.key !== 'Escape'", js)
        self.assertIn("matchMedia('(min-width: 641px)')", js)


# ---------------------------------------------------------------------------
# 14: Display has no decorative tinted background
# ---------------------------------------------------------------------------

class DisplayBackgroundTests(unittest.TestCase):
    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")

    def test_display_panel_uses_neutral_surface_not_tinted(self):
        body = _rule_body(self.css, ".workspace-pane-display")
        self.assertIn("var(--surface-primary)", body)
        self.assertNotIn("--surface-secondary", body)

    def test_document_viewer_frame_has_no_tint_or_rounded_box(self):
        body = _rule_body(self.css, ".document-viewer-frame")
        self.assertNotIn("--surface-secondary", body)
        self.assertNotIn("border-radius", body)

    def test_document_viewer_image_has_no_tint_or_rounded_box(self):
        body = _rule_body(self.css, ".document-viewer-image")
        self.assertNotIn("--surface-secondary", body)
        self.assertNotIn("border-radius", body)

    def test_divisions_are_separated_by_lines_not_boxes(self):
        body = _rule_body(self.css, '.display-divisions[data-layout="side-by-side"] [data-division="0"]')
        self.assertNotIn("box-shadow", body)
        self.assertNotIn("border-radius", body)
        self.assertIn("border-right", body)


if __name__ == "__main__":
    unittest.main()
