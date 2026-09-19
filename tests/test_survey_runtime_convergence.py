"""Consumer contracts, real route invocation and absence of authority laundering."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from flask import Flask
from services import survey_evaluation as evaluation
from services.case_workspace import CaseWorkspaceStore
from engine import spatial_compiler as geometry
from engine.ifc_volume_validator import IFCVolumeValidator, IFCValidationError


@pytest.fixture
def evaluation_app(tmp_path):
    app = Flask(__name__, instance_path=str(tmp_path))
    app.config["REGISTRY_STORE_PATH"] = str(tmp_path/"customer-registry")
    return app


@pytest.mark.parametrize("case, expected", [("monument","ESTABLISHED"), ("missing-monument","UNRESOLVED"),
    ("occupation","ESTABLISHED"), ("earned-h","ESTABLISHED"), ("degenerate-controls","DEGENERATE")])
def test_new_operations_persist_review_consume(evaluation_app, case, expected):
    identifier = evaluation.create(evaluation_app, case, "reviewer")
    before = evaluation.inspect(evaluation_app, identifier)
    evidence_id = before["record"]["operation_evidence_id"]
    store = CaseWorkspaceStore(str(evaluation.location(evaluation_app,identifier)/"registry"))
    assert not store.admit_proposition(store.get("evaluation"),evidence_id)["admissible"]
    evaluation.action(evaluation_app,identifier,"confirm","reviewer")
    after = evaluation.inspect(evaluation_app,identifier)
    admission = store.admit_proposition(store.get("evaluation"),evidence_id)
    assert admission["state"] == expected
    assert admission["evaluation_only"]
    assert not store.admit_proposition(store.get("evaluation"),evidence_id,use="canonical_ifc")["admissible"]
    assert any(row.get("evidence_item_id")==evidence_id for group in ("interpretation","not_established") for row in after["result"][group])
    if case == "occupation":
        assert admission["value"] == pytest.approx(.5)
        assert admission["record"]["derivation"]["comparison"] == "DIFFERENCE"
    if case == "earned-h":
        transform = admission["record"]["derivation"]
        assert transform["physical_scale"] == "NOT_ESTABLISHED"
        point=geometry.transform_homogeneous_point(transform,[1,.5,1],point_space="SOURCE_PIXELS",point_plane="survey-plane")
        assert point["value"] == pytest.approx([.5,.5])
        assert point["geometry_level"] == "PROJECTIVE"


def test_homography_invalid_and_roundtrip():
    scope=dict(source_space="SOURCE_PIXELS",target_space="AFFINE_RECTIFIED",source_plane="image",target_plane="frame",geometry_level="PROJECTIVE")
    a=[[0,0],[2,0],[2,1],[0,1]]; b=[[0,0],[1,0],[1,1],[0,1]]
    result=geometry.estimate_control_homography(a,b,**scope)
    assert result["state"]=="ESTABLISHED"
    assert max(result["control_residuals"]) <= geometry.ToleranceContext().round_trip
    for points in ([[0,0]]*4, [[0,0],[1,0],[2,0],[3,0]], [[float("nan"),0],*a[1:]]):
        assert geometry.estimate_control_homography(points,b,**scope)["state"] != "ESTABLISHED"


def test_raw_text_is_not_proposition(evaluation_app):
    store=CaseWorkspaceStore(evaluation_app.config["REGISTRY_STORE_PATH"])
    workspace=store.get_or_create("raw",register_document_source={"filename":"record.txt"})
    evidence=store.register_evidence_item(workspace,workspace.sources[0]["id"],"direct_source_evidence","Height is 10 m","text")
    result=store.admit_proposition(workspace,evidence["id"])
    assert result["state"]=="SOURCE_REFERENCE" and not result["admissible"]


def test_observation_attaches_to_actual_route_and_cannot_grant_authority(tmp_path):
    from app import create_app
    app=create_app("testing");app.instance_path=str(tmp_path)
    app.config.update(SECRET_KEY="test",WTF_CSRF_ENABLED=False,REGISTRY_STORE_PATH=str(tmp_path/"registry"))
    client=app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1,username="reviewer",role="admin",developer_mode=True,survey_observe=True)
    response=client.post("/admin/survey-evaluation",data={"case":"earned-h"})
    assert response.status_code==302
    identifier=response.headers["X-ARCHIOSK-Observation"]
    trace=json.loads((tmp_path/"runtime_observations"/(identifier+".json")).read_text())
    invoked={event["owner"] for event in trace["events"] if event["phase"]=="INVOKED"}
    assert "services.survey_graph.derive_survey_operation" in invoked
    assert "engine.spatial_compiler.estimate_control_homography" in invoked
    assert "services.case_workspace.CaseWorkspaceStore.register_evidence_item" in invoked
    registrations=[event for event in trace["events"] if event["owner"].endswith(".register_evidence_item")]
    assert all("content" not in event.get("inputs",{}) for event in registrations)
    assert any(event.get("result",{}).get("id") for event in registrations if event["phase"]=="RETURNED")
    assert trace["request"]["endpoint"]=="portal.survey_evaluation"
    assert not CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"]).get("evaluation")
    client.post("/admin/survey-evaluation",data={"action":"observe","enabled":"no"})
    response=client.get("/admin/survey-evaluation")
    assert "X-ARCHIOSK-Observation" not in response.headers


def test_canonical_ifc_requires_complete_scoped_current_metric_evidence(evaluation_app):
    from services.survey_evaluation_geometry import candidate_for, evaluation_controls
    model, _, _ = candidate_for(evaluation_controls()["R7-FIN-POS-001"]["inputs"])
    with pytest.raises(IFCValidationError, match="GOVERNED_EVIDENCE_REQUIRED"):
        IFCVolumeValidator().export(model)
    model["length_unit"]="METRE"
    store=CaseWorkspaceStore(evaluation_app.config["REGISTRY_STORE_PATH"])
    workspace=store.get_or_create("canonical",register_document_source={"filename":"controlled-contract-plan.pdf"})
    source=workspace.sources[0];source["document_authority"]="contractual";store.save(workspace)
    store.register_pdf_page_structure(workspace,source["id"],["Recorded metric geometry"])
    unit=workspace.structural_units[0]
    context=dict(coordinate_space="WORLD_SCALED",plane_id="world",geometry_level="METRIC_SCALED",length_unit="METRE",
                 provenance="Explicit reviewed metric test plan",
                 read_certainty="RECOVERED",bind_certainty="RECOVERED",bind_basis="declared")
    for row in model.get("label_containment",[]):
        row["relation"].update(coordinate_space="WORLD_SCALED",plane_id="world")
    identifiers=[]
    def quantities(value,prefix=""):
        if isinstance(value,dict):
            for key,child in value.items():
                if key!="geometry_context":yield from quantities(child,prefix+"."+key if prefix else key)
        elif isinstance(value,list):
            for i,child in enumerate(value):yield from quantities(child,prefix+"."+str(i))
        elif isinstance(value,(float,int)) and not isinstance(value,bool):yield prefix,value
    for collection in ("levels","spaces","walls"):
        for owner in model.get(collection,[]):
            object_id=owner.get("id") or owner["name"]
            owner["geometry_context"]=dict(context)
            region=store.create_addressable_region(workspace,unit["id"],"drawing_region",{"object_id":object_id})
            for field,value in quantities(owner):
                premise=store.register_evidence_item(workspace,source["id"],"direct_source_evidence",json.dumps(dict(context,value=value)),"application/json",region_id=region["id"])
                record=dict(context,state="FINITE",value=value,errors=[],object_id=object_id,field=field,
                    uncertainty={"state":"ESTABLISHED","basis":"Explicit bounded test measurement"},
                    derivation={"operator":"numeric_validity@1"},premise_ids=[premise["id"]],source_evidence_ids=[premise["id"]])
                evidence=store.register_evidence_item(workspace,source["id"],"calculated_value",json.dumps(record),"application/json",region_id=region["id"])
                edge=store.record_evidence_relationship(workspace,"evidence_item",evidence["id"],"evidence_item",premise["id"],"derived_from",provisional=True)
                store.confirm_relationship(workspace,edge["id"],actor="reviewer")
                identifiers.append(evidence["id"])
    output=IFCVolumeValidator().export(model,store=store,workspace=workspace,evidence_ids=identifiers)
    assert output.startswith("ISO-10303-21;")
    assert "IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.)" in output
    model["length_unit"]="FOOT"
    with pytest.raises(IFCValidationError,match="PHYSICAL_UNIT"):
        IFCVolumeValidator().export(model,store=store,workspace=workspace,evidence_ids=identifiers)
    model["length_unit"]="METRE"
    with pytest.raises(IFCValidationError,match="COVERAGE"):
        IFCVolumeValidator().export(model,store=store,workspace=workspace,evidence_ids=identifiers[:-1])
    edge=workspace.relationships[0]
    store.dispute_relationship(workspace,edge["id"],actor="reviewer")
    with pytest.raises(IFCValidationError):
        IFCVolumeValidator().export(model,store=store,workspace=workspace,evidence_ids=identifiers)


def test_workspace_provider_cannot_promote_raw_source(monkeypatch):
    from services import project_qa
    monkeypatch.setattr(project_qa,"call_llm_json",lambda **kw:SimpleNamespace(ran=True,parsed={"answer":"The boundary is legally established."},provider="test",model="test",requested_at="now"))
    documents=[dict(filename="Plan",excerpts=["Fence close to lot line"],proposition_admission=[dict(
        evidence_item_id="e",state="SOURCE_REFERENCE",admissible=False,record={})])]
    result=project_qa.answer_project_question("Boundary?","Plan",[],[],[],additional_document_evidence=documents)
    assert "legally established" not in result.answer
    assert "Source says (reference only)" in result.answer
    assert "Fence close" in result.answer


def test_traverse_and_curve_primitives_never_grant_authority():
    from services import survey_graph as graph, visual_examination as visual
    raw=visual.normalise_payload(evaluation._payload("curve"))["graph"]
    result=graph.build_primitives(raw)
    primitive=next(item for item in result["primitives"] if item.get("id")=="S0")
    assert primitive["state"]=="DISPLAY_APPROXIMATION"
    assert not primitive["certain"] and primitive["authority"]=="UNRESOLVED"
    assert "DISPLAY APPROXIMATION" in graph.emit_svg(result)


def test_traverse_calculation_is_retained_without_establishment(evaluation_app):
    identifier=evaluation.create(evaluation_app,"traverse","reviewer")
    report=evaluation.inspect(evaluation_app,identifier)
    store=CaseWorkspaceStore(str(evaluation.location(evaluation_app,identifier)/"registry"))
    record=json.loads(store.get_evidence_item(store.get("evaluation"),report["record"]["operation_evidence_id"])["content"])
    assert record["derivation"]["calculation"]["computed"]
    assert record["derivation"]["calculation"]["state"]=="CALCULATED_FROM_QUALIFIED_INPUT"
    assert record["state"]=="PARTIALLY_RECOVERED"
    assert record["value"]
    evaluation.action(evaluation_app,identifier,"confirm","reviewer")
    assert not store.admit_proposition(store.get("evaluation"),report["record"]["operation_evidence_id"])["admissible"]


def test_ordinary_project_route_invokes_same_resolver(tmp_path):
    from app import create_app
    from services.bhive_parser import ParsedDocument
    from services.requirements_registry import RequirementsRegistry
    app=create_app("testing");app.instance_path=str(tmp_path)
    app.config.update(SECRET_KEY="test",WTF_CSRF_ENABLED=False,REGISTRY_STORE_PATH=str(tmp_path/"registry"))
    store=CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"])
    workspace=store.get_or_create("live",register_document_source={"filename":"survey.pdf"})
    RequirementsRegistry(store.store_path).save(ParsedDocument("live","survey.pdf","2026-09-19"))
    source_id=workspace.sources[0]["id"]
    store.register_pdf_page_structure(workspace,source_id,["Found M1; recorded M1 at C1"])
    region=store.create_addressable_region(workspace,workspace.structural_units[0]["id"],"drawing_region",{"object_id":"corner"})
    identifiers=[]
    for role in ("recorded_monument","found_monument"):
        content=dict(survey_role=role,subject_id="parcel",monument_id="M1",record_corner_id="C1",point=[1,2],
            coordinate_space="EUCLIDEAN_RECTIFIED",plane_id="plan",geometry_level="EUCLIDEAN",
            read_certainty="RECOVERED",bind_certainty="RECOVERED",bind_basis="declared")
        identifiers.append(store.register_evidence_item(workspace,source_id,"direct_source_evidence",json.dumps(content),"application/json",region_id=region["id"])["id"])
    client=app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1,username="reviewer",role="admin",developer_mode=True,survey_observe=True)
    response=client.post("/projects/live/workspace/survey/derive",data={"region_id":region["id"],"operation":"monument","premise_id":identifiers})
    assert response.status_code==302
    derived=[e for e in store.get("live").evidence_items if e["evidence_class"]=="calculated_value"]
    assert len(derived)==1
    assert not store.admit_proposition(store.get("live"),derived[0]["id"])["admissible"]
    trace=json.loads((tmp_path/"runtime_observations"/(response.headers["X-ARCHIOSK-Observation"]+".json")).read_text())
    assert any(e["owner"]=="services.survey_graph.derive_survey_operation" and e["phase"]=="INVOKED" for e in trace["events"])
    assert trace["request"]["endpoint"]=="workspace.derive_survey_operation"


def test_worker_records_execution_not_just_enqueue(tmp_path):
    from services import runtime_observation as observe, visual_classification as visual
    from services.perception_jobs import PerceptionJobStore
    app=Flask(__name__,instance_path=str(tmp_path));app.secret_key="test"
    app.config["REGISTRY_STORE_PATH"]=str(tmp_path/"registry")
    jobs=PerceptionJobStore(app.config["REGISTRY_STORE_PATH"])
    observe.install(app)
    @app.post("/enqueue")
    def enqueue():
        job=visual.enqueue_for_source(jobs,workspace_id="absent",source_id="absent",source_sha256="digest")
        return {"id":job["job_id"]}
    client=app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1,username="reviewer",role="admin",developer_mode=True,survey_observe=True)
    response=client.post("/enqueue")
    job=jobs.get(response.json["id"])
    assert not any(t["request"]["method"]=="WORKER" for t in observe.recent(app))
    with app.app_context():
        result=visual.examine_source(app,jobs,job)
    trace=next(t for t in observe.recent(app) if t["request"]["method"]=="WORKER")
    assert trace["observed_enqueue_request"]==response.headers["X-ARCHIOSK-Observation"]
    assert any(e["owner"]=="services.visual_classification.examine_source" and e["phase"]=="INVOKED" for e in trace["events"])
    assert result["state"]=="failed"


def test_changed_control_premise_blocks_stored_H(evaluation_app):
    identifier=evaluation.create(evaluation_app,"earned-h","reviewer")
    evaluation.action(evaluation_app,identifier,"confirm","reviewer")
    report=evaluation.inspect(evaluation_app,identifier)
    store=CaseWorkspaceStore(str(evaluation.location(evaluation_app,identifier)/"registry"));workspace=store.get("evaluation")
    evidence_id=report["record"]["operation_evidence_id"]
    record=json.loads(store.get_evidence_item(workspace,evidence_id)["content"])
    premise=store.get_evidence_item(workspace,record["premise_ids"][0])
    altered=json.loads(premise["content"]);altered["point"]=[99,99];premise["content"]=json.dumps(altered);store.save(workspace)
    admission=store.admit_proposition(store.get("evaluation"),evidence_id)
    assert not admission["admissible"] and "PREMISE_CHANGED" in admission["errors"]


@pytest.mark.parametrize("case,operation,field,value,error", [
    ("monument","monument","monument_id","different","MONUMENT_IDENTITY_NOT_ESTABLISHED"),
    ("monument","monument","subject_id","other-parcel","SUBJECT_BINDING_UNESTABLISHED"),
    ("occupation","occupation","coordinate_space","SOURCE_PIXELS","SPACE_OR_PLANE_MISMATCH"),
    ("occupation","occupation","bind_certainty","UNRESOLVED","BINDING_UNESTABLISHED"),
    ("earned-h","rectification","target_frame_evidence_id","missing","AFFINE_FRAME_EVIDENCE_REQUIRED"),
])
def test_derivation_refuses_unearned_premise(evaluation_app,case,operation,field,value,error):
    identifier=evaluation.create(evaluation_app,case,"reviewer")
    report=evaluation.inspect(evaluation_app,identifier)
    store=CaseWorkspaceStore(str(evaluation.location(evaluation_app,identifier)/"registry"))
    workspace=store.get("evaluation")
    prior=store.get_evidence_item(workspace,report["record"]["operation_evidence_id"])
    record=json.loads(prior["content"])
    identifiers=record["premise_ids"][:4] if operation=="rectification" else record["premise_ids"]
    premise=store.get_evidence_item(workspace,identifiers[-1])
    payload=json.loads(premise["content"]);payload[field]=value;premise["content"]=json.dumps(payload);store.save(workspace)
    result=evaluation.sg.derive_survey_operation(store,workspace,source_id=prior["source_id"],region_id=prior["region_id"],
        object_id=record["object_id"],operation=operation,premise_ids=identifiers,actor="reviewer")
    derived=json.loads(result["content"])
    assert derived["state"]=="UNRESOLVED" and error in derived["errors"]
    assert derived["value"] is None
