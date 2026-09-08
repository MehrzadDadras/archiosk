"""CLAUDE-BLACK-BOX-DOOR-01: the first user-operable door into the Black Box.

The kernel tranche (`bdda7ce`) proved a governed container could exist with no
engagement programme, and then no route created one. A capability reachable
from nowhere is not a capability yet - the same lesson
`tests/test_asread_nav_01.py` recorded when a whole As-Read tranche shipped
behind a URL nobody could reach.

Three tests carry the weight:

`test_intake_asks_for_no_engagement_fact` - the door's whole reason to exist.
It asserts the form asks for none of the six facts a project demands, by
scanning what is actually rendered rather than trusting the route.

`test_none_is_not_used_as_a_shortcut` - the failure this design was built to
avoid. `operating_environment=None` already means "legacy, therefore ungated";
a door that produced one of those instead of a Black Box would silently create
the most permissive container in the system.

`test_the_door_predicts_no_destination` - BLACK BOX PRECEDES CLASSIFICATION,
IT DOES NOT PREDICT DESTINATION, asserted against the rendered words.
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
    CONTAINER_STATE_BLACK_BOX, CaseWorkspaceError, CaseWorkspaceStore,
)
from services.environment_capabilities import (
    CAPABILITY_NEUTRAL, CAPABILITY_REGISTRY, CLIENT_OWNER,
    TOOL_GROUP_DOCUMENT_AS_READ, TOOL_GROUP_PROJECT_INTELLIGENCE,
    TOOL_GROUP_RFP_PROCUREMENT, capability_availability, resolve_tool_exposure,
    tool_available,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent

DOOR = "/document-shop"


def _fake_parse(_parser, _raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test")


class BlackBoxDoorTests(unittest.TestCase):

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_bb_door_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _client(self, role="admin", username="owner"):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = username
            session["role"] = role
        return client

    def _post(self, client=None, filename="drawing.pdf", name=None, content=b"x"):
        client = client or self._client()
        data = {"file": (io.BytesIO(content), filename)}
        if name is not None:
            data["name"] = name
        with patch.object(BHiveParser, "parse", _fake_parse):
            return client.post(DOOR, data=data,
                               content_type="multipart/form-data")

    def _container_from(self, response):
        project_id = response.headers["Location"].split("/projects/")[1].split("/")[0]
        return self.store.get(project_id)

    # -- 1. the route exists, and it is authenticated ------------------------

    def test_the_intake_route_exists_and_renders(self):
        response = self._client().get(DOOR)
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('data-ui-ref="document-shop.file"', body)
        self.assertIn('data-ui-ref="document-shop.submit"', body)

    def test_an_unauthenticated_visitor_is_refused(self):
        anonymous = self.app.test_client()
        for method in ("get", "post"):
            with self.subTest(method=method):
                response = getattr(anonymous, method)(DOOR)
                self.assertIn(response.status_code, (302, 401, 403),
                              "durable governed storage must never be anonymous")
                if response.status_code == 302:
                    self.assertNotIn("/projects/", response.headers["Location"])

    def test_creating_a_container_holds_the_existing_authority_line(self):
        """A read-only reviewer may not create governed storage.

        Deliberately the SAME authority as portal.upload rather than a looser
        one. Who may create a durable governed container is a standing
        decision; a new door does not get to widen it quietly. A genuinely
        customer-facing Document Shop needs its own entitlement decision, and
        that is the storefront, which is not this.
        """
        response = self._post(client=self._client(role="read_only"))
        self.assertIn(response.status_code, (302, 401, 403))
        self.assertEqual(len(list(self.tmp.glob("*.workspace.json"))), 0)

    # -- 2/3. no engagement fact is demanded ---------------------------------

    def test_intake_asks_for_no_engagement_fact(self):
        body = self._client().get(DOOR).get_data(as_text=True)
        for demanded in ('name="operating_environment"', 'name="entry_choice"',
                         'name="retained_by"', 'name="project_code"',
                         'name="project_name"', 'name="source_domain"'):
            with self.subTest(field=demanded):
                self.assertNotIn(demanded, body,
                                 "the door must not ask for a fact the person "
                                 "does not have yet")

    def test_an_upload_with_nothing_but_a_file_succeeds(self):
        """No project selected, no environment chosen, no name given."""
        response = self._post()
        self.assertEqual(response.status_code, 302)
        workspace = self._container_from(response)
        self.assertEqual(workspace.container_state, CONTAINER_STATE_BLACK_BOX)

    # -- 4/5. the container that is actually created -------------------------

    def test_none_is_not_used_as_a_shortcut(self):
        """The most dangerous near-miss available to this design.

        `operating_environment=None` already means "legacy/unclassified,
        therefore UNGATED". A door that produced one of those instead of a
        Black Box would have created the most permissive container in the
        system while looking correct in every other respect.
        """
        workspace = self._container_from(self._post())
        self.assertIsNone(workspace.operating_environment)
        self.assertEqual(workspace.container_state, CONTAINER_STATE_BLACK_BOX,
                         "absent environment alone is a LEGACY project, not a "
                         "Black Box - the state must be explicit")
        self.assertIsNone(workspace.lifecycle_stage,
                          "no engagement means no procurement lifecycle")

    def test_the_container_keeps_owner_provenance_and_isolation(self):
        workspace = self._container_from(self._post())
        self.assertEqual(workspace.owner, "owner")
        self.assertTrue(workspace.project_id)
        self.assertEqual(len(workspace.sources), 1)
        self.assertEqual(workspace.sources[0]["project_id"], workspace.project_id)
        self.assertTrue(workspace.sources[0]["id"])

    # -- 6/7. governed creation, and the lock --------------------------------

    def test_creation_through_the_door_is_a_governed_event(self):
        from services.ingestion import get_governance_log

        workspace = self._container_from(self._post())
        with self.app.app_context():
            events = get_governance_log(self.app).read(workspace.project_id)
        types = [e.event_type for e in events]
        self.assertIn("container_state_established", types)
        self.assertIn("document_ingested", types)
        self.assertNotIn("operating_environment_established", types)
        self.assertNotIn("lifecycle_stage_established", types)

    def test_lock_semantics_survive_the_door(self):
        workspace = self._container_from(self._post())
        with self.assertRaises(CaseWorkspaceError):
            self.store.set_container_state(
                workspace, CONTAINER_STATE_BLACK_BOX, actor="test")

    # -- 8/9. what may come through the door ---------------------------------

    def test_a_supported_document_is_accepted(self):
        for filename in ("sheet.pdf", "spec.docx", "notes.txt", "data.csv",
                         "readme.md"):
            with self.subTest(filename=filename):
                response = self._post(filename=filename)
                self.assertEqual(response.status_code, 302)

    def test_a_spreadsheet_cannot_be_the_founding_document(self):
        """A PRE-EXISTING ingest_upload rule, pinned here rather than assumed.

        `.xlsx` is in ALLOWED_UPLOAD_EXTENSIONS but cannot found a container:
        ingest_upload refuses it because a workbook is not prose suitable for
        classification. That rule predates this door and is not changed by it.

        It is recorded because the door inherits it: someone arriving with a
        schedule as their only document is refused, and that is a real limit
        on "bring us your difficult material". A future tranche that wants
        spreadsheet-first intake changes ingest_upload, not this test.
        """
        response = self._post(filename="schedule.xlsx")
        self.assertEqual(response.status_code, 400)

    def test_image_formats_remain_refused_at_the_door(self):
        """The gap is REAL and stays closed in this tranche.

        Scans are exactly the material a Document Shop receives, and they are
        not accepted yet. Widening `ALLOWED_UPLOAD_EXTENSIONS` is a separate,
        security-reviewed decision - this test exists so that widening is a
        deliberate act with a failing test attached, never a quiet drift.
        """
        for filename in ("scan.jpg", "scan.jpeg", "scan.png", "scan.tif",
                         "scan.tiff"):
            with self.subTest(filename=filename):
                response = self._post(filename=filename)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(len(list(self.tmp.glob("*.workspace.json"))), 0,
                                 "a refused upload must leave no container")

    def test_a_refusal_is_explained_and_names_no_procurement_context(self):
        body = self._post(filename="scan.jpg").get_data(as_text=True)
        marker = 'data-ui-ref="document-shop.error">'
        self.assertIn(marker, body)
        # The MESSAGE, not the page. The surrounding shell legitimately carries
        # navigation wording; scanning the whole document would assert about
        # the menu bar rather than about the refusal.
        message = body.split(marker, 1)[1].split("</p>", 1)[0]
        self.assertTrue(message.strip(), "a refusal must say something")
        # CLAUDE-BLACK-BOX-D2-01: this now covers every refusal reachable
        # here, which is what test_the_founding_refusal_still_speaks_in_project_terms
        # said to do once the leak was fixed. That test is deleted per its own
        # instruction rather than left asserting a defect that no longer exists.
        for absent in ("Owner", "Proponent", "procurement", "RFP", "project"):
            with self.subTest(word=absent):
                self.assertNotIn(absent, message,
                                 "a refused document must not be explained in "
                                 "terms of an engagement this container has not "
                                 "got")

    # -- 10. where the person lands ------------------------------------------

    def test_a_successful_upload_lands_in_the_existing_as_read_bench(self):
        response = self._post()
        location = response.headers["Location"]
        self.assertIn("/workspace/sources/", location)
        self.assertTrue(location.endswith("/understanding"),
                        "the person must land on the source they just gave us, "
                        "not in a workspace they then have to search")

        workspace = self._container_from(response)
        body = self._client().get(location).get_data(as_text=True)
        self.assertEqual(self._client().get(location).status_code, 200)
        self.assertIn(workspace.sources[0]["id"], location)
        self.assertIn("Document Shop", body)

    # -- 11. isolation --------------------------------------------------------

    def test_one_persons_container_is_not_reachable_by_another(self):
        location = self._post(client=self._client(username="owner")).headers["Location"]
        stranger = self._client(role="read_only", username="stranger")
        self.assertEqual(stranger.get(location).status_code, 404,
                         "a generic 404, never a distinguishable refusal")

    # -- 12/13/14. capability and tool behaviour -----------------------------

    def test_the_bench_offers_document_work_and_withholds_the_rest(self):
        exposure = resolve_tool_exposure(
            None, source_kinds={"drawing"},
            container_state=CONTAINER_STATE_BLACK_BOX)
        self.assertTrue(exposure[TOOL_GROUP_DOCUMENT_AS_READ])
        self.assertFalse(exposure[TOOL_GROUP_RFP_PROCUREMENT])
        self.assertFalse(exposure[TOOL_GROUP_PROJECT_INTELLIGENCE])
        self.assertFalse(tool_available("spin", exposure))
        self.assertFalse(tool_available("rfi", exposure))
        self.assertFalse(tool_available("requirements", exposure))

    def test_the_rendered_container_page_withholds_spin(self):
        workspace = self._container_from(self._post())
        body = self._client().get(
            "/projects/%s/workspace" % workspace.project_id).get_data(as_text=True)
        self.assertNotIn('data-ui-ref="toolbox.spin"', body)

    def test_the_neutral_foundation_is_available_through_the_door(self):
        """Provenance and audit are not something an engagement grants."""
        for capability_id, definition in CAPABILITY_REGISTRY.items():
            if definition.classification != CAPABILITY_NEUTRAL:
                continue
            with self.subTest(capability=capability_id):
                self.assertTrue(capability_availability(
                    capability_id, None,
                    container_state=CONTAINER_STATE_BLACK_BOX))

    # -- 15/16. nothing about projects changed -------------------------------

    def test_conventional_project_creation_is_untouched(self):
        from services.ingestion import ingest_upload

        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                document = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"x"), filename="rfp.pdf"),
                    self.app, operating_environment=CLIENT_OWNER, owner="owner",
                    project_name="Ordinary Project")
        workspace = self.store.get(document.project_id)
        self.assertEqual(workspace.operating_environment, CLIENT_OWNER)
        self.assertIsNone(workspace.container_state)
        self.assertIsNotNone(workspace.lifecycle_stage)

    def test_project_level_document_shop_still_sees_project_intelligence(self):
        from services.environment_capabilities import WORKFLOW_DOCUMENT_SHOP

        exposure = resolve_tool_exposure(
            CLIENT_OWNER, source_kinds={"drawing"},
            selected_source_kind="drawing", workflow=WORKFLOW_DOCUMENT_SHOP)
        self.assertTrue(exposure[TOOL_GROUP_PROJECT_INTELLIGENCE])
        self.assertTrue(exposure[TOOL_GROUP_DOCUMENT_AS_READ])

    def test_the_new_door_did_not_change_the_project_door(self):
        """`portal.upload` still asks for an engagement, exactly as before."""
        body = self._client().get("/upload").get_data(as_text=True)
        self.assertIn('data-ui-ref="upload.page-title"', body)
        # The project door still asks for the project facts. Named by ref
        # rather than by field name: the environment is resolved through
        # perspective/entry choice here, not a bare radio, and asserting the
        # field name would pin an implementation detail this test does not own.
        self.assertIn('data-ui-ref="upload.project-identity"', body)
        self.assertIn('data-ui-ref="upload.identity"', body)

    # -- 17/18. no second store, no destination ------------------------------

    def test_no_second_source_or_as_read_store_was_introduced(self):
        services = {p.name for p in (_REPO_ROOT / "services").glob("*.py")}
        for invented in ("document_shop.py", "black_box.py", "intake_store.py",
                         "container_registry.py"):
            self.assertNotIn(invented, services)

        workspace = self._container_from(self._post())
        self.assertEqual(len(list(self.tmp.glob("*.workspace.json"))), 1,
                         "one container, one store, one workspace file")
        self.assertTrue(workspace.sources[0]["id"])

    def test_the_door_predicts_no_destination(self):
        """BLACK BOX PRECEDES CLASSIFICATION; IT DOES NOT PREDICT DESTINATION."""
        body = self._client().get(DOOR).get_data(as_text=True)
        for forbidden in ("Continue as Project", "finish project setup",
                          "choose project later", "not assigned yet",
                          "awaiting engagement", "pre-project",
                          "Black Box", "temporary"):
            with self.subTest(phrase=forbidden):
                self.assertNotIn(forbidden, body)

    def test_no_promotion_route_was_added(self):
        rules = {str(rule) for rule in self.app.url_map.iter_rules()}
        for invented in ("/document-shop/promote", "/document-shop/continue",
                         "/document-shop/convert"):
            self.assertNotIn(invented, rules)
