"""Human review must improve observability without laundering authority."""
import hashlib
import io
import json

import pytest
from PIL import Image
from services import document_examination as dx, image_intake, survey_evaluation as evaluation
from tests.test_kernel_mapping import project


def test_rectification_refuses_degenerate_and_preserves_bytes():
    buffer=io.BytesIO(); Image.new('RGB',(240,160),'white').save(buffer,'PNG')
    raw=buffer.getvalue(); digest=hashlib.sha256(raw).hexdigest()
    preview, frame=image_intake.rectify_document_preview(raw,'original.png',[[.1,.1],[.9,.2],[.8,.9],[.2,.8]])
    assert preview.startswith(b'\x89PNG') and hashlib.sha256(raw).hexdigest()==digest
    assert frame['authority']=='NOT_ESTABLISHED' and frame['north_orientation']=='UNRESOLVED'
    assert frame['transform']['operator']=='control_homography@1'
    with pytest.raises(ValueError):
        image_intake.rectify_document_preview(raw,'original.png',[[0,0],[.2,.2],[.4,.4],[.6,.6]])


def test_real_route_correction_explicit_consumption_revert_and_reload(project):
    app,store,workspace,_,client=project
    source=workspace.sources[0]
    store.register_pdf_page_structure(workspace,source['id'],['Dated 1956'])
    region=workspace.addressable_regions[0]
    machine=store.register_evidence_item(workspace,source['id'],'extracted_evidence','DATED 1056','positioned_text',region_id=region['id'])
    original=json.dumps(machine,sort_keys=True)
    url=f"/projects/project/sources/{source['id']}/review"
    data=dict(action='propose',field=machine['id']+'|content',after='DATED 1956',reason='Verified source date region')
    assert client.post(url,data=data).status_code==302
    workspace=store.get('project')
    correction=dx.source_review_state(workspace,source['id'])['corrections'][0]
    assert correction['status']=='PROPOSED' and correction['anchor']['region_id']==region['id']
    client.post(url,data=dict(action='accept',correction_id=correction['id']))
    workspace=store.get('project')
    assert dx.source_review_state(workspace,source['id'])['result'] is None
    assert 'DATED 1956' not in dx._recovered(workspace,source['id'])['preview']
    response=client.post(url,data=dict(action='reevaluate'))
    assert response.status_code==302
    workspace=store.get('project')
    result=dx.source_review_state(workspace,source['id'])['result']
    assert result['text_overrides'][machine['id']]=='DATED 1956'
    assert 'DATED 1956' in dx._recovered(workspace,source['id'])['preview']
    assert json.dumps(store.get_evidence_item(workspace,machine['id']),sort_keys=True)==original
    before=store._path_for('project').read_bytes()
    for _ in range(2):
        response=client.get(url)
        assert response.status_code==200
        # SUPERSEDED DELIBERATELY (MASTERUI cutover): the page-local "Reload view"
        # widget is retired (browser reload is the reload); a plain GET still
        # re-renders the same review, read-only.
        assert b'Before: DATED 1056' in response.data
    assert store._path_for('project').read_bytes()==before
    client.post(url,data=dict(action='revert',correction_id=correction['id']))
    assert dx.source_review_state(store.get('project'),source['id'])['stale']
    client.post(url,data=dict(action='reevaluate'))
    assert dx.source_review_state(store.get('project'),source['id'])['result']['text_overrides']=={}


def test_evaluation_reload_does_not_execute_or_write_producers(project,monkeypatch):
    app,_,_,_,client=project
    with app.app_context():
        run=evaluation.create(app,'source-review','reviewer')
        path=evaluation.location(app,run)
        before={p.relative_to(path):p.read_bytes() for p in path.rglob('*') if p.is_file()}
        def forbidden(*a,**k): raise AssertionError('Producer ran on Reload')
        monkeypatch.setattr(evaluation.sr,'render_pdf',forbidden)
        monkeypatch.setattr(evaluation,'evaluate',forbidden)
        for _ in range(2):
            response=client.get('/admin/survey-evaluation/'+run)
            assert response.status_code==200
        after={p.relative_to(path):p.read_bytes() for p in path.rglob('*') if p.is_file()}
        assert before==after
        assert client.get('/admin/survey-evaluation/'+run+'/source-review').status_code==200


