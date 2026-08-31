"""
CLAUDE-UPLOAD-COPY-TO-HELP-01 - the Help Center's guides, and the promises the
surfaces now make about them.

WHY THIS FILE EXISTS AT ALL

`routes/help_center.py` had no tests. Its `GUIDES` dict is a closed allowlist
mapping a URL key to a template path, and every entry is a promise that a file
exists at that path. A typo in either half produces a 404 or a 500 from a link
the product renders itself - and `templates/_app_menu.html` already carries a
comment about a hand-typed `/help/...` key 404ing silently, so this is a known
way to be wrong here.

The upload and Data Room surfaces now LINK to these guides instead of explaining
themselves inline. That converts a broken guide key from a cosmetic problem into
a dead end at the exact moment somebody needed help.

WHAT IS ASSERTED ABOUT CONTENT, AND WHY SO LITTLE

Almost nothing about prose - it will be edited, and a test that breaks when a
sentence improves is a test that gets deleted. The exceptions are the two claims
that must not silently become false: that the reconciliation guide continues to
say clash detection is NOT a capability, and that the safety sentence stayed on
the Reconcile control rather than moving behind a link.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from routes.help_center import GUIDES

_ROOT = Path(__file__).resolve().parent.parent


class _Base(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.app = app_module.create_app("testing")

    def client(self, authenticated=True, role="admin"):
        client = self.app.test_client()
        if authenticated:
            with client.session_transaction() as session:
                session["user_id"] = 1
                session["username"] = "tester"
                session["role"] = role
        return client


class EveryRegisteredGuideResolvesTests(_Base):
    """Each GUIDES entry is a promise that a template exists at that path."""

    def test_every_guide_template_file_exists(self):
        for key, entry in GUIDES.items():
            with self.subTest(guide=key):
                self.assertTrue((_ROOT / "templates" / entry["template"]).is_file(),
                                f"{key} points at a missing template")

    def test_every_guide_renders(self):
        client = self.client()
        for key in GUIDES:
            with self.subTest(guide=key):
                self.assertEqual(client.get(f"/help/{key}").status_code, 200)

    def test_every_guide_has_a_title_and_summary(self):
        for key, entry in GUIDES.items():
            with self.subTest(guide=key):
                self.assertTrue(entry.get("title"))
                self.assertTrue(entry.get("summary"))

    def test_the_index_links_every_guide(self):
        # A guide reachable only by typing its URL is a guide nobody reads.
        body = self.client().get("/help").get_data(as_text=True)
        for key in GUIDES:
            with self.subTest(guide=key):
                self.assertIn(key, body)

    def test_an_unknown_guide_is_404_not_a_template_error(self):
        # The allowlist exists so /help/<anything> cannot walk the template
        # directory; this asserts the refusal rather than trusting the dict.
        self.assertEqual(self.client().get("/help/no-such-guide").status_code, 404)

    def test_guides_are_behind_the_login_gate(self):
        # They name real project surfaces and role scopes; the blueprint
        # docstring is explicit that this is deliberate.
        response = self.client(authenticated=False).get("/help/what-is-reconciliation")
        self.assertIn(response.status_code, (302, 401))


class TheThreeNewGuidesTests(_Base):
    """Registered under the exact keys the surfaces link to."""

    EXPECTED = ("drawing-ingestion", "what-is-reconciliation", "file-types-and-limits")

    def test_all_three_are_registered(self):
        for key in self.EXPECTED:
            with self.subTest(guide=key):
                self.assertIn(key, GUIDES)

    def test_the_reconciliation_guide_says_clash_detection_is_not_a_capability(self):
        """The load-bearing content assertion.

        The brief for this guide asked it to describe "cross-discipline
        clash/version alignment". No clash detection exists in this codebase.
        The blueprint's own docstring forbids describing an unbuilt capability,
        so the guide states the absence - and this test exists so a later edit
        cannot quietly turn that into a description of a feature that is still
        not there.
        """
        body = self.client().get("/help/what-is-reconciliation").get_data(as_text=True)
        self.assertIn("not clash detection", body)

    def test_the_reconciliation_guide_names_the_real_verdicts(self):
        body = self.client().get("/help/what-is-reconciliation").get_data(as_text=True)
        for verdict in ("Unchanged", "New", "Modified", "Missing", "Renamed",
                        "Ineligible", "Ambiguous"):
            with self.subTest(verdict=verdict):
                self.assertIn(verdict, body)

    def test_the_limits_guide_does_not_quote_a_number_the_server_may_disagree_with(self):
        # MAX_UPLOAD_MB and MAX_CHUNKED_UPLOAD_MB are deployment settings. A
        # figure printed here that disagreed with the host would be worse than
        # no figure, so the guide names the variables instead.
        body = self.client().get("/help/file-types-and-limits").get_data(as_text=True)
        self.assertIn("MAX_UPLOAD_MB", body)
        self.assertIn("MAX_CHUNKED_UPLOAD_MB", body)

    def test_the_limits_guide_lists_exactly_the_accepted_extensions(self):
        from routes.workspace import ALLOWED_DOCUMENT_EXTENSIONS

        body = self.client().get("/help/file-types-and-limits").get_data(as_text=True)
        for ext in ALLOWED_DOCUMENT_EXTENSIONS:
            with self.subTest(ext=ext):
                self.assertIn(ext, body)


class TheSurfacesLinkRatherThanExplainTests(unittest.TestCase):
    """The point of the migration: a label and a link, not a wall of text."""

    def test_the_upload_card_links_to_file_types_and_limits(self):
        markup = (_ROOT / "templates" / "reset_project_data.html").read_text(encoding="utf-8")
        self.assertIn("guide='file-types-and-limits'", markup)

    def test_the_reconcile_control_links_to_the_reconciliation_guide(self):
        markup = (_ROOT / "templates" / "case_workspace.html").read_text(encoding="utf-8")
        self.assertIn("guide='what-is-reconciliation'", markup)

    def test_the_reconcile_safety_sentence_did_NOT_move_to_help(self):
        """An assurance about a governed action belongs at the point of action.

        "Nothing is added, relinked, or removed until you approve" is what makes
        the Reconcile button safe to press. Behind a link, the only people who
        read it are the ones who already went looking - which is not the group
        that needs it.
        """
        markup = (_ROOT / "templates" / "case_workspace.html").read_text(encoding="utf-8")
        # Whitespace-normalised: the sentence wraps across template lines, and a
        # test that breaks on re-indentation protects nothing.
        flat = " ".join(markup.split())
        self.assertIn("Nothing is added, relinked, or removed until you review",
                      flat)


if __name__ == "__main__":
    unittest.main()
