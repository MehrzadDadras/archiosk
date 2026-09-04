"""Focused source-domain coverage for Establish a Project."""
from __future__ import annotations

import io
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    SOURCE_DOMAIN_CLIENT_ISSUED,
    SOURCE_DOMAIN_EXTERNAL_REFERENCE,
    SOURCE_DOMAIN_TEAM_WORKSPACE,
    SOURCE_DOMAIN_UNKNOWN,
    CaseWorkspaceStore,
    source_domain_of,
)
from services.conversational_turn import gather_project_evidence
from services.environment_capabilities import DESIGN_BUILDER_PROPONENT
from services.ingestion import ingest_folder_upload


def _file(text: str, name: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(text.encode()), filename=name)


def _fake_parse(_parser, _raw_bytes, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
    )


@pytest.fixture()
def domain_app(tmp_path):
    import app as app_module
    from models import User, db

    application = app_module.create_app("testing")
    application.config["REGISTRY_STORE_PATH"] = str(tmp_path)
    with application.app_context():
        db.session.add(User(username="domain_admin", password_hash=generate_password_hash("x"), role="admin"))
        db.session.commit()
    return application


def test_establish_project_renders_three_source_domains_and_safe_single_file_fallback(domain_app):
    client = domain_app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1, username="domain_admin", role="admin")
    body = client.get("/upload").get_data(as_text=True)
    for text in (
        "Connect Client Data Room", "Connect Your Workspace", "Add External References",
    ):
        assert text in body
    for removed in ("CLIENT / OWNER INFORMATION", "YOUR WORKSPACE", "EXTERNAL REFERENCES"):
        assert removed not in body
    assert '<input type="hidden" name="source_domain" value="UNKNOWN">' in body
    assert 'id="single-file-source-domain"' not in body
    assert 'name="folder_source_domain"' in body


@pytest.mark.parametrize("domain", [
    SOURCE_DOMAIN_CLIENT_ISSUED,
    SOURCE_DOMAIN_TEAM_WORKSPACE,
    SOURCE_DOMAIN_EXTERNAL_REFERENCE,
])
def test_folder_sources_retain_explicit_domain_without_gaining_authority(domain_app, domain):
    with domain_app.app_context(), patch.object(BHiveParser, "parse", _fake_parse):
        document, results = ingest_folder_upload(
            files=[_file("Founding content", "RFP.txt"), _file("Working content", "notes.txt")],
            relative_paths=["Package/RFP.txt", "Package/notes.txt"], founding_index=0,
            app=domain_app, operating_environment=DESIGN_BUILDER_PROPONENT,
            owner="domain_admin", project_name=f"Domain {domain}", source_domain=domain,
        )
    assert results[0]["status"] == "added"
    workspace = CaseWorkspaceStore(domain_app.config["REGISTRY_STORE_PATH"]).get(document.project_id)
    assert {source["source_domain"] for source in workspace.sources} == {domain}
    assert all(source.get("document_authority") is None for source in workspace.sources)


def test_source_domain_survives_existing_evidence_provenance_projection(domain_app):
    with domain_app.app_context(), patch.object(BHiveParser, "parse", _fake_parse):
        document, _results = ingest_folder_upload(
            files=[_file("Founding content", "RFP.txt"), _file("Team coordination", "coordination.txt")],
            relative_paths=["Team/RFP.txt", "Team/coordination.txt"], founding_index=0,
            app=domain_app, operating_environment=DESIGN_BUILDER_PROPONENT,
            owner="domain_admin", project_name="Team Evidence", source_domain=SOURCE_DOMAIN_TEAM_WORKSPACE,
        )
    store = CaseWorkspaceStore(domain_app.config["REGISTRY_STORE_PATH"])
    evidence = gather_project_evidence(store.get(document.project_id), store)
    assert evidence.additional_document_evidence[0]["source_domain"] == SOURCE_DOMAIN_TEAM_WORKSPACE


def test_legacy_source_without_domain_loads_as_unknown(tmp_path):
    store = CaseWorkspaceStore(tmp_path)
    workspace = store.get_or_create("legacy-project")
    store.add_source(workspace, name="legacy.txt", file_path="legacy.txt", kind="project_document")
    workspace.sources[0].pop("source_domain")
    store.save(workspace)
    reloaded = store.get("legacy-project")
    assert "source_domain" not in reloaded.sources[0]
    assert source_domain_of(reloaded.sources[0]) == SOURCE_DOMAIN_UNKNOWN


def test_prime_role_keeps_all_domains_and_only_selected_engagement_control_active():
    template = (Path(__file__).resolve().parents[1] / "templates" / "upload.html").read_text(encoding="utf-8")
    assert 'value="{{ choice.value }}"' in template
    assert "prime_contractor" in (
        Path(__file__).resolve().parents[1] / "services" / "project_perspective.py"
    ).read_text(encoding="utf-8")
    assert template.count("data-folder-picker-button") == 4  # three controls plus the JS selector
    assert "group.hidden = !active" in template
    assert "select.disabled = !active" in template
    assert 'data-for-choice="{{ choice.value }}" hidden' in template
    assert 'data-ui-ref="upload.retained-by.{{ choice.value }}" disabled' in template
    assert "sourceDomainField.value = pendingSourceDomain" in template
    assert "domainLabels[pendingSourceDomain]" in template
    assert template.index("</form>") < template.index("group.hidden = !active")
