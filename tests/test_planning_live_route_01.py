"""CLAUDE-PLANNING-LIVE-01 - one bounded live Toronto path, and its edges.

    SIGNED-IN ADDRESS -> TORONTO GATE-01 -> RESULT VIEW -> RENDERED RESULT

HERMETIC. Not one test here reaches the City of Toronto: `run_live` takes its
gate and reader as injected seams with no defaults resolved until needed, so a
test that forgot to supply them would raise rather than quietly spend 77 seconds
on a municipal round trip. The real live request was run and measured separately;
what these tests defend is the routing, the flag, the boundary and the failure
vocabulary.

THE FLAG IS THE DEPLOYMENT DECISION. Default OFF, read from configuration only,
never inferred from DEBUG or a hostname or the presence of a credential - because
"live" is a governance state and guessing it from the surroundings is how a
preview becomes production without anyone deciding.

ONLY DATA_CLASS_LIVE REMOVES THE PREVIEW BANNER, and only the code that actually
ran the live path may set it. A test asserts the fixture route still shows the
banner with the flag ON, because a banner that disappears when a flag flips would
be reporting the environment rather than the data.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from services import planning_live as live
from services import planning_result_view as view

TORONTO = "573 Shuter Street, Toronto, ON"

#: A minimal governed Gate-01 envelope, shaped exactly as `toronto_gate01.run`
#: returns one. Built from the contract rather than copied from a live capture,
#: so it cannot drift into asserting whatever Toronto happened to answer once.
def _envelope(**overrides):
    document = {
        "contract": "GO-PDZ-1.0-ONEPAGE", "schema_version": "1.0",
        "gate": "GATE_01_ADDRESS_ONLY_ENVELOPE",
        "next_authorized_gate": "GATE_02_OWNER_PROGRAM_ENTRY",
        "subject": {"subject_id": "S-1", "address_as_given": TORONTO,
                    "normalized_address": "573 Shuter St",
                    "parcel_identifier": "TOR-PARCEL-TEST",
                    "municipality": "City of Toronto",
                    "identity_confidence": "HIGH"},
        "authorities": [{"authority_id": "TOR-BYLAW", "name": "By-law 569-2013",
                         "authority_status": "IN_FORCE",
                         "effective_date": "2013-05-09"}],
        "statements": [
            {"statement_id": "S-ZONE", "kind": "AUTHORITY_SAYS",
             "topic": "ZONING_DESIGNATION",
             "text": "The parcel lies within a zone labelled 'CR 2.0'.",
             "statement_status": "ESTABLISHED", "confidence": "HIGH",
             "authority_refs": ["TOR-BYLAW"], "conflict_refs": [],
             "derived_from": [], "spatial_relation": "INSIDE",
             "spatial_basis": "DETERMINISTIC_GIS"}],
        "site_specific_exceptions": [],
        "unresolved": [
            {"issue_id": "U-OFFICIAL-PLAN-DESIGNATION",
             "question": "Which Official Plan designation applies?",
             "materiality": "MATERIAL",
             "required_evidence": "The Official Plan land-use schedule."}],
        "result_status": "UNRESOLVED",
    }
    document.update(overrides.pop("document", {}))
    envelope = {"document": document,
                "retrieval": {"retrieved_at": "2026-09-13T00:00:00Z",
                              "runner_version": "toronto-gate01@2",
                              "authority_acquired": True,
                              "official_plan_acquired": True,
                              "overlays": []}}
    envelope["retrieval"].update(overrides.pop("retrieval", {}))
    return envelope


def _gate(envelope=None, error=None):
    def gate(address, *, reader=None):
        if error is not None:
            raise error
        return envelope if envelope is not None else _envelope()
    return gate


class TheFlagIsTheDeploymentDecision(unittest.TestCase):
    """A and B."""

    def test_it_defaults_off_in_configuration(self):
        import config
        self.assertFalse(config.BaseConfig.PLANNING_ZONING_LIVE_ENABLED)

    def test_it_is_not_inferred_from_the_environment(self):
        """Asserted against CODE, with the docstring stripped.

        A first version scanned the function's text for "DEBUG" and failed on the
        docstring sentence "Never from DEBUG, the hostname..." - a test of wording
        rather than of behaviour, and the sixth time this programme has made that
        exact mistake. AST gives the statements without the prose.
        """
        import ast
        tree = ast.parse(Path("routes/planning_zoning.py").read_text(
            encoding="utf-8"))
        function = next(node for node in ast.walk(tree)
                        if isinstance(node, ast.FunctionDef)
                        and node.name == "live_enabled")
        statements = [node for node in function.body
                      if not (isinstance(node, ast.Expr)
                              and isinstance(node.value, ast.Constant)
                              and isinstance(node.value.value, str))]
        code = " ".join(ast.dump(node) for node in statements)
        for ambient in ("DEBUG", "FLASK_ENV", "hostname", "TESTING",
                        "GEMINI_API_KEY", "environ"):
            self.assertNotIn(ambient, code,
                             "live must not be inferred from %s" % ambient)
        self.assertIn("PLANNING_ZONING_LIVE_ENABLED", code)


class TheLiveOrchestrationIsBounded(unittest.TestCase):
    """C, D, I, J - all hermetic."""

    def test_a_toronto_address_produces_a_live_classified_result(self):
        result = live.run_live(TORONTO, reader=object(), gate=_gate())
        self.assertEqual(result["outcome"], live.OUTCOME_OK)
        self.assertEqual(result["view"]["data_class"],
                         view.DATA_CLASS_LIVE)
        self.assertFalse(result["view"]["preview"])

    def test_an_address_outside_toronto_is_refused_by_name(self):
        def exploding(address, *, reader=None):
            raise AssertionError("the gate must not be called")
        result = live.run_live("100 Main Street, Mississauga, ON",
                               reader=object(), gate=exploding)
        self.assertEqual(result["outcome"],
                         live.OUTCOME_UNSUPPORTED_MUNICIPALITY)
        self.assertIn("Mississauga", result["message"])
        self.assertIsNone(result["document"])

    def test_toronto_local_names_are_not_mistaken_for_other_cities(self):
        """Etobicoke, North York and Scarborough ARE the City of Toronto."""
        for address in ("12 Somewhere Road, Etobicoke, ON",
                        "8 Example Street, North York, ON",
                        "5 Example Avenue, Scarborough, ON",
                        "5 Unnamed Lane"):
            self.assertTrue(live.municipality_check(address)["supported"],
                            address)

    def test_a_timeout_names_itself_and_fabricates_nothing(self):
        result = live.run_live(TORONTO, reader=object(),
                               gate=_gate(error=TimeoutError("read timed out")))
        self.assertEqual(result["outcome"], live.OUTCOME_SOURCE_TIMEOUT)
        self.assertIsNone(result["document"])
        self.assertNotIn("view", result)
        self.assertIn("could not be reached", result["message"])

    def test_every_transport_failure_has_its_own_name(self):
        import socket
        for error, expected in (
                (TimeoutError("x"), live.OUTCOME_SOURCE_TIMEOUT),
                (socket.timeout("x"), live.OUTCOME_SOURCE_TIMEOUT),
                (json.JSONDecodeError("Expecting value", "", 0),
                 live.OUTCOME_SOURCE_RESPONSE_INVALID),
                (ValueError("Expecting value: line 1"),
                 live.OUTCOME_SOURCE_RESPONSE_INVALID),
                (ConnectionError("refused"), live.OUTCOME_SOURCE_UNAVAILABLE),
                (OSError("down"), live.OUTCOME_SOURCE_UNAVAILABLE)):
            self.assertEqual(live.classify_failure(error), expected,
                             type(error).__name__)

    def test_an_unresolvable_address_is_not_a_result(self):
        envelope = _envelope()
        envelope["document"]["subject"]["identity_confidence"] = "UNRESOLVED"
        envelope["document"]["subject"]["parcel_identifier"] = None
        result = live.run_live("999999 Nowhere St, Toronto, ON",
                               reader=object(), gate=_gate(envelope))
        self.assertEqual(result["outcome"], live.OUTCOME_ADDRESS_UNRESOLVED)
        self.assertIsNone(result["document"])

    def test_a_partial_result_keeps_the_evidence_that_did_establish(self):
        """J. One source failing must not discard the zoning that succeeded."""
        envelope = _envelope(retrieval={
            "official_plan_acquired": False,
            "overlays": [{"layer_name": "Heritage District", "present": None,
                          "note": "1 undecided within 2000 m"}]})
        result = live.run_live(TORONTO, reader=object(), gate=_gate(envelope))
        self.assertEqual(result["outcome"], live.OUTCOME_OK)
        self.assertTrue(result["view"]["framework"]["statements"],
                        "established zoning must survive a failed sibling source")
        outcomes = {failure["outcome"] for failure in result["source_failures"]}
        self.assertIn(live.OUTCOME_AUTHORITY_UNRESOLVED, outcomes)
        self.assertIn(live.OUTCOME_SOURCE_RESPONSE_INVALID, outcomes)

    def test_no_options_are_invented_for_a_live_result(self):
        result = live.run_live(TORONTO, reader=object(), gate=_gate())
        self.assertEqual(result["view"]["options"], [])

    def test_the_measured_phases_are_reported(self):
        result = live.run_live(TORONTO, reader=object(), gate=_gate())
        for key in ("municipality_check_ms", "gate01_ms", "deterministic_ms",
                    "view_build_ms", "total_ms"):
            self.assertIn(key, result["timings"], key)

    def test_the_timing_reader_measures_without_changing_behaviour(self):
        calls = []

        def inner(url):
            calls.append(url)
            return b"{}"

        read, phases, counts = live.timing_reader(inner)
        self.assertEqual(read("https://gis.toronto.ca/x/cot_geospatial11/3/query"),
                         b"{}")
        self.assertEqual(calls, ["https://gis.toronto.ca/x/cot_geospatial11/3/query"])
        self.assertEqual(counts[live.PHASE_ZONING], 1)
        self.assertIn(live.PHASE_ZONING, phases)

    def test_a_reader_failure_still_propagates_through_the_timer(self):
        def inner(url):
            raise TimeoutError("slow")
        read, phases, _counts = live.timing_reader(inner)
        with self.assertRaises(TimeoutError):
            read("https://gis.toronto.ca/x/cot_geospatial27/101/query")
        self.assertIn(live.PHASE_ADDRESS, phases,
                      "a failed read still costs time and must be counted")

    def test_nothing_in_the_live_module_can_write_anything(self):
        """K, by source. Asserted against CALLS, not against the word "store" -
        the module's own docstring says it holds no store handle, and a prose
        scan would have matched that sentence."""
        source = Path("services/planning_live.py").read_text(encoding="utf-8")
        for write in ("open(", ".write(", "db.session", "CaseWorkspaceStore",
                      "save(", "commit(", "mkdir", "json.dump"):
            self.assertNotIn(write, source,
                             "%s would make a live result durable" % write)


class TheRouteHonoursTheFlag(unittest.TestCase):
    """B, E, F, G, H, L, N - through the real route, with the gate injected."""

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_pzlive_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False
        with self.flask_app.app_context():
            db.session.add(User(username="planner",
                                password_hash=generate_password_hash("x"),
                                role="user"))
            db.session.commit()

    def _client(self, live_enabled=False):
        self.flask_app.config["PLANNING_ZONING_LIVE_ENABLED"] = live_enabled
        client = self.flask_app.test_client()
        client.post("/login", data={"username": "planner", "password": "x"},
                    follow_redirects=True)
        return client

    def _submit(self, client, address=TORONTO, **extra):
        data = {"address": address}
        data.update(extra)
        return client.post("/planning-zoning/analyze",
                           data=data).get_data(as_text=True)

    def test_with_the_flag_off_the_development_state_behaviour_is_unchanged(self):
        client = self._client(live_enabled=False)
        page = client.get("/planning-zoning").get_data(as_text=True)
        self.assertIn("BACKEND_NOT_ROUTABLE", page)
        self.assertIn("not yet enabled on this environment", page)
        body = self._submit(client)
        self.assertIn("Entry checked", body)
        self.assertNotIn("Pre-Design Planning", body)

    def test_with_the_flag_on_the_intake_page_says_so(self):
        page = self._client(live_enabled=True).get(
            "/planning-zoning").get_data(as_text=True)
        self.assertIn("BACKEND_READY_TO_WIRE", page)
        self.assertIn("One property per request", page)

    def test_with_the_flag_on_a_toronto_address_renders_a_live_result(self):
        from unittest.mock import patch
        client = self._client(live_enabled=True)
        with patch("services.toronto_gate01.run", _gate()), \
                patch("services.toronto_planning_source.live_reader",
                      lambda **_kwargs: object()):
            body = self._submit(client)
        self.assertIn("Pre-Design Planning", body)
        self.assertIn("LIVE_ANALYSIS", body)
        self.assertNotIn("DEVELOPMENT PREVIEW", body)
        self.assertIn("TOR-PARCEL-TEST", body)

    def test_an_unresolved_live_result_still_renders_with_its_blocker_visible(self):
        from unittest.mock import patch
        client = self._client(live_enabled=True)
        with patch("services.toronto_gate01.run", _gate()), \
                patch("services.toronto_planning_source.live_reader",
                      lambda **_kwargs: object()):
            body = self._submit(client)
        self.assertIn("Analysis status: UNRESOLVED", body)
        self.assertIn("MATERIAL", body)
        self.assertIn("Blocks a governed planning conclusion", body)
        for unsupported in ("all clear", "no issues", "fully compliant",
                            "no constraints"):
            self.assertNotIn(unsupported, body.lower())

    def test_a_live_failure_is_rendered_on_the_intake_page_not_as_a_result(self):
        from unittest.mock import patch
        client = self._client(live_enabled=True)
        with patch("services.toronto_gate01.run",
                   _gate(error=TimeoutError("read timed out"))), \
                patch("services.toronto_planning_source.live_reader",
                      lambda **_kwargs: object()):
            body = self._submit(client)
        self.assertNotIn("Pre-Design Planning", body)
        self.assertIn("SOURCE_TIMEOUT", body)
        self.assertIn("could not be reached", body)

    def test_an_outside_toronto_address_is_refused_with_the_flag_on(self):
        client = self._client(live_enabled=True)
        body = self._submit(client, address="100 Main Street, Mississauga, ON")
        self.assertIn("Mississauga", body)
        self.assertNotIn("Pre-Design Planning", body)

    def test_the_fixture_route_keeps_its_banner_even_with_the_flag_on(self):
        """E and F. The banner reports the DATA, never the environment."""
        client = self._client(live_enabled=True)
        body = client.get("/planning-zoning/result").get_data(as_text=True)
        self.assertIn("DEVELOPMENT PREVIEW", body)
        self.assertIn("DEVELOPMENT_FIXTURE", body)
        self.assertNotIn("LIVE_ANALYSIS", body)

    def test_batch_never_reaches_the_live_path(self):
        """L."""
        from unittest.mock import patch
        client = self._client(live_enabled=True)
        with patch("services.toronto_gate01.run") as gate:
            body = client.post("/planning-zoning/analyze", data={
                "mode": "batch",
                "addresses": "%s\n250 Front Street West, Toronto, ON" % TORONTO,
            }).get_data(as_text=True)
        gate.assert_not_called()
        self.assertIn("2 address(es) prepared", body)
        self.assertNotIn("Pre-Design Planning", body)

    def test_a_live_request_creates_no_record_of_any_kind(self):
        """K, through the route."""
        from unittest.mock import patch
        from models import db
        client = self._client(live_enabled=True)
        before = sorted(p.name for p in self.tmp_dir.rglob("*") if p.is_file())
        with patch("services.toronto_gate01.run", _gate()), \
                patch("services.toronto_planning_source.live_reader",
                      lambda **_kwargs: object()):
            self._submit(client)
        after = sorted(p.name for p in self.tmp_dir.rglob("*") if p.is_file())
        self.assertEqual(before, after, "a live result must leave no file")
        with self.flask_app.app_context():
            from sqlalchemy import inspect as sa_inspect
            for table in sa_inspect(db.engine).get_table_names():
                if table == "users":
                    continue
                count = db.session.execute(
                    db.text("SELECT COUNT(*) FROM %s" % table)).scalar()
                self.assertEqual(count, 0, "%s gained a row" % table)

    def test_no_owner_programme_is_requested_on_the_live_path(self):
        from unittest.mock import patch
        import re as _re
        client = self._client(live_enabled=True)
        with patch("services.toronto_gate01.run", _gate()), \
                patch("services.toronto_planning_source.live_reader",
                      lambda **_kwargs: object()):
            body = self._submit(client)
        controls = " ".join(_re.findall(r'<(?:input|select|textarea)[^>]*>', body))
        for premature in ("bedroom", "unit_count", "budget", "room_count"):
            self.assertNotIn('name="%s"' % premature, controls)

    def test_the_working_state_exists_for_the_wait(self):
        """Section 9. A live Toronto request is a long round trip."""
        page = self._client(live_enabled=True).get(
            "/planning-zoning").get_data(as_text=True)
        self.assertIn('data-ui-ref="planning-zoning.working"', page)
        self.assertIn("Checking property and planning sources", page)

    def test_the_existing_pages_remain_intact(self):
        """N."""
        client = self._client(live_enabled=False)
        for path in ("/planning-zoning", "/planning-zoning?mode=batch",
                     "/planning-zoning/result"):
            self.assertEqual(client.get(path).status_code, 200, path)

    def test_the_reserved_benchmark_address_appears_nowhere(self):
        sealed = "Roch" + "elle"
        for name in ("services/planning_live.py",
                     "tests/test_planning_live_route_01.py",
                     "routes/planning_zoning.py"):
            self.assertNotIn(sealed, Path(name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
