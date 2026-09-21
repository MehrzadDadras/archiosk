"""Controlled test reviews exercise the real Claim / Finding / Apply path."""
import copy

import pytest

from tests.test_kernel_mapping import project
from tests.test_scoped_proposition_review import prepared
from tests.test_transaction_identity import admit
from tests.test_normalized_comparison import premise


def matching_scope(project, *, candidate_value='120', candidate_reviewed=True, inventory_reviewed=True,
                   obligation='MANDATORY', policy_operator='AT_LEAST', candidate_temporal='CURRENT_DISCLOSED_MANDATE', omitted_requirement=False,
                   divisible=False):
    store, workspace, evidence, _, _, proposal, _ = prepared(project)
    attention = store.record_go_attention(workspace, 'reviewer', 'Test reviewed requirement scope', [evidence['id']])
    opportunity = store.record_participant(workspace, 'Test opportunity', 'opportunity', 'reviewer')
    candidate = store.record_participant(workspace, 'Test candidate', 'investor', 'reviewer')
    subject = 'participant:' + opportunity['id']

    def append(property_key, value, *, kind='NUMBER', vocabulary='', owner=subject,
               temporal='DATED_REQUIREMENT', reviewed=True, qualifiers=None):
        normalization = premise(value, subject_key=owner, property_key=property_key, scope_key='controlled-scope',
            kind=kind, unit='USD' if kind == 'NUMBER' else '', vocabulary=vocabulary, premise_ids=[evidence['id']],
            qualifiers=qualifiers or [])
        claim = store.record_subject_proposition(workspace, 'reviewer', attention['id'], normalization,
            'PROJECT_DOCUMENT', temporal, evidence['content'], 'Explicit local test interpretation only.',
            as_of='2024-01-01', valid_until='2024-12-31', attribution='agent_assessment')
        if reviewed:
            admit(store, workspace, claim, proposal)
        return claim

    requirement = append('capital', '100')
    candidate_claim = append('capital', candidate_value, owner='participant:'+candidate['id'],
        temporal=candidate_temporal, reviewed=candidate_reviewed)
    policy = append('requirement_policy', [obligation, policy_operator, 'CURRENT_DISCLOSED_MANDATE'] + (['DIVISIBLE'] if divisible else []),
        kind='TOKEN_SET', vocabulary='requirement:'+requirement['id'])
    inventory_ids = [requirement['id']]
    if omitted_requirement:
        omitted = append('geography', ['REGION_A'], kind='TOKEN_SET', vocabulary='geography')
        append('requirement_policy', ['MANDATORY', 'CONTAINS_ALL', 'CURRENT_DISCLOSED_MANDATE'], kind='TOKEN_SET',
            vocabulary='requirement:'+omitted['id'])
        inventory_ids.append(omitted['id'])
    inventory = append('complete_requirement_inventory', inventory_ids, kind='TOKEN_SET',
        vocabulary='requirement_claims', reviewed=inventory_reviewed)
    criteria = [dict(required_claim_id=requirement['id'], candidate_claim_id=candidate_claim['id'],
        mandatory=True, operator='AT_LEAST', candidate_temporal_class='CURRENT_DISCLOSED_MANDATE')]

    def run(rows=None, inventory_id=inventory['id']):
        return store.run_requirement_matching(workspace, 'reviewer', attention['id'], 'participant:'+candidate['id'],
            rows or criteria, 'investment', 'Controlled factual review.', query_date='2024-06-01',
            inventory_claim_id=inventory_id)['governed_result']
    return store, workspace, append, run, criteria, inventory, attention


@pytest.mark.parametrize('changes,expected', [({},'FIT'), ({'candidate_value':'80'},'NON_FIT'),
    ({'candidate_reviewed':False},'UNRESOLVED'), ({'inventory_reviewed':False},'UNRESOLVED'),
    ({'candidate_temporal':'RECENT_COMMITMENT'},'UNRESOLVED')])
