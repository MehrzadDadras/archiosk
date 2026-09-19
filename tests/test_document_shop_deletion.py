"""Deletion is a persisted container transition, not a filtered empty row."""
import copy
import json
import uuid

import pytest

from app import create_app, _nav_recent_projects
from services.bhive_parser import ParsedDocument
from services.case_workspace import CaseWorkspaceStore, CaseWorkspaceError, CONTAINER_STATE_BLACK_BOX
from services.requirements_registry import RequirementsRegistry
from services.perception_jobs import PerceptionJobStore, STATE_FAILED
from services.chunked_upload import ChunkedUploadStore
from services.governance import GovernanceLog


@pytest.fixture
def env(tmp_path):
    app = create_app('testing')
    app.config['REGISTRY_STORE_PATH'] = str(tmp_path)
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1, username='owner', role='admin')
    return app, client, CaseWorkspaceStore(tmp_path), RequirementsRegistry(tmp_path), tmp_path


def shell(env, name='Failed empty Castille regression'):
    _, _, store, registry, _ = env
    pid = str(uuid.uuid4())
    document = ParsedDocument(project_id=pid, filename=name, ingested_at='2026-09-15T00:00:00Z')
    registry.save(document)
    workspace = store.get_or_create(pid)
    workspace.owner = 'owner'
    workspace.container_state = CONTAINER_STATE_BLACK_BOX
    workspace.display_title = name
    store.save(workspace)
    return workspace, document


def assert_absent(env, pid):
    app, client, store, registry, _ = env
    for url in ('/document-shop/jobs', '/projects', '/projects/choose', '/',
                '/search?q=Castille', '/removed-projects'):
        response = client.get(url, follow_redirects=True)
        assert response.status_code == 200, url
        assert pid not in response.get_data(as_text=True), url
    for suffix in ('', '/status'):
        assert client.get('/document-shop/jobs/' + pid + suffix).status_code == 404
    with app.test_request_context('/'):
        from flask import session
        session.update(user_id=1, username='owner', role='admin')
        assert pid not in {row['project_id'] for row in _nav_recent_projects(app)}


def test_failed_empty_job_delete_reload_projections_direct_url_and_no_collateral(env):
    app, client, store, registry, root = env
    workspace, document = shell(env)
    other, _ = shell(env, 'Retained evidence')
    other.evidence_items.append(dict(id='canonical', content='protected evidence'))
    store.save(other)
    before = (root / (other.project_id + '.workspace.json')).read_bytes()
    jobs = PerceptionJobStore(root)
    job = jobs.enqueue(workspace_id=workspace.project_id, source_id='failed-upload', source_sha256='x')
    job['state'] = STATE_FAILED
    jobs._write(job)
    chunks = ChunkedUploadStore(root)
    upload_id = uuid.uuid4().hex
    chunks.save_chunk(workspace.project_id, upload_id, 0, 1, 'upload.pdf', b'pending')
    owned = root / 'workspace_sources' / workspace.project_id
    owned.mkdir(parents=True)
    (owned / 'abandoned.part').write_bytes(b'unaccepted upload')
    store.record_last_viewed(workspace, 'owner')
    GovernanceLog(root).append(project_id=workspace.project_id, event_type='test_creation', actor='owner', role='human', payload={})
    body = client.get('/document-shop/jobs').get_data(as_text=True)
    assert workspace.project_id in body and 'Could not complete' in body and '0 documents' in body
    path = '/document-shop/jobs/' + workspace.project_id + '/delete'
    assert b'permanently erased' in client.post(path).data
    assert store.get(workspace.project_id) is not None
    response = client.post(path, data={'confirm': 'yes'}, follow_redirects=True)
    assert response.status_code == 200 and workspace.project_id.encode() not in response.data
    assert_absent(env, workspace.project_id)
    assert not jobs.for_workspace(workspace.project_id)
    assert not owned.exists()
    assert not (root / 'pending_chunk_uploads' / upload_id).exists()
    assert not (root / '_view_state' / (workspace.project_id + '.json')).exists()
    assert not (root / (workspace.project_id + '.workspace.json')).exists()
    assert not (root / (workspace.project_id + '.json')).exists()
    assert registry.is_deleted(workspace.project_id)
    assert (root / (other.project_id + '.workspace.json')).read_bytes() == before
    for write in (lambda: store.save(workspace), lambda: store.get_or_create(workspace.project_id),
                  lambda: registry.save(document), lambda: jobs._write(job),
                  lambda: chunks.save_chunk(workspace.project_id, upload_id, 0, 1, 'x.pdf', b'x')):
        with pytest.raises((ValueError, CaseWorkspaceError)):
            write()
    store.record_last_viewed(workspace, 'owner')  # absent workspace is already a no-op
    assert not (root / '_view_state' / (workspace.project_id + '.json')).exists()
    assert_absent(env, workspace.project_id)
    audit = GovernanceLog(root)
    audit.append(project_id=workspace.project_id, event_type='late_worker_status', actor='worker', role='system', payload={})
    assert audit.read(workspace.project_id) == []
    assert (root / (workspace.project_id + '.governance.jsonl')).exists()
    assert not (root / '_deleted' / (workspace.project_id + '.governance.jsonl')).exists()
    for url in (f'/projects/{workspace.project_id}/workspace', f'/dashboard/{workspace.project_id}'):
        assert client.get(url, follow_redirects=True).status_code == 404


