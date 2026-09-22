"""Project-scoped immutable snapshots using the existing workspace/binary store."""
import copy
import json
import time
import os
import re
from contextlib import contextmanager
import uuid
from datetime import datetime, timezone
from pathlib import Path

from services import planning_map_export as maps, planning_result_view as views
from services import planning_export, document_export

VERSION = "planning-study@1"


class WorkingResults:
    """Shared TTL staging, following PendingReconcileStore/ChunkedUploadStore.

    This is not project history. Only Save Study writes the workspace index.
    All workers must share the existing REGISTRY_STORE_PATH filesystem.
    """
    TTL_SECONDS = 3600

    def __init__(self, store_path):
        self.directory = Path(store_path) / 'pending_planning_results'
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, key):
        if not isinstance(key, str) or not re.fullmatch(r'[0-9a-f]{32}', key):
            raise ValueError('Invalid planning run ID')
        return self.directory / (key + '.json')

    def put(self, project_id, actor, result):
        if not project_id or not actor:
            raise ValueError('Project and authenticated actor required')
        now = time.time()
        # Opportunistic TTL cleanup, as in existing upload staging. Never sweep
        # lock files: unlinking an active lock would permit a second lock inode.
        for path in self.directory.glob('*.json'):
            try:
                if now >= json.loads(path.read_bytes())['expires_at']:
                    path.unlink(missing_ok=True)
            except (OSError, ValueError, KeyError):
                continue
        key = uuid.uuid4().hex
        payload = maps.encoded(result)
        envelope = dict(run_id=key, project_id=project_id, actor=actor,
                        created_at=now, expires_at=now + self.TTL_SECONDS,
                        result=result, result_sha256=maps.sha(payload))
        temporary = self.directory / (key + '.tmp')
        with temporary.open('xb') as stream:
            stream.write(maps.encoded(envelope))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self._path(key))
        return key

    def get(self, key, project_id, actor):
        path = self._path(key)
        try:
            item = json.loads(path.read_bytes())
        except FileNotFoundError:
            raise ValueError('Planning run unavailable or expired') from None
        if item['run_id'] != key:
            raise ValueError('Planning run identity mismatch')
        if not actor or item['actor'] != actor:
            raise ValueError('Planning run belongs to another user')
        if item['project_id'] != project_id:
            raise ValueError('Planning run belongs to another project')
        if time.time() >= item['expires_at']:
            raise ValueError('Planning run expired; no study was reconstructed')
        if maps.sha(maps.encoded(item['result'])) != item['result_sha256']:
            raise ValueError('Planning run integrity failure')
        return item['result']

    @contextmanager
    def _save_lock(self, project_id):
        # OS advisory lock, not Python memory or a stale O_EXCL lease. The OS
        # releases it on worker exit. Nonblocking contention is an explicit 409.
        path = self.directory / (maps.sha(project_id.encode()) + '.lock')
        with path.open('a+b') as stream:
            if path.stat().st_size == 0:
                stream.write(b'0'); stream.flush()
            stream.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise ValueError('Planning save already in progress; retry Save Study') from None
            try:
                yield
            finally:
                stream.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream, fcntl.LOCK_UN)

    def save_study(self, store, key, project_id, actor, *, formats=()):
        self._path(key)
        with self._save_lock(project_id):
            result = self.get(key, project_id, actor)
            workspace = store.get(project_id)
            if workspace is None or workspace.removed_at:
                raise ValueError('Project unavailable')
            existing = next((s for s in workspace.planning_studies if s['id'] == key), None)
            if existing and not set(formats) <= {
                    name.removeprefix('report.') for name in existing['artifacts'] if name.startswith('report.')}:
                raise ValueError('Study already saved with different report selection')
            from services.case_workspace import ConcurrentModificationError
            try:
                return save(store, workspace, result, actor=actor, study_id=key, formats=formats)
            except ConcurrentModificationError:
                raise ValueError('Project changed during save; study was not indexed') from None


def _directory(store, project_id, study_id):
    # Path identity is entirely host controlled; reject traversal, not sanitize it.
    if not project_id or any(c in project_id for c in '/\\:') or project_id in ('.','..'):
        raise ValueError("Invalid project identity")
    if uuid.UUID(hex=study_id).hex != study_id:
        raise ValueError("Invalid study identity")
    return store.binaries_path / project_id / study_id