def test_factual_fit_requires_actual_review_and_complete_governing_scope(project, changes, expected):
    store, workspace, _, run, _, _, _ = matching_scope(project, **changes)
    before = copy.deepcopy((workspace.sources, workspace.evidence_items, workspace.claims))
    result = run()
    assert result['state'] == expected
    assert result['canonical'] is False
    assert (workspace.sources, workspace.evidence_items, workspace.claims) == before
    assert store.get('project').analyses[-1]['governed_result'] == result


def test_form_operator_and_optional_checkbox_cannot_override_reviewed_mandatory_policy(project):
    _, _, _, run, criteria, _, _ = matching_scope(project, candidate_value='80')
    rows = copy.deepcopy(criteria)
    rows[0].update(mandatory=False, operator='AT_MOST')
    result = run(rows)
    assert result['model_label'] == 'FIT'
    assert result['state'] == 'NON_FIT'
    assert result['reviewed_scope']['model']['mandatory_failures']


def test_scope_omission_cannot_turn_unknown_mandatory_requirement_into_fit(project):
    _, _, append, run, criteria, _, _ = matching_scope(project)
    omitted = append('geography', ['REGION_A'], kind='TOKEN_SET', vocabulary='geography')
    inventory = append('complete_requirement_inventory', [criteria[0]['required_claim_id'], omitted['id']],
        kind='TOKEN_SET', vocabulary='requirement_claims')
    result = run(inventory_id=inventory['id'])
    # Competing positively reviewed complete inventories cannot be chosen away.
    assert result['state'] == 'UNRESOLVED'
    assert any('CONFLICTING_EVIDENCE' in reason for reason in result['reviewed_scope']['reasons'])


def test_ambiguous_governing_policy_is_not_resolved_by_latest_timestamp(project):
    _, _, append, run, criteria, _, _ = matching_scope(project)
    append('requirement_policy', ['OPTIONAL','AT_MOST','CURRENT_DISCLOSED_MANDATE'], kind='TOKEN_SET',
        vocabulary='requirement:'+criteria[0]['required_claim_id'])
    result = run()
    assert result['state'] == 'UNRESOLVED'
    assert 'ambiguous' in result['reviewed_scope']['model']['criteria'][0]['comparison']['reason']


def test_reviewed_inventory_surfaces_unselected_mandatory_dependency(project):
    _, _, _, run, _, _, _ = matching_scope(project, omitted_requirement=True)
    result = run()
    assert result['model_label'] == 'FIT'
    assert result['state'] == 'UNRESOLVED'
    assert result['reviewed_scope']['scope_crossing_dependencies'][0]['kind'] == 'SCOPE_CROSSING_DEPENDENCY'
    assert len(result['reviewed_scope']['model']['criteria']) == 2


def test_new_evidence_marks_factual_fit_retained_not_current_without_rerunning(project):
    store, workspace, append, run, _, _, attention = matching_scope(project)
    assert run()['state'] == 'FIT'
    append('additional_scope', ['REVIEW'], kind='TOKEN_SET', vocabulary='review')
    before = store._path_for('project').read_bytes()
    entries = store.inspect_requirement_matches(workspace, 'reviewer', attention['id'])
    assert entries[-1]['consumption_state'] == 'REVIEW_REQUIRED'
    assert entries[-1]['run']['governed_result']['state'] == 'FIT'
    assert store._path_for('project').read_bytes() == before


def test_discovery_tier_cannot_establish_factual_fit_despite_review_labels(project):
    store, workspace, _, run, criteria, _, _ = matching_scope(project, candidate_reviewed=False)
    candidate = store.get_claim(workspace, criteria[0]['candidate_claim_id'])
    review = copy.deepcopy(workspace.reviewer_validations[0]['proposition_review'])
    for field in ('scope_fingerprint', 'qualification', 'reviewer'):
        review.pop(field, None)
    review['evidence_tier'] = 0
    admit(store, workspace, candidate, review, tier=0)
    assert run()['state'] == 'UNRESOLVED'
