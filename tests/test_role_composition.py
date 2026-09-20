import copy
from unittest.mock import patch
import pytest
from tests.test_kernel_mapping import project
from services.case_workspace import CaseWorkspaceError


def composition_inputs(project, *, mandatory=False):
    _, store, workspace, evidence, _ = project
    attention = store.record_go_attention(workspace, 'reviewer', 'Evaluate role coverage', [evidence['id']])
    parties = [store.record_review_subject(workspace, 'reviewer', attention['id'], name, role)
               for name, role in [('Opportunity','opportunity'), ('Equity candidate','investor'), ('Debt candidate','lender')]]
    claims = []
    for index, value in [(0,'EQUITY'), (0,'DEBT'), (1,'EQUITY'), (2,'DEBT')]:
        norm = dict(subject_key='participant:'+parties[index]['id'], property_key='role', scope_key='opportunity-1',
            kind='TOKEN_SET', value=[value], unit='', vocabulary='roles', qualifiers=[], view_basis='VIEW_INVARIANT',
            view_id=None, basis='Explicit sourced role interpretation.', premise_ids=[evidence['id']])
        claims.append(store.record_subject_proposition(workspace, 'reviewer', attention['id'], norm,
            'PROJECT_DOCUMENT', 'DATED_REQUIREMENT' if index == 0 else 'CURRENT_DISCLOSED_CAPABILITY',
            evidence['content'], 'Role interpretation only.', attribution='agent_assessment'))
    runs = []
    for index in (2, 3):
        rows = [dict(required_claim_id=claims[i]['id'], candidate_claim_id=claims[index]['id'],
            mandatory=mandatory, operator='CONTAINS_ALL', candidate_temporal_class='CURRENT_DISCLOSED_CAPABILITY') for i in (0, 1)]
        runs.append(store.run_requirement_matching(workspace, 'reviewer', attention['id'],
            claims[index]['structured_proposition']['normalization']['subject_key'], rows,
            'investment', 'Compare each role explicitly.', require_currentness=False))
    return attention, parties, claims, runs


def test_real_route_composes_two_entities_without_ranking_or_mutating_evidence(project):
    _, store, _, _, client = project
    attention, parties, claims, runs = composition_inputs(project)
    workspace = store.get('project')
    original = copy.deepcopy((workspace.sources, workspace.evidence_items, workspace.claims, workspace.analyses))
    response = client.post('/projects/project/attention', data=dict(action='role_composition', analysis_id=attention['id'],
        matching_id=[run['id'] for run in runs], required_role_id=[claim['id'] for claim in claims[:2]], reason='Cover equity and debt roles.'))
    assert response.status_code == 303
    saved = store.get('project')
    result = saved.analyses[-1]['governed_result']
    assert result['model']['minimum_count'] == 2
    assert result['state'] == 'UNRESOLVED' and not result['canonical']
    assert result['model']['configurations'] == [sorted('participant:'+p['id'] for p in parties[1:])]
    assert (saved.sources, saved.evidence_items, saved.claims, saved.analyses[:-1]) == original
    persisted = store._path_for('project').read_bytes()
    with patch('services.cross_modal_investigation.cover_requirements', side_effect=AssertionError('Reload cannot compose')):
        page = client.get(response.location)
    assert page.status_code == 200 and b'Conditional role coverage MATCH' in page.data
    assert store._path_for('project').read_bytes() == persisted


def test_mandatory_candidate_failure_cannot_be_repaired_by_other_partners(project):
    _, store, _, _, _ = project
    attention, _, claims, runs = composition_inputs(project, mandatory=True)
    result = store.run_role_composition(store.get('project'), 'reviewer', attention['id'],
        [run['id'] for run in runs], [claim['id'] for claim in claims[:2]], 'Check mandatory exclusions.')['governed_result']
    assert result['model']['state'] == 'PARTIAL' and not result['model']['configurations']
    assert all(candidate['excluded_reasons'] for candidate in result['candidates'])


def test_unresolved_mandatory_constraint_excludes_otherwise_useful_candidate(project):
    _, store, _, _, _ = project
    attention, _, claims, _ = composition_inputs(project)
    workspace = store.get('project')
    criteria = [dict(required_claim_id=claims[i]['id'], candidate_claim_id=None if i == 0 else claims[3]['id'],
        mandatory=i == 0, operator='CONTAINS_ALL', candidate_temporal_class='CURRENT_DISCLOSED_CAPABILITY') for i in (0,1)]
    run = store.run_requirement_matching(workspace, 'reviewer', attention['id'],
        claims[3]['structured_proposition']['normalization']['subject_key'], criteria, 'investment',
        'Missing mandatory premise.', require_currentness=False)
    result = store.run_role_composition(workspace, 'reviewer', attention['id'], [run['id']],
        [claim['id'] for claim in claims[:2]], 'Check unresolved mandatory constraint.')['governed_result']
    assert not result['candidates'][0]['covered_claim_ids']
    assert 'unresolved' in ' '.join(result['candidates'][0]['excluded_reasons'])


