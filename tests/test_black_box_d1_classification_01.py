"""CLAUDE-BLACK-BOX-D1-01: a Source may exist before its type is known.

UNKNOWN SOURCE -> OBSERVE -> CLASSIFY -> THEN determine type.

Every founding Source used to be labelled `rfq_rfp_document` by a constant in
`CaseWorkspaceStore.get_or_create`. That was TRUE of every container that could
exist when it was written - the RFQ/RFP pipeline was the only way one came into
being - and became false the moment a Black Box could receive material whose
type nobody had established. It was never an inference failure: nothing ever
looked at the document.

Three tests carry the weight:

`test_no_founding_format_becomes_rfp_in_a_black_box` - the correction itself,
across every supported founding format, asserting the extension is not consulted.

`test_unclassified_activates_no_specialised_tooling` - the safety direction. An
unclassified Source must not open doors; "machine inference never becomes
authority" applied to a type nobody has established.

`test_a_conventional_project_still_founds_on_its_rfq_rfp_document` - the
regression this correction must not cause.
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
    CONTAINER_STATE_BLACK_BOX, CaseWorkspaceStore, SOURCE_DOMAIN_UNKNOWN,
    SOURCE_KIND_DRAWING, SOURCE_KIND_RFQ_RFP_DOCUMENT, SOURCE_KIND_UNCLASSIFIED,
)
from services.environment_capabilities import (
    CLIENT_OWNER, DESIGN_BUILDER_PROPONENT, TOOL_GROUP_DESIGN_CONSTRUCTION,
    TOOL_GROUP_DOCUMENT_AS_READ, TOOL_GROUP_RFP_PROCUREMENT,
    resolve_tool_exposure, tool_available,
)
from services.ingestion import UploadError, ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent

FOUNDING_FORMATS = ("notes.txt", "sheet.pdf", "spec.docx", "data.csv", "readme.md")


def _fake_parse(_parser, _raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test")


class SourceKindVocabularyTests(unittest.TestCase):
    """The axis separation, asserted directly."""

    def test_unclassified_is_its_own_kind_not_a_borrowed_one(self):
        self.assertEqual(SOURCE_KIND_UNCLASSIFIED, "unclassified")
        for borrowed in (SOURCE_KIND_RFQ_RFP_DOCUMENT, SOURCE_KIND_DRAWING,
                         SOURCE_DOMAIN_UNKNOWN):
            self.assertNotEqual(SOURCE_KIND_UNCLASSIFIED, borrowed)

    def test_kind_and_domain_remain_different_axes(self):
        """SOURCE_DOMAIN_UNKNOWN answers WHERE FROM; this answers WHAT IS IT.

        Reusing the domain value would have collapsed two independent questions
        into one field, and a Source whose origin is unknown is not the same
        fact as a Source whose type is unestablished.
        """
        self.assertNotEqual(SOURCE_KIND_UNCLASSIFIED, SOURCE_DOMAIN_UNKNOWN)

    def test_no_closed_source_kind_registry_was_introduced(self):
        import services.case_workspace as kernel
        self.assertFalse(hasattr(kernel, "KNOWN_SOURCE_KINDS"),
                         "Source.kind is open-world by existing design; this "
                         "tranche adds a value, never a closed list")

    def test_unclassified_activates_no_specialised_tooling(self):
        exposure = resolve_tool_exposure(
            None, source_kinds={SOURCE_KIND_UNCLASSIFIED},
            selected_source_kind=SOURCE_KIND_UNCLASSIFIED)
        self.assertFalse(exposure[TOOL_GROUP_RFP_PROCUREMENT],
                         "an unestablished type must not open procurement")
        self.assertFalse(exposure[TOOL_GROUP_DESIGN_CONSTRUCTION],
                         "an unestablished type must not open drawing tooling")
        self.assertFalse(tool_available("requirements", exposure))
        self.assertFalse(tool_available("rfi", exposure))
        self.assertFalse(tool_available("drawing-understanding", exposure))

    def test_specialised_tooling_still_follows_a_real_kind(self):
        """The correction must not have disabled exposure generally."""
        drawing = resolve_tool_exposure(
            None, source_kinds={SOURCE_KIND_DRAWING},
            selected_source_kind=SOURCE_KIND_DRAWING)
        rfp = resolve_tool_exposure(
            None, source_kinds={SOURCE_KIND_RFQ_RFP_DOCUMENT},
            selected_source_kind=SOURCE_KIND_RFQ_RFP_DOCUMENT)
        self.assertTrue(drawing[TOOL_GROUP_DESIGN_CONSTRUCTION])
        self.assertTrue(rfp[TOOL_GROUP_RFP_PROCUREMENT])


class FoundingSourceKindTests(unittest.TestCase):
    """Through the real ingest path, both container kinds."""

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_d1_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ingest(self, name, **kwargs):
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                return ingest_upload(
                    FileStorage(stream=io.BytesIO(b"x"), filename=name),
                    self.app, owner="owner", **kwargs)

    def _founding_kind(self, document):
        workspace = self.store.get(document.project_id)
        return workspace.sources[0]["kind"]

    # -- the correction -------------------------------------------------------

    def test_no_founding_format_becomes_rfp_in_a_black_box(self):
        """Every supported founding format, and the extension is not consulted."""
        for filename in FOUNDING_FORMATS:
            with self.subTest(filename=filename):
                document = self._ingest(
                    filename, operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="BB %s %s" % (filename, uuid.uuid4().hex[:6]))
                self.assertEqual(self._founding_kind(document),
                                 SOURCE_KIND_UNCLASSIFIED,
                                 "%s must not acquire a document type merely by "
                                 "founding a container" % filename)

    def test_a_black_box_founding_source_opens_nothing_by_its_kind(self):
        document = self._ingest(
            "notes.txt", operating_environment=None,
            container_state=CONTAINER_STATE_BLACK_BOX, project_name="BB tools")
        workspace = self.store.get(document.project_id)
        kinds = {s["kind"] for s in workspace.sources}
        exposure = resolve_tool_exposure(
            workspace.operating_environment, source_kinds=kinds,
            container_state=workspace.container_state)
        self.assertFalse(exposure[TOOL_GROUP_RFP_PROCUREMENT])
        self.assertFalse(exposure[TOOL_GROUP_DESIGN_CONSTRUCTION])
        self.assertTrue(exposure[TOOL_GROUP_DOCUMENT_AS_READ],
                        "document work is what an unclassified source is FOR")

    # -- the regression it must not cause ------------------------------------

    def test_a_conventional_project_still_founds_on_its_rfq_rfp_document(self):
        for environment in (CLIENT_OWNER, DESIGN_BUILDER_PROPONENT):
            with self.subTest(environment=environment):
                document = self._ingest(
                    "rfp.pdf", operating_environment=environment,
                    project_name="Project %s" % uuid.uuid4().hex[:6])
                self.assertEqual(self._founding_kind(document),
                                 SOURCE_KIND_RFQ_RFP_DOCUMENT)

    def test_conventional_project_procurement_exposure_is_unchanged(self):
        document = self._ingest("rfp.pdf", operating_environment=CLIENT_OWNER,
                                project_name="Procurement Intact")
        workspace = self.store.get(document.project_id)
        exposure = resolve_tool_exposure(
            workspace.operating_environment,
            source_kinds={s["kind"] for s in workspace.sources},
            container_state=workspace.container_state)
        self.assertTrue(exposure[TOOL_GROUP_RFP_PROCUREMENT])

    def test_owner_and_proponent_semantics_are_untouched(self):
        for environment in (CLIENT_OWNER, DESIGN_BUILDER_PROPONENT):
            with self.subTest(environment=environment):
                document = self._ingest(
                    "rfp.pdf", operating_environment=environment,
                    project_name="Env %s" % uuid.uuid4().hex[:6])
                workspace = self.store.get(document.project_id)
                self.assertEqual(workspace.operating_environment, environment)
                self.assertIsNotNone(workspace.lifecycle_stage)
                self.assertIsNone(workspace.container_state)

    # -- the axes stay separate ----------------------------------------------

    def test_source_domain_remains_independent_of_kind(self):
        document = self._ingest(
            "notes.txt", operating_environment=None,
            container_state=CONTAINER_STATE_BLACK_BOX, project_name="BB domain")
        source = self.store.get(document.project_id).sources[0]
        self.assertEqual(source["kind"], SOURCE_KIND_UNCLASSIFIED)
        self.assertEqual(source["source_domain"], SOURCE_DOMAIN_UNKNOWN)
        self.assertIn("source_domain", source)
        self.assertIn("kind", source)

    # -- what this tranche deliberately did NOT do ---------------------------

    def test_no_parser_guessing_was_introduced(self):
        """The kind is stated by the caller that knows, never derived.

        Asserted structurally: the ingestion module must not consult a file
        extension when choosing a founding kind. If a future change starts
        inferring, this fails.
        """
        source = (_REPO_ROOT / "services" / "ingestion.py").read_text(encoding="utf-8")
        window = source[source.index("def document_source_payload"):]
        window = window[:window.index("def _validated_source_domain")]
        for inference in (".pdf", ".docx", ".txt", ".csv", ".md", "endswith"):
            self.assertNotIn(inference, window,
                             "founding kind must not be inferred from a filename")

    def test_spreadsheet_founding_refusal_is_unchanged(self):
        with self.assertRaises(UploadError) as caught:
            self._ingest("schedule.xlsx", operating_environment=None,
                         container_state=CONTAINER_STATE_BLACK_BOX,
                         project_name="BB xlsx")
        self.assertIn("spreadsheet", str(caught.exception).lower())

    def test_no_upload_format_was_widened(self):
        allowed = self.app.config["ALLOWED_UPLOAD_EXTENSIONS"]
        for image in (".jpg", ".jpeg", ".png", ".tif", ".tiff"):
            self.assertNotIn(image, allowed)
        self.assertEqual(set(allowed),
                         {".pdf", ".docx", ".txt", ".csv", ".md", ".xlsx"})

    def test_the_wording_leak_was_left_to_d2_and_d2_fixed_it(self):
        """Originally asserted the leak SURVIVED D1 - proof the tranches were
        not mixed. CLAUDE-BLACK-BOX-D2-01 has since corrected the wording, so
        the assertion is inverted rather than deleted: the handoff is the fact
        worth keeping, and this now guards the project vocabulary from
        returning.
        """
        source = (_REPO_ROOT / "services" / "ingestion.py").read_text(encoding="utf-8")
        self.assertNotIn("cannot be a project's founding document", source)
        self.assertIn("cannot be used as a founding document", source)

    def test_no_second_decision_model_for_classification(self):
        """The progressive-classification SEAM only - nothing implemented.

        A later tranche may propose a type and have a human confirm it. That
        must reuse the existing As-Read proposition machinery, not a parallel
        one, so this asserts no classification decision service appeared.
        """
        services = {p.name for p in (_REPO_ROOT / "services").glob("*.py")}
        for invented in ("source_classification.py", "classification.py",
                         "kind_proposal.py", "document_type.py"):
            self.assertNotIn(invented, services)
