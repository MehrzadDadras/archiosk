"""CLAUDE-PERSPECTIVE-GATE-04 - the five-position project entry gate.

ARCHIOSK's entry model exposed only Client/Owner and Design-Builder/Proponent,
which stops the procurement chain well short of reality. The governing decision
(governance/specified-unbuilt/perspective-and-contract-dna.md) is REUSE
PERSPECTIVE + EXPLICIT RETAINED-BY, and explicitly not a separate
procurement_position concept.

What these tests hold:

  * all five positions can be declared, and they persist;
  * the upstream edge persists when supplied and may honestly stay unknown;
  * a position is never inferred, and never manufactures authority;
  * declaring a position changes no isolation semantics whatsoever;
  * a Trade or Subconsultant project is an independent project, never a
    participant row inside somebody else's;
  * projects created before this gate existed keep working.

Every ingestion call spies on BHiveParser.parse rather than letting it run for
real (repo-wide convention - no external boundary is reachable here).
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
from services.case_workspace import CaseWorkspaceError, CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER, DESIGN_BUILDER_PROPONENT
from services.governance import GovernanceLog
from services.ingestion import ingest_upload
from services.project_perspective import (
    ENTRY_CHOICES,
    ENTRY_CLIENT_OWNER,
    ENTRY_LEAD_DESIGN_CONSULTANT,
    ENTRY_PRIME_CONTRACTOR,
    ENTRY_SUBCONSULTANT,
    ENTRY_TRADE_BIDDER,
    KNOWN_PERSPECTIVES,
    PERSPECTIVE_CONSULTANT,
    PERSPECTIVE_CONTRACTOR,
    PERSPECTIVE_OWNER,
    RETAINED_BY_LEAD_CONSULTANT,
    RETAINED_BY_NOT_ESTABLISHED,
    RETAINED_BY_OWNER,
    RETAINED_BY_PRIME_CONTRACTOR,
    perspective_for_entry_choice,
)

ROOT = Path(__file__).resolve().parents[1]


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _GateCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_root = Path(tempfile.mkdtemp(prefix="beehive_test_gate04_"))
        self.tmp_dir = self.tmp_root / "registry"
        self.tmp_dir.mkdir()
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            for name, role in (("gate_a", "admin"), ("gate_b", "read_only")):
                db.session.add(User(
                    username=name, password_hash=generate_password_hash("x"), role=role,
                ))
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _log(self) -> GovernanceLog:
        return GovernanceLog(str(self.tmp_dir))

    def _ingest(self, owner="gate_a", name="Gate Project", environment=DESIGN_BUILDER_PROPONENT):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", "rfp.txt"), self.flask_app,
                    operating_environment=environment, owner=owner, project_name=name,
                )

    def _declare(self, project_id, entry_choice, retained_by=None, actor="gate_a"):
        store = self._store()
        with self.flask_app.app_context():
            return store.set_project_perspective(
                store.get(project_id), entry_choice=entry_choice, actor=actor,
                retained_by=retained_by, governance_log=self._log(),
            )


class AllFivePositionsWorkTests(_GateCase):
    def test_every_position_can_be_declared_and_persists(self):
        for choice in ENTRY_CHOICES:
            with self.subTest(position=choice):
                doc = self._ingest(name=f"Project {choice}")
                self._declare(doc.project_id, choice)
                # Re-read from a FRESH store: proves persistence, not memory.
                reloaded = self._store().get(doc.project_id)
                self.assertEqual(reloaded.entry_choice, choice)
                self.assertEqual(reloaded.perspective, perspective_for_entry_choice(choice))
                self.assertIn(reloaded.perspective, KNOWN_PERSPECTIVES)
                self.assertIsNotNone(reloaded.perspective_set_by)
                self.assertIsNotNone(reloaded.perspective_set_at)

    def test_positions_sharing_a_perspective_are_distinguished_by_the_upstream_edge(self):
        """Lead Consultant and Subconsultant are both the consultant position;
        Prime and Trade are both the contractor position. The edge separates
        them - which is the whole reason procurement_position was rejected."""
        lead = self._ingest(name="Lead")
        sub = self._ingest(name="Sub")
        self._declare(lead.project_id, ENTRY_LEAD_DESIGN_CONSULTANT, RETAINED_BY_OWNER)
        self._declare(sub.project_id, ENTRY_SUBCONSULTANT, RETAINED_BY_LEAD_CONSULTANT)

        store = self._store()
        lead_ws, sub_ws = store.get(lead.project_id), store.get(sub.project_id)
        self.assertEqual(lead_ws.perspective, sub_ws.perspective)
        self.assertEqual(lead_ws.perspective, PERSPECTIVE_CONSULTANT)
        self.assertNotEqual(lead_ws.retained_by, sub_ws.retained_by)

    def test_owner_is_the_apex_and_is_retained_by_no_one(self):
        doc = self._ingest(name="Owner project", environment=CLIENT_OWNER)
        self._declare(doc.project_id, ENTRY_CLIENT_OWNER)
        workspace = self._store().get(doc.project_id)
        self.assertEqual(workspace.perspective, PERSPECTIVE_OWNER)
        self.assertIsNone(workspace.retained_by)
        with self.assertRaises(CaseWorkspaceError):
            self._declare(doc.project_id, ENTRY_CLIENT_OWNER, RETAINED_BY_OWNER)


class UpstreamRelationshipTests(_GateCase):
    def test_relationship_persists_when_supplied(self):
        doc = self._ingest()
        self._declare(doc.project_id, ENTRY_TRADE_BIDDER, RETAINED_BY_PRIME_CONTRACTOR)
        workspace = self._store().get(doc.project_id)
        self.assertEqual(workspace.retained_by, RETAINED_BY_PRIME_CONTRACTOR)
        self.assertIsNotNone(workspace.retained_by_set_by)

    def test_relationship_may_stay_genuinely_unknown(self):
        """Unanswered and explicitly-not-established are different, and both
        honest. Neither is ever filled in by inference."""
        unanswered = self._ingest(name="Unanswered")
        declared = self._ingest(name="Declared unknown")
        self._declare(unanswered.project_id, ENTRY_TRADE_BIDDER)
        self._declare(declared.project_id, ENTRY_TRADE_BIDDER, RETAINED_BY_NOT_ESTABLISHED)

        store = self._store()
        self.assertIsNone(store.get(unanswered.project_id).retained_by)
        self.assertEqual(store.get(declared.project_id).retained_by, RETAINED_BY_NOT_ESTABLISHED)

    def test_a_relationship_from_another_position_is_refused(self):
        """A trade bidder is not retained by a lead design consultant."""
        doc = self._ingest()
        with self.assertRaises(CaseWorkspaceError):
            self._declare(doc.project_id, ENTRY_TRADE_BIDDER, RETAINED_BY_LEAD_CONSULTANT)

    def test_nothing_is_inferred_from_the_documents(self):
        """A project that never declares a position simply has none."""
        doc = self._ingest()
        workspace = self._store().get(doc.project_id)
        self.assertIsNone(workspace.perspective)
        self.assertIsNone(workspace.entry_choice)
        self.assertIsNone(workspace.retained_by)


class PositionIsContextNotAuthorityTests(_GateCase):
    def test_declaring_a_position_creates_no_contractual_state(self):
        doc = self._ingest()
        before = self._store().get(doc.project_id)
        before_counts = (
            len(before.requirements), len(before.findings), len(before.cases),
            len(before.relationships), len(before.sources),
        )
        self._declare(doc.project_id, ENTRY_PRIME_CONTRACTOR, RETAINED_BY_OWNER)
        after = self._store().get(doc.project_id)
        self.assertEqual(
            (len(after.requirements), len(after.findings), len(after.cases),
             len(after.relationships), len(after.sources)),
            before_counts,
        )

    def test_it_does_not_touch_the_operating_environment(self):
        """A different axis entirely - and that one stays locked."""
        doc = self._ingest(environment=DESIGN_BUILDER_PROPONENT)
        self._declare(doc.project_id, ENTRY_TRADE_BIDDER)
        self.assertEqual(
            self._store().get(doc.project_id).operating_environment, DESIGN_BUILDER_PROPONENT,
        )

    def test_it_selects_no_contract_form(self):
        """Entry context does not select Contract/Delivery DNA."""
        doc = self._ingest()
        self._declare(doc.project_id, ENTRY_TRADE_BIDDER, RETAINED_BY_PRIME_CONTRACTOR)
        workspace = self._store().get(doc.project_id)
        blob = repr(workspace.__dict__).lower()
        for form in ("ccdc", "cca 1", "cca1", "raic", "acec"):
            with self.subTest(form=form):
                self.assertNotIn(form, blob)

    def test_the_declaration_is_a_governed_event(self):
        doc = self._ingest()
        self._declare(doc.project_id, ENTRY_SUBCONSULTANT, RETAINED_BY_LEAD_CONSULTANT)
        with self.flask_app.app_context():
            events = self._log().read(doc.project_id)
        kinds = [e.event_type for e in events]
        self.assertIn("project_perspective_established", kinds)

    def test_it_is_correctable_and_preserves_the_previous_value(self):
        """Perspective is working context, not project truth, so it is not
        locked - but the change is recorded rather than overwritten."""
        doc = self._ingest()
        self._declare(doc.project_id, ENTRY_PRIME_CONTRACTOR, RETAINED_BY_OWNER)
        self._declare(doc.project_id, ENTRY_TRADE_BIDDER, RETAINED_BY_PRIME_CONTRACTOR)
        workspace = self._store().get(doc.project_id)
        self.assertEqual(workspace.entry_choice, ENTRY_TRADE_BIDDER)
        with self.flask_app.app_context():
            events = [e for e in self._log().read(doc.project_id)
                      if e.event_type == "project_perspective_established"]
        self.assertEqual(len(events), 2)
        self.assertEqual(events[-1].payload["previous_perspective"], PERSPECTIVE_CONTRACTOR)


class IsolationIsUnchangedTests(_GateCase):
    def test_a_trade_project_is_independent_of_its_gc_project(self):
        gc = self._ingest(owner="gate_a", name="GC project")
        trade = self._ingest(owner="gate_b", name="Trade project")
        self._declare(gc.project_id, ENTRY_PRIME_CONTRACTOR, RETAINED_BY_OWNER, actor="gate_a")
        self._declare(trade.project_id, ENTRY_TRADE_BIDDER, RETAINED_BY_PRIME_CONTRACTOR, actor="gate_b")

        from services.project_access import can_access_project

        store = self._store()
        self.assertFalse(can_access_project(store.get(gc.project_id), "gate_b", False))
        self.assertFalse(can_access_project(store.get(trade.project_id), "gate_a", False))

    def test_competing_trades_declaring_the_same_upstream_share_nothing(self):
        """Naming the same upstream party creates no shared state."""
        a = self._ingest(owner="gate_a", name="Trade A")
        b = self._ingest(owner="gate_b", name="Trade B")
        self._declare(a.project_id, ENTRY_TRADE_BIDDER, RETAINED_BY_PRIME_CONTRACTOR, actor="gate_a")
        self._declare(b.project_id, ENTRY_TRADE_BIDDER, RETAINED_BY_PRIME_CONTRACTOR, actor="gate_b")

        store = self._store()
        ws_a, ws_b = store.get(a.project_id), store.get(b.project_id)
        self.assertNotEqual(ws_a.project_id, ws_b.project_id)
        self.assertEqual(ws_a.retained_by, ws_b.retained_by)
        self.assertNotEqual(ws_a.owner, ws_b.owner)
        self.assertNotEqual([s["id"] for s in ws_a.sources], [s["id"] for s in ws_b.sources])

    def test_no_participant_row_is_created_in_another_project(self):
        """A Trade project is not a participant inside its GC's project."""
        gc = self._ingest(owner="gate_a", name="GC")
        trade = self._ingest(owner="gate_b", name="Trade")
        gc_before = len(self._store().get(gc.project_id).participants)
        self._declare(trade.project_id, ENTRY_TRADE_BIDDER, RETAINED_BY_PRIME_CONTRACTOR, actor="gate_b")

        store = self._store()
        self.assertEqual(len(store.get(gc.project_id).participants), gc_before)
        self.assertEqual(len(store.get(trade.project_id).participants), 0)


