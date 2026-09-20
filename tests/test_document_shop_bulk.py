import copy
import hashlib
import io
import uuid
from datetime import datetime, timedelta, timezone
from PIL import Image
import pytest
from tests.test_document_shop_deletion import env, shell, assert_absent
from services.case_workspace import CaseWorkspaceError
from services.perception_jobs import PerceptionJobStore
from services.document_examination import compare_document_analyses


def image_case(env, color='white'):
    _, _, store, _, root = env
    workspace, _ = shell(env)
    folder = root / 'workspace_sources' / workspace.project_id
    folder.mkdir(parents=True)
    path = folder / 'original.png'
    Image.new('RGB', (32, 32), color).save(path)
    store.add_source(workspace, kind='unclassified', name='Original', actor='owner', file_path=str(path),
                     file_hash=hashlib.sha256(path.read_bytes()).hexdigest())
    return workspace


def bulk(env, action, workspaces, **values):
    return env[1].post('/document-shop/bulk', data=dict(action=action,
        project_id=[w.project_id for w in workspaces], **values), follow_redirects=True)


def test_archive_reload_restore_preserves_evidence_and_bytes(env):
    _, client, store, _, root = env
    cases = [image_case(env), image_case(env)]
    before = [copy.deepcopy(w.sources) for w in cases]
    result = bulk(env, 'archive', cases)
    assert b'2 items archived' in result.data
    for w in cases:
        assert_absent(env, w.project_id)
        assert store.get(w.project_id).sources == before[cases.index(w)]
        assert w.project_id.encode() in client.get('/document-shop/jobs?view=archive').data
    bulk(env, 'restore', cases)
    for w in cases:
        assert store.get(w.project_id).removed_at is None
        assert w.project_id.encode() in client.get('/document-shop/jobs').data


def test_bulk_trash_confirmation_restore_and_expiry(env):
    _, client, store, registry, root = env
    cases = [image_case(env), image_case(env)]
    confirmation = bulk(env, 'delete', cases)
    assert b'Delete 2 selected items?' in confirmation.data and b'7 days' in confirmation.data
    assert all(not store.get(w.project_id).removed_at for w in cases)
    result = bulk(env, 'delete', cases, confirm='yes')
    assert b'2 items moved to Recently Deleted' in result.data
    for w in cases:
        assert_absent(env, w.project_id)
        assert w.project_id.encode() in client.get('/document-shop/jobs?view=trash').data
    assert store.purge_document_shop_trash() == []
    bulk(env, 'restore', [cases[0]])
    with env[0].app_context():
        assert store.purge_document_shop_trash(now=datetime.now(timezone.utc) + timedelta(days=8)) == [cases[1].project_id]
    assert store.get(cases[0].project_id) is not None
    assert registry.is_deleted(cases[1].project_id)
    assert not (root / 'workspace_sources' / cases[1].project_id).exists()


def test_expired_restore_refused_and_canonical_project_excluded(env):
    _, _, store, _, _ = env
    w = image_case(env)
    store.move_document_shop_case(w, 'owner', 'trash', now=datetime.now(timezone.utc) - timedelta(days=8))
    with pytest.raises(CaseWorkspaceError, match='expired'):
        store.move_document_shop_case(w, 'owner', 'active')
    other = image_case(env)
    other.container_state = 'project'
    store.save(other)
    assert bulk(env, 'delete', [other], confirm='yes').status_code == 404


@pytest.mark.parametrize('action', ['archive', 'delete', 'restore', 'reanalyze', 'compare'])
def test_entire_bulk_selection_validated_before_any_cross_user_action(env, action):
    _, _, store, _, root = env
    mine, other = image_case(env), image_case(env)
    other.owner = 'other'
    other.access_allow_list = ['owner']
    store.save(other)
    before = {p.name: p.read_bytes() for p in root.glob('*.workspace.json')}
    response = bulk(env, action, [mine, other], confirm='yes', request_id=uuid.uuid4().hex)
    assert response.status_code == 404
    assert {p.name: p.read_bytes() for p in root.glob('*.workspace.json')} == before


