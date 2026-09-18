"""Qualification of existing evidence governance at geometry consumer boundaries."""
import copy
import json
from types import SimpleNamespace

import pytest
from flask import Flask

from engine.ifc_volume_validator import IFCValidationError, IFCVolumeValidator
from services.case_workspace import CaseWorkspaceStore
from services import document_examination as dx, document_conversation as dc
from tools import validate_rule7_fixture_map as harness


SUITE = harness.load_suite()
ELIGIBLE = [f for f in SUITE["fixtures"] if f["inputs"]["kind"] not in harness.MISSING_OPERATORS]
FORMER_BLOCKERS = {"R7-FIN-ZERO-001", "R7-FIN-DOM-001", "R7-FIN-DOM-002",
                   "R7-FIN-TR-001", "R7-FIN-TR-002", "R7-FIN-TR-003"}


@pytest.mark.parametrize("fixture", ELIGIBLE, ids=lambda f: f["fixture_id"])
def test_existing_capability_entire_evidence_route(tmp_path, fixture):
    seen = harness.run_fixture(fixture, tmp_path)
    assert seen["validator"] == seen["persistence"]
    assert seen["review_trust"]["record"] == seen["persistence"]
    assert "geometry_premises" not in seen["ask_go"]["text"]
    for code in seen["validator"]["errors"]:
        assert code not in seen["ask_go"]["text"]


def test_rule7b_resolves_all_recorded_operator_blockers():
    assert harness.MISSING_OPERATORS == {}
    assert len(ELIGIBLE) == 34


@pytest.fixture
def route(tmp_path):
    fixture = next(f for f in ELIGIBLE if f["fixture_id"] == "R7-FIN-POS-001")
    seen = harness.run_fixture(fixture, tmp_path)
    store = CaseWorkspaceStore(str(tmp_path))
    workspace = store.get(fixture["fixture_id"])
    evidence_id = seen["review_trust"]["evidence_item_id"]
    model, _, _ = harness.candidate_for(fixture["inputs"])
    return store, workspace, evidence_id, model, tmp_path


def context_for(route):
    store, workspace, _, _, directory = route
    workspace = store.get(workspace.project_id)
    app = Flask(__name__)
    app.config["REGISTRY_STORE_PATH"] = str(directory)
    document = SimpleNamespace(filename="geometry-fixture.json", project_id=workspace.project_id)
    with app.app_context():
        result = dx.build_result(document, workspace, display_name="Geometry fixture")
        context = dc.build_context(document, workspace, result, "What height is established?")
    return result, context, dc.render_prompt(context)


def derived_copy(route, **updates):
    store, workspace, evidence_id, _, _ = route
    original = store.get_evidence_item(workspace, evidence_id)
    record = json.loads(original["content"])
    record.update(updates)
    row = store.register_evidence_item(workspace, original["source_id"], "calculated_value",
        json.dumps(record), "application/json", region_id=original["region_id"])
    for premise_id in record["premise_ids"]:
        edge = store.record_evidence_relationship(workspace, "evidence_item", row["id"],
            "evidence_item", premise_id, "derived_from", provisional=True)
        store.confirm_relationship(workspace, edge["id"], actor="test-reviewer")
    return row


@pytest.mark.parametrize("change", ["disputed", "contradicted", "stale", "duplicate_disputed"])
def test_changed_review_blocks_previously_finite_result_after_reload(route, change):
    store, workspace, evidence_id, model, _ = route
    original = store.get_evidence_item(workspace, evidence_id)["content"]
    premise_id = json.loads(original)["premise_ids"][0]
    edge = next(e for e in workspace.relationships if e["from_id"] == evidence_id)
    if change == "duplicate_disputed":
        edge = store.record_evidence_relationship(workspace, "evidence_item", evidence_id,
            "evidence_item", premise_id, "derived_from", provisional=True)
    if change in ("disputed", "duplicate_disputed"):
        store.dispute_relationship(workspace, edge["id"], actor="test-reviewer", reason="Input binding disputed")
    else:
        old = store.get_evidence_item(workspace, premise_id)
        replacement = store.register_evidence_item(workspace, old["source_id"], "direct_source_evidence",
            old["content"], "application/json", region_id=old["region_id"])
        if change == "stale":
            store.record_supersession(workspace, "evidence_item", premise_id,
                "evidence_item", replacement["id"], actor="test-reviewer")
        else:
            edge = store.record_evidence_relationship(workspace, "evidence_item", replacement["id"],
                "evidence_item", premise_id, "contradicts", provisional=True)
            store.confirm_relationship(workspace, edge["id"], actor="test-reviewer")
    reloaded = store.get(workspace.project_id)
    projected = store.project_geometry_evidence(reloaded, evidence_id)
    assert projected["value"] is None and projected["errors"]
    assert store.get_evidence_item(reloaded, evidence_id)["content"] == original
    with pytest.raises(IFCValidationError):
        IFCVolumeValidator().export_evidence(model, store, reloaded, evidence_id)
    result, context, prose = context_for(route)
    assert any(row.get("evidence_item_id") == evidence_id for row in result["not_established"])
    assert "Height could not be established" in prose
    assert "Height: 144" not in prose
    assert "geometry_premises" not in context


