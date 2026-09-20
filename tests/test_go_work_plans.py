"""Procedure history uses the real workspace/route, never a parallel store."""
import json

import pytest

from services.case_workspace import CaseWorkspaceError
from tests.test_kernel_mapping import project


def declare(client, evidence):
    response = client.post('/projects/project/attention', data=dict(
        declare_work_plan='yes', objective='Review the retained source', included_id=evidence['id'],
        csrf_token='must-not-be-persisted'))
    assert response.status_code == 200
    return response.json['plan']


def test_declaration_precedes_execution_preserves_evidence_and_reload(project):
    app, store, workspace, evidence, client = project
    original = json.dumps(workspace.evidence_items, sort_keys=True)
    plan = declare(client, evidence)
    retained = store.get('project')
    assert not retained.analyses
    assert plan['result_state']['status'] == 'PLANNED' and plan['authority'] == 'NONE'
    assert 'must-not-be-persisted' not in store._path_for('project').read_text(encoding='utf-8')
    assert len(retained.investigation_steps) == 1
    before = store._path_for('project').read_bytes()
    for _ in range(2):
        page = client.get('/projects/project/attention')
        assert page.status_code == 200
        # Production serves static assets with a long immutable cache. Reload
        # must reference the new review assets instead of the prior bare URL.
        markup = page.get_data(as_text=True)
        assert 'css/survey_evaluation.css?v=' in markup
        assert 'js/go_work_plan.js?v=' in markup
    assert store._path_for('project').read_bytes() == before
    # Caller cannot replace a declared objective/selection at execution time.
    response = client.post('/projects/project/attention', data=dict(plan_id=plan['plan_id'],
        action='subject_proposition', objective='forged replacement'))
    assert response.status_code == 303
    retained = store.get('project')
    assert len(retained.analyses) == 1
    assert retained.analyses[0]['objective'] == 'Review the retained source'
    assert json.dumps(retained.evidence_items, sort_keys=True) == original
    steps = retained.investigation_steps
    assert [s['step_kind'] for s in steps] == ['governed_work_plan', 'work_plan_execution', 'work_plan_result']
    assert steps[-1]['governed_work_plan']['status'] == 'PARTIAL'
    assert steps[-1]['governed_work_plan']['analysis_ids'] == [retained.analyses[0]['id']]
    from services.runtime_observation import read
    trace = read(app, response.headers['X-ARCHIOSK-Observation'])
    invoked = [e['owner'] for e in trace['events'] if e['phase'] == 'INVOKED']
    prefix = 'services.case_workspace.CaseWorkspaceStore.'
    assert invoked.index(prefix+'begin_go_work_plan') < invoked.index(prefix+'record_go_attention') < invoked.index(prefix+'finish_go_work_plan')
    assert client.get(response.location).status_code == 200
    before = store._path_for('project').read_bytes()
    assert client.get(response.location).status_code == 200
    replay = client.post('/projects/project/attention', data={'plan_id':plan['plan_id']})
    assert replay.status_code == 303
    assert store._path_for('project').read_bytes() == before


def test_revision_preserves_original_plan_and_changed_outside_records(project):
    _, store, workspace, evidence, client = project
    plan = declare(client, evidence)
    workspace = store.get('project')
    outside = store.register_evidence_item(workspace, evidence['source_id'], 'direct_source_evidence',
        'Material information outside the selected attention', 'text')
    client.post('/projects/project/attention', data={'plan_id':plan['plan_id']})
    workspace = store.get('project')
    revision = next(s for s in workspace.investigation_steps if s['step_kind'] == 'work_plan_revision')
    assert revision['governed_work_plan']['changed_records']['evidence_items'] == [outside['id']]
    assert workspace.investigation_steps[0]['governed_work_plan'] == plan
    page = client.get('/projects/project/attention').get_data(as_text=True)
    assert 'PLAN_REVISION' in page and outside['id'] in page


def test_foreign_actor_missing_plan_and_mutation_action_refused(project):
    _, store, workspace, evidence, client = project
    plan = declare(client, evidence)
    workspace = store.get('project')
    before = store._path_for('project').read_bytes()
    with pytest.raises(CaseWorkspaceError):
        store.begin_go_work_plan(workspace, 'other-user', plan['plan_id'])
    with pytest.raises(CaseWorkspaceError):
        store.begin_go_work_plan(workspace, 'reviewer', 'missing')
    response = client.post('/projects/project/attention', data=dict(declare_work_plan='yes', action='DELETE_ITEMS'))
    assert response.status_code == 400
    assert store._path_for('project').read_bytes() == before


def test_domain_refusal_is_persisted_without_completion_claim(project):
    _, store, workspace, evidence, client = project
    response = client.post('/projects/project/attention', data=dict(declare_work_plan='yes',
        objective='', included_id=evidence['id']))
    plan = response.json['plan']
    assert client.post('/projects/project/attention', data={'plan_id':plan['plan_id']}).status_code == 303
    workspace = store.get('project')
    report = store.inspect_go_work_plans(workspace, 'reviewer')[0]
    assert report['status'] == 'REFUSED' and not workspace.analyses
    assert report['history'][-1]['governed_work_plan']['error']


def test_concurrent_loaded_snapshots_cannot_start_plan_twice(project):
    _, store, _, evidence, client = project
    plan = declare(client, evidence)
    first, stale = store.get('project'), store.get('project')
    store.begin_go_work_plan(first, 'reviewer', plan['plan_id'])
    with pytest.raises(CaseWorkspaceError):
        store.begin_go_work_plan(stale, 'reviewer', plan['plan_id'])
    assert len([s for s in store.get('project').investigation_steps if s['step_kind'] == 'work_plan_execution']) == 1


def test_completion_reads_actual_trace_result_sources_and_surfacing(project):
    app,store,_,evidence,client=project
    with client.session_transaction() as session:
        session['survey_observe']=False
    plan=declare(client,evidence)
    response=client.post('/projects/project/attention',data={'plan_id':plan['plan_id']})
    assert 'X-ARCHIOSK-Observation' in response.headers
    client.get(response.location)
    workspace=store.get('project')
    before=store._path_for('project').read_bytes()
    report=store.inspect_go_work_plans(workspace,'reviewer',app=app)[0]
    assert all(report['proof'][key]['established'] for key in
        ('runtime_invocation','persisted_result','evidence_traceability','surfaced_output'))
    assert not report['proof']['regression_tests']['established'] and report['status']=='PARTIAL'
    assert store._path_for('project').read_bytes()==before
    workspace.evidence_items=[]
    weakened=store.inspect_go_work_plans(workspace,'reviewer',app=app)[0]
    assert not weakened['proof']['evidence_traceability']['established']


def test_unsupported_parameters_and_destructive_action_do_not_enter_plan_history(project):
    _,store,workspace,evidence,client=project
    before=store._path_for('project').read_bytes()
    for values in ({'password':'private'}, {'action':'DELETE_ITEMS'}, {'objective':['one','two']}):
        data=dict(declare_work_plan='yes',objective='Review',included_id=evidence['id'])
        data.update(values)
        assert client.post('/projects/project/attention',data=data).status_code==400
    assert store._path_for('project').read_bytes()==before
