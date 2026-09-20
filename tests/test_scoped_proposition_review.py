"""Controlled local reviewer fixtures exercise the actual persistence gate.

These tests are not production source authentication or investor evidence.
"""
import copy
import hashlib

import pytest

from services.case_workspace import CaseWorkspaceError
from services.cross_modal_investigation import PROPOSITION_REVIEW_CHECKS
from tests.test_kernel_mapping import project
from tests.test_transaction_propositions import event_data, record


def prepared(project, *, evaluation_only=False, two_participants=False, transaction_class='EQUITY_JV'):
    _, store, workspace, _, _ = project
    raw = (b'LOCAL TEST FIXTURE ONLY. Controlled participant, TEST-01, Test jurisdiction; '
           b'Controlled opportunity Phase A, OP-A, AGREEMENT-A. Joint equity structure. '
           b'The independently reviewed applicability interval is 2024-01-01 to 2024-12-31.')
    if two_participants:
        raw += b' Second controlled participant, TEST-02, Test jurisdiction; second equity participant.'
    path = store.store_path/'controlled-source.txt'
    path.write_bytes(raw)
    source = store.add_source(workspace, 'Local test disclosure', str(path), 'document',
        file_hash=hashlib.sha256(raw).hexdigest(), actor='reviewer')
    evidence = store.register_evidence_item(workspace, source['id'], 'direct_source_evidence', raw.decode(), 'text')
    attention = store.record_go_attention(workspace, 'reviewer', 'Review the controlled source proposition',
        [evidence['id']], evaluation_only=evaluation_only)
    party = store.record_participant(workspace, 'Controlled participant', 'investor', 'reviewer')
    data = event_data(party)
    data['identity']['transaction_class'] = transaction_class
    if transaction_class != 'EQUITY_JV':
        data['identity']['joint_structure'] = 'NOT_JV'
    if two_participants:
        second = store.record_participant(workspace, 'Second controlled participant', 'investor', 'reviewer')
        data['identity']['participants'].append(dict(participant_id=second['id'], legal_name=second['name'],
            jurisdiction='Test jurisdiction', registration_id='TEST-02', role='Equity participant', identity_relation='EXACT_ENTITY'))
    claim = record(store, workspace, evidence, attention, data)
    case = store.create_case(workspace, 'Scoped verification test', 'Review the actual source interpretation', 'reviewer')
    adopted = store.accept_claim_as_finding(workspace, claim['id'], 'reviewer', case['id'])
    proposal = dict(claim_id=claim['id'], evidence_tier=3, valid_from='2024-01-01', valid_until='2024-12-31',
        attribution='human_reviewed', reason='Controlled reviewer assertion tied to this exact local fixture.',
        checks={key:dict(state='ESTABLISHED', reason='The reviewer checked this dimension against the retained test source.',
                        evidence_ids=[evidence['id']]) for key in PROPOSITION_REVIEW_CHECKS})
    return store, workspace, evidence, adopted['claim'], adopted['finding_id'], proposal, path


def test_review_and_disposition_never_substitute_for_apply(project):
    store, workspace, _, claim, finding, proposal, _ = prepared(project)
    original = copy.deepcopy((workspace.sources, workspace.evidence_items, workspace.claims))
    assert not store.admit_reviewed_proposition(workspace, claim['id'], query_date='2024-06-01')['admissible']
    review = store.record_reviewer_validation(workspace, finding, 'Correct', 'reviewer', proposition_review=proposal)
    assert review['proposition_review']['scope_fingerprint']['claim_sha256']
    store.record_disposition(workspace, finding, 'Confirmed', 'reviewer')
    assert 'EXPLICIT_APPLY_NOT_ESTABLISHED' in store.admit_reviewed_proposition(workspace, claim['id'], query_date='2024-06-01')['errors']
    applied = store.apply_findings(workspace, [finding], 'reviewer')
    result = store.admit_reviewed_proposition(store.get(workspace.project_id), claim['id'], query_date='2024-06-01')
    assert result['admissible'] and result['state'] == 'ESTABLISHED'
    assert result['provenance']['apply_ids'] == [applied['id']]
    assert (workspace.sources, workspace.evidence_items, workspace.claims) == original
    # No changes to raw-source/geometry admission follow from a Claim review.
    assert not store.admit_proposition(workspace, proposal['checks']['READING']['evidence_ids'][0])['admissible']


def test_expired_currentness_preserves_historical_review_without_current_confirmation(project):
    store, workspace, _, claim, finding, proposal, _ = prepared(project)
    store.record_reviewer_validation(workspace, finding, 'Correct', 'reviewer', proposition_review=proposal)
    store.record_disposition(workspace, finding, 'Confirmed', 'reviewer')
    store.apply_findings(workspace, [finding], 'reviewer')
    old = copy.deepcopy(workspace.claims)
    current = store.admit_reviewed_proposition(workspace, claim['id'], query_date='2026-09-20')
    historical = store.admit_reviewed_proposition(workspace, claim['id'], query_date='2026-09-20', historical=True)
    assert not current['admissible'] and current['review_history_intact']
    assert historical['admissible'] and historical['current_applicability'] == 'UNRESOLVED'
    assert workspace.claims == old


