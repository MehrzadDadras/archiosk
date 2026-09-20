import copy
from unittest.mock import patch

import pytest

from tests.test_kernel_mapping import project
from tests.test_normalized_comparison import premise
from tests.test_subject_propositions import setup_proposition
from services.cross_modal_investigation import match_normalized_criteria, inspect_declared_temporal_scope


def criterion(key='sector', value='100', **changes):
    return dict(dict(id=key, mandatory=True, required=premise(), candidate=premise(value),
                     operator='EQUAL', blocked_reason=''), **changes)


def test_mandatory_failure_cannot_be_offset_by_many_matches():
    rows = [criterion(str(i)) for i in range(15)] + [criterion('failed', '101')]
    result = match_normalized_criteria(rows)
    assert result['state'] == 'NON_MATCH'
    assert result['mandatory_failures'] == ['failed']
    assert result['factual_fit'] == 'UNRESOLVED' and not result['canonical']


@pytest.mark.parametrize('row,state', [
    (criterion(), 'MATCH'), (criterion(candidate=None), 'UNRESOLVED'),
    (criterion(blocked_reason='Historical activity only'), 'UNRESOLVED'),
    (criterion(candidate=premise(unit='USD')), 'UNRESOLVED'),
    (criterion('optional', '101', mandatory=False), 'PARTIAL'),
])
def test_criteria_preserve_missing_and_incomparable_premises(row, state):
    assert match_normalized_criteria([row])['state'] == state


def test_no_duplicate_votes_or_opaque_score_override():
    assert match_normalized_criteria([criterion(), criterion()])['state'] == 'REFUSED'
    assert match_normalized_criteria([criterion(score=100)])['state'] == 'REFUSED'
    assert match_normalized_criteria([criterion(), criterion('missing', candidate=None)])['state'] == 'PARTIAL'


@pytest.mark.parametrize('temporal,until,query,expected', [
    ('HISTORICAL_ACTIVITY', '2027-01-01', '2026-09-20', 'CURRENTNESS_UNRESOLVED'),
    ('RECENT_COMMITMENT', '2027-01-01', '2026-09-20', 'CURRENTNESS_UNRESOLVED'),
    ('CURRENT_DISCLOSED_MANDATE', None, '2026-09-20', 'CURRENTNESS_UNRESOLVED'),
    ('CURRENT_DISCLOSED_MANDATE', '2027-01-01', '2026-09-20', 'DECLARED_INTERVAL_CONTAINS_QUERY'),
    ('CURRENT_DISCLOSED_MANDATE', '2026-01-01', '2026-09-20', 'CURRENTNESS_UNRESOLVED'),
])
def test_temporal_meanings_do_not_substitute_for_current_mandates(temporal, until, query, expected):
    result = inspect_declared_temporal_scope(dict(temporal_class=temporal, as_of='2026-01-01',
        valid_until=until), query, expected_class='CURRENT_DISCLOSED_MANDATE')
    assert result['state'] == expected and result['authority'] == 'UNCHANGED'


@pytest.mark.parametrize('context,label', [('construction','CONSISTENT'), ('rfp','MATCH'), ('investment','FIT'), ('asset','FIT')])
def test_matching_owner_preserves_sources_and_persists_qualified_result(project, context, label):
    _, store, _, _, client = project
    attention, subject, form = setup_proposition(project)
    for temporal in ('DATED_REQUIREMENT', 'CURRENT_DISCLOSED_MANDATE'):
        form.update(temporal_class=temporal, as_of='2026-01-01', valid_until='2027-01-01')
        assert client.post('/projects/project/attention', data=form).status_code == 303
    workspace = store.get('project')
    before = copy.deepcopy((workspace.sources, workspace.evidence_items, workspace.claims))
    rows = [dict(required_claim_id=workspace.claims[0]['id'], candidate_claim_id=workspace.claims[1]['id'],
        mandatory=True, operator='CONTAINS_ALL', candidate_temporal_class='CURRENT_DISCLOSED_MANDATE')]
    result = store.run_requirement_matching(workspace, 'reviewer', attention['id'], 'participant:'+subject['id'],
        rows, context, 'Compare explicit sourced interpretations.', query_date='2026-09-20')
    assert result['governed_result']['model_label'] == label
    assert result['governed_result']['state'] == 'UNRESOLVED'
    assert (workspace.sources, workspace.evidence_items, workspace.claims) == before
    assert len(workspace.analyses) == 2


def test_real_matching_route_reload_and_superseded_premises(project):
    app, store, _, _, client = project
    attention, subject, form = setup_proposition(project)
    for temporal in ('DATED_REQUIREMENT', 'CURRENT_DISCLOSED_MANDATE'):
        form.update(temporal_class=temporal, as_of='2026-01-01', valid_until='2027-01-01')
        client.post('/projects/project/attention', data=form)
    claims = store.get('project').claims
    command = dict(action='requirement_matching', analysis_id=attention['id'],
        target_subject='participant:'+subject['id'], context_key='investment', reason='Inspect capital alignment.',
        require_currentness='yes', query_date='2026-09-20', criterion_0_required=claims[0]['id'],
        criterion_0_candidate=claims[1]['id'], criterion_0_mandatory='yes', criterion_0_operator='CONTAINS_ALL',
        criterion_0_temporal='CURRENT_DISCLOSED_MANDATE')
    response = client.post('/projects/project/attention', data=command)
    assert response.status_code == 303
    from services.runtime_observation import read
    trace = read(app, response.headers['X-ARCHIOSK-Observation'])
    assert any(e['owner'].endswith('.match_normalized_criteria') and e['phase'] == 'INVOKED' for e in trace['events'])
    original = store._path_for('project').read_bytes()
    with patch('services.cross_modal_investigation.match_normalized_criteria', side_effect=AssertionError('Reload must not match')):
        page = client.get(response.location)
    assert page.status_code == 200 and b'conditional model FIT' in page.data
    assert b'Governed factual fit: <strong>UNRESOLVED' in page.data
    assert store._path_for('project').read_bytes() == original
    form.update(predecessor_id=claims[1]['id'], value='OTHER_SECTOR', reason='Correct the candidate classification.')
    client.post('/projects/project/attention', data=form)
    page = client.get(response.location)
    assert b'REVIEW_REQUIRED' in page.data
    assert store.get('project').analyses[-1]['governed_result']['model_label'] == 'FIT'
    client.post('/projects/project/attention', data=command)
    assert store.get('project').analyses[-1]['governed_result']['model_label'] == 'UNRESOLVED'


def test_foreign_claim_rejected_without_analysis(project):
    _, store, _, _, client = project
    attention, subject, form = setup_proposition(project)
    client.post('/projects/project/attention', data=form)
    response = client.post('/projects/project/attention', data=dict(action='requirement_matching',
        analysis_id=attention['id'], target_subject='participant:'+subject['id'], context_key='investment',
        reason='Review.', require_currentness='no', criterion_0_required='foreign', criterion_0_mandatory='yes',
        criterion_0_operator='EQUAL', criterion_0_temporal='CURRENT_DISCLOSED_MANDATE'))
    assert response.status_code in (200, 303)
    assert len(store.get('project').analyses) == 1
