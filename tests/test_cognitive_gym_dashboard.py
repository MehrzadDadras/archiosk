"""Dashboard evidence and authorization boundaries; no provider or evaluator execution."""
import hashlib
import json
from pathlib import Path

import pytest

from services.cognitive_gym import scan, dashboard


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def evidence(tmp_path):
    root = tmp_path / "evaluator"
    folder = root / "GO-COGNITIVE-GYM-C01-ADAPTIVE-CYCLE-91"
    for phase, actor, target in [("cheat", "GO_CHEAT_SHEET", None), ("gotex", "GOTEX", "B"), ("go9", "GO", "D")]:
        put(folder / "records" / f"{phase}-result.json", {"phase": phase, "actor": actor,
            "raw": "Exact authored sheet" if not target else json.dumps({"type": "SELECT", "selected": [target]}),
            "execution_valid": True, "usage": {"input_tokens": 50, "output_tokens": 12}, "cost_usd": .001})
        if target:
            put(folder / "records" / f"{phase}-material.json", {"objective": "Choose blue", "target": target, "distractor": "A", "salience": "SIZE only"})
    put(folder / "records/next-developmental-move.json", {"next_move": "VARY"})
    stopped = root / "GO-COGNITIVE-GYM-C01-STOPPED-CYCLE-90"
    put(stopped / "records/stopped-result.json", {"status": "STOPPED_INCOMPLETE_CHEAT_SHEET"})
    (stopped / "REPORT.md").write_text("Truncated teaching preserved.")
    put(root / "GO-COGNITIVE-GYM-C02-BLIND-ASSESSMENT-PREFLIGHT/preflight.json", {"status": "PRE_FLIGHT_BLOCKED", "executed": 0, "cognitive_measurement_run": False})
    return root


def test_records_drive_all_bars_and_separate_tracks(evidence):
    data = scan(evidence)
    assert [b["code"] for b in data["bars"]] == [f"C{i:02}" for i in range(1, 29)]
    assert data["bars"][0]["status"] == "DEVELOPMENT ONLY"
    assert data["bars"][1]["status"] == "UNTESTED"
    assert data["metrics"]["GOtex interventions"] == 1
    assert data["metrics"]["Assessments run"] == 0
    assert any(s["kind"] == "STOPPED / DEFECT" for s in data["sessions"])
    apprentice = next(e for e in data["events"] if e["actor"] == "GOTEX")
    assert apprentice["causation"] == "NOT ESTABLISHED" and apprentice["aligned"] is True
    path = next(evidence.glob("*91")) / "records/next-developmental-move.json"
    put(path, {"next_move": "CHANGE DISTRACTOR TYPE"})
    assert scan(evidence)["bars"][0]["next_move"] == "CHANGE DISTRACTOR TYPE"


def test_read_is_nonmutating_and_no_fake_promotion(evidence):
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in evidence.rglob("*") if p.is_file()}
    data = scan(evidence)
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in before.items())
    assert set(before) == {p for p in evidence.rglob("*") if p.is_file()}
    assert all(b["status"] not in ("RELIABLE AT THIS LEVEL", "TRANSFERRED") for b in data["bars"])
    assert not any(k in json.dumps(data) for k in ('"iq"', '"mastery_percent"', '"intelligence_score"'))


def test_missing_corrupt_and_unrecognized_evidence(tmp_path, evidence):
    assert len(scan(tmp_path / "missing")["bars"]) == 28
    path = next(evidence.glob("*91")) / "records/go9-result.json"
    path.write_text("{broken")
    data = scan(evidence)
    assert data["issues"] and not any(e["phase"] == "go9" for e in data["events"])
    put(path, {"unrecognized": True})
    assert next(s for s in scan(evidence)["sessions"] if s["identity"].endswith("91"))
    put(path, {"phase": "go9", "raw": "{}", "usage": []})
    assert scan(evidence)["issues"]


def test_legacy_policy_string_teacher_reference_is_valid(evidence):
    folder = next(evidence.glob("*91"))
    put(folder / "examiner/policy.json", {"teacher_action": "teaching-action-1", "state": {}})
    assert not scan(evidence)["issues"]


def test_assessment_transfer_and_governed_status_need_explicit_records(evidence):
    folder = next(evidence.glob("*91"))
    put(folder / "records/capability-status.json", {"status": "RELIABLE AT THIS LEVEL", "authorized": False})
    assert scan(evidence)["bars"][0]["status"] == "DEVELOPMENT ONLY"
    put(folder / "records/assessment-record.json", {"mode": "ASSESSMENT", "execution_valid": True, "completed": True})
    put(folder / "records/transfer-record.json", {"executed": True, "source_realm": "SHAPES", "destination_realm": "NUMBERS"})
    data = scan(evidence)
    assert data["metrics"]["Assessments run"] == data["metrics"]["Transfer activities"] == 1
    assert data["bars"][0]["status"] == "DEVELOPMENT ONLY"


def test_snapshot_fallback_and_corrupt_snapshot(tmp_path, evidence):
    put(tmp_path / "cognitive_gym/projection.json", scan(evidence))
    cfg = {"COGNITIVE_GYM_EVALUATOR_ROOT": str(tmp_path / "absent")}
    assert "snapshot" in dashboard(cfg, tmp_path)["source"]
    (tmp_path / "cognitive_gym/projection.json").write_text("bad")
    assert dashboard(cfg, tmp_path)["issues"]


@pytest.fixture
def app(evidence):
    from app import create_app
    application = create_app("testing")
    application.config["COGNITIVE_GYM_EVALUATOR_ROOT"] = str(evidence)
    return application


@pytest.mark.parametrize("role,developer,expected", [(None, False, 302), ("read_only", True, 403), ("admin", False, 403), ("admin", True, 200)])
def test_authorization(app, role, developer, expected):
    client = app.test_client()
    if role:
        with client.session_transaction() as session:
            session.update(user_id=1, username="gym-reviewer", role=role, developer_mode=developer)
    response = client.get("/admin/cognitive-gym")
    assert response.status_code == expected
    if expected == 200:
        assert response.headers["Cache-Control"] == "private, no-store"
        html = response.get_data(as_text=True)
        assert html.count('data-bar="C') == 28
        assert 'data-track="gotex"' in html
        assert 'STOPPED / DEFECT' in html and 'Exact authored sheet' in html
        assert 'gym-board-scroll' in html and 'Current training focus' in html
        assert client.post("/admin/cognitive-gym").status_code in (400, 405)


def test_output_is_escaped_and_credentials_redacted(app, evidence):
    path = next(evidence.glob("*91")) / "records/cheat-result.json"
    put(path, {"phase": "cheat", "raw": '<script>alert(1)</script> sk-ant-abcdefghijklmnop'})
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1, username="gym", role="admin", developer_mode=True)
    html = client.get("/admin/cognitive-gym").get_data(as_text=True)
    assert '<script>alert(1)</script>' not in html and 'sk-ant-abcdefghijklmnop' not in html
    assert '&lt;script&gt;' in html


def test_mobile_styles_are_bounded():
    css = (Path(__file__).resolve().parents[1] / "static/css/cognitive_gym.css").read_text()
    assert '@media(max-width:700px)' in css and 'overflow:auto' in css
    assert 'grid-template-columns:repeat(3,minmax(0,1fr))' in css
