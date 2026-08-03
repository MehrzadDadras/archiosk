"""
CLAUDE-P40-VW7B-QA1 - Real-Browser PDF Source Failure.

Real-browser acceptance review of pushed commit 0c6c520 reported: opening
"Nipigan Starter.pdf" correctly moved the Lists highlight from Chats to
the Document and correctly updated the breadcrumb/Toolbox, but Display
showed "This PDF could not be opened in the viewer: getDocument -
expected either data, range, or url parameter" and Thumbnails stayed at
its empty state.

Diagnosis, grounded directly against the vendored PDF.js source (never
assumed): static/js/pdf_viewer.js's own `mount()` and
`mountRememberedThumbnailsIfAny()` (CLAUDE-P40-LTH1) both called
`pdfjsLib.getDocument(url)` with `url` as a BARE STRING. The shipped
static/js/vendor/pdfjs/pdf.min.mjs (version 6.2.108, confirmed via that
directory's own README) does NOT normalize a bare string into
`{url: ...}` - its real `getDocument(t={})` immediately reads `t.url`,
which is `undefined` for a plain string, leaving neither `data`,
`range`, nor a resolved `url` set. The validation throw itself
("getDocument - expected either `data`, `range`, or `url`
parameter.", found verbatim in the shipped source) fires ASYNCHRONOUSLY
inside a `Promise.all([...]).then(...)` continuation once the PDF.js
worker responds - not synchronously at call time - which is exactly why
this was never caught by a synchronous smoke test and would fail
identically for EVERY PDF, not something specific to one fixture. This
predates CLAUDE-P40-VW7B entirely (mount()'s own call site is unchanged
since CLAUDE-P40-VW7A-QA2; mountRememberedThumbnailsIfAny() inherited
the identical bug when CLAUDE-P40-LTH1 added it) - VW7B never touched
pdf_viewer.js at all. Not a missing/invalid route, not a stale
restoration-state bug, not an invalid fixture, and not caused by LTH1's
own remembered-thumbnail LOGIC (only its unmodified copy-paste of the
already-broken call convention). Fix: both call sites now pass
`{ url: url }` - the real, verified contract this vendored build
actually requires - the smallest possible change, no data ever
modified.

No real browser tool exists in this environment - the fix itself was
verified by reading the actual shipped PDF.js source (not assumed or
guessed), including locating the literal throw statement and its
surrounding async validation branch; a Node.js empirical probe against
the same vendored file (stubbing just enough browser globals to import
it) additionally confirmed neither call form throws SYNCHRONOUSLY,
consistent with the throw being deferred into the async continuation
this diagnosis identifies. Coverage here is template/CSS/JS source and
rendered-HTML structural tests, the same practical ceiling this repo's
prior stages have already established.
"""
from __future__ import annotations

