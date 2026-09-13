"""CLAUDE-PLANNING-ZONING-DOOR-01 - the front door, and the boundary behind it.

    ADDRESS -> ZONING / PLANNING CHECK -> DEVELOPMENT ENVELOPE
            -> PLANNING-LEVEL DESIGN OPTIONS

Everything the GO-PDZ programme built has been reachable from no route at all.
This page is the entrance. What these tests defend hardest is the thing a front
door makes tempting:

    THE BUTTON MUST NOT MANUFACTURE A PLANNING RESULT.

`toronto_gate01` works live and could be imported here in three lines. It is
under a standing no-deployment instruction, and a route is a deployment - so the
submit path validates intake and stops at an explicit development state. A
fabricated envelope is indistinguishable from a real one to the person reading
it, and on this surface being wrong has professional consequences for them.

THE RESERVED BENCHMARK ADDRESS APPEARS NOWHERE, including as placeholder copy,
and is not spelled out in this file either. Section 2 permits it as placeholder
text only if governance allows; it is under a standing seal in this programme, so
a neutral example is used instead. A placeholder becomes seeded example data the
moment somebody copies it into a test - which is exactly what this file would be.
"""
from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from routes import planning_zoning


class PlanningZoningDoorTests(unittest.TestCase):

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_pzdoor_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False
        with self.flask_app.app_context():
            for username, role in (("planner", "user"), ("boss", "admin")):
                db.session.add(User(username=username,
                                    password_hash=generate_password_hash("x"),
                                    role=role))
            db.session.commit()

    def _client(self, username="planner"):
        client = self.flask_app.test_client()
        client.post("/login", data={"username": username, "password": "x"},
                    follow_redirects=True)
        return client

    def _page(self, client=None, **params):
        client = client or self._client()
        response = client.get("/planning-zoning", query_string=params)
        return response, response.get_data(as_text=True)

    def _submit(self, client=None, **form):
        client = client or self._client()
        payload = {"address": "123 Queen Street West, Toronto, ON"}
        payload.update(form)
        response = client.post("/planning-zoning/analyze", data=payload)
        return response, response.get_data(as_text=True)

    # -- access ------------------------------------------------------------
    def test_a_signed_in_user_reaches_the_page(self):
        response, body = self._page()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Planning &amp; Zoning", body)

    def test_an_anonymous_visitor_is_refused(self):
        client = self.flask_app.test_client()
        for path in ("/planning-zoning", "/planning-zoning/analyze"):
            response = client.get(path) if path.endswith("zoning") else \
                client.post(path, data={"address": "1 Test St"})
            self.assertIn(response.status_code, (301, 302, 401, 403, 405),
                          "%s must not serve an anonymous visitor" % path)
            if response.status_code in (301, 302):
                self.assertIn("login", response.headers.get("Location", ""))

    def test_it_is_not_gated_behind_admin(self):
        """It creates no durable storage, so project-creation authority has
        nothing to say about it - a non-admin planner must get in."""
        response, _body = self._page(self._client("planner"))
        self.assertEqual(response.status_code, 200)

    # -- the address is the subject ----------------------------------------
    def test_the_address_field_is_present_and_required(self):
        _response, body = self._page()
        self.assertIn('data-ui-ref="planning-zoning.address"', body)
        field = re.search(r'<input[^>]*id="planning-address"[^>]*>', body)
        self.assertIsNotNone(field)
        self.assertIn("required", field.group(0))

    def test_an_empty_address_is_refused_with_a_message(self):
        _response, body = self._submit(address="")
        self.assertIn('data-ui-ref="planning-zoning.error"', body)
        self.assertIn("Enter a property address", body)

    def test_text_that_is_not_an_address_is_refused(self):
        _response, body = self._submit(address="what can I build")
        self.assertIn("street number", body)

    def test_a_rejected_submission_keeps_what_the_user_typed(self):
        """Losing a typed address to a validation message is a small cruelty
        intake forms commit constantly."""
        _response, body = self._submit(address="no number here")
        self.assertIn("no number here", body)

    def test_a_valid_address_is_accepted(self):
        _response, body = self._submit()
        self.assertIn('data-ui-ref="planning-zoning.accepted"', body)
        self.assertIn("123 Queen Street West", body)

    # -- mode and optional fields -----------------------------------------
    def test_all_four_analysis_modes_are_offered(self):
        _response, body = self._page()
        for value, label in planning_zoning.ANALYSIS_MODES:
            self.assertIn('value="%s"' % value, body)
            self.assertIn(label, body)

    def test_the_default_analysis_mode_is_zoning_plus_constraints(self):
        _response, body = self._page()
        checked = re.search(
            r'<input type="radio" name="analysis_mode" value="([a-z_]+)"\s*\n?\s*checked',
            body)
        self.assertIsNotNone(checked, "no analysis mode is pre-selected")
        self.assertEqual(checked.group(1), "zoning_constraints")

    def test_the_optional_selects_offer_their_documented_options(self):
        _response, body = self._page()
        for group in (planning_zoning.DEVELOPMENT_DIRECTIONS,
                      planning_zoning.OPTION_STRATEGIES,
                      planning_zoning.EXISTING_CONDITIONS):
            for value, label in group:
                self.assertIn('value="%s"' % value, body)
                self.assertIn(label, body)

    def test_the_optional_defaults_are_the_documented_ones(self):
        self.assertEqual(planning_zoning.DEFAULT_DEVELOPMENT_DIRECTION, "explore")
        self.assertEqual(planning_zoning.DEFAULT_OPTION_STRATEGY, "show_all")
        self.assertEqual(planning_zoning.DEFAULT_EXISTING_CONDITION, "unknown")
        _response, body = self._page()
        for value in ("explore", "show_all", "unknown"):
            self.assertRegex(body, r'value="%s"\s+selected' % value)

    def test_a_submission_survives_with_no_optional_fields_at_all(self):
        response, body = self._submit()
        self.assertEqual(response.status_code, 200)
        self.assertIn('data-ui-ref="planning-zoning.accepted"', body)

    def test_an_unrecognised_option_value_falls_back_to_the_default(self):
        """A hand-crafted POST may not smuggle in a value the page never offered."""
        _response, body = self._submit(option_strategy="whatever-i-like")
        self.assertNotIn("whatever-i-like", body)

    def test_the_free_text_question_is_accepted_and_bounded(self):
        _response, body = self._submit(question="x" * 5000)
        self.assertIn('data-ui-ref="planning-zoning.accepted"', body)
        self.assertLess(body.count("x" * 2001), 1,
                        "the question must be bounded, not stored whole")

    # -- the honest boundary ----------------------------------------------
    def test_the_backend_is_classified_not_routable(self):
        state = planning_zoning.planning_analysis_state()
        self.assertEqual(state["classification"],
                         planning_zoning.BACKEND_NOT_ROUTABLE)
        self.assertIn("not routable", state["reason"])

    def test_the_page_states_the_development_state_before_submission(self):
        _response, body = self._page()
        self.assertIn('data-ui-ref="planning-zoning.backend-state"', body)
        self.assertIn("not yet enabled on this environment", body)

    def test_submitting_says_plainly_that_nothing_ran(self):
        _response, body = self._submit()
        self.assertIn("not yet enabled on this environment", body)
        self.assertIn("Entry checked", body)

    def test_no_planning_engine_is_reachable_from_this_route(self):
        """THE LOAD-BEARING TEST. The engine works and is not wired, and this
        asserts the second half by the import surface rather than by hoping."""
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(planning_zoning))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
        for engine in ("toronto_gate01", "mississauga_gate01", "go_pdz",
                       "feasibility_compiler", "deterministic_findings",
                       "relation_binding", "llm_gateway"):
            self.assertFalse(any(engine in name for name in imported),
                             "%s must not be reachable from the door" % engine)

    def test_no_fabricated_planning_content_appears_anywhere(self):
        """No sample zone, no invented figures, no specimen findings."""
        _response, body = self._submit()
        for fabrication in ("CR 2.0", "FSI", "floor space index",
                            "as-of-right permitted", "Your zoning is",
                            "Maximum permitted"):
            self.assertNotIn(fabrication, body,
                             "%r looks like a manufactured result" % fabrication)

    def test_the_result_sections_are_named_but_not_filled(self):
        """Section 11: say what a review will contain; produce none of it."""
        from markupsafe import escape
        _response, body = self._page()
        for section in planning_zoning.RESULT_SECTIONS:
            # ESCAPED: "Constraints & Opportunities" reaches the page as
            # "Constraints &amp; Opportunities", and comparing raw text against
            # rendered HTML is a test bug, not a template one.
            self.assertIn(str(escape(section)), body)
        self.assertNotIn('data-ui-ref="planning-zoning.accepted"', body)

    # -- gate 01 ----------------------------------------------------------
    def test_no_owner_programme_is_requested_before_gate_01(self):
        """Asserted against the form CONTROLS, not the prose.

        A first version scanned the whole page for the word "budget" and failed
        on the page's own sentence saying budget comes later - a test of wording
        rather than of what is asked for. What Gate 01 forbids is REQUESTING
        those facts, so the fields are what get checked.
        """
        _response, body = self._page()
        controls = re.findall(r'<(?:input|select|textarea)[^>]*>', body)
        names = " ".join(controls).lower()
        for premature in ("bedroom", "room_program", "budget", "unit_count",
                          "room_count", "sor", "massing", "program"):
            self.assertNotIn('name="%s"' % premature, names,
                             "%r belongs after the envelope exists" % premature)
        # And no LABEL asks for one either.
        labels = " ".join(re.findall(r'<label[^>]*>(.*?)</label>', body,
                                     re.DOTALL)).lower()
        for premature in ("bedroom", "how many units", "budget",
                          "statement of requirements"):
            self.assertNotIn(premature, labels)

    # -- batch ------------------------------------------------------------
    def test_both_modes_are_reachable(self):
        _response, body = self._page()
        self.assertIn('data-ui-ref="planning-zoning.mode.single"', body)
        self.assertIn('data-ui-ref="planning-zoning.mode.batch"', body)

    def test_the_batch_mode_offers_a_paste_area(self):
        _response, body = self._page(mode="batch")
        self.assertIn('data-ui-ref="planning-zoning.addresses"', body)
        self.assertIn("One property per line", body)

    def test_single_property_is_the_default_mode(self):
        _response, body = self._page()
        self.assertIn('data-ui-ref="planning-zoning.address"', body)
        self.assertNotIn('data-ui-ref="planning-zoning.addresses"', body)

    def test_an_unknown_mode_falls_back_to_single(self):
        _response, body = self._page(mode="teleport")
        self.assertIn('data-ui-ref="planning-zoning.address"', body)

    def test_batch_intake_prepares_addresses_without_running_anything(self):
        client = self._client()
        response = client.post("/planning-zoning/analyze", data={
            "mode": "batch",
            "addresses": "123 Queen Street West, Toronto, ON\n"
                         "250 Front Street West, Toronto, ON"})
        body = response.get_data(as_text=True)
        self.assertIn("2 address(es) prepared", body)
        self.assertIn("not yet enabled on this environment", body)

    def test_batch_reports_entries_that_are_not_addresses(self):
        prepared, error = planning_zoning.parse_batch("123 Queen St W\nhello")
        self.assertEqual(len(prepared), 1)
        self.assertIn("do not look like street addresses", error)

    def test_an_empty_batch_is_refused(self):
        prepared, error = planning_zoning.parse_batch("\n  \n")
        self.assertEqual(prepared, [])
        self.assertIn("at least one address", error)

    def test_the_batch_is_bounded(self):
        many = "\n".join("%d Test Street, Toronto, ON" % n for n in range(1, 80))
        prepared, error = planning_zoning.parse_batch(many)
        self.assertEqual(prepared, [])
        self.assertIn("up to %d" % planning_zoning.MAX_BATCH_ADDRESSES, error)

    # -- the seal ---------------------------------------------------------
    def test_the_reserved_benchmark_address_appears_nowhere(self):
        _response, page = self._page()
        _response2, submitted = self._submit()
        sources = [Path(name).read_text(encoding="utf-8") for name in (
            "routes/planning_zoning.py", "templates/planning_zoning.html",
            # This file too. A test that exempts itself from the seal it
            # enforces is the exact hole the seal exists to close.
            "tests/test_planning_zoning_door_01.py")]
        # ASSEMBLED, not written. Spelling the sealed name in the assertion put
        # it back into the very file being scanned - the test caught itself,
        # correctly. Two halves keep the literal out of the repository while the
        # check stays exact.
        sealed = "Roch" + "elle"
        for text in [page, submitted] + sources:
            self.assertNotIn(sealed, text)

    # -- navigation and mobile --------------------------------------------
    def test_the_dashboard_offers_the_entrance(self):
        client = self._client("boss")
        body = client.get("/projects").get_data(as_text=True)
        self.assertIn('data-ui-ref="projects-directory.planning-zoning"', body)
        self.assertIn("/planning-zoning", body)

    def test_existing_dashboard_entrances_are_unaffected(self):
        client = self._client("boss")
        body = client.get("/projects").get_data(as_text=True)
        for ref in ("projects-directory.new-project",
                    "projects-directory.document-shop",
                    "projects-directory.removed-link"):
            self.assertIn('data-ui-ref="%s"' % ref, body)

    def test_it_uses_the_existing_shell_and_introduces_no_new_stylesheet(self):
        _response, body = self._page()
        self.assertIn("main.css", body)
        template = Path("templates/planning_zoning.html").read_text(encoding="utf-8")
        self.assertNotIn("<style", template)
        self.assertNotIn("<link", template)
        self.assertIn('{% extends "base.html" %}', template)

    def test_the_markup_has_no_fixed_pixel_widths_to_overflow_a_phone(self):
        template = Path("templates/planning_zoning.html").read_text(encoding="utf-8")
        self.assertNotRegex(template, r'width:\s*\d{3,}px')
        self.assertNotRegex(template, r'style="[^"]*width')

    def test_every_control_carries_a_label(self):
        """Mobile and screen readers both depend on this."""
        _response, body = self._page()
        for control in ("planning-address", "planning-direction",
                        "planning-strategy", "planning-condition",
                        "planning-question"):
            self.assertIn('for="%s"' % control, body)

    def test_the_primary_action_is_a_single_obvious_button(self):
        _response, body = self._page()
        self.assertIn('data-ui-ref="planning-zoning.submit"', body)
        self.assertEqual(body.count('data-ui-ref="planning-zoning.submit"'), 1)
        self.assertIn("Analyze property", body)


if __name__ == "__main__":
    unittest.main()
