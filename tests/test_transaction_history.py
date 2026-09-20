"""Transaction reduction against real retained Claims and review/Apply history."""
import copy

import pytest

from services.cross_modal_investigation import investigate_transaction_history
from tests.test_kernel_mapping import project
from tests.test_scoped_proposition_review import prepared
from tests.test_transaction_identity import admit
from tests.test_transaction_propositions import event_data, record


def history(project, *, two_participants=False, transaction_class='EQUITY_JV'):
    store, workspace, evidence, root, _, proposal, _ = prepared(project, two_participants=two_participants, transaction_class=transaction_class)
    admit(store, workspace, root, proposal)
    attention = store.record_go_attention(workspace, 'reviewer', 'Reconstruct retained transaction events', [evidence['id']])
    def append(dimension, *, tier=3, reviewed=True, facets=None, **changes):
        data = event_data(workspace.participants[-1], root['id'], dimension, **changes)
        data['identity'] = copy.deepcopy(root['event_proposition']['data']['identity'])
        data['facets'].update(facets or {})
        claim = record(store, workspace, evidence, attention, data)
        if reviewed:
            admit(store, workspace, claim, proposal, tier=tier)
        return claim
    def inspect(as_of='2024-06-01'):
        return investigate_transaction_history(store, store.get(workspace.project_id), root['id'], as_of=as_of)
    return store, workspace, evidence, root, append, inspect


def executed(append):
    signed = append('SIGNED')
    execution = append('EXECUTED', occurred_at='2024-02-01', facets={
        'legal_effectiveness':'ESTABLISHED', 'execution_conditions_complete':'ESTABLISHED'})
    return signed, execution


def test_signing_is_not_execution_or_close_and_reload_does_not_persist(project):
    store, workspace, _, _, append, inspect = history(project)
    append('SIGNED')
    before = store._path_for(workspace.project_id).read_bytes()
    result = inspect()
    assert result['maturity_state'] == 'SIGNED'
    assert result['events']['EXECUTED']['state'] == 'UNRESOLVED'
    assert result['events']['FINANCIALLY_CLOSED']['state'] == 'UNRESOLVED'
    assert result['lifecycle_status'] == 'SUSPENDED'
    assert store._path_for(workspace.project_id).read_bytes() == before


def test_missing_current_interval_does_not_erase_scoped_historical_signing(project):
    _, _, _, _, append, inspect = history(project)
    append('SIGNED', effective_until=None)
    result = inspect()
    assert result['events']['SIGNED']['state'] == 'ESTABLISHED'
    assert result['lifecycle_status'] == 'SUSPENDED'
    assert result['governed_state'] == 'UNRESOLVED'


def test_financial_close_discovered_first_backfills_without_rewriting_event_time(project):
    store, workspace, _, _, append, inspect = history(project)
    close = append('FINANCIALLY_CLOSED', tier=4, occurred_at='2024-03-01', facets={
        'financial_close':'ESTABLISHED', 'closing_conditions_complete':'ESTABLISHED'})
    old = copy.deepcopy(close)
    assert inspect()['events']['FINANCIALLY_CLOSED']['state'] == 'UNRESOLVED'
    executed(append)
    result = inspect()
    assert result['maturity_state'] == 'FINANCIALLY_CLOSED'
    assert [r['data']['event_dimension'] for r in result['history']] == ['SIGNED', 'EXECUTED', 'FINANCIALLY_CLOSED']
    retained = store.get_claim(store.get(workspace.project_id), close['id'])
    assert retained['event_proposition'] == old['event_proposition']
    assert retained['created_at'] == old['created_at']


