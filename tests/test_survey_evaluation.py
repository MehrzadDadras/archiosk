"""Evaluation must invoke real owners while keeping customer registries untouched."""
import pytest
from flask import Flask
from services import survey_evaluation as evaluation
from services.case_workspace import CaseWorkspaceError
from pathlib import Path
from types import SimpleNamespace


def row(report, label):
    return next(value for value in report["rows"] if value["label"] == label)


@pytest.fixture
def evaluation_app(tmp_path):
    app = Flask(__name__, instance_path=str(tmp_path / "evaluation-instance"))
    app.config.update(TESTING=True, REGISTRY_STORE_PATH=str(tmp_path / "customer-registry"))
    return app


@pytest.mark.parametrize("case", [case for case in evaluation.CASES if case not in evaluation.REVIEW_GAMES and case not in evaluation.MATCHING_GAMES])
def test_real_case_roundtrip(evaluation_app, case):
    run_id = evaluation.create(evaluation_app, case, "evaluation reviewer")
    report = evaluation.inspect(evaluation_app, run_id)
    assert report["record"]["origin"] == "EVALUATION_INPUT"
    assert report["evidence"] and report["rows"]
    assert report["svg"]
    assert not Path(evaluation_app.config["REGISTRY_STORE_PATH"]).exists()
    evaluation.action(evaluation_app, run_id, "confirm", "evaluation reviewer")
    reloaded = evaluation.inspect(evaluation_app, run_id)
    assert reloaded["record"]["history"][-1]["action"] == "confirm"
    assert (evaluation.location(evaluation_app, run_id) / "reference.pdf").read_bytes().startswith(b"%PDF")


@pytest.mark.parametrize("case,expected", [("homography","IFC_EXPORTABLE"),("no-h","REFUSED"),
    ("singular","REFUSED"),("ill-conditioned","REFUSED"),("infinity","REFUSED"),
    ("space-mismatch","REFUSED"),("projective","REFUSED"),("non-finite","REFUSED"),("polygon","REFUSED")])
def test_governed_geometry_admission(evaluation_app, case, expected):
    identifier=evaluation.create(evaluation_app,case,"reviewer")
    before=evaluation.inspect(evaluation_app,identifier)
    assert row(before,"Governed IFC path")["raw_state"]=="REFUSED"
    evaluation.action(evaluation_app,identifier,"confirm","reviewer")
    after=evaluation.inspect(evaluation_app,identifier)
    assert row(after,"Governed IFC path")["raw_state"]==expected
    if case=="homography":
        assert after["record"]["kernel"]["round_trip"]["value"]==pytest.approx([2,3])
        for operation in ("validation","inverse","composition","line","round_trip"):
            assert row(after,"Reviewed kernel evidence: "+operation)["raw_state"]=="ESTABLISHED"
    else:
        assert not (evaluation.location(evaluation_app,identifier)/"governed.ifc").exists()
        assert after["result"]["not_established"]


@pytest.mark.parametrize("case,expected",[("north","ESTABLISHED"),("ambiguous-north","UNRESOLVED")])
def test_north_is_independently_measured(evaluation_app,case,expected):
    report=evaluation.inspect(evaluation_app,evaluation.create(evaluation_app,case,"reviewer"))
    result=row(report,"True North")["value"]
    assert result["state"]==expected
    assert all(candidate["measured_ok"] for candidate in result["candidates"])


def test_blurred_fields_preserve_view_without_filename_identity(evaluation_app):
    report=evaluation.inspect(evaluation_app,evaluation.create(evaluation_app,"unreadable","reviewer"))
    readings=report["rows"][0]["value"]
    assert readings
    fields=readings[0]["fields"]
    assert fields["sheet_number"]["certainty"]=="UNRESOLVED"
    assert fields["sheet_number"]["value"] is None


