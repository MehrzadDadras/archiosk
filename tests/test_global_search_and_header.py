"""
UI design-development pass: sidebar header recompose, brand
simplification, and global search overlay.

Lightweight route/template coverage only -- no domain, governance, or
persistence behavior changed. The sidebar-toggle stability fix itself
(display:none -> animatable max-width/max-height reveal) already has its
own coverage from the earlier bug-fix tranche; this file covers the
NEW surface added in this pass: the /search endpoint's real (Projects-
only) scope, and that "B-Hive"/"BEEHIVE" no longer appears in visible
UI text anywhere.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.requirements_registry import RequirementsRegistry


class GlobalSearchTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_global_search_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        registry = RequirementsRegistry(self.tmp_dir)
        registry.save(ParsedDocument(
            project_id="alpha-rfp", filename="Alpha_Recreation_Centre.pdf",
            ingested_at="2026-01-01T00:00:00+00:00",
        ))
        registry.save(ParsedDocument(
            project_id="beta-rfp", filename="Beta_Community_Library.pdf",
            ingested_at="2026-02-01T00:00:00+00:00",
        ))

        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "tester"
            sess["role"] = "admin"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_search_requires_authentication(self):
        anon = self.flask_app.test_client()
        response = anon.get("/search?q=alpha")
        # login_required redirects an anonymous request rather than
        # returning search results.
        self.assertNotEqual(response.status_code, 200)

    def test_search_matches_by_filename(self):
        response = self.client.get("/search?q=recreation")
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["kind"], "Project")
        self.assertEqual(data["results"][0]["title"], "Alpha_Recreation_Centre.pdf")
        self.assertEqual(data["results"][0]["subtitle"], "alpha-rfp")
        self.assertIn("/projects/alpha-rfp/workspace", data["results"][0]["url"])

    def test_search_matches_by_project_id(self):
        response = self.client.get("/search?q=beta-rfp")
        data = response.get_json()
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["title"], "Beta_Community_Library.pdf")

    def test_search_no_match_returns_empty_list_not_error(self):
        response = self.client.get("/search?q=nonexistent-project-xyz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"results": []})

    def test_search_empty_query_returns_empty_list(self):
        response = self.client.get("/search")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"results": []})

    def test_search_result_shape_is_generic_kind_title_subtitle_url(self):
        response = self.client.get("/search?q=alpha")
        result = response.get_json()["results"][0]
        self.assertEqual(set(result.keys()), {"kind", "title", "subtitle", "url"})


class HeaderAndBrandTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_header_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "tester"
            sess["role"] = "admin"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_no_visible_bhive_text_on_home(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("B-Hive", body)
        self.assertNotIn("BEEHIVE", body)
        self.assertNotIn("Beehive", body)

    def test_no_visible_bhive_text_on_login(self):
        body = self.client.get("/login").get_data(as_text=True)
        self.assertNotIn("B-Hive", body)
        self.assertNotIn("BEEHIVE", body)
        self.assertNotIn("Beehive", body)

    def test_no_visible_bhive_text_on_gateway(self):
        body = self.client.get("/gateway").get_data(as_text=True)
        self.assertNotIn("B-Hive", body)
        self.assertNotIn("BEEHIVE", body)
        self.assertNotIn("Beehive", body)

    def test_brand_lockup_reads_archiosk_only(self):
        # CLAUDE-P40-E2B1: the brand mark moved from the old side-rail
        # (.side-rail-brand-label) to the application-wide top bar
        # (.workspace-topbar-brand, base.html) - see that template's own
        # note on why identity now lives there instead of the launcher
        # panel.
        # CLAUDE-P40-VW7A added a data-ui-ref="menu.brand" attribute to this
        # same element (UI_REFERENCE_MAP.md) - selector updated to allow
        # attributes between the class and href, not asserting their
        # absence (this test's own subject is the visible text, not the
        # exact attribute ordering).
        # CLAUDE-P40-BRAND1 added a decorative archiosk_mark() SVG icon
        # directly before the wordmark, inside the same link (see that
        # template's own comment on why it's one shared tab-stop, not
        # two) - the wordmark text itself now lives in its own
        # .workspace-topbar-brand-text span, and the SVG spans multiple
        # lines, so a plain-substring check (not a single-line regex) is
        # used to pin down that the VISIBLE TEXT reads "Archiosk" only,
        # nothing appended after it - this test's own actual subject,
        # unchanged by the icon.
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn('workspace-topbar-brand"', body)
        idx = body.index('workspace-topbar-brand"')
        tag_close = body.index(">", idx)
        self.assertIn('href="/"', body[idx:tag_close])
        element_close = body.index("</a>", tag_close)
        self.assertTrue(
            body[tag_close + 1:element_close].endswith(
                '<span class="workspace-topbar-brand-text">Archiosk</span>'
            )
        )

    def test_search_toggle_and_nav_toggle_are_gone(self):
        # CLAUDE-P40-E2B1, Section F: "Remove superseded Home, search,
        # Open Project and old side-rail hamburger controls" - the old
        # side-rail's search magnifier and expand/collapse hamburger are
        # both retired outright, not merely hidden, now that the single
        # launcher panel replaces the side-rail they lived in.
        body = self.client.get("/").get_data(as_text=True)
        self.assertNotIn('id="search-toggle"', body)
        self.assertNotIn('id="nav-toggle"', body)

    def test_search_overlay_markup_is_gone(self):
        # Superseded along with the search-toggle control that was its
        # only entry point (Section F) - the markup is removed outright,
        # not left as inert hidden chrome (Section E's "no hidden
        # duplicate markup" principle, applied by extension).
        body = self.client.get("/").get_data(as_text=True)
        self.assertNotIn('id="search-overlay"', body)
        self.assertNotIn('id="search-input"', body)
        self.assertNotIn('id="search-close"', body)

    def test_launcher_panel_toggle_hides_in_full_not_via_partial_reveal(self):
        # CLAUDE-P40-E2B1: the old icon-only/labeled width-toggle rail
        # (.side-rail-label's animatable max-width/opacity reveal) is
        # retired along with the side-rail itself - the one launcher
        # panel now hides/shows in full via a plain class toggle
        # (html.launcher-hidden), the same idiom the Workspace's own
        # Toolbox toggle already established.
        css_path = Path("static/css/main.css")
        css = css_path.read_text(encoding="utf-8")
        self.assertIn("html.launcher-hidden .launcher-panel { display: none; }", css)
        self.assertNotIn(".side-rail-label {", css)


class ProjectsTreeTests(unittest.TestCase):
    """
    CLAUDE-P40-E2B1: the old side-rail's expand/collapse-only "Projects"
    tree node is retired along with the side-rail itself - the one
    launcher panel's "Projects" heading is now a real, navigating link
    into the authorized Project directory (portal.projects_list), with
    Project names only listed beneath it (Section B/C). The old separate
    "Current Project" / "Recent Projects" sidebar blocks and the RFQ/RFP
    explanatory paragraph remain gone.
    """

    def setUp(self):
        import app as app_module
        from services.bhive_parser import ParsedDocument
        from services.requirements_registry import RequirementsRegistry

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_tree_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        registry = RequirementsRegistry(self.tmp_dir)
        registry.save(ParsedDocument(project_id="alpha", filename="Alpha.pdf", ingested_at="2026-01-01T00:00:00+00:00"))
        registry.save(ParsedDocument(project_id="beta", filename="Beta.pdf", ingested_at="2026-02-01T00:00:00+00:00"))

        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "tester"
            sess["role"] = "admin"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_projects_heading_is_a_real_link_to_the_projects_directory(self):
        # SUPERSEDED (CLAUDE-P40-E3A, Section 2/4): "Projects" is now the
        # recursive tree's own root PARENT (a <button>, expand/collapse
        # toggle - the same pattern every other parent in the hierarchy,
        # e.g. "Documents"/"Investigations", already uses), not a
        # navigating <a>. The authorized Project directory itself remains
        # genuinely reachable elsewhere (index.html's own "Open Project"
        # hero, case_workspace.html's Project Home "<- Projects" link,
        # etc.) - just no longer duplicated as a second navigation
        # affordance on the Lists heading itself.
        body = self.client.get("/").get_data(as_text=True)
        import re
        match = re.search(r'<button type="button" class="tree-toggle launcher-heading[^"]*"[^>]*>\s*<span class="tree-label">Projects</span>', body)
        self.assertIsNotNone(match)
        self.assertIn('href="/projects"', body)

    def test_individual_projects_are_real_links_into_their_workspace(self):
        # CLAUDE-P40-E2B1A: Project names are the Projects root
        # launcher's own projected children - they live on /projects
        # (Display's level-1 projection target), never listed inline in
        # the launcher panel itself on every page.
        body = self.client.get("/projects").get_data(as_text=True)
        self.assertIn('href="/projects/alpha/workspace"', body)
        self.assertIn('href="/projects/beta/workspace"', body)
        self.assertIn("Alpha.pdf", body)
        self.assertIn("Beta.pdf", body)

    def test_projects_root_launcher_stays_highlighted_inside_an_open_workspace(self):
        # CLAUDE-P40-E2B1A: no per-project row exists in the panel to
        # highlight anymore (Rule 5 - no duplicated child hierarchy) -
        # the "Projects" root launcher itself stays active for as long
        # as any Project/Workspace subtree is open, and the in-Display
        # branch-nav's own "Overview" entry is the level-2 highlight.
        # SUPERSEDED (CLAUDE-P40-E3A): "Overview" is the level-2 highlight
        # now (the retired .display-branch-nav's own "Overview" entry no
        # longer exists) - checked against the active Project's own
        # expanded Lists branch instead.
        # SUPERSEDED AGAIN (CLAUDE-P40-VW7B, Section 3): the "Projects"
        # root launcher (.launcher-heading) no longer renders at all
        # while a Project is open (removed from the opened-Project
        # Lists entirely) - there is nothing left to "stay highlighted."
        # The Foreground Project's own branch is what now communicates
        # "which Project is current" - its own current-project marker
        # class + aria-current="true" (see .current-project's own CSS
        # comment for the restrained edge-marker treatment it gets
        # instead of a background fill).
        body = self.client.get("/projects/alpha/workspace").get_data(as_text=True)
        self.assertNotIn("launcher-heading", body)
        self.assertIn('tree-leaf launcher-link current-project" data-ui-ref="lists.project.self" aria-current="true"', body)
        self.assertNotIn("launcher-project-item", body)
        # The old standalone "Current Project" orientation block is gone.
        self.assertNotIn('side-rail-context-label">Current Project<', body)

    def test_recent_projects_block_removed_from_sidebar(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("side-rail-context", body)
        self.assertNotIn("side-rail-recent", body)

    def test_new_project_appears_exactly_once_in_launcher_panel(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertEqual(body.count(">+ New Project<"), 1)

    def test_projects_directory_header_no_longer_has_its_own_new_project_button(self):
        body = self.client.get("/projects").get_data(as_text=True)
        self.assertNotIn('<a class="btn btn-primary" href="/upload">New Project</a>', body)

    def test_rfq_explanatory_paragraph_removed_from_case_workspace(self):
        body = self.client.get("/projects/alpha/workspace").get_data(as_text=True)
        self.assertNotIn("This Project began as an RFQ/RFP ingestion", body)


class TypographyCorrectionTests(unittest.TestCase):
    """
    Typography correction pass: the Archiosk wordmark is restored to its
    pre-Arial-Nova appearance (the deliberate exception), every other
    visible UI text uses one family (Arial Nova Cond / Arial Narrow /
    Arial), and IBM Plex Mono is pulled back to only the two genuinely
    fixed-column-technical spots left in the whole stylesheet.
    """

    def setUp(self):
        self.css = Path("static/css/main.css").read_text(encoding="utf-8")

    def test_wordmark_restored_to_original_family_and_weight(self):
        self.assertIn('font-family: "Space Grotesk", sans-serif;', self.css)
        # The rule immediately following the family declaration must be
        # the original bold weight, not the Arial Nova era's 400.
        idx = self.css.index('font-family: "Space Grotesk", sans-serif;')
        following = self.css[idx:idx + 200]
        self.assertIn("font-weight: 700;", following)
        self.assertIn("font-size: 1.1rem;", following)

    def test_wordmark_is_the_only_space_grotesk_usage(self):
        # The wordmark is an explicit, isolated exception - Space Grotesk
        # must not leak into any other rule.
        self.assertEqual(self.css.count("Space Grotesk"), 1)

    def test_font_mono_reduced_to_exactly_the_three_technical_exceptions(self):
        # CLAUDE-P40-VW7A added a third: the UI Reference Mode badge
        # (.ui-reference-mode-active [data-ui-ref]::after) renders a
        # dot-path identifier string - exactly the "technical register"
        # tokens.css's own header reserves --font-mono for (paths, ids,
        # logs), the same category .finding-provenance and
        # .region-status already were. Not a leak into ordinary UI text.
        self.assertEqual(self.css.count("font-family: var(--font-mono);"), 3)
        self.assertIn(".region-status { font-family: var(--font-mono); }", self.css)
        self.assertIn(".ui-reference-mode-active [data-ui-ref]::after {", self.css)

    def test_common_ui_elements_no_longer_reference_font_mono(self):
        # Spot-check a representative sample of exactly the element types
        # named in the correction: buttons, inputs, badges, navigation,
        # labels, footer, table headers.
        no_longer_mono = [
            ".btn {", ".text-input {", ".workspace-form button {",
            # CLAUDE-P40-E2B1: .side-rail-link is retired along with the
            # side-rail itself - .launcher-link is its successor.
            ".launcher-link {", ".workspace-pane-label {",
            ".review-btn {", ".review-decision-badge {", ".applied-badge {",
            ".registry-table th {", ".eyebrow {",
            ".project-card-meta {",
        ]
        for selector in no_longer_mono:
            start = self.css.index(selector)
            end = self.css.index("}", start)
            rule_body = self.css[start:end]
            self.assertNotIn("var(--font-mono)", rule_body, msg=f"{selector} still uses font-mono")

    def test_form_controls_have_a_global_font_inherit_backstop(self):
        self.assertIn("button, input, select, textarea {", self.css)
        idx = self.css.index("button, input, select, textarea {")
        rule_body = self.css[idx:self.css.index("}", idx)]
        self.assertIn("font-family: inherit;", rule_body)

    def test_no_font_size_below_11px_floor(self):
        import re
        sizes_rem = [float(m) for m in re.findall(r"font-size:\s*([0-9.]+)rem", self.css)]
        sizes_px = [float(m) for m in re.findall(r"font-size:\s*([0-9.]+)px", self.css)]
        self.assertTrue(sizes_rem, "expected to find rem-based font-size declarations")
        for value in sizes_rem:
            self.assertGreaterEqual(value * 16, 11, f"{value}rem is below the 11px floor")
        for value in sizes_px:
            self.assertGreaterEqual(value, 11, f"{value}px is below the 11px floor")


if __name__ == "__main__":
    unittest.main()