import io
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload
import services.case_workspace as cw

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PDF_VIEWER_JS_PATH = _REPO_ROOT / "static" / "js" / "pdf_viewer.js"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_vw7bqa1_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="vw7bqa1_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, project_name, filename="spec.pdf", content=b"content", owner="vw7bqa1_owner"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )
        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(content, filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client(self, username="vw7bqa1_owner", user_id=1):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = "admin"
        return client

    def _first_source(self, project_id):
        store = cw.CaseWorkspaceStore(self.tmp_dir)
        return store.get(project_id).sources[0]


class GetDocumentCallShapeTests(unittest.TestCase):
    """The actual fix - both real call sites, source-level."""

    def setUp(self):
        self.js = _PDF_VIEWER_JS_PATH.read_text(encoding="utf-8")

    def test_mount_passes_an_object_with_url_key(self):
        mount_fn = self.js[self.js.index("function mount("):self.js.index("function unmount(")]
        self.assertIn("pdfjsLib.getDocument({ url: url })", mount_fn)

    def test_remembered_thumbnails_passes_an_object_with_url_key(self):
        fn = self.js[self.js.index("function mountRememberedThumbnailsIfAny("):self.js.index("function navigateToDocumentPage(")]
        self.assertIn("pdfjsLib.getDocument({ url: match.file_url })", fn)

    def test_no_bare_string_getdocument_call_remains_anywhere(self):
        # Regression guard: every REAL call site is prefixed
        # "pdfjsLib." (the only way this file ever invokes it) - scoped
        # to that exact prefix specifically so this can never match
        # this file's own prose comments (which quote the vendored
        # source's bare "getDocument(t={})" signature verbatim while
        # explaining the bug this stage fixed).
        calls = re.findall(r"pdfjsLib\.getDocument\(([^)]*)\)", self.js)
        self.assertTrue(calls, "expected to find at least one real getDocument( call")
        for call_args in calls:
            self.assertTrue(
                call_args.strip().startswith("{"),
                f"getDocument() called with non-object argument: {call_args!r}",
            )

    def test_exactly_two_getdocument_call_sites_both_fixed(self):
        # Pins the count so a THIRD call site added later (e.g. a future
        # stage) is forced to make the same deliberate choice, not
        # silently copy-paste the old broken form from git history.
        self.assertEqual(self.js.count("pdfjsLib.getDocument("), 2)


class HonestFailureStateTests(_BaseTestCase):
    """The GENUINELY-missing-file case (a real, separate failure mode
    from the getDocument argument-shape bug) must still surface an
    honest error, never a silently-undefined state - unaffected by,
    and unchanged by, this correction."""

    def test_missing_file_on_disk_returns_404_from_source_route(self):
        doc = self._ingest("VW7B-QA1 Missing File Project", "spec.pdf")
        source = self._first_source(doc.project_id)
        import os
        os.remove(source["file_path"])
        client = self._client()
        resp = client.get(f"/projects/{doc.project_id}/workspace/sources/{source['id']}/file")
        self.assertEqual(resp.status_code, 404)

    def test_load_error_path_unaffected_by_this_fix(self):
        # showLoadError/clearThumbnails (the genuine-failure UI state)
        # are unchanged by this correction - still wired into mount()'s
        # own .catch(), still the honest fallback for ANY getDocument
        # rejection reason, not just the one this stage fixed.
        js = _PDF_VIEWER_JS_PATH.read_text(encoding="utf-8")
        mount_fn = js[js.index("function mount("):js.index("function unmount(")]
        self.assertIn(".catch(function (err) {", mount_fn)
        catch_block = mount_fn[mount_fn.index(".catch(function (err) {"):]
        self.assertIn("clearThumbnails();", catch_block)
        self.assertIn("showLoadError(canvasContainer, err);", catch_block)


class DomSourceValueGroundingTests(_BaseTestCase):
    """Rules out "missing/invalid route or DOM source value" as an
    ALTERNATIVE cause, with direct evidence rather than assumption -
    the rendered data-pdf-url was always correct; the bug was entirely
    in how pdf_viewer.js consumed it client-side."""

    def test_data_pdf_url_renders_a_real_non_empty_authorized_url(self):
        doc = self._ingest("VW7B-QA1 DOM Value Project", "spec.pdf")
        source = self._first_source(doc.project_id)
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?source={source['id']}").get_data(as_text=True)
        idx = body.index('id="document-viewer-pdf-canvas"')
        tag = body[body.rindex("<div", 0, idx):body.index(">", idx) + 1]
        match = re.search(r'data-pdf-url="([^"]+)"', tag)
        self.assertIsNotNone(match)
        pdf_url = match.group(1)
        self.assertTrue(pdf_url)
        self.assertIn(f"/projects/{doc.project_id}/workspace/sources/{source['id']}/file", pdf_url)

    def test_the_authorized_url_actually_resolves_to_the_real_file(self):
        doc = self._ingest("VW7B-QA1 DOM Value Project 2", "spec.pdf", content=b"%PDF-1.4 fake content")
        source = self._first_source(doc.project_id)
        client = self._client()
        resp = client.get(f"/projects/{doc.project_id}/workspace/sources/{source['id']}/file")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b"%PDF-1.4 fake content")

    def test_remembered_thumbnails_file_url_in_json_island_is_also_real(self):
        # LTH1's own is_pdf/file_url fields - confirms the REMEMBERED
        # path's source of truth was never the defect either.
        doc = self._ingest("VW7B-QA1 DOM Value Project 3", "spec.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        import json
        start = body.index('id="workspace-active-sources-data"')
        script_start = body.index(">", start) + 1
        script_end = body.index("</script>", script_start)
        payload = json.loads(body[script_start:script_end])
        self.assertEqual(len(payload), 1)
        self.assertTrue(payload[0]["is_pdf"])
        self.assertTrue(payload[0]["file_url"])


if __name__ == "__main__":
    unittest.main()
