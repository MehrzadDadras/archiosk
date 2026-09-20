"""Explicit successor/facility links never collapse unrelated transactions."""
import copy

import pytest

from tests.test_kernel_mapping import project
from tests.test_transaction_history import history, executed
from tests.test_transaction_identity import admit
from tests.test_transaction_propositions import event_data, record


def successor(store, workspace, evidence, root, *, reviewed=True, reference='AGREEMENT-B', change=None):
    attention = store.record_go_attention(workspace, 'reviewer', 'Inspect explicit successor source interpretation', [evidence['id']])
    data = event_data(workspace.participants[-1])
    data['identity'] = copy.deepcopy(root['event_proposition']['data']['identity'])
    data['identity']['transaction_reference'] = reference
    if change:
        change(data['identity'])
    claim = record(store, workspace, evidence, attention, data)
    if reviewed:
        review = copy.deepcopy(workspace.reviewer_validations[0]['proposition_review'])
        proposal = {k:review[k] for k in ('claim_id','checks','evidence_tier','valid_from','valid_until','reason','attribution')}
        admit(store, workspace, claim, proposal)
    return claim


def test_express_full_supersession_retains_predecessor_and_maturity(project):
    store, workspace, evidence, root, append, inspect = history(project)
    executed(append)
    new = successor(store, workspace, evidence, root)
    append('SUPERSESSION', occurred_at='2024-04-01', related_claim_ids=[new['id']])
    result = inspect()
    assert result['lifecycle_status'] == 'SUPERSEDED'
    assert result['maturity_state'] == 'EXECUTED'
    assert store.get_claim(store.get(workspace.project_id), root['id'])


def test_newer_related_agreement_is_not_express_supersession(project):
    store, workspace, evidence, root, append, inspect = history(project)
    executed(append)
    successor(store, workspace, evidence, root)
    assert inspect()['lifecycle_status'] != 'SUPERSEDED'


@pytest.mark.parametrize('relation,component,expected', [
    ('REFINANCES','FULL_TRANSACTION','SUPERSEDED'),
    ('REPLACES_FACILITY','FULL_TRANSACTION','SUPERSEDED'),
    ('PARTIALLY_REFINANCES','FINANCING','SUSPENDED'),
    ('ADDS_TRANCHE','FINANCING','SUSPENDED'),
])
def test_refinancing_is_separate_scoped_link_preserving_predecessor_close(project, relation, component, expected):
    store, workspace, evidence, root, append, inspect = history(project, transaction_class='TERM_LOAN')
    executed(append)
    append('FINANCIALLY_CLOSED', tier=4, occurred_at='2024-03-01', facets={
        'financial_close':'ESTABLISHED','closing_conditions_complete':'ESTABLISHED'})
    new = successor(store, workspace, evidence, root)
    append('REFINANCING', occurred_at='2024-04-01', related_claim_ids=[new['id']], relationship_type=relation,
        component_scope=component, component_key='Tranche A' if component != 'FULL_TRANSACTION' else '')
    result = inspect()
    assert result['lifecycle_status'] == expected
    assert result['maturity_state'] == 'FINANCIALLY_CLOSED'
    assert result['financing_relationships'][0]['state'] == 'ESTABLISHED'
    assert result['financing_relationships'][0]['successor_claim_ids'] == [new['id']]
    assert result['governed_state'] != 'ACTUAL_JV_CONFIRMED'


def test_same_lender_parallel_facility_is_not_automatically_refinancing(project):
    store, workspace, evidence, root, append, inspect = history(project, transaction_class='TERM_LOAN')
    executed(append)
    new = successor(store, workspace, evidence, root)
    append('REFINANCING', occurred_at='2024-04-01', related_claim_ids=[new['id']])
    result = inspect()
    assert result['lifecycle_status'] != 'SUPERSEDED'
    assert result['financing_relationships'][0]['state'] == 'UNRESOLVED'


def test_unreviewed_successor_identity_cannot_supersede_existing_transaction(project):
    store, workspace, evidence, root, append, inspect = history(project)
    executed(append)
    new = successor(store, workspace, evidence, root, reviewed=False)
    append('SUPERSESSION', occurred_at='2024-04-01', related_claim_ids=[new['id']])
    assert inspect()['lifecycle_status'] != 'SUPERSEDED'


def test_debt_refinancing_does_not_replace_equity_jv(project):
    store, workspace, evidence, root, append, inspect = history(project)
    executed(append)
    new = successor(store, workspace, evidence, root)
    append('REFINANCING', occurred_at='2024-04-01', related_claim_ids=[new['id']], relationship_type='REFINANCES')
    result = inspect()
    assert result['lifecycle_status'] != 'SUPERSEDED'
    assert result['financing_relationships'][0]['state'] == 'UNRESOLVED'


