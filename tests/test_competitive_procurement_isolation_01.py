"""AUD-ENTRY-01A-1 - identical procurement evidence, fully isolated projects.

The real procurement shape this protects: one Owner-issued tender reaches
several competing GCs, and one GC-issued trade package reaches several
competing trades. Each independently ingests byte-identical evidence into
its own private ARCHIOSK project. That is normal and must keep working -
and no bidder may learn from it that a competitor exists.

Before this repair, `ingest_upload` wrote the matching project's id into
the NEW project's own `document_ingested` governance payload, which
`GET /api/v1/documents/<project_id>/governance` returns verbatim to any
authorized member of that project.

Constitutional invariant #8 already governs: no project's governed truth
transfers into another's operative state "regardless of shared client,
company, or physical asset." Identical content is exactly such a shared
asset; these tests prove it is not a channel.

Hermetic: `BHiveParser.parse` is replaced with a deterministic fake, per
CLAUDE.md's standing rule for any path that can reach an external
boundary.
"""
import io
import json
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from app import create_app
from services.bhive_parser import BHiveParser, ParsedDocument
from services.environment_capabilities import CLIENT_OWNER, DESIGN_BUILDER_PROPONENT
from services.ingestion import get_governance_log, get_registry, ingest_upload

# The one issued document every party in the chain receives, byte-identical.
ISSUED_TENDER = b"OWNER-ISSUED TENDER\nSection 1. Scope of Work.\nSection 2. Submission.\n"


def _fake_parse(self, raw_bytes, filename):
    """The established hermetic pattern (see tests/test_security_enforcement.py):
    a plain ParsedDocument, never the real extract/classify/consistency
    pipeline, so no test here can reach a live API."""
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
    )


