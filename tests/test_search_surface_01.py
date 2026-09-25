"""CLAUDE-SEARCH-SURFACE-01 - the primary nav must not open a JSON document.

UI baseline 2026-09-22, anomaly A-05: the "Search" item in the primary
navigation linked at portal.global_search, the JSON backend, so clicking it
left the shell and rendered `{"results":[]}` with no way back.

These tests hold the fix and the boundary around it: the page is in the shell,
the endpoint is unchanged, and there is still only one search implementation.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from app import create_app
from tests.master_ui_helpers import master_command, read_expanded, expand_partials


class _SignedIn(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="search_surface_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.app = create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "admin"
            session["role"] = "admin"

    def _html(self, path):
        response = self.client.get(path)
        return response, response.get_data(as_text=True)


class TheNavNeverPointsAtTheJsonEndpoint(_SignedIn):
    def test_the_rendered_nav_links_to_the_page_not_to_search(self):
        _, html = self._html("/projects")
        self.assertIn('href="/find"', html)
        # The exact defect: a bare href to the JSON endpoint in the nav.
        self.assertNotIn('href="/search"', html)

    def test_the_search_nav_item_carries_its_reference_id(self):
        # SUPERSEDED DELIBERATELY (MASTERUI cutover): the primary nav's Search
        # (menu.search) -> QUERY > Search, active, on the HTML page (/find), never
        # the JSON endpoint.
        _, html = self._html("/projects")
        state, inner = master_command(html, "query.search")
        self.assertEqual(state, "active")
        self.assertIn('href="/find"', inner)


class TheSearchPageStaysInTheShell(_SignedIn):
    def test_the_page_renders_html_not_json(self):
        response, html = self._html("/find")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        self.assertNotIn('{"results"', html)

    def test_the_page_keeps_the_primary_navigation(self):
        """Acceptance: navigation back to Projects/Review/Compare/Documents."""
        _, html = self._html("/find")
        for destination in ("/projects", "/document-shop/jobs"):
            self.assertIn(f'href="{destination}"', html)

    def test_the_page_offers_a_usable_search_interface(self):
        _, html = self._html("/find")
        self.assertIn('data-ui-ref="search.form"', html)
        self.assertIn('data-ui-ref="search.query"', html)
        self.assertIn('data-ui-ref="search.submit"', html)

    def test_the_query_lives_in_the_url_so_back_and_reload_work(self):
        """A GET form is what makes browser Back ordinary rather than a feature."""
        _, html = self._html("/find")
        self.assertIn('method="get"', html)
        response, echoed = self._html("/find?q=recreation")
        self.assertEqual(response.status_code, 200)
        self.assertIn('value="recreation"', echoed)

    def test_an_empty_query_shows_the_form_without_claiming_no_results(self):
        _, html = self._html("/find")
        self.assertNotIn('data-ui-ref="search.empty"', html)

    def test_a_query_with_no_matches_says_so_inside_the_shell(self):
        _, html = self._html("/find?q=nothing-matches-this-xyz")
        self.assertIn('data-ui-ref="search.empty"', html)
        self.assertIn('href="/projects"', html)

    def test_the_page_states_its_own_coverage(self):
        """A box that searched less than the user assumed would be worse."""
        _, html = self._html("/find")
        self.assertIn('data-ui-ref="search.coverage"', html)

    def test_the_page_requires_authentication(self):
        anon = self.app.test_client()
        self.assertNotEqual(anon.get("/find").status_code, 200)


class TheJsonEndpointIsUnchanged(_SignedIn):
    """Preserve /search as the backend endpoint - nine test files read it."""

    def test_search_still_returns_json(self):
        response = self.client.get("/search?q=anything")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/json", response.content_type)
        self.assertEqual(response.get_json(), {"results": []})

    def test_search_still_returns_an_empty_list_for_an_empty_query(self):
        self.assertEqual(self.client.get("/search").get_json(), {"results": []})


class SearchFindsTheNameTheUserCanSee(unittest.TestCase):
    """CLAUDE-SEARCH-NAME-MATCH-01.

    Reproduced live on the deployed build: a project shown everywhere as
    "Project Smoke Detector (PSD)" returned "Nothing matched" for the query
    "smoke", because search consulted only the ingested filename and the
    project id. _project_summary records the opposite intent a few hundred
    lines above the search code - "the professional-facing project identity
    should be its own display_title, not the accident of which document
    happened to be uploaded first".
    """

    def setUp(self):
        import app as app_module
        from services.case_workspace import CaseWorkspaceStore
        from services.requirements_registry import RequirementsRegistry
        from services.bhive_parser import ParsedDocument

        self.tmp = Path(tempfile.mkdtemp(prefix="search_name_match_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp)

        RequirementsRegistry(self.tmp).save(ParsedDocument(
            project_id="psd-001",
            filename="Owner_Program_Rev_2.pdf",
            ingested_at="2026-01-01T00:00:00+00:00",
        ))
        store = CaseWorkspaceStore(self.tmp)
        workspace = store.get_or_create("psd-001")
        workspace.display_title = "Project Smoke Detector (PSD)"
        store.save(workspace)

        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "admin"
            session["role"] = "admin"

    def _results(self, query):
        return self.client.get(f"/search?q={query}").get_json()["results"]

    def test_the_displayed_name_is_searchable(self):
        """The defect, stated as the property that was missing."""
        results = self._results("smoke")
        self.assertEqual(len(results), 1, "the displayed project name is not searchable")
        self.assertEqual(results[0]["title"], "Project Smoke Detector (PSD)")

    def test_the_original_filename_still_matches(self):
        """The prior behaviour is added to, never replaced."""
        self.assertEqual(len(self._results("Owner_Program")), 1)

    def test_the_project_reference_still_matches(self):
        self.assertEqual(len(self._results("psd-001")), 1)

    def test_a_result_carries_the_name_the_rest_of_the_product_shows(self):
        result = self._results("psd-001")[0]
        self.assertEqual(result["title"], "Project Smoke Detector (PSD)")
        self.assertEqual(result["subtitle"], "psd-001")

    def test_the_page_finds_it_too_since_both_share_one_function(self):
        html = self.client.get("/find?q=smoke").get_data(as_text=True)
        self.assertIn("Project Smoke Detector (PSD)", html)
        self.assertNotIn('data-ui-ref="search.empty"', html)

    def test_a_project_with_no_display_title_still_matches_by_filename(self):
        """The fallback path: display_name IS the filename until one is set."""
        from services.requirements_registry import RequirementsRegistry
        from services.bhive_parser import ParsedDocument
        RequirementsRegistry(self.tmp).save(ParsedDocument(
            project_id="plain-002", filename="Untitled_Upload.pdf",
            ingested_at="2026-01-02T00:00:00+00:00"))
        results = self._results("Untitled_Upload")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Untitled_Upload.pdf")

class ThereIsStillOneSearchImplementation(unittest.TestCase):
    """No second engine, no duplicate index - asserted against the source."""

    def test_both_presentations_call_the_same_matching_function(self):
        source = Path("routes/portal.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("def _global_search_results"), 1)
        # Both the endpoint and the page delegate to it.
        self.assertGreaterEqual(source.count("_global_search_results("), 3)

    def test_the_search_endpoint_no_longer_carries_a_match_rule_of_its_own(self):
        """global_search must delegate, not match.

        Deliberately NOT "the rule appears exactly once in the file". It
        already appeared four times before this change and still does: the
        Projects directory and the Document Shop run the same substring match
        over their own listings, which global_search's own docstring has always
        said ("the same filename/project_id substring match the Projects
        directory's own search already uses"). Asserting 1 would have been
        asserting a tidiness this change did not make and was not asked to.

        What this change is responsible for is not adding a fifth. So the
        property under test is the extraction itself: the endpoint's body is a
        delegation and contains no matching of its own.
        """
        source = Path("routes/portal.py").read_text(encoding="utf-8")
        start = source.index("def global_search()")
        body = source[start:source.index("def _global_search_results", start)]
        self.assertIn("_global_search_results(", body)
        self.assertNotIn("needle", body)
        self.assertNotIn(".lower()", body)

    def test_the_search_page_template_makes_no_network_call_of_its_own(self):
        template = Path("templates/search.html").read_text(encoding="utf-8")
        for forbidden in ("fetch(", "XMLHttpRequest", "<script"):
            self.assertNotIn(forbidden, template)


if __name__ == "__main__":
    unittest.main()
