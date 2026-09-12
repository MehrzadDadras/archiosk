"""Operation rules use source-bearing facts, never thresholds or Gym bar counts."""
import copy
import hashlib
import json
from pathlib import Path

from services.operational_frontier import classify, handoff_catalog, snapshot, reconcile


def facts():
    return {"capability_id": "op.example", "known_capability": True,
            "application": {"stable_handoff": True}, "governance_state": "PERMITTED",
            "model_baseline": "instrument-one", "negative_requirement": "REQUIRED",
            "observations": [{"control": "POSITIVE_CONTROL", "valid": True, "aligned": True},
                             {"control": "NULL_TARGET", "valid": True, "aligned": True}],
            "acceptance": {"authorized": True, "capability_id": "op.example", "scope": "bounded operation",
                           "model_baseline": "instrument-one", "evidence_ref": "acceptance.json",
                           "level": "CONDITIONALLY READY"}}


def test_stable_and_accepted_go_is_shared_without_band_inflation():
    r = classify(facts())
    assert r["shared_state"] == "SHARED_FRONTIER"
    assert r["qualitative_band"] == "UNRESOLVED"


def test_stable_application_weak_go_is_application_ahead():
    f = facts(); f["observations"] = []; f.pop("acceptance")
    r = classify(f)
    assert r["shared_state"] == "APPLICATION_AHEAD" and r["gap_owner"] == "CODEX"


def test_ready_go_no_application_is_go_ahead():
    f = facts(); f["application"] = {"implemented": False, "search_scope": "declared operation entry points"}
    r = classify(f)
    assert r["application_state"] == "UNAVAILABLE" and r["shared_state"] == "GO_AHEAD"
    assert r["gap_owner"] == "CLAUDE"


def test_positive_and_valid_null_miss_is_negative_block():
    f = facts(); f["observations"][1]["aligned"] = False
    r = classify(f)
    assert r["shared_state"] == "BLOCKED_BY_NEGATIVE_CONTROL" and r["qualitative_band"] == "FRAGILE"
    assert r["negative_control_state"] == "FAILED_VALID"


def test_invalid_model_output_is_not_automatically_invalid_instrument():
    f = facts(); f["observations"][1].update(valid=False, aligned=None)
    r = classify(f)
    assert r["shared_state"] == "BLOCKED_BY_NEGATIVE_CONTROL"
    assert r["negative_control_state"] == "INVALID_UNSCORED" and r["gap_owner"] == "CODEX"


def test_governance_and_instrument_boundaries():
    f = facts(); f["governance_state"] = "UNRESOLVED"
    assert classify(f)["shared_state"] == "BLOCKED_BY_GOVERNANCE"
    f["instrument_invalid"] = True
    assert classify(f)["shared_state"] == "BLOCKED_BY_INSTRUMENT"


def test_conflict_unknown_no_c01_fallback():
    f = facts(); f["conflicts"] = ["handoff-one says stable; handoff-two revokes it without ordering"]
    r = classify(f)
    assert r["shared_state"] == r["application_state"] == "UNRESOLVED"
    assert r["unresolved_reasons"] == f["conflicts"]
    assert classify({"capability_id": "unknown"})["shared_state"] == "UNRESOLVED"
    assert "C01" not in json.dumps(classify({}))


def test_no_pass_count_threshold_or_stage_closure_promotion():
    f = facts(); f.pop("acceptance"); f["stage_closed"] = True; f["observations"] *= 100
    assert classify(f)["go_state"] == "DEVELOPING"


def test_negative_not_required_needs_scope_reference():
    f = facts(); f["observations"] = f["observations"][:1]; f["negative_requirement"] = "NOT_REQUIRED"
    assert classify(f)["go_state"] == "DEVELOPING"
    f["negative_requirement_ref"] = "operation-scope.json"
    assert classify(f)["go_state"] == "CONDITIONALLY READY"


def test_acceptance_cannot_cross_operation_or_instrument():
    f = facts(); f["acceptance"]["capability_id"] = "different"
    assert classify(f)["go_state"] == "DEVELOPING"
    f = facts(); f["acceptance"]["model_baseline"] = "different"
    assert classify(f)["go_state"] == "DEVELOPING"


def test_equivalent_application_proof_requires_all_components():
    f = facts(); f["application"] = {"implemented": True, "tested": True, "deployment_satisfied": True,
                                     "corpus_proof_satisfied": True, "no_invalidating_blocker": True}
    assert classify(f)["application_state"] == "STABLE"
    f["application"].pop("corpus_proof_satisfied")
    assert classify(f)["application_state"] == "EXPERIMENTAL"


def test_implemented_not_found_does_not_mean_globally_unavailable():
    f = facts(); f["application"] = {"implemented": False}
    assert classify(f)["application_state"] == "UNRESOLVED"


