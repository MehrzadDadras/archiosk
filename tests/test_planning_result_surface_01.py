"""CLAUDE-PLANNING-RESULT-SURFACE-01 - the result surface, on a fixture.

    GO-PDZ-1.0-ONEPAGE  ->  ten sections an architect can read in order

WHAT IS BEING PROVEN IS RENDERING, NOT ANALYSIS, and the tests that matter most
are the ones that keep those two apart. The page is served from a development
fixture; no municipal source, no model and no live GO-PDZ service is consulted,
and the page says DEVELOPMENT PREVIEW before it says anything else.

THE FIXTURE IS A REAL CONTRACT DOCUMENT. It validates against
`go_pdz_contract.SCHEMA` and passes VR-01..VR-21 with zero errors - and it did
not at first. Its deterministic statement declared DETERMINISTIC_DERIVATION with
no attestation behind it, which VR-21 correctly governs as a model derivation
that may not be stated as ESTABLISHED / HIGH. A fixture that could not exist
would prove nothing about rendering the real thing, so it now carries an
attestation built by the actual verifier over its own figures.

THE RENDERER DOES NOT DECIDE WHAT IS AN OPPORTUNITY. The first version sorted
section 6 by looking for words like "permits", and filed "whether the Official
Plan permits this intensity CANNOT BE DETERMINED" as an opportunity. The split is
now declared by the producer, and a test holds that line.
"""
from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from markupsafe import escape
from werkzeug.security import generate_password_hash

from services import go_pdz_contract as contract
from services import go_pdz_validator as validator
from services import planning_result_view as view
from tests.master_ui_helpers import master_command, read_expanded, expand_partials


class TheFixtureIsARealContractDocument(unittest.TestCase):
    """Section 4."""

    def setUp(self):
        self.document = view.DEVELOPMENT_FIXTURE["document"]

    def test_it_satisfies_the_canonical_structure(self):
        self.assertEqual(contract.validate_structure(self.document), [])

    def test_it_passes_semantic_validation_with_no_errors(self):
        verdict = validator.validate(self.document)
        self.assertEqual(verdict["error_count"], 0,
                         str(verdict["findings"])[:600])

    def test_its_deterministic_statement_carries_a_real_attestation(self):
        """Not a hand-written proof object - VR-21 caught that version."""
        from services import derivation_check
        statement = next(s for s in self.document["statements"]
                         if s["statement_id"] == "F-FSI-ENVELOPE")
        check = statement["derivation_check"]
        self.assertTrue(derivation_check.is_valid_attestation(check))
        self.assertEqual(check["computed"],
                         {"sum": 2.5, "total": 2.0, "exceeds_by": 0.5})

    def test_it_is_marked_as_development_data(self):
        self.assertEqual(view.DEVELOPMENT_FIXTURE["data_class"],
                         view.DATA_CLASS_DEVELOPMENT)
        self.assertTrue(view.development_view()["preview"])

    def test_it_uses_a_synthetic_address(self):
        address = self.document["subject"]["address_as_given"]
        self.assertIn("Example", address)

    def test_the_reserved_benchmark_address_appears_nowhere(self):
        sealed = "Roch" + "elle"
        for name in ("services/planning_result_view.py",
                     "templates/planning_zoning_result.html",
                     "tests/test_planning_result_surface_01.py"):
            self.assertNotIn(sealed, Path(name).read_text(encoding="utf-8"))


