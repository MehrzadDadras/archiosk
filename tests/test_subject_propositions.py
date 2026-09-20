import copy
from unittest.mock import patch

import pytest

from tests.test_kernel_mapping import project
from services.case_workspace import CaseWorkspaceError
from services.runtime_observation import read


def setup_proposition(project):
    app, store, workspace, evidence, client = project
    attention = store.record_go_attention(workspace, 'reviewer', 'Inspect sourced subject propositions', [evidence['id']])
    response = client.post('/projects/project/attention', data=dict(action='record_subject',
        analysis_id=attention['id'], subject_name='Evaluation entity', subject_role='institutional_investor'))
    assert response.status_code == 303
    subject = store.get('project').participants[-1]
    form = dict(action='subject_proposition', analysis_id=attention['id'], subject_key='participant:'+subject['id'],
        property_key='sector', scope_key='declared-vehicle', kind='TOKEN_SET', value='EVALUATION_SECTOR',
        vocabulary='evaluation-sectors', unit='', qualifiers='[]', view_basis='VIEW_INVARIANT', evidence_id=evidence['id'],
        original_quote=evidence['content'], source_class='REPORTING', temporal_class='HISTORICAL_ACTIVITY',
        as_of='2020-01-01', valid_until='', attribution='agent_assessment',
        reason='Proposed categorization only; it is not a verified mandate.')
    return attention, subject, form


def test_real_route_persists_individual_claim_and_reload_does_not_compare_or_mutate(project):
    app, store, workspace, evidence, client = project
    attention, subject, form = setup_proposition(project)
    before = copy.deepcopy((workspace.sources, workspace.evidence_items))
    response = client.post('/projects/project/attention', data=form)
    assert response.status_code == 303
    saved = store.get('project')
    claim = saved.claims[-1]
    assert claim['structured_proposition']['normalization']['subject_key'] == 'participant:'+subject['id']
    assert claim['adoption_state'] == 'proposed'
    assert claim['author_type'] == 'ai' and claim['claim_class'] == 'ai_proposal'
    assert claim['structured_proposition']['original_quote'] == evidence['content']
    assert (saved.sources, saved.evidence_items) == before
    assert len(saved.analyses) == 1
    trace = read(app, response.headers['X-ARCHIOSK-Observation'])
    assert claim['runtime_trace_id'] == trace['id']
    assert any(e['owner'].endswith('.record_subject_proposition') and e['phase'] == 'INVOKED' for e in trace['events'])
    original = store._path_for('project').read_bytes()
    with patch('services.cross_modal_investigation.compare_normalized_information', side_effect=AssertionError('Reload must not compare')):
        page = client.get(response.location)
    assert page.status_code == 200 and b'HISTORICAL_ACTIVITY' in page.data
    assert b'NOT_ESTABLISHED' in page.data and b'temporal applicability UNRESOLVED' in page.data
    assert b'<script>alert(1)</script>' not in page.data
    assert store._path_for('project').read_bytes() == original
    trace = read(app, page.headers['X-ARCHIOSK-Observation'])
    assert not any(e['owner'].endswith('.compare_normalized_information') for e in trace['events'])
    assert trace['events'][-1]['phase'] == 'SURFACED'


def test_correction_keeps_original_claim_and_cited_machine_observation(project):
    _, store, _, evidence, client = project
    attention, _, form = setup_proposition(project)
    assert client.post('/projects/project/attention', data=form).status_code == 303
    original = copy.deepcopy(store.get('project').claims[-1])
    edited = client.get('/projects/project/attention', query_string={'analysis':attention['id'], 'claim':original['id']})
    assert edited.status_code == 200 and b'Correct proposition through a successor' in edited.data
    form.update(predecessor_id=original['id'], value='OTHER_EVALUATION_SECTOR', temporal_class='CURRENTNESS_UNRESOLVED',
        reason='Correct the categorization; current applicability is not established.')
    assert client.post('/projects/project/attention', data=form).status_code == 303
    saved = store.get('project')
    assert saved.claims[0] == original
    assert store.get_evidence_item(saved, evidence['id']) == evidence
    assert len(saved.claims) == 2 and len(saved.supersessions) == 1
    assert store.resolve_claim_status(saved, original['id'])['status'] == 'superseded'
    assert saved.claims[-1]['adoption_state'] == 'proposed'
    assert saved.claims[-1]['structured_proposition']['temporal_class'] == 'CURRENTNESS_UNRESOLVED'
    successor = store.inspect_subject_propositions(saved, 'reviewer', attention['id'])[-1]
    assert successor['predecessor_claim_id'] == original['id']
    assert any(change['field'] == 'temporal_class' and change['before'] == 'HISTORICAL_ACTIVITY' for change in successor['changes'])
    assert client.get('/projects/project/attention?analysis='+attention['id']+'&claim=foreign').status_code == 404


def test_adoption_is_only_interpretation_and_rejection_does_not_erase_history(project):
    _, store, _, _, client = project
    attention, _, form = setup_proposition(project)
    client.post('/projects/project/attention', data=form)
    claim = store.get('project').claims[-1]
    review = dict(action='review_subject_proposition', analysis_id=attention['id'], claim_id=claim['id'],
        outcome='accept_interpretation', attribution='human_reviewed', reason='Retain this classification as an interpretation only.')
    assert client.post('/projects/project/attention', data=review).status_code == 303
    saved = store.get('project')
    assert len(saved.derived_observations) == 1 and len(saved.analyses) == 1
    row = store.inspect_subject_propositions(saved, 'reviewer', attention['id'])[0]
    assert row['authority'] == 'NOT_ESTABLISHED' and row['temporal_applicability'] == 'UNRESOLVED'
    client.post('/projects/project/attention', data=review)
    assert len(store.get('project').derived_observations) == 1
    review.update(outcome='reject', reason='Classification is not adequately supported.')
    assert client.post('/projects/project/attention', data=review).status_code == 303
    saved = store.get('project')
    assert saved.claims[-1]['adoption_state'] == 'rejected' and len(saved.derived_observations) == 1
    assert saved.claims[-1]['structured_proposition'] == claim['structured_proposition']