@pytest.mark.parametrize("state", ["NON_FINITE", "DEGENERATE", "UNRESOLVED", "INCOMPARABLE",
                                   "PARTIALLY_RECOVERED", "WEAK", "CONTESTED"])
def test_review_confirmation_never_upgrades_stored_weak_state(route, state):
    store, workspace, _, model, _ = route
    row = derived_copy(route, state=state, value=None, errors=["PREMISE_UNESTABLISHED"])
    reloaded = store.get(workspace.project_id)
    projected = store.project_geometry_evidence(reloaded, row["id"])
    assert projected["state"] == state
    assert projected["value"] is None
    assert projected["record"]["state"] == state
    with pytest.raises(IFCValidationError):
        IFCVolumeValidator().export_evidence(model, store, reloaded, row["id"])


@pytest.mark.parametrize("updates", [
    {"value": float("inf")}, {"value": float("nan")}, {"object_id": "wrong-object"},
    {"source_evidence_ids": []}, {"plane_id": None}, {"errors": 123},
    {"bind_certainty": "PARTIALLY_RECOVERED"}, {"bind_basis": "proximity"},
])
def test_malformed_or_weakened_record_cannot_earn_export(route, updates):
    store, workspace, _, model, _ = route
    row = derived_copy(route, **updates)
    projected = store.project_geometry_evidence(store.get(workspace.project_id), row["id"])
    assert projected["value"] is None and projected["errors"]
    with pytest.raises(IFCValidationError):
        IFCVolumeValidator().export_evidence(model, store, workspace, row["id"])


def test_derived_premise_refusal_propagates_without_mutating_original(route):
    store, workspace, _, model, _ = route
    refused = derived_copy(route, state="NON_FINITE", value=None, errors=["NON_FINITE_DIMENSION"])
    downstream = derived_copy(route, premise_ids=[refused["id"]], source_evidence_ids=[refused["id"]])
    projected = store.project_geometry_evidence(store.get(workspace.project_id), downstream["id"])
    assert "NON_FINITE_DIMENSION" in projected["errors"]
    assert projected["value"] is None
    assert projected["record"]["state"] == "FINITE"
    with pytest.raises(IFCValidationError):
        IFCVolumeValidator().export_evidence(model, store, workspace, downstream["id"])


def test_positive_evidence_applies_real_value_without_mutating_candidate(route):
    store, workspace, evidence_id, model, _ = route
    model["spaces"][0]["height"] = 99
    original = copy.deepcopy(model)
    output = IFCVolumeValidator().export_evidence(model, store, workspace, evidence_id)
    assert "144.0" in output
    assert model == original


@pytest.mark.parametrize("key", ["coordinate_space", "plane_id"])
def test_ifc_target_context_must_match_evidence(route, key):
    store, workspace, evidence_id, model, _ = route
    model["spaces"][0]["geometry_context"][key] = "different"
    with pytest.raises(IFCValidationError) as caught:
        IFCVolumeValidator().export_evidence(model, store, workspace, evidence_id)
    assert caught.value.diagnostic["export_state"] == "IFC_BLOCKED_COORDINATE_SPACE"


def test_map_rejects_missing_hops_duplicate_ids_and_strengthening():
    assert harness.validate_suite(SUITE) == []
    for mutation in ("missing", "duplicate", "factual"):
        suite = copy.deepcopy(SUITE)
        if mutation == "missing":
            del suite["fixtures"][0]["persistence_expectation"]
        elif mutation == "duplicate":
            suite["fixtures"].append(copy.deepcopy(suite["fixtures"][0]))
        else:
            weak = next(f for f in suite["fixtures"] if f["inputs"]["kind"] == "weak_binding")
            weak["ask_go_expectation"]["state"] = "FACTUAL"
        assert harness.validate_suite(suite)


def test_inventory_accounts_for_all_original_failures_and_exact_missing_set():
    inventory = json.loads((harness.DIRECTORY / "rule7_adapter_inventory.v1.json").read_text())
    assert len(inventory["failures"]) == 25
    blocked = {f["fixture_id"] for f in inventory["failures"] if not f["eligible"]}
    # This inventory is the immutable adapter-tranche baseline, not a claim
    # that the mathematical operators implemented in Rule 7B remain missing.
    assert blocked == FORMER_BLOCKERS
    assert len(blocked) == 6