def test_handoff_and_snapshot_deterministic(tmp_path):
    text = '''### Capability handoff baseline
| Capability | Status | Surface | Evidence |
|---|---|---|---|
| Supersession behaviour | **READY (read)** | revision reader | approved lineage |
### Lane discipline
**Claude application frontier:** newer implementation
**Codex safe frontier:** stable read
'''
    path = tmp_path / "CONTINUATION_CHECKPOINT.md"; path.write_bytes(text.encode())
    normalized = {"records": [], "projection_sha256": "input-hash"}
    a = snapshot(normalized, tmp_path, tmp_path)
    assert a == snapshot(normalized, tmp_path, tmp_path)
    assert path.read_bytes() == text.encode()
    row = a["capabilities"][0]
    assert row["capability_id"] == "op.supersession-behaviour"
    assert row["application_state"] == "STABLE" and row["go_state"] == "UNTESTED"
    assert row["latest_evidence"][0]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert a["frontiers"]["active"] != a["frontiers"]["stable_handoff"]


def test_no_handoff_section_is_explicitly_unresolved(tmp_path):
    (tmp_path / "CONTINUATION_CHECKPOINT.md").write_text("unstructured evidence")
    _, frontier = handoff_catalog(tmp_path)
    assert frontier["conflicts"]


def test_duplicate_handoff_conflict_preserves_both_refs(tmp_path):
    (tmp_path / "CONTINUATION_CHECKPOINT.md").write_text('''### Capability handoff baseline
| Example | **READY** | reader | proof |
| Example | **NOT YET STABLE** | disputed |
### Lane discipline
''')
    result = snapshot({"records": [], "projection_sha256": "x"}, tmp_path, tmp_path)
    row = result["capabilities"][0]
    assert row["application_state"] == "UNRESOLVED"
    assert len(row["latest_evidence"]) == 2
    assert not result["ui_eligible"]


