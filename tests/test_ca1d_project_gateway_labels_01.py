"""
CLAUDE-CA1D-PROJECT-GATEWAY-LABELS-01 - Separate Role from New/Existing
State.

Covers the Project Gateway restructure from three flat cards (Create
Client/Owner, Create Design-Builder/Proponent, Open an existing
project) into two context groups -- Client/Owner Projects and Design-
Builder/Proponent Projects -- each offering New Project and Open
Existing Project, plus the new optional `?environment=` filter on
routes/portal.py's choose_project that makes "Open Existing Project"
actually scoped to the right context.

Every ingestion call spies on BHiveParser.parse rather than letting it
run for real (existing repo-wide convention).

Run via:

    python -m unittest discover -s tests -v
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
from services.environment_capabilities import CLIENT_OWNER, DESIGN_BUILDER_PROPONENT
from services.ingestion import ingest_upload


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseGatewayLabelsTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_root = Path(tempfile.mkdtemp(prefix="beehive_test_gateway_labels_"))
        self.tmp_dir = self.tmp_root / "registry"
        self.tmp_dir.mkdir()
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="gl_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="gl_reviewer", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, environment: str, filename: str = "rfp.txt"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", filename), self.flask_app,
                    operating_environment=environment, owner=owner, project_name=project_name,
                )

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client


class GatewayContextGroupTests(_BaseGatewayLabelsTestCase):
    def test_two_context_groups_present_not_three_flat_cards(self):
        client = self._client_as("gl_admin", 1)
        body = client.get("/gateway").get_data(as_text=True)
        self.assertIn("Client / Owner Projects", body)
        self.assertIn("Design-Builder / Proponent Projects", body)
        # The old flat, environment-agnostic entrance is gone.
        self.assertNotIn('data-ui-ref="gateway.open-existing"', body)
        self.assertNotIn(">Open an existing project<", body)

    def test_each_context_group_offers_new_and_open_existing_for_admin(self):
        client = self._client_as("gl_admin", 1)
        body = client.get("/gateway").get_data(as_text=True)
        self.assertIn('data-ui-ref="gateway.create-client-owner"', body)
        self.assertIn('data-ui-ref="gateway.open-existing-client-owner"', body)
        self.assertIn('data-ui-ref="gateway.create-design-builder"', body)
        self.assertIn('data-ui-ref="gateway.open-existing-design-builder"', body)

    def test_new_project_hidden_from_non_admin_but_open_existing_still_shown(self):
        client = self._client_as("gl_reviewer", 2, role="read_only")
        body = client.get("/gateway").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="gateway.create-client-owner"', body)
        self.assertNotIn('data-ui-ref="gateway.create-design-builder"', body)
        self.assertIn('data-ui-ref="gateway.open-existing-client-owner"', body)
        self.assertIn('data-ui-ref="gateway.open-existing-design-builder"', body)

    def test_new_project_links_still_deep_link_the_correct_environment(self):
        client = self._client_as("gl_admin", 1)
        body = client.get("/gateway").get_data(as_text=True)
        self.assertIn('href="/upload?environment=client_owner"', body)
        self.assertIn('href="/upload?environment=design_builder_proponent"', body)

    def test_open_existing_reveals_inline_not_a_link_to_the_chooser(self):
        """CLAUDE-CA1D-GATEWAY-INLINE-REOPEN-01: a PO correction removed
        the extra transition through `portal.choose_project` - "Open
        Existing Project" now reveals that context's own Projects
        inline (a `<details>` disclosure), never a navigating `<a>`."""
        client = self._client_as("gl_admin", 1)
        body = client.get("/gateway").get_data(as_text=True)
        self.assertNotIn('href="/projects/choose?environment=client_owner"', body)
        self.assertNotIn('href="/projects/choose?environment=design_builder_proponent"', body)
        self.assertIn('data-ui-ref="gateway.open-existing-client-owner"', body)
        self.assertIn('data-ui-ref="gateway.open-existing-design-builder"', body)

    def test_open_existing_shows_each_groups_own_projects_inline(self):
        self._ingest(owner="gl_admin", project_name="Riverside Client Project", environment=CLIENT_OWNER)
        self._ingest(owner="gl_admin", project_name="Riverside Bidder Project", environment=DESIGN_BUILDER_PROPONENT)
        client = self._client_as("gl_admin", 1)
        body = client.get("/gateway").get_data(as_text=True)
        self.assertIn("Riverside Client Project", body)
        self.assertIn("Riverside Bidder Project", body)
        # A real selection, not a bare link - the same select-then-confirm
        # pattern gateway.chooser itself already uses.
        self.assertIn('data-ui-ref="gateway.open-existing-client-owner.leaf"', body)
        self.assertIn('data-ui-ref="gateway.open-existing-design-builder.leaf"', body)

    def test_open_existing_empty_state_per_context_group(self):
        client = self._client_as("gl_admin", 1)
        body = client.get("/gateway").get_data(as_text=True)
        self.assertIn("No Client / Owner projects yet.", body)
        self.assertIn("No Design-Builder / Proponent projects yet.", body)


class ChooseProjectEnvironmentFilterTests(_BaseGatewayLabelsTestCase):
    def test_client_owner_filter_shows_only_client_owner_projects(self):
        self._ingest(owner="gl_admin", project_name="Riverside Client Project", environment=CLIENT_OWNER)
        self._ingest(owner="gl_admin", project_name="Riverside Bidder Project", environment=DESIGN_BUILDER_PROPONENT)
        client = self._client_as("gl_admin", 1)
        body = client.get("/projects/choose?environment=client_owner").get_data(as_text=True)
        self.assertIn("Riverside Client Project", body)
        self.assertNotIn("Riverside Bidder Project", body)

    def test_design_builder_filter_shows_only_design_builder_projects(self):
        self._ingest(owner="gl_admin", project_name="Riverside Client Project", environment=CLIENT_OWNER)
        self._ingest(owner="gl_admin", project_name="Riverside Bidder Project", environment=DESIGN_BUILDER_PROPONENT)
        client = self._client_as("gl_admin", 1)
        body = client.get("/projects/choose?environment=design_builder_proponent").get_data(as_text=True)
        self.assertIn("Riverside Bidder Project", body)
        self.assertNotIn("Riverside Client Project", body)

    def test_no_filter_shows_both(self):
        self._ingest(owner="gl_admin", project_name="Riverside Client Project", environment=CLIENT_OWNER)
        self._ingest(owner="gl_admin", project_name="Riverside Bidder Project", environment=DESIGN_BUILDER_PROPONENT)
        client = self._client_as("gl_admin", 1)
        body = client.get("/projects/choose").get_data(as_text=True)
        self.assertIn("Riverside Client Project", body)
        self.assertIn("Riverside Bidder Project", body)

    def test_invalid_environment_value_falls_back_to_unfiltered_not_an_error(self):
        self._ingest(owner="gl_admin", project_name="Riverside Client Project", environment=CLIENT_OWNER)
        client = self._client_as("gl_admin", 1)
        resp = client.get("/projects/choose?environment=not-a-real-environment")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Riverside Client Project", resp.get_data(as_text=True))

    def test_heading_names_the_environment_context_when_filtered(self):
        client = self._client_as("gl_admin", 1)
        body = client.get("/projects/choose?environment=client_owner").get_data(as_text=True)
        self.assertIn("Open an existing Client / Owner project", body)
        body_unfiltered = client.get("/projects/choose").get_data(as_text=True)
        self.assertIn(">Open an existing project<", body_unfiltered)

    def test_search_form_preserves_environment_filter_across_searches(self):
        client = self._client_as("gl_admin", 1)
        body = client.get("/projects/choose?environment=client_owner").get_data(as_text=True)
        self.assertIn('name="environment" value="client_owner"', body)

    def test_zero_state_new_project_link_carries_the_environment_filter(self):
        client = self._client_as("gl_admin", 1)
        body = client.get("/projects/choose?environment=client_owner").get_data(as_text=True)
        self.assertIn("No Client / Owner projects yet.", body)
        self.assertIn('href="/upload?environment=client_owner"', body)

    def test_access_control_still_scoped_to_accessible_documents_when_filtered(self):
        """Section: 'preserve access control and project isolation' -
        an outsider must not see a Project they aren't authorized for,
        even when it matches the requested environment filter."""
        self._ingest(owner="gl_admin", project_name="Private Client Project", environment=CLIENT_OWNER)
        outsider = self._client_as("gl_outsider", 3, role="read_only")
        body = outsider.get("/projects/choose?environment=client_owner").get_data(as_text=True)
        self.assertNotIn("Private Client Project", body)


if __name__ == "__main__":
    unittest.main()