class TheProjectionAddsNothingAndLosesNothing(unittest.TestCase):

    def test_every_statement_reaches_exactly_one_section(self):
        """A projection that loses a finding is worse than no projection: the
        reader cannot tell that something is missing."""
        document = view.DEVELOPMENT_FIXTURE["document"]
        rendered = view.development_view()
        seen = []
        for group in (rendered["identity"], rendered["framework"],
                      rendered["permitted"], rendered["envelope"],
                      rendered["mobility"]):
            seen += [item["statement_id"] for item in group["statements"]]
        seen += [item["statement_id"]
                 for item in rendered["interpretation"]["constraints"]]
        seen += [item["statement_id"]
                 for item in rendered["interpretation"]["opportunities"]]
        expected = [s["statement_id"] for s in document["statements"]]
        self.assertEqual(sorted(seen), sorted(expected))
        self.assertEqual(len(seen), len(set(seen)), "a statement was duplicated")

    def test_interpretations_are_separated_from_established_records(self):
        """Sections 1-5 are what the records establish; 6 is what was read in."""
        rendered = view.development_view()
        for group in (rendered["identity"], rendered["framework"],
                      rendered["permitted"], rendered["envelope"],
                      rendered["mobility"]):
            for item in group["statements"]:
                self.assertNotEqual(item["kind"], "GO_INTERPRETS", item["text"][:60])
        section_six = (rendered["interpretation"]["constraints"]
                       + rendered["interpretation"]["opportunities"])
        for item in section_six:
            self.assertEqual(item["kind"], "GO_INTERPRETS")

    def test_the_opportunity_split_is_declared_not_inferred_from_wording(self):
        """The dependency statement contains the word "permits" and is NOT an
        opportunity. Reading intent out of prose is the failure this avoids."""
        rendered = view.development_view()
        constraints = [i["statement_id"]
                       for i in rendered["interpretation"]["constraints"]]
        opportunities = [i["statement_id"]
                         for i in rendered["interpretation"]["opportunities"]]
        self.assertIn("F-OP-DEPENDENCY", constraints)
        self.assertEqual(opportunities,
                         view.DEVELOPMENT_FIXTURE["opportunity_statement_ids"])

    def test_an_undeclared_interpretation_defaults_to_a_constraint(self):
        result = {"document": {"statements": [
            {"statement_id": "X", "kind": "GO_INTERPRETS", "topic": "DENSITY",
             "text": "Something that allows more than it limits."}]}}
        rendered = view.build_view(result)
        self.assertEqual(
            [i["statement_id"] for i in rendered["interpretation"]["constraints"]],
            ["X"])
        self.assertEqual(rendered["interpretation"]["opportunities"], [])

    def test_the_established_flag_reads_the_derivation_axis(self):
        rendered = view.development_view()
        by_id = {i["statement_id"]: i
                 for i in rendered["interpretation"]["constraints"]
                 + rendered["interpretation"]["opportunities"]}
        self.assertTrue(by_id["F-FSI-ENVELOPE"]["established"],
                        "an attested deterministic derivation is established")
        self.assertFalse(by_id["F-MIX"]["established"],
                         "a model derivation is a reading, not a record")

    def test_an_empty_result_does_not_raise(self):
        rendered = view.build_view({})
        self.assertEqual(rendered["options"], [])
        self.assertEqual(rendered["unresolved"], [])

    def test_the_section_order_is_the_ten_contract_sections(self):
        self.assertEqual(len(view.SECTION_ORDER), 10)

    def test_every_mapped_topic_is_one_a_runner_really_emits(self):
        """The map is checkable against the producer, not aspirational."""
        from services import toronto_gate01
        producer = set(toronto_gate01.REPORTED_OVERLAYS.values())
        source = Path("services/toronto_gate01.py").read_text(encoding="utf-8")
        producer |= set(re.findall(r'"topic": "([A-Z_]+)"', source))
        unknown = [topic for topic in view.TOPIC_SECTIONS
                   if topic not in producer]
        self.assertEqual(
            unknown, ["PERMITTED_USE", "LAND_USE_CATEGORY", "PARKING", "LOADING"],
            "only the documented forward-looking topics may be unmatched")