def test_governed_c11_result_join_preserves_invalid_negative(tmp_path):
    (tmp_path / "CONTINUATION_CHECKPOINT.md").write_text('''### Capability handoff baseline
| Supersession behaviour | **READY (read)** | reader | lineage |
### Lane discipline
**Claude application frontier:** current
**Codex safe frontier:** stable
''')
    rows = []
    for index, compliance, control in ((1, "VALID", "POSITIVE_CONTROL"), (2, "INVALID", "NEGATIVE_CONTROL")):
        path = tmp_path / (str(index) + "-result.json")
        path.write_text(json.dumps({"delivery_integrity": True, "material_valid": True}))
        rows.append({"record_family": "ENCOUNTER", "actor": "GO", "capability": "C11",
                     "task_kind": "SELECT", "record_id": path.name,
                     "application_capability": "spin_current_sources", "model_baseline": "claude-sonnet-4-6",
                     "instrument_validity": "INDETERMINATE", "contract_compliance": compliance,
                     "control_type": control, "task_content_result": {"target_alignment": True},
                     "application_defect": "NONE", "timestamp": "2026-09-11",
                     "evidence_refs": [{"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()},
                                       {"path": str(index) + "-provenance.json", "sha256": "reference"}]})
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = snapshot({"records": rows, "projection_sha256": "x"}, tmp_path, tmp_path)
    row = result["capabilities"][0]
    assert row["shared_state"] == "BLOCKED_BY_NEGATIVE_CONTROL"
    assert row["negative_control_state"] == "INVALID_UNSCORED"
    assert row["observations"][1]["aligned"] is None
    assert row["go_state"] == "DEVELOPING" and row["gap_owner"] == "CODEX"
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


def test_miss_and_invalid_negative_are_both_visible():
    f = facts()
    f["observations"][1]["aligned"] = False
    f["observations"].append({"control": "NULL_TARGET", "valid": False, "aligned": None})
    assert classify(f)["negative_control_findings"] == ["FAILED_VALID", "INVALID_UNSCORED"]


def test_latest_shipped_table_does_not_promote_safe_frontier(tmp_path):
    (tmp_path / "CONTINUATION_CHECKPOINT.md").write_text('''### Shipped, gated and deployed
| `c92e380` | **Datum corroboration boundary** | green |
### Current frontier
**Claude application frontier:** new
**Codex safe frontier:** unchanged
### Capability handoff baseline
| Example | **READY** | reader | proof |
### Lane discipline
''')
    result = snapshot({"records": [], "projection_sha256": "x"}, tmp_path, tmp_path)
    row = next(r for r in result["capabilities"] if r["capability_id"] == "op.datum-corroboration")
    assert row["application_state"] == "REACHABLE"
    assert row["safe_for_training"] is False


def clarification_fixture(tmp_path):
    source = Path(__file__).resolve().parents[1] / "docs/records/operation-taxonomy-clarification-01.json"
    target = tmp_path / "docs/records/operation-taxonomy-clarification-01.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(source.read_bytes())
    for row in json.loads(source.read_text())["operations"]:
        if row["implementation"]:
            relative, symbol = row["implementation"].split(":")
            code = tmp_path / relative
            code.parent.mkdir(exist_ok=True)
            code.write_text("def " + symbol + "(): pass")


def test_clarification_splits_operations_without_advancing_safe_frontier(tmp_path):
    clarification_fixture(tmp_path)
    old = [{"capability_id": identity, "evidence_refs": [{"path": "history", "sha256": "old"}]}
           for identity in ("op.cross-source-relationship-proposal", "op.two-sided-micro-context", "op.sheet-identity-register")]
    rows, record = reconcile(old, tmp_path)
    assert len(rows) == 5 and len({r["capability_id"] for r in rows}) == 5
    assert not any(r["safe_for_training"] for r in rows)
    assert len(record["retired_projection_entries"]) == 3
    assert all(q["state"] == "UNRESOLVED" for q in record["product_questions"])
    assert "6b37511" in record["codex_safe_frontier"]
    for row in rows:
        row["known_capability"] = True
    datum = next(r for r in rows if r["capability_id"] == "op.datum-corroboration")
    assert datum["application"]["deployed"] is True and datum["application"]["reachable"] is False
    assert classify(datum)["application_state"] == "EXPERIMENTAL"
    sachet = next(r for r in rows if r["capability_id"] == "op.relationship-sachet")
    assert classify(sachet)["application_state"] == "STABLE"
    assert classify(sachet)["shared_state"] != "SHARED_FRONTIER"
    absent = next(r for r in rows if r["capability_id"] == "op.cross-discipline-micro-context")
    assert classify(absent)["application_state"] == "UNAVAILABLE"


def test_missing_clarified_implementation_is_a_conflict(tmp_path):
    clarification_fixture(tmp_path)
    (tmp_path / "services/sheet_identity.py").write_text("# missing implementation")
    rows, _ = reconcile([], tmp_path)
    row = next(r for r in rows if r["capability_id"] == "op.sheet-identity-reference")
    row["known_capability"] = True
    assert classify(row)["application_state"] == "UNRESOLVED"


def test_stable_component_not_trainable_even_with_accepted_go():
    f = facts()
    f["application"].update(stable=True, trainable=False)
    f["training_gap_owner"] = "CLAUDE"
    assert classify(f)["shared_state"] == "IMMATURE"
    assert classify(f)["gap_owner"] == "CLAUDE"


def test_product_questions_visible_without_broad_mapping_blocker(tmp_path):
    clarification_fixture(tmp_path)
    (tmp_path / "CONTINUATION_CHECKPOINT.md").write_text('''### Capability handoff baseline
| Cross-Source relationship proposal | **NOT YET STABLE** | historical absence |
| Two-sided micro-context | **NOT YET STABLE** | historical absence |
### Lane discipline
**Claude application frontier:** deployed code
**Codex safe frontier:** 6b37511 unchanged
''')
    normalized = {"records": [], "projection_sha256": "x"}
    result = snapshot(normalized, tmp_path, tmp_path)
    assert result["ui_eligible"] is True
    assert len(result["taxonomy_reconciliation"]["product_questions"]) == 3
    assert result == snapshot(normalized, tmp_path, tmp_path)
    assert not any(r["safe_for_training"] for r in result["capabilities"])


def transition_fixture(tmp_path):
    clarification_fixture(tmp_path)
    repo = Path(__file__).resolve().parents[1]
    relative = "docs/records/datum-lifecycle-transition-01.json"
    transition = json.loads((repo / relative).read_text())
    for name in [relative, *transition["repository_evidence"]]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((repo / name).read_bytes())


def test_lifecycle_transition_preserves_unwired_history_and_training_hold(tmp_path):
    transition_fixture(tmp_path)
    rows, record = reconcile([], tmp_path)
    row = next(r for r in rows if r["capability_id"] == "op.datum-corroboration")
    row["known_capability"] = True
    assert row["application"]["reachable"] is True
    assert row["application"]["stable"] == "UNRESOLVED"
    assert row["application"]["trainable"] is False
    assert classify(row)["application_state"] == "REACHABLE"
    assert row["state_transitions"][0]["from_facets"]["reachable"] is False
    sachet = next(r for r in rows if r["capability_id"] == "op.relationship-sachet")
    assert "now reachable" in sachet["training_boundary"]
    assert "UNRESOLVED" == record["product_questions"][0]["state"]


def test_changed_lifecycle_implementation_does_not_reuse_old_proof(tmp_path):
    transition_fixture(tmp_path)
    path = tmp_path / "services/perception_worker.py"
    path.write_bytes(path.read_bytes() + b"\n# different implementation\n")
    rows, _ = reconcile([], tmp_path)
    row = next(r for r in rows if r["capability_id"] == "op.datum-corroboration")
    row["known_capability"] = True
    assert classify(row)["application_state"] == "UNRESOLVED"
