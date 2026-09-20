import copy
from unittest.mock import patch
import pytest
from tests.test_kernel_mapping import project
from services.work_product_export import compress_presentation_records


def item(identifier, **changes):
    semantic = dict(subject='M1', proposition='height', scope='parcel', state='UNRESOLVED', value='144.12',
        authority='NOT_ESTABLISHED', binding='UNRESOLVED', applicability='UNRESOLVED', supersession='current', evaluation_only=True)
    semantic.update(changes)
    return dict(id=identifier, semantic=semantic, raw={'id':identifier}, source_ids=['source'],
                runtime_trace_ids=['job-'+identifier], reasons=['binding','authority'])


def test_twenty_duplicates_preserve_all_occurrences_and_job_traces():
    records=[item(str(i)) for i in range(20)]
    before=copy.deepcopy(records)
    report=compress_presentation_records(records)
    assert report['group_count']==1 and report['groups'][0]['occurrence_count']==20
    assert len(report['groups'][0]['runtime_trace_ids'])==20 and records==before


@pytest.mark.parametrize('change', [dict(value='143.80'),dict(authority='GOVERNING'),dict(binding='BOUND'),
    dict(applicability='APPLIES'),dict(supersession='superseded'),dict(evaluation_only=False),
    dict(temporal_class='HISTORICAL_ACTIVITY'),dict(scope='other'),dict(geometry='METRIC')])
def test_material_distinctions_never_merge(change):
    assert compress_presentation_records([item('a'),item('b',**change)])['group_count']==2


def test_independence_requires_reviewed_pairs_and_never_changes_authority():
    from itertools import combinations
    rows=[item(str(i)) for i in range(5)]
    for i,row in enumerate(rows): row['source_ids']=[str(i)]
    assert compress_presentation_records(rows)['groups'][0]['independent_source_count']==0
    group=compress_presentation_records(rows,list(combinations(map(str,range(5)),2)))['groups'][0]
    assert group['independent_source_count']==5 and group['semantic']['authority']=='NOT_ESTABLISHED'


def test_unresolved_dimensions_remain_recoverable_and_new_disagreement_surfaces():
    report=compress_presentation_records([item('a'),item('b')])
    assert report['groups'][0]['reasons']==['binding','authority']
    report=compress_presentation_records([item('a'),item('b',value='143.80')])
    assert all(group['conflict'] for group in report['groups'])


def test_real_owner_readonly_report_and_filters_do_not_analyze(project):
    app,store,workspace,evidence,client=project
    for _ in range(19):
        store.register_evidence_item(workspace,evidence['source_id'],evidence['evidence_class'],evidence['content'],'text')
    attention=store.record_go_attention(workspace,'reviewer','Inspect readings',[e['id'] for e in workspace.evidence_items])
    before=store._path_for('project').read_bytes()
    report=store.project_attention_report(workspace,'reviewer',attention['id'])
    assert report['occurrence_count']==20
    assert report['group_count']==1, {k:(v,report['groups'][1]['semantic'].get(k)) for k,v in report['groups'][0]['semantic'].items() if v != report['groups'][1]['semantic'].get(k)}
    with patch.object(type(store),'record_go_attention',side_effect=AssertionError('Reload cannot analyze')):
        for filter_key in ('all','material','unresolved','conflicts','changes','evidence','technical'):
            response=client.get('/projects/project/attention',query_string={'analysis':attention['id'],'filter':filter_key})
            assert response.status_code==200
            assert b'What matters' in response.data if filter_key=='all' else True
            assert store._path_for('project').read_bytes()==before
    from services.runtime_observation import read
    trace=read(app,response.headers['X-ARCHIOSK-Observation'])
    assert any(e['owner'].endswith('.project_attention_report') and e['phase']=='INVOKED' for e in trace['events'])


