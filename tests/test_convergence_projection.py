"""Read-model boundaries: fixtures are disposable records, never training material."""
import hashlib
import json
from pathlib import Path

from services.cognitive_gym import scan
from services.convergence_projection import FIELDS, attribution


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def encounter(root, folder="COGNITIVE-GYM-AUTONOMOUS-BLOCK", phase="one", **fields):
    path = root / folder / "records" / (phase + "-result.json")
    put(path, {"phase": phase, "actor": "GO", "capability": "C28", "raw": '{"type":"SELECT","selected":["A"]}',
               "execution_valid": True, **fields})
    return path


def rows(root):
    return scan(root)["normalized"]["records"]


def test_legacy_and_modern_families_and_explicit_actor(tmp_path):
    encounter(tmp_path, "GO-COGNITIVE-GYM-C01-LEGACY", capability="C01")
    encounter(tmp_path, actor="GOTEX")
    data = scan(tmp_path)
    assert len(data["events"]) == 2
    assert {r["actor"] for r in data["normalized"]["records"]} == {"GO", "GOtex"}
    assert data["metrics"]["GOtex interventions"] == 1
    assert data["bars"][27]["status"] == "DEVELOPMENT ONLY"


def test_multi_capability_block_never_uses_primary_as_every_capability(tmp_path):
    path = encounter(tmp_path, capability="C28")
    encounter(tmp_path, phase="two", capability="C26")
    put(path.parent / "plan.json", {"primary": "C28", "mode": "DEVELOPMENT"})
    data = scan(tmp_path)
    assert {e["code"] for e in data["events"]} == {"C28", "C26"}
    assert data["bars"][0]["status"] == "UNTESTED"
    assert data["bars"][25]["status"] == data["bars"][27]["status"] == "DEVELOPMENT ONLY"


def test_explicit_actor_and_capability_override_directory_and_phase(tmp_path):
    encounter(tmp_path, "GO-COGNITIVE-GYM-C01-LEGACY", phase="gotex", actor="GO", capability="C11")
    r = rows(tmp_path)[0]
    assert r["actor"] == "GO" and r["capability"] == "C11"
    assert scan(tmp_path)["events"][0]["actor"] == "GO"


def test_missing_and_conflicting_attribution_are_unresolved(tmp_path):
    path = encounter(tmp_path)
    put(path, {"phase": "one", "raw": "{}"})
    r = rows(tmp_path)[0]
    assert r["capability"] == r["actor"] == "UNRESOLVED"
    assert scan(tmp_path)["bars"][0]["status"] == "UNTESTED"
    put(path, {"phase": "one", "raw": "{}", "capability": "C28", "actor": "GO"})
    put(path.parent / "one-material.json", {"capability": "C26", "actor": "GOTEX"})
    r = rows(tmp_path)[0]
    assert r["capability"] == r["actor"] == "UNRESOLVED"
    assert "conflicting" in r["attribution_basis"]["capability"]


def test_invalid_null_output_is_unscored_not_application_failure(tmp_path):
    path = encounter(tmp_path, capability="C11", execution_valid=False, target_alignment=True,
                     raw='{"type":"SELECT","selected":["A"]}\nWait...',
                     contract_compliance="MODEL CONTRACT-COMPLIANCE FAILURE", application_defect="NONE OBSERVED")
    put(path.parent / "one-material.json", {"target_present": False})
    put(path.parent / "one-observation.json", {"task_content": "Visible prose correctly states neither claim is supported, then selects A.",
                                               "instrument_validity": "VALID"})
    r = next(r for r in rows(tmp_path) if r["record_family"] == "ENCOUNTER")
    assert r["contract_compliance"] == "INVALID" and r["instrument_validity"] == "VALID"
    assert r["application_defect"] == "NONE OBSERVED"
    assert r["task_content_result"]["scoring"] == "UNSCORED"
    assert r["task_content_result"]["target_alignment"] is None
    assert r["control_type"] == "NULL_TARGET" and r["qualitative_band"] == "BLOCKED"
    assert r["operator_risks"][0]["kind"] == "PREMATURE COMMITMENT"
    assert scan(tmp_path)["events"][0]["aligned"] is None


def test_valid_null_miss_kept_separate(tmp_path):
    path = encounter(tmp_path, target_alignment=False)
    put(path.parent / "one-material.json", {"target": None, "options": {"A": "first", "B": "second"}})
    r = rows(tmp_path)[0]
    assert r["qualitative_band"] == "FRAGILE"
    assert r["shared_frontier_state"] == "BLOCKED_BY_NEGATIVE_CONTROL"


def test_stops_specimens_stages_frontiers_and_handoffs_are_not_encounters(tmp_path):
    f = tmp_path / "COGNITIVE-GYM-CONVERGENCE-C11-01" / "records"
    for name, data in {
        "termination.json": {"condition": "REPEATED INSTRUMENT FAILURE"},
        "specimen-verification.json": {"status": "VERIFIED", "current_source_ids": ["new"]},
        "stage-checkpoints.json": {"C11": {"observed": "positive lineage"}},
        "frontier-ledgers.json": {"GAP_OWNER": "CODEX", "CLAUDE_APPLICATION_FRONTIER": {"latest": "stable handoff"}},
        "stable-handoff-evidence.json": {"interpretation": "Stable read only"},
    }.items():
        put(f / name, data)
    data = scan(tmp_path)
    assert not data["events"]
    assert {r["record_family"] for r in data["normalized"]["records"]} == {"STOPPED", "SPECIMEN", "STAGE_CLOSEOUT", "FRONTIER", "HANDOFF"}
    assert not data["normalized"]["health_eligible"]
    assert data["normalized"]["health_blockers"]


