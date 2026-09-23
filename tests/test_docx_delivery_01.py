"""CLAUDE-DOCX-DELIVERY-01 - a Word file is never offered inline.

Reported live: ARCHIOSK/GO-generated Word downloads showed "Blocked by your
organisation" in Chrome, on an unmanaged browser where ordinary .docx downloads
work.

WHAT WAS MEASURED BEFORE ANYTHING CHANGED, against the live host:

  /projects/<id>/workspace/export/findings.docx
      200, not redirected, 36,932 bytes, PK zip magic, exact .docx
      Content-Type, Content-Disposition: attachment, X-Content-Type-Options:
      nosniff, no CSP sandbox directive, no HTML body. Triggered by an anchor
      click it downloaded normally and the app's own toast reported
      "Report export completed".

  /projects/<id>/workspace/sources/<id>/file  and  ?download=1
      200 both ways, real zip bytes, correct .docx Content-Type; inline on the
      default, attachment with the flag.

NO SERVER DELIVERY DEFECT WAS FOUND, and the reported block was NOT
reproducible: a generated .docx downloaded normally in the same Chrome.

One candidate was examined and REJECTED rather than changed. The no-preview
card's "Open externally" links the route WITHOUT the download flag, so a Word
file - which no browser renders - is served inline into a new tab. That looked
like the one delivery path differing from the ones that work. It is deliberate:
tests/test_ca1d_river_po02_document_opening.py asserts exactly that shape, and
the card pairs it with a separate Download action that does force an
attachment. Collapsing the two would be a redesign of a tested decision, made
to fix something that could not be reproduced, so it was left alone and raised
instead.

What remains here is the delivery CONTRACT on the real download route, which
had no regression of its own: real OOXML bytes, never HTML under a .docx name,
attachment disposition, nosniff, no sandbox, and no redirect for an
authenticated caller.
"""
from __future__ import annotations

import io
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

