"""Read-only diagnostic UI boundaries and evidence integrity."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from services.operational_frontier import snapshot
from services.operational_flight_deck import dashboard


def seal(data):
    data.pop("sha256", None)
    data["sha256"] = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return data


@pytest.fixture
def feed(tmp_path):
    data = snapshot({"records": [], "projection_sha256": "fixture"}, tmp_path, Path(__file__).resolve().parents[1])
    path = tmp_path / "convergence/frontier.json"
    path.parent.mkdir()
    path.write_text(json.dumps(data), encoding="utf-8")
    return path, data


@pytest.fixture
def app(tmp_path, feed):
    from app import create_app
    application = create_app("testing")
    application.config.update(SECRET_KEY="flight-deck-tests", COGNITIVE_GYM_EVALUATOR_ROOT=str(tmp_path / "absent"))
    application.instance_path = str(tmp_path)
    return application


@pytest.mark.parametrize("role,developer,expected", [(None, False, 302), ("customer", True, 403), ("admin", False, 403), ("admin", True, 200)])
def test_existing_authorization_only(app, role, developer, expected):
    client = app.test_client()
    if role:
        with client.session_transaction() as session:
            session.update(user_id=1, username="reviewer", role=role, developer_mode=developer)
    response = client.get("/admin/operational-convergence")
    assert response.status_code == expected
    if expected == 200:
        assert response.headers["Cache-Control"] == "private, no-store"
        html = response.get_data(as_text=True)
        assert 'data-operation="op.datum-corroboration"' in html
        assert "Historical state" in html and "Product decisions / unresolved" in html
        assert "Cognitive Gym / AI Learning Lab" in html
        assert client.post("/admin/operational-convergence").status_code in (400, 405)


def test_unauthorized_request_does_not_read_feed(app, monkeypatch):
    monkeypatch.setattr("services.operational_flight_deck.dashboard", lambda *args: pytest.fail("unauthorized feed read"))
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1, role="customer", developer_mode=True)
    assert client.get("/admin/operational-convergence").status_code == 403


def test_snapshot_integrity_missing_and_ineligible_degrade_safely(tmp_path, feed):
    path, data = feed
    cfg = {"COGNITIVE_GYM_EVALUATOR_ROOT": str(tmp_path / "absent")}
    assert dashboard(cfg, tmp_path)["available"]
    data["capabilities"][0]["go_state"] = "RELIABLE FOR THIS OPERATION"
    path.write_text(json.dumps(data))
    assert not dashboard(cfg, tmp_path)["available"]
    data["ui_eligible"] = False
    path.write_text(json.dumps(seal(data)))
    assert not dashboard(cfg, tmp_path)["available"]
    path.write_text("{broken")
    assert not dashboard(cfg, tmp_path)["available"]
    path.unlink()
    assert not dashboard(cfg, tmp_path)["available"]


def test_no_mutation_no_promotion_and_facets_remain_separate(tmp_path, feed):
    path, data = feed
    before = path.read_bytes()
    cfg = {"COGNITIVE_GYM_EVALUATOR_ROOT": str(tmp_path / "absent")}
    a = dashboard(cfg, tmp_path)
    assert a == dashboard(cfg, tmp_path) and path.read_bytes() == before
    assert not a["shared"]
    datum = next(r for r in a["rows"] if r["capability_id"] == "op.datum-corroboration")
    assert datum["application_facets"]["reachable"] is True
    assert datum["application_facets"]["trainable"] is False
    assert datum["state_transitions"][0]["from_facets"]["reachable"] is False
    assert not any(key in json.dumps(a) for key in ('"iq"', '"intelligence_score"', '"mastery_percent"'))


def test_invalid_response_inspection_escaped_and_credentials_redacted(app, feed):
    path, data = feed
    row = next(r for r in data["capabilities"] if r["capability_id"] == "op.supersession-behaviour")
    row["observations"] = [{"control": "NULL_TARGET", "contract_compliance": "INVALID", "timestamp": "UNRESOLVED",
        "record_id": "example-result.json", "task_content": {"scoring": "UNSCORED"}, "instrument_validity": "VALID",
        "application_defect": "NONE", "raw_response": '<script>unsafe()</script> sk-ant-abcdefghijklmnop'}]
    path.write_text(json.dumps(seal(data)))
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1, role="admin", developer_mode=True)
    html = client.get("/admin/operational-convergence").get_data(as_text=True)
    assert "UNSCORED" in html and "INVALID" in html and "&lt;script&gt;" in html
    assert "<script>unsafe()" not in html and "sk-ant-abcdefghijklmnop" not in html


def test_mobile_and_readonly_navigation():
    repo = Path(__file__).resolve().parents[1]
    css = (repo / "static/css/operational_flight_deck.css").read_text()
    js = (repo / "static/js/operational_flight_deck.js").read_text()
    assert "@media(max-width:700px)" in css and ".fd-empty{display:none}" in css
    assert "grid-template-columns:1fr" in css and "overflow:auto" in css
    assert "fetch(" not in js and "localStorage" not in js
    assert "panel.open = true" in js
