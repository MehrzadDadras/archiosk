"""
CLAUDE-P40-VW4 - Independent Vertical and Horizontal Display Division
Controls.

Product-owner walkthrough correction: the Display Layout panel treated
Vertical and Horizontal as an either/or choice sharing one quantity.
Replaced with two fully independent numbers - Vertical divisions
(side-by-side columns) and Horizontal divisions (stacked rows) - both
permanently visible at once, resulting Display count = their PRODUCT,
capped at the existing ceiling of 6.

Existing Display state model examined before changing it (see
static/js/case_workspace.js's own setUpDisplayLayout): a single
`quantity` (1-6) + `orientation` ('vertical'|'horizontal') pair,
persisted as `{quantity, orientation}` in localStorage under
`beehive:display:layout:{projectId}`, applied to
`.display-divisions`'s `[data-count]`/`[data-orientation]` attributes,
which a static CSS attribute-selector table (14 valid combinations
existed for the OLD single axis; this stage's V*H<=6 space also has
14, but along two dimensions, not a linear range) turned into
grid-template-columns/rows. Extended (not replaced) that same
mechanism: `vertical`/`horizontal` are now the two source-of-truth
numbers, `quantity` is a derived value (vertical * horizontal) kept
for the parts of the function (active-target bounds, six-Display
show/hide) that only ever needed a total. The show/hide-by-index CSS
table ([data-count="N"] hides division N and beyond) is completely
unchanged, since it never depended on which axis produced the total.

Compatibility mapping (this stage's own required rule, implemented in
`normalizeStoredLayout`): a stored {quantity, orientation} shape
(pre-VW4) maps quantity 1 (either orientation) to Vertical 1/Horizontal
1; a "vertical" quantity N to Vertical N/Horizontal 1; a "horizontal"
quantity N to Vertical 1/Horizontal N. A value already in the new
{vertical, horizontal} shape passes through unchanged (idempotent).

No browser/rendering tool exists in this environment. Interactive
behaviour (button clicks, disabled states, Apply-gating, dismiss-
without-apply) is verified via JS source assertions - the exact,
deterministic code paths a browser's event loop would execute - plus
server-rendered HTML/CSS structural checks. Stated honestly rather than
skipped, matching this repo's established convention (see
test_p40e3a_qa_reconciliation.py's own docstring).
"""
from __future__ import annotations

import io
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_BASE_HTML_PATH = Path(__file__).resolve().parent.parent / "templates" / "base.html"
_CASE_WORKSPACE_HTML_PATH = Path(__file__).resolve().parent.parent / "templates" / "case_workspace.html"
_JS_PATH = Path(__file__).resolve().parent.parent / "static" / "js" / "case_workspace.js"
_CSS_PATH = Path(__file__).resolve().parent.parent / "static" / "css" / "main.css"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw4_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="vw4_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="vw4_owner", project_name="Riverside Terminal VW4 Workspace")
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

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)


# ---------------------------------------------------------------------------
# Default state: Vertical 1, Horizontal 1
# ---------------------------------------------------------------------------

