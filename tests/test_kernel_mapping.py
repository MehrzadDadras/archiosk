"""Stage 1: real routes, existing records, no stronger state or new persistence."""
import json
from dataclasses import asdict

import pytest

from services.case_workspace import CaseWorkspaceStore
from services import survey_evaluation as evaluation


@pytest.fixture
def project(tmp_path):
    from app import create_app
    from services.bhive_parser import ParsedDocument
    from services.requirements_registry import RequirementsRegistry
    app = create_app("testing")
    app.instance_path = str(tmp_path)
    app.config.update(SECRET_KEY="test", WTF_CSRF_ENABLED=False,
                      REGISTRY_STORE_PATH=str(tmp_path / "registry"))
    store = CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"])
    workspace = store.get_or_create("project", register_document_source={"filename": "survey.pdf"})
    workspace.owner = "reviewer"
    store.save(workspace)
    RequirementsRegistry(store.store_path).save(ParsedDocument("project", "survey.pdf", "2026-09-19"))
    source = workspace.sources[0]
    evidence = store.register_evidence_item(workspace, source["id"], "direct_source_evidence",
        "Readable prose is not governed truth <script>alert(1)</script>", "text")
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1, username="reviewer", role="admin", developer_mode=True, survey_observe=True)
    return app, store, workspace, evidence, client


def test_route_invokes_owned_admission_consumes_and_surfaces_without_writing(project):
    app, store, workspace, evidence, client = project
    before = store._path_for(workspace.project_id).read_bytes()
    response = client.get("/projects/project/kernel", query_string={"item": "evidence_items:" + evidence["id"]})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "SOURCE_REFERENCE" in html and "NOT_ESTABLISHED" in html
    assert r"\u003cscript\u003ealert(1)\u003c/script\u003e" in html
    assert '<script>alert(1)</script>' not in html
    assert evidence["source_id"] in html and evidence["id"] in html
    # SUPERSEDED DELIBERATELY (MASTERUI cutover): the page-local "Reload view"
    # widget is retired; the page itself is the Master Workspace.
    assert 'data-master-shell="on"' in html
    # (The retired Reload form's hidden inputs preserved the selected item; it is
    # gone with the widget. The item itself is still rendered - asserted above.)
    assert store._path_for(workspace.project_id).read_bytes() == before
    from services.runtime_observation import read
    trace = read(app, response.headers["X-ARCHIOSK-Observation"])
    owners = {e["owner"] for e in trace["events"] if e["phase"] == "INVOKED"}
    for method in ("inspect_kernel_mapping", "admit_proposition", "explain_evidence_trust", "resolve_anchor_currentness"):
        assert "services.case_workspace.CaseWorkspaceStore." + method in owners
    assert any(e["phase"] == "CONSUMED" and e["owner"] == "kernel_mapping.html" for e in trace["events"])
    assert trace["events"][-1]["phase"] == "SURFACED"
    assert "private, no-store" == response.headers["Cache-Control"]


@pytest.mark.parametrize("role,developer,expected", [(None, False, 302), ("read_only", True, 403), ("admin", False, 403)])
def test_admin_developer_gates(project, role, developer, expected):
    _, _, _, _, client = project
    with client.session_transaction() as session:
        session.clear()
        if role:
            session.update(user_id=1, username="reviewer", role=role, developer_mode=developer)
    assert client.get("/projects/project/kernel").status_code == expected


def test_foreign_unknown_and_removed_project_refused(project):
    _, store, workspace, _, client = project
    assert client.get("/projects/missing/kernel").status_code == 404
    assert client.get("/projects/project/kernel?item=evidence_items:foreign").status_code == 404
    workspace.removed_at = "2026-09-19"
    store.save(workspace)
    response = client.get("/projects/project/kernel")
    assert response.status_code == 302
    assert "/workspace" in response.headers["Location"]


def test_private_case_refuses_project_inspection_including_indirect_references(project):
    _, store, workspace, evidence, client = project
    store.create_case(workspace, "private secret", "secret objective", created_by="someone-else")
    response = client.get("/projects/project/kernel", query_string={"item": "evidence_items:" + evidence["id"]})
    assert response.status_code == 403
    html = response.get_data(as_text=True)
    assert "REFUSED" in html
    # Reload may echo the caller's submitted item ID, never protected records.
    assert "secret objective" not in html and "private secret" not in html
    assert evidence["source_id"] not in html and 'id="kernel-record"' not in html


def test_mapping_reads_changes_and_preserves_record_and_qualification(project):
    _, store, workspace, evidence, _ = project
    before = asdict(workspace)
    report = store.inspect_kernel_mapping(workspace, "reviewer", "evidence_items:" + evidence["id"])
    assert asdict(workspace) == before
    assert report["selected"]["record"] == evidence
    assert report["selected"]["governed"] == store.admit_proposition(workspace, evidence["id"])
    workspace.sources[0]["name"] = "Actual changed source"
    report = store.inspect_kernel_mapping(workspace, "reviewer", "sources:" + workspace.sources[0]["id"])
    assert report["selected"]["record"]["name"] == "Actual changed source"
    assert report["selected"]["governed"] is None


def test_exact_references_and_provisional_relationship_preserved(project):
    _, store, workspace, evidence, _ = project
    source = workspace.sources[0]
    edge = store.record_relationship(workspace, "source", source["id"], "evidence_item", evidence["id"], "supports")
    before = asdict(workspace)
    report = store.inspect_kernel_mapping(workspace, "reviewer", "evidence_items:" + evidence["id"])
    assert report["selected"]["relationships"][0]["resolved"] == store.resolve_relationship_status(workspace, edge["id"])
    assert report["selected"]["relationships"][0]["record"]["provisional"]
    assert any(c["id"] == edge["id"] and "to_id" in c["reference_fields"] for c in report["selected"]["consumers"])
    assert report["selected"]["governed"]["state"] == "SOURCE_REFERENCE"
    assert asdict(workspace) == before


@pytest.mark.parametrize("case", ["earned-h", "missing-monument", "traverse"])
def test_evaluation_uses_same_mapping_and_admission_without_customer_writes(project, case):
    app, customer_store, customer, _, client = project
    before = customer_store._path_for(customer.project_id).read_bytes()
    identifier = evaluation.create(app, case, "reviewer")
    path = evaluation.location(app, identifier)
    record = evaluation._read(path)
    store = CaseWorkspaceStore(str(path / "registry"))
    workspace = store.get(record["project_id"])
    evidence_id = record["operation_evidence_id"]
    expected = store.admit_proposition(workspace, evidence_id)
    evaluation_before = store._path_for(workspace.project_id).read_bytes()
    response = client.get(f"/admin/survey-evaluation/{identifier}/kernel", query_string={"item": "evidence_items:" + evidence_id})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "EVALUATION_INPUT" in html and expected["state"] in html
    assert expected["evaluation_only"]
    assert store._path_for(workspace.project_id).read_bytes() == evaluation_before
    assert customer_store._path_for(customer.project_id).read_bytes() == before


def test_no_items_unknown_evaluation_and_mapping_gaps(project):
    _, store, workspace, _, client = project
    workspace.sources.clear()
    workspace.evidence_items.clear()
    report = store.inspect_kernel_mapping(workspace, "reviewer")
    assert report["selected"] is None and report["items"] == []
    assert "AnalysisRun.attention_scope" in dict(report["concepts"])["Attention Scope"]
    assert "GAP:" in dict(report["concepts"])["Temporary Analytical Relationship"]
    assert client.get("/admin/survey-evaluation/unknown/kernel").status_code == 404