def _upload(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.app = create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self._patcher = patch.object(BHiveParser, "parse", _fake_parse)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ingest(self, project_name, owner, environment=DESIGN_BUILDER_PROPONENT,
                content=ISSUED_TENDER, filename="Owner-Issued-RFP.txt"):
        return ingest_upload(
            _upload(content, filename), self.app,
            operating_environment=environment, owner=owner, project_name=project_name,
        )

    def _payload_text(self, project_id):
        """Everything this project's own authorized member can read from
        its governance trail - the exact surface the API returns."""
        events = get_governance_log(self.app).read(project_id)
        return json.dumps([e.__dict__ for e in events], default=str)


class CompetingGeneralContractorTests(_Base):
    """The same Owner-issued tender seeds three independent GC bid projects."""

    def test_three_competing_gcs_ingest_identical_tender_in_full_isolation(self):
        with self.app.app_context():
            gc_a = self._ingest("GC A Bid", "gc_a_user")
            gc_b = self._ingest("GC B Bid", "gc_b_user")
            gc_c = self._ingest("GC C Bid", "gc_c_user")

            ids = {gc_a.project_id, gc_b.project_id, gc_c.project_id}
            self.assertEqual(len(ids), 3, "each bidder must get its own project")

            # C - identical evidence really is present in all three.
            for doc in (gc_a, gc_b, gc_c):
                self.assertEqual(doc.original_file_hash, gc_a.original_file_hash)

            # A - and no project's readable trail names any other.
            for mine, others in (
                (gc_a, (gc_b, gc_c)), (gc_b, (gc_a, gc_c)), (gc_c, (gc_a, gc_b)),
            ):
                readable = self._payload_text(mine.project_id)
                for other in others:
                    with self.subTest(mine=mine.project_id[:8], other=other.project_id[:8]):
                        self.assertNotIn(other.project_id, readable)

    def test_no_duplicate_key_survives_anywhere_in_the_readable_trail(self):
        with self.app.app_context():
            self._ingest("GC A Bid", "gc_a_user")
            gc_b = self._ingest("GC B Bid", "gc_b_user")
            self.assertNotIn("duplicate_of_project_id", self._payload_text(gc_b.project_id))


class CompetingTradeTests(_Base):
    """The same GC-issued trade package seeds independent trade bid projects."""

    def test_competing_trades_ingest_identical_package_in_full_isolation(self):
        package = b"MECHANICAL PACKAGE 23\nScope: HVAC.\nSubmit pricing.\n"
        with self.app.app_context():
            t1 = self._ingest("Trade 1 Bid", "trade_1_user", content=package,
                              filename="Mech-Package-23.txt")
            t2 = self._ingest("Trade 2 Bid", "trade_2_user", content=package,
                              filename="Mech-Package-23.txt")
            t3 = self._ingest("Trade 3 Bid", "trade_3_user", content=package,
                              filename="Mech-Package-23.txt")

            self.assertEqual(len({t1.project_id, t2.project_id, t3.project_id}), 3)
            for mine, others in ((t1, (t2, t3)), (t2, (t1, t3)), (t3, (t1, t2))):
                readable = self._payload_text(mine.project_id)
                for other in others:
                    with self.subTest(mine=mine.project_id[:8]):
                        self.assertNotIn(other.project_id, readable)


class OwnerToGeneralContractorTests(_Base):
    """The Owner's own project must not learn who imported its tender."""

    def test_owner_project_never_names_a_downstream_bidder(self):
        with self.app.app_context():
            owner = self._ingest("Owner Tender", "owner_user", environment=CLIENT_OWNER)
            gc = self._ingest("GC Bid", "gc_user")

            self.assertNotIn(gc.project_id, self._payload_text(owner.project_id))
            self.assertNotIn(owner.project_id, self._payload_text(gc.project_id))


class NoCrossProjectAuthorityTests(_Base):
    """E - duplicate detection creates no membership, permission or link."""

    def test_duplicate_ingestion_creates_no_shared_state_or_authority(self):
        from services.case_workspace import CaseWorkspaceStore

        with self.app.app_context():
            first = self._ingest("First Bid", "first_user")
            second = self._ingest("Second Bid", "second_user")

            store = CaseWorkspaceStore(Path(self.app.config["REGISTRY_STORE_PATH"]))
            ws_a = store.get_or_create(first.project_id)
            ws_b = store.get_or_create(second.project_id)

            # No membership was manufactured from shared content.
            self.assertEqual(ws_a.owner, "first_user")
            self.assertEqual(ws_b.owner, "second_user")
            self.assertNotIn("second_user", ws_a.access_allow_list)
            self.assertNotIn("first_user", ws_b.access_allow_list)

            # No cross-project relationship, claim or finding, and every
            # in-project record stays stamped with its OWN project. A
            # SourceReference IS legitimately created at ingestion (the
            # declared-reference extractor finds "Section 1" in the text);
            # what matters is that it is project-scoped, not that it is
            # absent.
            for ws, foreign in ((ws_a, second.project_id), (ws_b, first.project_id)):
                with self.subTest(project=ws.project_id[:8]):
                    self.assertEqual(ws.relationships, [])
                    self.assertEqual(ws.claims, [])
                    self.assertEqual(ws.findings, [])
                    for record in (*ws.sources, *ws.source_references):
                        self.assertEqual(record["project_id"], ws.project_id)
                        self.assertNotIn(foreign, json.dumps(record, default=str))

    def test_each_project_keeps_its_own_source_records(self):
        with self.app.app_context():
            from services.case_workspace import CaseWorkspaceStore

            first = self._ingest("First Bid", "first_user")
            second = self._ingest("Second Bid", "second_user")
            store = CaseWorkspaceStore(Path(self.app.config["REGISTRY_STORE_PATH"]))

            a_ids = {s["id"] for s in store.get_or_create(first.project_id).sources}
            b_ids = {s["id"] for s in store.get_or_create(second.project_id).sources}
            self.assertTrue(a_ids and b_ids, "each project registers its own Source")
            self.assertFalse(a_ids & b_ids, "no Source record is shared between projects")


class DuplicateMetadataNeverReachesCognitionTests(_Base):
    """D - nothing about duplication enters the evidence handed to a model."""

    def test_project_evidence_contains_no_foreign_project_identifier(self):
        from services.case_workspace import CaseWorkspaceStore
        from services.conversational_turn import gather_project_evidence

        with self.app.app_context():
            first = self._ingest("First Bid", "first_user")
            second = self._ingest("Second Bid", "second_user")
            store = CaseWorkspaceStore(Path(self.app.config["REGISTRY_STORE_PATH"]))

            evidence = gather_project_evidence(store.get_or_create(second.project_id), store)
            serialized = json.dumps(evidence, default=lambda o: getattr(o, "__dict__", str(o)))
            self.assertNotIn(first.project_id, serialized)
            self.assertNotIn("duplicate_of_project_id", serialized)


if __name__ == "__main__":
    unittest.main()