@pytest.mark.parametrize('outcome,expected', [('FAILED','NOT_OCCURRED'), ('UNRESOLVED','UNRESOLVED'), ('WAIVED','ESTABLISHED'), ('SATISFIED','ESTABLISHED')])
def test_blocking_condition_outcomes_preserve_signing(project, outcome, expected):
    _, _, evidence, _, append, inspect = history(project)
    append('SIGNED')
    append('EXECUTED', facets={'legal_effectiveness':'ESTABLISHED', 'execution_conditions_complete':'ESTABLISHED'},
        conditions=[dict(key='regulatory', outcome=outcome, blocking_for='EXECUTED', evidence_ids=[evidence['id']])])
    result = inspect()
    assert result['events']['SIGNED']['state'] == 'ESTABLISHED'
    assert result['events']['EXECUTED']['state'] == expected
    if outcome == 'FAILED':
        assert result['events']['FINANCIALLY_CLOSED']['state'] == 'NOT_OCCURRED'
    assert result['lifecycle_status'] != 'TERMINATED'


def test_failed_financing_condition_does_not_erase_execution(project):
    _, _, evidence, _, append, inspect = history(project)
    executed(append)
    append('FINANCIALLY_CLOSED', tier=4, occurred_at='2024-03-01', facets={
        'financial_close':'ESTABLISHED', 'closing_conditions_complete':'ESTABLISHED'},
        conditions=[dict(key='funding', outcome='FAILED', blocking_for='FINANCIALLY_CLOSED', evidence_ids=[evidence['id']])])
    result = inspect()
    assert result['events']['EXECUTED']['state'] == 'ESTABLISHED'
    assert result['events']['FINANCIALLY_CLOSED']['state'] == 'NOT_OCCURRED'


def test_nonblocking_unknown_condition_does_not_degrade_execution(project):
    _, _, _, _, append, inspect = history(project)
    append('SIGNED')
    append('EXECUTED', facets={'legal_effectiveness':'ESTABLISHED', 'execution_conditions_complete':'ESTABLISHED'},
        conditions=[dict(key='optional', outcome='UNRESOLVED', blocking_for='NON_BLOCKING', evidence_ids=[])])
    assert inspect()['events']['EXECUTED']['state'] == 'ESTABLISHED'


def test_termination_discovered_before_signing_preserves_maturity(project):
    _, _, _, _, append, inspect = history(project)
    append('TERMINATION', occurred_at='2024-04-01')
    assert inspect()['lifecycle_status'] != 'TERMINATED'
    executed(append)
    result = inspect()
    assert result['maturity_state'] == 'EXECUTED'
    assert result['lifecycle_status'] == 'TERMINATED'
    append('CURRENT_CONFIRMATION', occurred_at='2024-05-01', facets={'express_current_confirmation':'ESTABLISHED'})
    assert inspect()['lifecycle_status'] == 'TERMINATED'


def test_partial_financing_change_does_not_supersede_equity_transaction(project):
    _, _, _, _, append, inspect = history(project)
    executed(append)
    append('SUPERSESSION', occurred_at='2024-03-01', component_scope='FINANCING', component_key='Tranche A')
    result = inspect()
    assert result['maturity_state'] == 'EXECUTED'
    assert result['lifecycle_status'] != 'SUPERSEDED'
    assert len(result['component_changes']) == 1


def test_newer_conflicting_event_never_silently_wins(project):
    _, _, _, _, append, inspect = history(project)
    append('SIGNED')
    append('SIGNED', occurred_at='2024-02-01', asserted_state='NOT_OCCURRED')
    result = inspect()
    assert result['events']['SIGNED']['state'] == 'CONFLICTING'
    assert result['governed_state'] == 'CONFLICTING'


def test_explicit_positive_correction_preserves_corrected_historical_claim(project):
    store, workspace, _, _, append, inspect = history(project)
    original = append('SIGNED')
    append('CORRECTION', occurred_at='2024-02-01', asserted_state='NOT_OCCURRED', replaces_claim_ids=[original['id']])
    result = inspect()
    assert result['events']['SIGNED']['state'] == 'NOT_OCCURRED'
    assert len(result['history']) == 2
    assert store.get_claim(store.get(workspace.project_id), original['id']) is not None


