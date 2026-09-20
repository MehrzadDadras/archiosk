import copy
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests.test_document_shop_deletion import env
from tests.test_document_shop_bulk import image_case
from services.conversational_turn import resolve_selection_command
from services.perception_jobs import PerceptionJobStore


def proposal(action, **extra):
    return dict(action_id=action, parameters={}, user_requested=True, **extra)


def post_command(env, cases, command, **form):
    with patch('services.conversational_turn.call_llm_json', return_value=SimpleNamespace(
            ran=True, parsed={'command':command})) as provider:
        response = env[1].post('/document-shop/bulk', data=dict(action='command',
            project_id=[w.project_id for w in cases], command_text='Apply the requested action to these selected documents.',
            request_id=uuid.uuid4().hex, **form), follow_redirects=True)
    return response, provider


def test_archive_command_uses_existing_lifecycle_and_sends_only_selection_labels(env):
    _, client, store, _, root = env
    cases = [image_case(env), image_case(env)]
    original = [copy.deepcopy((w.sources, w.evidence_items, w.analyses)) for w in cases]
    response, provider = post_command(env, cases, proposal('ARCHIVE_ITEMS'))
    assert b'2 items archived' in response.data
    for index, case in enumerate(cases):
        saved = store.get(case.project_id)
        assert saved.document_desk_state == 'archive'
        assert (saved.sources, saved.evidence_items, saved.analyses) == original[index]
        assert case.project_id.encode() not in client.get('/document-shop/jobs').data
    kwargs = provider.call_args.kwargs
    assert 'image_base64' not in kwargs and str(root) not in kwargs['user_prompt']
    assert all(case.project_id not in kwargs['user_prompt'] for case in cases)
    assert 'ARCHIVE_ITEMS' in kwargs['system_prompt'] and 'ROTATE_VIEW' not in kwargs['system_prompt']


def test_delete_command_cannot_supply_confirmation_even_through_form(env):
    _, client, store, _, _ = env
    case = image_case(env)
    response, _ = post_command(env, [case], proposal('DELETE_ITEMS'), confirm='yes')
    assert b'Delete 1 selected items?' in response.data and b'7 days' in response.data
    assert store.get(case.project_id).document_desk_state == 'active'
    response = client.post('/document-shop/bulk', data=dict(action='delete', project_id=case.project_id, confirm='yes'))
    assert response.status_code == 303 and store.get(case.project_id).document_desk_state == 'trash'


def test_compare_command_uses_existing_qualified_comparison_without_mutation(env):
    _, _, store, _, _ = env
    cases = [image_case(env), image_case(env)]
    before = [store._path_for(w.project_id).read_bytes() for w in cases]
    response, _ = post_command(env, cases, proposal('COMPARE_ITEMS'))
    assert b'Analytical, non-canonical' in response.data
    assert all(w.project_id.encode() in response.data for w in cases)
    assert [store._path_for(w.project_id).read_bytes() for w in cases] == before


def test_reanalyze_command_preserves_source_and_reload_never_calls_provider(env):
    _, client, store, _, root = env
    case = image_case(env)
    source = copy.deepcopy(case.sources[0])
    original = Path(source['file_path']).read_bytes()
    response, _ = post_command(env, [case], proposal('REANALYZE_ITEMS'))
    assert b'1 documents queued for re-analysis' in response.data
    assert len(PerceptionJobStore(root).for_workspace(case.project_id)) == 1
    assert store.get(case.project_id).sources[0] == source
    assert Path(source['file_path']).read_bytes() == original
    before = {str(p):p.read_bytes() for p in root.rglob('*.json')}
    with patch('services.conversational_turn.call_llm_json') as provider:
        assert client.get('/document-shop/jobs').status_code == 200
    provider.assert_not_called()
    assert {str(p):p.read_bytes() for p in root.rglob('*.json')} == before


