"""CLAUDE-DOCSRC-03 - the uploaded filename survives the work-item rename.

WHAT WAS MEASURED BEFORE ANYTHING CHANGED (DOCSRC02, read-only, against the
real ingestion path in-process):

    after attach:  name='Existentialism and Human Emotions.pdf'
                   file_path='061a50b2...df_Existentialism_and_Human_Emotions.pdf'
    after rename:  name='Existentialism 1'
                   file_path unchanged

    report.source.name             = 'Existentialism 1'   <- all Document Review rendered
    report.source.origin_reference = None
    governance log  source_registered      {source_id, kind, document_id}
                    source_identity_updated {source_id}

Every carrier was closed. `name` was overwritten with no prior value retained;
`origin_reference` is not set on the Document Shop path; the staging manifest
holds the true filename but is explicitly transient; and `file_path` holds only
`secure_filename(original)` - a LOSSY derivative, measured turning
"Existentialism and Human Emotions.pdf" into "Existentialism_and_Human_Emotions.pdf"
and "Etude sur l'etre.pdf" into "Etude_sur_letre.pdf". The original was gone.

The fix is one immutable field written once at intake. What these tests defend:

  1. It is recorded, verbatim, by every intake path reachable from
     services/ingestion.py and from the founding registration.
  2. The work-item rename does not touch it - that is the whole reason it
     exists, and it is the assertion that fails first if anyone adds an
     `original_filename` parameter to update_source_identity.
  3. Document Review displays it BESIDE the work-item name, not instead of it.
  4. A Source that predates the field reads None and SAYS so. It is never
     back-filled from `file_path`: a sanitized derivative shown as "the
     original filename" is a false provenance claim, which
     governance/constitutional-invariants.md #3 forbids. This is the one that
     would pass just as well if the field were reconstructed instead of
     recorded, so it asserts the reconstruction is absent, not merely that
     something is displayed.
  5. Source identity, stored bytes, file_path and the project name are
     unchanged by any of it.
"""
from __future__ import annotations

import hashlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.datastructures import FileStorage

UPLOADED = "Existentialism and Human Emotions.pdf"
ACCENTED = "Etude sur l'etre.pdf"
PLAIN = "plain_name.pdf"


def _no_api_call(*args, **kwargs):  # pragma: no cover - a tripwire, not a stub
    raise AssertionError("BHiveParser.parse must never run in this test file.")


def _pdf(tag: bytes) -> bytes:
    return b"%PDF-1.4\n" + tag + b"\n%%EOF\n"


