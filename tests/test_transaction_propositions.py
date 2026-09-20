"""Source event proposals use actual Claim persistence and existing attention."""
import copy

import pytest

from services.case_workspace import CaseWorkspaceError
from tests.test_kernel_mapping import project


def identity(party):
    return dict(project=dict(name='Controlled opportunity', phase='Phase A', location='Test region',
        sponsor='Controlled sponsor', project_type='Infrastructure', opportunity_reference='OP-A'),
        participants=[dict(participant_id=party['id'], legal_name=party['name'], jurisdiction='Test jurisdiction',
            registration_id='TEST-01', role='Equity participant', identity_relation='EXACT_ENTITY')],
        transaction_class='EQUITY_JV', transaction_reference='AGREEMENT-A',
        economic_scope='Controlled Phase A equity structure', joint_structure='JOINT_EQUITY')


def event_data(party, root=None, dimension=None, **changes):
    return dict(dict(kind='TRANSACTION_EVENT' if root else 'TRANSACTION_IDENTITY',
        transaction_claim_id=root, identity=identity(party), event_dimension=dimension,
        asserted_state='ESTABLISHED', occurred_at='2024-01-01', effective_from='2024-01-01',
        effective_until='2024-12-31', discovered_at='2026-09-20', component_scope='FULL_TRANSACTION',
        component_key='', related_claim_ids=[], replaces_claim_ids=[], continuity='UNRESOLVED',
        facets=dict.fromkeys(('explicit_signing', 'legal_effectiveness', 'financial_close',
            'execution_conditions_complete', 'closing_conditions_complete', 'express_current_confirmation'), 'UNRESOLVED'),
        conditions=[]), **changes)


def source_case(project, *, evaluation_only=False):
    _, store, workspace, evidence, _ = project
    attention = store.record_go_attention(workspace, 'reviewer', 'Inspect transaction source history',
        [evidence['id']], evaluation_only=evaluation_only)
    party = store.record_participant(workspace, 'Controlled participant', 'investor', 'reviewer')
    return store, workspace, evidence, attention, party


def record(store, workspace, evidence, attention, data):
    return store.record_event_proposition(workspace, 'reviewer', attention['id'], data, [evidence['id']],
        'PROJECT_DOCUMENT', 3, evidence['content'], 'Interpret the retained source; authority is not established.',
        attribution='agent_assessment')


def test_event_proposals_append_claims_without_promoting_identity_or_maturity(project):
    store, workspace, evidence, attention, party = source_case(project)
    original = copy.deepcopy((workspace.sources, workspace.evidence_items))
    root = record(store, workspace, evidence, attention, event_data(party))
    signed = record(store, workspace, evidence, attention, event_data(party, root['id'], 'SIGNED'))
    persisted = store.get(workspace.project_id)
    assert len(persisted.claims) == 2 and not persisted.findings and not persisted.applies
    assert persisted.claims[0] == root
    assert signed['adoption_state'] == 'proposed' and signed['claim_class'] == 'ai_proposal'
    assert signed['event_proposition']['data']['occurred_at'] == '2024-01-01'
    assert signed['event_proposition']['data']['discovered_at'] == '2026-09-20'
    assert signed['created_at'] != signed['event_proposition']['data']['occurred_at']
    assert dict(object_type='claim', object_id=root['id']) in signed['evidence_links']
    assert (persisted.sources, persisted.evidence_items) == original
    # A later independent analysis does not rewrite an event's occurrence time.
    store.record_go_attention(persisted, 'reviewer', 'Re-examine retained transaction history', [evidence['id']])
    assert store.get(workspace.project_id).claims == [root, signed]


@pytest.mark.parametrize('change', [
    dict(occurred_at='yesterday'), dict(effective_until='2023-01-01'),
    dict(component_scope='FINANCING', component_key=''),
    dict(transaction_claim_id='foreign', kind='TRANSACTION_EVENT', event_dimension='SIGNED'),
    dict(related_claim_ids=['foreign']),
    dict(conditions=[dict(key='regulatory', outcome='FAILED', blocking_for='EXECUTED', evidence_ids=[])]),
])
def test_invalid_or_foreign_event_premises_do_not_persist_partial_records(project, change):
    store, workspace, evidence, attention, party = source_case(project)
    before = store._path_for(workspace.project_id).read_bytes()
    with pytest.raises(CaseWorkspaceError):
        record(store, workspace, evidence, attention, event_data(party, **change))
    assert store._path_for(workspace.project_id).read_bytes() == before


def test_evaluation_ancestry_cannot_be_removed_by_a_lower_level_claim_call(project):
    store, workspace, evidence, attention, party = source_case(project, evaluation_only=True)
    root = record(store, workspace, evidence, attention, event_data(party))
    event = record(store, workspace, evidence, attention, event_data(party, root['id'], 'ANNOUNCED'))
    assert event['event_proposition']['evaluation_only']
    forged = copy.deepcopy(event['event_proposition'])
    forged['evaluation_only'] = False
    with pytest.raises(CaseWorkspaceError, match='Evaluation ancestry'):
        store.record_investigation_claim(workspace, event['investigation_step_id'],
            statement='Attempted laundering', claim_class='ai_proposal', method='source_event_interpretation',
            confidence_state=event['confidence_state'], author_type='ai', created_by='reviewer',
            evidence_links=event['evidence_links'], event_proposition=forged)
    assert len(store.get(workspace.project_id).claims) == 2


def test_source_mutation_invalidates_event_fingerprint_without_rewriting_history(project):
    store, workspace, evidence, attention, party = source_case(project)
    root = record(store, workspace, evidence, attention, event_data(party))
    changed = copy.deepcopy(workspace)
    changed.evidence_items[0]['content'] = 'A different source reading'
    with pytest.raises(CaseWorkspaceError, match='fingerprints'):
        store._validate_event_proposition(changed, root['event_proposition'], root['evidence_links'])
    assert store.get(workspace.project_id).claims[0] == root


def test_parent_and_subsidiary_scope_is_preserved_not_substituted(project):
    store, workspace, evidence, attention, party = source_case(project)
    data = event_data(party)
    data['identity']['participants'][0]['identity_relation'] = 'PARENT_CHILD_LINKED'
    root = record(store, workspace, evidence, attention, data)
    assert root['event_proposition']['data']['identity']['participants'][0]['identity_relation'] == 'PARENT_CHILD_LINKED'
    assert root['adoption_state'] == 'proposed'


def test_browser_line_endings_match_without_rewriting_quote_or_machine_observation(project):
    store, workspace, evidence, attention, party = source_case(project)
    multiline = store.register_evidence_item(workspace, evidence['source_id'], 'direct_source_evidence', 'First line\nSecond line\n', 'text')
    attention = store.record_go_attention(workspace, 'reviewer', 'Read a multiline source', [multiline['id']])
    before = copy.deepcopy(workspace.evidence_items)
    claim = store.record_event_proposition(workspace, 'reviewer', attention['id'], event_data(party), [multiline['id']],
        'PROJECT_DOCUMENT', 0, 'First line\r\nSecond line\r\n', 'Browser line endings only.', attribution='agent_assessment')
    assert claim['event_proposition']['original_quote'] == 'First line\r\nSecond line\r\n'
    assert workspace.evidence_items == before
    assert not store._source_quote_matches('First  line\nSecond line', multiline['content'])
