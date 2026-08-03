"""
CLAUDE-P40-E3A - Numbered Prototype Layout Transfer and Interface
Reconciliation.

New regression coverage for this stage's own contract (the prompt's own
"Section 14" enumerated list, reconstructed here from the verbatim
Sections 0-13 after the exact original wording was lost to an earlier
context compaction - see this stage's completion report). Complements,
rather than duplicates, the file-by-file fixes already made to the
pre-existing suite (test_p40e2b1_single_launcher_and_directories.py,
test_p40e2b1a_recursive_projection.py, test_p40e2b_flexible_workspace_frame.py,
test_p40e_unified_workspace.py, and others) to reflect this stage's own
architecture.

No browser/rendering tool exists in this environment - these tests
verify what IS provable without one: server-rendered HTML/attributes,
real route behavior, and the actual CSS/JS text a browser would act on.
Stated honestly rather than skipped.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import json
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
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40e3a_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="e3a_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="e3a_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        self.doc = self._ingest(owner="e3a_owner", project_name="Cedar Harbour E3A Workspace")
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
# Section 3: top bar
# ---------------------------------------------------------------------------

class TopBarContractTests(_BaseTestCase):
    def test_identity_breadcrumb_and_user_menu_present(self):
        client = self._client_as("e3a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('class="workspace-topbar-brand"', body)
        self.assertIn('class="workspace-topbar-context"', body)
        self.assertIn('id="workspace-user-menu"', body)
        self.assertIn("e3a_owner", body)
        self.assertIn(f'href="{"/logout"}"', body)

    def test_display_layout_and_appearance_menus_only_within_a_workspace(self):
        client = self._client_as("e3a_owner", 1)
        workspace_body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="workspace-layout-menu"', workspace_body)
        self.assertIn('id="workspace-appearance-menu"', workspace_body)

        for url in ("/", "/projects", "/upload", "/removed-projects"):
            body = client.get(url).get_data(as_text=True)
            self.assertNotIn('id="workspace-layout-menu"', body, url)
            self.assertNotIn('id="workspace-appearance-menu"', body, url)

    def test_excluded_top_bar_controls_never_render(self):
        # Section 3: "Do not restore: Home; global search magnifier;
        # Open Project; Project Gateway; duplicate navigation controls."
        client = self._client_as("e3a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        topbar = body[body.index('class="workspace-topbar"'):body.index('id="app-shell-body-marker"') if 'id="app-shell-body-marker"' in body else body.index('class="app-shell-body"')]
        self.assertNotIn("global-search", topbar)
        self.assertNotIn("magnifier", topbar)
        self.assertNotIn(">Open Project<", topbar)
        self.assertNotIn("Project Gateway", topbar)
        self.assertNotIn("workspace-overflow-menu", topbar)

    def test_no_nonfunctional_drawing_or_tagging_controls(self):
        # Section 3/6/8: "Do not add nonfunctional Undo, Redo, drawing or
        # tagging controls during this stage."
        #
        # CLAUDE-P40-VW8-QA (reversibility correction) later added a
        # REAL, functional Undo control (#conv-selection-undo) - reverses
        # a just-removed Tag/Highlight/Important/Question occurrence via
        # the same add-Tag route, not a decorative placeholder.
        #
        # CLAUDE-P40-VW7A-QA2 later added REAL, functional PDF annotation
        # Undo/Redo (#doc-annotate-undo/#doc-annotate-redo - genuine undo/
        # redo stacks over annotation add/delete operations, see
        # static/js/pdf_viewer.js's own undo()/redo()) and a real
        # freehand-drawing ("ink") annotation tool (#doc-annotate-ink) -
        # this test's own underlying constraint ("no NONFUNCTIONAL Undo/
        # Redo control") is still satisfied by all of them; only the
        # blanket substring checks needed narrowing to exclude these
        # specific, real controls, the same precedent the VW8-QA
        # correction above already established. paint-bucket/
        # color-palette/chat-tag remain genuinely out of scope and still
        # checked as-is; "drawing-tool" only ever referred to a literal
        # forbidden id/class of that exact name, which #doc-annotate-ink
        # does not use, so it needed no narrowing.
        client = self._client_as("e3a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="conv-selection-undo"', body)  # the one real, functional Undo control
        self.assertIn('id="doc-annotate-undo"', body)  # real annotation Undo
        self.assertIn('id="doc-annotate-redo"', body)  # real annotation Redo
        body_without_real_controls = re.sub(r'<button[^>]*id="conv-selection-undo"[^>]*>[^<]*</button>', "", body)
        body_without_real_controls = re.sub(r'<button[^>]*id="doc-annotate-undo"[^>]*>[^<]*</button>', "", body_without_real_controls)
        body_without_real_controls = re.sub(r'<button[^>]*id="doc-annotate-redo"[^>]*>[^<]*</button>', "", body_without_real_controls)
        for token in ("Undo", "Redo", "drawing-tool", "paint-bucket", "color-palette", "chat-tag"):
            self.assertNotIn(token, body_without_real_controls, token)


# ---------------------------------------------------------------------------
# Section 4: Lists hierarchy
# ---------------------------------------------------------------------------

class ListsHierarchyContractTests(_BaseTestCase):
    def test_real_authorized_names_render_not_prototype_examples(self):
        client = self._client_as("e3a_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Schedule Conflict Review", "objective": ""})
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Cedar Harbour E3A Workspace", body)
        self.assertIn("rfp.txt", body)
        self.assertIn("Schedule Conflict Review", body)
        # None of the numbered prototype's own example names/labels leak in.
        for prototype_artifact in ("01", "02U", "05", "11-58"):
            self.assertNotIn(f">{prototype_artifact}<", body)

    def test_active_project_branch_pre_rendered_open_others_closed(self):
        # CLAUDE-P40-VW7B, Section 3 superseded the "others render as a
        # plain closed leaf" half of this test - another Project no
        # longer renders AT ALL inside an open Project's Lists (not
        # even as a closed leaf) - see OpenedProjectPortfolioRemovalTests
        # in tests/test_p40vw7b_vestibule_and_attention.py for that
        # explicit regression coverage. The still-valid half (the
        # ACTIVE project's own branch pre-renders open) is preserved
        # below.
        self._ingest(owner="e3a_owner", project_name="A Second Project Not Open")
        client = self._client_as("e3a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)

        self.assertNotIn("A Second Project Not Open", body)

        panel_start = body.index('<nav class="launcher-panel"')
        active_pos = body.index("Cedar Harbour E3A Workspace", panel_start)
        active_tail = body[active_pos:active_pos + 400]
        self.assertIn('<ul class="tree-children" data-tree-open>', active_tail)

    def test_unauthorized_project_names_never_render(self):
        # Admins can see every Project by design (P32) - a non-admin
        # reviewer with no access to this OTHER project must not see its
        # name leak into the shared, every-page Lists nav (CLAUDE-P32's
        # own real bypass this function's history already documents).
        owner_client = self._client_as("e3a_owner", 1)
        owner_client.post(f"/projects/{self.project_id}/workspace/access/grant", data={"username": "e3a_outsider"})
        self._ingest(owner="e3a_owner", project_name="Owner Only Project Not Granted")

        outsider_client = self._client_as("e3a_outsider", 2, role="read_only")
        body = outsider_client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn("Owner Only Project Not Granted", body)

    def test_no_other_project_name_duplication_between_lists_and_display(self):
        # The CURRENT project's own display title legitimately appears in
        # Overview content (breadcrumb, edit-details form, etc.) - the
        # real invariant is that a DIFFERENT project's name never leaks
        # into this project's own Display (already covered for Lists
        # itself by test_p40e2b1a_recursive_projection.py's own
        # duplication tests; checked here against Display specifically).
        other = self._ingest(owner="e3a_owner", project_name="A Distinctly Different Project")
        client = self._client_as("e3a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        display_start = body.index('class="workspace-pane-display"')
        self.assertNotIn("A Distinctly Different Project", body[display_start:])

    def test_no_document_investigation_second_listing_in_display(self):
        client = self._client_as("e3a_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "No Second Listing Investigation", "objective": ""})
        body = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        display_start = body.index('class="workspace-pane-display"')
        display_html = body[display_start:]
        # "rfp.txt" and the Investigation title legitimately appear once
        # in Lists; Overview's own Active Work listing also legitimately
        # names the Investigation (that's real selected content, not a
        # second navigation directory) - the thing forbidden is a
        # standalone Documents/Investigations DIRECTORY inside Display.
        self.assertNotIn('id="project-sources"', display_html)
        self.assertNotIn("display-branch-nav", display_html)


# ---------------------------------------------------------------------------
# Section 5: Display
# ---------------------------------------------------------------------------

class DisplayBlankByDefaultTests(_BaseTestCase):
    def test_blank_when_nothing_selected(self):
        # CLAUDE-P40-LTH1: scoped to the Display region itself (this
        # test's own actual subject - "Display blank by default") rather
        # than the whole page body. Lists' own permanent Page Thumbnails
        # pane (CLAUDE-P40-VW7A-QA2, corrected CLAUDE-P40-LTH1) now
        # always renders a real, legitimate #thumbnails-empty-state
        # element on every page, including this one - an unrelated,
        # correct use of the substring "empty-state" that a whole-body
        # search would incorrectly flag.
        client = self._client_as("e3a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        display = body[body.index('id="workspace-display-panel"'):body.index("</main>")]
        for forbidden in (
            "project-card", "UUID", "search box", "onboarding",
            "select a Project", "empty-state", "project-home",
        ):
            self.assertNotIn(forbidden, display, forbidden)
        self.assertNotIn('id="project-overview"', display)

    def test_overview_leaf_shows_consolidated_content(self):
        client = self._client_as("e3a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertIn('id="project-overview"', body)
        self.assertIn("Project Instructions", body)
        self.assertIn(">RFIs<", body)

    def test_document_leaf_projects_its_content(self):
        client = self._client_as("e3a_owner", 1)
        source_id = self._store().get(self.project_id).sources[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?source={source_id}").get_data(as_text=True)
        self.assertIn("workspace-pane-document", body)

    def test_investigation_leaf_projects_its_content(self):
        client = self._client_as("e3a_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Projected Investigation", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        self.assertIn("<h2>Projected Investigation</h2>", body)

    def test_rfi_leaf_opens_its_owning_investigation(self):
        # No standalone RFI page exists - Lists routes an RFI leaf to the
        # owning Investigation's own ?case= URL, where the draft is
        # visible in Toolbox (Section 4's own documented interpretation).
        client = self._client_as("e3a_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "RFI Source Investigation", "objective": ""})
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('href="{}?case='.format(f"/projects/{self.project_id}/workspace"), body)


# ---------------------------------------------------------------------------
# Section 6: multi-Display
# ---------------------------------------------------------------------------

class MultiDisplayMarkupTests(_BaseTestCase):
    def test_six_divisions_present_zero_through_five(self):
        client = self._client_as("e3a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for i in range(6):
            self.assertIn(f'id="display-division-{i}"', body)

    def test_dynamic_vertical_horizontal_and_count_attributes_not_fixed_presets(self):
        # SUPERSEDED (CLAUDE-P40-VW4): data-orientation is retired -
        # replaced by two independent axes, data-vertical/data-horizontal.
        client = self._client_as("e3a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-vertical="1"', body)
        self.assertIn('data-horizontal="1"', body)
        self.assertIn('data-count="1"', body)
        self.assertNotIn("data-layout=", body)
        self.assertNotIn("data-orientation=", body)

    def test_divisions_one_through_five_have_header_and_close_division_zero_does_not(self):
        client = self._client_as("e3a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for i in range(1, 6):
            self.assertIn(f'data-division-close="{i}"', body)
        division_zero = body[body.index('id="display-division-0"'):body.index('id="display-division-1"')]
        self.assertNotIn("data-division-close", division_zero)

    def test_context_menu_offers_only_close_divide_vertical_horizontal_apply(self):
        # SUPERSEDED (CLAUDE-P40-VW4): the either/or direction radiogroup
        # is retired - replaced by two independent Vertical/Horizontal
        # steppers, same as the top-bar control.
        client = self._client_as("e3a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="display-context-menu"', body)
        menu = body[body.index('id="display-context-menu"'):body.index("</body>")]
        menu = menu[:menu.index("</div>\n    </div>") + 10] if "</div>\n    </div>" in menu else menu[:2000]
        self.assertIn('id="display-context-close"', body)
        self.assertIn('id="display-context-vertical-decrement"', body)
        self.assertIn('id="display-context-vertical-increment"', body)
        self.assertIn('id="display-context-horizontal-decrement"', body)
        self.assertIn('id="display-context-horizontal-increment"', body)
        self.assertIn('id="display-context-apply"', body)
        self.assertNotIn('id="display-context-orientation-vertical"', body)
        # No drawing "modes" (Section 6's own explicit exclusion).
        self.assertNotIn("drawing-mode", body)

    def test_max_display_divisions_is_six_and_documented(self):
        js = _JS_PATH.read_text(encoding="utf-8")
        self.assertIn("MAX_DISPLAY_DIVISIONS = 6", js)


# ---------------------------------------------------------------------------
# Section 7-8: Toolbox
# ---------------------------------------------------------------------------

class ToolboxContractTests(_BaseTestCase):
    def test_toolbox_and_chat_absent_outside_a_workspace(self):
        client = self._client_as("e3a_owner", 1)
        for url in ("/", "/projects", "/upload", "/removed-projects"):
            body = client.get(url).get_data(as_text=True)
            self.assertNotIn('id="workspace-toolbox-panel"', body, url)
            self.assertNotIn('id="chat-region"', body, url)

    def test_toolbox_never_duplicates_new_project_removed_projects_or_security(self):
        # CLAUDE-P40-EYE1: was sliced to id="chat-region" - Chat now
        # renders BEFORE the Toolbox/Eye right column in DOM order (see
        # test_toolbox_empty_when_nothing_selected's own comment below),
        # which silently made this slice empty (body.index for the START
        # marker landing AFTER the END marker) and every assertNotIn
        # below vacuously true regardless of the real content - fixed to
        # the Toolbox <aside>'s own closing tag, a real, DOM-accurate
        # boundary.
        client = self._client_as("e3a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        start = body.index('id="workspace-toolbox-panel"')
        toolbox = body[start:body.index("</aside>", start)]
        self.assertNotIn("+ New Project", toolbox)
        self.assertNotIn("Removed Projects", toolbox)
        self.assertNotIn(">Security<", toolbox)

    def test_toolbox_empty_when_nothing_selected(self):
        # CLAUDE-P40-EYE1: Chat now renders BEFORE the Toolbox/Eye right
        # column in DOM order (Chat is nested inside .workspace-main-
        # column, itself before .workspace-right-column as a sibling of
        # Lists) - slicing to the next "</aside>" (the Toolbox <aside>'s
        # own closing tag) is DOM-structure-accurate regardless of
        # ordering elsewhere, unlike the old id="chat-region" boundary.
        client = self._client_as("e3a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        start = body.index('id="workspace-toolbox-panel"')
        toolbox = body[start:body.index("</aside>", start)]
        self.assertIn("No Investigation or Document is currently selected", toolbox)


# ---------------------------------------------------------------------------
# Section 12: required preservation (spot checks)
# ---------------------------------------------------------------------------

class PreservationSpotCheckTests(_BaseTestCase):
    def test_get_never_mutates_the_workspace_record_beyond_last_viewed_by(self):
        workspace_path = self.tmp_dir / f"{self.project_id}.workspace.json"
        before_raw = json.loads(workspace_path.read_text(encoding="utf-8"))

        client = self._client_as("e3a_owner", 1)
        client.get(f"/projects/{self.project_id}/workspace")
        client.get(f"/projects/{self.project_id}/workspace?view=overview")
        source_id = self._store().get(self.project_id).sources[0]["id"]
        client.get(f"/projects/{self.project_id}/workspace?source={source_id}")

        after_raw = json.loads(workspace_path.read_text(encoding="utf-8"))
        changed_keys = {k for k in set(before_raw) | set(after_raw) if before_raw.get(k) != after_raw.get(k)}
        self.assertTrue(changed_keys.issubset({"last_viewed_by"}), changed_keys)

    def test_auth_pages_remain_isolated_from_the_shell(self):
        client = self.flask_app.test_client()
        body = client.get("/login").get_data(as_text=True)
        self.assertNotIn('id="launcher-panel"', body)
        self.assertNotIn('class="workspace-topbar"', body)

    def test_multi_display_geometry_is_presentation_state_only(self):
        # Section 6: "Multi-Display geometry may remain reviewer/device
        # presentation state. It must not alter: Project records;
        # Document records..." - the division-count/orientation control
        # writes only localStorage, never a form POST/fetch.
        js = _JS_PATH.read_text(encoding="utf-8")
        layout_section = js[js.index("setUpDisplayLayout"):js.index("setUpDisplayLayout") + 6000]
        self.assertIn("window.localStorage.setItem(layoutKey", layout_section)
        self.assertNotIn("fetch(", layout_section)


# ---------------------------------------------------------------------------
# Section 13: explicitly excluded this stage
# ---------------------------------------------------------------------------

class ExcludedFeaturesAbsentTests(_BaseTestCase):
    def test_no_new_persisted_capability_added_this_stage(self):
        client = self._client_as("e3a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for excluded in (
            "lessons-learned", "sharepoint", "autosave", "markup-persistence",
            "conversation-archive", "chat-tag", "camera-intake", "screenshot-intake",
        ):
            self.assertNotIn(excluded, body, excluded)


if __name__ == "__main__":
    unittest.main()