def test_last_source_removal_erases_disposable_case_and_private_evidence(env):
    _, client, store, registry, root = env
    workspace, _ = shell(env)
    source = store.add_source(workspace, kind='unclassified', name='Castille', actor='owner', file_path=None)
    workspace.evidence_items.append(dict(id='ocr', source_id=source['id'], content='machine text'))
    store.save(workspace)
    response = client.post(f'/document-shop/jobs/{workspace.project_id}/sources/{source["id"]}/remove',
                           data={'confirm': 'yes'}, follow_redirects=True)
    assert response.status_code == 200
    after = store.get(workspace.project_id)
    assert after is None
    assert registry.is_deleted(workspace.project_id)
    assert_absent(env, workspace.project_id)


def test_existing_zero_active_source_shell_is_erased(env):
    _, _, store, registry, root = env
    workspace, _ = shell(env)
    source = store.add_source(workspace, kind='unclassified', name='Old Castille', actor='owner', file_path=None)
    source['removed_at'] = '2026-09-19T00:00:00Z'
    workspace.project_conversation.append(dict(id='conversation', text='Retain my review'))
    store.save(workspace)
    before = copy.deepcopy(workspace.sources)
    assert store.delete_document_shop_job(workspace, actor='owner')['state'] == 'SAFE_TO_ERASE'
    assert store.get(workspace.project_id) is None
    assert_absent(env, workspace.project_id)


def test_foreign_canonical_reference_survives_disposable_case_deletion(env):
    _, client, store, _, root = env
    workspace, _ = shell(env)
    other, _ = shell(env, 'Other project')
    other.relationships.append(dict(id='shared-reference', target_project_id=workspace.project_id))
    store.save(other)
    before = (root / (other.project_id + '.workspace.json')).read_bytes()
    assert store.document_shop_deletion_state(workspace)['state'] == 'SAFE_TO_ERASE'
    response = client.post('/document-shop/jobs/' + workspace.project_id + '/delete', data={'confirm': 'yes'})
    assert response.status_code == 303
    assert (root / (other.project_id + '.workspace.json')).read_bytes() == before
    assert_absent(env, workspace.project_id)


def test_unauthorized_delete_and_populated_project_cannot_use_shell_erasure(env):
    _, client, store, _, _ = env
    workspace, _ = shell(env)
    with client.session_transaction() as session:
        session.update(username='stranger', role='customer')
    assert client.post('/document-shop/jobs/' + workspace.project_id + '/delete', data={'confirm': 'yes'}).status_code == 404
    with pytest.raises(CaseWorkspaceError):
        store.delete_document_shop_job(workspace, actor='stranger')
    workspace.container_state = 'project'
    store.save(workspace)
    with pytest.raises(CaseWorkspaceError):
        store.delete_document_shop_job(workspace, actor='owner')
    assert store.get(workspace.project_id) is not None


def test_running_worker_cannot_resurrect_deleted_case(env):
    _, _, store, _, root = env
    workspace, _ = shell(env)
    jobs = PerceptionJobStore(root)
    job = jobs.enqueue(workspace_id=workspace.project_id, source_id='upload', source_sha256='x')
    job['state'] = 'running'
    jobs._write(job)
    store.delete_document_shop_job(workspace, actor='owner')
    with pytest.raises(ValueError):
        jobs._write(job)


def test_reload_is_read_only(env):
    _, client, _, _, root = env
    workspace, _ = shell(env)
    client.get('/document-shop/jobs')  # establish any pre-existing owner backfill
    paths = list(root.glob('*.json'))
    before = {str(p): p.read_bytes() for p in paths}
    response = client.get('/document-shop/jobs')
    assert b'document-shop.jobs.reload' in response.data
    assert response.cache_control.no_store
    assert {str(p): p.read_bytes() for p in paths} == before


def test_interrupted_cleanup_cannot_resurrect_and_can_be_resumed(env, monkeypatch):
    _, _, store, registry, root = env
    workspace, _ = shell(env)
    audit = GovernanceLog(root)
    audit.append(project_id=workspace.project_id, event_type='before_deletion', actor='owner', role='human')
    cleanup = store._erase_document_shop_files
    def interrupted(_pid):
        raise OSError('simulated cleanup interruption')
    monkeypatch.setattr(store, '_erase_document_shop_files', interrupted)
    with pytest.raises(OSError):
        store.delete_document_shop_job(workspace, actor='owner')
    assert registry.is_deleted(workspace.project_id)
    assert store.get(workspace.project_id) is None
    assert_absent(env, workspace.project_id)
    audit.append(project_id=workspace.project_id, event_type='late_status', actor='worker', role='system')
    monkeypatch.setattr(store, '_erase_document_shop_files', cleanup)
    store.delete_document_shop_job(workspace, actor='owner')
    assert not (root / (workspace.project_id + '.workspace.json')).exists()
    records = [json.loads(line) for line in (root / (workspace.project_id + '.governance.jsonl')).read_text().splitlines()]
    assert [r['event_type'] for r in records] == ['before_deletion', 'late_status']
    assert audit.read(workspace.project_id) == []


