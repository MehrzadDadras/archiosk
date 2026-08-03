"""
CLAUDE-P40-VW8-QA - Project-Creation Upload-Capacity Correction.

A product-owner walkthrough hit Werkzeug's raw, unstyled default
"Request Entity Too Large" page while creating a Project from a real
document - MAX_UPLOAD_MB (25MB) was too small for a real procurement
RFP/RFQ/spec PDF, and nothing app-level ever caught RequestEntityTooLarge
outside routes/api.py's own JSON-only handler (routes/portal.py's real
upload FORM had no equivalent).

Diagnosis (see this stage's own CONTINUATION_CHECKPOINT.md entry for
the full writeup): the ONLY enforcing layer reachable in this dev/test
environment is Flask's MAX_CONTENT_LENGTH (config.py, sourced from
MAX_UPLOAD_MB); deploy/nginx.conf's client_max_body_size is a second,
production-only layer kept in sync by convention, not exercised here.
Because Werkzeug's form parser raises RequestEntityTooLarge BEFORE
routes/portal.py:upload's view function ever runs, a rejected request
never reaches services/ingestion.py:ingest_upload at all - no Project,
Document, workspace, or temp file is ever created for it. This file
verifies that directly (not merely asserts it in prose) by checking
registry/workspace_sources state before and after a 413.

Uses a small MAX_CONTENT_LENGTH override (not the real 60MB) so the
boundary/over-limit cases stay fast - the mechanism under test
(Werkzeug's own enforcement + app.py's error handler) doesn't care
what the actual number is.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.environment_capabilities import CLIENT_OWNER


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


def _fake_parse(self_parser, raw_bytes, filename_):
    import uuid
    from datetime import datetime, timezone
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename_,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
    )


_TEST_MAX_MB = 1
_TEST_MAX_BYTES = _TEST_MAX_MB * 1024 * 1024


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw8qa_upload_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["MAX_CONTENT_LENGTH"] = _TEST_MAX_BYTES

        with self.flask_app.app_context():
            db.session.add(User(username="vw8qa_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="vw8qa_reader", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _registry_project_count(self) -> int:
        from services.ingestion import get_registry
        with self.flask_app.app_context():
            return len(get_registry(self.flask_app).list_ids())

    def _workspace_sources_dir(self) -> Path:
        return self.tmp_dir / "workspace_sources"

    def _upload_data(self, size_bytes, filename="rfp.pdf", project_name=None, environment=CLIENT_OWNER):
        data = {
            "operating_environment": environment,
            "file": (io.BytesIO(b"x" * size_bytes), filename),
        }
        if project_name:
            data["project_name"] = project_name
        return data


class BoundaryBehaviorTests(_BaseTestCase):
    def test_a_file_safely_below_the_limit_is_accepted(self):
        client = self._client_as("vw8qa_admin", 1)
        with patch.object(BHiveParser, "parse", _fake_parse):
            resp = client.post(
                "/upload",
                data=self._upload_data(1024, project_name="Small File Project"),
                content_type="multipart/form-data",
            )
        self.assertEqual(resp.status_code, 302, resp.get_data(as_text=True)[:500])
        self.assertEqual(self._registry_project_count(), 1)

    def test_a_file_just_under_the_boundary_is_accepted(self):
        # Werkzeug's own MAX_CONTENT_LENGTH check applies to the WHOLE
        # request body, not just the file field - multipart encoding
        # (boundary markers, field headers, the other form fields this
        # request also carries) adds real overhead on top of the file's
        # own byte count, so "at the boundary" is tested with enough
        # margin to stay net-under the limit despite that overhead,
        # not the file size exactly equal to MAX_CONTENT_LENGTH.
        margin = 4096
        client = self._client_as("vw8qa_admin", 1)
        with patch.object(BHiveParser, "parse", _fake_parse):
            resp = client.post(
                "/upload",
                data=self._upload_data(_TEST_MAX_BYTES - margin, project_name="Boundary Project"),
                content_type="multipart/form-data",
            )
        self.assertEqual(resp.status_code, 302, resp.get_data(as_text=True)[:500])
        self.assertEqual(self._registry_project_count(), 1)

    def test_a_file_above_the_limit_is_rejected_with_413(self):
        client = self._client_as("vw8qa_admin", 1)
        resp = client.post(
            "/upload",
            data=self._upload_data(_TEST_MAX_BYTES + (500 * 1024), project_name="Too Big Project"),
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 413)


class CustomPresentationTests(_BaseTestCase):
    def test_413_response_is_archiosk_styled_not_the_raw_werkzeug_page(self):
        client = self._client_as("vw8qa_admin", 1)
        resp = client.post(
            "/upload",
            data=self._upload_data(_TEST_MAX_BYTES + (500 * 1024)),
            content_type="multipart/form-data",
        )
        body = resp.get_data(as_text=True)
        # Werkzeug's own raw default page contains this exact phrase and
        # nothing of Archiosk's - its absence, plus the app chrome's
        # presence, is what proves the styled page rendered instead.
        self.assertNotIn("<title>413 Request Entity Too Large</title>", body)
        self.assertIn("File too large", body)
        self.assertIn("Archiosk", body)

    def test_413_message_states_the_actual_configured_limit(self):
        client = self._client_as("vw8qa_admin", 1)
        resp = client.post(
            "/upload",
            data=self._upload_data(_TEST_MAX_BYTES + (500 * 1024)),
            content_type="multipart/form-data",
        )
        body = resp.get_data(as_text=True)
        self.assertIn(f"{_TEST_MAX_MB}MB", body)

    def test_413_page_offers_a_return_action_back_to_upload(self):
        client = self._client_as("vw8qa_admin", 1)
        resp = client.post(
            "/upload",
            data=self._upload_data(_TEST_MAX_BYTES + (500 * 1024)),
            content_type="multipart/form-data",
        )
        body = resp.get_data(as_text=True)
        self.assertIn('href="/upload"', body)

    def test_413_page_never_exposes_paths_or_internals(self):
        client = self._client_as("vw8qa_admin", 1)
        resp = client.post(
            "/upload",
            data=self._upload_data(_TEST_MAX_BYTES + (500 * 1024)),
            content_type="multipart/form-data",
        )
        body = resp.get_data(as_text=True)
        self.assertNotIn(str(self.tmp_dir), body)
        self.assertNotIn("Traceback (most recent call last)", body)

    def test_413_action_link_carries_its_ui_reference(self):
        client = self._client_as("vw8qa_admin", 1)
        resp = client.post(
            "/upload",
            data=self._upload_data(_TEST_MAX_BYTES + (500 * 1024)),
            content_type="multipart/form-data",
        )
        body = resp.get_data(as_text=True)
        self.assertIn('data-ui-ref="errors.upload-too-large"', body)

    def test_api_ingest_413_still_returns_json_not_html(self):
        # routes/api.py's own blueprint-scoped RequestEntityTooLarge
        # handler must still win for /api/v1/* specifically - the new
        # app-level HTML handler must not shadow it.
        client = self._client_as("vw8qa_admin", 1)
        resp = client.post(
            "/api/v1/documents/ingest",
            data={"operating_environment": CLIENT_OWNER, "file": (io.BytesIO(b"x" * (_TEST_MAX_BYTES + 1024)), "rfp.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 413)
        self.assertEqual(resp.get_json()["error"], "file_too_large")


class TransactionalSafetyTests(_BaseTestCase):
    def test_no_project_is_created_by_a_rejected_upload(self):
        client = self._client_as("vw8qa_admin", 1)
        self.assertEqual(self._registry_project_count(), 0)
        client.post(
            "/upload",
            data=self._upload_data(_TEST_MAX_BYTES + (500 * 1024), project_name="Rejected Project"),
            content_type="multipart/form-data",
        )
        self.assertEqual(self._registry_project_count(), 0)

    def test_no_workspace_sources_directory_is_created_by_a_rejected_upload(self):
        client = self._client_as("vw8qa_admin", 1)
        client.post(
            "/upload",
            data=self._upload_data(_TEST_MAX_BYTES + (500 * 1024)),
            content_type="multipart/form-data",
        )
        # ingest_upload only ever creates this directory AFTER a
        # successful parse - a request that never reached that function
        # must leave the registry store's own tree untouched beyond
        # whatever create_app("testing") itself initializes.
        sources_dir = self._workspace_sources_dir()
        if sources_dir.exists():
            self.assertEqual(list(sources_dir.iterdir()), [])

    def test_project_name_is_still_available_for_a_retry_after_rejection(self):
        # A rejected (too-large) upload must not "burn" the requested
        # project name via _reject_if_name_taken - retrying with a
        # smaller file under the same name must succeed.
        client = self._client_as("vw8qa_admin", 1)
        client.post(
            "/upload",
            data=self._upload_data(_TEST_MAX_BYTES + (500 * 1024), project_name="Retry Project"),
            content_type="multipart/form-data",
        )
        with patch.object(BHiveParser, "parse", _fake_parse):
            resp = client.post(
                "/upload",
                data=self._upload_data(1024, project_name="Retry Project"),
                content_type="multipart/form-data",
            )
        self.assertEqual(resp.status_code, 302, resp.get_data(as_text=True)[:500])
        self.assertEqual(self._registry_project_count(), 1)


class AuthorizationPreservedTests(_BaseTestCase):
    def test_a_non_admin_still_cannot_reach_upload_regardless_of_file_size(self):
        client = self._client_as("vw8qa_reader", 2, role="read_only")
        resp = client.post(
            "/upload",
            data=self._upload_data(_TEST_MAX_BYTES + (500 * 1024)),
            content_type="multipart/form-data",
        )
        # @admin_required must still win - a read-only session gets
        # redirected/forbidden, never a 413 that would otherwise leak
        # "yes, this route exists and processes uploads" to a caller
        # who was never allowed to reach it in the first place.
        self.assertNotEqual(resp.status_code, 413)
        self.assertIn(resp.status_code, (302, 403))

    def test_an_unauthenticated_request_still_cannot_reach_upload(self):
        client = self.flask_app.test_client()
        resp = client.post(
            "/upload",
            data=self._upload_data(_TEST_MAX_BYTES + (500 * 1024)),
            content_type="multipart/form-data",
        )
        self.assertNotEqual(resp.status_code, 413)
        self.assertEqual(resp.status_code, 302)


class UploadFormPresentationTests(_BaseTestCase):
    def test_upload_form_states_the_configured_limit_before_any_file_is_chosen(self):
        client = self._client_as("vw8qa_admin", 1)
        body = client.get("/upload").get_data(as_text=True)
        self.assertIn(f"Maximum size {_TEST_MAX_MB}MB", body)

    def test_upload_form_states_accepted_formats(self):
        client = self._client_as("vw8qa_admin", 1)
        body = client.get("/upload").get_data(as_text=True)
        for fmt in ("PDF", "DOCX", "TXT", "CSV", "MD"):
            self.assertIn(fmt, body)

    def test_file_input_carries_the_client_side_size_budget(self):
        client = self._client_as("vw8qa_admin", 1)
        body = client.get("/upload").get_data(as_text=True)
        self.assertIn(f'data-max-upload-bytes="{_TEST_MAX_BYTES}"', body)
        self.assertIn(f'data-max-upload-mb="{_TEST_MAX_MB}"', body)

    def test_client_side_size_check_script_is_present(self):
        client = self._client_as("vw8qa_admin", 1)
        body = client.get("/upload").get_data(as_text=True)
        self.assertIn("upload-size-error", body)
        self.assertIn("checkSize", body)

    def test_upload_form_controls_carry_ui_references(self):
        client = self._client_as("vw8qa_admin", 1)
        body = client.get("/upload").get_data(as_text=True)
        for ref in (
            "upload.limits", "upload.file", "upload.project-name",
            "upload.submit", "upload.operating-environment.client_owner",
            "upload.operating-environment.design_builder_proponent",
        ):
            self.assertIn(f'data-ui-ref="{ref}"', body)


class FileTypeValidationTests(_BaseTestCase):
    def test_supported_file_type_under_the_limit_is_accepted(self):
        client = self._client_as("vw8qa_admin", 1)
        with patch.object(BHiveParser, "parse", _fake_parse):
            resp = client.post(
                "/upload",
                data=self._upload_data(1024, filename="spec.docx", project_name="Docx Project"),
                content_type="multipart/form-data",
            )
        self.assertEqual(resp.status_code, 302, resp.get_data(as_text=True)[:500])

    def test_unsupported_file_type_under_the_limit_is_still_rejected_by_ingestion(self):
        client = self._client_as("vw8qa_admin", 1)
        resp = client.post(
            "/upload",
            data=self._upload_data(1024, filename="drawing.dwg", project_name="Unsupported Type Project"),
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unsupported file type", resp.get_data(as_text=True))
        self.assertEqual(self._registry_project_count(), 0)


if __name__ == "__main__":
    unittest.main()