@pytest.mark.parametrize("case,endpoint",[("supersession","evidence_item"),("whole-source","source")])
def test_human_accepted_scoped_lineage(evaluation_app,case,endpoint):
    identifier=evaluation.create(evaluation_app,case,"reviewer")
    assert not evaluation.inspect(evaluation_app,identifier)["supersessions"]
    evaluation.action(evaluation_app,identifier,"accept","reviewer")
    assert not evaluation.inspect(evaluation_app,identifier)["supersessions"]
    evaluation.action(evaluation_app,identifier,"apply","reviewer")
    links=evaluation.inspect(evaluation_app,identifier)["supersessions"]
    assert len(links)==1 and links[0]["predecessor_type"]==endpoint
    assert links[0]["successor_type"]==endpoint


def test_missing_predecessor_cannot_be_applied(evaluation_app):
    identifier=evaluation.create(evaluation_app,"missing-predecessor","reviewer")
    with pytest.raises(CaseWorkspaceError):
        evaluation.action(evaluation_app,identifier,"accept","reviewer")
    assert not evaluation.inspect(evaluation_app,identifier)["supersessions"]


@pytest.mark.parametrize("case,expected",[("datum","GOVERNING_DATUM_ESTABLISHED"),("no-authority","APPLICABILITY_UNRESOLVED")])
def test_authority_is_independent_of_street_geometry(evaluation_app,case,expected):
    identifier=evaluation.create(evaluation_app,case,"reviewer")
    evaluation.action(evaluation_app,identifier,"confirm","reviewer")
    assert row(evaluation.inspect(evaluation_app,identifier),"Centerline / governing datum")["raw_state"]==expected


def test_existing_ask_go_rejects_provider_strengthening(evaluation_app,monkeypatch):
    from services import llm_gateway
    calls=[]
    def provider(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(ran=True,parsed={"answer":"The certified height is 10 metres."})
    monkeypatch.setattr(llm_gateway,"call_llm_json",provider)
    evaluation_app.config["ANTHROPIC_API_KEY"]="test-only"
    identifier=evaluation.create(evaluation_app,"non-finite","reviewer")
    evaluation.action(evaluation_app,identifier,"confirm","reviewer")
    evaluation.action(evaluation_app,identifier,"ask","reviewer","What is the height?")
    report=evaluation.inspect(evaluation_app,identifier)
    answer=report["record"]["answer"]
    assert answer["qualification_preserved"]
    assert "Height could not be established" in answer["answer"]
    assert "certified height is 10" not in answer["answer"]
    assert "certified height is 10" in answer["proposed_answer"]
    assert calls[0]["user_prompt"]==report["record"]["answer_context"]


def test_binding_qualification_reaches_drawing(evaluation_app):
    report=evaluation.inspect(evaluation_app,evaluation.create(evaluation_app,"survey","reviewer"))
    primitives=row(report,"Actual Survey Reference drawing")["value"]["primitives"]
    qualified=[p for p in primitives if "[BINDING PARTIALLY_RECOVERED]" in p.get("tags", [])]
    assert qualified
    assert all(not p["certain"] and p["provenance"]==evaluation.sg.PROVENANCE_OBSERVED for p in qualified)


@pytest.mark.parametrize("case,label,expected",[("access","Public access / not legal frontage","PRIMARY_PUBLIC_ACCESS"),
    ("history","Historical / current dimension","RECOVERED"),("conflict","Historical / current dimension","UNRESOLVED"),
    ("open-parcel","Subject property containment","UNRESOLVED"),("binding","Subject property containment","UNRESOLVED")])
def test_professional_review_states(evaluation_app,case,label,expected):
    identifier=evaluation.create(evaluation_app,case,"reviewer")
    evaluation.action(evaluation_app,identifier,"confirm","reviewer")
    report=evaluation.inspect(evaluation_app,identifier)
    assert row(report,label)["raw_state"]==expected
    if case=="conflict": assert row(report,"Active counterevidence")["state"]=="CONFLICT"


def test_expected_absent_then_arrived(evaluation_app):
    identifier=evaluation.create(evaluation_app,"missing-sheet","reviewer")
    label="Expected-but-absent sheet / retained history"
    assert row(evaluation.inspect(evaluation_app,identifier),label)["value"]
    original={e["id"] for e in evaluation.inspect(evaluation_app,identifier)["evidence"]}
    evaluation.action(evaluation_app,identifier,"arrival","reviewer")
    report=evaluation.inspect(evaluation_app,identifier)
    assert row(report,label)["value"]==[]
    assert original.issubset({e["id"] for e in report["evidence"]})


def test_stale_ifc_artifact_never_authorizes_download(web_app):
    client=web_app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1,username="reviewer",role="admin",developer_mode=True)
    identifier=evaluation.create(web_app,"no-h","reviewer")
    (evaluation.location(web_app,identifier)/"governed.ifc").write_text("stale prior export")
    assert client.get("/admin/survey-evaluation/"+identifier+"/artifact/governed.ifc").status_code==404


