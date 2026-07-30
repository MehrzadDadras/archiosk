"""
CLAUDE-P28: forward-ingestion metadata gaps confirmed real by repository
investigation (not just assumed from the prompt) -- parser_version was
never stamped on ParsedDocument at all, and original_file_hash was
already computed on every ingestion but never actually checked against
anything. Also covers _reject_if_name_taken (CLAUDE-P28 investigation
found this rule real and enforced, but with no dedicated test of its
own anywhere in the suite).

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import BHIVE_PARSER_VERSION
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import UploadError, ingest_upload
from services.requirements_registry import RequirementsRegistry


class ParserVersionStampingTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_parser_version_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_new_ingestion_is_stamped_with_the_current_parser_version(self):
        file_storage = _fake_file(b"Contractor shall comply with applicable ASTM specifications.\n", "sample.txt")
        with self.flask_app.app_context():
            document = ingest_upload(file_storage, self.flask_app, operating_environment=CLIENT_OWNER, owner="fwd_test_owner")
        self.assertEqual(document.parser_version, BHIVE_PARSER_VERSION)

    def test_legacy_document_without_parser_version_key_loads_as_none(self):
        # Same idiom as tests/test_foundation_batch_h.py's Test Q -- a
        # hand-written pre-P28 JSON record with no "parser_version" key
        # at all must load with parser_version=None, never fabricated.
        registry = RequirementsRegistry(self.tmp_dir)
        legacy_data = {
            "project_id": "legacy-project-p28",
            "filename": "old.txt",
            "ingested_at": "2020-01-01T00:00:00+00:00",
            "requirements": [],
            "milestones": [],
            "tables": [],
            "consistency_flags": [],
            "consistency_checked": False,
            "consistency_note": None,
        }
        (self.tmp_dir / "legacy-project-p28.json").write_text(json.dumps(legacy_data), encoding="utf-8")

        document = registry.get("legacy-project-p28")
        self.assertIsNone(document.parser_version)


class DuplicateContentDetectionTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_dup_content_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_identical_content_is_flagged_in_the_governance_log_not_blocked(self):
        from services.ingestion import get_governance_log

        content = b"Contractor shall comply with applicable ASTM specifications.\n"
        with self.flask_app.app_context():
            first = ingest_upload(_fake_file(content, "first.txt"), self.flask_app, operating_environment=CLIENT_OWNER, owner="fwd_test_owner", project_name="First Project")
            second = ingest_upload(_fake_file(content, "second.txt"), self.flask_app, operating_environment=CLIENT_OWNER, owner="fwd_test_owner", project_name="Second Project")

            # Not blocked -- both projects exist, this is informational only.
            self.assertNotEqual(first.project_id, second.project_id)

            events = get_governance_log(self.flask_app).read(second.project_id)
            ingest_event = next(e for e in events if e.event_type == "document_ingested")
            self.assertEqual(ingest_event.payload["duplicate_of_project_id"], first.project_id)

    def test_distinct_content_is_not_flagged_as_duplicate(self):
        from services.ingestion import get_governance_log

        with self.flask_app.app_context():
            ingest_upload(_fake_file(b"First document content.\n", "first.txt"), self.flask_app, operating_environment=CLIENT_OWNER, owner="fwd_test_owner", project_name="First")
            second = ingest_upload(_fake_file(b"Entirely different content.\n", "second.txt"), self.flask_app, operating_environment=CLIENT_OWNER, owner="fwd_test_owner", project_name="Second")

            events = get_governance_log(self.flask_app).read(second.project_id)
            ingest_event = next(e for e in events if e.event_type == "document_ingested")
            self.assertIsNone(ingest_event.payload["duplicate_of_project_id"])


class ProjectNameUniquenessTests(unittest.TestCase):
    """CLAUDE-P28 investigation confirmed _reject_if_name_taken is real and
    enforced (services/ingestion.py, checked before parsing even starts)
    but had no dedicated test anywhere in the suite."""

    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_name_uniqueness_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_duplicate_project_name_is_rejected(self):
        with self.flask_app.app_context():
            ingest_upload(_fake_file(b"First content.\n", "a.txt"), self.flask_app, operating_environment=CLIENT_OWNER, owner="fwd_test_owner", project_name="Same Name")
            with self.assertRaises(UploadError):
                ingest_upload(_fake_file(b"Different content.\n", "b.txt"), self.flask_app, operating_environment=CLIENT_OWNER, owner="fwd_test_owner", project_name="Same Name")

    def test_distinct_project_names_both_succeed(self):
        with self.flask_app.app_context():
            first = ingest_upload(_fake_file(b"First content.\n", "a.txt"), self.flask_app, operating_environment=CLIENT_OWNER, owner="fwd_test_owner", project_name="Name One")
            second = ingest_upload(_fake_file(b"Second content.\n", "b.txt"), self.flask_app, operating_environment=CLIENT_OWNER, owner="fwd_test_owner", project_name="Name Two")
        self.assertNotEqual(first.project_id, second.project_id)


def _fake_file(content: bytes, filename: str):
    from werkzeug.datastructures import FileStorage

    return FileStorage(stream=io.BytesIO(content), filename=filename)


if __name__ == "__main__":
    unittest.main()
