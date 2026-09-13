"""CLAUDE-SPATIAL-DEDUPE-02A - do not compute the same relation twice.

    MEASURED: 573 Shuter Street, one live request
    deterministic spatial      66,829 ms
    of which ONE polygon       ~63,400 ms  (281,023 vertices, 557 rings)
    related                    TWICE, for the same answer: OUTSIDE

`toronto_planning_source.overlay_finding` proved the absence, kept the witness
GEOMETRY and threw the ANSWER away; `go_pdz_lifecycle.spatial_context` then
derived that same answer again from the geometry alone. 31.7 s to learn something
already known.

REUSE IS PROVEN, NOT ASSUMED. `deterministic_spatial.token_matches` compares the
two geometry hashes the token already carries, both CRSs, both source labels, the
version, the operation and the engine. A token is reused only when every input
that can change the answer is provably identical; a subject that resolved to
several parcels, or a conflicting-layer condition, falls through and recomputes,
because those make `relate` answer AMBIGUOUS for reasons geometry cannot see.

NO GEOMETRY MATHEMATICS CHANGED BY THIS TRANCHE. Not one line of the ring,
crossing, distance or containment code was touched here; the saving comes entirely
from not asking twice. CLAUDE-SPATIAL-PREFILTER-02B later changed that code
deliberately, under its own differential equivalence proof - so read this sentence
as a statement about 02A, not as a current claim about the engine.
"""
from __future__ import annotations

import unittest

from services import deterministic_spatial as spatial
from services import go_pdz_lifecycle as lifecycle

#: A small square, and a larger square containing it. Real coordinates in the
#: engine's own working frame; nothing here needs to be a municipal polygon.
INNER = {"type": "Polygon", "coordinates": [[[0.0, 0.0], [10.0, 0.0],
                                             [10.0, 10.0], [0.0, 10.0],
                                             [0.0, 0.0]]]}
OUTER = {"type": "Polygon", "coordinates": [[[-100.0, -100.0], [200.0, -100.0],
                                             [200.0, 200.0], [-100.0, 200.0],
                                             [-100.0, -100.0]]]}
FAR = {"type": "Polygon", "coordinates": [[[900.0, 900.0], [910.0, 900.0],
                                           [910.0, 910.0], [900.0, 910.0],
                                           [900.0, 900.0]]]}

SUBJECT = {"crs": "EPSG:3857", "geometry": INNER}
LAYER = {"crs": "EPSG:3857", "geometry": OUTER}
ARGUMENTS = {"subject_source": "parcel layer", "layer_source": "zone layer",
             "layer_version": "By-law 569-2013"}


def _identity(**overrides):
    identity = {"_crs": "EPSG:3857", "_geometry": INNER,
                "_geometry_source": "parcel layer", "_parcel_count": 1}
    identity.update(overrides)
    return identity


def _layers(token=None, **overrides):
    layer = {"crs": "EPSG:3857", "geometry": OUTER, "source": "zone layer",
             "version": "By-law 569-2013"}
    if token is not None:
        layer["precomputed_token"] = token
    layer.update(overrides)
    return {"zone": layer}