DOCX_MIMETYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class _Workspace(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from services.bhive_parser import ParsedDocument
        from services.case_workspace import CaseWorkspaceStore
        from services.document_export import ExportDocument, build
        from services.requirements_registry import RequirementsRegistry

        self.tmp = Path(tempfile.mkdtemp(prefix="docx_delivery_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp)

        RequirementsRegistry(self.tmp).save(ParsedDocument(
            project_id="delivery", filename="Spec.pdf",
            ingested_at="2026-01-01T00:00:00+00:00"))

        # A real .docx on disk, written by the product's own writer.
        payload = build(ExportDocument(title="A Word file"), "docx").getvalue()
        self.stored = self.tmp / "generated.docx"
        self.stored.write_bytes(payload)

        store = CaseWorkspaceStore(self.tmp)
        self.workspace = store.get_or_create("delivery")
        source = store.add_source(
            self.workspace, name="Recovered document.docx",
            file_path=str(self.stored), kind="project_document")
        self.source_id = source["id"]

        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "admin"
            session["role"] = "admin"

    def _url(self, download=False):
        base = f"/projects/delivery/workspace/sources/{self.source_id}/file"
        return base + ("?download=1" if download else "")


class TheRealDownloadRouteDeliversAWordFile(_Workspace):
    def test_the_attachment_response_is_a_real_openable_docx(self):
        response = self.client.get(self._url(download=True))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, DOCX_MIMETYPE)
        self.assertTrue(
            response.headers["Content-Disposition"].lower().startswith("attachment"))
        # Openable by Word means a real OOXML package, not a renamed blob.
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertIn("word/document.xml", archive.namelist())

    def test_no_html_is_ever_served_under_a_docx_filename(self):
        """The failure mode that makes a browser refuse the file."""
        response = self.client.get(self._url(download=True))
        self.assertNotIn("html", response.mimetype)
        self.assertNotEqual(response.data[:1], b"<")
        self.assertEqual(response.data[:2], b"PK")

    def test_the_filename_reaches_the_browser_intact(self):
        response = self.client.get(self._url(download=True))
        disposition = response.headers["Content-Disposition"]
        self.assertIn("Recovered document.docx", disposition.replace("%20", " "))

    def test_content_type_is_not_sniffable(self):
        response = self.client.get(self._url(download=True))
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")

    def test_the_route_does_not_redirect_an_authenticated_download(self):
        """A redirect to a login page is HTML arriving under a .docx name."""
        response = self.client.get(self._url(download=True))
        self.assertEqual(response.status_code, 200)

    def test_an_unauthenticated_download_is_refused_not_served_as_html(self):
        anon = self.flask_app.test_client()
        response = anon.get(self._url(download=True))
        self.assertNotEqual(response.status_code, 200)


class NoSandboxOrPolicyIsImposedOnTheDownload(_Workspace):
    """Nothing in the response may tell a browser to distrust the file."""

    def test_the_response_carries_no_csp_sandbox(self):
        response = self.client.get(self._url(download=True))
        self.assertNotIn("sandbox", response.headers.get("Content-Security-Policy", ""))

    def test_the_page_offering_the_file_is_not_sandboxed_either(self):
        page = self.client.get("/projects/delivery/workspace")
        self.assertNotIn("sandbox", page.headers.get("Content-Security-Policy", ""))


class TheDownloadFilenameAlwaysCarriesTheExtension(_Workspace):
    """CLAUDE-DOWNLOAD-EXTENSION-01, found in chrome://downloads.

    The blocked entries were named "Existentialism 1" - no extension. A
    Source's `name` is a DISPLAY identity and services/ingestion.py numbers
    intake by position on purpose, so four uploaded PDFs become
    "Existentialism 1".."Existentialism 4" while the stored files stay .pdf.
    Content-Disposition carried the display name verbatim, and an extensionless
    download is a file the OS cannot type.
    """

    def _named(self, display_name, stored_suffix, payload=b"PKstub"):
        from services.case_workspace import CaseWorkspaceStore

        stored = self.tmp / ("stored" + stored_suffix)
        stored.write_bytes(payload)
        store = CaseWorkspaceStore(self.tmp)
        workspace = store.get_or_create("delivery")
        source = store.add_source(
            workspace, name=display_name, file_path=str(stored), kind="project_document")
        return source["id"]

    def _filename_of(self, source_id):
        response = self.client.get(
            f"/projects/delivery/workspace/sources/{source_id}/file?download=1")
        self.assertEqual(response.status_code, 200)
        return response.headers["Content-Disposition"]

    def test_the_reported_case_now_downloads_with_an_extension(self):
        """"Existentialism 1" over a stored .pdf."""
        disposition = self._filename_of(self._named("Existentialism 1", ".pdf"))
        self.assertIn("Existentialism 1.pdf", disposition.replace("%20", " "))

    def test_a_generated_word_file_ends_in_docx(self):
        disposition = self._filename_of(self._named("Recovered Existentialism", ".docx"))
        self.assertIn("Recovered Existentialism.docx", disposition.replace("%20", " "))

    def test_an_existing_extension_is_not_duplicated(self):
        disposition = self._filename_of(self._named("Report.docx", ".docx"))
        self.assertIn("Report.docx", disposition.replace("%20", " "))
        self.assertNotIn(".docx.docx", disposition)

    def test_a_differently_cased_extension_is_not_duplicated(self):
        disposition = self._filename_of(self._named("REPORT.DOCX", ".docx"))
        self.assertNotIn(".DOCX.docx", disposition)

    def test_unicode_and_spacing_survive(self):
        disposition = self._filename_of(self._named("Étude sur l'existence — 1", ".pdf"))
        decoded = disposition.encode("latin-1", "ignore").decode("utf-8", "ignore")
        self.assertTrue("Étude" in decoded or "%C3%89tude" in disposition,
                        "the accented name did not survive the header")
        self.assertTrue(disposition.endswith(".pdf") or ".pdf" in disposition)

    def test_the_mimetype_and_attachment_behaviour_are_unchanged(self):
        """The brief: fix the filename only."""
        source_id = self._named("Existentialism 1", ".pdf")
        response = self.client.get(
            f"/projects/delivery/workspace/sources/{source_id}/file?download=1")
        self.assertTrue(
            response.headers["Content-Disposition"].lower().startswith("attachment"))
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")

    def test_a_stored_file_with_no_extension_invents_none(self):
        disposition = self._filename_of(self._named("Mystery", ""))
        self.assertIn("Mystery", disposition)
        self.assertNotIn("Mystery.", disposition)


if __name__ == "__main__":
    unittest.main()
