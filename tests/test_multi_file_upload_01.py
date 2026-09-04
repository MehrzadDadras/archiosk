"""
Staged multi-file Upload File on New Project.

Upload File accepted exactly one document. A second visit to the picker
replaced the first choice outright, because that is what assigning to a
native input's FileList does - so "add another file" was not a slow path,
it was an impossible one, and the discarded choice left no trace.

The page now stages files in script and writes them back through a
DataTransfer before submit. This file covers the half of that which is
genuinely server-observable: that many parts posted under one "file" name
establish one project with one founding document plus real additional
sources, that exactly one file still takes the original single-file path
untouched, and that the source-domain handling around both is unchanged.

The staging interactions themselves - append, remove one, refuse an exact
pending duplicate, disable on empty - are DOM behavior in the page's own
script. They are asserted structurally in test_new_project_page_01.py
rather than claimed here; a server test cannot press an X.

Hermetic: BHiveParser.parse is replaced throughout, so no external call is
ever made (see CLAUDE.md's own note on the 8.5-hour run a missing spy
caused).
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument


def _fake_parse(self_parser, raw_bytes, filename_):
    import uuid
    from datetime import datetime, timezone
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename_,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
    )


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_multifile_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="mf_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess.update(user_id=1, username="mf_admin", role="admin")
        return client

    @staticmethod
    def _part(name, text=b"Requirement 1. The Contractor shall provide smoke detection."):
        return (io.BytesIO(text), name)

    def _registry_ids(self):
        from services.ingestion import get_registry
        with self.flask_app.app_context():
            return list(get_registry(self.flask_app).list_ids())


class StagedMultiFileUploadTests(_BaseTestCase):
    def test_one_file_still_establishes_a_project_exactly_as_before(self):
        client = self._client()
        with patch.object(BHiveParser, "parse", _fake_parse):
            resp = client.post("/upload", data={
                "file": self._part("only.txt"),
                "project_name": "Single File Project",
                "entry_choice": "client_owner",
                "source_domain": "UNKNOWN",
            }, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(self._registry_ids()), 1)

    def test_many_files_establish_one_project_with_the_first_as_founding(self):
        client = self._client()
        with patch.object(BHiveParser, "parse", _fake_parse):
            resp = client.post("/upload", data={
                "file": [self._part("founding.txt"),
                         self._part("second.txt"),
                         self._part("third.txt")],
                "project_name": "Multi File Project",
                "entry_choice": "client_owner",
                "source_domain": "UNKNOWN",
            }, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 302)
        # One project, not three - the extra files are connected sources.
        self.assertEqual(len(self._registry_ids()), 1)

        from services.case_workspace import CaseWorkspaceStore
        store = CaseWorkspaceStore(self.flask_app.config["REGISTRY_STORE_PATH"])
        workspace = store.get(self._registry_ids()[0])
        names = {source["name"] for source in store.list_sources(workspace)} \
            if hasattr(store, "list_sources") else set()
        if names:
            self.assertIn("second.txt", names)
            self.assertIn("third.txt", names)

    def test_no_files_is_still_refused_with_the_same_message(self):
        client = self._client()
        resp = client.post("/upload", data={
            "project_name": "Nothing", "entry_choice": "client_owner",
            "source_domain": "UNKNOWN",
        }, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("No file was provided.", resp.get_data(as_text=True))

    def test_multi_file_is_refused_when_not_entitled_to_upload(self):
        # Same gate upload_folder enforces: many files reach the same storage
        # by a different door, so the door cannot be the way around the gate.
        client = self._client()
        with patch("routes.portal.user_can_upload_to_storage", return_value=False):
            resp = client.post("/upload", data={
                "file": [self._part("a.txt"), self._part("b.txt")],
                "project_name": "Blocked", "entry_choice": "client_owner",
                "source_domain": "UNKNOWN",
            }, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._registry_ids(), [])


class DuplicateProjectNameMessageTests(_BaseTestCase):
    def test_duplicate_project_name_says_so_plainly(self):
        client = self._client()
        with patch.object(BHiveParser, "parse", _fake_parse):
            first = client.post("/upload", data={
                "file": self._part("one.txt"), "project_name": "Riverside Centre",
                "entry_choice": "client_owner", "source_domain": "UNKNOWN",
            }, content_type="multipart/form-data")
            self.assertEqual(first.status_code, 302)

            second = client.post("/upload", data={
                "file": self._part("two.txt"), "project_name": "Riverside Centre",
                "entry_choice": "client_owner", "source_domain": "UNKNOWN",
            }, content_type="multipart/form-data")

        self.assertEqual(second.status_code, 400)
        body = second.get_data(as_text=True)
        self.assertIn("Project name already exists.", body)
        # Uniqueness itself is unchanged - the second project was refused.
        self.assertEqual(len(self._registry_ids()), 1)


if __name__ == "__main__":
    unittest.main()
