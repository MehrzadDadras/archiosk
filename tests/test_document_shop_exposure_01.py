"""CLAUDE-DOCUMENT-SHOP-01: capability may be shared, exposure must be contextual.

The gap this closes was measured, not assumed: 66 registered `toolbox.*` refs,
none of them behind a conditional, so drawing tooling is reachable in a project
that holds no drawings purely because the engine has the capability.

The fix extends the capability mechanism that already governs procurement
actions rather than building a second framework beside it -
`test_no_second_capability_framework` is the guard on that promise.

Two tests carry the most weight:

`test_drawing_tools_are_withheld_in_a_pure_rfp_context` - the Product Owner's
actual concern, asserted directly.

`test_unknown_context_degrades_to_general_not_to_everything` - the safety
direction. An unclassified project must not silently ACQUIRE specialised
tooling; that is "machine inference never becomes authority" applied to
exposure.
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
    CaseWorkspaceStore, SOURCE_KIND_DRAWING, SOURCE_KIND_RFQ_RFP_DOCUMENT,
)
from services.environment_capabilities import (
    CLIENT_OWNER, DESIGN_BUILDER_PROPONENT, KNOWN_TOOL_GROUPS,
    TOOL_GROUP_BINDINGS, TOOL_GROUP_DESIGN_CONSTRUCTION,
    TOOL_GROUP_DOCUMENT_AS_READ, TOOL_GROUP_GENERAL, TOOL_GROUP_RFP_PROCUREMENT,
    WORKFLOW_DOCUMENT_SHOP, capability_availability, resolve_tool_exposure,
    tool_available, tool_group_available,
)
from services.environment_capabilities import CAPABILITY_REGISTRY
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent

DRAWING = SOURCE_KIND_DRAWING
RFP = SOURCE_KIND_RFQ_RFP_DOCUMENT


class ToolExposureTests(unittest.TestCase):
    """The decision function on its own - no app, no project, just the rules."""

    # -- the concern that started this ---------------------------------------

    def test_drawing_tools_are_withheld_in_a_pure_rfp_context(self):
        exposure = resolve_tool_exposure(
            CLIENT_OWNER, source_kinds={RFP}, selected_source_kind=RFP)
        self.assertFalse(exposure[TOOL_GROUP_DESIGN_CONSTRUCTION])
        self.assertTrue(exposure[TOOL_GROUP_RFP_PROCUREMENT])
        self.assertTrue(exposure[TOOL_GROUP_GENERAL])

    def test_unknown_context_degrades_to_general_not_to_everything(self):
        exposure = resolve_tool_exposure(None)
        self.assertTrue(exposure[TOOL_GROUP_GENERAL])
        self.assertFalse(exposure[TOOL_GROUP_DESIGN_CONSTRUCTION])
        self.assertFalse(exposure[TOOL_GROUP_DOCUMENT_AS_READ])

    # -- mixed projects: context, not a permanent project property -----------

    def test_a_mixed_project_shows_different_tools_per_open_source(self):
        kinds = {RFP, DRAWING}
        on_drawing = resolve_tool_exposure(None, source_kinds=kinds,
                                           selected_source_kind=DRAWING)
        on_rfp = resolve_tool_exposure(None, source_kinds=kinds,
                                       selected_source_kind=RFP)
        self.assertTrue(on_drawing[TOOL_GROUP_DESIGN_CONSTRUCTION])
        self.assertFalse(on_rfp[TOOL_GROUP_DESIGN_CONSTRUCTION],
                         "an RFP document open in a mixed project must not "
                         "offer drawing tooling")
        # Both remain procurement-capable: the project genuinely holds RFP work.
        self.assertTrue(on_drawing[TOOL_GROUP_RFP_PROCUREMENT])
        self.assertTrue(on_rfp[TOOL_GROUP_RFP_PROCUREMENT])

    def test_design_tools_appear_for_eligible_document_context(self):
        self.assertTrue(resolve_tool_exposure(
            None, source_kinds={DRAWING},
            selected_source_kind=DRAWING)[TOOL_GROUP_DESIGN_CONSTRUCTION])
        # Nothing open, but the project genuinely holds drawings.
        self.assertTrue(resolve_tool_exposure(
            None, source_kinds={DRAWING})[TOOL_GROUP_DESIGN_CONSTRUCTION])

    def test_not_over_restricted_by_operating_environment_alone(self):
        """A proponent with drawings still gets drawing tools."""
        exposure = resolve_tool_exposure(
            DESIGN_BUILDER_PROPONENT, source_kinds={RFP, DRAWING},
            selected_source_kind=DRAWING)
        self.assertTrue(exposure[TOOL_GROUP_DESIGN_CONSTRUCTION])
        self.assertTrue(exposure[TOOL_GROUP_RFP_PROCUREMENT])

    # -- the Document Shop bench ---------------------------------------------

    def test_document_shop_withholds_project_wide_procurement_tools(self):
        exposure = resolve_tool_exposure(
            CLIENT_OWNER, source_kinds={RFP, DRAWING},
            selected_source_kind=DRAWING, workflow=WORKFLOW_DOCUMENT_SHOP)
        self.assertTrue(exposure[TOOL_GROUP_DOCUMENT_AS_READ])
        self.assertTrue(exposure[TOOL_GROUP_DESIGN_CONSTRUCTION])
        self.assertFalse(exposure[TOOL_GROUP_RFP_PROCUREMENT],
                         "the workshop bench is about this source, not the "
                         "project's procurement position")

    def test_document_shop_on_a_non_drawing_source_withholds_drawing_tools(self):
        exposure = resolve_tool_exposure(
            None, source_kinds={RFP}, selected_source_kind=RFP,
            workflow=WORKFLOW_DOCUMENT_SHOP)
        self.assertTrue(exposure[TOOL_GROUP_DOCUMENT_AS_READ])
        self.assertFalse(exposure[TOOL_GROUP_DESIGN_CONSTRUCTION])

    # -- the contract itself --------------------------------------------------

    def test_every_known_group_is_always_answered(self):
        for exposure in (resolve_tool_exposure(None),
                         resolve_tool_exposure(CLIENT_OWNER, source_kinds={DRAWING}),
                         resolve_tool_exposure(None, workflow=WORKFLOW_DOCUMENT_SHOP)):
            self.assertEqual(set(exposure), set(KNOWN_TOOL_GROUPS))

    def test_an_unknown_group_raises_rather_than_hiding_a_tool(self):
        exposure = resolve_tool_exposure(None)
        with self.assertRaises(ValueError):
            tool_group_available("no_such_group", exposure)

    def test_unmapped_toolbox_groups_default_to_general(self):
        """A tool nobody classified stays visible, rather than vanishing."""
        exposure = resolve_tool_exposure(None, source_kinds={RFP})
        self.assertTrue(tool_available("something-nobody-classified", exposure))
        self.assertTrue(tool_available("tasks", exposure))
        self.assertFalse(tool_available("drawing-understanding", exposure))

    def test_spin_is_general_and_never_gated_by_source_type(self):
        """Spin is the project-wide question every context legitimately asks."""
        self.assertEqual(TOOL_GROUP_BINDINGS["spin"], TOOL_GROUP_GENERAL)
        for kinds in ({RFP}, {DRAWING}, set()):
            exposure = resolve_tool_exposure(None, source_kinds=kinds)
            self.assertTrue(tool_available("spin", exposure))

    # -- nothing was duplicated ----------------------------------------------

    def test_existing_owner_proponent_capability_gating_still_works(self):
        sample = next(iter(CAPABILITY_REGISTRY))
        for environment in (CLIENT_OWNER, DESIGN_BUILDER_PROPONENT, None):
            self.assertIsInstance(capability_availability(sample, environment), bool)
        # And the procurement axis is untouched by the tool axis.
        self.assertTrue(capability_availability("rfi_respond", CLIENT_OWNER)
                        or capability_availability("rfi_respond", DESIGN_BUILDER_PROPONENT))

    def test_no_second_capability_framework(self):
        """Exposure lives beside the existing mechanism, not in a new service."""
        services = {p.name for p in (_REPO_ROOT / "services").glob("*.py")}
        for invented in ("realm_registry.py", "tool_registry.py",
                         "realm.py", "work_realm.py", "tool_exposure.py"):
            self.assertNotIn(invented, services)
        source = (_REPO_ROOT / "services" / "environment_capabilities.py").read_text(
            encoding="utf-8")
        self.assertIn("def resolve_tool_exposure", source)

    def test_forbidden_naming_is_absent(self):
        """The Product Owner excluded one family of naming. Prove it is gone.

        The needle is ASSEMBLED rather than written, because a test that spells
        a forbidden word finds itself - which is exactly what happened on the
        first run here, and what happened earlier in this codebase to a comment
        describing the data-ui-ref scanner. A scanner cannot tell prose from
        the thing it is looking for, so the search term must not be spellable
        in the file that searches.
        """
        needle = "med" + "ici"
        for folder, pattern in (("services", "*.py"), ("routes", "*.py"),
                                ("templates", "*.html"), ("tests", "*.py")):
            for path in (_REPO_ROOT / folder).rglob(pattern):
                if "__pycache__" in str(path) or path.name == Path(__file__).name:
                    continue
                self.assertNotIn(needle, path.read_text(encoding="utf-8").lower(),
                                 "%s uses forbidden naming" % path.name)
        # The guard must actually be capable of finding it.
        self.assertIn(needle, ("a " + needle + " workshop").lower())


class DocumentShopSurfaceTests(unittest.TestCase):
    """The rules, as the real application applies them."""

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_document_shop_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)

        def fake_parse(_parser, _raw, filename):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename,
                ingested_at=datetime.now(timezone.utc).isoformat(),
                parser_version="test")

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.app.app_context():
                self.document = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"x"), filename="owner.txt"),
                    self.app, operating_environment=CLIENT_OWNER, owner="owner",
                    project_name="Document Shop Fixture")
        self.project_id = self.document.project_id
        self.store = CaseWorkspaceStore(self.tmp)
        self.source = self.store.get(self.project_id).sources[0]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "owner"
            session["role"] = "read_only"
        return client

    def test_document_shop_entry_is_offered_on_a_real_source(self):
        body = self._client().get(
            "/projects/%s/workspace?source=%s" % (self.project_id, self.source["id"])
        ).get_data(as_text=True)
        self.assertIn('data-ui-ref="display.document.as-read"', body)
        self.assertIn("Document Shop", body)

    def test_document_shop_bench_renders_and_names_itself(self):
        body = self._client().get(
            "/projects/%s/workspace/sources/%s/understanding"
            % (self.project_id, self.source["id"])).get_data(as_text=True)
        self.assertIn("Document Shop &mdash; %s" % self.source["name"], body)
        self.assertIn("As-Read", body)
        self.assertIn("before Spin tests", body)

    def test_the_shop_uses_existing_project_data_with_no_duplicate_store(self):
        before = sorted(p.name for p in self.tmp.rglob("*.json"))
        self._client().get("/projects/%s/workspace/sources/%s/understanding"
                           % (self.project_id, self.source["id"]))
        after = sorted(p.name for p in self.tmp.rglob("*.json"))
        self.assertEqual(before, after, "the workshop must not create a store")
        workspace = self.store.get(self.project_id)
        for invented in ("document_shop", "realms", "tool_registry"):
            self.assertFalse(hasattr(workspace, invented))

    def test_project_isolation_is_unchanged(self):
        with patch.object(BHiveParser, "parse", lambda _p, _r, f: ParsedDocument(
                project_id=str(uuid.uuid4()), filename=f,
                ingested_at=datetime.now(timezone.utc).isoformat(),
                parser_version="test")):
            with self.app.app_context():
                other = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"y"), filename="other.txt"),
                    self.app, operating_environment=CLIENT_OWNER, owner="owner",
                    project_name="Other")
        response = self._client().get(
            "/projects/%s/workspace/sources/%s/understanding"
            % (other.project_id, self.source["id"]))
        self.assertIn(response.status_code, (302, 404))

    def test_composer_spine_is_not_forked(self):
        """One shared spine; context binding is not a second Composer."""
        services = {p.name for p in (_REPO_ROOT / "services").glob("*.py")}
        for invented in ("document_shop_composer.py", "realm_composer.py",
                         "composer_document_shop.py"):
            self.assertNotIn(invented, services)
        routes = [str(r) for r in self.app.url_map.iter_rules()]
        self.assertFalse([r for r in routes if "document-shop" in r and "composer" in r])

    def test_existing_routes_remain_compatible(self):
        client = self._client()
        for url in ("/projects/%s/workspace" % self.project_id,
                    "/projects/%s/workspace?source=%s" % (self.project_id, self.source["id"]),
                    "/projects/%s/workspace/sources/%s/understanding"
                    % (self.project_id, self.source["id"])):
            self.assertEqual(client.get(url).status_code, 200, url)
