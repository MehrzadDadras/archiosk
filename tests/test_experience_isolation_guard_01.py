"""CLAUDE-EXPERIENCE-RECONCILIATION-01 - the Experience Corpus boundary, enforced.

ARCHIOSK's ratified position is that it may eventually learn *how to
investigate* without learning *what to believe*
(`governance/specified-unbuilt/cross-boundary-architecture.md`), and
`governance/STATUS.md` currently lists the Experience Corpus (all forms) as
**NOT AUTHORIZED - specified only**. CLAUDE.md is explicit that code
implementing something marked NOT AUTHORIZED is a defect.

That boundary was documented in three places and enforced in one. The import
isolation between quality ratings and the learning zones already has tests
(tests/test_learning_governance.py). What had no test was the claim those
records lean on hardest: that no cross-project retrieval mechanism exists, so
one project's material is structurally unable to reach another's reasoning.

These are absence guards. They are deliberately written to fail if someone
builds the NOT AUTHORIZED feature quietly, which is exactly the failure mode
the governance rule exists to catch - a documented boundary that nothing
checks is rhetoric, not architecture.

They assert no capability. They prove that a boundary still holds.
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
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

ROOT = Path(__file__).resolve().parents[1]

# Real retrieval-index libraries. Prose mentioning the word "embedding" is not
# a violation; a dependency on one of these would be.
_RETRIEVAL_LIBRARIES = (
    "faiss", "chromadb", "pinecone", "weaviate", "qdrant", "pgvector",
    "sentence_transformers", "sentence-transformers", "llama_index",
    "langchain", "annoy", "hnswlib", "usearch",
)


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class NoCrossProjectRetrievalIndexTests(unittest.TestCase):
    """The claim `services/learning_governance.py` states about itself."""

    def test_no_retrieval_index_dependency_is_declared(self):
        declared = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
        for library in _RETRIEVAL_LIBRARIES:
            with self.subTest(library=library):
                self.assertNotIn(library, declared)

    def test_no_retrieval_index_is_imported_by_the_application(self):
        for directory in ("services", "routes"):
            for path in (ROOT / directory).rglob("*.py"):
                text = path.read_text(encoding="utf-8", errors="ignore")
                for library in _RETRIEVAL_LIBRARIES:
                    with self.subTest(file=path.name, library=library):
                        self.assertNotIn(f"import {library}", text)
                        self.assertNotIn(f"from {library}", text)

    def test_the_learning_module_still_moves_nothing_between_zones(self):
        """Its own honesty boundary: approval tracking, never data transfer."""
        text = (ROOT / "services" / "learning_governance.py").read_text(encoding="utf-8")
        self.assertIn("no embedding index shared across projects", text)


class HistoricalSimilarityCannotBecomeEvidenceTests(unittest.TestCase):
    """The behavioural half: one project's content cannot surface in another.

    Written against the only cross-project surface that exists today - global
    search. If a retrieval mechanism is ever added, this is the test that
    should fail first.
    """

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_root = Path(tempfile.mkdtemp(prefix="beehive_test_expiso_"))
        self.tmp_dir = self.tmp_root / "registry"
        self.tmp_dir.mkdir()
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(
                username="exp_a", password_hash=generate_password_hash("x"), role="admin",
            ))
            db.session.commit()

        # A distinctive phrase that exists in exactly one project's evidence.
        self.secret = "smokecontrolcoordinationfailure" + uuid.uuid4().hex[:8]
        self.past = self._ingest(b"Lessons: " + self.secret.encode(), "past-project.txt", "Past Project")
        self.current = self._ingest(b"Unrelated current scope.", "current-project.txt", "Current Project")

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _ingest(self, content: bytes, filename: str, name: str):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(content, filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner="exp_a", project_name=name,
                )

    def _client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "exp_a"
            sess["role"] = "admin"
        return client

    def test_one_projects_content_is_not_retrievable_across_projects(self):
        """Even for a user authorized on BOTH projects: the cross-project
        surface matches identity, never document content, so a past project's
        lesson cannot arrive as material in another project."""
        response = self._client().get(f"/search?q={self.secret}")
        self.assertNotIn(self.secret, response.get_data(as_text=True))

    def test_the_two_projects_remain_separately_stored(self):
        """Isolation is structural - separate records, not a filtered view of
        one shared store."""
        self.assertNotEqual(self.past.project_id, self.current.project_id)
        files = {p.name for p in self.tmp_dir.glob("*.workspace.json")}
        self.assertIn(f"{self.past.project_id}.workspace.json", files)
        self.assertIn(f"{self.current.project_id}.workspace.json", files)

    def test_the_secret_never_reaches_the_other_projects_record(self):
        """Scan every file under the shared storage root and assert the phrase
        never appears in anything belonging to the OTHER project.

        Deliberately framed as the negative. Raw uploads are stored under their
        own storage id rather than the project id, so "every carrier is named
        for the owning project" is simply not how this layout works - asserting
        it would be testing a storage convention, not an isolation boundary.
        What matters is that nothing carrying one project's material is
        reachable as the other project's record.
        """
        carriers = [
            path for path in self.tmp_dir.rglob("*")
            if path.is_file() and self.secret in path.read_text(encoding="utf-8", errors="ignore")
        ]
        self.assertTrue(carriers, "fixture must actually plant the phrase somewhere")
        for path in carriers:
            with self.subTest(file=path.name):
                self.assertNotIn(self.current.project_id, path.name)

    def test_the_other_projects_workspace_record_is_clean(self):
        record = self.tmp_dir / f"{self.current.project_id}.workspace.json"
        self.assertNotIn(self.secret, record.read_text(encoding="utf-8"))


class ExperienceCorpusRemainsUnauthorizedTests(unittest.TestCase):
    """A guard on the authorization itself, not on any capability.

    If the Product Owner later authorizes the Experience Corpus, this test is
    the intended place to notice - it should be updated deliberately, as part
    of that authorization, rather than a feature appearing while the table
    still says otherwise.
    """

    def test_status_still_records_it_as_not_authorized(self):
        status = (ROOT / "governance" / "STATUS.md").read_text(encoding="utf-8")
        self.assertIn("Experience Corpus", status)
        row = next(
            line for line in status.splitlines()
            if "Experience Corpus" in line and "NOT AUTHORIZED" in line
        )
        self.assertIn("specified only", row)

    def test_the_governing_principle_is_still_recorded(self):
        text = (ROOT / "governance" / "specified-unbuilt" / "cross-boundary-architecture.md").read_text(encoding="utf-8")
        self.assertIn("learn how to investigate without learning what to believe", text)
        # The three constraints that make it a bounded distinction rather than
        # an unconditional licence.
        self.assertIn("outcome-valence stripped", text)
        self.assertIn("adversarial-party eligibility check", text)


if __name__ == "__main__":
    unittest.main()