def test_unreviewed_high_tier_close_cannot_strengthen_maturity(project):
    _, _, _, _, append, inspect = history(project)
    executed(append)
    append('FINANCIALLY_CLOSED', tier=4, reviewed=False, facets={
        'financial_close':'ESTABLISHED', 'closing_conditions_complete':'ESTABLISHED'})
    result = inspect()
    assert result['maturity_state'] == 'EXECUTED'
    assert result['events']['FINANCIALLY_CLOSED']['state'] == 'UNRESOLVED'


@pytest.mark.parametrize('interruption', ['SUSPENSION','TERMINATION'])
def test_positive_same_transaction_reinstatement_requires_exact_interruption_link(project, interruption):
    _, _, _, _, append, inspect = history(project)
    executed(append)
    interrupted = append(interruption, occurred_at='2024-03-01')
    append('REINSTATEMENT', occurred_at='2024-04-01', continuity='CONTINUES',
        facets={'express_current_confirmation':'ESTABLISHED'})
    assert inspect()['lifecycle_status'] == ('TERMINATED' if interruption == 'TERMINATION' else 'SUSPENDED')
    append('REINSTATEMENT', occurred_at='2024-05-01', continuity='CONTINUES',
        related_claim_ids=[interrupted['id']], facets={'express_current_confirmation':'ESTABLISHED'})
    result = inspect()
    assert result['lifecycle_status'] == 'ACTIVE'
    assert result['transitions'][-1]['transition_class'] == 'REINSTATEMENT'
    assert result['transitions'][-1]['prior_evidence_refs'] == [interrupted['id']]


def test_component_reinstatement_does_not_revive_terminated_whole(project):
    _, _, _, _, append, inspect = history(project)
    executed(append)
    terminal = append('TERMINATION', occurred_at='2024-03-01')
    append('REINSTATEMENT', occurred_at='2024-04-01', continuity='CONTINUES',
        component_scope='FINANCING', component_key='Tranche A', related_claim_ids=[terminal['id']],
        facets={'express_current_confirmation':'ESTABLISHED'})
    assert inspect()['lifecycle_status'] == 'TERMINATED'


def test_later_discovery_of_older_lifecycle_event_does_not_reverse_termination(project):
    _, _, _, _, append, inspect = history(project)
    executed(append)
    append('TERMINATION', occurred_at='2024-04-01')
    append('CURRENT_CONFIRMATION', occurred_at='2024-03-01', facets={'express_current_confirmation':'ESTABLISHED'})
    result = inspect()
    assert result['lifecycle_status'] == 'TERMINATED'
    assert [r['effective_at'] for r in result['transitions']] == ['2024-03-01','2024-04-01']


def test_exact_authoritative_joint_transaction_can_confirm_without_claiming_financial_close(project):
    _, _, _, _, append, inspect = history(project, two_participants=True)
    executed(append)
    append('CURRENT_CONFIRMATION', occurred_at='2024-03-01', facets={'express_current_confirmation':'ESTABLISHED'})
    result = inspect()
    assert result['governed_state'] == 'ACTUAL_JV_CONFIRMED'
    assert result['events']['FINANCIALLY_CLOSED']['state'] == 'UNRESOLVED'
    assert inspect('2026-09-20')['governed_state'] == 'UNRESOLVED'
    assert inspect('2026-09-20')['maturity_state'] == 'EXECUTED'


def test_explicit_later_waiver_closes_named_condition_without_erasing_prior_failure(project):
    _, _, evidence, _, append, inspect = history(project)
    signed = append('SIGNED', conditions=[dict(key='regulatory', outcome='FAILED',
        blocking_for='EXECUTED', evidence_ids=[evidence['id']])])
    assert inspect()['events']['EXECUTED']['state'] == 'NOT_OCCURRED'
    waiver = append('CONDITION_UPDATE', occurred_at='2024-02-01', replaces_claim_ids=[signed['id']],
        conditions=[dict(key='regulatory', outcome='WAIVED', blocking_for='EXECUTED', evidence_ids=[evidence['id']])])
    append('EXECUTED', occurred_at='2024-03-01', facets={
        'legal_effectiveness':'ESTABLISHED', 'execution_conditions_complete':'ESTABLISHED'})
    result = inspect()
    assert result['events']['EXECUTED']['state'] == 'ESTABLISHED'
    assert waiver['id'] in result['events']['EXECUTED']['condition_evidence_refs']
    assert len(result['history']) == 3
    assert result['history'][0]['data']['conditions'][0]['outcome'] == 'FAILED'