def test_reanalysis_new_jobs_same_source_prior_jobs_retained_and_reload_readonly(env):
    _, client, store, _, root = env
    w = image_case(env)
    source = copy.deepcopy(w.sources[0])
    request_id = uuid.uuid4().hex
    result = bulk(env, 'reanalyze', [w], request_id=request_id)
    assert b'1 documents queued for re-analysis' in result.data
    old = PerceptionJobStore(root).for_workspace(w.project_id)
    assert len(old) == 1 and old[0]['analysis_run_id'] == request_id
    bulk(env, 'reanalyze', [w], request_id=request_id)
    assert len(PerceptionJobStore(root).for_workspace(w.project_id)) == 1
    bulk(env, 'reanalyze', [w], request_id=uuid.uuid4().hex)
    assert len(PerceptionJobStore(root).for_workspace(w.project_id)) == 2
    before = {str(p): p.read_bytes() for p in root.rglob('*.json')}
    client.get('/document-shop/jobs')
    assert {str(p): p.read_bytes() for p in root.rglob('*.json')} == before
    assert store.get(w.project_id).sources[0] == source
    assert source['file_hash'] == hashlib.sha256(__import__('pathlib').Path(source['file_path']).read_bytes()).hexdigest()
    assert request_id.encode() in client.get(f'/document-shop/jobs/{w.project_id}/analysis-history').data


def test_compare_real_pixels_read_only_and_qualification(env):
    _, _, store, _, root = env
    cases = [image_case(env, 'white'), image_case(env, 'black')]
    before = {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    result = bulk(env, 'compare', cases)
    assert b'changed' in result.data and b'non-canonical' in result.data and b'unresolved' in result.data
    for w in cases:
        assert w.project_id.encode() in result.data
        assert w.sources[0]['file_hash'].encode() in result.data
    assert {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()} == before
    with pytest.raises(CaseWorkspaceError):
        compare_document_analyses(cases + [cases[0]], 'owner')


def test_inactive_queues_defer_and_selection_is_session_scoped(env):
    _, client, store, _, root = env
    w = image_case(env)
    bulk(env, 'reanalyze', [w], request_id=uuid.uuid4().hex)
    bulk(env, 'archive', [w])
    assert PerceptionJobStore(root).claim_next(worker_id='test') is None
    with client.session_transaction() as session:
        previous = session['document_desk_selection']
    client.get('/logout')
    with client.session_transaction() as session:
        assert 'document_desk_selection' not in session
        session.update(user_id=2, username='other', role='admin')
    client.get('/document-shop/jobs')
    with client.session_transaction() as session:
        assert session['document_desk_selection'] != previous
    assert w.project_id.encode() not in client.get('/document-shop/jobs?view=archive').data


def test_nonimage_reanalysis_uses_existing_parser_without_replacing_registry(env):
    from services import founding_classification
    from services.bhive_parser import ParsedDocument
    from pathlib import Path
    _, _, store, registry, root = env
    w, document = shell(env)
    path = root / 'workspace_sources' / w.project_id / 'original.txt'
    path.parent.mkdir(parents=True)
    path.write_text('The contractor shall preserve original evidence.')
    source = store.add_source(w, kind='unclassified', name='Original text', actor='owner', file_path=str(path),
        file_hash=hashlib.sha256(path.read_bytes()).hexdigest())
    before = (root / (w.project_id + '.json')).read_bytes()
    run_id = uuid.uuid4().hex
    bulk(env, 'reanalyze', [w], request_id=run_id)
    jobs = founding_classification.founding_store(root)
    job = jobs.claim_next(worker_id='test')
    assert job and job['analysis_run_id'] == run_id
    class Parser:
        def parse(self, raw, name):
            assert raw == path.read_bytes()
            return ParsedDocument(project_id='parser-generated-id', filename=name, ingested_at='2026-09-20')
    result = founding_classification.classify_source(env[0], jobs, job, parser=Parser())
    assert result['state'] == 'completed' and result['evidence_refs']
    assert (root / (w.project_id + '.json')).read_bytes() == before
    reading = next(e for e in store.get(w.project_id).evidence_items if e['id'] in result['evidence_refs'])
    assert reading['source_id'] == source['id']
    assert reading['evidence_class'] == 'ai_generated_proposal'
    assert run_id in reading['content'] and 'ANALYTICAL_NOT_CANONICAL' in reading['content']
    founding_classification.classify_source(env[0], jobs, job, parser=Parser())
    assert len(store.get(w.project_id).evidence_items) == 1
