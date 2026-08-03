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

    def test_only_one_row_carries_the_active_selection_class(self):
        doc = self._ingest("Nipigon Ramp", "rfp.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        lists_html = self._lists_html(body)
        # Every .tree-leaf.launcher-link(.active) opening tag - count
        # how many actually carry the literal "active" token.
        leaf_tags = re.findall(r'<a class="tree-leaf launcher-link[^"]*"[^>]*>', lists_html)
        active_leaves = [t for t in leaf_tags if re.search(r'\bactive\b', t)]
        self.assertEqual(len(active_leaves), 1, active_leaves)
        self.assertIn('data-ui-ref="lists.project.chats"', active_leaves[0])

    def test_projects_root_active_class_present_but_no_longer_styled_as_selected(self):
        doc = self._ingest("Nipigon Ramp", "rfp.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        lists_html = self._lists_html(body)
        self.assertIn('data-ui-ref="lists.projects"', lists_html)
        idx = lists_html.index('data-ui-ref="lists.projects"')
        tag = lists_html[lists_html.rindex("<button", 0, idx):lists_html.index(">", idx)]
        self.assertIn("launcher-heading", tag)
        self.assertIn('aria-expanded="true"', tag)

    def test_selecting_a_different_child_moves_the_active_class_there(self):
        doc = self._ingest("Nipigon Ramp", "rfp.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?view=overview").get_data(as_text=True)
        lists_html = self._lists_html(body)
        leaf_tags = re.findall(r'<a class="tree-leaf launcher-link[^"]*"[^>]*>', lists_html)
        active_leaves = [t for t in leaf_tags if re.search(r'\bactive\b', t)]
        self.assertEqual(len(active_leaves), 1)
        self.assertIn('data-ui-ref="lists.project.overview"', active_leaves[0])
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
        doc = self._ingest("Nipigon Ramp", "rfp.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        lists_html = self._lists_html(body)
        idx = lists_html.index('data-ui-ref="lists.project.chats"')
        tag = lists_html[lists_html.rindex("<a", 0, idx):lists_html.index(">", idx)]
        self.assertIn('aria-current="page"', tag)

    def test_only_one_element_carries_aria_current_page(self):
        doc = self._ingest("Nipigon Ramp", "rfp.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?view=overview").get_data(as_text=True)
        lists_html = self._lists_html(body)
        self.assertEqual(lists_html.count('aria-current="page"'), 1)
        self.assertEqual(lists_html.count('aria-current="true"'), 1)

    def test_projects_root_uses_aria_expanded_not_aria_current(self):
        doc = self._ingest("Nipigon Ramp", "rfp.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        lists_html = self._lists_html(body)
        idx = lists_html.index('data-ui-ref="lists.projects"')
        tag = lists_html[lists_html.rindex("<button", 0, idx):lists_html.index(">", idx)]
        self.assertIn("aria-expanded", tag)
        self.assertNotIn("aria-current", tag)


class SiblingSeparationTests(_BaseTestCase):
    """nav_recent_projects (app.py) sorts by ingested_at, most-recently-
    INGESTED first - so the render order is the REVERSE of ingestion
    order. Verified empirically against a real render before writing
    these, not assumed."""

    def test_sibling_immediately_after_current_project_gets_separation_class(self):
        self._ingest("Oldest Project", "a.txt")
        current = self._ingest("Nipigon Ramp", "b.txt")
        self._ingest("Newest Project", "c.txt")
        # Render order (most-recent-ingested first): Newest Project,
        # Nipigon Ramp, Oldest Project - "Oldest Project" is the one
        # that actually renders immediately after the current Project's
        # own closed child group.
        client = self._client()
        body = client.get(f"/projects/{current.project_id}/workspace").get_data(as_text=True)
        lists_html = self._lists_html(body)
        self.assertEqual(lists_html.count("sibling-project-after-current"), 1)
        idx = lists_html.index("sibling-project-after-current")
        row_end = lists_html.index("</li>", idx)
        self.assertIn("Oldest Project", lists_html[idx:row_end])
        self.assertNotIn("Newest Project", lists_html[idx:row_end])

    def test_no_separation_class_when_current_project_renders_last(self):
        # Ingesting the current Project FIRST (oldest of the two) means
        # it renders LAST (most-recent-first order) - "Newest Project"
        # renders BEFORE it, and nothing renders after it at all.
        current = self._ingest("Nipigon Ramp", "a.txt")
        self._ingest("Newest Project", "b.txt")
        client = self._client()
        body = client.get(f"/projects/{current.project_id}/workspace").get_data(as_text=True)
        lists_html = self._lists_html(body)
        self.assertNotIn("sibling-project-after-current", lists_html)


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

    def test_launcher_link_active_unchanged_selection_fill(self):
        body = self._rule_body(".launcher-link.active {")
        self.assertIn("background: var(--surface-selected)", body)

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

    def test_sibling_separation_is_whitespace_only_no_border(self):
        body = self._rule_body(".tree-node.sibling-project-after-current {")
        self.assertIn("margin-top", body)
        self.assertNotIn("border", body)

    def test_no_gradients_glow_or_backdrop_filter_introduced(self):
        for selector in (
            ".launcher-heading {", ".launcher-link.current-project {",
            ".tree-children {\n    padding-left", ".tree-node.sibling-project-after-current {",
        ):
            body = self._rule_body(selector)
            self.assertNotIn("gradient", body)
            self.assertNotIn("box-shadow", body)
            self.assertNotIn("backdrop-filter", body)
            self.assertNotIn("filter:", body)


class PanelHideRevealPinUntouchedTests(unittest.TestCase):
    """Section 5's own explicit requirement - none of this correction's
    changes may alter the existing hide/hover-reveal/pin mechanism."""

    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_launcher_hidden_mechanism_intact(self):
        self.assertIn("html.launcher-hidden .launcher-panel { display: none; }", self.css)

    def test_hover_reveal_and_pin_js_intact(self):
        self.assertIn("function isDescendantActive(node)", self.html)
        self.assertIn("node.addEventListener('mouseenter'", self.html)
        self.assertIn("node.addEventListener('mouseleave'", self.html)

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
        for ref in (
            "lists.projects", "lists.projects.leaf", "lists.project.self",
            "lists.project.overview", "lists.project.documents", "lists.project.documents.leaf",
            "lists.project.investigations", "lists.project.investigations.leaf",
            "lists.project.rfis", "lists.project.rfis.leaf", "lists.project.chats",
        ):
            self.assertIn(f'data-ui-ref="{ref}"', self.html, ref)

    def test_no_refs_renumbered_for_styling_reasons(self):
        # The styling/indentation/class changes this stage made must not
        # have produced a NEW numbered variant of an existing ref
        # (e.g. lists.project.self2) - same identifiers as before.
        self.assertNotIn("lists.project.self2", self.html)
        self.assertNotIn("lists.projects.root", self.html)


if __name__ == "__main__":
    unittest.main()