class TokenMatchesProvesIdentity(unittest.TestCase):
    """Section 3. Reuse by proof, never by name, proximity or call order."""

    def setUp(self):
        self.token = spatial.relate(SUBJECT, LAYER, **ARGUMENTS)

    def test_the_same_inputs_match(self):
        self.assertTrue(spatial.token_matches(
            self.token, subject=SUBJECT, layer=LAYER, **ARGUMENTS))

    def test_a_different_layer_geometry_does_not_match(self):
        self.assertFalse(spatial.token_matches(
            self.token, subject=SUBJECT,
            layer={"crs": "EPSG:3857", "geometry": FAR}, **ARGUMENTS))

    def test_a_different_subject_geometry_does_not_match(self):
        self.assertFalse(spatial.token_matches(
            self.token, subject={"crs": "EPSG:3857", "geometry": FAR},
            layer=LAYER, **ARGUMENTS))

    def test_a_different_crs_does_not_match(self):
        self.assertFalse(spatial.token_matches(
            self.token, subject={"crs": "EPSG:4326", "geometry": INNER},
            layer=LAYER, **ARGUMENTS))

    def test_a_different_source_label_does_not_match(self):
        """The label reaches the governed document, so it is part of identity."""
        self.assertFalse(spatial.token_matches(
            self.token, subject=SUBJECT, layer=LAYER,
            **dict(ARGUMENTS, layer_source="a different layer")))

    def test_a_different_version_does_not_match(self):
        self.assertFalse(spatial.token_matches(
            self.token, subject=SUBJECT, layer=LAYER,
            **dict(ARGUMENTS, layer_version="an amendment")))

    def test_a_transformation_difference_does_not_match(self):
        self.assertFalse(spatial.token_matches(
            self.token, subject=SUBJECT, layer=LAYER,
            upstream_transformation="EPSG:26917 -> EPSG:3857", **ARGUMENTS))

    def test_multiple_parcels_never_reuses(self):
        """`relate` answers AMBIGUOUS for a reason geometry cannot see."""
        self.assertFalse(spatial.token_matches(
            self.token, subject=SUBJECT, layer=LAYER,
            subject_parcel_count=2, **ARGUMENTS))

    def test_a_conflicting_layer_condition_never_reuses(self):
        self.assertFalse(spatial.token_matches(
            self.token, subject=SUBJECT, layer=LAYER,
            conflicting_layers=True, **ARGUMENTS))

    def test_a_foreign_or_forged_token_never_matches(self):
        for forged in (None, {}, "OUTSIDE", {"spatial_relation": "OUTSIDE"},
                       {"engine": "somebody-elses-engine",
                        "provenance": self.token.get("provenance")},
                       dict(self.token, engine="archiosk-exact-ring@2")):
            self.assertFalse(spatial.token_matches(
                forged, subject=SUBJECT, layer=LAYER, **ARGUMENTS), forged)

    def test_two_missing_geometries_are_not_the_same_geometry(self):
        empty = {"crs": "EPSG:3857", "geometry": None}
        token = spatial.relate(empty, empty, **ARGUMENTS)
        self.assertFalse(spatial.token_matches(token, subject=empty, layer=empty,
                                               **ARGUMENTS),
                         "reuse by coincidence is not reuse by identity")

    def test_it_performs_no_geometry(self):
        """A comparison of identifiers, not a second computation."""
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(spatial.token_matches))
        called = {node.func.id for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        for geometry_function in ("_parts", "_all_rings", "_point_in_parts",
                                  "_any_crossing", "_min_distance_to_polygon",
                                  "_ring_is_valid", "relate"):
            self.assertNotIn(geometry_function, called)


class SpatialContextDoesNotRelateTwice(unittest.TestCase):
    """Section 5. The call-count regression, which is the point of the tranche."""

    def _count(self, layers, identity=None):
        calls = []
        real = spatial.relate

        def counted(subject, layer, **kwargs):
            calls.append(kwargs.get("layer_source"))
            return real(subject, layer, **kwargs)

        spatial.relate = counted
        try:
            tokens = lifecycle.spatial_context(identity or _identity(), layers)
        finally:
            spatial.relate = real
        return tokens, calls

    def test_without_a_carried_token_it_relates_once(self):
        tokens, calls = self._count(_layers())
        self.assertEqual(len(calls), 1)
        self.assertEqual(tokens["zone"]["spatial_relation"], "INSIDE")

    def test_with_a_matching_carried_token_it_relates_not_at_all(self):
        token = spatial.relate(SUBJECT, LAYER, **ARGUMENTS)
        tokens, calls = self._count(_layers(token=token))
        self.assertEqual(calls, [], "the duplicate computation must not occur")
        self.assertIs(tokens["zone"], token)

    def test_the_reused_token_is_the_one_relate_would_have_produced(self):
        token = spatial.relate(SUBJECT, LAYER, **ARGUMENTS)
        reused, _calls = self._count(_layers(token=token))
        fresh, _calls = self._count(_layers())
        self.assertEqual(reused["zone"], fresh["zone"])

    def test_a_mismatched_carried_token_is_recomputed_not_trusted(self):
        wrong = spatial.relate(SUBJECT, {"crs": "EPSG:3857", "geometry": FAR},
                               **ARGUMENTS)
        tokens, calls = self._count(_layers(token=wrong))
        self.assertEqual(len(calls), 1, "a token that does not match is not reused")
        self.assertEqual(tokens["zone"]["spatial_relation"], "INSIDE")
        self.assertNotEqual(tokens["zone"]["spatial_relation"],
                            wrong["spatial_relation"])

    def test_a_forged_token_is_recomputed(self):
        forged = {"spatial_relation": "INSIDE", "spatial_basis": "DETERMINISTIC_GIS",
                  "engine": spatial.ENGINE, "reason": None, "provenance": {}}
        tokens, calls = self._count(_layers(token=forged))
        self.assertEqual(len(calls), 1)
        self.assertNotEqual(tokens["zone"], forged)

    def test_several_parcels_recompute_even_with_a_token_offered(self):
        token = spatial.relate(SUBJECT, LAYER, **ARGUMENTS)
        tokens, calls = self._count(_layers(token=token),
                                    identity=_identity(_parcel_count=3))
        self.assertEqual(len(calls), 1)
        self.assertEqual(tokens["zone"]["spatial_relation"], "AMBIGUOUS")
        self.assertEqual(tokens["zone"]["reason"],
                         spatial.REASON_MULTIPLE_PARCELS)


class TheWitnessAnswerIsCarriedForward(unittest.TestCase):
    """The producer side: the absence proof keeps its answer, not just geometry."""

    def test_overlay_finding_returns_a_witness_token(self):
        import inspect
        from services import toronto_planning_source as source
        body = inspect.getsource(source.overlay_finding)
        self.assertIn("witness_token", body)
        self.assertIn('"witness_token": witness_token', body)

    def test_the_gate_carries_it_into_the_layer_description(self):
        import inspect
        from services import toronto_gate01
        body = inspect.getsource(toronto_gate01._layers)
        self.assertIn('"precomputed_token": finding.get("witness_token")', body)
        self.assertIn('"precomputed_token": finding.get("token")', body)

    def test_no_cache_of_any_kind_was_introduced(self):
        """Section 4: intra-request reuse only."""
        from pathlib import Path
        for name in ("services/deterministic_spatial.py",
                     "services/go_pdz_lifecycle.py"):
            source = Path(name).read_text(encoding="utf-8")
            for banned in ("lru_cache", "functools.cache", "_CACHE", "global ",
                           "shelve", "pickle"):
                self.assertNotIn(banned, source, "%s in %s" % (banned, name))

    def test_the_deduplication_is_independent_of_the_geometry_code(self):
        """SUPERSEDES "no geometry mathematics was changed".

        That assertion was correct for 02A, whose whole discipline was to remove
        duplicate work without touching the ruler - and it read the git diff to
        prove no hot function had been redefined. CLAUDE-SPATIAL-PREFILTER-02B is
        authorized to change exactly that, so the old form would now fail for the
        right reason, which makes it a test defending a constraint that has been
        deliberately lifted rather than an invariant.

        What survives is the invariant that actually matters to 02A: reuse is
        decided by comparing IDENTIFIERS, never by computing geometry, so the
        deduplication cannot be affected by how the arithmetic is implemented.
        The prohibition on changing answers now lives where it belongs - in
        `tests/test_spatial_prefilter_02b.py`, which proves equivalence
        differentially against the pre-change implementation.
        """
        import ast
        import inspect
        source = inspect.getsource(spatial.token_matches)
        tree = ast.parse(source)
        called = {node.func.id for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertEqual(called & {"_point_in_ring", "_segments_cross",
                                   "_distance_point_to_segment", "_rings_cross",
                                   "_any_crossing", "_min_distance_to_ring",
                                   "_min_distance_to_polygon", "_point_in_polygon",
                                   "_point_in_parts", "relate", "prepare_parts",
                                   "ring_band"}, set(),
                         "reuse must be decided without any geometry")
        self.assertIn("geometry_hash", called,
                      "identity is proven by hashing, which is the whole point")


if __name__ == "__main__":
    unittest.main()