class TheResultPageRenders(unittest.TestCase):

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_pzresult_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False
        with self.flask_app.app_context():
            db.session.add(User(username="planner",
                                password_hash=generate_password_hash("x"),
                                role="user"))
            db.session.commit()

    def _client(self):
        client = self.flask_app.test_client()
        client.post("/login", data={"username": "planner", "password": "x"},
                    follow_redirects=True)
        return client

    def _page(self):
        response = self._client().get("/planning-zoning/result")
        return response, response.get_data(as_text=True)

    def test_a_signed_in_user_reaches_it(self):
        response, body = self._page()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Pre-Design Planning", body)

    def test_an_anonymous_visitor_is_refused(self):
        response = self.flask_app.test_client().get("/planning-zoning/result")
        self.assertIn(response.status_code, (301, 302, 401, 403))
        if response.status_code in (301, 302):
            self.assertIn("login", response.headers.get("Location", ""))

    def test_all_ten_sections_render_in_order(self):
        _response, body = self._page()
        positions = []
        for _key, label in view.SECTION_ORDER:
            marker = str(escape(label))
            self.assertIn(marker, body, label)
            positions.append(body.index(marker))
        self.assertEqual(positions, sorted(positions),
                         "the sections must read in contract order")

    def test_the_development_preview_banner_is_first(self):
        _response, body = self._page()
        self.assertIn("DEVELOPMENT PREVIEW", body)
        self.assertLess(body.index("DEVELOPMENT PREVIEW"),
                        body.index("Property Identity"),
                        "a reader must know what this is before they read it")

    def test_property_identity_shows_what_section_6_asks_for(self):
        _response, body = self._page()
        for ref in ("identity.address", "identity.confidence",
                    "identity.parcel", "identity.status"):
            self.assertIn('data-ui-ref="planning-zoning.result.%s"' % ref, body)

    def test_statements_are_labelled_by_basis(self):
        _response, body = self._page()
        self.assertIn("from record", body)
        self.assertIn("GO reading", body)

    def test_the_basis_badge_does_not_collide_with_the_status_word(self):
        """"UNRESOLVED established" read as a contradiction; two axes, two words."""
        _response, body = self._page()
        self.assertNotRegex(body, r"UNRESOLVED\s*</span>\s*<span[^>]*>\s*established")

    def test_option_cards_render_with_their_parts(self):
        _response, body = self._page()
        self.assertEqual(body.count('data-ui-ref="planning-zoning.result.option"'),
                         len(view.DEVELOPMENT_FIXTURE["options"]))
        for posture in ("AS-OF-RIGHT", "MAXIMUM COMPLIANT", "RELIEF-DEPENDENT"):
            self.assertIn(posture, body)
        for ref in ("option.rationale", "option.conditions", "option.constraint",
                    "option.dependency"):
            self.assertIn('data-ui-ref="planning-zoning.result.%s"' % ref, body)

    def test_only_options_present_in_the_result_are_rendered(self):
        """The fixture carries no Option D, so none may appear."""
        _response, body = self._page()
        self.assertNotIn("SPECULATIVE TEST", body)

    def test_unresolved_items_say_what_settles_them_and_whether_they_block(self):
        _response, body = self._page()
        self.assertIn("Settled by:", body)
        self.assertIn("Blocks a governed planning conclusion", body)
        self.assertIn("Does not block a planning conclusion", body)
        self.assertIn("MATERIAL", body)

    def test_the_evidence_footer_is_expandable_and_carries_provenance(self):
        _response, body = self._page()
        self.assertIn('data-ui-ref="planning-zoning.result.evidence"', body)
        self.assertIn("<details", body)
        self.assertIn(contract.CONTRACT_ID, body)
        self.assertIn("IN_FORCE", body)

    def test_the_evidence_footer_does_not_dump_a_prompt(self):
        _response, body = self._page()
        for leak in ("You compile already-retrieved", "EVIDENCE PACKAGE:",
                     "system prompt", "instructions:"):
            self.assertNotIn(leak, body)

    def test_the_conclusion_reports_the_documents_own_status(self):
        _response, body = self._page()
        self.assertIn("Result status:", body)
        self.assertIn("UNRESOLVED", body)

    def test_back_to_address_is_available_and_develop_further_is_disabled(self):
        _response, body = self._page()
        # SUPERSEDED DELIBERATELY (MASTERUI cutover): the page-local "Back to
        # address" -> MODEL > Planning & Zoning Analysis, active, same route.
        self.assertIn('href="/planning-zoning"', master_command(body, "model.planning")[1])
        control = re.search(
            r'<button[^>]*data-ui-ref="planning-zoning\.result\.develop-further"[^>]*>',
            body)
        self.assertIsNotNone(control)
        self.assertIn("disabled", control.group(0))

    def test_gate_01_is_not_crossed(self):
        _response, body = self._page()
        controls = " ".join(re.findall(r'<(?:input|select|textarea)[^>]*>', body))
        for premature in ("bedroom", "budget", "unit_count", "room_count"):
            self.assertNotIn('name="%s"' % premature, controls)


