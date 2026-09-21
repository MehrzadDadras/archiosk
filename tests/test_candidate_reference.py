"""Candidate discovery uses real source persistence, without granting authority."""
import copy
import hashlib
from dataclasses import replace

import pytest

from tests.test_kernel_mapping import project
from tests.test_airlock_web_research_01 import _FakeOpener
from services import external_research as er
from services.case_workspace import CaseWorkspaceError


def setup_reference(project, monkeypatch, *, evaluation=False):
    _, store, workspace, evidence, client = project
    attention = store.record_go_attention(workspace, 'reviewer', 'Investigate a candidate capital source',
        [evidence['id']], evaluation_only=evaluation)
    raw = b'<html><body>' + b'Controlled public disclosure fixture. No current investor mandate or project applicability is established. ' * 4 + b'</body></html>'
    opener = _FakeOpener(body=raw)
    original = er.retrieve_reference
    monkeypatch.setattr(er, 'retrieve_reference', lambda source: original(source, opener=opener))
    return store, workspace, attention, client, raw, opener


def test_actual_route_retains_bytes_provenance_and_readonly_reload(project, monkeypatch):
    store, workspace, attention, client, raw, opener = setup_reference(project, monkeypatch)
    old = copy.deepcopy((workspace.claims, workspace.reviewer_validations, workspace.applies))
    response = client.post('/projects/project/attention', data=dict(action='public_reference',
        analysis_id=attention['id'], source_key='cib-sectors', reason='Inspect the public source as candidate material.'))
    assert response.status_code == 303
    saved = store.get('project')
    result = saved.analyses[-1]['governed_result']
    assert result['kind'] == 'public_reference' and result['state'] == 'UNRESOLVED'
    source = saved.sources[-1]
    from pathlib import Path
    assert Path(source['file_path']).read_bytes() == raw
    assert source['file_hash'] == hashlib.sha256(raw).hexdigest()
    assert source['origin_reference'] == 'https://cib-bic.ca/en/sectors/priority-sectors/'
    assert saved.evidence_items[-1]['validation_status'] is None
    assert (saved.claims, saved.reviewer_validations, saved.applies) == old
    before = store._path_for('project').read_bytes()
    page = client.get(response.location)
    assert page.status_code == 200 and b'Candidate public sources' in page.data
    assert b'CURRENTNESS_UNRESOLVED' in page.data
    assert store._path_for('project').read_bytes() == before and len(opener.calls) == 1
    from services.runtime_observation import read
    trace = read(project[0], response.headers['X-ARCHIOSK-Observation'])
    assert any(e['phase']=='INVOKED' and e['owner'].endswith('.retain_public_reference') for e in trace['events'])
    assert any(step['step_kind'] == 'governed_work_plan' for step in saved.investigation_steps)


def test_repeated_explicit_fetch_reuses_identical_source_without_strengthening(project, monkeypatch):
    store, workspace, attention, _, _, opener = setup_reference(project, monkeypatch)
    first = store.retain_public_reference(workspace, 'reviewer', attention['id'], 'cib-process', 'Candidate investigation')
    sources = copy.deepcopy((workspace.sources, workspace.evidence_items, workspace.claims))
    second = store.retain_public_reference(workspace, 'reviewer', attention['id'], 'cib-process', 'Explicit source refresh')
    assert len(opener.calls) == 2 and first['id'] != second['id']
    assert second['governed_result']['reused_identical_source']
    assert second['governed_result']['state'] == 'UNRESOLVED'
    assert (workspace.sources, workspace.evidence_items, workspace.claims) == sources


def test_policy_denial_precedes_network_and_persistence(project, monkeypatch):
    store, workspace, attention, _, _, opener = setup_reference(project, monkeypatch)
    workspace.security_profile = 'highly_restricted'
    store.save(workspace)
    before = store._path_for('project').read_bytes()
    with pytest.raises(CaseWorkspaceError, match='not authorized'):
        store.retain_public_reference(workspace, 'reviewer', attention['id'], 'cib-sectors', 'Candidate investigation')
    assert not opener.calls and store._path_for('project').read_bytes() == before


def test_unknown_or_same_host_unconfigured_route_is_refused_before_network(project, monkeypatch):
    store, workspace, attention, _, _, opener = setup_reference(project, monkeypatch)
    with pytest.raises(CaseWorkspaceError, match='configured'):
        store.retain_public_reference(workspace, 'reviewer', attention['id'], 'https://cib-bic.ca/private', 'Candidate investigation')
    assert not opener.calls
    with pytest.raises(er.ExternalResearchError):
        er.retrieve_reference(replace(er.REFERENCE_SOURCES[0], url='https://www.ontario.ca/unconfigured'))


def test_failed_atomic_save_leaves_no_source_evidence_or_owned_file(project, monkeypatch):
    store, workspace, attention, _, _, _ = setup_reference(project, monkeypatch)
    before = store._path_for('project').read_bytes()
    count = len(workspace.sources)
    def fail(*args, **kwargs):
        raise OSError('Controlled disk write failure')
    monkeypatch.setattr(store, 'save', fail)
    with pytest.raises(OSError, match='disk'):
        store.retain_public_reference(workspace, 'reviewer', attention['id'], 'cib-sectors', 'Candidate investigation')
    assert store._path_for('project').read_bytes() == before and len(workspace.sources) == count
    assert not list((store.store_path/'workspace_sources'/'project').glob('*.bin'))


def test_evaluation_retains_explicit_boundary_and_source_admission_remains_reference_only(project, monkeypatch):
    store, workspace, attention, _, _, _ = setup_reference(project, monkeypatch, evaluation=True)
    result = store.retain_public_reference(workspace, 'reviewer', attention['id'], 'cib-sectors', 'Evaluation retrieval')['governed_result']
    assert result['evaluation_only'] and workspace.sources[-1]['evaluation_only']
    admission = store.admit_proposition(workspace, result['premise_ids'][0])
    assert admission['evaluation_only'] and not admission['admissible']


def test_post_commit_failure_never_removes_committed_original(project, monkeypatch):
    from pathlib import Path
    store, workspace, attention, _, raw, _ = setup_reference(project, monkeypatch)
    save = store.save
    def fail_after_commit(*args, **kwargs):
        save(*args, **kwargs)
        raise OSError('Controlled post-commit failure')
    monkeypatch.setattr(store, 'save', fail_after_commit)
    with pytest.raises(OSError, match='post-commit'):
        store.retain_public_reference(workspace, 'reviewer', attention['id'], 'cib-sectors', 'Candidate investigation')
    retained = store.get('project')
    assert Path(retained.sources[-1]['file_path']).read_bytes() == raw
    assert retained.analyses[-1]['governed_result']['state'] == 'UNRESOLVED'


def test_private_workspace_denies_route_before_retrieval(project, monkeypatch):
    store, workspace, attention, client, _, opener = setup_reference(project, monkeypatch)
    store.create_case(workspace, 'Private case', 'Private objective', created_by='another-owner')
    response = client.post('/projects/project/attention', data=dict(action='public_reference',
        analysis_id=attention['id'], source_key='cib-sectors', reason='Not authorized'))
    assert response.status_code == 403 and not opener.calls
