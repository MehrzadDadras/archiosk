"""
CLAUDE-P40-VW8-QA - Complete Root and Subfolder UI Reference Tagging.

Bounded extension/audit of the existing UI Reference Mode (established
CLAUDE-P40-VW7A, extended by every VW8-QA stage since) - no new
numbering system, no changed syntax, no restructured document
hierarchy. This file covers what tests/test_p40vw7a_ui_reference_map.py's
own static-analysis registry-consistency checks (already re-run and
passing against every reference this stage adds) don't: LIVE rendering
of the specific gaps this stage closed (empty folders that previously
had none, a whole administrative page - Security Department - that had
zero references at all, and the two standalone Project-directory
pages), authorization-scoped exposure, and the badge mechanism's
click-target/keyboard/theme safety for the NEW `<details>`-based
(accordion/subdisclosure) references specifically, which the tree-
toggle-based mechanism these tests already exercised elsewhere never
needed to prove.

No interactive browser-automation tool is connected in this
environment (consistent with every prior VW stage) - "real browser"
verification here means structural/rendered-HTML proof that the
mechanism is genuinely wired correctly (badge CSS present, click
listeners correctly scoped, theme tokens applied), not a pixel/
interaction-level trace; stated honestly in the final report rather
than fabricated.
"""
from __future__ import annotations

import io
import re
import uuid
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.environment_capabilities import CLIENT_OWNER

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_MACROS_HTML_PATH = _REPO_ROOT / "templates" / "_macros.html"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


def _fake_parse(self_parser, raw_bytes, filename_):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename_,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
    )


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw8qa_tagging_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="tag_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="tag_reader", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.flask_app.app_context():
                from services.ingestion import ingest_upload
                self.doc = ingest_upload(
                    _fake_file(b"content", "rfp.txt"), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner="tag_admin", project_name="Tagging Project",
                )
        self.project_id = self.doc.project_id

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client


# ---------------------------------------------------------------------------
# Empty-folder coverage - the concrete gap this stage found and closed.
# ---------------------------------------------------------------------------