@pytest.mark.parametrize('change', [
    {'subject_key':'participant:foreign'}, {'evidence_id':'foreign'},
    {'original_quote':'An invented source quote'}, {'source_class':'VERIFIED_PRIMARY_TRUTH'},
    {'temporal_class':'AUTHORITATIVE_CURRENT'}, {'as_of':'yesterday'},
    {'as_of':'2025-01-01', 'valid_until':'2024-01-01'}, {'qualifiers':''},
    {'kind':'NUMBER', 'value':'NaN', 'unit':'CAD'}, {'value':'free prose is not a token'},
    {'view_basis':'UNRESOLVED'},
    {'attribution':''},
])
def test_invalid_proposition_does_not_leave_claim_or_investigation_shell(project, change):
    _, store, _, _, client = project
    _, _, form = setup_proposition(project)
    original = store._path_for('project').read_bytes()
    form.update(change)
    response = client.post('/projects/project/attention', data=form)
    assert response.status_code == 303
    assert store._path_for('project').read_bytes() == original


def test_changed_evidence_weakens_integrity_and_blocks_adoption(project):
    _, store, _, evidence, client = project
    attention, _, form = setup_proposition(project)
    client.post('/projects/project/attention', data=form)
    saved = store.get('project')
    claim = saved.claims[-1]
    store.get_evidence_item(saved, evidence['id'])['content'] += ' later alteration'
    store.save(saved)
    row = store.inspect_subject_propositions(saved, 'reviewer', attention['id'])[0]
    assert row['source_integrity'] == 'UNRESOLVED'
    with pytest.raises(CaseWorkspaceError, match='fingerprints'):
        store.review_subject_proposition(saved, 'reviewer', attention['id'], claim['id'], 'accept_interpretation', 'Review', attribution='human_reviewed')
    assert saved.derived_observations == []


def test_expired_attention_and_private_case_cannot_record_or_review_propositions(project):
    _, store, _, _, client = project
    attention, _, form = setup_proposition(project)
    saved = store.get('project')
    saved.analyses[0]['attention_scope']['expires_at'] = '2000-01-01T00:00:00+00:00'
    store.save(saved)
    original = store._path_for('project').read_bytes()
    client.post('/projects/project/attention', data=form)
    assert store._path_for('project').read_bytes() == original
    store.create_case(saved, 'Private', 'Private', created_by='someone-else')
    assert client.post('/projects/project/attention', data=form).status_code == 403


def test_evaluation_provenance_is_inherited_and_cannot_be_removed_on_correction(project):
    _, store, _, _, client = project
    attention, _, form = setup_proposition(project)
    saved = store.get('project')
    saved.analyses[0]['attention_scope']['evaluation_only'] = True
    store.save(saved)
    client.post('/projects/project/attention', data=form)
    saved = store.get('project')
    claim = saved.claims[-1]
    assert claim['structured_proposition']['evaluation_only']
    forged = copy.deepcopy(claim['structured_proposition'])
    forged['evaluation_only'] = False
    original = store._path_for('project').read_bytes()
    with pytest.raises(CaseWorkspaceError, match='originating evaluation'):
        store.supersede_claim(saved, claim['id'], claim['statement'], claim['claim_class'], claim['method'],
            claim['confidence_state'], claim['author_type'], 'Invalid attempted promotion', 'reviewer',
            structured_proposition=forged)
    assert store._path_for('project').read_bytes() == original


def test_claim_payload_cannot_supply_authority_and_review_cannot_promote(project):
    _, store, _, _, client = project
    attention, _, form = setup_proposition(project)
    client.post('/projects/project/attention', data=form)
    saved = store.get('project')
    claim = saved.claims[-1]
    original = store._path_for('project').read_bytes()
    forged = copy.deepcopy(claim['structured_proposition'])
    forged['authority'] = 'VERIFIED'
    with pytest.raises(CaseWorkspaceError, match='explicit classification'):
        store.supersede_claim(saved, claim['id'], claim['statement'], claim['claim_class'], claim['method'],
            claim['confidence_state'], claim['author_type'], 'Attempted strengthening', 'reviewer', structured_proposition=forged)
    with pytest.raises(CaseWorkspaceError, match='separate action'):
        store.review_subject_proposition(saved, 'reviewer', attention['id'], claim['id'], 'promote', 'Attempted strengthening', attribution='human_reviewed')
    assert store._path_for('project').read_bytes() == original


def test_agent_cannot_record_human_adoption_or_rejection(project):
    _, store, _, _, client = project
    attention, _, form = setup_proposition(project)
    client.post('/projects/project/attention', data=form)
    saved = store.get('project')
    claim = saved.claims[-1]
    original = store._path_for('project').read_bytes()
    for outcome in ('accept_interpretation', 'reject'):
        with pytest.raises(CaseWorkspaceError, match='human must explicitly attest'):
            store.review_subject_proposition(saved, 'reviewer', attention['id'], claim['id'], outcome,
                'An automated suggestion is not a human decision.', attribution='agent_assessment')
    assert store._path_for('project').read_bytes() == original
