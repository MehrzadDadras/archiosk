"""
CLAUDE-P40-E3A-QA - Browser-Grounded Layout Reconciliation, Interaction
Verification, and Test-Change Audit.

Focused regression coverage for exactly what THIS stage changed, in
response to a real product-owner browser walkthrough of P40-E3A - not a
repeat of test_p40e3a_layout_reconciliation.py's own broader contract
coverage (that stays valid and untouched; this file only covers the new
corrections layered on top of it):

- RFIs branch renders unconditionally (like its Documents/Investigations
  siblings), never silently disappearing at zero drafts.
- The six-division ceiling, verified explicitly per this stage's own
  Section 5 instruction not to reconsider it, only test/report it.
- One Chat size toggle, not two simultaneously-visible preset buttons.
- Toolbox's project-level sections (Add a Document/Removed Items/Project
  Data Management) are scoped to the no-selection state only, not
  unconditionally bleeding into an open Investigation/Document view.
- Toolbox has a plain neutral default background (a real gap from this
  stage's own earlier CSS, not a deliberate omission).
- No duplicate/redundant divider lines stacked at the top of Chat.
- The panel-divider's z-index stays below every overlay it must never
  show through.

No browser/rendering tool exists in this environment - CSS/JS source
assertions verify structural facts a browser would act on; HTML
assertions verify server-rendered markup. Stated honestly rather than
skipped.
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
from services.case_workspace import AnalysisTrigger, CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_BASE_HTML_PATH = Path(__file__).resolve().parent.parent / "templates" / "base.html"
_CASE_WORKSPACE_HTML_PATH = Path(__file__).resolve().parent.parent / "templates" / "case_workspace.html"
_MACROS_HTML_PATH = Path(__file__).resolve().parent.parent / "templates" / "_macros.html"
_JS_PATH = Path(__file__).resolve().parent.parent / "static" / "js" / "case_workspace.js"
_CSS_PATH = Path(__file__).resolve().parent.parent / "static" / "css" / "main.css"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40e3a_qa_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="e3aqa_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="e3aqa_owner", project_name="Riverside Terminal E3A-QA Workspace")
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
# RFIs branch always visible (Section 4)
# ---------------------------------------------------------------------------

class RFIsBranchAlwaysRendersTests(_BaseTestCase):
    def test_rfis_branch_renders_even_with_zero_drafts(self):
        # Product-owner browser observation: "RFIs are absent from the
        # visible active-Project hierarchy." Root cause: the RFIs <li>
        # was the only branch of the four (Overview/Documents/
        # Investigations/RFIs/Chats) gated on non-empty content - a
        # Project with no RFI drafts yet lost the whole row instead of
        # showing "RFIs (0)" like its siblings always do at any count.
        client = self._client_as("e3aqa_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn(">RFI Correspondence <span class=\"launcher-count\">0</span>", body)

    def test_rfis_branch_count_reflects_real_drafts_and_filters_unauthorized(self):
        # Same hermetic setup pattern as tests/test_capability_architecture.py's
        # own _make_finding_with_validation - record_analysis against the
        # rfq_rfp_document Source ingest_upload already registers, then a
        # Reviewer Validation (create_rfi_draft's own precondition), then
        # the RFI draft itself - all via the store directly, matching this
        # repo's established convention for setting up an RFI-eligible
        # Finding without a bespoke constructor.
        store = self._store()
        workspace = store.get(self.project_id)
        case = store.create_case(workspace, title="Foundation Review", objective="x", created_by="e3aqa_owner")
        source_id = next(s for s in workspace.sources if s["kind"] == "rfq_rfp_document")["id"]
        trigger = AnalysisTrigger(trigger_type="user_initiated", triggered_by_actor="e3aqa_owner")
        analysis = store.record_analysis(
            workspace, case_id=case["id"], source_ids=[source_id], objective="x",
            engine_name="test", engine_version="1.0",
            findings=[{"statement": "Footing depth inconsistent with drawing.", "machine_confidence": 0.9, "source_id": source_id}],
            trigger=trigger,
        )
        finding_id = analysis["finding_ids"][0]
        workspace = store.get(self.project_id)
        store.record_reviewer_validation(workspace, finding_id=finding_id, validation="Correct", reviewer="e3aqa_owner")
        workspace = store.get(self.project_id)
        store.create_rfi_draft(workspace, finding_id=finding_id, question_text="Confirm footing depth?", created_by="e3aqa_owner")

        client = self._client_as("e3aqa_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn(">RFI Correspondence <span class=\"launcher-count\">1</span>", body)


# ---------------------------------------------------------------------------
# Six-division ceiling - verified explicitly, not reconsidered (Section 5)
# ---------------------------------------------------------------------------

class SixDivisionCeilingTests(_BaseTestCase):
    def test_exactly_six_divisions_zero_through_five_server_rendered(self):
        client = self._client_as("e3aqa_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for i in range(6):
            self.assertIn(f'id="display-division-{i}"', body)
        self.assertNotIn('id="display-division-6"', body)

    def test_max_display_divisions_constant_is_six_in_js(self):
        js = _JS_PATH.read_text(encoding="utf-8")
        self.assertRegex(js, r"MAX_DISPLAY_DIVISIONS\s*=\s*6")

    def test_quantity_stepper_cannot_exceed_six(self):
        # SUPERSEDED (CLAUDE-P40-VW4): the single shared pendingQuantity
        # clamped via Math.min is retired - Vertical and Horizontal are
        # now independent, and the ceiling applies to their PRODUCT, so
        # each increment handler guards on (thisAxis + 1) * otherAxis
        # rather than clamping one shared number.
        js = _JS_PATH.read_text(encoding="utf-8")
        self.assertIn("if ((pendingVertical + 1) * pendingHorizontal > MAX_DISPLAY_DIVISIONS) return;", js)
        self.assertIn("if (pendingVertical * (pendingHorizontal + 1) > MAX_DISPLAY_DIVISIONS) return;", js)


# ---------------------------------------------------------------------------
# Chat: one size toggle, not two presets (Section 10)
# ---------------------------------------------------------------------------

class ChatSizeToggleTests(_BaseTestCase):
    def test_exactly_one_size_toggle_present(self):
        client = self._client_as("e3aqa_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertEqual(body.count('id="conversation-size-toggle"'), 1)
        self.assertNotIn("conversation-preset-btn", body)
        self.assertNotIn("conversation-dock-presets", body)

    def test_toggle_label_and_state_stay_in_sync_with_height(self):
        js = _JS_PATH.read_text(encoding="utf-8")
        self.assertIn("function syncSizeToggle(px)", js)
        # Called from applyHeight itself, so every resize source (drag,
        # keyboard, or the toggle's own click) keeps the label correct -
        # not just the toggle's own click handler.
        self.assertIn("syncSizeToggle(clamped)", js)

    def test_planning_copy_removed_from_rendered_page(self):
        # Checked against actual rendered output, not the macro's own
        # source text - the macro file's explanatory comment about this
        # removal legitimately still mentions the retired phrase.
        client = self._client_as("e3aqa_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn("planned, not available yet", body)


# ---------------------------------------------------------------------------
# Toolbox contextual scoping (Section 9)
#
# CLAUDE-P40-VW2 superseded this class's original premise: "Add a
# Document"/"Removed Items"/"Project Data Management" used to live IN
# Toolbox and only render there in the no-selection state. They have
# since been relocated wholesale to Lists' own "Project Tools" branch
# (base.html), which - like its Documents/Investigations/RFIs/Chats
# siblings - is always part of the active Project's rendered hierarchy
# regardless of what's currently selected (collapsed by default, not
# absent). These tests now scope their assertions to the Toolbox
# region specifically (workspace-toolbox-panel), the thing that
# actually changed, rather than the whole page body.
# ---------------------------------------------------------------------------

class ToolboxContextualScopingTests(_BaseTestCase):
    def _toolbox_html(self, body: str) -> str:
        start = body.index('id="workspace-toolbox-panel"')
        return body[start:body.index("</aside>", start)]

    def test_project_level_sections_absent_from_toolbox_when_nothing_selected(self):
        client = self._client_as("e3aqa_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        toolbox = self._toolbox_html(body)
        self.assertNotIn("Add a Document", toolbox)
        self.assertNotIn("Removed Items", toolbox)
        self.assertNotIn("Remove Project", toolbox)

    def test_project_level_sections_absent_from_toolbox_when_a_document_is_selected(self):
        client = self._client_as("e3aqa_owner", 1)
        source_id = self._store().get(self.project_id).sources[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?source={source_id}").get_data(as_text=True)
        toolbox = self._toolbox_html(body)
        self.assertNotIn("Add a Document", toolbox)
        self.assertNotIn("Removed Items", toolbox)

    def test_project_level_sections_absent_from_toolbox_when_an_investigation_is_selected(self):
        client = self._client_as("e3aqa_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Load Path Review", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        toolbox = self._toolbox_html(body)
        self.assertNotIn("Add a Document", toolbox)
        self.assertNotIn("Removed Items", toolbox)
        self.assertIn("Investigation", toolbox)

    def test_project_level_sections_present_in_lists_panel_regardless_of_selection(self):
        # CLAUDE-P40-VW2: unlike the old Toolbox placement, Lists'
        # Project Tools branch is part of the always-rendered active-
        # Project hierarchy - present whether or not a Document/
        # Investigation happens to be selected, exactly like its
        # Documents/Investigations siblings.
        client = self._client_as("e3aqa_owner", 1)
        source_id = self._store().get(self.project_id).sources[0]["id"]
        for url in (
            f"/projects/{self.project_id}/workspace",
            f"/projects/{self.project_id}/workspace?source={source_id}",
        ):
            body = client.get(url).get_data(as_text=True)
            self.assertIn('id="project-sources-add-document"', body, url)
            self.assertIn('id="project-removed-items"', body, url)


# ---------------------------------------------------------------------------
# Neutral default appearance (Section 8)
# ---------------------------------------------------------------------------

class NeutralDefaultAppearanceTests(unittest.TestCase):
    def test_toolbox_has_a_plain_default_background_not_only_a_tinted_one(self):
        # CLAUDE-P40-EYE1: the background now lives on .workspace-right-
        # column (the new full-height column containing Toolbox AND
        # Eye) - .workspace-pane-toolbox itself paints nothing of its
        # own anymore (mirrors .lists-pane inside .launcher-panel), but
        # the underlying concern this test checks ("a plain neutral
        # background is reliably painted, not only a tinted one") is
        # still true, just one level up.
        css = _CSS_PATH.read_text(encoding="utf-8")
        rule = re.search(r"^\.workspace-right-column\s*\{[^}]*\}", css, re.M | re.S)
        self.assertIsNotNone(rule, "no base .workspace-right-column rule found")
        self.assertIn("background: var(--surface-primary)", rule.group(0))

    def test_chat_has_no_duplicate_top_divider(self):
        css = _CSS_PATH.read_text(encoding="utf-8")
        chat_region_rule = re.search(r"\.chat-region\s*\{[^}]*\}", css, re.S)
        self.assertIsNotNone(chat_region_rule)
        self.assertNotIn("border-top", chat_region_rule.group(0))

    def test_conversation_dock_panel_zeroes_the_inherited_accordion_border(self):
        css = _CSS_PATH.read_text(encoding="utf-8")
        panel_rule = re.search(r"\.conversation-dock-panel\s*\{[^}]*\}", css, re.S)
        self.assertIsNotNone(panel_rule)
        self.assertIn("border-top: none", panel_rule.group(0))


# ---------------------------------------------------------------------------
# Overlay stacking: divider must never outrank a menu/context-menu (Section 6/7)
# ---------------------------------------------------------------------------

class OverlayStackingTests(unittest.TestCase):
    def _z_index(self, css: str, selector_pattern: str) -> int:
        rule = re.search(selector_pattern + r"\s*\{[^}]*\}", css, re.S)
        self.assertIsNotNone(rule, f"no rule found for {selector_pattern}")
        match = re.search(r"z-index:\s*(-?\d+)", rule.group(0))
        self.assertIsNotNone(match, f"no z-index found for {selector_pattern}")
        return int(match.group(1))

    def test_panel_divider_z_index_below_top_bar_menus_and_context_menu(self):
        css = _CSS_PATH.read_text(encoding="utf-8")
        divider_z = self._z_index(css, r"\.panel-divider")
        menu_z = self._z_index(css, r"\.workspace-layout-options,\n\.workspace-appearance-options,\n\.workspace-user-options")
        context_menu_z = self._z_index(css, r"\.display-context-menu")
        self.assertLess(divider_z, menu_z)
        self.assertLess(divider_z, context_menu_z)

    def test_context_menu_position_is_clamped_to_the_viewport_in_js(self):
        js = _JS_PATH.read_text(encoding="utf-8")
        self.assertIn("window.innerWidth", js)
        self.assertIn("window.innerHeight", js)
        self.assertIn("Math.max(margin, Math.min(x, maxLeft))", js)
