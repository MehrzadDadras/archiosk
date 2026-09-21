"""Admin evaluation orchestration over existing Survey owners.

All writes are confined to a separate registry per run. There is no promotion
or customer-project input API. Controlled premises are never canonical facts.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import re
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from flask import Flask
from services.case_workspace import CaseWorkspaceStore
from services import binding, document_examination as dx, document_conversation as dc
from services import survey_graph as sg, survey_reference as sr, visual_examination as vx
from services.survey_evaluation_geometry import evaluation_controls
from services.runtime_observation import observed

CASES = {
    "source-review": "Photographed document frame and anchored transcription review",
    "traverse": "Calculated relative traverse retains qualified premises",
    "monument": "Declared monument correspondence, not legal authority",
    "missing-monument": "Expected monument absent: no invented replacement",
    "occupation": "Observed fence versus record line: geometric difference only",
    "earned-h": "Calculated H from four addressed correspondence premises",
    "degenerate-controls": "Collinear control points: rectification refused",
    "survey": "Situated parcel, building and qualified dimensions",
    "unreadable": "Unreadable title block: the view must survive",
    "binding": "Readable dimension, missing binding",
    "history": "Historical and newer measurement: review precedence",
    "conflict": "Conflicting measurement evidence",
    "missing-sheet": "Expected sheet absent, then supplied",
    "supersession": "Scoped clause replacement: propose, review, apply",
    "missing-predecessor": "Replacement with no predecessor",
    "whole-source": "Explicit whole-document replacement",
    "north": "Independently measured True North",
    "ambiguous-north": "Conflicting True North observations",
    "open-parcel": "Open parcel: no invented closing edge",
    "curve": "Historical curve notation: unresolved metric placement",
    "access": "Reviewed public access, not legal frontage",
    "datum": "Governing datum: independently reviewed evaluation authority",
    "no-authority": "Street geometry without governing authority",
    "homography": "Explicit evaluation homography",
    "no-h": "No homography: no invented rectification",
    "singular": "Singular homography refusal",
    "ill-conditioned": "Ill-conditioned homography refusal",
    "infinity": "Homogeneous w = 0 refusal",
    "space-mismatch": "Coordinate-space mismatch refusal",
    "projective": "Projective result cannot authorize Euclidean IFC",
    "non-finite": "Non-finite height: governed IFC refusal",
    "projection": "Finite segment projection",
    "polygon": "Invalid polygon refusal",
    "missing-primitives": "Remaining limits: automatic controls and professional certification",
}
CONTROLS=evaluation_controls()
REVIEW_GAMES = {
    'review:readable-mirror': dict(title='Native annotations remain readable in a derived mirrored view', native_annotations=True),
    'review:orphan': dict(title='Required detail has no upstream connection', expectation='upstream'),
    'review:independent': dict(title='Independent information needs no continuum connection', expectation='independent'),
    'review:essential': dict(title='Unique required representation', conditions=1, representation=True),
    'review:typical': dict(title='One applicable typical section covers two conditions', conditions=2, representation=True),
    'review:section-gap': dict(title='Materially distinct condition has no section', conditions=1),
    'review:discipline-gap': dict(title='Section exists but affected discipline is missing', conditions=1, representation=True, missing_discipline=True),
    'review:specification-gap': dict(title='Specification clause has no downstream manifestation', expectation='downstream', representation_class='SPECIFICATION'),
    'review:drawing-support-gap': dict(title='Drawing condition lacks required specification support', expectation='upstream', conditions=1),
    'review:constraint-closes': dict(title='Cross-document scalar constraints have a common interval', constraints=('90','110','95','105')),
    'review:constraint-conflict': dict(title='Cross-document scalar constraints have no common interval', constraints=('90','94','95','105')),
    'review:breakpoint': dict(title='Controlled variation reaches the first limiting constraint', constraints=('90','110','95','105')),
    'review:physical-path-gap': dict(title='Labelled air control lacks a recorded continuity path', conditions=1, physical=True),
}
CASES.update({key: value['title'] for key, value in REVIEW_GAMES.items()})
MATCHING_GAMES = {
    'matching:construction': dict(title='Construction: required and represented assembly layers', matching='domain', context='construction', property_key='assembly_layers', tokens=['AIR_CONTROL', 'DRAINAGE']),
    'matching:rfp': dict(title='RFP: required discipline and company capability', matching='domain', context='rfp', property_key='discipline', tokens=['STRUCTURAL']),
    'matching:asset': dict(title='Asset: deterioration control and proposed intervention', matching='domain', context='asset', property_key='control_function', tokens=['DRAINAGE']),
    'matching:fit': dict(title='Capital alignment: all declared predicates fit, factual authority unresolved', matching='fit'),
    'matching:partial': dict(title='Capital alignment: one match and missing geographic evidence', matching='partial'),
    'matching:known-partial': dict(title='Known optional geographic preference mismatch; mandatory criteria match', matching='known_partial'),
    'matching:mandatory-failure': dict(title='Capital alignment: capital fits but mandatory sector fails', matching='mandatory_failure'),
    'matching:historical': dict(title='Historical activity does not establish a current mandate', matching='historical'),
    'matching:repeated-claim': dict(title='Repeated reporting does not establish investor authority', matching='repeated'),
    'matching:missing-provenance': dict(title='Unanchored candidate claim cannot supply matching evidence', matching='missing'),
    'matching:composition': dict(title='Two entities jointly cover equity and debt roles without capital summation', matching='composition'),
    'matching:brief': dict(title='Capital Alignment Brief preserves missing evidence and unresolved authority', matching='brief'),
    'matching:coverage-one': dict(title='One participant covers all mandatory roles; factual status unresolved', matching='coverage_one'),
    'matching:coverage-two': dict(title='Two-party minimum coverage with partnership compatibility unresolved', matching='coverage_two'),
    'matching:coverage-three': dict(title='Three roles require three participants; no pair is sufficient', matching='coverage_three'),
    'matching:coverage-alternatives': dict(title='Equal minimum configurations and redundant selected coverage', matching='coverage_alternatives'),
    'matching:additive-capital': dict(title='Explicit additive capacity basis closes conditional capital coverage', matching='additive_capital'),
    'matching:additive-unresolved': dict(title='Partial amounts cannot combine without a supporting basis', matching='additive_unresolved'),
}
CASES.update({key: value['title'] for key, value in MATCHING_GAMES.items()})
TRANSACTION_GAMES = {
    'transaction:unverified-signing': dict(title='Proposed signing does not establish execution or current authority', transaction='signing'),
    'transaction:debt-not-jv': dict(title='A debt facility is not an equity JV', transaction='debt'),
    'transaction:out-of-order': dict(title='Close discovered first preserves occurrence chronology and missing authority', transaction='out_of_order'),
}
CASES.update({key:value['title'] for key,value in TRANSACTION_GAMES.items()})
CASES.update({"control:"+key:"Rule 7 control: "+key+" / "+value["category"] for key,value in CONTROLS.items()})
H_CASES = {"homography", "no-h", "singular", "ill-conditioned", "infinity", "space-mismatch", "projective"}
UNIMPLEMENTED = ["Automatic control-point extraction and professional/legal certification"]


def root(app):
    return Path(app.instance_path) / "survey_evaluation"


def location(app, run_id):
    if not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise ValueError("Unknown evaluation")
    path = root(app) / run_id
    if not (path / "run.json").is_file():
        raise ValueError("Unknown evaluation")
    return path


@contextmanager
def isolated(app, path):
    child = Flask("survey-evaluation-context")
    child.config.update(app.config)
    child.config["REGISTRY_STORE_PATH"] = str(path / "registry")
    with child.app_context():
        yield child


def _read(path):
    return json.loads((path / "run.json").read_text(encoding="utf-8"))


def _save(path, record):
    temp = path / (uuid.uuid4().hex + ".tmp")
    temp.write_text(json.dumps(record, indent=2, allow_nan=False), encoding="utf-8")
    temp.replace(path / "run.json")


def recent(app):
    if not root(app).is_dir():
        return []
    rows = []
    for path in sorted(root(app).glob("*/run.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:30]:
        record = json.loads(path.read_text(encoding="utf-8"))
        rows.append({k: record[k] for k in ("id", "title", "case", "actor")})
    return rows


@observed
def compare_runtime_domains(app, run_ids):
    """Read retained evaluation analyses and their actual trace owners only."""
    from services import runtime_observation
    if (not isinstance(run_ids, list) or len(run_ids) > 8 or len(set(run_ids)) != len(run_ids)):
        raise ValueError('Select at most eight distinct retained evaluation runs.')
    executions, traces, owners = [], {}, {}
    for identifier in run_ids:
        path = location(app, identifier)
        record = _read(path)
        store = CaseWorkspaceStore(path / 'registry')
        workspace = store.get(record['project_id'])
        if not workspace or workspace.removed_at or workspace.document_desk_state != 'active':
            raise ValueError('A selected evaluation workspace is unavailable.')
        for analysis in workspace.analyses:
            result = analysis.get('governed_result') or {}
            if not result:
                continue
            trace_id = analysis.get('runtime_trace_id')
            if trace_id not in traces:
                traces[trace_id] = runtime_observation.muscle_exposure(runtime_observation.read(app, trace_id) if trace_id else None)
            exposure = traces[trace_id]
            execution = dict(run_id=identifier, analysis_id=analysis['id'], title=record['title'],
                attention_id=result.get('attention_analysis_id'), kind=result['kind'],
                domain=result.get('context_key') or (result.get('narrative') or {}).get('professional_lens') or 'Survey',
                state=result['state'], evaluation_only=True, trace_id=trace_id,
                trace_available=exposure['trace_id'] is not None, truncated=exposure['truncated'],
                consumer_events=exposure['consumer_events'])
            executions.append(execution)
            for muscle in exposure['muscles']:
                if muscle['invoked_count']:
                    row = owners.setdefault(muscle['owner'], dict(owner=muscle['owner'], name=muscle['contract']['name'], executions=[]))
                    row['executions'].append(dict(execution=execution, invoked_count=muscle['invoked_count'],
                        return_count=muscle['return_count'], error_count=muscle['error_count'], events=muscle['events']))
    return dict(executions=executions, muscles=list(owners.values()), selected_ids=list(run_ids),
        qualification='Actual request-level invocations only. A shared trace may contain several analyses; counts are not per-analysis calls. '
            'Missing or truncated traces cannot prove complete activation. This view reruns no analysis and grants no authority.')


def _rect(a, b, c, d):
    return [dict(x=x, y=y) for x, y in ((a, b), (c, b), (c, d), (a, d))]


def _payload(case):
    provenance = "EVALUATION_INPUT: controlled plan, no customer or legal authority"
    graph = {"subject_parcel": dict(identity="Evaluation parcel", boundary_segments=["S0", "S1", "S2", "S3"],
        read_certainty="RECOVERED", bind_certainty="RECOVERED", bind_basis="declared", provenance=provenance),
        "nodes": [dict(p, id="N%d" % i, kind="property_corner", certainty="RECOVERED")
                  for i, p in enumerate(_rect(.2, .2, .8, .8))],
        "segments": [dict(id="S%d" % i, **{"from": "N%d" % i, "to": "N%d" % ((i + 1) % 4)},
            kind="straight", boundary="lot_line", certainty="RECOVERED", label="Evaluation boundary",
            dimension=dict(text="100 m", value=100, unit="m", certainty="RECOVERED"),
            bearing=dict(text=["N 90 E", "S 0 E", "S 90 W", "N 0 E"][i], certainty="RECOVERED")) for i in range(4)],
        "footprints": [dict(id="B1", kind="structure", label="Evaluation building", outline=_rect(.4,.4,.6,.6), certainty="RECOVERED")],
        "bearing_reference": "ASSUMED_NORTH"}
    if case == "open-parcel":
        graph["segments"].pop()
    if case == "binding":
        graph["subject_parcel"]["bind_basis"] = "none"
    if case == "curve":
        graph["segments"][0].update(kind="arc", notation="Historical R / C notation",
            radius=dict(text="R 100", value=100, unit="m", certainty="RECOVERED"),
            chord=dict(text="C 50", value=50, unit="m", certainty="RECOVERED"))
    if case in ("history", "conflict"):
        graph["segments"][0]["measurements"] = [dict(occurrence_id=identifier, segment_id="S0",
            text=str(value), value=value, unit="m", source_plan="Evaluation plan " + date, survey_date=date,
            role=role, printed_role=role, read_certainty="RECOVERED", bind_certainty="RECOVERED", bind_basis="declared",
            provenance=provenance, authority_basis="Evaluation note names working measurement, not legal authority",
            applicability_basis="Same evaluation segment S0", prior_occurrence="M1" if identifier=="M2" else "",
            precedence_basis="Evaluation note explicitly relates M2 to M1")
            for identifier,value,date,role in (("M1",100,"1990-01-02","REGISTERED_PLAN"),("M2",100.12,"2025-03-04","CURRENT_MEASURED"))]
    def premise(value, **extra):
        return dict(value=value, read_certainty="RECOVERED", bind_certainty="RECOVERED", bind_basis="declared",
            provenance=provenance, source_region=dict(x=.1,y=.1,w=.4,h=.4), **extra)
    if case == "access":
        features = {name: premise(name in ("public_street","driveway_access","building_entry_relation"), bound_to="S0") for name in sg.ACCESS_FEATURES}
        graph["access_occurrences"] = [dict(id="A1", edge_id="S0", entry_id="E1", building_id="B1", street_name="Evaluation Street",
            printed_role="Explicit evaluation entry", provenance=provenance, source_region=dict(x=.1,y=.1,w=.4,h=.4),
            entry_region=dict(x=.4,y=.4,w=.1,h=.1), classification="PRIMARY_PUBLIC_ACCESS", **features)]
    if case in ("datum", "no-authority"):
        graph["height_datums"] = [dict(id="D1", subject_id="Evaluation parcel",
            street_centerline_geometry=premise("Evaluation centerline", kind="STREET_CENTERLINE", street_id="ST1", street_name="Evaluation Street", bound_to="ST1", points=[dict(x=.1,y=.9),dict(x=.9,y=.9)]),
            regulatory_requirement=premise("CENTERLINE_HEIGHT_DATUM", locator="evaluation clause 4", text="Evaluation height datum is the selected street centerline at the documented reference axis."),
            authority=premise("EVALUATION AUTHORITY ONLY"), applicability=premise("APPLIES", subject_id="Evaluation parcel"),
            selected_governing_street=premise("ST1", bound_to="ST1"),
            building_reference_alignment_or_midpoint=premise("Evaluation axis", kind="DOCUMENTED_REFERENCE_AXIS", building_id="B1", street_id="ST1", bound_to="B1", points=[dict(x=.5,y=.5),dict(x=.5,y=.9)]))]
    return dict(document_category="survey", category_certainty="RECOVERED", graph=graph,
        observations=[dict(key="legal_description", value="EVALUATION_INPUT parcel, not legal evidence", certainty="RECOVERED"),
                      dict(key="lot_dimensions", value="100 m annotation; attachment only partially recovered", certainty="PARTIALLY_RECOVERED")],
        unresolved=["Evaluation-only evidence. No certified land survey conclusion."])


def _source_pdf(path, case):
    import pymupdf
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=600, height=800)
        page.insert_text((40,40), "EVALUATION INPUT - not a customer survey", fontsize=16)
        page.draw_rect(pymupdf.Rect(120,160,480,640), color=(.1,.3,.5))
        page.draw_rect(pymupdf.Rect(240,320,360,480), color=(.3,.4,.2))
        page.insert_text((125,150), "Evaluation parcel / 100 m annotation")
        if case != "unreadable":
            page.insert_text((470,680), "Sheet: A-203\nDrawing title: Evaluation plan\nDiscipline: Architectural\nRevision: 2\nIssue date: 2026-09-18", fontsize=5)
        else:
            from PIL import Image, ImageDraw, ImageFilter
            picture=Image.new("RGB",(300,150),"white")
            ImageDraw.Draw(picture).text((10,30),"A-203 REV 2",fill="black")
            buf=io.BytesIO(); picture.filter(ImageFilter.GaussianBlur(12)).save(buf,"PNG")
            page.insert_image(pymupdf.Rect(460,675,595,790), stream=buf.getvalue())
        raw=pdf.tobytes()
        page.get_pixmap().save(str(path/"source.png"))
    (path / "source.pdf").write_bytes(raw)
    return raw


def create(app, case, actor, matrix_text=""):
    if case not in CASES:
        raise ValueError("Unknown evaluation case")
    if case in REVIEW_GAMES or case in MATCHING_GAMES or case in TRANSACTION_GAMES:
        return _create_review_game(app, case, actor)
    if matrix_text and len(matrix_text)>2000:
        raise ValueError("Transform input too large")
    matrix = json.loads(matrix_text) if matrix_text.strip() else [[1,0,4],[0,1,5],[0,0,1]]
    run_id=uuid.uuid4().hex; path=root(app)/run_id; path.mkdir(parents=True)
    record=dict(id=run_id, case=case, title=CASES[case], actor=actor, origin="EVALUATION_INPUT", matrix=matrix,
                capabilities_not_implemented=UNIMPLEMENTED, results={}, history=[])
    _save(path,record)
    store=CaseWorkspaceStore(str(path/"registry"))
    workspace=store.get_or_create("evaluation", register_document_source={"filename":"EVALUATION_A-999-rev99-current.pdf"})
    record["project_id"]=workspace.project_id; source=workspace.sources[0]
    source.update(file_path=str(path/"source.pdf"), evaluation_only=True)
    store.save(workspace)
    raw=_source_pdf(path,case)
    source["file_hash"] = hashlib.sha256(raw).hexdigest()
    store.save(workspace)
    store.register_pdf_page_structure(workspace,source["id"],["EVALUATION_INPUT\n\n100 m annotation; binding is not established."])
    from services import drawing_segmentation, sheet_identity, height_datum_governance as hd
    if case in ("survey", "unreadable"):
        drawing_segmentation.examine_title_blocks(store,workspace,source["id"],raw,actor=actor)
    if case == "missing-sheet":
        index=store.add_source(workspace,"Evaluation index",None,"project_document")
        store.register_pdf_page_structure(workspace,index["id"],["DRAWING INDEX\nA-777"])
        sheet_identity.register_sheet_index(store,workspace,index["id"])
        record["index_source"]=index["id"]
    payload=vx.normalise_payload(_payload(case))
    payload.update(label="Evaluation survey", classification="LIKELY_SURVEY", evaluation_only=True)
    if case in ("north", "ambiguous-north"):
        from PIL import Image, ImageDraw
        from services import survey_north
        candidates=[]
        for number,rotation in enumerate((0,90) if case=="ambiguous-north" else (0,)):
            pic=Image.new("RGB",(200,200),"white")
            draw=ImageDraw.Draw(pic)
            draw.polygon([(100,20),(65,80),(135,80)],fill="black")
            draw.rectangle((94,75,106,170),fill="black")
            pic=pic.rotate(-rotation); buf=io.BytesIO();pic.save(buf,"PNG")
            candidate=survey_north.normalise_candidates([dict(id="NORTH"+str(number),source_type="survey_arrow", reference_type="TRUE_NORTH",
                reference_text="Explicit evaluation True North",provenance="EVALUATION_INPUT arrow image; deterministic measurement",
                applicability="THIS_VIEW",degrees=rotation,read_certainty="RECOVERED",bind_certainty="RECOVERED",bind_basis="declared",
                source_region=dict(x=0,y=0,w=1,h=1))])[0]
            measured=survey_north.measure_north(buf.getvalue(),dict(x=0,y=0,w=1,h=1))
            candidate.update(measured_degrees=measured["degrees"], measured_ok=measured["ok"],
                measured_reason=measured["reason"], measure_version=survey_north.MEASURE_VERSION)
            candidates.append(candidate)
            (path/("north-%d.png"%number)).write_bytes(buf.getvalue())
        payload["graph"]["north_candidates"]=candidates
    evidence=store.register_evidence_item(workspace,source["id"],"ai_generated_proposal",json.dumps(payload),vx.VISUAL_CONTENT_TYPE,actor=actor)
    record["visual_id"]=evidence["id"]
    sg.propose_measurement_premises(store,workspace,evidence,payload["graph"])
    sg.propose_access_interpretations(store,workspace,evidence,payload["graph"])
    hd.propose_height_datums(store,workspace,evidence,payload["graph"])
    if case == "datum":
        from services import planning_authority
        clause=payload["graph"]["height_datums"][0]["regulatory_requirement"]["text"]
        authority_source=store.add_source(workspace,"EVALUATION authority - not a real bylaw",None,"document")
        acquired=planning_authority.acquire("https://www.toronto.ca/evaluation-only-not-a-real-provision",fetcher=lambda _:clause,
            authority_id="EVALUATION",issuing_authority="EVALUATION ONLY",official_title="Synthetic evaluation authority",retrieved_at="2026-09-18",
            applicability="CURRENT",provision_locator="evaluation clause 4",retained_representation=clause)
        authority=store.register_evidence_item(workspace,authority_source["id"],"direct_source_evidence",json.dumps(acquired["record"]),"planning_authority",actor=actor)
        for item in list(workspace.evidence_items):
            if item.get("content_type")==hd.HEIGHT_PREMISE_TYPE and json.loads(item["content"]).get("axis")=="authority":
                store.record_evidence_relationship(workspace,"evidence_item",authority["id"],"evidence_item",item["id"],"supports",provisional=True,created_by=actor)
    if case == "conflict":
        targets=[e for e in workspace.evidence_items if e.get("content_type")==sg.MEASUREMENT_PREMISE_CONTENT_TYPE]
        counter=store.register_evidence_item(workspace,source["id"],"direct_source_evidence","EVALUATION_INPUT: same-segment precedence disputed","text",actor=actor)
        store.record_evidence_relationship(workspace,"evidence_item",counter["id"],"evidence_item",targets[0]["id"],"contradicts",provisional=True,created_by=actor)
    if case in ("supersession","missing-predecessor","whole-source"):
        from services import package_muscles
        base=store.add_source(workspace,"Evaluation record.pdf",None,"project_document",document_authority="contractual")
        newer=store.add_source(workspace,"Evaluation amendment.pdf",None,"project_document",document_authority="contractual")
        store.register_pdf_page_structure(workspace,base["id"],["Section 2.4 Retain this recorded dimension.\n\nSection 2.5 Unaffected provision."])
        text=('This document replaces "Evaluation record.pdf" in its entirety.' if case=="whole-source" else
              "Replace Section %s with: New evaluation working dimension." % ("99.9" if case=="missing-predecessor" else "2.4"))
        store.register_pdf_page_structure(workspace,newer["id"],[text])
        record["supersession_proposals"]=package_muscles.register_supersessions(store,workspace,newer["id"],actor=actor)
    if case in H_CASES or case in ("non-finite","projection","polygon") or case.startswith("control:"):
        _geometry(store,workspace,record,path)
    if case in ("monument", "missing-monument", "occupation", "earned-h", "degenerate-controls", "traverse"):
        _survey_operation(store, workspace, record)
    if case == 'source-review':
        source.update(file_path=str(path/'source.png'), name='EVALUATION photographed sheet.png',
            file_hash=hashlib.sha256((path/'source.png').read_bytes()).hexdigest())
        store.save(workspace)
        region = next(r for r in workspace.addressable_regions)
        store.register_evidence_item(workspace, source['id'], 'extracted_evidence',
            'Sheet: A-2O3', 'positioned_text', region_id=region['id'], actor='evaluation-machine-reading')
    _save(path,record)
    evaluate(app, run_id)
    return run_id


@observed
def _create_review_game(app, case, actor):
    """Controlled inputs only; ordinary review/constraint owners derive results.

    Reuses the evaluation registry boundary, Source/region identities, attention,
    professional review and quantitative investigation. No expected result enters
    the fixture or an alternative evaluator. Review premises remain evaluation-only.
    """
    import pymupdf
    spec = (REVIEW_GAMES | MATCHING_GAMES | TRANSACTION_GAMES)[case]
    run_id = uuid.uuid4().hex
    path = root(app) / run_id
    path.mkdir(parents=True)
    record = dict(id=run_id, case=case, title=spec['title'], actor=actor,
        origin='EVALUATION_INPUT', results={}, history=[], capabilities_not_implemented=UNIMPLEMENTED,
        evaluation_kind='professional_review', premise_origin='AUTOMATED_CONTROLLED_EVALUATION_NOT_HUMAN_PROJECT_REVIEW')
    store = CaseWorkspaceStore(path / 'registry')
    workspace = store.get_or_create('evaluation')
    record['project_id'] = workspace.project_id
    subject = 'EVALUATION_INPUT envelope interface'
    count = max(1, spec.get('conditions', 0))
    condition_text = [f'EVALUATION_INPUT condition {index + 1}: {subject}; materially distinct local condition.' for index in range(count)]
    if spec.get('physical'):
        condition_text = ['EVALUATION_INPUT: AIR BARRIER label. No connection, termination or continuity evidence is supplied.']
    if spec.get('constraints'):
        lo_a, hi_a, lo_b, hi_b = spec['constraints']
        condition_text = [f'EVALUATION_INPUT: opening width hypothetical interval [{lo_a}, {hi_a}] mm.']
        other_text = [f'EVALUATION_INPUT: same opening width hypothetical interval [{lo_b}, {hi_b}] mm.']
    else:
        other_text = ['EVALUATION_INPUT: typical structural wall section applies to each explicitly reviewed condition; local exceptions must be reviewed separately.']
    if case == 'review:specification-gap':
        condition_text = ['EVALUATION_INPUT specification clause: provide continuous air control at this interface. No downstream manifestation is provided.']
    if case == 'review:independent':
        condition_text = ['EVALUATION_INPUT independent reference: no upstream or downstream participation is required for this review objective.']
    if spec.get('matching'):
        condition_text = ['EVALUATION_INPUT opportunity: capital minimum 100 EVAL_CURRENCY; sector EVAL_SECTOR; geography EVAL_REGION; collective roles EQUITY and DEBT. Declared interval 2026-01-01 to 2027-01-01.']
        other_text = ['EVALUATION_INPUT candidate: capital 100 EVAL_CURRENCY; sector '
            + ('OTHER_SECTOR' if spec['matching'] == 'mandatory_failure' else 'EVAL_SECTOR')
            + '; geography EVAL_REGION. Hypothetical candidate A offers EQUITY role coverage; candidate B offers DEBT role coverage. '
            + ('Historical activity only; no current mandate supplied.' if spec['matching'] == 'historical'
               else 'Declared hypothetical interval 2026-01-01 to 2027-01-01. This is not verified investor information.')]
    if spec.get('transaction'):
        condition_text = ['EVALUATION_INPUT: fictional transaction EVAL-AGREEMENT-A; project EVAL-PROJECT phase A; '
            'parties EVAL-PARTY-A and EVAL-PARTY-B. No human verification, executed instrument or current authority is supplied.']
        other_text = ['EVALUATION_INPUT: proposed signing occurred 2024-01-01, proposed execution 2024-02-01, '
            'proposed close 2024-03-01. Discovery order does not establish event order. All assertions remain hypothetical.']
    if spec.get('matching') == 'domain':
        condition_text = ['EVALUATION_INPUT requirement: ' + spec['property_key'] + ' = ' + ', '.join(spec['tokens'])
            + '. Declared interval 2026-01-01 to 2027-01-01; no source authority is asserted.']
        other_text = ['EVALUATION_INPUT candidate representation: ' + spec['property_key'] + ' = ' + ', '.join(spec['tokens'])
            + '. Declared interval 2026-01-01 to 2027-01-01; applicability and physical sufficiency remain unverified.']
    evidence = []
    with isolated(app, path):
        for number, lines in enumerate((condition_text, other_text)):
            directory = path / 'registry' / 'workspace_sources' / workspace.project_id
            directory.mkdir(parents=True, exist_ok=True)
            file = directory / f'evaluation-{number}.pdf'
            with pymupdf.open() as pdf:
                pages = []
                for line in lines:
                    page = pdf.new_page()
                    page.insert_textbox(pymupdf.Rect(40, 40, 550, 780), line, fontsize=12)
                    pages.append(page.get_text('text'))
                pdf.save(file)
            source = store.add_source(workspace, name=f'EVALUATION_INPUT representation {number + 1}.pdf',
                kind='document', file_path=str(file), file_hash=hashlib.sha256(file.read_bytes()).hexdigest(), actor=actor)
            store._find(workspace.sources, source['id'])['evaluation_only'] = True
            store.save(workspace)
            store.register_pdf_page_structure(workspace, source['id'], pages,
                extractor_version='pymupdf-controlled-evaluation-pdf', actor=actor)
            if spec.get('native_annotations'):
                from services.positioned_text import _native_positioned_lines
                unit = next(item for item in workspace.structural_units
                    if item['source_id'] == source['id'] and item['unit_type'] == 'page')
                positioned = _native_positioned_lines(file.read_bytes(), 0)
                store.register_positioned_text_regions(workspace, source['id'], unit['id'], positioned['lines'],
                    frame=positioned['frame'], extractor_version='pymupdf-native', actor=actor)
                if number == 0:
                    with pymupdf.open(file) as document:
                        document[0].get_pixmap().save(path/'source.png')
            rows = [item for item in workspace.evidence_items if item['source_id'] == source['id'] and item.get('region_id')]
            if not rows:
                raise ValueError('The controlled source did not produce addressed evidence.')
            evidence.append(rows)
        identifiers = [item['id'] for rows in evidence for item in rows]
        attention = store.record_go_attention(workspace, actor, 'EVALUATION_INPUT: ' + spec['title'],
            identifiers, evaluation_only=True)
        record['attention_id'] = attention['id']
        reason = 'Explicit automated EVALUATION_INPUT premise; not human professional approval or project authority.'
        for index in range(spec.get('conditions', 0)):
            anchored = evidence[0][min(index, len(evidence[0])-1)]
            condition = store.record_review_condition(workspace, actor, attention['id'], anchored['id'],
                condition_text[index], ['structural', 'mechanical'] if spec.get('missing_discipline') else ['structural'],
                'ASSEMBLY_LAYERS', True, reason)
            store.review_coverage_record(workspace, actor, attention['id'], condition['id'], 'confirm_condition', reason)
            if spec.get('representation'):
                representation = store.record_review_representation(workspace, actor, attention['id'], condition['id'],
                    evidence[1][0]['id'], 'structural', 'WALL_SECTION', 'ASSEMBLY_LAYERS', reason)
                store.review_coverage_record(workspace, actor, attention['id'], representation['id'], 'resolve_representation', reason)
        if spec.get('transaction'):
            analysis = _transaction_game_inputs(store, workspace, actor, attention['id'], evidence, spec['transaction'], reason)
        elif spec.get('matching'):
            analysis = _matching_game_inputs(store, workspace, actor, attention['id'], evidence, spec['matching'], reason, specification=spec)
        elif spec.get('constraints'):
            constraints = [dict(id=f'constraint-{index}', subject=subject, parameter='opening_width', unit='mm',
                lower=lower, upper=upper, premise_ids=[evidence[index][0]['id']])
                for index, (lower, upper) in enumerate(((lo_a, hi_a), (lo_b, hi_b)))]
            analysis = store.run_constraint_review(workspace, actor, attention['id'], constraints, '100', 'increase', reason)
        else:
            analysis = store.run_professional_review(workspace, actor, attention['id'],
                'physical_control' if spec.get('physical') else 'building_science', evidence[0][0]['id'], subject,
                'PHYSICAL_PHENOMENON' if spec.get('physical') else spec.get('representation_class', 'DETAIL'),
                'ASSEMBLY_LAYERS', 'ASSEMBLY_LAYERS', 'evaluation-review', 'structural', reason,
                participation_expectation=spec.get('expectation', 'unknown'))
        record['analysis_id'] = analysis['id']
    _save(path, record)
    return run_id


def _transaction_game_inputs(store, workspace, actor, attention_id, evidence, variant, reason):
    """Declared fictional source inputs; no reviewer or authority is fabricated."""
    from copy import deepcopy
    parties = [store.record_review_subject(workspace, actor, attention_id, 'EVAL-PARTY-'+name, 'investor') for name in ('A','B')]
    identity = dict(project=dict(name='EVAL-PROJECT', phase='A', location='EVAL-REGION', sponsor='EVAL-SPONSOR',
        project_type='EVAL-ASSET', opportunity_reference='EVAL-OPPORTUNITY'),
        participants=[dict(participant_id=p['id'], legal_name=p['name'], jurisdiction='EVAL-JURISDICTION',
            registration_id='EVAL-REG-'+str(i), role='Lender' if variant == 'debt' else 'Equity participant',
            identity_relation='EXACT_ENTITY') for i,p in enumerate(parties)],
        transaction_class='TERM_LOAN' if variant == 'debt' else 'EQUITY_JV',
        transaction_reference='EVAL-AGREEMENT-A', economic_scope='EVALUATION_INPUT scope',
        joint_structure='NOT_JV' if variant == 'debt' else 'JOINT_EQUITY')
    base = dict(kind='TRANSACTION_IDENTITY', transaction_claim_id=None, identity=identity, event_dimension=None,
        asserted_state='ESTABLISHED', occurred_at='2024-01-01', effective_from='2024-01-01', effective_until='2024-12-31',
        discovered_at='2026-09-20', component_scope='FULL_TRANSACTION', component_key='', related_claim_ids=[],
        replaces_claim_ids=[], continuity='UNRESOLVED', conditions=[], facets=dict.fromkeys(
            ('explicit_signing','legal_effectiveness','financial_close','execution_conditions_complete',
             'closing_conditions_complete','express_current_confirmation'), 'UNRESOLVED'))
    def propose(data, item):
        return store.record_event_proposition(workspace, actor, attention_id, data, [item['id']],
            'PROJECT_DOCUMENT', 0, item['content'], reason, attribution='agent_assessment')
    root_claim = propose(base, evidence[0][0])
    dimensions = [('FINANCIALLY_CLOSED','2024-03-01'),('SIGNED','2024-01-01'),('EXECUTED','2024-02-01')] if variant == 'out_of_order' else [('SIGNED','2024-01-01')]
    for dimension, occurred in dimensions:
        data = deepcopy(base)
        data.update(kind='TRANSACTION_EVENT', transaction_claim_id=root_claim['id'], event_dimension=dimension, occurred_at=occurred)
        propose(data, evidence[1][0])
    return store.run_transaction_review(workspace, actor, attention_id, root_claim['id'], '2024-06-01', reason)


def _matching_game_inputs(store, workspace, actor, attention_id, evidence, variant, reason, *, specification=None):
    """Supply declared fixture premises; ordinary Claim/matching/composition owners execute."""
    specification = specification or {}
    subjects = ([('required condition', 'requirement'), ('candidate representation', 'representation'), ('support', 'support')]
        if variant == 'domain' else [('opportunity', 'opportunity'), ('candidate A','investor'), ('candidate B','lender')])
    parties = [store.record_review_subject(workspace, actor, attention_id, 'EVALUATION '+name, role)
        for name, role in subjects]

    def proposition(party, property_key, value, *, historical=False, reporting=False):
        item = evidence[0 if party == 0 else 1][0]
        numeric = property_key == 'capital'
        norm = dict(subject_key='participant:'+parties[party]['id'], property_key=property_key,
            scope_key='evaluation-opportunity', kind='NUMBER' if numeric else 'TOKEN_SET', value=value,
            unit='EVAL_CURRENCY' if numeric else '', vocabulary='' if numeric else 'evaluation-'+property_key,
            qualifiers=[], view_basis='VIEW_INVARIANT', view_id=None, basis=reason, premise_ids=[item['id']])
        return store.record_subject_proposition(workspace, actor, attention_id, norm,
            'REPORTING' if reporting else 'PROJECT_DOCUMENT',
            'HISTORICAL_ACTIVITY' if historical else 'DATED_REQUIREMENT' if party == 0 else
                'CURRENT_DISCLOSED_CAPABILITY' if variant == 'domain' else 'CURRENT_DISCLOSED_MANDATE',
            item['content'], reason, as_of='2026-01-01', valid_until='2027-01-01', attribution='agent_assessment')

    if variant == 'domain':
        required = proposition(0, specification['property_key'], specification['tokens'])
        candidate = proposition(1, specification['property_key'], specification['tokens'])
        return store.run_requirement_matching(workspace, actor, attention_id, 'participant:'+parties[1]['id'],
            [dict(required_claim_id=required['id'], candidate_claim_id=candidate['id'], mandatory=True,
                operator='CONTAINS_ALL', candidate_temporal_class='CURRENT_DISCLOSED_CAPABILITY')],
            specification['context'], reason, query_date='2026-09-20')
    if variant.startswith('coverage_') or variant.startswith('additive_'):
        if variant in ('coverage_three', 'coverage_alternatives'):
            parties.append(store.record_review_subject(workspace, actor, attention_id, 'EVALUATION candidate C', 'operator'))
        additive = variant.startswith('additive_')
        roles = ('EQUITY', 'DEBT', 'OPERATOR') if variant == 'coverage_three' else ('EQUITY', 'DEBT')
        required = [proposition(0, 'capital', '100')] if additive else [proposition(0, 'role', [role]) for role in roles]
        runs = []
        for party in range(1, len(parties)):
            values = list(roles) if variant == 'coverage_one' and party == 1 else [roles[min(party-1, len(roles)-1)]]
            candidate = proposition(party, 'capital' if additive else 'role', '50' if additive else values)
            criteria = [dict(required_claim_id=claim['id'], candidate_claim_id=candidate['id'], mandatory=True,
                operator='AT_LEAST' if additive else 'CONTAINS_ALL', candidate_temporal_class='CURRENT_DISCLOSED_MANDATE') for claim in required]
            runs.append(store.run_requirement_matching(workspace, actor, attention_id, 'participant:'+parties[party]['id'],
                criteria, 'investment', reason, query_date='2026-09-20'))
        basis = None
        if variant == 'additive_capital':
            item = evidence[0][0]
            norm = dict(subject_key='participant:'+parties[0]['id'], property_key='additive_capacity_basis',
                scope_key='evaluation-opportunity', kind='TOKEN_SET', value=['participant:'+p['id'] for p in parties[1:]],
                unit='', vocabulary='additive:capital:EVAL_CURRENCY', qualifiers=[], view_basis='VIEW_INVARIANT',
                view_id=None, basis=reason, premise_ids=[item['id']])
            basis = store.record_subject_proposition(workspace, actor, attention_id, norm, 'PROJECT_DOCUMENT',
                'DATED_REQUIREMENT', item['content'], reason, as_of='2026-01-01', valid_until='2027-01-01', attribution='agent_assessment')
        policies = {c['id']:dict(classification='COMPOSITIONAL' if additive else 'MANDATORY', divisible=additive,
            combination_claim_id=basis['id'] if basis else None) for c in required}
        return store.run_role_composition(workspace, actor, attention_id, [r['id'] for r in runs],
            [c['id'] for c in required], reason, coverage_policies=policies)

    if variant == 'composition':
        required = [proposition(0, 'role', [role]) for role in ('EQUITY','DEBT')]
        runs = []
        for party, role in ((1,'EQUITY'),(2,'DEBT')):
            candidate = proposition(party, 'role', [role])
            criteria = [dict(required_claim_id=claim['id'], candidate_claim_id=candidate['id'], mandatory=False,
                operator='CONTAINS_ALL', candidate_temporal_class='CURRENT_DISCLOSED_MANDATE') for claim in required]
            runs.append(store.run_requirement_matching(workspace, actor, attention_id, 'participant:'+parties[party]['id'],
                criteria, 'investment', reason, query_date='2026-09-20'))
        return store.run_role_composition(workspace, actor, attention_id, [run['id'] for run in runs],
            [claim['id'] for claim in required], reason)
    criteria = []
    for property_key, value in [('capital','100'), ('sector',['EVAL_SECTOR']), ('geography',['EVAL_REGION'])]:
        required = proposition(0, property_key, value)
        candidate = None
        if not (variant == 'missing' or (variant in ('partial','brief') and property_key == 'geography')):
            candidate_value = ['OTHER_SECTOR'] if variant == 'mandatory_failure' and property_key == 'sector' else ['OTHER_REGION'] if variant == 'known_partial' and property_key == 'geography' else value
            candidate = proposition(1, property_key, candidate_value,
                historical=variant == 'historical', reporting=variant == 'repeated')
            if variant == 'repeated':
                proposition(1, property_key, candidate_value, reporting=True)
        criteria.append(dict(required_claim_id=required['id'], candidate_claim_id=candidate['id'] if candidate else None,
            mandatory=not (variant == 'known_partial' and property_key == 'geography'), operator='AT_LEAST' if property_key == 'capital' else 'CONTAINS_ALL',
            candidate_temporal_class='CURRENT_DISCLOSED_MANDATE'))
    analysis = store.run_requirement_matching(workspace, actor, attention_id, 'participant:'+parties[1]['id'],
        criteria, 'investment', reason, query_date='2026-09-20')
    if variant == 'brief':
        store.render_professional_review(workspace, actor, analysis['id'])
    return analysis


def _survey_operation(store, workspace, record):
    """Controlled premises only; domain implementation is the project resolver."""
    source_id = workspace.sources[0]["id"]
    unit = next(u for u in workspace.structural_units if u["source_id"] == source_id)
    region = store.create_addressable_region(workspace, unit["id"], "drawing_region", {"object_id":"survey-object"})
    common = dict(read_certainty="RECOVERED", bind_certainty="RECOVERED", bind_basis="declared",
        subject_id="evaluation-parcel",
        coordinate_space="EUCLIDEAN_RECTIFIED", plane_id="survey-plane", geometry_level="EUCLIDEAN",
        evaluation_only=True, provenance="EVALUATION_INPUT; declared controlled correspondence")
    case = record["case"]
    if case == "traverse":
        evidence=sg.derive_survey_operation(store,workspace,source_id=source_id,region_id=region["id"],object_id="survey-object",
            operation="traverse",premise_ids=[record["visual_id"]],actor=record["actor"])
        record["operation_evidence_id"]=evidence["id"]
        return
    if case in ("monument", "missing-monument"):
        operation="monument"
        inputs=[dict(survey_role="recorded_monument",monument_id="M1",record_corner_id="C1",point=[0,0]),
                dict(survey_role="found_monument" if case=="monument" else "missing_monument",monument_id="M1",record_corner_id="C1",point=[0,.1])]
    elif case=="occupation":
        operation="occupation"
        inputs=[dict(survey_role="record_boundary",segment=[[0,0],[10,0]]),
                dict(survey_role="observed_occupation",point=[2,.5])]
    else:
        operation="rectification"
        points=[[0,0],[2,0],[2,1],[0,1]] if case=="earned-h" else [[0,0],[1,0],[2,0],[3,0]]
        target_points=[[0,0],[1,0],[1,1],[0,1]]
        frame = store.register_evidence_item(workspace,source_id,"direct_source_evidence",
            json.dumps(dict(common,survey_role="affine_control_frame",frame_id="affine-control-frame",
                controls={str(i):p for i,p in enumerate(target_points)})),"application/json",region_id=region["id"],actor=record["actor"])
        common.update(coordinate_space="SOURCE_PIXELS",geometry_level="PROJECTIVE")
        inputs=[dict(survey_role="control_correspondence",control_id=str(i),point=p,target_point=q,
            target_frame_evidence_id=frame["id"],
            image_source_id=source_id,target_frame_id="affine-control-frame",target_frame_level="AFFINE",target_space="AFFINE_RECTIFIED")
            for i,(p,q) in enumerate(zip(points,target_points))]
    premises=[store.register_evidence_item(workspace,source_id,"direct_source_evidence",json.dumps(dict(common,**item)),
        "application/json",region_id=region["id"],actor=record["actor"])["id"] for item in inputs]
    evidence=sg.derive_survey_operation(store,workspace,source_id=source_id,region_id=region["id"],object_id="survey-object",
        operation=operation,premise_ids=premises,actor=record["actor"])
    record["operation_evidence_id"]=evidence["id"]


def _geometry(store,workspace,record,path):
    from engine import spatial_compiler as math
    from services.survey_evaluation_geometry import candidate_for, run_validator
    case=record["case"]
    fixture_id={"non-finite":"R7-FIN-NF-001", "projection":"R7-FIN-POS-001", "polygon":"R7-FIN-POS-001"}.get(case,"R7-FIN-TR-001")
    inputs=copy.deepcopy(CONTROLS[case.partition(":")[2] if case.startswith("control:") else fixture_id]["inputs"])
    inputs["provenance"]="EVALUATION_INPUT: explicitly supplied isolated premises"
    if case=="projection":
        inputs.update(kind="projection",value=dict(point=[2,3],a=[0,0],b=[10,0]))
    if case=="polygon":
        inputs.update(kind="polygon",value=[[0,0],[10,10],[0,10],[10,0],[0,0]])
    if case in H_CASES:
        matrix=record["matrix"]
        if case=="no-h": matrix=None
        if case=="singular": matrix=[[1,0,0],[0,0,0],[0,0,1]]
        if case=="ill-conditioned": matrix=[[1,0,0],[0,1e-12,0],[0,0,1]]
        if case=="infinity": matrix=[[1,0,0],[0,1,0],[1,0,-2]]
        if case=="projective": matrix=[[1,0,0],[0,1,0],[.01,0,1]]
        inputs["value"]=dict(matrix=matrix,point=[2,3,1])
    model,owner,field=candidate_for(inputs)
    unit=store.create_structural_unit(workspace,workspace.sources[0]["id"],"page",0)
    region=store.create_addressable_region(workspace,unit["id"],"geometry",dict(object_id=owner["id"],page_index=0))
    premise=store.register_evidence_item(workspace,workspace.sources[0]["id"],"direct_source_evidence",json.dumps(inputs),"application/json",region_id=region["id"])
    if inputs["kind"] in ("contested","stale"):
        other=store.register_evidence_item(workspace,workspace.sources[0]["id"],"direct_source_evidence",
            json.dumps(dict(inputs,value=145)),"application/json",region_id=region["id"])
        if inputs["kind"]=="contested":
            edge=store.record_evidence_relationship(workspace,"evidence_item",other["id"],"evidence_item",premise["id"],"contradicts",provisional=True,created_by=record["actor"])
            store.confirm_relationship(workspace,edge["id"],actor=record["actor"]+" (explicit evaluation counterevidence)")
        else:
            store.record_supersession(workspace,"evidence_item",premise["id"],"evidence_item",other["id"],actor=record["actor"],reason="EVALUATION_INPUT: explicitly supplied historical replacement, not a customer authority decision")
    validated=run_validator(inputs,store=store,workspace=workspace,source_evidence=premise,model=model)
    if case in H_CASES:
        scope=dict(source_space=inputs["coordinate_space"],target_space=inputs["coordinate_space"],source_plane=inputs["plane_id"],target_plane=inputs["plane_id"],geometry_level=inputs["geometry_level"],source={"evaluation_only":True})
        transform=math.validate_homography(inputs["value"]["matrix"],**scope)
        point=math.transform_homogeneous_point(transform,[2,3,1],point_space="SOURCE_PIXELS" if case=="space-mismatch" else inputs["coordinate_space"],point_plane=inputs["plane_id"])
        validated.update(state=point["state"],value=point["value"],errors=[point["error"]] if point["error"] else [],derivation=point)
        inverse=math.invert_homography(transform)
        roundtrip=math.transform_homogeneous_point(inverse,[*point["value"],1],point_space=inputs["coordinate_space"],point_plane=inputs["plane_id"]) if point["value"] else None
        record["kernel"]=dict(validation=transform,point=point,inverse=inverse,round_trip=roundtrip,
            line=math.transform_homogeneous_line(transform,[1,0,-2],line_space=inputs["coordinate_space"],line_plane=inputs["plane_id"]),
            composition=math.compose_homographies(transform,inverse),
            vanishing=math.classify_vanishing_direction([0,0,1],[1,0,0],**scope),
            horizon=math.classify_horizon_residual(.002,residual_units="IMAGE_DIAGONAL",**scope),
            tiny_vector=math.vector_usability([1e-200,0],**scope),domain=math.bounded_acos(1.0000000000000002,1e-15,**scope))
    validated.update(field=field,object_id=owner["id"],source_evidence_ids=[premise["id"]],premise_ids=[premise["id"]],
        plane_id=inputs["plane_id"],geometry_level=inputs["geometry_level"],evaluation_only=True,uncertainty={"state":"EVALUATION_INPUT"})
    derived=store.register_evidence_item(workspace,workspace.sources[0]["id"],"calculated_value",json.dumps(validated,allow_nan=False),"application/json",region_id=region["id"])
    store.record_evidence_relationship(workspace,"evidence_item",derived["id"],"evidence_item",premise["id"],"derived_from",provisional=True,created_by=record["actor"])
    record.update(geometry_evidence_id=derived["id"],geometry_inputs=inputs)
    record["kernel_evidence"]={}
    dependencies={"inverse":["validation"],"round_trip":["point","inverse"],"line":["validation"],"composition":["validation","inverse"]}
    identifiers={"point":derived["id"]}
    for name, output in record.get("kernel",{}).items():
        if name=="point" or output is None:
            continue
        upstream=[premise["id"],*[identifiers[key] for key in dependencies.get(name,[])]]
        value=output.get("value")
        if name=="vanishing" and output.get("exact_parallel"):
            value=output.get("homogeneous_direction")
        calculation=dict(validated, field={"validation":"transform","round_trip":"point","tiny_vector":"vector","domain":"domain"}.get(name,name),
            state=output["state"],value=value,errors=[output["error"]] if output.get("error") else [],
            derivation=output,premise_ids=upstream)
        item=store.register_evidence_item(workspace,workspace.sources[0]["id"],"calculated_value",json.dumps(calculation,allow_nan=False),"application/json",region_id=region["id"])
        identifiers[name]=item["id"];record["kernel_evidence"][name]=item["id"]
        for identifier in upstream:
            store.record_evidence_relationship(workspace,"evidence_item",item["id"],"evidence_item",identifier,"derived_from",provisional=True,created_by=record["actor"])


def state(value):
    name=str(value or "UNRESOLVED")
    if name in ("proposed","accepted"): return "QUALIFIED"
    if name=="rejected": return "REFUSED"
    if name in ("QUALIFIED", "REFUSED", "CONFLICT", "EVALUATION_INPUT"): return name
    if name in ("CONTESTED","SUPPORTED_BUT_CONTESTED","EVIDENCE_CONFLICT"): return "CONFLICT"
    if name in ("DEGENERATE","BLOCKED","INCOMPARABLE","NON_FINITE") or name.startswith("IFC_BLOCKED"): return "REFUSED"
    if name in ("WEAK","PARTIAL","PARTIALLY_RECOVERED","CONDITIONAL_ARC_FAMILY","GEOMETRY_ONLY"): return "QUALIFIED"
    if name in ("ESTABLISHED","RECOVERED","FINITE","INSIDE_SUBJECT_PARCEL","OUTSIDE_SUBJECT_PARCEL","PRIMARY_PUBLIC_ACCESS","GOVERNING_DATUM_ESTABLISHED","IFC_EXPORTABLE"): return "ESTABLISHED"
    return "UNRESOLVED"


@observed
def inspect(app,run_id):
    """Reload reads a persisted consumer snapshot; it never runs producers."""
    path=location(app,run_id); record=_read(path)
    snapshot=path/'inspection.json'
    store=CaseWorkspaceStore(str(path/'registry')); workspace=store.get(record['project_id'])
    if snapshot.is_file():
        report=json.loads(snapshot.read_text(encoding='utf-8'))
        if report.get('inspection_format') == 1 and report.get('workspace_version') == workspace.version:
            report['record']=record
            return report
    return dict(record=record, rows=[], result={}, context={}, prompt='', reference={},
        ifc_exportable=False, svg='', discrepancies=[], evidence=workspace.evidence_items,
        relationships=workspace.relationships, supersessions=workspace.supersessions,
        assessments=workspace.change_arrival_assessments, sources=workspace.sources,
        regions=workspace.addressable_regions, units=workspace.structural_units,
        reevaluation_required=True)


@observed
def evaluate(app,run_id):
    path=location(app,run_id); record=_read(path)
    if record.get('evaluation_kind') == 'professional_review':
        raise ValueError('Use the professional review or constraint action in the recorded attention scope.')
    store=CaseWorkspaceStore(str(path/"registry")); workspace=store.get(record["project_id"])
    document=SimpleNamespace(project_id=workspace.project_id,filename=workspace.sources[0]["name"])
    with isolated(app,path):
        result=dx.build_result(document,workspace,display_name=record["title"])
        visual=dx.visual_reading(workspace,workspace.sources[0]["id"])
        context=dc.build_context(document,workspace,result,"What is established and what must remain unresolved?")
    graph=visual["graph"]
    from services import sheet_identity, survey_north, height_datum_governance
    rows=[]
    def add(stage,label,operator,raw,value):
        explanation=(value.get("reason") or value.get("statement") or value.get("value") or value.get("uncertainty") or "") if isinstance(value,dict) else ""
        rows.append(dict(stage=stage,label=label,operator=operator,raw_state=raw,state=state(raw),value=value,summary=str(explanation)))
    add("SITUATE","Physical views and independently recovered fields","sheet_identity.title_block_readings","RECOVERED" if workspace.derived_views else "UNRESOLVED",sheet_identity.title_block_readings(workspace,workspace.sources[0]["id"]))
    for view in sheet_identity.title_block_readings(workspace,workspace.sources[0]["id"]):
        for field,reading in view.get("fields",{}).items():
            add("SITUATE",field.replace("_"," ").capitalize(),"sheet_identity.title_block_readings",reading["certainty"],reading)
    for segment in graph["segments"]:
        dimension=segment.get("dimension")
        if dimension: add("BIND","Dimension attachment "+segment["id"],"binding.bound_certainty",binding.bound_certainty(dimension),dimension)
        if segment.get("measurements"):
            genealogy=sg.measurement_genealogy(segment); add("COMPARE","Historical / current dimension","survey_graph.measurement_genealogy",genealogy["status"],genealogy)
        if segment["kind"]=="arc":
            curve=sg.curve_constraints(segment); add("REASON","Curve alternatives / placement","survey_graph.curve_constraints",curve["state"],curve)
    for footprint in graph["footprints"]:
        containment=sg.footprint_containment(graph,footprint); add("BIND","Subject property containment","survey_graph.footprint_containment",containment["state"],containment)
    north=survey_north.resolve_true_north(graph); add("REASON","True North","survey_north.resolve_true_north",north["state"],north)
    for access in sg.access_interpretations(graph): add("GOVERN","Public access / not legal frontage","survey_graph.access_interpretations",access["state"],access)
    for datum in height_datum_governance.height_datum_projection(graph): add("GOVERN","Centerline / governing datum","height_datum_projection",datum["datum_status"],datum)
    if record.get("index_source"):
        missing=sheet_identity.declared_but_absent(workspace,record["index_source"])
        add("COMPARE","Expected-but-absent sheet / retained history","sheet_identity.declared_but_absent","UNRESOLVED" if missing else "ESTABLISHED",missing)
    for assessment in workspace.change_arrival_assessments:
        add("GOVERN","Scoped replacement / human decision","change_application",assessment.get("state","UNRESOLVED"),assessment)
    for edge in workspace.relationships:
        if edge.get("relationship_type")=="contradicts":
            trust=store.explain_evidence_trust(workspace,edge["to_id"])
            add("GOVERN","Active counterevidence","explain_evidence_trust","CONTESTED" if trust.get("confirmed_counterevidence") else "UNRESOLVED",trust)
    visual_object=SimpleNamespace(**visual,prompt_version="evaluation-controlled-input",model="NO MODEL: explicit evaluation input")
    reference=sr.derive(visual_object,project_id=workspace.project_id,source_id=workspace.sources[0]["id"],
        source_filename=workspace.sources[0]["name"],source_sha256=hashlib.sha256((path/"source.pdf").read_bytes()).hexdigest(),frame_size=[600,800])
    reference["source_note"]="EVALUATION_INPUT: isolated controlled source. Not customer evidence."
    reference["authority_note"]="EVALUATION ONLY. No canonical authority. Not a certified or legal survey."
    pdf=sr.render_pdf(reference); (path/"reference.pdf").write_bytes(pdf)
    drawing=sr.resolved_plan(reference)
    add("CONSUME","Actual Survey Reference drawing","survey_reference.resolved_plan","QUALIFIED",drawing)
    discrepancies=[dict(boundary="Survey graph → drawing",governed=[dict(segment=s["id"],dimension=s.get("dimension"),bearing=s.get("bearing")) for s in graph["segments"]],received=dict(stats=drawing["stats"],primitives=drawing["primitives"]),
        surfaced="Computed/observed provenance and qualified placeholders; inspect actual primitives below.",status="INTENTIONALLY SURFACED"),
        dict(boundary="Raw text → Ask GO",governed="Observation is not authority",received=context["recovered_text"],
        surfaced="Evaluation answer admission preserves deterministic statements; provider text is inspectable but not authoritative.",status="GUARDED EVALUATION CONSUMER")]
    if record.get("operation_evidence_id"):
        admission = store.admit_proposition(workspace, record["operation_evidence_id"])
        add("GOVERN", "Survey operation after review/reload", "CaseWorkspaceStore.admit_proposition", admission["state"], admission)
    if record.get("geometry_evidence_id"):
        from engine.ifc_volume_validator import IFCVolumeValidator, IFCValidationError
        from services.survey_evaluation_geometry import candidate_for
        model, _, _ = candidate_for(record["geometry_inputs"])
        model["project_name"]="EVALUATION_INPUT - NOT CUSTOMER AUTHORITY - " + run_id
        governed=store.project_geometry_evidence(workspace,record["geometry_evidence_id"])
        add("GOVERN","Calculated evidence after persistence/reload","project_geometry_evidence",governed["state"],governed)
        for name,call in (("governed",lambda:IFCVolumeValidator().export_evidence(model,store,workspace,record["geometry_evidence_id"],evaluation=True)),
                          ("direct",lambda:IFCVolumeValidator().export(model))):
            try:
                output=call(); status="IFC_EXPORTABLE"; detail={"state":status,"bytes":len(output)}
                if name=="governed": (path/"governed.ifc").write_text(output,encoding="utf-8")
            except IFCValidationError as error:
                status="REFUSED";detail={"state":status,"diagnostic":error.diagnostic,"reason":str(error)}
            add("CONSUME",name.capitalize()+" IFC path","IFCVolumeValidator."+("export_evidence" if name=="governed" else "export"),status,detail)
        discrepancies.append(dict(boundary="Direct IFC vs governed IFC",governed=governed["state"],received=rows[-1]["value"],surfaced="Direct diagnostic only; only governed IFC can be downloaded.",status="DIRECT CANONICAL PATH NOW REQUIRES EVIDENCE"))
    for name,output in record.get("kernel",{}).items():
        add("REASON","Projective kernel: "+name,output.get("operator",name) if output else name,output.get("state") if output else "UNRESOLVED",output)
    for name, identifier in record.get("kernel_evidence",{}).items():
        projection=store.project_geometry_evidence(workspace,identifier)
        add("GOVERN","Reviewed kernel evidence: "+name,"project_geometry_evidence",projection["state"],projection)
    for group in ("interpretation","not_established"):
        for line in result[group]:
            add("SURFACE",line["label"],"document_examination.build_result",line.get("state","UNRESOLVED" if group=="not_established" else "QUALIFIED"),line)
    report = dict(record=record,rows=rows,result=result,context=context,prompt=dc.render_prompt(context),reference=reference,
        ifc_exportable=any(r["label"]=="Governed IFC path" and r["raw_state"]=="IFC_EXPORTABLE" for r in rows),
        svg=sr.review_svg(reference),discrepancies=discrepancies,evidence=workspace.evidence_items,relationships=workspace.relationships,
        supersessions=workspace.supersessions,assessments=workspace.change_arrival_assessments,
        sources=workspace.sources,regions=workspace.addressable_regions,units=workspace.structural_units)
    report['workspace_version']=workspace.version
    report['inspection_format']=1
    temp=path/(uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(report, allow_nan=False), encoding='utf-8')
    temp.replace(path/'inspection.json')
    return report


def action(app,run_id,action_name,actor,question=""):
    path=location(app,run_id); record=_read(path)
    if record.get('evaluation_kind') == 'professional_review':
        raise ValueError('Use the professional review or constraint action in the recorded attention scope.')
    store=CaseWorkspaceStore(str(path/"registry")); workspace=store.get(record["project_id"])
    if action_name=='reevaluate':
        pass
    elif action_name=="confirm":
        for edge in list(workspace.relationships):
            if edge.get("provisional"):
                store.confirm_relationship(workspace,edge["id"],actor=actor)
    elif action_name in ("accept","reject","apply"):
        from services import change_application
        for assessment in list(workspace.change_arrival_assessments):
            if action_name=="apply": change_application.apply_accepted_change(store,workspace,assessment["id"],actor=actor)
            else: store.review_change_arrival_assessment(workspace,assessment["id"],actor=actor,outcome="accepted" if action_name=="accept" else "rejected")
    elif action_name=="arrival":
        source=store.add_source(workspace,"Evaluation A777",None,"project_document")
        source["sheet_number"]="A777";store.save(workspace)
    elif action_name=="ask":
        report=inspect(app,run_id)
        if report.get('reevaluation_required'):
            raise ValueError('Explicitly re-evaluate this legacy or changed case before asking GO.')
        document=SimpleNamespace(project_id=workspace.project_id,filename=workspace.sources[0]["name"])
        with isolated(app,path) as child:
            answer=dc.ask(document,workspace,report["result"],question or "What is established?",app=child,evaluation_guard=True)
        record["answer"]=answer
        record["question"]=question
        record["answer_context"]=dc.render_prompt({**report["context"],"question":question})
    else: raise ValueError("Unknown evaluation action")
    record["history"].append(dict(action=action_name,actor=actor))
    _save(path,record)
    if action_name != 'ask':
        evaluate(app,run_id)