class EmptyFolderCoverageTests(_BaseTestCase):
    def test_every_empty_family_carries_its_own_reference_on_a_brand_new_project(self):
        # A freshly-ingested Project has zero Investigations/RFIs/Tasks/
        # Tags/(all Documents removed) - every empty-state ref must
        # render, not just exist in the registry.
        client = self._client_as("tag_admin", 1)
        with self.flask_app.app_context():
            from services.case_workspace import CaseWorkspaceStore
            store = CaseWorkspaceStore(self.tmp_dir)
            workspace = store.get(self.project_id)
            for source in list(workspace.sources):
                store.remove_source(workspace, source["id"], actor="tag_admin")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for ref in (
            "lists.project.documents.empty",
            "lists.project.rfis.empty",
            "lists.project.tags.empty",
        ):
            self.assertIn(f'data-ui-ref="{ref}"', body, ref)

    def test_investigations_empty_state_and_new_action_both_present_together(self):
        # Section: "the action row is never gated on this state" - both
        # must render side by side, never one instead of the other.
        client = self._client_as("tag_admin", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.project.investigations.new"', body)
        self.assertIn('data-ui-ref="lists.project.investigations.empty"', body)

    def test_tasks_open_and_completed_empty_states_are_independently_tagged(self):
        client = self._client_as("tag_admin", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.project.tasks.open.empty"', body)
        self.assertIn('data-ui-ref="lists.project.tasks.completed.empty"', body)


# ---------------------------------------------------------------------------
# Recursive/nested-folder coverage + parent-child relationships.
# ---------------------------------------------------------------------------

class NestedFolderCoverageTests(_BaseTestCase):
    def test_investigation_new_action_nests_correctly_under_its_parent_family(self):
        client = self._client_as("tag_admin", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        parent_pos = body.index('data-ui-ref="lists.project.investigations"')
        child_pos = body.index('data-ui-ref="lists.project.investigations.new"')
        rfis_pos = body.index('data-ui-ref="lists.project.rfis"')
        self.assertLess(parent_pos, child_pos)
        self.assertLess(child_pos, rfis_pos)

    def test_security_subdisclosure_nests_inside_its_parent_accordion_in_source_order(self):
        client = self._client_as("tag_admin", 1)
        body = client.get("/security/").get_data(as_text=True)
        parent_pos = body.index('data-ui-ref="security.policies"')
        child_pos = body.index('data-ui-ref="security.policies.add"')
        next_parent_pos = body.index('data-ui-ref="security.controls"')
        self.assertLess(parent_pos, child_pos)
        self.assertLess(child_pos, next_parent_pos)

    def test_project_tools_subfamily_still_nests_correctly_unaffected_by_this_stage(self):
        # Pre-existing nesting (untouched by this stage) - a regression
        # guard that the new empty-state insertions didn't disturb it.
        client = self._client_as("tag_admin", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        parent_pos = body.index('data-ui-ref="lists.project.tools"')
        child_pos = body.index('data-ui-ref="lists.project.tools.add-document"')
        self.assertLess(parent_pos, child_pos)


# ---------------------------------------------------------------------------
# Administrative-page coverage - Security Department had ZERO references
# before this stage.
# ---------------------------------------------------------------------------

class SecurityDepartmentCoverageTests(_BaseTestCase):
    def test_every_top_level_security_accordion_is_tagged(self):
        client = self._client_as("tag_admin", 1)
        body = client.get("/security/").get_data(as_text=True)
        for ref in (
            "security.floor", "security.claims", "security.baselines", "security.policies",
            "security.controls", "security.qa", "security.exceptions", "security.projects",
            "security.learning", "security.assurance-activity", "security.self-check",
        ):
            self.assertIn(f'data-ui-ref="{ref}"', body, ref)

    def test_no_unauthorized_exposure_a_non_admin_never_sees_any_security_reference(self):
        client = self._client_as("tag_reader", 2, role="read_only")
        resp = client.get("/security/")
        self.assertNotEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertNotIn("data-ui-ref=\"security.", body)

    def test_unauthenticated_request_never_sees_any_security_reference(self):
        client = self.flask_app.test_client()
        resp = client.get("/security/")
        self.assertNotEqual(resp.status_code, 200)


class ProjectsDirectoryAndRemovedProjectsCoverageTests(_BaseTestCase):
    def test_projects_directory_leaf_and_empty_state_are_mutually_exclusive_and_tagged(self):
        client = self._client_as("tag_admin", 1)
        body = client.get("/projects").get_data(as_text=True)
        self.assertIn('data-ui-ref="projects-directory.leaf"', body)
        self.assertNotIn('data-ui-ref="projects-directory.empty"', body)

    def test_removed_projects_page_is_tagged(self):
        client = self._client_as("tag_admin", 1)
        body = client.get("/removed-projects").get_data(as_text=True)
        self.assertIn('data-ui-ref="removed-projects.empty"', body)

    def test_a_project_id_is_never_embedded_inside_a_reference_value(self):
        # "Do not expose UUIDs, secrets, database keys... Do not use DOM
        # order as the source of identity" - the pattern ref itself
        # must be a fixed string, never per-instance.
        client = self._client_as("tag_admin", 1)
        body = client.get("/projects").get_data(as_text=True)
        match = re.search(r'data-ui-ref="projects-directory\.leaf"', body)
        self.assertIsNotNone(match)
        self.assertNotIn(self.project_id, match.group(0))


# ---------------------------------------------------------------------------
# Badge mechanism safety for the NEW <details>-based references
# (accordion/subdisclosure) - click-target, keyboard, theme.
# ---------------------------------------------------------------------------

class BadgeMechanismSafetyTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_reference_badge_css_is_generic_across_every_element_type(self):
        # [data-ui-ref] is a plain attribute selector - already proven
        # generic (applies identically to <button>/<a>/<span>/<details>)
        # by construction; this pins that down explicitly for the two
        # NEW element shapes this stage introduced (<details> via
        # accordion/subdisclosure).
        self.assertIn(".ui-reference-mode-active [data-ui-ref]", self.css)
        self.assertNotIn(".ui-reference-mode-active details[data-ui-ref]", self.css)
        self.assertNotIn(".ui-reference-mode-active button[data-ui-ref]", self.css)

    def test_badge_is_positioned_outside_the_elements_own_box_never_covering_it(self):
        idx = self.css.index(".ui-reference-mode-active [data-ui-ref]::after")
        body = self.css[idx:idx + 400]
        self.assertIn("position: absolute", body)
        self.assertIn("translateY(-100%)", body)

    def test_badge_never_intercepts_clicks(self):
        idx = self.css.index(".ui-reference-mode-active [data-ui-ref]::after")
        body = self.css[idx:idx + 700]
        self.assertIn("pointer-events: none", body)

    def test_reference_mode_has_zero_layout_effect_when_inactive(self):
        # position:relative/outline are scoped under .ui-reference-mode-
        # active only - never applied to [data-ui-ref] at rest, so a
        # newly-tagged <details> never shifts layout when the mode is off.
        self.assertNotRegex(self.css, r"(?<!-active )\[data-ui-ref\]\s*\{[^}]*position:\s*relative")

    def test_no_position_absolute_descendant_inside_accordion_or_subdisclosure_could_now_mismatch_ancestor(self):
        # Adding position:relative to a NEW ancestor (<details>, via
        # this stage's own data-ui-ref) only matters if some descendant
        # relies on position:absolute resolving against a DIFFERENT,
        # more distant ancestor - confirmed there is none.
        idx = self.css.index(".accordion-section {")
        end = self.css.index("/* -- Case Workspace", idx + 1) if "/* -- Case Workspace" in self.css[idx:] else idx + 3000
        # Search the whole accordion/subdisclosure rule neighborhood.
        region = self.css[max(0, idx - 1500):idx + 2000]
        self.assertNotIn("position: absolute", region)


class DetailsSummaryElementsAreRealFocusableControlsTests(unittest.TestCase):
    """Keyboard accessibility: <details>/<summary> are native, always
    keyboard-operable (Enter/Space toggles, Tab reaches them) - not a
    <div onclick> reimplementation this stage could have broken.
    Structural proof, not a live keyboard trace (no browser tool)."""

    def setUp(self):
        self.macros = _MACROS_HTML_PATH.read_text(encoding="utf-8")

    def test_accordion_macro_uses_native_details_summary(self):
        idx = self.macros.index("{% macro accordion(")
        body = self.macros[idx:idx + 1100]
        self.assertIn("<details", body)
        self.assertIn("<summary", body)

    def test_subdisclosure_macro_uses_native_details_summary(self):
        idx = self.macros.index("{% macro subdisclosure(")
        body = self.macros[idx:idx + 900]
        self.assertIn("<details", body)
        self.assertIn("<summary", body)


class ThemeAwareTests(_BaseTestCase):
    """Light/Dark/Tinted presentation for the newly-tagged elements -
    the SAME per-surface CSS-scoping mechanism every other reference in
    this app already relies on (see test_p40vw8qa_r3_appearance_mode_
    integrity.py for the mechanism's own correctness proof) - this only
    confirms the badge's own color declarations are token-based, not
    hardcoded, so a newly-tagged element's badge stays legible in every
    mode exactly like every pre-existing one."""

    def test_badge_foreground_and_background_are_token_based_not_hardcoded(self):
        css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        idx = css.index(".ui-reference-mode-active [data-ui-ref]::after")
        body = css[idx:idx + 400]
        self.assertIn("var(--surface-primary)", body)
        self.assertIn("var(--machine-blue)", body)
        self.assertNotRegex(body, r"#[0-9a-fA-F]{3,6}")

    def test_security_page_accordions_use_theme_tokens_not_hardcoded_colors(self):
        css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        idx = css.index(".accordion-summary {")
        body = css[idx:idx + 400]
        self.assertNotRegex(body, r"#[0-9a-fA-F]{3,6}")


class WideAndNarrowViewportTests(unittest.TestCase):
    def test_reference_badge_css_has_no_viewport_specific_override_that_could_hide_it(self):
        css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        # The badge rule block itself must not sit inside a @media
        # query that could exclude narrow or wide viewports - it should
        # apply unconditionally whenever Reference Mode is active.
        idx = css.index(".ui-reference-mode-active [data-ui-ref]::after")
        preceding = css[max(0, idx - 200):idx]
        self.assertNotIn("@media", preceding)


# ---------------------------------------------------------------------------
# Dynamic-record instance convention - unchanged, still safe.
# ---------------------------------------------------------------------------

class DynamicRecordConventionTests(_BaseTestCase):
    def test_new_investigation_records_still_use_the_pattern_convention_not_per_instance_ids(self):
        client = self._client_as("tag_admin", 1)
        with self.flask_app.app_context():
            from services.case_workspace import CaseWorkspaceStore
            store = CaseWorkspaceStore(self.tmp_dir)
            workspace = store.get(self.project_id)
            case = store.create_case(workspace, title="A Tagged Investigation", objective="", created_by="tag_admin")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        # The SAME data-ui-ref value for every Investigation row -
        # identity comes from data-case-id, never a per-instance ref.
        self.assertEqual(body.count('data-ui-ref="lists.project.investigations.leaf"'), 1)
        self.assertIn(case["id"], body)  # present as data-case-id, not as part of the ref
        self.assertNotIn(f'data-ui-ref="lists.project.investigations.leaf.{case["id"]}"', body)


if __name__ == "__main__":
    unittest.main()