def test_explicit_marker_discovers_nonstandard_folder(tmp_path):
    put(tmp_path / "BOUNDARY-RESEARCH" / "records/development-record.json", {"mode": "DEVELOPMENT"})
    assert len(scan(tmp_path)["sessions"]) == 1
    assert rows(tmp_path)[0]["capability"] == "UNRESOLVED"


def test_deterministic_and_no_source_mutation_or_copy_time_dependency(tmp_path):
    root = tmp_path / "source"
    path = encounter(root)
    put(path.parent / "one-dispatch.json", {"timestamp": "2026-09-12T00:00:00+00:00"})
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    a, b = scan(root), scan(root)
    assert a == b
    assert before == {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    copy = tmp_path / "copy"
    for name, content in before.items():
        p = copy / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    assert scan(copy) == a
    assert all(set(FIELDS) <= r.keys() for r in a["normalized"]["records"])


def test_no_band_promotion_from_positive_and_no_raw_prose_diagnosis(tmp_path):
    encounter(tmp_path, target_alignment=True, raw="Wait, neither is correct")
    r = rows(tmp_path)[0]
    assert r["qualitative_band"] == "UNRESOLVED" and not r["operator_risks"]


def test_secret_and_unknown_actor_do_not_leak_or_default(tmp_path):
    encounter(tmp_path, actor="unknown", raw="password=private sk-ant-abcdefghijklmnop")
    r = rows(tmp_path)[0]
    assert r["actor"] == "UNRESOLVED"
    assert "private" not in r["raw_response"] and "sk-ant-" not in r["raw_response"]


def test_no_read_of_tools_provider_requests_or_auth_db(tmp_path):
    path = encounter(tmp_path)
    for name in ["one-input.json", "one-provider-response.json", "one-expected-wire.json"]:
        put(path.parent / name, {"secret": "must not be read"})
    put(path.parent.parent / "specimen/auth.sqlite", {"secret": "must not be read"})
    data = scan(tmp_path)
    assert not any("provider-response" in p or "input.json" in p or "auth.sqlite" in p for p in data["source_hashes"])


def test_legacy_directory_hint_does_not_override_explicit_conflict():
    assert attribution("capability", [{"capability": "C28"}, {"capability": "C26"}], "GO-COGNITIVE-GYM-C01-OLD")[0] == "UNRESOLVED"


def test_unknown_and_corrupt_families_remain_visible(tmp_path):
    folder = tmp_path / "COGNITIVE-GYM-UNKNOWN"
    put(folder / "records/termination.json", {"condition": "STOP"})
    (folder / "records/termination.json").write_text("broken")
    data = scan(tmp_path)
    assert data["normalized"]["inventory"][0]["readable"] is False
    assert not data["normalized"]["health_eligible"]


def test_legacy_actor_capsule_requires_matching_raw_and_hash(tmp_path):
    path = encounter(tmp_path)
    raw = '{"type":"SELECT","selected":["A"]}'
    put(path, {"phase": "one", "raw": raw, "request_id": "request-one"})
    capsule = {"actor": "GOTEX", "raw": raw, "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(), "request_id": "request-one"}
    companion = path.parent.parent / "examiner/intervention-record.json"
    put(companion, {"GOtex_action": capsule})
    r = next(r for r in rows(tmp_path) if r["record_family"] == "ENCOUNTER")
    assert r["actor"] == "GOtex"
    assert any(ref["path"].endswith("intervention-record.json") for ref in r["evidence_refs"])
    capsule["raw_sha256"] = "not-matching"
    put(companion, {"GOtex_action": capsule})
    r = next(r for r in rows(tmp_path) if r["record_family"] == "ENCOUNTER")
    assert r["actor"] == "UNRESOLVED"
    capsule["raw_sha256"] = hashlib.sha256(raw.encode()).hexdigest()
    capsule["request_id"] = "different-request"
    put(companion, {"GOtex_action": capsule})
    r = next(r for r in rows(tmp_path) if r["record_family"] == "ENCOUNTER")
    assert r["actor"] == "UNRESOLVED"


def test_early_raw_response_counted_once_and_qualification_never_development(tmp_path):
    put(tmp_path / "GO-COGNITIVE-GYM-C01-OLD/examiner/development-record.json",
        {"mode": "DEVELOPMENT", "raw_response": "{}", "execution_valid": True})
    put(tmp_path / "GO-COGNITIVE-GYM-C02-QUALIFICATION/examiner/final-results.json",
        {"verdicts": [{"passed": True}], "no_real_development": True})
    data = scan(tmp_path)
    assert len(data["events"]) == 1
    assert sum(r["record_family"] == "ENCOUNTER" for r in data["normalized"]["records"]) == 1
    assert next(r for r in data["normalized"]["records"] if r["record_family"] == "QUALIFICATION")["task_kind"] == "QUALIFICATION"
