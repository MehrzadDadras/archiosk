"""
CLAUDE-POSTCAMEL-COMM-I5A - OPR-5.3 corrective tranche.

`RequirementAdjudication`'s own class docstring has always called it
"the first-class record of a human's answer", but nothing on the
object ever enforced or even recorded that - a username
(`adjudicator`) says who/what account performed the write, never
whether the judgment itself was personally formed by a human. This
tranche adds a real, closed-vocabulary `attribution` field
(`human_reviewed`/`agent_assessment`), makes it a mandatory, explicit,
never-defaulted choice at the real product route
(`adjudicate_requirement`), and provides a read-time-only resolver
(`resolve_requirement_adjudication_attribution`) for the four
COMM-I3 legacy records that predate the field - without mutating them,
per ADR-032-R06's append-only, never-overwrite principle.

Run via:

    python -m unittest tests.test_comm_i5a_adjudication_attribution -v
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    ADJUDICATION_ATTRIBUTION_AGENT_ASSESSMENT,
    ADJUDICATION_ATTRIBUTION_HUMAN_REVIEWED,
    ADJUDICATION_ATTRIBUTION_UNKNOWN_LEGACY,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    LEGACY_AGENT_ATTRIBUTED_ADJUDICATION_IDS,
    REQUIREMENT_ADJUDICATION_SATISFIED,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    resolve_requirement_adjudication_attribution,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


# ---------------------------------------------------------------------------
# Store-layer
# ---------------------------------------------------------------------------

class AdjudicationAttributionStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_comm_i5a_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project_id = "comm-i5a-project"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _requirement(self, workspace):
        path = self.tmp_dir / "spec.txt"
        path.write_text("Widgets shall be blue.", encoding="utf-8")
        source = self.store.add_source(
            workspace, name="spec.txt", file_path=str(path), kind="project_document", actor="tester",
        )
        return self.store.register_requirement(
            workspace, source_id=source["id"], original_requirement_identifier="SPEC-1",
            text_reference="Widgets shall be blue.", created_by="tester",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )

    def test_human_origin_adjudication_provenance(self):
        workspace = self.store.get_or_create(self.project_id)
        requirement = self._requirement(workspace)
        record = self.store.record_requirement_adjudication(
            workspace, requirement_id=requirement["id"], outcome=REQUIREMENT_ADJUDICATION_SATISFIED,
            adjudicator="a_real_person", reasoning="I personally reviewed the evidence.",
            attribution=ADJUDICATION_ATTRIBUTION_HUMAN_REVIEWED,
        )
        self.assertEqual(record["attribution"], ADJUDICATION_ATTRIBUTION_HUMAN_REVIEWED)
        self.assertEqual(
            resolve_requirement_adjudication_attribution(record), ADJUDICATION_ATTRIBUTION_HUMAN_REVIEWED,
        )

    def test_agent_origin_adjudication_provenance(self):
        workspace = self.store.get_or_create(self.project_id)
        requirement = self._requirement(workspace)
        record = self.store.record_requirement_adjudication(
            workspace, requirement_id=requirement["id"], outcome=REQUIREMENT_ADJUDICATION_SATISFIED,
            adjudicator="archiosk_commissioning", reasoning="Repository-grounded agent assessment.",
            attribution=ADJUDICATION_ATTRIBUTION_AGENT_ASSESSMENT,
        )
        self.assertEqual(record["attribution"], ADJUDICATION_ATTRIBUTION_AGENT_ASSESSMENT)
        self.assertEqual(
            resolve_requirement_adjudication_attribution(record), ADJUDICATION_ATTRIBUTION_AGENT_ASSESSMENT,
        )

    def test_invalid_attribution_value_is_rejected(self):
        """The store's own closed vocabulary is the second line of
        defense against a fictional attribution value, beneath the
        route's own mandatory-choice enforcement."""
        workspace = self.store.get_or_create(self.project_id)
        requirement = self._requirement(workspace)
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_requirement_adjudication(
                workspace, requirement_id=requirement["id"], outcome=REQUIREMENT_ADJUDICATION_SATISFIED,
                adjudicator="tester", reasoning="x", attribution="definitely_a_real_human_i_promise",
            )

    def test_omitted_attribution_stays_backward_compatible_and_resolves_unknown(self):
        """Every pre-existing direct caller of record_requirement_adjudication
        (six test files predate this field) must keep working unchanged."""
        workspace = self.store.get_or_create(self.project_id)
        requirement = self._requirement(workspace)
        record = self.store.record_requirement_adjudication(
            workspace, requirement_id=requirement["id"], outcome=REQUIREMENT_ADJUDICATION_SATISFIED,
            adjudicator="tester", reasoning="pre-existing caller shape, no attribution kwarg",
        )
        self.assertIsNone(record["attribution"])
        self.assertEqual(
            resolve_requirement_adjudication_attribution(record), ADJUDICATION_ATTRIBUTION_UNKNOWN_LEGACY,
        )

    def test_known_legacy_comm_i3_ids_resolve_to_agent_assessment_without_mutation(self):
        """The four real COMM-I3 ids, referenced by the fixed constant -
        never guessed, never applied to any other record."""
        for legacy_id in LEGACY_AGENT_ATTRIBUTED_ADJUDICATION_IDS:
            fabricated_pre_field_record = {"id": legacy_id, "attribution": None}
            self.assertEqual(
                resolve_requirement_adjudication_attribution(fabricated_pre_field_record),
                ADJUDICATION_ATTRIBUTION_AGENT_ASSESSMENT,
            )
        self.assertEqual(len(LEGACY_AGENT_ATTRIBUTED_ADJUDICATION_IDS), 4)

    def test_unrelated_legacy_record_never_mislabeled_as_agent(self):
        record = {"id": "some-other-id-not-in-the-legacy-set", "attribution": None}
        self.assertEqual(
            resolve_requirement_adjudication_attribution(record), ADJUDICATION_ATTRIBUTION_UNKNOWN_LEGACY,
        )

    def test_append_only_history_and_latest_resolution_human_supersedes_agent_in_effect(self):
        workspace = self.store.get_or_create(self.project_id)
        requirement = self._requirement(workspace)

        agent_record = self.store.record_requirement_adjudication(
            workspace, requirement_id=requirement["id"], outcome=REQUIREMENT_ADJUDICATION_SATISFIED,
            adjudicator="archiosk_commissioning", reasoning="Agent assessment.",
            attribution=ADJUDICATION_ATTRIBUTION_AGENT_ASSESSMENT,
        )
        human_record = self.store.record_requirement_adjudication(
            workspace, requirement_id=requirement["id"], outcome=REQUIREMENT_ADJUDICATION_SATISFIED,
            adjudicator="a_real_person", reasoning="Personally confirmed after review.",
            attribution=ADJUDICATION_ATTRIBUTION_HUMAN_REVIEWED,
        )

        history = self.store.requirement_adjudications_for(workspace, requirement["id"])
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["id"], agent_record["id"])
        self.assertEqual(history[1]["id"], human_record["id"])

        latest = self.store.latest_requirement_adjudication_for(workspace, requirement["id"])
        self.assertEqual(latest["id"], human_record["id"])
        self.assertEqual(
            resolve_requirement_adjudication_attribution(latest), ADJUDICATION_ATTRIBUTION_HUMAN_REVIEWED,
        )