def test_unlinked_positive_condition_does_not_override_failed_condition(project):
    _, _, evidence, _, append, inspect = history(project)
    append('SIGNED', conditions=[dict(key='regulatory', outcome='FAILED', blocking_for='EXECUTED', evidence_ids=[evidence['id']])])
    append('CONDITION_UPDATE', occurred_at='2024-02-01',
        conditions=[dict(key='regulatory', outcome='SATISFIED', blocking_for='EXECUTED', evidence_ids=[evidence['id']])])
    append('EXECUTED', occurred_at='2024-03-01', facets={
        'legal_effectiveness':'ESTABLISHED', 'execution_conditions_complete':'ESTABLISHED'})
    assert inspect()['events']['EXECUTED']['state'] == 'CONFLICTING'


def test_positive_lifecycle_conflict_cannot_be_hidden_by_current_confirmation(project):
    _, _, _, _, append, inspect = history(project, two_participants=True)
    executed(append)
    append('CURRENT_CONFIRMATION', occurred_at='2024-03-01', facets={'express_current_confirmation':'ESTABLISHED'})
    append('TERMINATION', occurred_at='2024-04-01', asserted_state='CONFLICTING')
    result = inspect()
    assert result['lifecycle_status'] == 'CONFLICTING'
    assert result['governed_state'] == 'CONFLICTING'
    assert result['maturity_state'] == 'EXECUTED'


def test_execution_after_explicit_waiver_preserves_failed_earlier_attempt(project):
    _, _, evidence, _, append, inspect = history(project)
    append('SIGNED')
    failure = append('EXECUTED', occurred_at='2024-02-01',
        facets={'legal_effectiveness':'ESTABLISHED','execution_conditions_complete':'ESTABLISHED'},
        conditions=[dict(key='regulatory', outcome='FAILED', blocking_for='EXECUTED', evidence_ids=[evidence['id']])])
    assert inspect()['events']['EXECUTED']['state'] == 'NOT_OCCURRED'
    append('CONDITION_UPDATE', occurred_at='2024-03-01', replaces_claim_ids=[failure['id']],
        conditions=[dict(key='regulatory', outcome='WAIVED', blocking_for='EXECUTED', evidence_ids=[evidence['id']])])
    append('EXECUTED', occurred_at='2024-04-01',
        facets={'legal_effectiveness':'ESTABLISHED','execution_conditions_complete':'ESTABLISHED'})
    result = inspect()
    assert result['events']['EXECUTED']['state'] == 'ESTABLISHED'
    assert result['events']['EXECUTED']['historical_nonoccurrence_refs'] == [failure['id']]


def test_history_projection_is_reconstructable_and_not_an_alias_of_evidence(project):
    store, workspace, _, root, append, inspect = history(project)
    executed(append)
    first, second = inspect(), inspect()
    assert first == second
    first['identity']['project']['name'] = 'Presentation-only change'
    first['history'][0]['data']['occurred_at'] = '1900-01-01'
    assert inspect() == second
    assert store.get_claim(workspace, root['id'])['event_proposition']['data']['identity']['project']['name'] != 'Presentation-only change'


def test_silence_or_new_activity_does_not_resume_explicit_suspension(project):
    _, _, _, _, append, inspect = history(project)
    executed(append)
    append('SUSPENSION', occurred_at='2024-03-01')
    append('CURRENT_CONFIRMATION', occurred_at='2024-04-01', facets={'express_current_confirmation':'ESTABLISHED'})
    result = inspect()
    assert result['lifecycle_status'] == 'SUSPENDED'
    assert any(r.get('reason') == 'POSITIVE_REINSTATEMENT_OR_RESOLUTION_REQUIRED' for r in result['unresolved'])