@pytest.mark.parametrize('change', ['foreign_run','duplicate_run','foreign_role','non_role'])
def test_invalid_composition_does_not_create_analysis(project, change):
    _, store, _, _, _ = project
    attention, _, claims, runs = composition_inputs(project)
    workspace = store.get('project')
    identifiers = [run['id'] for run in runs]
    requirements = [claim['id'] for claim in claims[:2]]
    if change == 'foreign_run': identifiers[0] = 'foreign'
    if change == 'duplicate_run': identifiers[1] = identifiers[0]
    if change == 'foreign_role': requirements[0] = 'foreign'
    if change == 'non_role': workspace.claims[0]['structured_proposition']['normalization']['property_key'] = 'capital'
    count = len(workspace.analyses)
    with pytest.raises(CaseWorkspaceError):
        store.run_role_composition(workspace, 'reviewer', attention['id'], identifiers, requirements, 'Compare roles.')
    assert len(workspace.analyses) == count


def test_rejected_premise_flags_historical_composition_and_excludes_candidate_on_rerun(project):
    _, store, _, _, _ = project
    attention, _, claims, runs = composition_inputs(project)
    workspace = store.get('project')
    args = ('reviewer', attention['id'], [run['id'] for run in runs], [claim['id'] for claim in claims[:2]], 'Compose roles.')
    store.run_role_composition(workspace, *args)
    store.review_subject_proposition(workspace, 'reviewer', attention['id'], claims[2]['id'], 'reject',
        'The role interpretation is not supported.', attribution='human_reviewed')
    assert store.inspect_role_compositions(workspace, 'reviewer', attention['id'])[0]['consumption_state'] == 'REVIEW_REQUIRED'
    result = store.run_role_composition(workspace, *args)['governed_result']
    assert result['model']['missing'] == [claims[0]['id']]


@pytest.mark.parametrize('use_composition', [False, True])
def test_capital_brief_renders_retained_results_without_reanalysis_or_authority(project, use_composition):
    _, store, _, _, client = project
    attention, _, claims, runs = composition_inputs(project)
    workspace = store.get('project')
    run = store.run_role_composition(workspace, 'reviewer', attention['id'], [r['id'] for r in runs],
        [claim['id'] for claim in claims[:2]], 'Compose coverage.') if use_composition else runs[0]
    before = copy.deepcopy((workspace.sources, workspace.evidence_items, workspace.claims, workspace.analyses))
    with patch('services.cross_modal_investigation.match_normalized_criteria', side_effect=AssertionError('No reanalysis')):
        response = client.post('/projects/project/attention', data=dict(action='professional_presentation', review_id=run['id']))
    assert response.status_code == 303
    saved = store.get('project')
    assert (saved.sources, saved.evidence_items, saved.claims, saved.analyses) == before
    product = saved.work_products[-1]
    assert product['artifact_type'] == 'capital_alignment_brief' and product['state'] == 'draft'
    from services.work_product_export import export_work_product
    import docx
    buffer, _ = export_work_product(product, 'docx')
    document = docx.Document(buffer)
    text = '\n'.join(p.text for p in document.paragraphs)
    assert 'UNRESOLVED' in text and 'NOT_APPROVED_BY_COMPUTATION' in text
    assert run['id'] in text and 'No external contact' in text
    page = client.get(response.location)
    assert page.status_code == 200 and b'Capital Alignment Brief' in page.data


def test_brief_surfaces_changed_premises_without_rewriting_original_match(project):
    _, store, _, _, _ = project
    attention, _, claims, runs = composition_inputs(project)
    workspace = store.get('project')
    original = copy.deepcopy(runs[0])
    store.review_subject_proposition(workspace, 'reviewer', attention['id'], claims[2]['id'], 'reject',
        'Unsupported role interpretation.', attribution='human_reviewed')
    product = store.render_professional_review(workspace, 'reviewer', runs[0]['id'])
    sections = {section['section_type']: section['content'] for section in product['sections']}
    assert sections['objective_and_context']['consumption_state'] == 'REVIEW_REQUIRED'
    assert next(run for run in workspace.analyses if run['id'] == original['id']) == original


def test_unavailable_citation_refuses_brief_before_creating_product(project):
    _, store, _, _, _ = project
    _, _, _, runs = composition_inputs(project)
    workspace = store.get('project')
    workspace.evidence_items.clear()
    with pytest.raises(CaseWorkspaceError):
        store.render_professional_review(workspace, 'reviewer', runs[0]['id'])
    assert not workspace.work_products