def test_existing_non_evaluation_ask_boundary_also_preserves_calculated_refusal(evaluation_app,monkeypatch):
    from services import llm_gateway, document_conversation
    monkeypatch.setattr(llm_gateway,"call_llm_json",lambda **kwargs:SimpleNamespace(ran=True,parsed={"answer":"Height is established at 10 metres."}))
    evaluation_app.config["ANTHROPIC_API_KEY"]="test-only"
    identifier=evaluation.create(evaluation_app,"non-finite","reviewer")
    report=evaluation.inspect(evaluation_app,identifier)
    path=evaluation.location(evaluation_app,identifier)
    store=evaluation.CaseWorkspaceStore(str(path/"registry"))
    workspace=store.get(report["record"]["project_id"])
    document=SimpleNamespace(project_id=workspace.project_id,filename=workspace.sources[0]["name"])
    with evaluation.isolated(evaluation_app,path) as app:
        answer=document_conversation.ask(document,workspace,report["result"],"What height?",app=app)
    assert answer["reason"]=="governed_geometry_admission"
    assert "Height could not be established" in answer["answer"]
    assert "Height is established at 10" not in answer["answer"]


def test_mutations_require_existing_csrf(tmp_path,monkeypatch):
    import config
    from app import create_app
    monkeypatch.setattr(config.TestingConfig,"WTF_CSRF_ENABLED",True)
    web_app=create_app("testing")
    web_app.instance_path=str(tmp_path/"csrf")
    client=web_app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1,username="reviewer",role="admin",developer_mode=True)
    assert client.post("/admin/survey-evaluation",data={"case":"survey"}).status_code==302
    assert not evaluation.root(web_app).exists()


@pytest.fixture
def web_app(tmp_path):
    from app import create_app
    app=create_app("testing")
    app.instance_path=str(tmp_path / "web")
    app.config.update(SECRET_KEY="evaluation-tests",WTF_CSRF_ENABLED=False)
    return app


@pytest.mark.parametrize("role,developer,status",[(None,False,302),("customer",True,403),("admin",False,403),("admin",True,200)])
def test_admin_developer_boundary(web_app,role,developer,status):
    client=web_app.test_client()
    if role:
        with client.session_transaction() as session:
            session.update(user_id=1,username="reviewer",role=role,developer_mode=developer)
    assert client.get("/admin/survey-evaluation").status_code==status
    if status!=200:
        assert client.post("/admin/survey-evaluation",data={"case":"homography"}).status_code==status
        assert not evaluation.root(web_app).exists()


def test_real_surface_and_artifacts(web_app):
    client=web_app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1,username="reviewer",role="admin",developer_mode=True)
    response=client.post("/admin/survey-evaluation",data={"case":"homography"})
    assert response.status_code==302
    url=response.headers["Location"]
    response=client.get(url)
    assert response.status_code==200
    html=response.get_data(as_text=True)
    assert "EVALUATION_INPUT" in html and "REFUSED" in html and "survey_evaluation.css" in html
    assert response.headers["Cache-Control"]=="private, no-store"
    assert client.get(url+"/artifact/governed.ifc").status_code==404
    assert client.post(url,data={"action":"confirm"}).status_code==302
    assert client.get(url).status_code==200
    for name,prefix in (("source.pdf",b"%PDF"),("reference.pdf",b"%PDF"),("governed.ifc",b"ISO-10303")):
        artifact=client.get(url+"/artifact/"+name)
        assert artifact.status_code==200 and artifact.data.startswith(prefix)
    assert client.get(url+"/artifact/run.json").status_code==404
