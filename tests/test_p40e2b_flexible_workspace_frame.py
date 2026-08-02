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
# 1-4: Launcher/Toolbox independent collapse
# ---------------------------------------------------------------------------
# CLAUDE-P40-E2B1: the Lists panel this stage's own tests originally
# covered is eliminated (Section E) - its show/hide control is now the
# application-wide launcher panel's own toggle (base.html), not a
# Workspace-local grid column. Toolbox is unaffected and stays covered
# exactly as before.

class IndependentPanelCollapseTests(_BaseTestCase):
    def test_launcher_and_toolbox_have_independent_toggle_controls(self):
        # SUPERSEDED (CLAUDE-P40-E3A, Section 7): the top-bar toggle
        # buttons are retired - the panel-dividing lines themselves are
        # the collapse controls now (#lists-divider/#toolbox-divider).
        client = self._client_as("p40e2b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="lists-divider"', body)
        self.assertIn('id="toolbox-divider"', body)
        self.assertIn('id="launcher-panel"', body)
        self.assertIn('id="workspace-toolbox-panel"', body)

    def test_launcher_preference_is_reviewer_wide_toolbox_preference_is_per_project(self):
        # CLAUDE-P40-E2B1: a deliberate scope change from the old Lists
        # panel this replaces - the launcher panel is now present on
        # every authenticated page (not just this one Project's own
        # Workspace), so its own preference is reviewer-wide
        # (beehive:panel:launcher, no project_id). Toolbox stays
        # Workspace-local, so it keeps its per-project key.
        client = self._client_as("p40e2b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("beehive:panel:launcher", body)
        self.assertIn(f"beehive:panel:toolbox:{self.project_id}", body)
        self.assertNotIn(f"beehive:panel:launcher:{self.project_id}", body)
        self.assertNotIn("beehive:panel:lists:{{", body)  # never an unrendered Jinja artifact

    def test_hiding_launcher_panel_is_a_plain_class_toggle(self):
        css = _CSS_PATH.read_text(encoding="utf-8")
        body = _rule_body(css, "html.launcher-hidden .launcher-panel")
        self.assertIn("display: none", body)

    def test_hiding_toolbox_releases_its_grid_column_to_display(self):
        # SUPERSEDED (CLAUDE-P40-E3A): the old .case-workspace grid (whose
        # column count had to be explicitly recomputed for the
        # toolbox-hidden state) is retired - Lists/Display/Toolbox are
        # now flex siblings in base.html's .app-shell-body, so Display
        # (flex: 1) automatically expands into Toolbox's released space
        # the moment display:none removes it, with no separate
        # column-count override needed at all. That absence is itself
        # the thing to confirm here.
        css = _CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("flex: 1", _rule_body(css, ".app-main"))
        self.assertIn("display: none", _rule_body(css, "html.toolbox-hidden .workspace-pane-toolbox"))
        # No active rule for the retired grid (historical comments
        # mentioning its old name are fine and expected).
        self.assertNotIn(".case-workspace {", css)

    def test_hidden_panel_mechanism_is_display_none_not_merely_invisible(self):
        # display:none is what makes a hidden panel's own contents fall
        # OUT of the tab order entirely - opacity:0/visibility:hidden
        # would not (Section B: "must not remain keyboard-focusable
        # off-screen"). Checked separately now that Launcher (base.html)
        # and Toolbox (case_workspace.html) are two independent rules,
        # not one combined selector.
        css = _CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("display: none", _rule_body(css, "html.launcher-hidden .launcher-panel"))
        self.assertIn("display: none", _rule_body(css, "html.toolbox-hidden .workspace-pane-toolbox"))

    def test_preferences_are_localstorage_reviewer_specific_not_a_project_write(self):
        # SUPERSEDED (CLAUDE-P40-E3A, Section 7): the old top-bar-button
        # toggle scripts (setUpPanelToggles in case_workspace.js,
        # #launcher-toggle-btn wiring in base.html) are retired -
        # replaced by the shared panel-divider script (setUpDivider),
        # inline in base.html. Toggling panels is still pure client-side
        # viewing state - the route itself performs no write; GETting the
        # page twice never touches workspace.json (see the dedicated
        # no-mutation test below). The divider script only ever calls
        # window.localStorage, never fetch()/a form submit, to persist
        # panel state.
        base_html = (Path(__file__).resolve().parent.parent / "templates" / "base.html").read_text(encoding="utf-8")
        anchor = "function setUpDivider"
        divider_section = base_html[base_html.index(anchor):base_html.index(anchor) + 2000]
        self.assertIn("window.localStorage", divider_section)
        self.assertNotIn("fetch(", divider_section)


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
        # SUPERSEDED (CLAUDE-P40-E3A, Section 9): Chat is no longer
        # confined to a "chat" grid-area sharing a row with "toolbox"
        # inside the retired .case-workspace grid - it's now a full-
        # width flex row (.chat-region) beneath .app-shell-body
        # entirely, structurally incapable of sharing a column with
        # Toolbox (which lives INSIDE .app-shell-body). Checked
        # structurally: .conversation-dock-panel carries no leftover
        # grid-area, and .chat-region is its own top-level rule, never
        # nested under .workspace-pane-toolbox's own selector.
        css = _CSS_PATH.read_text(encoding="utf-8")
        panel = _rule_body(css, ".conversation-dock-panel")
        self.assertNotIn("grid-area", panel)
        self.assertIn("flex-shrink: 0", _rule_body(css, ".chat-region"))
        self.assertNotIn(".case-workspace {", css)


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
        # SUPERSEDED (CLAUDE-P40-E3A, Section 6): the old fixed single/
        # side-by-side/stacked/grid preset menu is retired - replaced by
        # a genuinely dynamic orientation (vertical/horizontal) + numeric
        # quantity (1-6) + Apply control, "not limited to decorative
        # presets such as 1, 2 or 3" per the stage's own instruction.
        client = self._client_as("p40e2b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="display-orientation-vertical"', body)
        self.assertIn('id="display-orientation-horizontal"', body)
        self.assertIn('id="display-quantity-decrement"', body)
        self.assertIn('id="display-quantity-increment"', body)
        self.assertIn('id="display-quantity-value"', body)
        self.assertIn('id="display-layout-apply"', body)

    def test_every_layout_option_produces_a_distinct_real_grid(self):
        css = _CSS_PATH.read_text(encoding="utf-8")
        # Different counts produce different real column/row templates -
        # never a decorative no-op - and vertical/horizontal produce
        # genuinely different axes for the same count.
        two_col = _rule_body(css, '.display-divisions[data-orientation="vertical"][data-count="2"]')
        three_col = _rule_body(css, '.display-divisions[data-orientation="vertical"][data-count="3"]')
        self.assertIn("grid-template-columns: repeat(2, 1fr)", two_col)
        self.assertIn("grid-template-columns: repeat(3, 1fr)", three_col)
        self.assertNotEqual(two_col, three_col)
        two_row = _rule_body(css, '.display-divisions[data-orientation="horizontal"][data-count="2"]')
        self.assertIn("grid-template-rows: repeat(2, 1fr)", two_row)
        self.assertNotEqual(two_col, two_row)

    def test_single_layout_hides_every_division_but_the_primary(self):
        css = _CSS_PATH.read_text(encoding="utf-8")
        body = _rule_body(css, '.display-divisions[data-count="1"] [data-division]:not([data-division="0"])')
        self.assertIn("display: none", body)

    def test_layout_choice_is_never_a_dead_decorative_no_op(self):
        # Every control carries a real, distinct id/data attribute the
        # JS reads to set .display-divisions[data-count]/[data-orientation]
        # - never a bare icon with no handler, and only committed on the
        # explicit Apply click (never re-rendering on every keystroke).
        js = _JS_PATH.read_text(encoding="utf-8")
        self.assertIn("divisionsRoot.dataset.count = String(quantity)", js)
        self.assertIn("divisionsRoot.dataset.orientation = orientation", js)
        self.assertIn("display-layout-apply", js)
        self.assertIn("MAX_DISPLAY_DIVISIONS = 6", js)


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

    def test_launcher_and_toolbox_become_fixed_overlay_drawers_at_narrow_width(self):
        # CLAUDE-P40-E2B1: the Launcher panel's own narrow-screen drawer
        # rule now lives in main.css alongside the panel's other rules
        # (app-shell-level), separate from Toolbox's (Workspace-local) -
        # two independent rules, not one combined selector, since the
        # panels are no longer siblings in the same grid. Both
        # ".launcher-panel {" and ".workspace-pane-toolbox {" are each
        # declared TWICE in this stylesheet (a base rule, then a narrow-
        # width override) so _rule_body's "first match" helper can't
        # target the override specifically - matched directly instead.
        self.assertIn(
            "@media (max-width: 640px) {\n    .launcher-panel {\n        position: fixed",
            self.css,
        )
        self.assertIn(
            "@media (max-width: 640px) {\n    .workspace-pane-toolbox {\n        position: fixed",
            self.css,
        )

    def test_multi_division_layouts_collapse_to_one_column_at_medium_width(self):
        # SUPERSEDED (CLAUDE-P40-E3A): mobile-first now, not a max-width
        # override - .display-divisions' own BASE rule (outside any media
        # query) is already single-column/stacked; the dynamic multi-
        # column/multi-row geometry only activates inside
        # @media (min-width: 900px), so anything narrower automatically
        # gets the single-column base rule with no override needed.
        base_body = _rule_body(self.css, ".display-divisions")
        self.assertIn("grid-template-columns: 1fr", base_body)
        self.assertIn("@media (min-width: 900px)", self.css)

    def test_escape_closes_narrow_drawers(self):
        # SUPERSEDED (CLAUDE-P40-E3A): base.html's own divider script
        # uses the direct max-width threshold check now, not the old
        # inverted min-width one - same 640/641px breakpoint, different
        # phrasing.
        base_html = (Path(__file__).resolve().parent.parent / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertIn("e.key !== 'Escape'", base_html)
        self.assertIn("matchMedia('(max-width: 640px)')", base_html)


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
        # SUPERSEDED (CLAUDE-P40-E3A): the old fixed 2-division
        # side-by-side/stacked preset selectors are retired - divisions
        # are separated by a border on the SECOND-and-later division
        # (:not(:first-child)) now, real for any count/orientation, not
        # just a hardcoded 2-way split.
        body = _rule_body(self.css, '.display-divisions[data-orientation="vertical"] .display-division:not(:first-child)')
        self.assertNotIn("box-shadow", body)
        self.assertNotIn("border-radius", body)
        self.assertIn("border-left", body)


if __name__ == "__main__":
    unittest.main()