@pytest.mark.parametrize('dimension', PROPOSITION_REVIEW_CHECKS)
def test_one_unresolved_review_dimension_blocks_stronger_admission(project, dimension):
    store, workspace, _, claim, finding, proposal, _ = prepared(project)
    proposal['checks'][dimension]['state'] = 'UNRESOLVED'
    store.record_reviewer_validation(workspace, finding, 'Correct', 'reviewer', proposition_review=proposal)
    store.record_disposition(workspace, finding, 'Confirmed', 'reviewer')
    before = store._path_for(workspace.project_id).read_bytes()
    with pytest.raises(CaseWorkspaceError, match='Scoped proposition verification is incomplete'):
        store.apply_findings(workspace, [finding], 'reviewer')
    assert store._path_for(workspace.project_id).read_bytes() == before
    result = store.admit_reviewed_proposition(workspace, claim['id'], query_date='2024-06-01')
    assert not result['admissible'] and dimension+'_UNRESOLVED' in result['errors']


def test_generic_correct_review_cannot_bypass_typed_scope_verification(project):
    store, workspace, _, _, finding, _, _ = prepared(project)
    store.record_reviewer_validation(workspace, finding, 'Correct', 'reviewer')
    store.record_disposition(workspace, finding, 'Confirmed', 'reviewer')
    before = store._path_for(workspace.project_id).read_bytes()
    with pytest.raises(CaseWorkspaceError, match='SCOPED_HUMAN_REVIEW_NOT_ESTABLISHED'):
        store.apply_findings(workspace, [finding], 'reviewer')
    assert store._path_for(workspace.project_id).read_bytes() == before


def test_evaluation_proposition_cannot_enter_canonical_apply_ledger(project):
    store, workspace, _, claim, finding, proposal, _ = prepared(project, evaluation_only=True)
    store.record_reviewer_validation(workspace, finding, 'Correct', 'reviewer', proposition_review=proposal)
    store.record_disposition(workspace, finding, 'Confirmed', 'reviewer')
    before = store._path_for(workspace.project_id).read_bytes()
    with pytest.raises(CaseWorkspaceError, match='Evaluation propositions'):
        store.apply_findings(workspace, [finding], 'reviewer')
    assert store._path_for(workspace.project_id).read_bytes() == before
    assert not store.admit_reviewed_proposition(workspace, claim['id'], historical=True)['admissible']


def test_changed_bytes_or_missing_review_dimension_cannot_reuse_prior_verification(project):
    store, workspace, _, claim, finding, proposal, path = prepared(project)
    store.record_reviewer_validation(workspace, finding, 'Correct', 'reviewer', proposition_review=proposal)
    store.record_disposition(workspace, finding, 'Confirmed', 'reviewer')
    store.apply_findings(workspace, [finding], 'reviewer')
    changed = copy.deepcopy(workspace)
    changed.reviewer_validations[-1]['proposition_review']['checks'].pop('SOURCE_AUTHENTICITY')
    assert not store.admit_reviewed_proposition(changed, claim['id'], historical=True)['admissible']
    path.write_bytes(b'changed outside the immutable-source contract')
    result = store.admit_reviewed_proposition(workspace, claim['id'], historical=True)
    assert not result['admissible'] and 'IMMUTABLE_SOURCE_UNAVAILABLE' in result['errors']
    assert store.get(workspace.project_id).claims == workspace.claims


def test_private_or_unattributed_review_is_refused_before_persistence(project):
    store, workspace, _, _, finding, proposal, _ = prepared(project)
    before = store._path_for(workspace.project_id).read_bytes()
    with pytest.raises(CaseWorkspaceError, match='not visible'):
        store.record_reviewer_validation(workspace, finding, 'Correct', 'another-user', proposition_review=proposal)
    proposal['attribution'] = 'agent_assessment'
    with pytest.raises(CaseWorkspaceError, match='human review'):
        store.record_reviewer_validation(workspace, finding, 'Correct', 'reviewer', proposition_review=proposal)
    assert store._path_for(workspace.project_id).read_bytes() == before


def test_existing_finding_review_route_records_scoped_review_without_apply(project):
    _, _, _, _, client = project
    store, workspace, _, claim, finding, proposal, _ = prepared(project)
    form = dict(validation='Correct', proposition_claim_id=claim['id'],
        proposition_evidence_tier='3', proposition_valid_from=proposal['valid_from'],
        proposition_valid_until=proposal['valid_until'], proposition_reason=proposal['reason'],
        proposition_attribution='human_reviewed')
    for key, check in proposal['checks'].items():
        form.update({'review_'+key+'_state':check['state'], 'review_'+key+'_reason':check['reason'],
                     'review_'+key+'_evidence_id':check['evidence_ids']})
    response = client.post('/projects/project/workspace/findings/'+finding+'/validate', data=form)
    assert response.status_code == 302
    saved = store.get('project')
    assert saved.reviewer_validations[-1]['proposition_review']['claim_id'] == claim['id']
    assert saved.applies == [] and saved.dispositions == []
    page = client.get('/projects/project/workspace', query_string={'case':workspace.cases[-1]['id']})
    assert page.status_code == 200
    assert 'Review this exact sourced proposition' in page.get_data(as_text=True)