def test_projective_frame_blocks_north_and_frontage():
    from services.survey_north import resolve_true_north, orientation_propositions
    graph={'frame_qualification':{'angles':'UNRESOLVED'},'north_candidates':[]}
    assert resolve_true_north(graph)['state']=='UNRESOLVED'
    rows=orientation_propositions({'graph':graph})
    assert len(rows)==6 and rows[-1]['state']=='UNRESOLVED'
    assert 'municipal' in rows[-1]['reason']


def test_duplicate_review_and_foreign_anchor_refused(project):
    _,store,workspace,_,client=project
    source=workspace.sources[0]
    machine=store.register_evidence_item(workspace,source['id'],'extracted_evidence','100','positioned_text')
    correction=dx.propose_text_correction(store,workspace,source['id'],machine['id']+'|content','101','source check','reviewer')
    count=len(workspace.evidence_items)
    assert dx.propose_text_correction(store,workspace,source['id'],machine['id']+'|content','101','source check','reviewer')['id']==correction['id']
    assert len(workspace.evidence_items)==count
    other=store.add_source(workspace,'other.pdf',None,'project_document')
    with pytest.raises(ValueError):
        dx.propose_text_correction(store,workspace,other['id'],machine['id']+'|content','102','source check','reviewer')
    with pytest.raises(ValueError):
        dx.propose_text_correction(store,workspace,source['id'],machine['id']+'|authority','contractual','source check','reviewer')
    with client.session_transaction() as session:
        session['role']='read_only'
    assert client.post(f"/projects/project/sources/{source['id']}/review",data={'action':'reevaluate'}).status_code==403


def test_correction_cannot_upgrade_weak_binding_or_consume_mutated_original(project):
    app,store,workspace,_,_=project
    from services import visual_examination as vx, binding
    source=workspace.sources[0]
    visual=vx.normalise_payload({'document_category':'survey','category_certainty':'RECOVERED',
        'observations':[{'key':'plan_date','value':'1056','certainty':'PARTIALLY_RECOVERED'}]})
    machine=store.register_evidence_item(workspace,source['id'],'ai_generated_proposal',json.dumps(visual),vx.VISUAL_CONTENT_TYPE)
    correction=dx.propose_text_correction(store,workspace,source['id'],machine['id']+'|observations/0/value','1956','legible source','reviewer')
    dx.review_text_correction(store,workspace,source['id'],correction['id'],'accept','reviewer')
    original=json.loads(machine['content'])['observations'][0]
    with app.app_context():
        dx.reevaluate_source_review(store,workspace,source['id'],'reviewer')
    corrected=dx.source_review_state(workspace,source['id'])['result']['visual']['observations'][0]
    assert corrected['read_certainty']=='RECOVERED'
    assert binding.rank(binding.bound_certainty(corrected)) <= binding.rank(binding.bound_certainty(original))
    assert corrected.get('bind_certainty')==original.get('bind_certainty')
    store.get_evidence_item(workspace,machine['id'])['content']='changed original'
    with pytest.raises(ValueError):
        dx.review_text_correction(store,workspace,source['id'],correction['id'],'accept','reviewer')


def test_frame_is_separate_derived_source_and_original_immutable(project):
    _,store,workspace,_,_=project
    original=__import__('pathlib').Path(store.store_path)/'original.png'
    Image.new('RGB',(200,120),'white').save(original)
    source=workspace.sources[0]
    raw=original.read_bytes()
    source.update(name='original.png',file_path=str(original),file_hash=hashlib.sha256(raw).hexdigest())
    store.save(workspace)
    frame=dx.create_document_frame(store,workspace,source['id'],[[.1,.1],[.9,.1],[.9,.9],[.1,.9]],1.4,90,'document border','reviewer')
    data=json.loads(frame['content'])
    assert data['derived_source_id']!=source['id']
    assert original.read_bytes()==raw
    assert dx.frame_qualification(workspace,source['id'])['angles']=='UNRESOLVED'
    assert dx.source_review_state(workspace,source['id'])['result'] is None