class LegacyProjectsKeepWorkingTests(_GateCase):
    def test_a_project_created_before_this_gate_still_loads_and_is_usable(self):
        doc = self._ingest(environment=CLIENT_OWNER, name="Legacy")
        workspace = self._store().get(doc.project_id)
        # Undeclared is the legacy state, and it is honest rather than broken.
        self.assertIsNone(workspace.perspective)
        self.assertEqual(workspace.operating_environment, CLIENT_OWNER)
        self.assertTrue(workspace.sources)

    def test_a_legacy_project_can_declare_a_position_later(self):
        doc = self._ingest(environment=CLIENT_OWNER, name="Legacy then declared")
        self._declare(doc.project_id, ENTRY_CLIENT_OWNER)
        self.assertEqual(self._store().get(doc.project_id).perspective, PERSPECTIVE_OWNER)


class EntryGateSurfaceTests(_GateCase):
    def _admin_client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "gate_a"
            sess["role"] = "admin"
        return client

    def test_all_five_positions_are_offered(self):
        body = self._admin_client().get("/upload").get_data(as_text=True)
        for choice in ENTRY_CHOICES:
            with self.subTest(position=choice):
                self.assertIn(f'upload.entry-choice.{choice}', body)

    def test_the_redundant_environment_question_is_gone(self):
        """CLAUDE-ENTRY-REDUNDANCY-01: it asked the same thing twice, in the
        same words. The environment is derived from the declared position now -
        removed as a user decision, preserved as an internal distinction."""
        body = self._admin_client().get("/upload").get_data(as_text=True)
        for env in (CLIENT_OWNER, DESIGN_BUILDER_PROPONENT):
            with self.subTest(environment=env):
                self.assertNotIn(f'upload.operating-environment.{env}', body)
        self.assertNotIn("Project Operating Environment", body)

    def test_no_architecture_vocabulary_reaches_the_user(self):
        """The system carries the sophistication; the user should not have to."""
        body = self._admin_client().get("/upload").get_data(as_text=True).lower()
        for term in ("contract dna", "retained-by graph", "referencestandard",
                     "procurement_position", "perspective object"):
            with self.subTest(term=term):
                self.assertNotIn(term, body)

    def test_no_contract_form_names_appear_on_the_gate(self):
        body = self._admin_client().get("/upload").get_data(as_text=True).lower()
        for form in ("ccdc", "raic", "acec", "cca 1"):
            with self.subTest(form=form):
                self.assertNotIn(form, body)


class NoProcurementPositionConceptTests(_GateCase):
    def test_the_rejected_field_was_not_implemented(self):
        for path in ("services/case_workspace.py", "services/project_perspective.py",
                     "routes/portal.py"):
            with self.subTest(file=path):
                self.assertNotIn(
                    "procurement_position", (ROOT / path).read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
