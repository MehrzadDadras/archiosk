"""CLAUDE-BLACK-BOX-D2-01: vocabulary follows the operating context.

SHARED KERNEL DOES NOT MEAN SHARED USER-FACING VOCABULARY.

A Black Box reuses ProjectWorkspace and therefore inherited a page that offered
to classify its operating environment, asked who the reader represents in "this
Project", and invited them to add Project Parties - every one of which is a fact
the container has deliberately refused to hold.

Three tests carry the weight:

`test_a_black_box_is_never_invited_to_declare_an_engagement` - the harm is the
INVITATION, not the noun. A label reads oddly; a form to classify an operating
environment on a container that has none is an offer to do something incoherent.

`test_a_conventional_project_keeps_every_word` - the regression this must not
cause. RIGHT LANGUAGE AT THE RIGHT LEVEL, never "make everything generic".

`test_presentation_keys_on_container_state_only` - the wrong mechanism, refused.
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

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    CONTAINER_STATE_BLACK_BOX, CaseWorkspaceStore, SOURCE_KIND_UNCLASSIFIED,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import UploadError, ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent

#: Every engagement-shaped offer the shared page used to make unconditionally.
ENGAGEMENT_OFFERS = (
    "Project Operating Environment",
    "who you represent in this Project",
    "Add Project Party",
    "Participants &amp; Perspective",
    "Go / No-Go",
    "Project Instructions",
    "Project Briefing",
    "Project Management &amp; Settings",
    "Project State",
)


def _fake_parse(_parser, _raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test")


class PresentationTests(unittest.TestCase):

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_d2_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)

        self.project = self._ingest("rfp.pdf", operating_environment=CLIENT_OWNER,
                                    project_name="A Real Project")
        self.black_box = self._ingest(
            "notes.txt", operating_environment=None,
            container_state=CONTAINER_STATE_BLACK_BOX,
            project_name="A Shop Job")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ingest(self, name, **kwargs):
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                return ingest_upload(
                    FileStorage(stream=io.BytesIO(b"x"), filename=name),
                    self.app, owner="owner", **kwargs)

    def _client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "owner"
            session["role"] = "admin"
        return client

    def _overview(self, document):
        return self._client().get(
            "/projects/%s/workspace?view=overview" % document.project_id
        ).get_data(as_text=True)

    # -- the Black Box surface -----------------------------------------------

    def test_a_black_box_is_never_invited_to_declare_an_engagement(self):
        body = self._overview(self.black_box)
        for offer in ENGAGEMENT_OFFERS:
            with self.subTest(offer=offer):
                self.assertNotIn(offer, body)

    def test_a_black_box_carries_document_shop_identity(self):
        body = self._overview(self.black_box)
        self.assertIn("Document Shop", body)
        self.assertNotIn("Black Box", body,
                         "the container state is internal vocabulary")

    def test_the_as_read_bench_carries_no_project_vocabulary(self):
        """The bench was already clean, and this asserts it stays that way.

        Written first to assert it said "Document Context", on the assumption
        that base.html's topbar renders here. It does not - the Project Context
        control is absent from this surface entirely, which is why the original
        audit measured zero project vocabulary on it. The assertion is what was
        actually true, not what was assumed.
        """
        workspace = self.store.get(self.black_box.project_id)
        source_id = workspace.sources[0]["id"]
        body = self._client().get(
            "/projects/%s/workspace/sources/%s/understanding"
            % (self.black_box.project_id, source_id)).get_data(as_text=True)
        self.assertNotIn("Project Context", body)
        for offer in ENGAGEMENT_OFFERS:
            with self.subTest(offer=offer):
                self.assertNotIn(offer, body)

    def test_navigation_does_not_route_a_black_box_into_project_setup(self):
        body = self._overview(self.black_box)
        for setup in ("classify_operating_environment",
                      "set_represented_party_route",
                      "correct_operating_environment"):
            with self.subTest(route=setup):
                self.assertNotIn(setup, body)

    # -- the conventional Project, untouched ---------------------------------

    def test_a_conventional_project_keeps_every_word(self):
        body = self._overview(self.project)
        for offer in ENGAGEMENT_OFFERS:
            with self.subTest(offer=offer):
                self.assertIn(offer, body,
                              "Project language must not be genericized")

    def test_a_conventional_project_keeps_project_context(self):
        body = self._overview(self.project)
        self.assertIn("Project Context", body)
        self.assertIn("Edit Project Details", body)

    def test_a_legacy_project_without_container_state_keeps_project_wording(self):
        workspace = self.store.get(self.project.project_id)
        workspace.operating_environment = None
        self.store.save(workspace)
        body = self._overview(self.project)
        self.assertIn("Project State", body)
        self.assertIn("Project Context", body)

    # -- the mechanism -------------------------------------------------------

    def test_presentation_keys_on_container_state_only(self):
        """Source.kind must not decide vocabulary.

        A conventional Project may hold unclassified sources (D1), and a Black
        Box may later hold classified ones. Deciding presentation from a
        document's type would repeat the assumption class this whole sequence
        has been removing.
        """
        workspace = self.store.get(self.project.project_id)
        for source in workspace.sources:
            source["kind"] = SOURCE_KIND_UNCLASSIFIED
        self.store.save(workspace)
        body = self._overview(self.project)
        self.assertIn("Project State", body,
                      "unclassified sources must not restyle a Project")

    def test_the_route_reads_container_state_and_nothing_else(self):
        source = (_REPO_ROOT / "routes" / "workspace.py").read_text(encoding="utf-8")
        window = source[source.index("document_shop_container=("):]
        window = window[:window.index(")") + 1]
        self.assertIn("container_state", window)
        for wrong in ("kind", "source_domain", "operating_environment",
                      "project_id", "endswith"):
            with self.subTest(axis=wrong):
                self.assertNotIn(wrong, window)

    # -- neutral upload wording ----------------------------------------------

    def test_founding_refusal_is_context_neutral(self):
        with self.assertRaises(UploadError) as caught:
            self._ingest("schedule.xlsx", operating_environment=None,
                         container_state=CONTAINER_STATE_BLACK_BOX,
                         project_name="BB xlsx")
        message = str(caught.exception)
        self.assertNotIn("project", message.lower())
        self.assertIn("founding document", message)

    def test_duplicate_name_refusal_is_context_neutral(self):
        with self.assertRaises(UploadError) as caught:
            self._ingest("other.txt", operating_environment=None,
                         container_state=CONTAINER_STATE_BLACK_BOX,
                         project_name="A Shop Job")
        self.assertNotIn("project", str(caught.exception).lower())

    def test_missing_owner_refusal_is_context_neutral(self):
        source = (_REPO_ROOT / "services" / "ingestion.py").read_text(encoding="utf-8")
        self.assertIn('UploadError("An authenticated owner is required.")', source)
        self.assertNotIn("A project owner (the authenticated uploader)", source)

    def test_one_message_serves_both_paths(self):
        """No route-specific duplicate error strings were introduced."""
        source = (_REPO_ROOT / "services" / "ingestion.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("That name is already in use."), 1)
        self.assertEqual(source.count("cannot be used as a founding document"), 1)

    # -- what D2 deliberately did NOT do -------------------------------------

    def test_name_uniqueness_is_still_deployment_wide(self):
        """Wording changed; the RULE did not. Still a Product Owner decision."""
        source = (_REPO_ROOT / "services" / "ingestion.py").read_text(encoding="utf-8")
        window = source[source.index("def _reject_if_name_taken"):]
        window = window[:window.index("def reject_if_display_name_taken")]
        self.assertIn("registry.list_ids()", window)
        self.assertNotIn("owner", window,
                         "scoping names per owner is a separate decision")

    def test_internal_names_were_not_renamed(self):
        kernel = (_REPO_ROOT / "services" / "case_workspace.py").read_text(encoding="utf-8")
        self.assertIn("class ProjectWorkspace", kernel)
        self.assertIn("class CaseWorkspaceStore", kernel)

    def test_help_is_untouched(self):
        from services.help_mode import HELP_LIBRARY_PROJECT_ID, is_help_workspace

        self.assertTrue(is_help_workspace(HELP_LIBRARY_PROJECT_ID))
        self.assertFalse(is_help_workspace(self.black_box.project_id))

    def test_listing_boundary_and_d1_are_unchanged(self):
        body = self._client().get("/projects").get_data(as_text=True)
        self.assertNotIn(self.black_box.project_id, body)
        self.assertIn(self.project.project_id, body)
        workspace = self.store.get(self.black_box.project_id)
        self.assertEqual(workspace.sources[0]["kind"], SOURCE_KIND_UNCLASSIFIED)

    def test_entitlement_was_not_widened(self):
        source = (_REPO_ROOT / "routes" / "portal.py").read_text(encoding="utf-8")
        header = source[:source.index("def document_shop_intake")]
        self.assertTrue(header.rstrip().endswith("@limiter.limit(\"20 per hour\", methods=[\"POST\"])")
                        or "@admin_required" in header[-200:])
