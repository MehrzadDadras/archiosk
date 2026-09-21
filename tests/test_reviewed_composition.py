"""Reviewed composition uses real source Claims, review, Apply and AnalysisRun persistence."""
import copy

import pytest

from tests.test_kernel_mapping import project
from tests.test_reviewed_requirement_matching import matching_scope


def composition_scope(project, *, amounts=('60', '40'), addition=False, divisible=True,
                      partnership=None, missing_candidate=False):
    store, workspace, append, _, criteria, inventory, attention = matching_scope(
        project, candidate_value=amounts[0], candidate_reviewed=not missing_candidate, divisible=divisible)
    requirement_id = criteria[0]['required_claim_id']
    candidates = [(criteria[0]['candidate_claim_id'],
        store.get_claim(workspace, criteria[0]['candidate_claim_id'])['structured_proposition']['normalization']['subject_key'])]
    for index, amount in enumerate(amounts[1:], 2):
        party = store.record_participant(workspace, 'Candidate ' + str(index), 'investor', 'reviewer')
        subject = 'participant:' + party['id']
        claim = append('capital', amount, owner=subject, temporal='CURRENT_DISCLOSED_MANDATE')
        candidates.append((claim['id'], subject))
    if addition:
        append('additive_capacity_basis', [s for _, s in candidates], kind='TOKEN_SET', vocabulary='additive:capital:USD')
    partnership_inputs = []
    if partnership:
        condition = append('control', ['JOINT'], kind='TOKEN_SET', vocabulary='control')
        append('requirement_policy', ['MANDATORY', 'EQUAL', 'CURRENT_DISCLOSED_MANDATE'],
            kind='TOKEN_SET', vocabulary='requirement:' + condition['id'])
        partnership_inventory = append('complete_partnership_inventory', [condition['id']],
            kind='TOKEN_SET', vocabulary='requirement_claims',
            qualifiers=[s for _, s in candidates] if partnership != 'wrong_group' else [candidates[0][1]])
        for index, (_, subject) in enumerate(candidates):
            partner_claim = append('control', ['SOLE' if partnership == 'conflict' and index == 0 else 'JOINT'],
                owner=subject, temporal='CURRENT_DISCLOSED_MANDATE', kind='TOKEN_SET', vocabulary='control',
                reviewed=not (partnership == 'missing' and index == 0))
            partnership_inputs.append((subject, partner_claim, condition, partnership_inventory))
    runs = []
    for claim_id, subject in candidates:
        runs.append(store.run_requirement_matching(workspace, 'reviewer', attention['id'], subject,
            [dict(required_claim_id=requirement_id, candidate_claim_id=claim_id, mandatory=True,
                operator='AT_LEAST', candidate_temporal_class='CURRENT_DISCLOSED_MANDATE')],
            'investment', 'Reviewed capital scope.', query_date='2024-06-01', inventory_claim_id=inventory['id']))
    partnership_runs = []
    for subject, claim, condition, partnership_inventory in partnership_inputs:
        partnership_runs.append(store.run_requirement_matching(workspace, 'reviewer', attention['id'], subject,
            [dict(required_claim_id=condition['id'], candidate_claim_id=claim['id'], mandatory=True,
                operator='EQUAL', candidate_temporal_class='CURRENT_DISCLOSED_MANDATE')],
            'investment', 'Reviewed partnership scope.', query_date='2024-06-01', inventory_claim_id=partnership_inventory['id']))
    return store, workspace, attention, requirement_id, runs, partnership_runs


@pytest.mark.parametrize('amounts,addition,divisible,state,count', [
    (('120',), False, False, 'INDIVIDUAL_CONFIGURATION_FEASIBLE', 1),
    (('60',), False, True, 'PARTIAL_CONFIGURATION', None),
    (('60','40'), False, True, 'CONFIGURATION_UNRESOLVED', None),
    (('60','40'), True, True, 'PARTNERSHIP_COMPATIBILITY_UNRESOLVED', 2),
    (('40','30','30'), True, True, 'PARTNERSHIP_COMPATIBILITY_UNRESOLVED', 3),
    (('60','40','40'), True, True, 'PARTNERSHIP_COMPATIBILITY_UNRESOLVED', 2),
])
def test_reviewed_minimum_composition_persists_without_rewriting_sources(project, amounts, addition, divisible, state, count):
    store, workspace, attention, required, runs, _ = composition_scope(project,
        amounts=amounts, addition=addition, divisible=divisible)
    before = copy.deepcopy((workspace.sources, workspace.evidence_items, workspace.claims, workspace.analyses))
    result = store.run_role_composition(workspace, 'reviewer', attention['id'], [r['id'] for r in runs],
        [required], 'Find the minimum reviewed configuration.', reviewed_scope=True)['governed_result']
    assert result['state'] == state
    assert result['model'].get('minimum_count') == count
    assert result['canonical'] is False
    assert (workspace.sources, workspace.evidence_items, workspace.claims, workspace.analyses[:-1]) == before
    assert store.get('project').analyses[-1]['governed_result'] == result
    if count:
        assert all(a['evidence_refs'] and a['evidence_status'] == 'QUALIFIED'
            for c in result['minimum_configurations'] for a in c['result']['assignments'])
        assert all(not check['remaining']['coverage_complete'] for c in result['minimum_configurations']
            for check in c['removal_checks'])
    if len(amounts) == 3 and count == 2:
        assert len(result['minimum_configurations']) == 2