class DefaultStateTests(_BaseTestCase):
    def test_default_vertical_and_horizontal_are_both_one(self):
        client = self._client_as("vw4_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-vertical="1"', body)
        self.assertIn('data-horizontal="1"', body)
        self.assertIn('data-count="1"', body)

    def test_both_top_bar_steppers_default_to_one(self):
        client = self._client_as("vw4_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        start = body.index('id="workspace-layout-menu"')
        menu = body[start:body.index("</details>", start)]
        self.assertIn('id="display-vertical-value" aria-live="polite">1<', menu)
        self.assertIn('id="display-horizontal-value" aria-live="polite">1<', menu)


# ---------------------------------------------------------------------------
# Both controls visible simultaneously, real steppers, no either/or choice
# ---------------------------------------------------------------------------

class BothControlsAlwaysVisibleTests(_BaseTestCase):
    def _top_bar_menu(self, body: str) -> str:
        start = body.index('id="workspace-layout-menu"')
        return body[start:body.index("</details>", start)]

    def test_vertical_and_horizontal_steppers_both_present_in_top_bar(self):
        client = self._client_as("vw4_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        menu = self._top_bar_menu(body)
        for control in (
            "display-vertical-decrement", "display-vertical-value", "display-vertical-increment",
            "display-horizontal-decrement", "display-horizontal-value", "display-horizontal-increment",
        ):
            self.assertIn(f'id="{control}"', menu, control)

    def test_no_either_or_orientation_choice_remains(self):
        client = self._client_as("vw4_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        menu = self._top_bar_menu(body)
        self.assertNotIn("data-display-orientation", menu)
        self.assertNotIn('id="display-orientation-vertical"', menu)

    def test_apply_present_exactly_once_in_top_bar_menu(self):
        client = self._client_as("vw4_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        menu = self._top_bar_menu(body)
        self.assertEqual(menu.count('id="display-layout-apply"'), 1)

    def test_limit_note_present_in_both_menus(self):
        client = self._client_as("vw4_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertEqual(body.count("workspace-layout-limit-note"), 2)  # top-bar + context menu
        self.assertIn("Maximum 6 Displays total", body)


# ---------------------------------------------------------------------------
# Independent increment/decrement, minimum 1, six-Display ceiling
# ---------------------------------------------------------------------------

class IndependentAxisJsTests(unittest.TestCase):
    def setUp(self):
        self.js = _JS_PATH.read_text(encoding="utf-8")

    def test_vertical_and_horizontal_are_separate_state_variables(self):
        self.assertIn("let vertical = 1;", self.js)
        self.assertIn("let horizontal = 1;", self.js)

    def test_apply_layout_takes_two_independent_arguments(self):
        self.assertIn("function applyLayout(nextVertical, nextHorizontal, persist)", self.js)

    def test_decrementing_vertical_never_touches_horizontal(self):
        block = self._handler("vDec.addEventListener")
        self.assertIn("pendingVertical", block)
        self.assertNotIn("pendingHorizontal =", block)

    def test_incrementing_vertical_never_touches_horizontal(self):
        block = self._handler("vInc.addEventListener")
        self.assertIn("pendingVertical", block)
        self.assertNotIn("pendingHorizontal =", block)

    def test_decrementing_horizontal_never_touches_vertical(self):
        block = self._handler("hDec.addEventListener")
        self.assertIn("pendingHorizontal", block)
        self.assertNotIn("pendingVertical =", block)

    def test_incrementing_horizontal_never_touches_vertical(self):
        block = self._handler("hInc.addEventListener")
        self.assertIn("pendingHorizontal", block)
        self.assertNotIn("pendingVertical =", block)

    def test_minimum_is_clamped_to_one_on_both_axes(self):
        self.assertIn("pendingVertical = Math.max(MIN_DISPLAY_DIVISIONS, pendingVertical - 1);", self.js)
        self.assertIn("pendingHorizontal = Math.max(MIN_DISPLAY_DIVISIONS, pendingHorizontal - 1);", self.js)
        self.assertIn("const MIN_DISPLAY_DIVISIONS = 1;", self.js)

    def test_six_display_ceiling_applies_to_the_product_not_either_axis(self):
        self.assertIn("if ((pendingVertical + 1) * pendingHorizontal > MAX_DISPLAY_DIVISIONS) return;", self.js)
        self.assertIn("if (pendingVertical * (pendingHorizontal + 1) > MAX_DISPLAY_DIVISIONS) return;", self.js)
        self.assertIn("const MAX_DISPLAY_DIVISIONS = 6;", self.js)

    def test_increment_buttons_disabled_rather_than_silently_no_op(self):
        self.assertIn("vInc.disabled = (pendingVertical + 1) * pendingHorizontal > MAX_DISPLAY_DIVISIONS;", self.js)
        self.assertIn("hInc.disabled = pendingVertical * (pendingHorizontal + 1) > MAX_DISPLAY_DIVISIONS;", self.js)

    def test_apply_layout_itself_also_enforces_the_ceiling_defensively(self):
        # Even a corrupted/hand-edited localStorage value can't produce a
        # >6 layout - applyLayout re-derives and clamps independently of
        # whether the UI-level guards were bypassed.
        self.assertIn("while (v * h > MAX_DISPLAY_DIVISIONS) {", self.js)

    def _handler(self, marker: str) -> str:
        # Two IIFEs (top-bar, context menu) each define a handler with
        # this marker text - concatenate both occurrences' bodies so a
        # single assertion covers both wiring sites at once.
        bodies = []
        pos = 0
        while True:
            idx = self.js.find(marker, pos)
            if idx == -1:
                break
            end = self.js.index(";\n", idx) + 1
            # Handlers here are one-liner arrow functions; a single
            # statement/line is enough to see whether the OTHER axis's
            # pending variable is reassigned.
            bodies.append(self.js[idx:end])
            pos = end
        self.assertTrue(bodies, f"no handler found for {marker!r}")
        return "\n".join(bodies)


# ---------------------------------------------------------------------------
# Apply required before mutation / dismissal without Apply leaves state
# unchanged
# ---------------------------------------------------------------------------

class ApplyGatingJsTests(unittest.TestCase):
    def setUp(self):
        self.js = _JS_PATH.read_text(encoding="utf-8")

    def test_only_apply_click_handlers_call_apply_layout_with_pending_values(self):
        # applyLayout(pendingVertical, pendingHorizontal) must appear only
        # inside an applyBtn click handler, never inside a stepper's own
        # click handler (Requirement 4: layout must not change until
        # Apply).
        calls = [m.start() for m in re.finditer(r"applyLayout\(pendingVertical, pendingHorizontal\)", self.js)]
        self.assertEqual(len(calls), 2, "expected exactly 2 call sites (top-bar + context menu)")
        for pos in calls:
            preceding = self.js[max(0, pos - 700):pos]
            self.assertIn("applyBtn.addEventListener", preceding)

    def test_top_bar_menu_reopen_reseeds_pending_from_applied_state(self):
        self.assertIn("menuDetails.addEventListener('toggle'", self.js)
        block = self.js[self.js.index("menuDetails.addEventListener('toggle'"):]
        block = block[:block.index("});") + 3]
        self.assertIn("pendingVertical = vertical;", block)
        self.assertIn("pendingHorizontal = horizontal;", block)

    def test_context_menu_reopen_reseeds_pending_from_applied_state_not_a_fixed_preset(self):
        block = self.js[self.js.index("function openMenu(x, y, divisionIndex)"):]
        block = block[:block.index("menu.hidden = false;")]
        self.assertIn("pendingVertical = vertical;", block)
        self.assertIn("pendingHorizontal = horizontal;", block)
        # SUPERSEDED (CLAUDE-P40-E3A): the old hardcoded "pendingQuantity = 2"
        # preset is gone - both menus now seed from the real applied state.
        self.assertNotIn("pendingQuantity = 2", self.js)


# ---------------------------------------------------------------------------
# 2x3 and 3x2 arrangements, deterministic ordering, six-Display maximum
# ---------------------------------------------------------------------------

class ArrangementSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")

    def test_grid_uses_row_major_auto_flow_for_deterministic_ordering(self):
        rule = re.search(r"\.display-divisions\s*\{([^}]*)\}", self.css, re.S)
        self.assertIsNotNone(rule)
        self.assertIn("grid-auto-flow: row", rule.group(1))

    def test_grid_template_columns_and_rows_are_independently_driven(self):
        media = re.search(r"@media \(min-width: 900px\) \{(.*?)\n\}", self.css, re.S)
        self.assertIsNotNone(media)
        block = media.group(1)
        self.assertIn("grid-template-columns: repeat(var(--display-v, 1), 1fr)", block)
        self.assertIn("grid-template-rows: repeat(var(--display-h, 1), 1fr)", block)

    def test_two_by_three_and_three_by_two_both_total_six(self):
        # 2 vertical x 3 horizontal and 3 vertical x 2 horizontal both
        # resolve to a total of 6 (data-count), while being distinct
        # arrangements (different --display-v/--display-h values) - the
        # product owner's own worked examples.
        js = _JS_PATH.read_text(encoding="utf-8")
        self.assertIn("quantity = vertical * horizontal;", js)

    def test_max_display_divisions_is_still_six(self):
        js = _JS_PATH.read_text(encoding="utf-8")
        self.assertRegex(js, r"MAX_DISPLAY_DIVISIONS\s*=\s*6")


# ---------------------------------------------------------------------------
# Right-click invocation and top-level invocation use the same mechanism,
# both correctly targeted (VW1 preservation)
# ---------------------------------------------------------------------------

class ContextMenuAndTopLevelSameMechanismTests(unittest.TestCase):
    def setUp(self):
        self.js = _JS_PATH.read_text(encoding="utf-8")

    def test_both_menus_call_the_same_sync_quantity_controls_helper(self):
        self.assertIn("syncQuantityControls('display', pendingVertical, pendingHorizontal);", self.js)
        self.assertIn("syncQuantityControls('display-context', pendingVertical, pendingHorizontal);", self.js)

    def test_context_menu_still_targets_the_right_clicked_division(self):
        self.assertIn("openMenu(e.clientX, e.clientY, parseInt(division.dataset.division, 10));", self.js)

    def test_context_menu_still_hidden_by_default_vw1_preserved(self):
        html = _CASE_WORKSPACE_HTML_PATH.read_text(encoding="utf-8")
        start = html.index('id="display-context-menu"')
        tag = html[start - 40:start + 60]
        self.assertIn("hidden", tag)

    def test_context_menu_hidden_css_override_still_present_vw1_preserved(self):
        css = _CSS_PATH.read_text(encoding="utf-8")
        self.assertRegex(css, r"\.display-context-menu\[hidden\]\s*\{[^}]*display:\s*none")

    def test_close_this_display_still_present_vw1_preserved(self):
        html = _CASE_WORKSPACE_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('id="display-context-close"', html)


# ---------------------------------------------------------------------------
# Legacy {quantity, orientation} state compatibility
# ---------------------------------------------------------------------------

class LegacyCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.js = _JS_PATH.read_text(encoding="utf-8")

    def test_normalize_function_exists_and_is_used_on_restore(self):
        self.assertIn("function normalizeStoredLayout(stored)", self.js)
        self.assertIn("const normalizedLayout = normalizeStoredLayout(storedLayout);", self.js)
        self.assertIn("applyLayout(normalizedLayout.vertical, normalizedLayout.horizontal, false);", self.js)

    def test_new_shape_passes_through_unchanged(self):
        block = self.js[self.js.index("function normalizeStoredLayout(stored)"):]
        block = block[:block.index("return { vertical: 1, horizontal: 1 };")]
        self.assertIn("Number.isInteger(stored.vertical) && Number.isInteger(stored.horizontal)", block)
        self.assertIn("return { vertical: stored.vertical, horizontal: stored.horizontal };", block)

    def test_legacy_vertical_quantity_maps_to_vertical_n_horizontal_one(self):
        block = self.js[self.js.index("function normalizeStoredLayout(stored)"):]
        block = block[:block.index("return { vertical: 1, horizontal: 1 };")]
        self.assertIn("{ vertical: stored.quantity, horizontal: 1 }", block)

    def test_legacy_horizontal_quantity_maps_to_vertical_one_horizontal_n(self):
        block = self.js[self.js.index("function normalizeStoredLayout(stored)"):]
        block = block[:block.index("return { vertical: 1, horizontal: 1 };")]
        self.assertIn("{ vertical: 1, horizontal: stored.quantity }", block)

    def test_legacy_unsplit_or_unrecognized_maps_to_one_by_one(self):
        self.assertIn("return { vertical: 1, horizontal: 1 };", self.js)


# ---------------------------------------------------------------------------
# Refresh / Stable URL Restoration, active-target routing, and content
# projection preservation
# ---------------------------------------------------------------------------

class PreservationTests(_BaseTestCase):
    def test_fresh_requests_render_identical_display_attributes(self):
        client = self._client_as("vw4_owner", 1)
        first = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        second = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for body in (first, second):
            self.assertIn('data-vertical="1"', body)
            self.assertIn('data-horizontal="1"', body)

    def test_active_target_routing_untouched(self):
        # CLAUDE-P40-VW7B: populateDivision's own signature is no longer
        # (index, sourceId) - it generalized to (index, kind, id,
        # displayName) so Investigations/Overview can also project into
        # a Display division, not only Documents (see that function's
        # own comment in case_workspace.js). The invariant this test
        # actually protects - "one active-target mechanism, not two
        # competing ones" - still holds and is asserted directly.
        js = _JS_PATH.read_text(encoding="utf-8")
        self.assertIn("window.ArchioskDisplay = {", js)
        self.assertIn("getActiveTarget: () => activeTarget,", js)
        self.assertIn("populateDivision: (index, kind, id, displayName) => populateDivision(index, kind, id, displayName, true),", js)

    def test_six_divisions_still_server_rendered_zero_through_five(self):
        client = self._client_as("vw4_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for i in range(6):
            self.assertIn(f'id="display-division-{i}"', body)
        self.assertNotIn('id="display-division-6"', body)

    def test_document_selected_still_projects_into_display(self):
        client = self._client_as("vw4_owner", 1)
        source_id = self._store().get(self.project_id).sources[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?source={source_id}").get_data(as_text=True)
        self.assertIn("workspace-pane-document", body)

    def test_authorization_and_project_isolation_untouched_outsider_still_404s(self):
        from models import User, db
        with self.flask_app.app_context():
            db.session.add(User(username="vw4_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()
        client = self._client_as("vw4_outsider", 2, role="read_only")
        resp = client.get(f"/projects/{self.project_id}/workspace")
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Appearance-mode (VW3) compatibility - no hardcoded colours
# ---------------------------------------------------------------------------

class AppearanceCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")

    def test_display_divisions_geometry_uses_only_tokens_no_hardcoded_hex(self):
        rule = re.search(r"\.display-divisions\s*\{([^}]*)\}", self.css, re.S)
        self.assertIsNotNone(rule)
        self.assertNotRegex(rule.group(1), r"#[0-9a-fA-F]{3,6}\b")
        self.assertIn("var(--border)", rule.group(1))

    def test_display_division_uses_only_tokens_no_hardcoded_hex(self):
        rule = re.search(r"(?<!s)\.display-division\s*\{([^}]*)\}", self.css, re.S)
        self.assertIsNotNone(rule)
        self.assertNotRegex(rule.group(1), r"#[0-9a-fA-F]{3,6}\b")
        self.assertIn("var(--surface-primary)", rule.group(1))

    def test_stepper_disabled_state_uses_only_tokens(self):
        rule = re.search(r"\.workspace-layout-stepper:disabled\s*\{([^}]*)\}", self.css, re.S)
        self.assertIsNotNone(rule)
        self.assertNotRegex(rule.group(1), r"#[0-9a-fA-F]{3,6}\b")
        self.assertIn("var(--text-disabled)", rule.group(1))

    def test_limit_note_uses_only_tokens(self):
        rule = re.search(r"\.workspace-layout-limit-note\s*\{([^}]*)\}", self.css, re.S)
        self.assertIsNotNone(rule)
        self.assertNotRegex(rule.group(1), r"#[0-9a-fA-F]{3,6}\b")

    def test_display_surface_still_covered_by_appearance_dark_scoping(self):
        # VW3's shared .appearance-dark rule already covers .app-main
        # (Display's own surface) - VW4 must not have introduced a
        # SECOND, competing background/color source that bypasses it.
        rule = re.search(r"\.app-main\.appearance-dark \.workspace-pane-display\s*\{([^}]*)\}", self.css, re.S)
        self.assertIsNotNone(rule, "VW3's Display dark-mode companion rule is missing")


# ---------------------------------------------------------------------------
# Keyboard and focus behaviour
# ---------------------------------------------------------------------------

class KeyboardAndFocusTests(_BaseTestCase):
    def test_all_stepper_controls_are_real_buttons_not_divs_with_click_handlers(self):
        client = self._client_as("vw4_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for control_id in (
            "display-vertical-decrement", "display-vertical-increment",
            "display-horizontal-decrement", "display-horizontal-increment",
            "display-context-vertical-decrement", "display-context-vertical-increment",
            "display-context-horizontal-decrement", "display-context-horizontal-increment",
        ):
            idx = body.index(f'id="{control_id}"')
            tag_start = body.rindex("<", 0, idx)
            self.assertTrue(body[tag_start:idx].startswith("<button"), control_id)

    def test_global_focus_visible_rule_covers_buttons(self):
        # A real global rule already exists (main.css) covering every
        # <button>, not something VW4 needed to add - confirmed present
        # so these new real <button> controls inherit it automatically.
        css = _CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("button:focus-visible", css)


if __name__ == "__main__":
    unittest.main()