def test_participant_substitution_preserves_continuing_transaction_and_original_parties(project):
    store, workspace, evidence, root, append, inspect = history(project)
    executed(append)
    replacement = store.record_participant(workspace, 'Controlled replacement participant', 'investor', 'reviewer')
    def replace(identity):
        identity['participants'][0].update(participant_id=replacement['id'], legal_name=replacement['name'], registration_id='TEST-03')
    amended = successor(store, workspace, evidence, root, reference='AGREEMENT-A', change=replace)
    append('PARTICIPANT_SUBSTITUTION', occurred_at='2024-04-01', component_scope='PARTICIPANTS', component_key='Equity participant',
        continuity='CONTINUES', related_claim_ids=[amended['id']], replaces_claim_ids=[root['id']])
    result = inspect()
    assert result['current_configuration']['state'] == 'ESTABLISHED'
    assert result['current_configuration']['identity']['participants'][0]['participant_id'] == replacement['id']
    assert result['identity']['participants'][0]['participant_id'] != replacement['id']
    assert result['maturity_state'] == 'EXECUTED'
    assert result['lifecycle_status'] not in ('SUPERSEDED','TERMINATED')


def test_ownership_amendment_changes_only_reviewed_scope(project):
    store, workspace, evidence, root, append, inspect = history(project)
    executed(append)
    amended = successor(store, workspace, evidence, root, reference='AGREEMENT-A',
        change=lambda identity:identity.update(economic_scope='Explicit amended ownership scope'))
    append('STRUCTURE_AMENDMENT', occurred_at='2024-04-01', component_scope='OWNERSHIP', component_key='Equity allocation',
        continuity='CONTINUES', related_claim_ids=[amended['id']], replaces_claim_ids=[root['id']])
    result = inspect()
    assert result['current_configuration']['identity']['economic_scope'] == 'Explicit amended ownership scope'
    assert result['current_configuration']['identity']['participants'] == result['identity']['participants']
    assert result['configuration_history'][0]['state'] == 'ESTABLISHED'
    assert result['lifecycle_status'] != 'TERMINATED'


def test_new_participant_activity_without_continuity_does_not_replace_identity(project):
    store, workspace, evidence, root, append, inspect = history(project)
    executed(append)
    amended = successor(store, workspace, evidence, root, reference='AGREEMENT-A')
    append('PARTICIPANT_SUBSTITUTION', occurred_at='2024-04-01', component_scope='PARTICIPANTS', component_key='Equity participant',
        related_claim_ids=[amended['id']], replaces_claim_ids=[root['id']])
    result = inspect()
    assert result['current_configuration']['state'] == 'UNRESOLVED'
    assert result['current_configuration']['identity_claim_id'] == root['id']


def test_refinance_discovered_before_original_close_preserves_backfilled_maturity(project):
    store, workspace, evidence, root, append, inspect = history(project, transaction_class='TERM_LOAN')
    new = successor(store, workspace, evidence, root)
    append('REFINANCING', occurred_at='2024-04-01', related_claim_ids=[new['id']], relationship_type='REFINANCES')
    assert inspect()['maturity_state'] is None
    executed(append)
    append('FINANCIALLY_CLOSED', tier=4, occurred_at='2024-03-01', facets={
        'financial_close':'ESTABLISHED','closing_conditions_complete':'ESTABLISHED'})
    result = inspect()
    assert result['maturity_state'] == 'FINANCIALLY_CLOSED'
    assert result['lifecycle_status'] == 'SUPERSEDED'


def test_explicit_predecessor_restoration_after_supersession_preserves_both_identities(project):
    store, workspace, evidence, root, append, inspect = history(project)
    executed(append)
    new = successor(store, workspace, evidence, root)
    supersession = append('SUPERSESSION', occurred_at='2024-03-01', related_claim_ids=[new['id']])
    append('REINSTATEMENT', occurred_at='2024-04-01', related_claim_ids=[supersession['id']],
        continuity='CONTINUES', facets={'express_current_confirmation':'ESTABLISHED'})
    result = inspect()
    assert result['lifecycle_status'] == 'ACTIVE'
    assert [t['after_state'] for t in result['transitions']] == ['SUPERSEDED','ACTIVE']
    saved = store.get(workspace.project_id)
    assert store.get_claim(saved, root['id']) and store.get_claim(saved, new['id'])
