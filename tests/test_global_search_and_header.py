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
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn('side-rail-brand-label">Archiosk<', body)

    def test_search_toggle_and_nav_toggle_both_present(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn('id="search-toggle"', body)
        self.assertIn('id="nav-toggle"', body)

    def test_search_overlay_markup_present_and_hidden_by_default(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn('id="search-overlay"', body)
        self.assertIn('id="search-input"', body)
        self.assertIn('id="search-close"', body)
        # The overlay ships hidden - it must not be visible on page load.
        self.assertIn('id="search-overlay" hidden', body)

    def test_sidebar_toggle_reveal_uses_animatable_properties_not_display_none(self):
        # Regression guard for the earlier single-click shake fix: the
        # label/context reveal must stay on max-width/max-height/opacity,
        # never regress back to display:none<->block/inline (which
        # cannot be transitioned and caused the original bug).
        css_path = Path("static/css/main.css")
        css = css_path.read_text(encoding="utf-8")
        self.assertIn(".side-rail-label {", css)
        self.assertIn("max-width: 0;", css)
        self.assertNotIn(".side-rail-label { display: none; }", css)
        self.assertNotIn(".side-rail-context { display: none;", css)


if __name__ == "__main__":
    unittest.main()