class _Intake(unittest.TestCase):
    """One real project, three real uploads, then the real work-item rename."""

    PROJECT = "docsrc03"

    def setUp(self):
        import app as app_module
        from services.bhive_parser import ParsedDocument
        from services.case_workspace import CaseWorkspaceStore
        from services.ingestion import document_source_payload
        from services.requirements_registry import RequirementsRegistry

        self.tmp = Path(tempfile.mkdtemp(prefix="docsrc03_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp)

        # The founding document, exactly as ingest_upload registers it: the
        # ParsedDocument carries the uploaded filename and get_or_create builds
        # the founding Source from `document_source_payload`.
        self.document = ParsedDocument(
            project_id=self.PROJECT, filename=UPLOADED,
            ingested_at="2026-01-01T00:00:00+00:00")
        RequirementsRegistry(self.tmp).save(self.document)

        self.store = CaseWorkspaceStore(self.tmp)
        self.workspace = self.store.get_or_create(
            self.PROJECT, register_document_source=document_source_payload(self.document))

    def _reload(self):
        self.workspace = self.store.get(self.PROJECT)
        return self.workspace

    def _attach(self, filenames):
        """The Document Shop batch path - services/ingestion.py:1208.

        Deliberately NOT a founding path: its own docstring records "no parse,
        no classification", so nothing here can reach BHiveParser or the API.
        """
        from services.ingestion import attach_document_shop_sources

        files = [FileStorage(stream=io.BytesIO(_pdf(name.encode("utf-8", "replace"))),
                             filename=name)
                 for name in filenames]
        with self.flask_app.app_context():
            results = attach_document_shop_sources(
                self.flask_app, self.workspace, files, owner="owner", actor="owner")
        self._reload()
        return results

    def _rename_into_work_items(self, project_name="Existentialism"):
        """routes/portal.py:3952 verbatim in shape: founding source first (found
        by its filename, because intake_order is None on the Source record),
        then the accepted attachments in intake order."""
        from services.ingestion import work_item_names

        ordered = [s["id"] for s in self._reload().sources if not s.get("removed_at")]
        names = work_item_names(project_name, len(ordered))
        for source_id, display_name in zip(ordered, names):
            self.store.update_source_identity(
                self.workspace, source_id, actor="owner", name=display_name)
        return self._reload()

    def _sources(self):
        return [s for s in self._reload().sources if not s.get("removed_at")]

    def _by_original(self, filename):
        match = [s for s in self._sources() if s.get("original_filename") == filename]
        self.assertEqual(len(match), 1, "expected exactly one Source uploaded as %r" % filename)
        return match[0]


class TheUploadedFilenameIsRecordedAtIntake(_Intake):
    def test_the_founding_source_records_the_uploaded_filename(self):
        founding = self._sources()[0]
        self.assertEqual(founding["original_filename"], UPLOADED)

    def test_the_document_shop_batch_path_records_it(self):
        self._attach([ACCENTED, PLAIN])
        self.assertEqual(
            {s.get("original_filename") for s in self._sources()},
            {UPLOADED, ACCENTED, PLAIN})

    def test_it_is_recorded_verbatim_not_sanitized(self):
        """The exact substitution that made the original unrecoverable."""
        from werkzeug.utils import secure_filename

        self._attach([ACCENTED])
        source = self._by_original(ACCENTED)
        self.assertEqual(source["original_filename"], ACCENTED)
        self.assertNotEqual(source["original_filename"], secure_filename(ACCENTED))
        self.assertIn(" ", source["original_filename"])
        self.assertIn("'", source["original_filename"])

    def test_the_data_room_path_records_the_unsanitized_name(self):
        """services/ingestion.py:1502, where `name` is deliberately safe_name.

        reconcile_data_room_upload registers into an EXISTING project, so it
        never reaches ingest_upload/BHiveParser.parse; `_register_source_content`
        extracts locally through `parser._extract`. `parse` is stubbed with a
        tripwire anyway, because a hermetic test must not rest on that staying
        true - see CLAUDE.md's 8.5-hour un-mocked ingest.
        """
        from unittest.mock import patch

        from services.bhive_parser import BHiveParser
        from services.ingestion import reconcile_data_room_upload

        name = "Etude sur l'etre.txt"
        files = [FileStorage(stream=io.BytesIO(b"An uploaded text record."), filename=name)]
        with self.flask_app.app_context():
            with patch.object(BHiveParser, "parse", _no_api_call):
                results = reconcile_data_room_upload(
                    files, ["Data Room/" + name], self.PROJECT, self.flask_app,
                    actor="owner", role="admin")

        self.assertEqual([r["status"] for r in results], ["added"], results)
        source = next((s for s in self._sources()
                       if s.get("original_filename") == name), None)
        self.assertIsNotNone(source, "the Data Room path did not record the filename")
        self.assertNotEqual(source["name"], name,
                            "this path stores secure_filename as the display name - "
                            "if that changed, this test is asserting the wrong thing")

    def test_every_ingestion_intake_path_passes_the_unsanitized_filename(self):
        """The regression that would reintroduce the defect silently.

        Two of the three call sites sit beside a `safe_name` local, which is
        what the line above them passes as `name`. Passing it here too would
        look right, read right, and persist the sanitized form - so this reads
        the actual argument rather than trusting the cases above to keep
        covering every site as more are added.
        """
        import ast

        source_file = Path(__file__).resolve().parent.parent / "services" / "ingestion.py"
        tree = ast.parse(source_file.read_text(encoding="utf-8"))
        sites = [node for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and node.func.attr == "add_source"]
        self.assertEqual(len(sites), 3, "the set of intake paths changed")

        for site in sites:
            passed = {kw.arg: kw.value for kw in site.keywords}
            self.assertIn("original_filename", passed,
                          "services/ingestion.py:%d registers a Source without "
                          "recording the uploaded filename" % site.lineno)
            value = passed["original_filename"]
            self.assertIsInstance(value, ast.Name)
            self.assertEqual(value.id, "filename",
                             "services/ingestion.py:%d does not pass the "
                             "unsanitized `filename`" % site.lineno)


class TheWorkItemRenameDoesNotTouchIt(_Intake):
    """The reason the field exists. This fails first if it becomes mutable."""

    def test_renaming_into_work_items_leaves_the_uploaded_filename_intact(self):
        self._attach([ACCENTED, PLAIN])
        before = {s["id"]: s["original_filename"] for s in self._sources()}

        self._rename_into_work_items()

        after = {s["id"]: s.get("original_filename") for s in self._sources()}
        self.assertEqual(before, after)

    def test_the_reported_case_still_knows_what_it_was(self):
        """"Existentialism 1" can name the file it came from."""
        self._attach([ACCENTED, PLAIN])
        self._rename_into_work_items()

        displayed = {s["name"] for s in self._sources()}
        self.assertIn("Existentialism 1", displayed)
        renamed = next(s for s in self._sources() if s["name"] == "Existentialism 1")
        self.assertEqual(renamed["original_filename"], UPLOADED)

    def test_update_source_identity_has_no_parameter_for_it(self):
        """An intake fact a later rename can edit is not an intake fact."""
        import inspect

        from services.case_workspace import CaseWorkspaceStore

        signature = inspect.signature(CaseWorkspaceStore.update_source_identity)
        self.assertNotIn("original_filename", signature.parameters)

    def test_every_other_identity_update_leaves_it_alone(self):
        """Not just `name` - the whole identity-update surface."""
        self._attach([PLAIN])
        source = self._by_original(PLAIN)

        self.store.update_source_identity(
            self.workspace, source["id"], actor="owner",
            name="Renamed", document_id="A-101", revision="3",
            issue_date="2026-02-02", issuer="Someone", document_status="ISSUED",
            file_hash="0" * 64, mime_type="application/pdf", size_bytes=99)

        self.assertEqual(self._by_original(PLAIN)["original_filename"], PLAIN)


class ItIsRecordedNeverReconstructed(_Intake):
    """The assertion a back-fill from file_path would fail."""

    def test_a_source_registered_without_one_reads_none(self):
        source = self.store.add_source(
            self.workspace, name="Text Record", file_path=None,
            kind="text_record", actor="owner")
        self.assertIsNone(source["original_filename"])

    def test_a_legacy_source_record_loads_and_reads_none(self):
        """Sources persist as plain dicts, so a record written before this field
        existed simply has no key - the CLAUDE-P40-C shape. Reading it must not
        raise, and must not invent a value."""
        workspace = self._reload()
        legacy = dict(workspace.sources[0])
        legacy.pop("original_filename")
        legacy["id"] = "legacy-source"
        workspace.sources.append(legacy)
        self.store.save(workspace)

        reloaded = next(s for s in self.store.get(self.PROJECT).sources
                        if s["id"] == "legacy-source")
        self.assertNotIn("original_filename", reloaded)
        self.assertIsNone(reloaded.get("original_filename"))

    def test_nothing_derives_it_from_the_stored_file_name(self):
        """file_path keeps a sanitized copy. If anyone ever back-fills from it,
        this Source would read the underscored form instead of None."""
        from werkzeug.utils import secure_filename

        source = self.store.add_source(
            self.workspace, name="Display only",
            file_path=str(self.tmp / ("deadbeef_" + secure_filename(ACCENTED))),
            kind="project_document", actor="owner")

        self.assertIsNone(source["original_filename"])
        self.assertIn(secure_filename(ACCENTED), source["file_path"])


class DocumentReviewShowsItBesideTheWorkItemName(_Intake):
    def setUp(self):
        super().setUp()
        self._attach([ACCENTED, PLAIN])
        self._rename_into_work_items()
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "admin"
            session["role"] = "admin"
            # routes/workspace.py's source_review calls _require_developer_tools()
            # before it renders. The gate is not what is under test here.
            session["developer_mode"] = True

    def _filename_line(self, html):
        """The rendered "Original filename: ..." line, and only that line.

        Asserting over the whole page would be wrong here: this project's
        display name IS the founding document's filename, so it appears in the
        shell navigation for entirely legitimate reasons. A page-wide
        assertNotIn would fail on that and prove nothing about this line.
        """
        import re

        match = re.search(r"<p>Original filename:(.*?)</p>", html, re.S)
        self.assertIsNotNone(match, "Document Review rendered no Original filename line")
        return re.sub(r"<[^>]+>", "", match.group(1)).strip()

    def _review_html(self, source_id):
        response = self.client.get(
            f"/projects/{self.PROJECT}/sources/{source_id}/review")
        self.assertEqual(response.status_code, 200,
                         "Document Review did not render (%s)" % response.status_code)
        return response.get_data(as_text=True)

    def test_the_uploaded_filename_appears_on_the_page(self):
        html = self._review_html(self._by_original(UPLOADED)["id"])
        self.assertIn(UPLOADED, html)

    def test_the_work_item_name_is_still_there_too(self):
        """Beside, not instead of. The heading is the work item."""
        source = self._by_original(UPLOADED)
        html = self._review_html(source["id"])
        self.assertIn(source["name"], html)
        self.assertIn("Source review: %s" % source["name"], html)

    def test_the_report_carries_it_to_the_template(self):
        from services import document_examination as dx

        report = dx.inspect_source_review(self._reload(), self._by_original(ACCENTED)["id"])
        self.assertEqual(report["source"]["original_filename"], ACCENTED)

    def test_the_label_and_value_render_together(self):
        """CLAUDE-DOCUI-04: the wording is the deliverable, so assert it whole."""
        source = self._by_original(UPLOADED)
        self.assertIn("Original filename: %s" % UPLOADED, self._review_html(source["id"]))

    def test_a_source_without_one_says_so_rather_than_guessing(self):
        from werkzeug.utils import secure_filename

        source = self.store.add_source(
            self.workspace, name="Legacy document",
            file_path=str(self.tmp / ("deadbeef_" + secure_filename(ACCENTED))),
            kind="project_document", actor="owner")

        html = self._review_html(source["id"])
        self.assertIn("Original filename: [Not recorded]", html)
        self.assertNotIn(secure_filename(ACCENTED), html)
        self.assertNotIn("Etude", html)

    def test_a_source_persisted_before_the_field_existed_renders_not_recorded(self):
        """CLAUDE-DOCUI-04, the actual legacy shape: a stored dict with NO
        `original_filename` key at all, not one whose key is None. Sources are
        persisted as plain dicts and never rehydrated through Source(**d), so
        this is what every pre-existing record on the live host looks like."""
        from werkzeug.utils import secure_filename

        workspace = self._reload()
        legacy = dict(workspace.sources[0])
        legacy.pop("original_filename")
        legacy["id"] = "legacy-render"
        legacy["name"] = "Existentialism 1"
        legacy["file_path"] = str(self.tmp / ("deadbeef_" + secure_filename(UPLOADED)))
        workspace.sources.append(legacy)
        self.store.save(workspace)

        html = self._review_html("legacy-render")
        self.assertIn("Original filename: [Not recorded]", html)
        self.assertIn("Source review: Existentialism 1", html)
        self.assertNotIn(secure_filename(UPLOADED), html)

    def test_the_legacy_line_offers_no_reconstructed_alternative(self):
        """Nothing lossy is presented as a substitute - not the sanitized stored
        name, not the work-item name relabelled as a filename."""
        from werkzeug.utils import secure_filename

        workspace = self._reload()
        legacy = dict(workspace.sources[0])
        legacy.pop("original_filename")
        legacy["id"] = "legacy-no-substitute"
        legacy["name"] = "Existentialism 1"
        legacy["file_path"] = str(self.tmp / ("deadbeef_" + secure_filename(UPLOADED)))
        workspace.sources.append(legacy)
        self.store.save(workspace)

        line = self._filename_line(self._review_html("legacy-no-substitute"))
        self.assertEqual(line, "[Not recorded]")
        self.assertNotIn("Existentialism 1", line)
        self.assertNotIn(secure_filename(UPLOADED), line)
        self.assertNotIn(UPLOADED, line)

    def test_rendering_a_legacy_source_does_not_write_anything_back(self):
        """Reading the page is not a migration. The stored record keeps having
        no key, and no byte on disk changes."""
        import hashlib
        import json

        workspace = self._reload()
        legacy = dict(workspace.sources[0])
        legacy.pop("original_filename")
        legacy["id"] = "legacy-untouched"
        workspace.sources.append(legacy)
        self.store.save(workspace)

        record_path = self.tmp / ("%s.workspace.json" % self.PROJECT)
        self.assertTrue(record_path.exists(), record_path)
        before = hashlib.sha256(record_path.read_bytes()).hexdigest()

        self._review_html("legacy-untouched")

        self.assertEqual(hashlib.sha256(record_path.read_bytes()).hexdigest(), before,
                         "rendering Document Review rewrote the workspace record")
        stored = json.loads(record_path.read_text(encoding="utf-8"))
        reloaded = next(s for s in stored["sources"] if s["id"] == "legacy-untouched")
        self.assertNotIn("original_filename", reloaded)


class NothingElseAboutTheSourceChanged(_Intake):
    """The brief: persist and display, change nothing else."""

    def setUp(self):
        super().setUp()
        self._attach([ACCENTED, PLAIN])
        self.before = {s["id"]: dict(s) for s in self._sources()}
        self.digests = {
            s["id"]: hashlib.sha256(Path(s["file_path"]).read_bytes()).hexdigest()
            for s in self._sources() if s.get("file_path") and Path(s["file_path"]).exists()}
        self._rename_into_work_items()

    def test_source_ids_are_unchanged(self):
        self.assertEqual({s["id"] for s in self._sources()}, set(self.before))

    def test_stored_file_paths_are_unchanged(self):
        for source in self._sources():
            self.assertEqual(source["file_path"], self.before[source["id"]]["file_path"])

    def test_the_stored_bytes_are_unchanged(self):
        self.assertTrue(self.digests, "no stored files to compare - the test proves nothing")
        for source_id, digest in self.digests.items():
            path = Path(self._by_id(source_id)["file_path"])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

    def test_file_hashes_are_unchanged(self):
        for source in self._sources():
            self.assertEqual(source.get("file_hash"), self.before[source["id"]].get("file_hash"))

    def test_the_project_name_is_untouched(self):
        from services.requirements_registry import RequirementsRegistry

        document = RequirementsRegistry(self.tmp).get(self.PROJECT)
        self.assertEqual(document.filename, UPLOADED)

    def _by_id(self, source_id):
        return next(s for s in self._sources() if s["id"] == source_id)


if __name__ == "__main__":
    unittest.main()