# ---------------------------------------------------------------------------
# Route-layer: mandatory choice, no self-declared fiction, UI representation
# ---------------------------------------------------------------------------

class AdjudicateRequirementRouteTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_comm_i5a_route_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="i5a_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="i5a_owner", project_name="COMM-I5A Attribution Test Project")
        self.project_id = self.doc.project_id

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str = "founding.txt"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"founding content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "i5a_owner"
            sess["role"] = "admin"
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _register_requirement(self, client) -> str:
        resp = client.post(
            f"/projects/{self.project_id}/workspace/sources/document",
            data={"document": _fake_file(b"Widgets shall be blue.", "spec.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 302)
        workspace = self._store().get(self.project_id)
        source_id = next(s["id"] for s in workspace.sources if s["name"] == "spec.txt")

        resp = client.post(
            f"/projects/{self.project_id}/workspace/requirements/register",
            data={
                "source_id": source_id,
                "original_requirement_identifier": "SPEC-1",
                "text_reference": "Widgets shall be blue.",
            },
        )
        self.assertEqual(resp.status_code, 302)
        workspace = self._store().get(self.project_id)
        return next(r["id"] for r in workspace.requirements if r["original_requirement_identifier"] == "SPEC-1")

    def test_missing_attribution_is_rejected_no_record_created(self):
        client = self._client()
        requirement_id = self._register_requirement(client)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/requirements/{requirement_id}/adjudicate",
            data={"outcome": "Satisfied", "reasoning": "no attribution supplied"},
        )
        self.assertEqual(resp.status_code, 302)
        workspace = self._store().get(self.project_id)
        self.assertEqual(len(workspace.requirement_adjudications), 0)

    def test_arbitrary_self_declared_attribution_value_is_rejected(self):
        """The server must not accept provenance as a self-declared
        fiction outside the two real, closed choices."""
        client = self._client()
        requirement_id = self._register_requirement(client)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/requirements/{requirement_id}/adjudicate",
            data={"outcome": "Satisfied", "reasoning": "x", "attribution": "definitely_human_trust_me"},
        )
        self.assertEqual(resp.status_code, 302)
        workspace = self._store().get(self.project_id)
        self.assertEqual(len(workspace.requirement_adjudications), 0)

    def test_agent_assessment_attribution_succeeds_and_renders_labeled(self):
        client = self._client()
        requirement_id = self._register_requirement(client)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/requirements/{requirement_id}/adjudicate",
            data={"outcome": "Satisfied", "reasoning": "Agent assessment.", "attribution": "agent_assessment"},
        )
        self.assertEqual(resp.status_code, 302)
        workspace = self._store().get(self.project_id)
        self.assertEqual(len(workspace.requirement_adjudications), 1)
        self.assertEqual(workspace.requirement_adjudications[0]["attribution"], "agent_assessment")

        body = client.get(f"/projects/{self.project_id}/workspace?view=requirements").get_data(as_text=True)
        self.assertIn("Agent assessment", body)

    def test_human_reviewed_attribution_succeeds_and_supersedes_agent_assessment_in_effect(self):
        client = self._client()
        requirement_id = self._register_requirement(client)

        client.post(
            f"/projects/{self.project_id}/workspace/requirements/{requirement_id}/adjudicate",
            data={"outcome": "Satisfied", "reasoning": "Agent assessment.", "attribution": "agent_assessment"},
        )
        resp = client.post(
            f"/projects/{self.project_id}/workspace/requirements/{requirement_id}/adjudicate",
            data={"outcome": "Satisfied", "reasoning": "Personally confirmed.", "attribution": "human_reviewed"},
        )
        self.assertEqual(resp.status_code, 302)

        workspace = self._store().get(self.project_id)
        # append-only: both records preserved, never deleted or overwritten
        self.assertEqual(len(workspace.requirement_adjudications), 2)
        store = self._store()
        latest = store.latest_requirement_adjudication_for(workspace, requirement_id)
        self.assertEqual(latest["attribution"], "human_reviewed")

        body = client.get(f"/projects/{self.project_id}/workspace?view=requirements").get_data(as_text=True)
        self.assertIn("Human-reviewed", body)
        # history disclosure (2 entries) still shows the superseded agent one too
        self.assertIn("Agent assessment", body)


if __name__ == "__main__":
    unittest.main()
