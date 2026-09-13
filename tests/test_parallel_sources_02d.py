"""CLAUDE-PARALLEL-SOURCES-02D - parallelize waiting, never dependencies.

After 02C the single-address path was 15.2-18.1 s, of which ~4.7-5.3 s was our
own arithmetic and the rest was waiting on the City: 29 of 37 reads, issued one
after another, for ten overlay layers and a heritage register that have nothing
to do with each other.

    THE ONLY READS RUN CONCURRENTLY ARE THE ONES WHOSE INDEPENDENCE IS A DATA
    FACT, not a coincidence of position in the function.

Each overlay and the heritage register need the subject PARCEL and nothing else.
Address resolution, `zoning_at` and authority retrieval stay sequential, and the
reasons are not performance reasons: identity is the prerequisite for every
spatial question; the by-law and the exception are CHOSEN from the zone's own
attributes; and fetching an authority before applicability is established is how
the wrong by-law gets cited.

WHAT THESE TESTS DEFEND HARDEST is that scheduling changed and meaning did not -
same findings, same tokens, same ORDER (statement ids derive from overlay
position), same provenance - and that one slow or failing source cannot take the
others down with it.
"""
from __future__ import annotations

import ast
import inspect
import io
import json
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from services import planning_live as live
from services import toronto_gate01
from services import toronto_planning_source as source

CAPTURE = (r"C:\Users\info\AppData\Local\Temp\claude"
           r"\C--Archiosk-Research-archiosk"
           r"\eaae86eb-ca55-4f6b-a899-6fa7adebc222\scratchpad"
           r"\spatial_capture.json")

ADDRESS = "573 Shuter Street, Toronto, ON"


def _finding(binding, *_args, **_kwargs):
    """A minimal successful overlay finding for the named binding."""
    return {"layer_name": binding[2], "present": False, "token": None,
            "absence_established": True, "polygons_in_envelope": 0,
            "computed_outside": 0, "undecided": 0, "overlapping": 0,
            "witness_geometry": None, "witness_token": None,
            "envelope_metres": 2000.0, "note": "test"}


