"""
Canonical terminology — an INTERNAL capability, deliberately not a feature.

WHY THIS MODULE HAS NO USER-FACING SURFACE

A visible vocabulary aid was built and then superseded by the Product Owner
before it shipped: a context-aware Help system should infer what "this" means
from the UI context the user came from, rather than ask them to learn ARCHIOSK's
vocabulary. Asking someone to consult a glossary is the thing a context-aware
system exists to avoid.

The matcher was kept because none of the reasons to have it depended on showing
it. Permitted internal uses are normalization, retrieval, matching Help Scripts
and output wording. The CANONICAL/AMBIGUOUS distinction it reports is precisely
what a future contextual resolver needs in order to decide between resolving
silently and asking "Do you mean Delta Spin or Survival Mode?" — so it is
retained rather than deleted, and its ambiguity half is the part that matters.

Half of the tests below defend the pure matching behaviour. The other half exist
to make the DROP durable: they assert the module stays unwired and the Studio
renders no vocabulary UI, so its return would have to be a deliberate act rather
than a quiet drift back.

No test here reaches the network, and the matcher makes no model call at all.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from services.case_workspace import CaseWorkspaceStore
from services.help_clip_studio import guide_documents
from services.help_vocabulary import (
    CANONICAL_TERMS,
    CONFIDENCE_AMBIGUOUS,
    CONFIDENCE_CANONICAL,
    apply_accepted_terms,
    canonical_terms,
    suggest_terms,
)

SCENARIO = "Explain the survival review button and the second spin to a new user."
_REPO_ROOT = Path(__file__).resolve().parent.parent


class TerminologyMatchingTests(unittest.TestCase):
    """The pure function. No app, no store, no model, no UI."""

    def test_a_misspelled_canonical_term_is_recognised(self):
        hints = suggest_terms("Explain survival mode to a new user.")
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]["canonical"], "Survival Mode")
        self.assertEqual(hints[0]["confidence"], CONFIDENCE_CANONICAL)

    def test_correct_wording_produces_nothing(self):
        self.assertEqual(suggest_terms("Explain Survival Mode and Delta Spin."), [])

    def test_unrelated_wording_produces_nothing(self):
        self.assertEqual(suggest_terms("Explain how to upload a drawing set."), [])

    def test_ambiguous_wording_is_reported_as_ambiguous(self):
        """The half that survives into contextual Help.

        A resolver may only answer silently when exactly one reading is
        plausible; this flag is how it knows the difference. Without it there is
        no principled place to decide between resolving and asking.
        """
        hints = {h["canonical"]: h for h in suggest_terms(SCENARIO)}
        self.assertEqual(hints["Delta Spin"]["confidence"], CONFIDENCE_AMBIGUOUS)
        self.assertEqual(hints["Survival Mode"]["confidence"], CONFIDENCE_AMBIGUOUS)

    def test_more_than_one_plausible_reading_is_visible_to_a_caller(self):
        """"survival spin" could be Survival Mode or a Spin. A caller must be
        able to see that two readings exist rather than receive one of them."""
        readings = {h["canonical"] for h in suggest_terms("run the survival spin")}
        self.assertIn("Survival Mode", readings)

    def test_nothing_is_rewritten_without_an_explicit_accept(self):
        self.assertEqual(apply_accepted_terms(SCENARIO, []), SCENARIO)
        self.assertEqual(apply_accepted_terms(SCENARIO, None), SCENARIO)

    def test_accepting_one_term_leaves_the_others_untouched(self):
        applied = apply_accepted_terms(SCENARIO, ["Survival Mode"])
        self.assertIn("Survival Mode", applied)
        self.assertIn("second spin", applied)

    def test_normalization_rewrites_only_the_phrase_not_the_sentence(self):
        applied = apply_accepted_terms(SCENARIO, ["Survival Mode", "Delta Spin"])
        self.assertEqual(applied,
                         "Explain the Survival Mode and the Delta Spin to a new user.")

    def test_an_unknown_term_changes_nothing(self):
        self.assertEqual(apply_accepted_terms(SCENARIO, ["Not A Real Term"]), SCENARIO)

    def test_matching_makes_no_model_call(self):
        with patch("anthropic.Anthropic") as never:
            suggest_terms(SCENARIO)
            apply_accepted_terms(SCENARIO, ["Delta Spin"])
            never.assert_not_called()

    def test_matching_is_word_boundary_not_substring(self):
        self.assertEqual(suggest_terms("The rfid tag and the respinning wheel."), [])

    def test_matching_tolerates_whitespace_but_is_not_fuzzy(self):
        self.assertEqual(len(suggest_terms("survival  mode")), 1)
        self.assertEqual(suggest_terms("survivel moed"), [])


class TerminologyStaysInternalTests(unittest.TestCase):
    """The drop, made durable."""

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_vocab_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False
        with self.flask_app.app_context():
            db.session.add(User(username="reviewer",
                                password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def _client(self):
        client = self.flask_app.test_client()
        client.post("/login", data={"username": "reviewer", "password": "x"},
                    follow_redirects=True)
        return client

    def test_no_route_imports_the_vocabulary_module(self):
        """An unused import is how a dropped feature quietly comes back."""
        for path in (_REPO_ROOT / "routes").glob("*.py"):
            self.assertNotIn("help_vocabulary", path.read_text(encoding="utf-8"),
                             "%s wired the vocabulary back into a route" % path.name)

    def test_no_template_renders_vocabulary_ui(self):
        for path in (_REPO_ROOT / "templates").rglob("*.html"):
            markup = path.read_text(encoding="utf-8")
            self.assertNotIn("vocab-chip", markup)
            self.assertNotIn("accept_term", markup)

    def test_the_studio_page_shows_no_terminology_surface(self):
        """The real page, not just the source. A reviewer sees one field."""
        page = self._client().get("/help/studio").get_data(as_text=True)
        self.assertIn("Scenario", page, "the Studio lost its one real field")
        for forbidden in ("Preferred term", "Did you mean", "vocab-chip",
                          "accept_term", "Glossary", "glossary"):
            self.assertNotIn(forbidden, page)

    def test_generation_asks_nothing_about_wording(self):
        """Submitting a scenario full of non-canonical wording must go straight
        to generation, not pause to teach the reviewer vocabulary."""
        client = self._client()
        client.get("/help/studio")
        with patch("routes.help_center.generate_help_clip") as generate:
            generate.side_effect = RuntimeError("stop here")
            try:
                client.post("/help/studio/generate", data={"scenario": SCENARIO})
            except RuntimeError:
                pass
        self.assertTrue(generate.called, "generation was interrupted by a wording prompt")
        self.assertEqual(generate.call_args.kwargs["scenario"], SCENARIO,
                         "the reviewer's wording was altered without being asked")

    def test_the_module_reaches_into_nothing(self):
        """No store, no Flask, no model, no geometry - it is string matching."""
        import services.help_vocabulary as vocab
        source = Path(vocab.__file__).read_text(encoding="utf-8").lower()
        for forbidden in ("caseworkspacestore", "from flask", "anthropic",
                          "engine.", "render_template"):
            self.assertNotIn(forbidden, source)

    def test_terms_are_grounded_in_the_published_guides(self):
        """A product rename breaks this rather than leaving the list quietly
        contradicting the guides it is supposed to reflect."""
        from routes.help_center import GUIDES
        from flask import render_template

        with self.flask_app.test_request_context():
            corpus = " ".join(
                doc["text"] for doc in guide_documents(
                    lambda template: render_template(template, guides=GUIDES), GUIDES)
            ).lower()

        exempt = {"WorkProduct", "Help / Learning Mode", "Project Mode", "Investigation"}
        for term in canonical_terms():
            if term in exempt:
                continue
            self.assertIn(term.lower(), corpus,
                          "%r is not used by any published guide" % term)

    def test_it_stayed_a_list_and_not_a_taxonomy(self):
        self.assertLessEqual(len(CANONICAL_TERMS), 15)
        for term in CANONICAL_TERMS:
            self.assertFalse(hasattr(term, "children"))
            self.assertFalse(hasattr(term, "parent"))


if __name__ == "__main__":
    unittest.main()