def test_malformed_dependent_storage_refuses_before_committing(env):
    _, _, store, registry, root = env
    workspace, _ = shell(env)
    directory = root / 'visual_jobs'
    directory.mkdir()
    (directory / 'unreadable.json').write_text('{')
    with pytest.raises(CaseWorkspaceError):
        store.delete_document_shop_job(workspace, actor='owner')
    assert not registry.is_deleted(workspace.project_id)
    assert store.get(workspace.project_id) is not None


def test_old_project_delete_door_erases_only_disposable_case(env):
    _, client, store, registry, _ = env
    workspace, _ = shell(env)
    store.add_source(workspace, kind='unclassified', name='Retained', actor='owner', file_path=None)
    response = client.post(f'/projects/{workspace.project_id}/delete', data={'confirm': 'yes'})
    assert response.status_code == 303
    after = store.get(workspace.project_id)
    assert after is None
    assert registry.is_deleted(workspace.project_id)


def test_stale_upload_and_reconcile_cannot_leave_new_staging(env):
    import io
    from werkzeug.datastructures import FileStorage
    from services.ingestion import attach_document_shop_sources, PendingReconcileStore
    app, _, store, _, root = env
    workspace, _ = shell(env)
    store.delete_document_shop_job(workspace, actor='owner')
    results = attach_document_shop_sources(app, workspace,
        [FileStorage(stream=io.BytesIO(b'unaccepted'), filename='late.txt')], owner='owner')
    assert results[0]['status'] == 'rejected'
    assert not (root / 'workspace_sources' / workspace.project_id).exists()
    with pytest.raises(ValueError):
        PendingReconcileStore(root).create(workspace.project_id, {}, [], 'owner', 'human')


def test_legacy_registry_shared_upload_is_protected_even_without_workspace(env):
    _, _, store, registry, root = env
    workspace, _ = shell(env)
    shared = root / 'workspace_sources' / workspace.project_id / 'shared.pdf'
    shared.parent.mkdir(parents=True)
    shared.write_bytes(b'canonical in another container')
    registry.save(ParsedDocument(project_id=str(uuid.uuid4()), filename='Legacy retained source',
        ingested_at='2026-09-15', original_file_path=str(shared)))
    store.delete_document_shop_job(workspace, actor='owner')
    assert shared.read_bytes() == b'canonical in another container'
    assert registry.is_deleted(workspace.project_id)


def test_populated_disposable_case_erases_private_files_and_runtime(env, tmp_path):
    from services.runtime_observation import directory, _retain, read
    app, client, store, registry, root = env
    app.instance_path = str(tmp_path / 'instance')
    workspace, _ = shell(env)
    folder = root / 'workspace_sources' / workspace.project_id
    folder.mkdir(parents=True)
    original = folder / 'original.pdf'
    original.write_bytes(b'private original')
    source = store.add_source(workspace, kind='unclassified', name='Private', actor='owner', file_path=str(original))
    workspace.evidence_items.append(dict(id='derived', source_id=source['id'], content='private result'))
    store.save(workspace)
    record = dict(id='a' * 32, request=dict(arguments=dict(project_id=workspace.project_id)), events=[])
    unrelated = dict(id='b' * 32, request=dict(arguments=dict(project_id='other')), events=[])
    _retain(app, record)
    _retain(app, unrelated)
    response = client.post('/document-shop/jobs/' + workspace.project_id + '/delete', data={'confirm': 'yes'})
    assert response.status_code == 303
    assert not folder.exists()
    assert not (directory(app) / (record['id'] + '.json')).exists()
    assert not _retain(app, record)
    assert read(app, unrelated['id']) == unrelated
    assert_absent(env, workspace.project_id)


def test_shared_source_identity_preserves_bytes_but_private_sibling_is_erased(env):
    _, _, store, registry, root = env
    workspace, _ = shell(env)
    other, _ = shell(env, 'Established project')
    other.container_state = 'project'
    folder = root / 'workspace_sources' / workspace.project_id
    folder.mkdir(parents=True)
    shared = folder / 'shared.pdf'
    shared.write_bytes(b'shared canonical bytes')
    private = folder / 'private.pdf'
    private.write_bytes(b'private bytes')
    source = store.add_source(workspace, kind='unclassified', name='Shared', actor='owner', file_path=str(shared))
    other.evidence_items.append(dict(id='canonical', source_id=source['id'], content='canonical evidence'))
    store.save(other)
    before = (root / (other.project_id + '.workspace.json')).read_bytes()
    store.delete_document_shop_job(workspace, actor='owner')
    assert shared.read_bytes() == b'shared canonical bytes'
    assert not private.exists()
    assert registry.is_deleted(workspace.project_id)
    assert (root / (other.project_id + '.workspace.json')).read_bytes() == before
