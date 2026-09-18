"""Versioned Rule 7 contract and real-consumer qualification. Never fabricates a hop.

Reuses go_pdz_contract's structural walker and CaseWorkspaceStore persistence.
Unimplemented operators/adapters fail qualification rather than becoming skips.
CLI: --structure-only; otherwise --fixture ID (default NaN height end-to-end).
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DIRECTORY = ROOT / "tests/fixtures/rule7"
HOPS = ("validator_expectation", "transform_expectation", "persistence_expectation",
        "ifc_expectation", "ask_go_expectation")
BLOCKING = {"NON_FINITE", "DEGENERATE", "UNRESOLVED", "INCOMPARABLE", "BLOCKED",
            "WEAK", "PARTIALLY_RECOVERED", "CONTESTED"}


class QualificationFailure(AssertionError):
    def __init__(self, message, observations=None):
        super().__init__(message)
        self.observations = observations or {}


def load_suite():
    return json.loads((DIRECTORY / "rule7_fixture_map.v1.json").read_text())


def fingerprint(fixture):
    return hashlib.sha256(json.dumps(fixture, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_suite(suite, registry=None, previous=None):
    from services.go_pdz_contract import validate_structure
    schema = json.loads((DIRECTORY / "rule7_fixture_map.schema.json").read_text())
    problems = ["SCHEMA: %s %s" % p for p in validate_structure(suite, schema)]
    if problems:
        return problems
    def patterns(value, spec, path):
        if "pattern" in spec and (not isinstance(value, str) or not re.fullmatch(spec["pattern"], value)):
            problems.append("SCHEMA: invalid version/ID at " + path)
        if isinstance(value, dict):
            for k, v in value.items():
                patterns(v, spec.get("properties", {}).get(k, {}), path + "." + k)
        if isinstance(value, list):
            for i, v in enumerate(value):
                patterns(v, spec.get("items", {}), path + "." + str(i))
    patterns(suite, schema, "suite")
    fixtures = suite.get("fixtures", [])
    ids = [f.get("fixture_id") for f in fixtures]
    if not fixtures or len(ids) != len(set(ids)):
        problems.append("R7-MAP-06: empty suite or duplicate fixture ID")
    for f in fixtures:
        for i, hop in enumerate(HOPS, 1):
            if hop not in f:
                problems.append("R7-MAP-%02d: %s missing %s" % (i, f.get("fixture_id"), hop))
        if not all(hop in f for hop in HOPS):
            continue
        v, t, p, exporter, ask = (f[h] for h in HOPS)
        errors = set(v.get("errors", [])) - {"NONE"}
        for name, hop in zip(HOPS[1:], (t, p, exporter, ask)):
            if errors - set(hop.get("errors", [])):
                problems.append("R7-MAP-07: blocking error lost at " + name)
        if p.get("state_after_reload") != p.get("state") or (v.get("state") in BLOCKING and p.get("state") not in BLOCKING):
            problems.append("R7-MAP-08: unexplained persistence strengthening")
        if p.get("must_not_strengthen") is not True:
            problems.append("R7-MAP-08: missing monotonicity contract")
        if exporter.get("export_state") == "IFC_EXPORTABLE" and (errors or any(h.get("state") in BLOCKING for h in (v, t, p))):
            problems.append("R7-MAP-09: prior blocker authorizes IFC export")
        if exporter.get("must_not_export") != (exporter.get("export_state") != "IFC_EXPORTABLE"):
            problems.append("R7-MAP-09: inconsistent export permission")
        if (errors or v.get("state") in BLOCKING) and ask.get("state") == "FACTUAL":
            problems.append("R7-MAP-10: factual invalid geometry")
        if not {"NaN", "Infinity"}.issubset(set(ask.get("must_not_contain", []))):
            problems.append("R7-MAP-10: missing invalid numeric prose exclusions")
    if registry is None:
        registry = json.loads((DIRECTORY / "rule7_fixture_map.ids.v1.json").read_text())
    by_id = {f["fixture_id"]: f for f in fixtures}
    entries = registry["entries"]
    if len({e["id"] for e in entries}) != len(entries):
        problems.append("R7-ID: duplicate registry ID")
    for entry in entries:
        f = by_id.get(entry["id"])
        if not f:
            if entry["status"] != "RETIRED" or not entry.get("retired_version"):
                problems.append("R7-ID: registered ID silently disappeared: " + entry["id"])
            continue
        if entry["status"] != "ACTIVE" or entry["category"] != f["category"]:
            problems.append("R7-ID: conceptual identity changed")
        if entry["fixture_version"] != f["fixture_version"] or entry["sha256"] != fingerprint(f):
            problems.append("R7-VERSION: fixture does not match its versioned registry entry")
    if set(ids) - {e["id"] for e in entries}:
        problems.append("R7-ID: unregistered fixture")
    if previous:
        if previous["suite_id"] != suite["suite_id"]:
            problems.append("R7-VERSION: suite identity changed")
        if previous != suite and previous["suite_version"] == suite["suite_version"]:
            problems.append("R7-VERSION: suite changed without version bump")
        for old in previous["fixtures"]:
            current = by_id.get(old["fixture_id"])
            if current and old != current and old["fixture_version"] == current["fixture_version"]:
                problems.append("R7-VERSION: fixture changed without version bump")
    return problems


def assert_hop(actual, expected, name):
    state_key = "export_state" if name == "ifc" else "state"
    if actual.get(state_key) != expected[state_key]:
        raise QualificationFailure(f"{name}: expected {expected[state_key]}, got {actual.get(state_key)}")
    if set(expected.get("errors", [])) - set(actual.get("errors", [])):
        raise QualificationFailure(f"R7-MAP-07: {name} lost expected failure code")
    if "coordinate_space" in expected and actual.get("coordinate_space") != expected["coordinate_space"]:
        raise QualificationFailure(f"{name}: coordinate space changed")
    for key in expected.get("must_preserve", []):
        if key not in actual:
            raise QualificationFailure(f"{name}: provenance/premise field missing: {key}")
    if expected.get("value_expected") is False and actual.get("value") is not None:
        raise QualificationFailure(f"{name}: invalid value was emitted")
    if expected.get("value_expected") is True and actual.get("value") is None:
        raise QualificationFailure(f"{name}: expected value missing")
    prose = actual.get("text", "")
    for token in expected.get("must_contain", []):
        if token not in prose:
            raise QualificationFailure(f"{name}: required surfaced qualification missing: {token}")
    for token in expected.get("must_not_contain", []):
        if token.casefold() in prose.casefold():
            raise QualificationFailure(f"R7-MAP-10: {name} contains forbidden numeric prose")


def decode(value):
    if isinstance(value, str) and value in ("NaN", "+Infinity", "-Infinity"):
        return float({"NaN": "nan", "+Infinity": "inf", "-Infinity": "-inf"}[value])
    if isinstance(value, list):
        return [decode(v) for v in value]
    if isinstance(value, dict):
        return {k: decode(v) for k, v in value.items()}
    return value


# These are absent mathematical capabilities, not failed adapters. Keep this
# explicit and narrow: an unknown kind still fails qualification.
MISSING_OPERATORS = {}


class MissingOperator(QualificationFailure):
    pass


def candidate_for(inputs):
    """Put source inputs in the existing IFC candidate, in their declared chart."""
    model = json.loads((DIRECTORY / "ifc_candidate.v1.json").read_text())
    kind, value = inputs["kind"], decode(inputs["value"])
    context = {key: inputs[key] for key in ("coordinate_space", "plane_id", "geometry_level",
                                            "read_certainty", "bind_certainty", "provenance")}
    for owner in model["spaces"] + model["walls"]:
        owner["geometry_context"] = dict(context)
    model["label_containment"][0]["relation"].update(
        coordinate_space=inputs["coordinate_space"], plane_id=inputs["plane_id"])
    field = {"weak_binding": "height", "contested": "height", "stale": "height",
             "unbound": "height", "zero_area": "polygon", "homography": "point"}.get(kind, kind)
    owner = model["spaces"][0] if field in ("height", "polygon") else model["walls"][0]
    if field in ("height", "thickness"):
        owner[field] = value
    elif field in ("point", "endpoint") and kind != "homography":
        owner["baseline"][0 if field == "point" else 1] = dict(zip(("x", "y"), value))
    elif field == "polygon":
        owner["boundary_polygon_2d"] = [dict(zip(("x", "y"), point)) for point in value]
    elif field in ("projection", "wall"):
        owner["baseline"] = [dict(zip(("x", "y"), value[key])) for key in ("a", "b")]
        # Declared fixture opening, not a clamped dimension or measured width.
        owner["openings"][0].update(width=value.get("width", 2), offset=0)
    if kind == "unbound":
        model["label_containment"] = []
    return model, owner, field


def run_validator(inputs, *, store=None, workspace=None, source_evidence=None, model=None):
    from engine.ifc_volume_validator import numeric_validity, polygon_region, _semantic_binding_established
    from engine.spatial_compiler import project_point_to_segment, SpatialCompiler, SpatialCompilationError
    from services import binding
    kind, value = inputs["kind"], decode(inputs["value"])
    if kind in MISSING_OPERATORS:
        raise MissingOperator(MISSING_OPERATORS[kind])
    record = {k: copy.deepcopy(inputs[k]) for k in ("coordinate_space", "provenance", "read_certainty", "bind_certainty")}
    def finish(state, output, errors, derivation=None):
        record.update(state=state, value=output, errors=errors,
            derivation=derivation or {"operator": "numeric_validity@1", "operator_version": "1",
                "tolerance_context": {"policy": "strict_finiteness", "tolerance": None}})
        return record
    if kind == "homography":
        from engine.spatial_compiler import validate_homography, transform_homogeneous_point
        # These map controls declare a same-chart/same-plane transformation.
        # Cross-chart operator controls supply both endpoints explicitly.
        transform = validate_homography(value["matrix"], source_space=inputs["coordinate_space"],
            target_space=inputs["coordinate_space"], source_plane=inputs["plane_id"],
            target_plane=inputs["plane_id"], geometry_level=inputs["geometry_level"],
            uncertainty=inputs.get("uncertainty"), source=inputs["provenance"])
        result = transform_homogeneous_point(transform, value["point"],
            point_space=inputs["coordinate_space"], point_plane=inputs["plane_id"])
        return finish(result["state"], result["value"], [result["error"]] if result["error"] else [], result)
    if kind in ("vector", "domain"):
        from engine.spatial_compiler import vector_usability, bounded_acos
        operation = vector_usability if kind == "vector" else bounded_acos
        arguments = (value,) if kind == "vector" else (value["value"], value["error_bound"])
        if kind == "domain" and value.get("operation") != "acos":
            raise QualificationFailure("UNWIRED_DOMAIN_OPERATION")
        result = operation(*arguments, source_space=inputs["coordinate_space"],
            target_space=inputs["coordinate_space"], source_plane=inputs["plane_id"],
            target_plane=inputs["plane_id"], geometry_level=inputs["geometry_level"],
            source=inputs["provenance"], uncertainty=inputs.get("uncertainty"))
        return finish(result["state"], result["value"], [result["error"]] if result["error"] else [], result)
    if kind in ("height", "thickness", "weak_binding", "contested", "stale", "unbound"):
        state = numeric_validity(value)
        if state != "FINITE":
            return finish(state, None, ["NON_FINITE_DIMENSION"])
        if binding.bound_certainty(inputs) != "RECOVERED":
            return finish("PARTIALLY_RECOVERED", None, ["PREMISE_UNESTABLISHED"])
        trust = store.explain_evidence_trust(workspace, source_evidence["id"])
        if trust["confirmed_counterevidence"]:
            return finish("CONTESTED", None, ["EVIDENCE_CONFLICT"])
        if trust["currentness"]["status"] != "current":
            return finish("UNRESOLVED", None, ["STALE_EVIDENCE"])
        if not _semantic_binding_established(model, model["spaces"][0]):
            return finish("UNRESOLVED", None, ["SEMANTIC_BINDING_UNRESOLVED"],
                          {"operator": "semantic_binding@1", "operator_version": "1"})
        return finish("FINITE", value, [])
    if kind in ("point", "endpoint", "polygon", "zero_area"):
        points = value if kind in ("polygon", "zero_area") else [value]
        states = [numeric_validity(v) for point in points for v in point]
        if any(state != "FINITE" for state in states):
            code = {"point": "NON_FINITE_POINT", "endpoint": "NON_FINITE_SEGMENT",
                    "polygon": "NON_FINITE_POLYGON", "zero_area": "NON_FINITE_POLYGON"}[kind]
            return finish("NON_FINITE" if "NON_FINITE" in states else "UNRESOLVED", None, [code])
        if kind in ("polygon", "zero_area"):
            region = polygon_region(model["spaces"][0])
            if region["state"] != "VALID_REGION":
                return finish("DEGENERATE", None, ["DEGENERATE_GEOMETRY"], region)
            return finish("ESTABLISHED", value, [], region)
        return finish("FINITE", value, [])
    if kind == "projection":
        result = project_point_to_segment(value["point"], value["a"], value["b"],
            point_space=inputs["coordinate_space"], segment_space=value.get("segment_space", inputs["coordinate_space"]),
            point_plane=inputs["plane_id"], segment_plane=value.get("segment_plane", inputs["plane_id"]),
            geometry_level=inputs["geometry_level"], source=inputs["provenance"])
        error = {"INCOMPARABLE_COORDINATE_SPACES": "SPACE_MISMATCH"}.get(result["error"], result["error"])
        return finish(result["state"], result["point"], [error] if error else [], result)
    if kind == "wall":
        try:
            host, offset, shift = SpatialCompiler._host_wall(value["point"], model["walls"], value["width"])
        except SpatialCompilationError as error:
            diagnostic = error.diagnostic
            return finish(diagnostic["state"], None, [diagnostic["error"]], diagnostic)
        return finish("ESTABLISHED" if host else "UNRESOLVED", [offset, shift] if host else None,
                      [] if host else ["PREMISE_UNESTABLISHED"],
                      {"operator": "wall_host@1", "premises": {"point": value["point"], "segment": [value["a"], value["b"]]}})
    raise QualificationFailure("UNWIRED_VALIDATOR: " + kind)


def run_fixture(fixture, directory):
    """Real source, validator, evidence/review, reload, consumers and IFC.

    Explicit registration qualifies these APIs, not automatic compiler ingestion
    or a live model answer. Expected states/prose never enter production records.
    """
    from engine.ifc_volume_validator import IFCValidationError, IFCVolumeValidator
    from services.case_workspace import (CaseWorkspaceStore, EVIDENCE_CLASS_CALCULATED_VALUE,
                                         EVIDENCE_CLASS_DIRECT_SOURCE)
    from flask import Flask
    from services import document_examination as dx, document_conversation as dc
    seen = {}
    try:
        inputs = fixture["inputs"]
        if inputs["kind"] in MISSING_OPERATORS:
            raise MissingOperator(MISSING_OPERATORS[inputs["kind"]])
        model, owner, field = candidate_for(inputs)
        store = CaseWorkspaceStore(str(directory))
        workspace = store.get_or_create(fixture["fixture_id"], register_document_source={"filename": "geometry-fixture.json"})
        source_id = workspace.sources[0]["id"]
        unit = store.create_structural_unit(workspace, source_id, "page", 0)
        region = store.create_addressable_region(workspace, unit["id"], "geometry",
            {"object_id": owner["id"], "page_index": 0})
        source_evidence = store.register_evidence_item(workspace, source_id, EVIDENCE_CLASS_DIRECT_SOURCE,
            json.dumps(inputs, allow_nan=False), "application/json", region_id=region["id"])
        if inputs["kind"] in ("contested", "stale"):
            other = store.register_evidence_item(workspace, source_id, EVIDENCE_CLASS_DIRECT_SOURCE,
                json.dumps(dict(inputs, value=145), allow_nan=False), "application/json", region_id=region["id"])
            if inputs["kind"] == "contested":
                edge = store.record_evidence_relationship(workspace, "evidence_item", other["id"],
                    "evidence_item", source_evidence["id"], "contradicts", provisional=True)
                store.confirm_relationship(workspace, edge["id"], actor="fixture-reviewer")
            else:
                store.record_supersession(workspace, "evidence_item", source_evidence["id"],
                    "evidence_item", other["id"], actor="fixture-reviewer", reason="Replaced input occurrence")
        validated = run_validator(inputs, store=store, workspace=workspace,
                                  source_evidence=source_evidence, model=model)
        validated.update(field=field, object_id=owner["id"],
            source_evidence_ids=[source_evidence["id"]], premise_ids=[source_evidence["id"]],
            plane_id=inputs["plane_id"], uncertainty=inputs.get("uncertainty", {"state": "UNRESOLVED"}))
        seen["validator"] = validated
        assert_hop(validated, fixture["validator_expectation"], "validator")
        evidence = store.register_evidence_item(workspace, source_id, EVIDENCE_CLASS_CALCULATED_VALUE,
            json.dumps(validated, allow_nan=False), "application/json", region_id=region["id"],
            extractor_version=validated["derivation"]["operator"])
        link = store.record_evidence_relationship(workspace, "evidence_item", evidence["id"],
            "evidence_item", source_evidence["id"], "derived_from", provisional=True,
            created_by="rule7-qualification", reason="Deterministic validation of this scoped input")
        store.confirm_relationship(workspace, link["id"], actor="fixture-reviewer")
        reloaded_store = CaseWorkspaceStore(str(directory))
        reloaded = reloaded_store.get(workspace.project_id)
        retained = json.loads(reloaded_store.get_evidence_item(reloaded, evidence["id"])["content"])
        seen["persistence"] = retained
        assert_hop(retained, fixture["persistence_expectation"], "persistence")
        if retained != validated:
            raise QualificationFailure("R7-MAP-08: persistence changed the governed record")
        governed = reloaded_store.project_geometry_evidence(reloaded, evidence["id"])
        seen["review_trust"] = governed
        exported = None
        try:
            exported = IFCVolumeValidator().export_evidence(model, reloaded_store, reloaded, evidence["id"])
            transform = dict(retained)
            ifc = {"export_state": "IFC_EXPORTABLE", "errors": [], "text": exported}
        except IFCValidationError as error:
            diagnostic = error.diagnostic or {}
            if "export_state" not in diagnostic:
                raise QualificationFailure("UNCLASSIFIED_IFC_REFUSAL: " + str(error)) from error
            if governed["state"] == "WEAK" and not governed["errors"]:
                # Retain the conditional interval, never promote it to a usable
                # measurement merely because IFC has made its refusal decision.
                transform = dict(retained, state="WEAK", diagnostic=diagnostic)
            else:
                transform = dict(retained, state="BLOCKED", value=None, errors=diagnostic["errors"], diagnostic=diagnostic)
            ifc = {"export_state": diagnostic["export_state"], "errors": diagnostic["errors"]}
        seen["transform"] = transform
        assert_hop(transform, fixture["transform_expectation"], "transform")
        seen["ifc"] = ifc
        assert_hop(ifc, fixture["ifc_expectation"], "ifc")
        if fixture["ifc_expectation"]["must_not_export"] and exported is not None:
            raise QualificationFailure("R7-MAP-09: blocked geometry exported")
        document = SimpleNamespace(project_id=workspace.project_id, filename="geometry-fixture.json")
        app = Flask(__name__)
        app.config["REGISTRY_STORE_PATH"] = str(directory)
        with app.app_context():
            result = dx.build_result(document, reloaded, display_name="Geometry fixture")
            context = dc.build_context(document, reloaded, result, "What %s is established?" % field)
        prose = dc.render_prompt(context)
        matches = [(group, row) for group in ("interpretation", "not_established")
                   for row in result[group] if row.get("evidence_item_id") == evidence["id"]]
        if len(matches) != 1:
            raise QualificationFailure("MISSING_EXAMINATION_EVIDENCE_ROUTE")
        group, row = matches[0]
        line = "%s: %s" % (row["label"], row["value"])
        if line not in context[group] or line not in prose:
            raise QualificationFailure("MISSING_ASK_GO_EXAMINATION_ROUTE")
        if row["state"] != governed["state"] or row["errors"] != governed["errors"]:
            raise QualificationFailure("EXAMINATION_CHANGED_GOVERNED_STATE")
        ask = {"state": "UNRESOLVED" if group == "not_established" else
               "QUALIFIED" if row["state"] in ("PARTIALLY_RECOVERED", "WEAK") else "FACTUAL",
               "errors": row["errors"], "text": prose}
        seen["ask_go"] = ask
        assert_hop(ask, fixture["ask_go_expectation"], "ask_go")
        return seen
    except QualificationFailure as error:
        error.observations = seen
        raise


def run_suite(suite):
    outcomes = []
    for fixture in suite["fixtures"]:
        with tempfile.TemporaryDirectory(prefix="rule7-map-") as directory:
            try:
                run_fixture(fixture, directory)
                row = {"fixture_id": fixture["fixture_id"], "status": "PASS"}
            except MissingOperator as error:
                row = {"fixture_id": fixture["fixture_id"], "status": "BLOCKED_MISSING_OPERATOR", "operator": str(error)}
            except QualificationFailure as error:
                row = {"fixture_id": fixture["fixture_id"], "status": "FAIL", "error": str(error)}
            outcomes.append(row)
    counts = {state: sum(row["status"] == state for row in outcomes)
              for state in ("PASS", "FAIL", "BLOCKED_MISSING_OPERATOR", "NOT_APPLICABLE")}
    return {"status": "FAIL" if counts["FAIL"] else "ADAPTERS_PASS_WITH_BLOCKED_OPERATORS" if
            counts["BLOCKED_MISSING_OPERATOR"] else "PASS", "counts": counts,
            "end_to_end_proven": counts["PASS"] == len(outcomes), "results": outcomes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--structure-only", action="store_true")
    parser.add_argument("--fixture", default="R7-FIN-NF-001")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--report", type=Path, help="Retain the exact qualification report")
    args = parser.parse_args()
    suite = load_suite()
    problems = validate_suite(suite)
    if problems:
        report = {"status": "FAIL", "errors": problems}
    elif args.structure_only:
        report = {"status": "STRUCTURE_VALID", "fixtures": len(suite["fixtures"]), "end_to_end_proven": False}
    elif args.all:
        report = run_suite(suite)
    else:
        fixture = next(f for f in suite["fixtures"] if f["fixture_id"] == args.fixture)
        with tempfile.TemporaryDirectory(prefix="rule7-map-") as directory:
            try:
                report = {"status": "PASS", "observations": run_fixture(fixture, directory)}
            except MissingOperator as error:
                report = {"status": "BLOCKED_MISSING_OPERATOR", "operator": str(error)}
            except QualificationFailure as error:
                report = {"status": "FAIL", "error": str(error), "observations": error.observations}
    rendered = json.dumps(report, indent=2, allow_nan=False)
    if args.report:
        args.report.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 1 if report["status"] == "FAIL" else 2 if report["status"] == "BLOCKED_MISSING_OPERATOR" else 0


if __name__ == "__main__":
    raise SystemExit(main())