def test_reload_command_is_only_a_read_of_persisted_state(env):
    _, _, store, _, root = env
    case = image_case(env)
    original = {str(p):p.read_bytes() for p in root.rglob('*.json')}
    response, _ = post_command(env, [case], proposal('RELOAD_STATE'))
    assert response.status_code == 200 and b'My documents' in response.data
    assert {str(p):p.read_bytes() for p in root.rglob('*.json')} == original
    assert PerceptionJobStore(root).for_workspace(case.project_id) == []


@pytest.mark.parametrize('command', [None, proposal('FIT_VIEW'),
    proposal('DELETE_ITEMS', actor='admin'),
    dict(action_id='DELETE_ITEMS', parameters={'confirm':True}, user_requested=True),
    dict(action_id='ARCHIVE_ITEMS', parameters={}, user_requested=False)])
def test_unresolved_or_out_of_context_commands_do_not_mutate(env, command):
    _, _, store, _, _ = env
    case = image_case(env)
    original = store._path_for(case.project_id).read_bytes()
    response, _ = post_command(env, [case], command)
    assert b'No single supported action was resolved' in response.data
    assert store._path_for(case.project_id).read_bytes() == original


def test_foreign_or_inactive_selection_refuses_before_sending_context(env):
    _, client, store, _, _ = env
    case = image_case(env)
    case.owner = 'someone-else'
    store.save(case)
    response, provider = post_command(env, [case], proposal('ARCHIVE_ITEMS'))
    assert response.status_code == 404
    provider.assert_not_called()
    case.owner = 'owner'
    store.save(case)
    store.move_document_shop_case(case, 'owner', 'archive')
    response, provider = post_command(env, [case], proposal('DELETE_ITEMS'))
    assert response.status_code == 409
    provider.assert_not_called()


def test_lifecycle_is_rechecked_after_intent_resolution(env):
    _, client, store, _, _ = env
    case = image_case(env)
    def changed_selection(**kwargs):
        store.move_document_shop_case(store.get(case.project_id), 'owner', 'archive')
        return SimpleNamespace(ran=True, parsed={'command':proposal('DELETE_ITEMS')})
    with patch('services.conversational_turn.call_llm_json', side_effect=changed_selection):
        response = client.post('/document-shop/bulk', data=dict(action='command',
            project_id=case.project_id, command_text='Delete this selected case'))
    assert response.status_code == 409
    assert store.get(case.project_id).document_desk_state == 'archive'


def test_provider_outage_and_invalid_input_are_explicit_without_execution():
    with patch('services.conversational_turn.call_llm_json', return_value=SimpleNamespace(ran=False)):
        assert resolve_selection_command('Archive these', ['Document'])['state'] == 'UNRESOLVED'
    with patch('services.conversational_turn.call_llm_json') as provider:
        assert resolve_selection_command('', ['Document'])['state'] == 'REFUSED'
        assert resolve_selection_command('Archive', [])['state'] == 'REFUSED'
    provider.assert_not_called()
    with patch('services.conversational_turn.call_llm_json', return_value=SimpleNamespace(ran=True,
            parsed={'command':proposal('ARCHIVE_ITEMS'), 'project_id':'foreign'})):
        assert resolve_selection_command('Archive these', ['Document'])['command'] is None


def test_one_restricted_case_blocks_provider_for_entire_selection(env):
    _, _, store, _, _ = env
    cases = [image_case(env), image_case(env)]
    cases[1].security_profile = 'restricted'
    store.save(cases[1])
    original = [store._path_for(w.project_id).read_bytes() for w in cases]
    response, provider = post_command(env, cases, proposal('ARCHIVE_ITEMS'))
    assert b'do not permit this AI request' in response.data
    provider.assert_not_called()
    assert [store._path_for(w.project_id).read_bytes() for w in cases] == original


def test_unreadable_security_policy_fails_closed(env):
    case = image_case(env)
    with patch('services.conversation_interpreter._evaluate_external_ai_policy', side_effect=OSError('Unavailable')):
        response, provider = post_command(env, [case], proposal('ARCHIVE_ITEMS'))
    assert b'do not permit this AI request' in response.data
    provider.assert_not_called()
    assert env[2].get(case.project_id).document_desk_state == 'active'