class TheDependencyGraphIsRespected(unittest.TestCase):
    """A. Proven from the code, not asserted in prose."""

    def setUp(self):
        self.source_text = inspect.getsource(toronto_gate01.gather)
        self.tree = ast.parse(inspect.getsource(toronto_gate01))

    def _pool_body(self):
        """The statements lexically inside the ThreadPoolExecutor block."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.With):
                if "ThreadPoolExecutor" in ast.unparse(node.items[0].context_expr):
                    return ast.unparse(node)
        return ""

    def test_the_independent_reads_are_the_ones_submitted(self):
        body = self._pool_body()
        self.assertTrue(body, "gather must schedule through a bounded pool")
        self.assertIn("read_overlay", body)
        self.assertIn("read_heritage_register", body)

    def test_address_resolution_is_not_parallelized(self):
        """Property identity is the prerequisite for every spatial question, and
        the ordering semantics of its four reads are not proven."""
        self.assertNotIn("resolve_address", self._pool_body())

    def test_zoning_is_not_parallelized(self):
        """The by-law and the exception are CHOSEN from its attributes."""
        self.assertNotIn("zoning_at", self._pool_body())

    def test_authority_retrieval_is_not_parallelized(self):
        """Fetching a source before applicability is established is how the
        wrong instrument gets cited."""
        body = self._pool_body()
        for authority_call in ("acquire_zoning_bylaw", "acquire_official_plan",
                               "acquire_exception"):
            self.assertNotIn(authority_call, body)

    def test_zoning_is_still_read_before_the_authority_it_selects(self):
        text = self.source_text
        self.assertLess(text.index("zoning_at("), text.index("acquire_zoning_bylaw("))
        self.assertLess(text.index("resolve_address("), text.index("zoning_at("))

    def test_the_exception_is_still_conditional_on_the_zone(self):
        self.assertIn('attributes.get("ZN_EXCPTN") == "Y"', self.source_text)

    def test_each_task_gets_its_own_cache(self):
        """A dict mutated from several threads is a race, and the shared cache is
        keyed by (service, layer_id) so it never shared anything across layers.

        Read from the AST of the two closures actually submitted to the pool -
        the `cache={}` lives in THEIR bodies, not lexically inside the `with`."""
        for name in ("read_overlay", "read_heritage_register"):
            closure = _nested_function(self.tree, "gather", name)
            self.assertIsNotNone(closure, name)
            caches = [keyword for call in ast.walk(closure)
                      if isinstance(call, ast.Call)
                      for keyword in call.keywords
                      if keyword.arg == "cache"]
            self.assertTrue(caches, "%s must pass a cache explicitly" % name)
            for keyword in caches:
                self.assertIsInstance(keyword.value, ast.Dict, name)
                self.assertEqual(keyword.value.keys, [], "a FRESH dict, per task")


class ConcurrencyIsBounded(unittest.TestCase):
    """B and H."""

    def test_a_cap_exists_and_is_small(self):
        cap = toronto_gate01.MAX_CONCURRENT_SOURCE_READS
        self.assertIsInstance(cap, int)
        self.assertGreater(cap, 1)
        self.assertLessEqual(cap, 12, "a municipal service is not our infrastructure")

    def test_the_pool_is_created_with_the_cap_and_never_unbounded(self):
        body = inspect.getsource(toronto_gate01.gather)
        self.assertIn("max_workers=MAX_CONCURRENT_SOURCE_READS", body)
        self.assertNotIn("max_workers=None", body)

    def test_observed_concurrency_never_exceeds_the_cap(self):
        peak = {"value": 0, "inflight": 0}
        lock = threading.Lock()

        def slow_finding(binding, *_args, **_kwargs):
            with lock:
                peak["inflight"] += 1
                peak["value"] = max(peak["value"], peak["inflight"])
            try:
                time.sleep(0.05)
                return _finding(binding)
            finally:
                with lock:
                    peak["inflight"] -= 1

        with patch.object(source, "resolve_address", _resolved), \
                patch.object(source, "zoning_at", lambda *a, **k: _zoning()), \
                patch.object(source, "overlay_finding", slow_finding), \
                patch.object(source, "heritage_register_near",
                             lambda *a, **k: {"checked": True, "properties": []}), \
                patch.object(source, "acquire_zoning_bylaw", lambda **k: None), \
                patch.object(source, "acquire_official_plan", lambda **k: None):
            toronto_gate01.gather(ADDRESS, reader=object())
        self.assertGreater(peak["value"], 1, "reads must actually overlap")
        self.assertLessEqual(peak["value"],
                             toronto_gate01.MAX_CONCURRENT_SOURCE_READS)


def _resolved(*_args, **_kwargs):
    return {"parcel_count": 1, "parcel_identifier": "TOR-PARCEL-TEST",
            "geometry": {"type": "Polygon",
                         "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
            "point": {"x": 0.5, "y": 0.5}, "crs": "EPSG:3857",
            "source": "cot_geospatial27/36 (Property Boundary)"}


def _zoning():
    return {"present": True, "attributes": {"ZN_ZONE": "CR", "ZN_EXCPTN": "N"},
            "geometry": None, "layer": {"name": "Zoning Area"}}


class OrderAndIdentitySurviveConcurrency(unittest.TestCase):
    """C and F."""

    def _gather_with(self, overlay):
        with patch.object(source, "resolve_address", _resolved), \
                patch.object(source, "zoning_at", lambda *a, **k: _zoning()), \
                patch.object(source, "overlay_finding", overlay), \
                patch.object(source, "heritage_register_near",
                             lambda *a, **k: {"checked": True, "properties": []}), \
                patch.object(source, "acquire_zoning_bylaw", lambda **k: None), \
                patch.object(source, "acquire_official_plan", lambda **k: None):
            return toronto_gate01.gather(ADDRESS, reader=object())

    def test_findings_come_back_in_the_declared_layer_order(self):
        gathered = self._gather_with(_finding)
        self.assertEqual([f["layer_name"] for f in gathered["overlays"]],
                         [binding[2] for binding in source.OVERLAY_LAYERS])

    def test_order_holds_when_completion_order_is_reversed(self):
        """The whole risk of a fan-out: results arrive in whatever order the
        City answers, and statement ids derive from POSITION."""
        total = len(source.OVERLAY_LAYERS)
        positions = {binding[2]: index
                     for index, binding in enumerate(source.OVERLAY_LAYERS)}

        def reversed_speed(binding, *_args, **_kwargs):
            # The LAST layer answers first, the first answers last.
            time.sleep(0.002 * (total - positions[binding[2]]))
            return _finding(binding)

        gathered = self._gather_with(reversed_speed)
        self.assertEqual([f["layer_name"] for f in gathered["overlays"]],
                         [binding[2] for binding in source.OVERLAY_LAYERS])

    def test_every_finding_belongs_to_the_binding_that_produced_it(self):
        """D-identity: a result may never be attributed to the wrong layer."""
        def tagged(binding, *_args, **_kwargs):
            finding = _finding(binding)
            finding["note"] = "produced-for:%s" % binding[2]
            return finding

        gathered = self._gather_with(tagged)
        for finding in gathered["overlays"]:
            self.assertEqual(finding["note"],
                             "produced-for:%s" % finding["layer_name"])

    def test_no_finding_is_lost_or_duplicated(self):
        gathered = self._gather_with(_finding)
        names = [f["layer_name"] for f in gathered["overlays"]]
        self.assertEqual(len(names), len(source.OVERLAY_LAYERS))
        self.assertEqual(len(names), len(set(names)))


class OneFailureDoesNotCancelTheOthers(unittest.TestCase):
    """D and E. No all-or-nothing fan-out."""

    def _gather_failing(self, error, failing="Heritage District"):
        def sometimes(binding, *_args, **_kwargs):
            if binding[2] == failing:
                raise error
            return _finding(binding)

        with patch.object(source, "resolve_address", _resolved), \
                patch.object(source, "zoning_at", lambda *a, **k: _zoning()), \
                patch.object(source, "overlay_finding", sometimes), \
                patch.object(source, "heritage_register_near",
                             lambda *a, **k: {"checked": True, "properties": []}), \
                patch.object(source, "acquire_zoning_bylaw", lambda **k: None), \
                patch.object(source, "acquire_official_plan", lambda **k: None):
            return toronto_gate01.gather(ADDRESS, reader=object())

    def test_a_timeout_in_one_layer_leaves_the_rest_established(self):
        gathered = self._gather_failing(TimeoutError("read timed out"))
        findings = {f["layer_name"]: f for f in gathered["overlays"]}
        self.assertEqual(len(findings), len(source.OVERLAY_LAYERS))
        failed = findings["Heritage District"]
        self.assertIsNone(failed["present"])
        self.assertFalse(failed["absence_established"])
        self.assertIn("TimeoutError", failed["note"])
        for name, finding in findings.items():
            if name != "Heritage District":
                self.assertTrue(finding["absence_established"], name)

    def test_each_failure_class_keeps_its_own_outcome(self):
        for error in (TimeoutError("t"), ConnectionError("c"),
                      ValueError("Expecting value"), RuntimeError("?")):
            gathered = self._gather_failing(error)
            findings = {f["layer_name"]: f for f in gathered["overlays"]}
            self.assertIn(type(error).__name__,
                          findings["Heritage District"]["note"])

    def test_a_failing_heritage_register_does_not_affect_overlays(self):
        def boom(*_args, **_kwargs):
            raise TimeoutError("register timed out")

        with patch.object(source, "resolve_address", _resolved), \
                patch.object(source, "zoning_at", lambda *a, **k: _zoning()), \
                patch.object(source, "overlay_finding", _finding), \
                patch.object(source, "heritage_register_near", boom), \
                patch.object(source, "acquire_zoning_bylaw", lambda **k: None), \
                patch.object(source, "acquire_official_plan", lambda **k: None):
            gathered = toronto_gate01.gather(ADDRESS, reader=object())
        self.assertFalse(gathered["heritage_register"]["checked"])
        self.assertIn("TimeoutError", gathered["heritage_register"]["reason"])
        self.assertEqual(len(gathered["overlays"]), len(source.OVERLAY_LAYERS))

    def test_every_layer_failing_still_produces_one_finding_each(self):
        def always(binding, *_args, **_kwargs):
            raise ConnectionError("the City is unreachable")

        with patch.object(source, "resolve_address", _resolved), \
                patch.object(source, "zoning_at", lambda *a, **k: _zoning()), \
                patch.object(source, "overlay_finding", always), \
                patch.object(source, "heritage_register_near",
                             lambda *a, **k: {"checked": True, "properties": []}), \
                patch.object(source, "acquire_zoning_bylaw", lambda **k: None), \
                patch.object(source, "acquire_official_plan", lambda **k: None):
            gathered = toronto_gate01.gather(ADDRESS, reader=object())
        self.assertEqual(len(gathered["overlays"]), len(source.OVERLAY_LAYERS))
        for finding in gathered["overlays"]:
            self.assertIsNone(finding["present"])


class NothingForbiddenWasIntroduced(unittest.TestCase):
    """Sections 13, 14 and 17.

    Asserted against the IMPORT GRAPH and the AST, never against the words in
    the file. This programme has now produced seven prose-scan false positives,
    every one of them a test matching a docstring that was explaining the very
    thing the test was banning.
    """

    MODULES = ("services/toronto_gate01.py",
               "services/toronto_planning_source.py",
               "services/deterministic_spatial.py")

    def test_no_caching_machinery_was_imported(self):
        for path in self.MODULES:
            imported = _imported_names(path)
            for banned in ("functools", "shelve", "pickle", "diskcache",
                           "sqlite3", "redis"):
                self.assertNotIn(banned, imported, "%s in %s" % (banned, path))

    def test_nothing_is_memoised_by_decorator(self):
        for path in self.MODULES:
            for decorator in _decorator_names(path):
                self.assertNotIn("cache", decorator.lower(), path)
                self.assertNotIn("memo", decorator.lower(), path)

    def test_no_module_level_mutable_store_was_introduced(self):
        """A cache that outlives a request is a cache whatever it is called."""
        for path in self.MODULES:
            tree = ast.parse(Path(path).read_text(encoding="utf-8"))
            for node in tree.body:
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                value = node.value
                if isinstance(value, (ast.Dict, ast.List, ast.Set)) and (
                        getattr(value, "keys", None) == [] or
                        getattr(value, "elts", None) == []):
                    targets = ast.unparse(node)
                    self.fail("empty module-level container in %s: %s"
                              % (path, targets))

    def test_the_spatial_engine_is_untouched_by_this_tranche(self):
        from services import deterministic_spatial as spatial
        self.assertEqual(spatial.ENGINE, "archiosk-exact-ring@3")
        for name in ("ring_y_index", "point_in_ring_indexed", "ring_band",
                     "prepare_parts", "token_matches", "relate"):
            self.assertTrue(hasattr(spatial, name), name)

    def test_scheduling_lives_in_the_runner_not_the_reader(self):
        """`toronto_planning_source` stays a pure reader library, so 02C's guard
        against a second spatial implementation there keeps its meaning."""
        imported = _imported_names("services/toronto_planning_source.py")
        for scheduling in ("concurrent", "concurrent.futures", "asyncio",
                           "threading", "multiprocessing"):
            self.assertNotIn(scheduling, imported)

    def test_the_runner_is_the_only_place_that_schedules(self):
        imported = _imported_names("services/toronto_gate01.py")
        self.assertIn("concurrent.futures", imported)
        for heavier in ("asyncio", "multiprocessing"):
            self.assertNotIn(heavier, imported)

    def test_timeouts_were_not_relaxed(self):
        """Concurrency is not a licence to wait longer per read."""
        signature = inspect.signature(source.live_reader)
        self.assertEqual(signature.parameters["timeout"].default, 45)

    def test_no_retry_loop_was_introduced(self):
        """A failed source is a FINDING, not something to ask the City again for."""
        tree = ast.parse(Path("services/toronto_gate01.py").read_text(encoding="utf-8"))
        gather = _function(tree, "gather")
        self.assertIsNotNone(gather)
        self.assertEqual([], [node for node in ast.walk(gather)
                              if isinstance(node, ast.While)])
        # The one loop that submits work iterates the declared layers exactly once.
        submissions = [node for node in ast.walk(gather)
                       if isinstance(node, ast.Call)
                       and ast.unparse(node.func).endswith("submit")]
        self.assertEqual(len(submissions), 2, "overlays plus heritage, no more")


class TheMeasurementSurvivedTheConcurrency(unittest.TestCase):
    """02D broke a derived figure, and this is the fix under test.

    `deterministic_ms` was `gate01_ms - sum(read durations)`. That was exact
    while the reads were serial. Once six run at once the sum exceeds the
    elapsed time it is subtracted from, so the figure went to zero - and because
    the subtraction was clamped with `max(0.0, ...)`, it would have reported
    ZERO DETERMINISTIC WORK as though that were an answer.
    """

    def test_the_union_of_two_disjoint_spans_is_their_sum(self):
        self.assertAlmostEqual(
            live.busy_millis([(0.0, 1.0), (2.0, 3.0)]), 2000.0, places=3)

    def test_the_union_of_two_identical_spans_is_one_of_them(self):
        self.assertAlmostEqual(
            live.busy_millis([(0.0, 1.0), (0.0, 1.0)]), 1000.0, places=3)

    def test_a_span_wholly_inside_another_adds_nothing(self):
        self.assertAlmostEqual(
            live.busy_millis([(0.0, 5.0), (1.0, 2.0)]), 5000.0, places=3)

    def test_overlapping_spans_merge_and_a_gap_does_not(self):
        # 0-2 and 1-3 merge to 0-3; 5-6 is separate. 3s + 1s.
        self.assertAlmostEqual(
            live.busy_millis([(1.0, 3.0), (0.0, 2.0), (5.0, 6.0)]),
            4000.0, places=3)

    def test_touching_spans_do_not_double_count_the_boundary(self):
        self.assertAlmostEqual(
            live.busy_millis([(0.0, 1.0), (1.0, 2.0)]), 2000.0, places=3)

    def test_no_spans_is_no_time(self):
        self.assertEqual(live.busy_millis([]), 0.0)

    def test_input_order_does_not_change_the_answer(self):
        spans = [(0.0, 2.0), (1.0, 3.0), (5.0, 6.0), (5.5, 9.0)]
        answer = live.busy_millis(spans)
        for rotation in range(len(spans)):
            rotated = spans[rotation:] + spans[:rotation]
            self.assertAlmostEqual(live.busy_millis(rotated), answer, places=6)

    def test_the_union_never_exceeds_the_sum(self):
        spans = [(0.0, 2.0), (1.0, 3.0), (0.5, 1.5)]
        summed = sum(finish - start for start, finish in spans) * 1000.0
        self.assertLessEqual(live.busy_millis(spans), summed)

    def test_the_reader_reports_peak_concurrency_and_failures(self):
        def inner(url):
            if "fail" in url:
                raise TimeoutError("slow")
            return b"{}"

        read, _phases, _calls, meter = live.timing_reader(inner)
        read("https://gis.toronto.ca/x/cot_geospatial11/3/query")
        with self.assertRaises(TimeoutError):
            read("https://gis.toronto.ca/fail/cot_geospatial11/9/query")
        self.assertEqual(meter["reads"], 2)
        self.assertEqual(meter["failed"], 1, "a failed read is still a read")
        self.assertEqual(meter["max_concurrent"], 1)
        self.assertEqual(len(meter["spans"]), 2)

    def test_the_meter_is_safe_to_mutate_from_several_threads(self):
        read, _phases, _calls, meter = live.timing_reader(
            lambda url: time.sleep(0.02) or b"{}")
        threads = [threading.Thread(
            target=read,
            args=("https://gis.toronto.ca/x/cot_geospatial11/%d/query" % n,))
            for n in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(meter["reads"], 8)
        self.assertEqual(len(meter["spans"]), 8)
        self.assertGreater(meter["max_concurrent"], 1)

    def test_deterministic_time_is_derived_from_the_union_not_the_sum(self):
        """The whole point: with overlap, the sum would have zeroed it."""
        import services.toronto_gate01 as runner

        def gate(address, *, reader, **_kwargs):
            with __import__("concurrent.futures", fromlist=["x"]) \
                    .ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(reader, [
                    "https://gis.toronto.ca/x/cot_geospatial11/%d/query" % n
                    for n in range(8)]))
            time.sleep(0.15)          # our own arithmetic, after the network
            return _governed_stub()

        result = live.run_live("573 Shuter Street, Toronto, ON",
                              reader=lambda url: time.sleep(0.05) or b"{}",
                              gate=gate)
        timings = result["timings"]
        self.assertEqual(timings["network_reads"], 8)
        self.assertEqual(timings["max_concurrent_reads"], 4)
        self.assertGreater(timings["read_overlap_factor"], 1.5,
                           "the reads must actually have overlapped")
        self.assertGreater(timings["network_read_ms"], timings["network_busy_ms"])
        self.assertGreater(timings["deterministic_ms"], 100.0,
                           "the 150 ms of arithmetic must survive the subtraction")
        self.assertLessEqual(timings["network_busy_ms"], timings["gate01_ms"] + 1.0)
        self.assertEqual(runner.MAX_CONCURRENT_SOURCE_READS, 6)


def _governed_stub():
    """The smallest Gate-01 outcome `run_live` will accept as resolved."""
    return {
        "document": {
            "contract": "GO-PDZ-1.0-ONEPAGE", "gate": "GATE_01_ADDRESS_ONLY_ENVELOPE",
            "subject": {"address": "573 Shuter Street, Toronto, ON",
                        "identity_confidence": "HIGH",
                        "parcel_identifier": "TOR-PARCEL-TEST",
                        "municipality": "City of Toronto"},
            "authorities": [], "statements": [], "unresolved": [],
            "site_specific_exceptions": [], "spatial_tokens": {},
            "result_status": "UNRESOLVED"},
        "validation": {"valid": True, "violations": []},
        "spatial_tokens": {},
        "retrieval": {"runner_version": "toronto-gate01@3"}}


def _imported_names(path):
    """Every module named by an import in the file, dotted form included."""
    names = set()
    for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
                for alias in node.names:
                    names.add("%s.%s" % (node.module, alias.name))
    return names


def _decorator_names(path):
    for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for decorator in node.decorator_list:
                yield ast.unparse(decorator)


def _function(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _nested_function(tree, outer, inner):
    enclosing = _function(tree, outer)
    return _function(enclosing, inner) if enclosing is not None else None


class TheRealSubjectIsUnchanged(unittest.TestCase):
    """G, against the captured municipal responses."""

    #: (present, absence_established, polygons_in_envelope, computed_outside,
    #:  undecided, overlapping) as they stood on the frozen 02C tree.
    FROZEN_OVERLAYS = {
        "Zoning Height Overlay": (True, False, None, None, None, None),
        "Zoning Lot Coverage Overlay": (False, True, 0, 0, 0, 0),
        "Zoning Policy Area Overlay": (True, False, None, None, None, None),
        "Zoning Building Setback Overlay": (True, False, None, None, None, None),
        "Zoning Not Part of This Bylaw": (False, False, 177, 176, 1, 0),
        "Secondary Plan": (True, False, None, None, None, None),
        "Site and Area Specific Policy": (False, True, 30, 30, 0, 0),
        "Heritage District": (False, True, 9, 9, 0, 0),
        "Natural Heritage System (polygon)": (False, True, 1, 1, 0, 0),
        "Major Transit Station Area": (False, True, 14, 14, 0, 0),
    }
    FROZEN_TOKENS = {
        "zoning_area": "INSIDE",
        "overlay:Zoning Height Overlay": "INSIDE",
        "overlay:Zoning Policy Area Overlay": "INSIDE",
        "overlay:Zoning Building Setback Overlay": "INSIDE",
        "overlay:Secondary Plan": "INSIDE",
        "absence:Site and Area Specific Policy": "OUTSIDE",
        "absence:Heritage District": "OUTSIDE",
        "absence:Natural Heritage System (polygon)": "OUTSIDE",
        "absence:Major Transit Station Area": "OUTSIDE",
    }

    def setUp(self):
        if not Path(CAPTURE).exists():
            self.skipTest("the municipal capture is a scratchpad artefact")
        self.responses = json.loads(io.open(CAPTURE, encoding="utf-8").read())

    def _replay(self, url):
        if url not in self.responses:
            raise AssertionError("replay miss: %s" % url)
        return self.responses[url].encode("utf-8")

    def test_the_whole_gate_01_result_is_unchanged(self):
        outcome = toronto_gate01.run(ADDRESS, reader=self._replay)
        document = outcome["document"]
        self.assertEqual(document["subject"]["identity_confidence"], "HIGH")
        self.assertEqual(document["subject"]["parcel_identifier"],
                         "TOR-PARCEL-5439471")
        self.assertEqual(document["result_status"], "UNRESOLVED")
        self.assertEqual([a["authority_id"] for a in document["authorities"]],
                         ["TOR-BYLAW-569-2013", "TOR-OFFICIAL-PLAN"])
        self.assertEqual(
            [(u["issue_id"], u["materiality"]) for u in document["unresolved"]],
            [("U-OFFICIAL-PLAN-DESIGNATION", "MATERIAL"),
             ("U-BYLAW-PROVISION-TEXT", "MINOR")])

        findings = {f["layer_name"]: f
                    for f in outcome["retrieval"]["overlays"]}
        for name, expected in self.FROZEN_OVERLAYS.items():
            with self.subTest(layer=name):
                finding = findings[name]
                self.assertEqual(
                    (finding.get("present"), finding.get("absence_established"),
                     finding.get("polygons_in_envelope"),
                     finding.get("computed_outside"), finding.get("undecided"),
                     finding.get("overlapping")),
                    expected)

        tokens = outcome["spatial_tokens"]
        self.assertEqual(set(tokens), set(self.FROZEN_TOKENS))
        for name, relation in self.FROZEN_TOKENS.items():
            with self.subTest(token=name):
                self.assertEqual(tokens[name]["spatial_relation"], relation)
                self.assertTrue(
                    (tokens[name].get("provenance") or {}).get("layer_geometry_id"),
                    "provenance must survive concurrency")

    def test_the_overlay_order_matches_the_declared_bindings(self):
        outcome = toronto_gate01.run(ADDRESS, reader=self._replay)
        self.assertEqual(
            [f["layer_name"] for f in outcome["retrieval"]["overlays"]],
            [binding[2] for binding in source.OVERLAY_LAYERS])

    def test_the_read_count_did_not_change(self):
        """Scheduling, not strategy: the same reads, differently ordered."""
        reads = []

        def counting(url):
            reads.append(url)
            return self._replay(url)

        toronto_gate01.run(ADDRESS, reader=counting)
        self.assertEqual(len(reads), 37)


if __name__ == "__main__":
    unittest.main()