class NothingLiveIsConsulted(unittest.TestCase):
    """Section 19, asserted by the import surface rather than by intention."""

    def _imports_of(self, module_name):
        import ast
        import importlib
        module = importlib.import_module(module_name)
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                names.add(node.module or "")
                names.update("%s.%s" % (node.module or "", alias.name)
                             for alias in node.names)
        return names

    def test_the_view_reaches_no_municipal_source_and_no_model(self):
        forbidden = ("toronto_planning_source", "mississauga_planning_source",
                     "toronto_gate01", "mississauga_gate01", "llm_gateway",
                     "gateway_model", "feasibility_compiler", "requests",
                     "urllib")
        names = self._imports_of("services.planning_result_view")
        for banned in forbidden:
            self.assertFalse(any(banned in name for name in names),
                             "%s must not be reachable from the view" % banned)

    def test_the_route_module_reaches_no_municipal_source_and_no_model(self):
        forbidden = ("toronto_planning_source", "toronto_gate01", "llm_gateway",
                     "gateway_model", "feasibility_compiler", "requests")
        names = self._imports_of("routes.planning_zoning")
        for banned in forbidden:
            self.assertFalse(any(banned in name for name in names),
                             "%s must not be reachable from the route" % banned)

    def test_the_only_services_the_view_uses_are_offline_and_pure(self):
        """`derivation_check` and `relation_binding` are arithmetic, not engines -
        which is what lets the fixture carry a real attestation while the page
        still makes no live call."""
        names = self._imports_of("services.planning_result_view")
        modules = {name for name in names
                   if name.startswith("services.") and name != "services"}
        self.assertTrue(modules, "the view should import something")
        for name in modules:
            self.assertTrue(
                any(token in name for token in ("derivation_check",
                                                "go_pdz_contract",
                                                "relation_binding")),
                "%s is not one of the three pure, offline modules" % name)


class TheIntakePageIsUnaffected(unittest.TestCase):

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_pzresult2_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False
        with self.flask_app.app_context():
            db.session.add(User(username="planner",
                                password_hash=generate_password_hash("x"),
                                role="user"))
            db.session.commit()

    def test_the_intake_page_still_renders_and_still_stops(self):
        client = self.flask_app.test_client()
        client.post("/login", data={"username": "planner", "password": "x"},
                    follow_redirects=True)
        body = client.get("/planning-zoning").get_data(as_text=True)
        self.assertIn('data-ui-ref="planning-zoning.address"', body)
        self.assertIn("not yet enabled on this environment", body)
        submitted = client.post("/planning-zoning/analyze", data={
            "address": "123 Queen Street West, Toronto, ON"}).get_data(as_text=True)
        self.assertIn("Entry checked", submitted)
        self.assertNotIn("Pre-Design Planning", submitted,
                         "submitting must not render a fixture result")


if __name__ == "__main__":
    unittest.main()