def test_propositions_from_separate_runtime_jobs_keep_both_traces(project):
    from tests.test_subject_propositions import setup_proposition
    _,store,_,_,client=project
    attention,_,form=setup_proposition(project)
    traces=[]
    for _ in range(2):
        response=client.post('/projects/project/attention',data=form)
        assert response.status_code==303
        traces.append(response.headers['X-ARCHIOSK-Observation'])
    workspace=store.get('project')
    before=store._path_for('project').read_bytes()
    report=store.project_attention_report(workspace,'reviewer',attention['id'])
    groups=[g for g in report['groups'] if g['occurrences'][0]['kind']=='claims']
    assert len(groups)==1
    assert groups[0]['occurrence_count']==2
    assert set(groups[0]['runtime_trace_ids'])==set(traces)
    assert len(workspace.claims)==2 and store._path_for('project').read_bytes()==before


def test_noise_and_trace_preserved_with_conflict_taking_priority():
    records=[item('ocr',noise=True),item('trace',technical=True)]
    report=compress_presentation_records(records)
    assert [g['importance'] for g in report['groups']]==['NOISE','TRACE']
    assert all(g['section']=='technical' for g in report['groups'])
    assert [g['occurrences'][0] for g in report['groups']]==records
    conflict=compress_presentation_records([item('ocr',noise=True,state='CONFLICTING')])['groups'][0]
    assert conflict['importance']=='CRITICAL' and conflict['section']=='matters'
    nested=item('review',payload={'coverage':{'representation_necessity':{'representations':[
        {'necessity_class':'REDUNDANT_CONFLICTING'}]}}})
    group=compress_presentation_records([nested])['groups'][0]
    assert group['conflict'] and group['recorded_conflicts']==['REDUNDANT_CONFLICTING']


def test_default_report_does_not_repeat_changed_unresolved_group():
    row=item('changed')
    row['changed']=True
    group=compress_presentation_records([row])['groups'][0]
    assert group['changed'] and group['unresolved'] and group['section']=='changes'


def test_five_independent_sources_use_existing_relationship_owner(project):
    from itertools import combinations
    from tests.test_subject_propositions import setup_proposition
    _,store,_,evidence,client=project
    _,_,form=setup_proposition(project)
    workspace=store.get('project')
    sources=[workspace.sources[0]]
    items=[evidence]
    for index in range(4):
        source=store.add_source(workspace,'Reviewed independent source '+str(index),'','document')
        sources.append(source)
        items.append(store.register_evidence_item(workspace,source['id'],evidence['evidence_class'],evidence['content'],'text'))
    attention=store.record_go_attention(workspace,'reviewer','Compare explicit same-subject readings',[item['id'] for item in items])
    form['analysis_id']=attention['id']
    for evidence in items:
        form['evidence_id']=evidence['id']
        assert client.post('/projects/project/attention',data=form).status_code==303
    workspace=store.get('project')
    report=store.project_attention_report(workspace,'reviewer',attention['id'])
    groups=[g for g in report['groups'] if g['occurrences'][0]['kind']=='claims']
    assert len(groups)==1, [g['semantic'] for g in groups]
    assert groups[0]['source_count']==5 and groups[0]['independent_source_count']==0
    for left,right in combinations(sources,2):
        edge=store.record_relationship(workspace,'source',left['id'],'source',right['id'],'independent_of',
            created_by='reviewer',reason='Local test reviewer independently established source origins.')
        store.confirm_relationship(workspace,edge['id'],'reviewer')
    before=store._path_for('project').read_bytes()
    report=store.project_attention_report(workspace,'reviewer',attention['id'])
    group=next(g for g in report['groups'] if g['occurrences'][0]['kind']=='claims')
    assert group['independent_source_count']==5 and group['semantic']['authority']=='NOT_ESTABLISHED'
    assert len(group['occurrences'])==5 and store._path_for('project').read_bytes()==before
    # A material source-authority distinction splits the display even when the
    # same reviewer has confirmed independent origins for every source pair.
    store.update_source_identity(workspace,sources[-1]['id'],'reviewer',document_authority='governing')
    report=store.project_attention_report(workspace,'reviewer',attention['id'])
    assert len([g for g in report['groups'] if g['occurrences'][0]['kind']=='claims'])==2