def save(store, workspace, result, *, actor, study_id, formats=(), source_ids=()):
    if workspace.removed_at:
        raise ValueError("Removed project")
    if not set(formats)<=set(planning_export.FORMATS):
        raise ValueError("Unsupported report format")
    if not set(source_ids)<={s['id'] for s in workspace.sources}:
        raise ValueError("Source reference outside project")
    result=copy.deepcopy(result)
    digest=maps.sha(maps.encoded(result))
    existing=next((s for s in workspace.planning_studies if s['id']==study_id),None)
    if existing:
        if existing['snapshot_sha256']!=digest:
            raise ValueError("Immutable result identity conflict")
        return existing
    view=views.build_view(result)
    subject=result['document']['subject']
    address=subject.get('normalized_address') or subject.get('address_as_given')
    if not address:raise ValueError("Property identity missing")
    r=result.get('retrieval') or {}
    created=datetime.now(timezone.utc).isoformat()
    files={'snapshot.json':maps.encoded(result)}
    # The snapshot contains the unchanged matrix/statements, unresolveds, source
    # URLs/hashes and existing Source IDs. Raw source documents are not copied.
    panels=[]; visual_status='UNAVAILABLE'; figure=None
    from services import planning_acceptance as acceptance, planning_visual
    panels=planning_visual.panels_for(r,tokens=result.get('spatial_tokens'))
    check=acceptance.evaluate(result,panels=panels)
    if check['state']==acceptance.FAIL:
        raise ValueError("Visual/text disagreement; study not saved")
    try:
        asset=maps.build(result,address=address)
        files.update({'evidence/zoning-map.png':asset['png'],
                      'evidence/zoning-map.svg':asset['svg'].encode(),
                      'evidence/provenance.json':maps.encoded(asset['provenance']),
                      'evidence/parcel-geometry.json':maps.encoded(asset['parcel']),
                      'evidence/zoning-geometry.json':maps.encoded(asset['zones'])})
        visual_status=asset['provenance']['acceptance']['state'];figure=asset['figure']
    except ValueError as exc:
        if check['state'] in (acceptance.PASS, acceptance.PASS_WITH_UNRESOLVED_EXCEPTION):
            raise
        files['evidence/provenance.json']=maps.encoded({'visual_status':'UNAVAILABLE','reason':str(exc),
            'acceptance':check,'retrieval':r})
    document=planning_export.build_export_document(view,generated_at=created)
    if result.get('fixture_note'):document.preamble.insert(0,result['fixture_note'])
    if figure:document.figures.append(figure)
    else:document.preamble.append('Official zoning visual unavailable; see retained evidence limitations.')
    if result.get('workspace_context'):
        from services import planning_composer
        document = planning_composer.report_document(result)
        # Each parcel keeps its own geometry/provenance namespace. No union.
        for index, item in enumerate(planning_composer.properties(result)[1:], 2):
            prefix = f'evidence/property-{index}/'
            extra_panels = planning_visual.panels_for(item.get('retrieval') or {}, tokens=item.get('spatial_tokens'))
            extra_check = acceptance.evaluate(item, panels=extra_panels)
            if extra_check['state'] == acceptance.FAIL:
                raise ValueError('Visual/text disagreement in additional property')
            try:
                extra = maps.build(item, address=item['document']['subject'].get('normalized_address'))
                files.update({prefix+'zoning-map.png': extra['png'],
                              prefix+'provenance.json': maps.encoded(extra['provenance']),
                              prefix+'parcel-geometry.json': maps.encoded(extra['parcel']),
                              prefix+'zoning-geometry.json': maps.encoded(extra['zones'])})
            except ValueError:
                if extra_check['state'] in (acceptance.PASS, acceptance.PASS_WITH_UNRESOLVED_EXCEPTION):
                    raise
                files[prefix+'provenance.json'] = maps.encoded({'visual_status': 'UNAVAILABLE', 'acceptance': extra_check})
    for fmt in formats:
        files['report.'+fmt]=document_export.build(document,fmt).getvalue()
    zones=r.get('zone_features') or []
    record={'id':study_id,'project_id':workspace.project_id,'version':VERSION,'saved_at':created,
            'analysis_timestamp':r.get('retrieved_at'),'saved_by':actor,'address':address,
            'status':result['document'].get('result_status'),'parcel_identifier':subject.get('parcel_identifier'),
            'zone_labels':[z.get('zone_label') for z in zones if z.get('qualified')],
            'exception_status':[z.get('exception_status') for z in zones if z.get('qualified')],
            'unresolved_count':len(result['document'].get('unresolved') or []),
            'source_ids':list(source_ids),'snapshot_sha256':digest,'visual_status':visual_status,
            'artifacts':{n:maps.sha(b) for n,b in files.items()}}
    if result.get('workspace_context'):
        record['properties'] = [{'subject': p['document']['subject'],
                                 'result_status': p['document'].get('result_status')}
                                for p in planning_composer.properties(result)]
    root=_directory(store,workspace.project_id,study_id)
    root.mkdir(parents=True,exist_ok=True)
    for name,data in files.items():
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            if target.read_bytes()!=data:raise ValueError("Existing artifact conflict")
        else:
            with target.open('xb') as stream:stream.write(data)
    # The index is published only after every artifact is complete. Store.save
    # supplies the existing atomic version check; failed writes cannot replace
    # another study. Unindexed files never appear in saved-study navigation.
    workspace.planning_studies.append(record)
    store.save(workspace)
    return copy.deepcopy(record)


def artifact(store, workspace, study_id, name):
    record=next((s for s in workspace.planning_studies if s['id']==study_id),None)
    if not record or name not in record['artifacts']:raise ValueError("Study/artifact not found")
    path=_directory(store,workspace.project_id,study_id)/name
    raw=path.read_bytes()
    if maps.sha(raw)!=record['artifacts'][name]:raise ValueError("Saved artifact integrity failure")
    return raw


def reopen(store,workspace,study_id):
    return json.loads(artifact(store,workspace,study_id,'snapshot.json'))
