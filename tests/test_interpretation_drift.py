"""Real proposition review, dependency and retained professional-review path."""
import copy

import pytest

from tests.test_kernel_mapping import project
from tests.test_scoped_proposition_review import prepared
from tests.test_transaction_identity import admit
from tests.test_normalized_comparison import premise
from services.cross_modal_investigation import inspect_interpretation_drift, trace_governing_root


def interpretation_scope(project, *, changed=False, qualifier_loss=False, authorization=None, reviewed=True, dependency=True):
    store, workspace, evidence, _, _, proposal, _ = prepared(project)
    attention = store.record_go_attention(workspace, 'reviewer', 'Trace the intended requirement', [evidence['id']])
    participant = store.record_participant(workspace, 'Controlled subject', 'assembly', 'reviewer')
    subject = 'participant:' + participant['id']

    def append(value, quote, *, property_key='clearance', qualifiers=None, kind='NUMBER', vocabulary='', review=True):
        normalized = premise(value, subject_key=subject, property_key=property_key, scope_key='assembly-scope',
            kind=kind, unit='mm' if kind == 'NUMBER' else '', vocabulary=vocabulary,
            qualifiers=qualifiers or [], premise_ids=[evidence['id']])
        claim = store.record_subject_proposition(workspace, 'reviewer', attention['id'], normalized,
            'PROJECT_DOCUMENT', 'DATED_REQUIREMENT', quote, 'Controlled source interpretation in test only.',
            as_of='2024-01-01', valid_until='2024-12-31', attribution='agent_assessment')
        if review:
            admit(store, workspace, claim, proposal)
        return claim

    upstream = append('100', evidence['content'], qualifiers=['MINIMUM'] if qualifier_loss else [])
    # Both exact quotes are contained in the immutable source. Their typed
    # interpretations are positively reviewed by the controlled test fixture.
    target = append('80' if changed else '100', evidence['content'][:20], review=reviewed)
    if dependency:
        edge = store.record_relationship(workspace, 'claim', target['id'], 'claim', upstream['id'], 'based_on')
        store.confirm_relationship(workspace, edge['id'], 'reviewer')
    if authorization:
        for decision in authorization.split(','):
            append([upstream['id'], target['id']], evidence['content'], property_key='interpretation_change_authorization',
                kind='TOKEN_SET', vocabulary='claim_transition', qualifiers=[decision])
    return store, workspace, attention, evidence, upstream, target


@pytest.mark.parametrize('changes,state,meaning', [
    ({}, 'MEANING_PRESERVED', 'MEANING_PRESERVED'),
    ({'changed':True}, 'UNRESOLVED', 'MEANING_CHANGED'),
    ({'qualifier_loss':True}, 'UNRESOLVED', 'MEANING_CHANGED'),
    ({'changed':True,'authorization':'AUTHORIZED'}, 'AUTHORIZED_CHANGE', 'MEANING_CHANGED'),
    ({'changed':True,'authorization':'PROHIBITED'}, 'INTERPRETATION_DRIFT', 'MEANING_CHANGED'),
    ({'changed':True,'authorization':'AUTHORIZED,PROHIBITED'}, 'CONFLICTING', 'MEANING_CHANGED'),
    ({'reviewed':False}, 'UNRESOLVED', 'MEANING_PRESERVED'),
    ({'dependency':False}, 'UNRESOLVED', 'MEANING_PRESERVED'),
])
def test_wording_meaning_and_authorization_are_separate(project, changes, state, meaning):
    store, workspace, _, _, upstream, target = interpretation_scope(project, **changes)
    before = store._path_for('project').read_bytes()
    result = inspect_interpretation_drift(store, workspace, upstream['id'], target['id'], query_date='2024-06-01')
    assert result['state'] == state
    assert result['meaning_state'] == meaning
    assert result['wording_state'] == 'WORDING_CHANGED'
    assert not result['canonical'] and result['authority'] == 'UNCHANGED'
    assert store._path_for('project').read_bytes() == before


def test_same_scoped_root_returns_to_target_without_following_peripheral_links(project):
    store, workspace, _, _, upstream, target = interpretation_scope(project)
    trace = trace_governing_root(store, workspace, target['id'], target_type='claim', query_date='2024-06-01')
    assert trace['state'] == 'QUALIFIED'
    assert trace['root'] == upstream['id'] and trace['return_target'] == target['id']
    assert [row['claim_id'] for row in trace['trace']] == [target['id'], upstream['id']]
    stale = trace_governing_root(store, workspace, target['id'], target_type='claim', query_date='2025-06-01')
    assert stale['state'] == 'UNRESOLVED' and stale['root'] is None


def test_real_professional_route_invokes_and_retains_drift_and_root_trace(project):
    app, _, _, _, client = project
    store, workspace, attention, evidence, upstream, target = interpretation_scope(project,
        changed=True, authorization='PROHIBITED')
    original = copy.deepcopy((workspace.sources, workspace.evidence_items, workspace.claims))
    response = client.post('/projects/project/attention', data=dict(action='professional_review',
        analysis_id=attention['id'], narrative='structural_coordination', focus_id=evidence['id'],
        subject='Controlled assembly', representation_class='PLAN', current_resolution='OVERALL',
        required_resolution='LOCAL_TIE_IN', project_phase='design-review', discipline='structural',
        reason='Review the downstream deviation against source intent.', upstream_claim_id=upstream['id'],
        target_claim_id=target['id'], query_date='2024-06-01'))
    assert response.status_code == 303
    saved = store.get('project')
    result = saved.analyses[-1]['governed_result']
    assert result['interpretation_drift']['state'] == 'INTERPRETATION_DRIFT'
    assert result['proposition_root_trace']['root'] == upstream['id']
    assert (saved.sources, saved.evidence_items, saved.claims) == original
    before = store._path_for('project').read_bytes()
    page = client.get(response.location)
    assert page.status_code == 200 and b'INTERPRETATION_DRIFT' in page.data
    assert store._path_for('project').read_bytes() == before
    from services.runtime_observation import read
    trace = read(app, response.headers['X-ARCHIOSK-Observation'])
    assert any(e['phase'] == 'INVOKED' and e['owner'].endswith('.inspect_interpretation_drift') for e in trace['events'])
    response = client.post('/projects/project/attention', data=dict(action='professional_presentation', review_id=saved.analyses[-1]['id']))
    assert response.status_code == 303
    product = store.get('project').work_products[-1]
    assert 'INTERPRETATION_DRIFT' in str(product['sections'])
    assert target['id'] in str(product['sections']) and upstream['id'] in str(product['sections'])
