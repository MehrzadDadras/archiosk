"""Objective scopes exercise the real UI/owner and cannot strengthen evidence."""
import copy

import pytest

from tests.test_kernel_mapping import project
from services import survey_evaluation as evaluation
from services.case_workspace import CaseWorkspaceStore, CaseWorkspaceError


def test_post_consumes_persisted_scope_and_reload_is_read_only(project):
    app, store, workspace, evidence, client = project
    before = copy.deepcopy((workspace.sources, workspace.evidence_items, workspace.relationships))
    response = client.post('/projects/project/attention', data={
        'objective': 'Review readable prose', 'included_id': evidence['id'], 'lifetime_minutes': '60'})
    assert response.status_code == 303
    saved = store.get('project')
    assert len(saved.analyses) == 1
    scope = saved.analyses[0]['attention_scope']
    assert scope['state'] == 'SCOPED'
    assert scope['entries'][0]['admission']['authority'] == 'NOT_ESTABLISHED'
    assert (saved.sources, saved.evidence_items, saved.relationships) == before
    persisted = store._path_for('project').read_bytes()
    page = client.get(response.location)
    assert page.status_code == 200
    assert b'Focused evidence' in page.data and b'SOURCE_REFERENCE' in page.data
    assert client.get(response.location).status_code == 200
    assert store._path_for('project').read_bytes() == persisted
    from services.runtime_observation import read
    trace = read(app, response.headers['X-ARCHIOSK-Observation'])
    assert any(e['phase'] == 'INVOKED' and e['owner'].endswith('.record_go_attention') for e in trace['events'])


def test_deemphasis_and_missing_evidence_never_erases_truth(project):
    _, store, workspace, evidence, _ = project
    result = store.record_go_attention(workspace, 'reviewer', 'readable', de_emphasized_ids=[evidence['id']])
    assert result['attention_scope']['state'] == 'UNRESOLVED'
    assert result['attention_scope']['entries'][0]['category'] == 'de_emphasized'
    assert workspace.evidence_items[0] == evidence
    with pytest.raises(CaseWorkspaceError):
        store.record_go_attention(workspace, 'reviewer', 'readable', ['foreign'])
    with pytest.raises(CaseWorkspaceError):
        store.record_go_attention(workspace, 'reviewer', 'readable', [evidence['id']], [evidence['id']])
    assert len(store.get('project').analyses) == 1


def test_evaluation_uses_owned_scope_and_normal_template_context(project):
    app, customer_store, customer, _, client = project
    original = customer_store._path_for(customer.project_id).read_bytes()
    identifier = evaluation.create(app, 'missing-monument', 'reviewer')
    path = evaluation.location(app, identifier)
    record = evaluation._read(path)
    route = f'/admin/survey-evaluation/{identifier}/attention'
    assert client.get(route).status_code == 200
    response = client.post(route, data={'objective': 'Review monument', 'included_id': record['operation_evidence_id']})
    assert response.status_code == 303
    page = client.get(response.location)
    assert page.status_code == 200 and b'EVALUATION_INPUT' in page.data
    scope = CaseWorkspaceStore(path / 'registry').get(record['project_id']).analyses[-1]['attention_scope']
    assert scope['evaluation_only']
    assert customer_store._path_for(customer.project_id).read_bytes() == original


def test_temporary_edge_ui_keeps_hypothesis_out_of_canonical_confirmation(project):
    _, store, workspace, first, client = project
    second = store.register_evidence_item(workspace, first['source_id'], 'direct_source_evidence', 'Second label', 'text')
    analysis = store.record_go_attention(workspace, 'reviewer', 'Review labels', [first['id'], second['id']])
    response = client.post('/projects/project/attention', data=dict(action='temporary_relationship',
        analysis_id=analysis['id'], from_id=first['id'], to_id=second['id'], evidence_id=first['id'],
        hypothesis='Possible same subject', reason='A question for review; not an identity assertion'))
    assert response.status_code == 303
    saved = store.get('project')
    edge = saved.relationships[-1]
    assert edge['provisional'] and edge['relationship_type'] == 'analytical_hypothesis'
    assert store.resolve_relationship_status(saved, edge['id'])['status'] == 'temporary'
    assert b'Possible same subject' in client.get(response.location).data
    with pytest.raises(CaseWorkspaceError):
        store.confirm_relationship(saved, edge['id'], 'reviewer')
    assert store.get('project').relationships[-1]['provisional']
    assert store.relationships_for(saved, 'evidence_item', first['id']) == []
    assert store.relationships_for(saved, 'evidence_item', first['id'], include_temporary=True)[0]['id'] == edge['id']
    from services.cross_modal_investigation import investigate_cross_modal_question
    case = store.create_case(saved, 'Question', 'Review', created_by='reviewer')
    prior_claims = len(saved.claims)
    investigate_cross_modal_question(store, saved, 'What connection is established?', case['id'],
                                     'evidence_item', first['id'], 'reviewer')
    assert len(saved.claims) > prior_claims
    assert all(c['claim_class'] == 'unknown' for c in saved.claims[prior_claims:])
    with pytest.raises(CaseWorkspaceError):
        store.record_temporary_relationship(saved, 'reviewer', analysis['id'], first['id'], 'foreign', 'h', 'r', [first['id']])
