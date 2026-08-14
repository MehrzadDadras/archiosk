"""
CLAUDE-P40-VW7A-QA - Clarify Project Hierarchy and Selection State.

Product-owner report: PROJECTS (an expanded root heading), the current
Project ("Nipigon Ramp"), and the actually-selected destination within
it (e.g. "Chats") all shared the exact same literal CSS state
(`.active`), so all three read as "selected" even though only one of
them genuinely was.

Root cause, confirmed by reading the actual markup/CSS: the Project's
own name row (`lists.project.self`) carried a HARDCODED `active` class
unconditionally, identical to the class every genuinely-selected child
leaf (`lists.project.chats`, `.overview`, `.documents.leaf`, ...)
already computed conditionally - two different states sharing one
selector (`.launcher-link.active`), which also happened to be the same
selector `.launcher-heading.active` (PROJECTS) painted with its own
fill.

Fix: three now-genuinely-distinct treatments.
- `.launcher-heading` (PROJECTS, and any future equivalent root) keeps
  its already-distinct structural-title typography (uppercase, letter-
  spaced, --text-metadata) but no longer fills a background merely for
  being expanded (.active) - only real :hover/:focus-visible feedback.
- `.current-project` (new class, `lists.project.self` only) - a
  restrained left-edge marker + bold text, never `--surface-selected`.
- `.launcher-link.active` (unchanged selector/value) is now reserved
  exclusively for the ONE child leaf whose own href is what's actually
  displayed - `lists.project.self` no longer qualifies for it at all.

Also: a tree-guide connector line on every `.tree-children` (uniform,
"do not rely on background highlighting to communicate nesting"), and
whitespace-only separation on the one sibling Project row immediately
after the current Project's own child group closes ("without
introducing a heavy border").
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
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_lists_hierarchy_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="hierarchy_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, project_name, filename):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )
        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner="hierarchy_owner", project_name=project_name,
                )

    def _client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "hierarchy_owner"
            sess["role"] = "admin"
        return client

    def _lists_html(self, body):
        start = body.index('id="launcher-panel"')
        end = body.index("</nav>", start)
        return body[start:end]

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)


class SelectionTierSeparationTests(_BaseTestCase):
    """The three states (root/current-Project/selected-child) must
    render with genuinely different markup, not share one class."""

    def test_current_project_row_no_longer_carries_active_class(self):
        doc = self._ingest("Nipigon Ramp", "rfp.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        lists_html = self._lists_html(body)
        idx = lists_html.index('data-ui-ref="lists.project.self"')
        tag = lists_html[lists_html.rindex("<a", 0, idx):lists_html.index(">", idx)]
        self.assertNotIn("active", tag)
        self.assertIn("current-project", tag)

    def test_no_row_is_active_when_nothing_lists_relevant_is_selected(self):
        # CLAUDE-GO-DNA-01 (Panel Zoning): "Chats" (the old default-active
        # leaf on the bare workspace URL) relocated out of Lists entirely
        # - Lists' own remaining selectable leaves (Documents/Files) are
        # BOTH inactive until their own specific selection - so unlike
        # before, a fully bare URL now legitimately activates none of them.
        doc = self._ingest("Nipigon Ramp", "rfp.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        lists_html = self._lists_html(body)
        leaf_tags = re.findall(r'<a class="tree-leaf launcher-link[^"]*"[^>]*>', lists_html)
        active_leaves = [t for t in leaf_tags if re.search(r'\bactive\b', t)]
        self.assertEqual(len(active_leaves), 0, active_leaves)

    def test_only_one_row_carries_the_active_selection_class(self):
        # CLAUDE-GO-DNA-01 (Panel Zoning): "Chats" is gone from Lists -
        # exercised here against a Document selection instead, Lists' own
        # remaining genuinely-selectable leaf kind.
        doc = self._ingest("Nipigon Ramp", "rfp.txt")
        client = self._client()
        source_id = self._store().get(doc.project_id).sources[0]["id"]
        body = client.get(f"/projects/{doc.project_id}/workspace?source={source_id}").get_data(as_text=True)
        lists_html = self._lists_html(body)
        leaf_tags = re.findall(r'<a class="tree-leaf launcher-link[^"]*"[^>]*>', lists_html)
        active_leaves = [t for t in leaf_tags if re.search(r'\bactive\b', t)]
        self.assertEqual(len(active_leaves), 1, active_leaves)
        self.assertIn('data-ui-ref="lists.project.documents.leaf"', active_leaves[0])

    def test_projects_root_always_renders_as_a_live_project_switcher(self):
        # CLAUDE-LEFT-RAIL-01: supersedes CLAUDE-P40-VW7B's own Section 3
        # assertion (immediately above, in this test's own prior form)
        # that the PROJECTS root was removed entirely while a Project was
        # open - the Product Owner has since clarified the opposite: the
        # left rail's ONE job is "show me the projects I can work on, and
        # let me switch which one GO and the workspace are currently
        # working with," which is meaningless unless it stays visible
        # while a Project is already open (otherwise a PM managing
        # several Projects would have to leave the one they're in just to
        # see the others). PROJECTS is now unconditional - see
        # templates/base.html's own CLAUDE-LEFT-RAIL-01 comment.
        doc = self._ingest("Nipigon Ramp", "rfp.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        lists_html = self._lists_html(body)
        self.assertIn('data-ui-ref="lists.projects"', lists_html)

    def test_selecting_a_different_child_moves_the_active_class_there(self):
        # CLAUDE-GO-DNA-01 (Panel Zoning): "Overview" was itself retired
        # as a Lists leaf (redundant with lists.project.self, which
        # already opens the same page) - exercised here against
        # ?view=files (lists.project.files), Lists' other still-real
        # selectable leaf kind besides a Document.
        doc = self._ingest("Nipigon Ramp", "rfp.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?view=files").get_data(as_text=True)
        lists_html = self._lists_html(body)
        leaf_tags = re.findall(r'<a class="tree-leaf launcher-link[^"]*"[^>]*>', lists_html)
        active_leaves = [t for t in leaf_tags if re.search(r'\bactive\b', t)]
        self.assertEqual(len(active_leaves), 1)
        self.assertIn('data-ui-ref="lists.project.files"', active_leaves[0])
        # current-project row still present, still un-selected.
        self_idx = lists_html.index('data-ui-ref="lists.project.self"')
        self_tag = lists_html[lists_html.rindex("<a", 0, self_idx):lists_html.index(">", self_idx)]
        self.assertNotIn("active", self_tag)


class AccessibilityStateTests(_BaseTestCase):
    def test_current_project_gets_aria_current_true(self):
        doc = self._ingest("Nipigon Ramp", "rfp.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        lists_html = self._lists_html(body)
        idx = lists_html.index('data-ui-ref="lists.project.self"')
        tag = lists_html[lists_html.rindex("<a", 0, idx):lists_html.index(">", idx)]
        self.assertIn('aria-current="true"', tag)

    def test_selected_child_gets_aria_current_page_not_true(self):
        # CLAUDE-GO-DNA-01 (Panel Zoning): "Chats" is gone from Lists -
        # exercised here against ?view=files instead.
        doc = self._ingest("Nipigon Ramp", "rfp.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?view=files").get_data(as_text=True)
        lists_html = self._lists_html(body)
        idx = lists_html.index('data-ui-ref="lists.project.files"')
        tag = lists_html[lists_html.rindex("<a", 0, idx):lists_html.index(">", idx)]
        self.assertIn('aria-current="page"', tag)

    def test_only_one_element_carries_aria_current_page(self):
        # CLAUDE-GO-DNA-01 (Panel Zoning): ?view=overview no longer
        # activates a Lists leaf (Overview was retired from Lists) -
        # exercised here against ?view=files instead.
        doc = self._ingest("Nipigon Ramp", "rfp.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?view=files").get_data(as_text=True)
        lists_html = self._lists_html(body)
        self.assertEqual(lists_html.count('aria-current="page"'), 1)
        self.assertEqual(lists_html.count('aria-current="true"'), 1)

    def test_projects_root_renders_with_exactly_one_unambiguous_current_project(self):
        # CLAUDE-LEFT-RAIL-01: supersedes CLAUDE-P40-VW7B's own Section 3
        # assertion (immediately above, in this test's own prior form)
        # that the PROJECTS root was absent while a Project was open -
        # see test_projects_root_always_renders_as_a_live_project_switcher
        # above for why it is now unconditional. What that older test's
        # own concern actually protected - no ambiguity about WHICH
        # Project is current - still holds under the new structure: the
        # root itself uses aria-expanded, never aria-current; every OTHER
        # accessible Project renders as a plain lists.projects.leaf link
        # with no aria-current at all; only the current Project's own
        # self-link (lists.project.self) carries aria-current="true" -
        # exactly one, never zero, never two.
        doc = self._ingest("Nipigon Ramp", "rfp.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        lists_html = self._lists_html(body)
        self.assertIn('data-ui-ref="lists.projects"', lists_html)
        self.assertEqual(lists_html.count('aria-current="true"'), 1)


# CLAUDE-P40-VW7B: SiblingSeparationTests (two tests) retired outright,
# not just updated - the mechanism it tested (a whitespace-only class
# marking whichever sibling Project row rendered immediately after the
# current Project's own closed child group) no longer has anything to
# apply to: the current Project's own branch never renders inside the
# nav_recent_projects loop anymore (Section 3's own removal of the
# portfolio from the opened-Project Lists panel), so there is no longer
# a "sibling immediately after it" to distinguish. See main.css's own
# comment where .tree-node.sibling-project-after-current used to be
# defined for the CSS half of this same retirement.


class CssTierTreatmentTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def _rule_body(self, selector: str) -> str:
        idx = self.css.index(selector)
        start = self.css.index("{", idx)
        end = self.css.index("}", start)
        return self.css[start:end]

    def test_launcher_heading_active_no_longer_fills_background(self):
        idx = self.css.index(".launcher-heading:hover")
        line_end = self.css.index("\n", idx)
        line = self.css[idx:line_end]
        self.assertNotIn(".launcher-heading.active", line)
        self.assertIn(".launcher-heading:focus-visible", line)

    def test_launcher_link_active_uses_a_translucent_wash_not_a_solid_fill(self):
        # CLAUDE-LEFTPANEL-DENSITY-04 (Product Owner refinement, "reduce
        # the opacity/intensity of the current filled highlight... a
        # restrained tint... rather than a large solid block"): the flat
        # 100%-opaque --surface-selected fill from CLAUDE-P40-VW7A-QA is
        # superseded here, not merely tweaked - a real, deliberate
        # visual-strength reduction, not a token rename.
        body = self._rule_body(".launcher-link.active {")
        self.assertIn("color-mix(in srgb, var(--surface-selected)", body)
        self.assertNotIn("background: var(--surface-selected)", body)

    def test_launcher_link_active_edge_accent_distinguishes_it_from_current_project(self):
        # Both .active and .current-project now use a left-edge accent
        # instead of (or alongside) a fill, so "hover, active, and
        # selected states remain distinguishable" needs its own explicit
        # check: different color token, and .active keeps a translucent
        # fill that .current-project deliberately has none of.
        active_body = self._rule_body(".launcher-link.active {")
        self.assertIn("border-left: 2px solid var(--machine-blue)", active_body)
        self.assertNotIn("var(--border-strong)", active_body)

    def test_current_project_uses_edge_marker_not_full_fill(self):
        body = self._rule_body(".launcher-link.current-project {")
        self.assertIn("border-left", body)
        self.assertNotIn("--surface-selected", body)
        self.assertNotIn("background:", body)

    def test_current_project_marker_uses_a_quiet_not_vivid_accent(self):
        body = self._rule_body(".launcher-link.current-project {")
        self.assertIn("var(--border-strong)", body)
        self.assertNotIn("var(--machine-blue)", body)

    def test_tree_children_has_a_restrained_guide_line(self):
        body = self._rule_body(".tree-children {\n    padding-left")
        self.assertIn("border-left: 1px solid var(--border)", body)

    # CLAUDE-P40-VW7B: test_sibling_separation_is_whitespace_only_no_border
    # retired along with .tree-node.sibling-project-after-current itself -
    # see SelectionTierSeparationTests' own retirement comment above.

    def test_no_gradients_glow_or_backdrop_filter_introduced(self):
        for selector in (
            ".launcher-heading {", ".launcher-link.current-project {",
            ".tree-children {\n    padding-left",
        ):
            body = self._rule_body(selector)
            self.assertNotIn("gradient", body)
            self.assertNotIn("box-shadow", body)
            self.assertNotIn("backdrop-filter", body)
            self.assertNotIn("filter:", body)


class PanelHideRevealPinUntouchedTests(unittest.TestCase):
    """Section 5's own explicit requirement - none of this correction's
    changes may alter the existing hide/pin mechanism (the hover-REVEAL
    half of it was later removed outright by CLAUDE-LEFTPANEL-CALM-01 -
    see PanelCalmNoHoverExpansionTests below for its own dedicated
    coverage; this class now only guards what's still there)."""

    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_launcher_hidden_mechanism_intact(self):
        self.assertIn("html.launcher-hidden .launcher-panel { display: none; }", self.css)

    def test_pin_via_click_js_intact(self):
        self.assertIn("function isDescendantActive(node)", self.html)
        self.assertIn("toggle.addEventListener('click', function () {", self.html)

    def test_projects_root_still_opts_out_of_active_descendant_clearing(self):
        self.assertIn("data-tree-no-clear", self.html)
        idx = self.html.index("data-ui-ref=\"lists.projects\"")
        tag = self.html[self.html.rindex("<button", 0, idx):self.html.index(">", idx)]
        self.assertIn("data-tree-no-clear", tag)

    def test_is_descendant_active_still_finds_a_selected_child_leaf(self):
        # The comment explaining WHY data-tree-no-clear is needed was
        # updated for accuracy (the current-Project row itself no longer
        # carries .active) - the underlying selector this function reads
        # (.tree-leaf.active) is unchanged, still present on whichever
        # child leaf is genuinely selected.
        self.assertIn("node.querySelector('.tree-leaf.active')", self.html)


class UiReferenceRetentionTests(unittest.TestCase):
    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.map_text = (_REPO_ROOT / "UI_REFERENCE_MAP.md").read_text(encoding="utf-8")

    def test_all_existing_lists_project_refs_retained(self):
        # CLAUDE-GO-DNA-01 (Panel Zoning) relocated Investigations/RFIs/
        # Chats (and Overview, retired outright as redundant with
        # lists.project.self) out of Lists into the Toolbox - genuinely
        # no longer present here by design, not a regression. This test
        # now only asserts the refs that are still genuinely Lists' own
        # (file-territory); the structural guard for the full zoning
        # invariant (nothing outside file-territory ever reappears in
        # Lists) lives in
        # tests/test_p40vw7a_ui_reference_map.py::PanelZoningInvariantTests.
        for ref in (
            "lists.projects", "lists.projects.leaf", "lists.project.self",
            "lists.project.documents", "lists.project.documents.leaf",
        ):
            self.assertIn(f'data-ui-ref="{ref}"', self.html, ref)
        for retired_ref in (
            "lists.project.overview", "lists.project.investigations",
            "lists.project.investigations.leaf", "lists.project.rfis",
            "lists.project.rfis.leaf", "lists.project.chats",
        ):
            self.assertNotIn(f'data-ui-ref="{retired_ref}"', self.html, retired_ref)

    def test_no_refs_renumbered_for_styling_reasons(self):
        # The styling/indentation/class changes this stage made must not
        # have produced a NEW numbered variant of an existing ref
        # (e.g. lists.project.self2) - same identifiers as before.
        self.assertNotIn("lists.project.self2", self.html)
        self.assertNotIn("lists.projects.root", self.html)


if __name__ == "__main__":
    unittest.main()
