"""Bounded hypothetical arithmetic never becomes canonical physical evidence."""
import copy
import pytest
from tests.test_kernel_mapping import project
from services.quantitative_investigation import probe_interval_constraints, search_interval_breakpoint


def constraints():
    return [dict(id='architecture', subject='opening-1', parameter='width', unit='mm',
                 lower='990', upper='1010', premise_ids=['a']),
            dict(id='structure', subject='opening-1', parameter='width', unit='mm',
                 lower='1000', upper='1020', premise_ids=['b'])]


def test_common_configuration_and_exact_inclusive_failure_threshold():
    rows = constraints()
    original = copy.deepcopy(rows)
    result = probe_interval_constraints(rows)
    assert result['state'] == 'CONSISTENT_WITH_TOLERANCE'
    assert result['common_interval'] == ['1000', '1010']
    probe = search_interval_breakpoint(result, '1005', 'increase')
    assert probe['failure_point'] == '1010' and probe['margin_to_failure'] == '5'
    assert probe['first_violated_constraints'] == ['architecture']
    assert probe['boundary_is_admissible']
    assert probe['origin'] == 'EVALUATION_INPUT' and not probe['canonical']
    assert probe['physical_failure_mode'] == 'UNRESOLVED'
    assert search_interval_breakpoint(result, '1010', 'increase')['margin_to_failure'] == '0'
    assert search_interval_breakpoint(result, '999', 'increase')['state'] == 'UNRESOLVED'
    assert search_interval_breakpoint(result, '1005', 'decrease')['first_violated_constraints'] == ['structure']
    assert rows == original


def test_no_common_configuration_prevents_breakpoint_search():
    rows = constraints()
    rows[1]['lower'] = '1011'
    result = probe_interval_constraints(rows)
    assert result['state'] == 'NO_COMMON_ADMISSIBLE_CONDITION'
    assert search_interval_breakpoint(result, '1005', 'increase')['state'] == 'UNRESOLVED'


@pytest.mark.parametrize('field,value,state', [('unit', 'in', 'INCOMPARABLE'),
    ('subject', 'opening-2', 'INCOMPARABLE'), ('lower', None, 'UNRESOLVED'),
    ('lower', True, 'UNRESOLVED'), ('upper', 'NaN', 'UNRESOLVED'),
    ('upper', 'Infinity', 'UNRESOLVED'), ('upper', '1e100000000', 'UNRESOLVED'),
    ('premise_ids', [], 'UNRESOLVED')])
def test_missing_or_incompatible_premises_are_never_completed(field, value, state):
    rows = constraints()
    rows[1][field] = value
    assert probe_interval_constraints(rows)['state'] == state


def test_real_route_persists_hypothesis_without_modifying_evidence_and_reload_is_read_only(project):
    app, store, workspace, evidence, client = project
    attention = store.record_go_attention(workspace, 'reviewer', 'Compare opening bounds', [evidence['id']])
    original = copy.deepcopy((workspace.sources, workspace.evidence_items))
    response = client.post('/projects/project/attention', data=dict(action='constraint_review',
        analysis_id=attention['id'], subject='opening', parameter='width', unit='mm',
        evidence_1=evidence['id'], evidence_2=evidence['id'], lower_1='990', upper_1='1010',
        lower_2='1000', upper_2='1020', baseline='1005', direction='increase',
        reason='Explicit hypothetical bounds; not a reading of the cited prose'))
    assert response.status_code == 303
    saved = store.get('project')
    result = saved.analyses[-1]['governed_result']
    assert result['state'] == 'EVALUATION_INPUT' and result['evaluation_only']
    assert result['admissions'][0]['authority'] == 'NOT_ESTABLISHED'
    assert (saved.sources, saved.evidence_items) == original
    before = store._path_for('project').read_bytes()
    page = client.get(response.location)
    assert page.status_code == 200 and b'BOUNDARY_FOUND' in page.data
    assert b'Actual project value: UNRESOLVED' in page.data
    assert store._path_for('project').read_bytes() == before
    from services.runtime_observation import read
    owners = {e['owner'] for e in read(app, response.headers['X-ARCHIOSK-Observation'])['events'] if e['phase'] == 'INVOKED'}
    assert 'services.quantitative_investigation.probe_interval_constraints' in owners
    assert 'services.quantitative_investigation.search_interval_breakpoint' in owners
    from services.case_workspace import CaseWorkspaceError
    with pytest.raises(CaseWorkspaceError):
        store.run_constraint_review(saved, 'reviewer', attention['id'], constraints(), '1005', 'increase', 'foreign references')
    assert store._path_for('project').read_bytes() == before
