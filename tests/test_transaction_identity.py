"""Identity closure uses persisted Claims, scoped human review and Apply."""
import copy

import pytest

from services.cross_modal_investigation import resolve_transaction_identity
from tests.test_kernel_mapping import project
from tests.test_scoped_proposition_review import prepared
from tests.test_transaction_propositions import event_data, record


def admit(store, workspace, claim, proposal, *, tier=3):
    proposal = copy.deepcopy(proposal)
    if not claim.get('finding_id'):
        case = workspace.cases[-1]
        adopted = store.accept_claim_as_finding(workspace, claim['id'], 'reviewer', case['id'])
        finding = adopted['finding_id']
    else:
        finding = claim['finding_id']
    proposal.update(claim_id=claim['id'], evidence_tier=tier)
    store.record_reviewer_validation(workspace, finding, 'Correct', 'reviewer', proposition_review=proposal)
    store.record_disposition(workspace, finding, 'Confirmed', 'reviewer')
    store.apply_findings(workspace, [finding], 'reviewer')


def pair(project, change=None, reviewed=True):
    store, workspace, evidence, root, _, proposal, _ = prepared(project)
    admit(store, workspace, root, proposal)
    attention = store.record_go_attention(workspace, 'reviewer', 'Inspect exact event identity', [evidence['id']])
    party = workspace.participants[-1]
    data = event_data(party, root['id'], 'SIGNED')
    if change:
        change(data)
    event = record(store, workspace, evidence, attention, data)
    if reviewed:
        admit(store, workspace, event, proposal)
    return store, workspace, root, event


def test_exact_reviewed_scopes_close_without_mutating_source_or_history(project):
    store, workspace, root, event = pair(project)
    before = store._path_for(workspace.project_id).read_bytes()
    result = resolve_transaction_identity(store, workspace, root['id'], event['id'], as_of='2024-06-01')
    assert result['state'] == 'EXACT_TRANSACTION'
    assert result['temporal_scope_match'] == 'ESTABLISHED'
    assert len(result['admissions']) == 2
    assert store._path_for(workspace.project_id).read_bytes() == before
    old = resolve_transaction_identity(store, workspace, root['id'], event['id'], as_of='2026-09-20')
    assert old['state'] == 'EXACT_TRANSACTION' and old['temporal_scope_match'] == 'HISTORICAL'


def test_identical_machine_interpretation_does_not_close_identity(project):
    store, workspace, root, event = pair(project, reviewed=False)
    result = resolve_transaction_identity(store, workspace, root['id'], event['id'], as_of='2024-06-01')
    assert result['state'] == 'TRANSACTION_UNRESOLVED'
    assert result['reasons'] == ['SCOPED_IDENTITY_AUTHORITY_NOT_ESTABLISHED']


@pytest.mark.parametrize('field,value', [('phase', 'Phase B'), ('name', 'Another project'), ('opportunity_reference', 'OP-B')])
def test_same_participants_do_not_close_different_project_or_phase(project, field, value):
    store, workspace, root, event = pair(project, lambda d:d['identity']['project'].update({field:value}))
    result = resolve_transaction_identity(store, workspace, root['id'], event['id'], as_of='2024-06-01')
    assert result['state'] == 'DIFFERENT_TRANSACTION'


@pytest.mark.parametrize('relation', ['PARENT_CHILD_LINKED', 'QUALIFIED_ENTITY', 'AMBIGUOUS_ENTITY'])
def test_related_or_ambiguous_entity_cannot_substitute_for_transaction_party(project, relation):
    store, workspace, root, event = pair(project, lambda d:d['identity']['participants'][0].update(identity_relation=relation))
    result = resolve_transaction_identity(store, workspace, root['id'], event['id'], as_of='2024-06-01')
    assert result['state'] == 'TRANSACTION_UNRESOLVED'
    assert 'EXACT_LEGAL_PARTICIPANTS_NOT_ESTABLISHED' in result['reasons']


@pytest.mark.parametrize('transaction_class', ['TERM_LOAN', 'MOU', 'STRATEGIC_PARTNERSHIP'])
def test_related_structure_is_not_the_same_equity_transaction(project, transaction_class):
    store, workspace, root, event = pair(project, lambda d:d['identity'].update(transaction_class=transaction_class, joint_structure='NOT_JV'))
    result = resolve_transaction_identity(store, workspace, root['id'], event['id'], as_of='2024-06-01')
    assert result['state'] == 'RELATED_TRANSACTION'


def test_unknown_project_scope_is_not_a_wildcard(project):
    store, workspace, root, event = pair(project, lambda d:d['identity']['project'].update(phase=''))
    result = resolve_transaction_identity(store, workspace, root['id'], event['id'], as_of='2024-06-01')
    assert result['state'] == 'TRANSACTION_UNRESOLVED'


def test_no_shared_interval_cannot_become_current_by_silence(project):
    store, workspace, root, event = pair(project, lambda d:d.update(effective_from='2025-01-01', effective_until='2025-12-31'))
    result = resolve_transaction_identity(store, workspace, root['id'], event['id'], as_of='2025-06-01')
    assert result['state'] == 'EXACT_TRANSACTION'
    assert result['temporal_scope_match'] == 'UNRESOLVED'
    assert 'NO_COMMON_APPLICABILITY_INTERVAL' in result['temporal_reasons']