def test_unreviewed_candidate_cannot_supply_factual_capital(project):
    store, workspace, attention, required, runs, _ = composition_scope(project,
        amounts=('120',), divisible=False, missing_candidate=True)
    result = store.run_role_composition(workspace, 'reviewer', attention['id'], [r['id'] for r in runs],
        [required], 'Review source sufficiency.', reviewed_scope=True)['governed_result']
    assert result['state'] == 'CONFIGURATION_UNRESOLVED'
    assert not result['minimum_configurations']


def test_real_composition_route_surfaces_retained_reviewed_matrix_and_reload_is_read_only(project):
    app, _, _, _, client = project
    store, workspace, attention, required, runs, _ = composition_scope(project, amounts=('120',), divisible=False)
    response = client.post('/projects/project/attention', data=dict(action='role_composition',
        analysis_id=attention['id'], matching_id=[r['id'] for r in runs], required_role_id=[required],
        coverage_mode='reviewed_requirements', reason='Reviewed minimum configuration.'))
    assert response.status_code == 303
    result = store.get('project').analyses[-1]['governed_result']
    assert result['state'] == 'INDIVIDUAL_CONFIGURATION_FEASIBLE'
    before = store._path_for('project').read_bytes()
    page = client.get(response.location)
    assert page.status_code == 200
    assert b'Qualified for the reviewed scope' in page.data
    assert store._path_for('project').read_bytes() == before
    from services.runtime_observation import read
    trace = read(app, response.headers['X-ARCHIOSK-Observation'])
    for owner in ('cover_requirements', 'evaluate_requirement_coverage'):
        assert any(e['phase'] == 'INVOKED' and e['owner'].endswith('.' + owner) for e in trace['events'])


@pytest.mark.parametrize('partnership,expected', [('established', 'JOINT_CONFIGURATION_FEASIBLE'),
    ('missing', 'PARTNERSHIP_COMPATIBILITY_UNRESOLVED'), ('wrong_group', 'PARTNERSHIP_COMPATIBILITY_UNRESOLVED'),
    ('conflict', 'CONFIGURATION_NON_FIT')])
def test_partnership_requires_positive_review_for_exact_configuration(project, partnership, expected):
    store, workspace, attention, required, runs, partners = composition_scope(project,
        addition=True, partnership=partnership)
    result = store.run_role_composition(workspace, 'reviewer', attention['id'], [r['id'] for r in runs],
        [required], 'Separate coverage from partnership.', reviewed_scope=True,
        compatibility_matching_ids=[r['id'] for r in partners])['governed_result']
    assert result['state'] == expected
    assert result['state'] != 'ACTUAL_JV_CONFIRMED'
    assert result['reviewed_configuration']['compatibility_analyses']


def test_later_premise_requires_explicit_re_evaluation_without_erasing_composition(project):
    store, workspace, attention, required, runs, _ = composition_scope(project, amounts=('120',), divisible=False)
    retained = store.run_role_composition(workspace, 'reviewer', attention['id'], [r['id'] for r in runs],
        [required], 'Persist scoped conclusion.', reviewed_scope=True)
    store.register_evidence_item(workspace, workspace.sources[0]['id'], 'direct_source_evidence',
        'Additional governing information requires investigation.', 'text')
    before = store._path_for('project').read_bytes()
    rows = store.inspect_role_compositions(workspace, 'reviewer', attention['id'])
    assert rows[-1]['consumption_state'] == 'REVIEW_REQUIRED'
    assert rows[-1]['run'] == retained
    assert store._path_for('project').read_bytes() == before
    new = store.run_role_composition(workspace, 'reviewer', attention['id'], [r['id'] for r in runs],
        [required], 'Changed source requires new matching.', reviewed_scope=True)
    assert new['governed_result']['state'] == 'CONFIGURATION_UNRESOLVED'
    assert store.get('project').analyses[-2] == retained


def test_reviewed_composition_route_refuses_another_owners_workspace(project):
    _, _, _, _, client = project
    store, workspace, attention, required, runs, _ = composition_scope(project, amounts=('120',), divisible=False)
    with client.session_transaction() as session:
        session.update(username='other-user', role='reviewer')
    before = store._path_for('project').read_bytes()
    response = client.post('/projects/project/attention', data=dict(action='role_composition',
        analysis_id=attention['id'], matching_id=[r['id'] for r in runs], required_role_id=[required],
        coverage_mode='reviewed_requirements', reason='Must be refused.'))
    assert response.status_code == 403
    assert store._path_for('project').read_bytes() == before


@pytest.mark.parametrize('partnership,unresolved,conflict', [('missing', True, False), ('conflict', False, True)])
def test_report_filters_keep_configuration_unknowns_and_conflicts_visible(project, partnership, unresolved, conflict):
    store, workspace, attention, required, runs, partners = composition_scope(project, addition=True, partnership=partnership)
    run = store.run_role_composition(workspace, 'reviewer', attention['id'], [r['id'] for r in runs],
        [required], 'Surface material coverage state.', reviewed_scope=True,
        compatibility_matching_ids=[r['id'] for r in partners])
    before = store._path_for('project').read_bytes()
    report = store.project_attention_report(workspace, 'reviewer', attention['id'])
    groups = [g for g in report['groups'] if g['semantic'].get('state') == run['governed_result']['state']]
    assert groups and all(g['unresolved'] == unresolved for g in groups)
    if conflict:
        assert all(g['conflict'] for g in groups)
    assert store._path_for('project').read_bytes() == before
