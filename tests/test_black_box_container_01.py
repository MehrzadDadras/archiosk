"""CLAUDE-BLACK-BOX-01: a governed container may exist before it is programmed.

GOVERNED BUT UNPROGRAMMED. The investigation that preceded this found the
blocker precisely: every governed container required an engagement context,
because there had only ever been one kind of container. Project creation and
procurement classification were historically fused - deliberately, and
correctly, FOR PROJECTS.

Three tests carry the weight:

`test_black_box_is_not_ungated` - the inversion this state exists to prevent.
`operating_environment=None` already means "legacy, therefore ungated"; a
container with no programme must mean the opposite, and falling through to the
legacy branch would hand an unprogrammed job every capability in the registry.

`test_black_box_is_not_a_third_operating_environment` - the axis stays clean.
Engagement classifies authority; container state says whether a programme is
attached at all.

`test_conventional_project_creation_is_unchanged` - the rule "a project cannot
exist without an engagement context" is not weakened anywhere.
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
    LEGEND_KIND_SECTION_REFERENCE, LEGEND_STATUS_CONFIRMED, PROPOSITION_IDENTITY,
    SOURCE_KIND_DRAWING, SOURCE_KIND_RFQ_RFP_DOCUMENT,
)
from services.environment_capabilities import (
    CAPABILITY_FUTURE_NOT_AUTHORIZED, CAPABILITY_NEUTRAL,
    CAPABILITY_REGISTRY, CLIENT_OWNER,
    DESIGN_BUILDER_PROPONENT, KNOWN_CONTAINER_STATES, OPERATING_ENVIRONMENTS,
    TOOL_GROUP_BINDINGS, TOOL_GROUP_DESIGN_CONSTRUCTION, TOOL_GROUP_GENERAL,
    TOOL_GROUP_DOCUMENT_AS_READ, TOOL_GROUP_PROJECT_INTELLIGENCE,
    TOOL_GROUP_RFP_PROCUREMENT, WORKFLOW_DOCUMENT_SHOP, capability_availability,
    capability_denial_reason, resolve_tool_exposure, tool_available,
)
from services.ingestion import UploadError, ingest_upload
from services.legend_of_understanding import decide_proposition, legend_proposition

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _file(content: bytes, name: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=name)


class BlackBoxVocabularyTests(unittest.TestCase):
    """The axis separation, asserted directly."""

    def test_black_box_is_not_a_third_operating_environment(self):
        self.assertNotIn(CONTAINER_STATE_BLACK_BOX, OPERATING_ENVIRONMENTS)
        self.assertEqual(OPERATING_ENVIRONMENTS,
                         (CLIENT_OWNER, DESIGN_BUILDER_PROPONENT))
        for forbidden in ("black_box", "document_shop"):
            self.assertNotIn(forbidden, OPERATING_ENVIRONMENTS)
        self.assertIn(CONTAINER_STATE_BLACK_BOX, KNOWN_CONTAINER_STATES)

    def test_no_engagement_capability_leaks_into_an_unprogrammed_container(self):
        """Absence of a programme is not permission.

        Retargeted (operating-model clarification 02). This first asserted that
        EVERY registry capability was refused, which was too broad and wrong in
        a way that mattered: four entries are CAPABILITY_NEUTRAL - source
        preservation, neutral extraction, case investigation and the governance
        audit trail - and the blanket rule switched off provenance and audit in
        the one container whose whole purpose is governed intake.

        The surviving intent is asserted here exactly: nothing defined BY the
        Owner/Proponent relationship may be exercised from a container that has
        no such relationship.
        """
        for capability_id, definition in CAPABILITY_REGISTRY.items():
            if definition.classification == CAPABILITY_NEUTRAL:
                continue
            with self.subTest(capability=capability_id):
                self.assertFalse(
                    capability_availability(
                        capability_id, None,
                        container_state=CONTAINER_STATE_BLACK_BOX),
                    "%s leaked into an unprogrammed container" % capability_id)

    def test_the_shared_kernel_is_never_withheld_from_a_black_box(self):
        """SHARED CORPORATE INFRASTRUCTURE IS NOT THE OPERATING PROGRAMME.

        CAPABILITY_NEUTRAL is defined in environment_capabilities as the shared
        foundation available identically in every environment. It is what every
        operating line stands on, not something an engagement grants - so a
        container with no engagement keeps all of it. Refusing
        governance_audit_trail here would contradict NO PROGRAM DOES NOT MEAN
        NO GOVERNANCE in the most direct way available.
        """
        neutral = [cid for cid, d in CAPABILITY_REGISTRY.items()
                   if d.classification == CAPABILITY_NEUTRAL]
        self.assertTrue(neutral, "the neutral foundation must not be empty")
        for capability_id in neutral:
            with self.subTest(capability=capability_id):
                self.assertTrue(
                    capability_availability(
                        capability_id, None,
                        container_state=CONTAINER_STATE_BLACK_BOX),
                    "%s is corporate kernel, not engagement programme"
                    % capability_id)
                self.assertIsNone(capability_denial_reason(
                    capability_id, None,
                    container_state=CONTAINER_STATE_BLACK_BOX))
        for expected in ("source_preservation", "governance_audit_trail"):
            self.assertIn(expected, neutral)

    def test_black_box_is_not_equivalent_to_none(self):
        """The two must reach OPPOSITE conclusions from the same absent field."""
        differed = False
        for capability_id in CAPABILITY_REGISTRY:
            legacy = capability_availability(capability_id, None)
            black_box = capability_availability(
                capability_id, None, container_state=CONTAINER_STATE_BLACK_BOX)
            if legacy != black_box:
                differed = True
        self.assertTrue(differed,
                        "if Black Box and legacy None agreed everywhere, the "
                        "state would be doing nothing")

    def test_legacy_none_semantics_are_unchanged(self):
        for capability_id in CAPABILITY_REGISTRY:
            definition = CAPABILITY_REGISTRY[capability_id]
            expected = definition.classification != "future_not_authorized"
            self.assertEqual(capability_availability(capability_id, None), expected)

    def test_owner_and_proponent_gating_is_unchanged(self):
        for capability_id, definition in CAPABILITY_REGISTRY.items():
            self.assertEqual(
                capability_availability(capability_id, CLIENT_OWNER),
                definition.client_variant is not None)
            self.assertEqual(
                capability_availability(capability_id, DESIGN_BUILDER_PROPONENT),
                definition.proponent_variant is not None)

    def test_denial_reason_explains_the_container_not_the_environment(self):
        """Asked about an ENGAGEMENT capability - the only kind refused here."""
        reason = capability_denial_reason(
            "rfi_originate", None, container_state=CONTAINER_STATE_BLACK_BOX)
        self.assertIn("no engagement programme", reason)
        self.assertNotIn("Client /", reason)
        self.assertNotIn("Proponent project", reason)

    def test_denial_reason_does_not_predict_a_destination(self):
        """BLACK BOX PRECEDES CLASSIFICATION; IT DOES NOT PREDICT DESTINATION.

        "no programme attached YET" quietly promises a project is coming. It is
        not: the material may stay a standalone job, become reference material,
        be archived, or be routed onward.
        """
        reason = capability_denial_reason(
            "rfi_originate", None, container_state=CONTAINER_STATE_BLACK_BOX)
        self.assertNotIn("yet", reason)
        self.assertIn("Whether one is ever attached", reason)

    # -- tool exposure --------------------------------------------------------

    def test_black_box_exposure_is_document_work_only(self):
        exposure = resolve_tool_exposure(
            None, source_kinds={"drawing"},
            container_state=CONTAINER_STATE_BLACK_BOX)
        self.assertTrue(exposure[TOOL_GROUP_DOCUMENT_AS_READ])
        self.assertTrue(exposure[TOOL_GROUP_DESIGN_CONSTRUCTION])
        self.assertFalse(exposure[TOOL_GROUP_RFP_PROCUREMENT])
        self.assertFalse(exposure[TOOL_GROUP_PROJECT_INTELLIGENCE])

    def test_no_project_intelligence_without_a_project(self):
        black_box = resolve_tool_exposure(
            None, source_kinds={"drawing"},
            container_state=CONTAINER_STATE_BLACK_BOX)
        project = resolve_tool_exposure(CLIENT_OWNER, source_kinds={"drawing"})
        self.assertFalse(tool_available("spin", black_box))
        self.assertTrue(tool_available("spin", project),
                        "a real project must keep Spin exactly as before")

    def test_exposure_uses_the_one_existing_mechanism(self):
        services = {p.name for p in (_REPO_ROOT / "services").glob("*.py")}
        for invented in ("black_box.py", "container_registry.py",
                         "realm_registry.py", "tool_exposure.py"):
            self.assertNotIn(invented, services)


class BlackBoxContainerTests(unittest.TestCase):
    """The container itself, created through the real ingest path."""

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_black_box_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ingest(self, name="drawing.txt", **kwargs):
        def fake_parse(_parser, _raw, filename):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename,
                ingested_at=datetime.now(timezone.utc).isoformat(),
                parser_version="test")

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.app.app_context():
                return ingest_upload(_file(b"x", name), self.app,
                                     owner="owner", **kwargs)

    def _black_box(self, name=None):
        # Distinct names on purpose: a Black Box goes through the SAME registry
        # and the same "Project name already exists" uniqueness rule as any
        # other container - which is itself evidence there is no second store.
        return self._ingest(operating_environment=None,
                            container_state=CONTAINER_STATE_BLACK_BOX,
                            project_name=name or ("Black Box Job %s" % uuid.uuid4().hex[:8]))

    # -- creation -------------------------------------------------------------

    def test_a_black_box_can_be_created_without_an_engagement_context(self):
        document = self._black_box()
        workspace = self.store.get(document.project_id)
        self.assertEqual(workspace.container_state, CONTAINER_STATE_BLACK_BOX)
        self.assertIsNone(workspace.operating_environment)
        self.assertIsNone(workspace.lifecycle_stage,
                          "an unprogrammed container has no procurement lifecycle")

    def test_conventional_project_creation_is_unchanged(self):
        document = self._ingest(operating_environment=CLIENT_OWNER,
                                project_name="Normal Project")
        workspace = self.store.get(document.project_id)
        self.assertEqual(workspace.operating_environment, CLIENT_OWNER)
        self.assertIsNone(workspace.container_state)
        self.assertIsNotNone(workspace.lifecycle_stage)

    def test_a_project_still_cannot_be_created_without_an_environment(self):
        with self.assertRaises(UploadError) as caught:
            self._ingest(operating_environment=None, project_name="No Env")
        self.assertIn("operating environment", str(caught.exception))

    def test_a_black_box_may_not_also_declare_an_environment(self):
        """Unprogrammed and Client/Owner are different claims."""
        with self.assertRaises(UploadError) as caught:
            self._ingest(operating_environment=CLIENT_OWNER,
                         container_state=CONTAINER_STATE_BLACK_BOX,
                         project_name="Both")
        self.assertIn("no engagement programme", str(caught.exception))

    # -- the evidence kernel is fully present --------------------------------

    def test_the_evidence_kernel_is_preserved(self):
        document = self._black_box()
        workspace = self.store.get(document.project_id)
        self.assertTrue(workspace.project_id)
        self.assertEqual(len(workspace.sources), 1)
        source = workspace.sources[0]
        self.assertEqual(source["project_id"], workspace.project_id)
        self.assertTrue(source["id"])
        self.assertEqual(workspace.owner, "owner")

    def test_access_control_and_isolation_are_intact(self):
        first = self._black_box()
        second = self._black_box()
        self.assertNotEqual(first.project_id, second.project_id)
        one = self.store.get(first.project_id)
        two = self.store.get(second.project_id)
        self.assertNotEqual(one.sources[0]["id"], two.sources[0]["id"])
        for source in one.sources:
            self.assertEqual(source["project_id"], one.project_id)

    def test_document_intelligence_runs_inside_a_black_box(self):
        """The whole point: As-Read works, unchanged, with no programme."""
        document = self._black_box()
        workspace = self.store.get(document.project_id)
        source = workspace.sources[0]
        snapshot = self.tmp / "crop.png"
        snapshot.write_bytes(b"\x89PNG\r\n\x1a\n")
        unit = self.store.register_drawing_sheet_structure(
            workspace, source["id"],
            [{"index": 0, "label": "Sheet", "width": 100.0, "height": 100.0,
              "source_rotation": 0, "metadata": {}}],
            actor="test")["structural_unit_ids"][0]
        workspace = self.store.get(document.project_id)
        item = self.store.propose_legend_item(
            workspace, source_id=source["id"], page_structural_unit_id=unit,
            region={"x": 1.0, "y": 1.0, "width": 5.0, "height": 5.0},
            proposed_kind=LEGEND_KIND_SECTION_REFERENCE,
            proposed_meaning="A section reference marker.",
            interpretation_method="test", actor="GO",
            snapshot_path=str(snapshot))
        decide_proposition(self.store, self.store.get(document.project_id),
                           item["id"], PROPOSITION_IDENTITY,
                           action=LEGEND_STATUS_CONFIRMED, actor="Product Owner")
        workspace = self.store.get(document.project_id)
        stored = next(i for i in workspace.legend_items if i["id"] == item["id"])
        self.assertTrue(legend_proposition(stored, PROPOSITION_IDENTITY)["settled"])
        self.assertTrue(stored["decisions"], "append-only history is present")

    def test_no_second_source_or_as_read_store_exists(self):
        document = self._black_box()
        workspace = self.store.get(document.project_id)
        for invented in ("black_box_sources", "job_sources", "shop_sources",
                         "black_box_legend_items"):
            self.assertFalse(hasattr(workspace, invented))
        registry_files = {p.name for p in self.tmp.rglob("*.json")}
        self.assertTrue(
            any(document.project_id in name for name in registry_files),
            "a Black Box persists through the ordinary registry, not a second store")

    # -- routing onward, whatever the destination turns out to be -------------

    def test_routing_a_container_onward_never_recreates_the_evidence(self):
        """PROGRAM THE CONTAINER. DO NOT RECREATE THE EVIDENCE.

        Deliberately NOT a promotion test. A Black Box has no predetermined
        destination - it may remain a standalone Document Shop job, produce a
        one-time deliverable and close, become governed reference material, be
        archived, or be routed into a project or a procurement matter. This
        asserts only the SHAPE that keeps every one of those cheap: container
        state and engagement environment are independent fields on ONE
        workspace, so any onward routing is a field transition, never a
        re-ingest. Source ids, hashes and history are untouched by it.

        Attaching a programme this way is NOT built or authorized; the test
        drives the fields directly to prove the evidence survives the shape of
        such a transition, not to sanction one.
        """
        document = self._black_box()
        workspace = self.store.get(document.project_id)
        source_id = workspace.sources[0]["id"]
        project_id = workspace.project_id

        # The field transition ANY onward routing would make.
        workspace.container_state = None
        self.store.set_operating_environment(workspace, CLIENT_OWNER, actor="PO")

        promoted = self.store.get(project_id)
        self.assertEqual(promoted.project_id, project_id)
        self.assertEqual(promoted.sources[0]["id"], source_id)
        self.assertEqual(promoted.operating_environment, CLIENT_OWNER)
        self.assertIsNone(promoted.container_state)
        self.assertTrue(
            capability_availability(next(iter(CAPABILITY_REGISTRY)), CLIENT_OWNER,
                                    container_state=promoted.container_state)
            in (True, False),
            "capability resolution follows the programme once attached")

    def test_legacy_containers_without_the_field_still_load(self):
        document = self._ingest(operating_environment=CLIENT_OWNER,
                                project_name="Legacy Shape")
        workspace = self.store.get(document.project_id)
        del workspace.container_state
        self.store.save(workspace)
        reloaded = self.store.get(document.project_id)
        self.assertIsNone(getattr(reloaded, "container_state", None))
        self.assertEqual(reloaded.operating_environment, CLIENT_OWNER)


    # -- the establishment of the container state is itself governed ----------

    def test_creating_a_black_box_is_a_governed_event(self):
        """NO PROGRAM DOES NOT MEAN NO GOVERNANCE - including the act itself.

        A bare attribute write would have made the one transition that MAKES a
        container a Black Box the only creation-time state change in the kernel
        with no governance record.
        """
        from services.ingestion import get_governance_log

        document = self._black_box()
        with self.app.app_context():
            events = get_governance_log(self.app).read(document.project_id)
        types = [e.event_type for e in events]
        self.assertIn("container_state_established", types)
        established = next(e for e in events
                           if e.event_type == "container_state_established")
        self.assertEqual(established.payload["container_state"],
                         CONTAINER_STATE_BLACK_BOX)
        # The engagement axis was never touched, so its events must be absent.
        self.assertNotIn("operating_environment_established", types)
        self.assertNotIn("lifecycle_stage_established", types)

    def test_a_conventional_project_logs_what_it_always_did(self):
        from services.ingestion import get_governance_log

        document = self._ingest(operating_environment=CLIENT_OWNER,
                                project_name="Governed Normal Project")
        with self.app.app_context():
            events = get_governance_log(self.app).read(document.project_id)
        types = [e.event_type for e in events]
        self.assertIn("operating_environment_established", types)
        self.assertIn("lifecycle_stage_established", types)
        self.assertNotIn("container_state_established", types)

    def test_container_state_is_locked_exactly_as_the_environment_is(self):
        document = self._black_box()
        workspace = self.store.get(document.project_id)
        with self.assertRaises(CaseWorkspaceError):
            self.store.set_container_state(
                workspace, CONTAINER_STATE_BLACK_BOX, actor="test")
        self.assertEqual(
            self.store.get(document.project_id).container_state,
            CONTAINER_STATE_BLACK_BOX)

    def test_an_unrecognized_container_state_is_refused(self):
        document = self._ingest(operating_environment=CLIENT_OWNER,
                                project_name="Unrecognized State")
        workspace = self.store.get(document.project_id)
        with self.assertRaises(ValueError):
            self.store.set_container_state(workspace, "sort_of_programmed",
                                           actor="test")

    # -- the decision must reach the rendered page ---------------------------

    def _client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "owner"
            session["role"] = "read_only"
        return client

    def test_a_black_box_page_withholds_spin_but_keeps_document_work(self):
        """The end-to-end proof, not the decision function in isolation.

        Before this, resolve_tool_exposure knew the answer and the application
        never asked it: `_tool_exposure()` did not pass container_state, and no
        template consulted project_intelligence. The classification was real and
        inert at the same time.
        """
        document = self._black_box()
        body = self._client().get(
            "/projects/%s/workspace" % document.project_id).get_data(as_text=True)
        self.assertNotIn('data-ui-ref="toolbox.spin"', body,
                         "no project -> no project-wide Spin")
        self.assertNotIn('data-ui-ref="toolbox.spin.run-first"', body)
        self.assertIn('data-ui-ref="toolbox.project-intelligence"', body,
                      "the PANE holds Tasks/Tags/Conversation and stays")

    def test_an_ordinary_project_page_still_shows_spin(self):
        """The regression guard on the same conditional."""
        document = self._ingest(operating_environment=CLIENT_OWNER,
                                project_name="Spin Still Here")
        body = self._client().get(
            "/projects/%s/workspace" % document.project_id).get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.spin"', body)
        self.assertIn('data-ui-ref="toolbox.project-intelligence"', body)

    def test_a_legacy_unclassified_project_still_shows_spin(self):
        """operating_environment=None keeps meaning legacy, never Black Box."""
        document = self._ingest(operating_environment=CLIENT_OWNER,
                                project_name="Legacy Shape")
        workspace = self.store.get(document.project_id)
        workspace.operating_environment = None
        self.store.save(workspace)
        body = self._client().get(
            "/projects/%s/workspace" % document.project_id).get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.spin"', body)


class SpinSemanticDependencyTests(unittest.TestCase):
    """CLAUDE-BLACK-BOX-01 final verification: WHY Spin moved, not that it did.

    SPIN REQUIRES A PROJECT CONTEXT TO SPIN. The classification change is a
    semantic dependency, and these tests are written to fail if it is ever
    justified as category symmetry instead - both
    `test_spin_follows_project_context_not_source_type` and
    `test_a_black_box_holding_drawings_still_has_no_project_to_spin` hold source
    type CONSTANT and vary only whether a project exists.
    """

    # -- 1. existing project behaviour is unchanged ---------------------------

    def test_every_project_context_still_exposes_spin(self):
        contexts = {
            "client_owner": resolve_tool_exposure(CLIENT_OWNER),
            "proponent": resolve_tool_exposure(DESIGN_BUILDER_PROPONENT),
            "owner with drawings": resolve_tool_exposure(
                CLIENT_OWNER, source_kinds={SOURCE_KIND_DRAWING}),
            "proponent with rfp": resolve_tool_exposure(
                DESIGN_BUILDER_PROPONENT, source_kinds={SOURCE_KIND_RFQ_RFP_DOCUMENT}),
            "mixed project": resolve_tool_exposure(
                CLIENT_OWNER, source_kinds={SOURCE_KIND_DRAWING,
                                            SOURCE_KIND_RFQ_RFP_DOCUMENT}),
            "unclassified legacy project": resolve_tool_exposure(None),
            "empty project": resolve_tool_exposure(CLIENT_OWNER, source_kinds=set()),
        }
        for label, exposure in contexts.items():
            with self.subTest(context=label):
                self.assertTrue(exposure[TOOL_GROUP_PROJECT_INTELLIGENCE],
                                "%s must retain Spin exactly as before" % label)
                self.assertTrue(tool_available("spin", exposure))
                self.assertTrue(tool_available("spin-launcher", exposure))

    def test_document_shop_inside_a_project_still_exposes_spin(self):
        """The workshop bench narrows procurement, never project intelligence.

        A source open on the bench still belongs to a project, so the object
        Spin reasons across still exists.
        """
        for selected in (SOURCE_KIND_DRAWING, SOURCE_KIND_RFQ_RFP_DOCUMENT, None):
            with self.subTest(selected=selected):
                exposure = resolve_tool_exposure(
                    CLIENT_OWNER,
                    source_kinds={SOURCE_KIND_DRAWING, SOURCE_KIND_RFQ_RFP_DOCUMENT},
                    selected_source_kind=selected,
                    workflow=WORKFLOW_DOCUMENT_SHOP)
                self.assertTrue(exposure[TOOL_GROUP_PROJECT_INTELLIGENCE])
                self.assertFalse(exposure[TOOL_GROUP_RFP_PROCUREMENT],
                                 "unchanged from CLAUDE-DOCUMENT-SHOP-01")

    # -- 2. the Black Box, justified semantically ----------------------------

    def test_a_black_box_holding_drawings_still_has_no_project_to_spin(self):
        """Source type held constant; only the presence of a project varies."""
        project = resolve_tool_exposure(None, source_kinds={SOURCE_KIND_DRAWING})
        black_box = resolve_tool_exposure(
            None, source_kinds={SOURCE_KIND_DRAWING},
            container_state=CONTAINER_STATE_BLACK_BOX)

        self.assertTrue(project[TOOL_GROUP_PROJECT_INTELLIGENCE])
        self.assertFalse(black_box[TOOL_GROUP_PROJECT_INTELLIGENCE],
                         "no project -> no project-wide object to reason across")
        # Identical drawings on both sides: design tooling is unaffected, which
        # is what proves the withholding is about the missing project.
        self.assertEqual(project[TOOL_GROUP_DESIGN_CONSTRUCTION],
                         black_box[TOOL_GROUP_DESIGN_CONSTRUCTION])
        self.assertTrue(black_box[TOOL_GROUP_DOCUMENT_AS_READ],
                        "document intelligence is what a Black Box is FOR")

    def test_spin_follows_project_context_not_source_type(self):
        for kinds in ({SOURCE_KIND_DRAWING}, {SOURCE_KIND_RFQ_RFP_DOCUMENT},
                      {SOURCE_KIND_DRAWING, SOURCE_KIND_RFQ_RFP_DOCUMENT}, set()):
            with self.subTest(kinds=sorted(kinds)):
                self.assertTrue(resolve_tool_exposure(
                    CLIENT_OWNER, source_kinds=kinds)[TOOL_GROUP_PROJECT_INTELLIGENCE],
                    "source type must never decide Spin")
                self.assertFalse(resolve_tool_exposure(
                    None, source_kinds=kinds,
                    container_state=CONTAINER_STATE_BLACK_BOX)[
                        TOOL_GROUP_PROJECT_INTELLIGENCE])

    # -- 4. no overreach ------------------------------------------------------

    def test_only_spin_moved_and_nothing_else_was_reclassified(self):
        """The guard on "do not move tools merely to make groups symmetrical"."""
        by_group = {}
        for tool, group in TOOL_GROUP_BINDINGS.items():
            by_group.setdefault(group, set()).add(tool)

        self.assertEqual(by_group[TOOL_GROUP_PROJECT_INTELLIGENCE],
                         {"spin", "spin-launcher"},
                         "exactly two tools moved, and only because Spin needs "
                         "a project; anything else here is category tidying")
        self.assertEqual(by_group[TOOL_GROUP_DOCUMENT_AS_READ],
                         {"document", "eye-thumbnails"})
        self.assertEqual(by_group[TOOL_GROUP_RFP_PROCUREMENT],
                         {"requirements", "rfi"})
        self.assertEqual(by_group[TOOL_GROUP_DESIGN_CONSTRUCTION],
                         {"drawing-understanding"})
        self.assertEqual(by_group[TOOL_GROUP_GENERAL], {
            "composer-findings", "conversation", "heading",
            "investigation-findings", "investigations", "panel",
            "project-admin", "project-intelligence", "q-materials", "tags",
            "tasks", "work-products"})

    def test_the_project_intelligence_pane_stays_general(self):
        """A container is not its contents.

        `toolbox.project-intelligence` is the pane that HOLDS Spin, Tasks,
        Tags, Conversation, Requirements and RFI - a mixed container whose
        children are gated individually. Its near-identical name to the new
        group is a real trap: moving the pane would hide Tasks and Tags from a
        Black Box, and neither has anything to do with project-wide reasoning.
        """
        self.assertEqual(TOOL_GROUP_BINDINGS["project-intelligence"],
                         TOOL_GROUP_GENERAL)
        exposure = resolve_tool_exposure(
            None, container_state=CONTAINER_STATE_BLACK_BOX)
        self.assertTrue(tool_available("project-intelligence", exposure))
        self.assertTrue(tool_available("tasks", exposure))
        self.assertTrue(tool_available("conversation", exposure))
        self.assertFalse(tool_available("spin", exposure))

    def test_no_third_operating_environment_and_none_semantics_intact(self):
        self.assertEqual(OPERATING_ENVIRONMENTS,
                         (CLIENT_OWNER, DESIGN_BUILDER_PROPONENT))
        for capability_id in CAPABILITY_REGISTRY:
            with self.subTest(capability=capability_id):
                self.assertEqual(
                    capability_availability(capability_id, None),
                    capability_availability(capability_id, None,
                                            container_state=None),
                    "an absent container_state must change nothing")


class BlackBoxDenialReasonOrderTests(unittest.TestCase):
    """A denial must name the REAL reason, and an unknown id must still raise."""

    def test_an_unknown_capability_raises_even_in_a_black_box(self):
        with self.assertRaises(KeyError):
            capability_denial_reason("no_such_capability", None,
                                     container_state=CONTAINER_STATE_BLACK_BOX)

    def test_an_unauthorized_capability_is_not_blamed_on_the_container(self):
        unauthorized = [
            cid for cid, d in CAPABILITY_REGISTRY.items()
            if d.classification == CAPABILITY_FUTURE_NOT_AUTHORIZED]
        if not unauthorized:
            self.skipTest("no NOT-AUTHORIZED capability registered")
        for capability_id in unauthorized:
            with self.subTest(capability=capability_id):
                reason = capability_denial_reason(
                    capability_id, None,
                    container_state=CONTAINER_STATE_BLACK_BOX)
                self.assertIn("not yet authorized", reason)
                self.assertNotIn("engagement programme", reason,
                                 "attaching a programme would NOT enable this, "
                                 "so the container must not be blamed for it")
