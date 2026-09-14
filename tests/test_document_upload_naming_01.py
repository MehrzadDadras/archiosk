"""CLAUDE-DOCUMENT-UPLOAD-01 - the page says what the person is doing.

    PUBLIC LANGUAGE MAY CHANGE.  CANONICAL IDENTITY MUST NOT.

"Document Shop" described a place. "Document Upload" describes an act, and the
act is what the person came to perform. The rename is therefore deliberately
SHALLOW: five public labels, and not one route, blueprint endpoint, template
filename, `data-ui-ref`, governance record or internal identifier.

The other half is the project name. It was optional with a placeholder, and
optional meant `ingest_upload` fell back to `_resolve_project_code(app,
project_name or filename)` - so an unnamed upload silently took its identity
from whatever a phone called the photo. That was a hidden default, already
live, and it is what section 3 removes.
"""
from __future__ import annotations

import io
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from services import ingestion
from services.bhive_parser import BHiveParser
from services.case_workspace import CaseWorkspaceStore

INTAKE_HTML = Path("templates/document_shop_intake.html").read_text(encoding="utf-8")
HELP_HTML = Path("templates/help/file_types_and_limits.html").read_text(encoding="utf-8")
PROJECTS_HTML = Path("templates/projects.html").read_text(encoding="utf-8")
MENU_HTML = Path("templates/_app_menu.html").read_text(encoding="utf-8")


def _handler_source() -> str:
    """Just the `document_shop_intake` handler body, isolated from the module.

    Scoped so an assertion about this route cannot pass or fail because of what
    some other route in a 7,000-line blueprint happens to contain.
    """
    source = Path("routes/portal.py").read_text(encoding="utf-8")
    after = source.split("def document_shop_intake()")[1]
    return after.split("\ndef ")[0]


def _markup(html: str) -> str:
    """The template with Jinja comments stripped.

    A `{# CLAUDE-… #}` block explaining why a label changed is not a label, and
    scanning raw source for a banned phrase matches the explanation of the ban.
    This programme has produced eight such false positives; this strips them.
    """
    return re.sub(r"\{#.*?#\}", "", html, flags=re.S)


# ============================================================================
# A, B - THE PUBLIC LABEL
# ============================================================================

class ThePublicLabelSaysUpload(unittest.TestCase):
    """A and B, against the markup rather than the comments."""

    def test_a_the_page_title_and_heading_say_document_upload(self):
        markup = _markup(INTAKE_HTML)
        self.assertIn("{% block title %}Document Upload &mdash; Archiosk{% endblock %}",
                      markup)
        self.assertIn(">Document Upload</h1>", markup)

    def test_b_the_obsolete_label_is_absent_from_this_surface(self):
        self.assertNotIn("Document Shop", _markup(INTAKE_HTML))

    def test_a_the_navigation_entries_pointing_here_say_document_upload(self):
        for html, name in ((PROJECTS_HTML, "projects.html"),
                           (MENU_HTML, "_app_menu.html")):
            markup = _markup(html)
            anchor = [line for line in markup.splitlines()
                      if "portal.document_shop_intake" in line]
            self.assertTrue(anchor, name)
            for line in anchor:
                with self.subTest(template=name):
                    self.assertIn("Document Upload", line)
                    self.assertNotIn(">Document Shop", line)

    def test_the_help_copy_reads_naturally_after_the_rename(self):
        markup = _markup(HELP_HTML)
        self.assertIn("Uploading a document", markup)
        self.assertNotIn("Bringing a document to the Document Shop", markup)

    def test_the_help_copy_no_longer_contradicts_the_required_field(self):
        """It said "Naming the work is optional", which is now false."""
        markup = _markup(HELP_HTML)
        self.assertNotIn("Naming the work is optional", markup)
        self.assertNotIn("listed under its own filename", markup)
        self.assertIn("name of project", markup.lower())

    def test_the_public_action_is_upload_not_indexing(self):
        """Section 9. Indexing is a stage after the files arrive."""
        markup = _markup(INTAKE_HTML)
        for banned in ("Indexing", "Document Index", "Document Intake"):
            self.assertNotIn(banned, markup, banned)


class CanonicalIdentityWasNotRenamed(unittest.TestCase):
    """Section 2 and 11 - the half of this tranche that is about NOT changing."""

    def test_the_route_path_is_unchanged(self):
        import app as app_module
        flask_app = app_module.create_app("testing")
        rules = {str(rule) for rule in flask_app.url_map.iter_rules()}
        self.assertIn("/document-shop", rules)

    def test_the_endpoint_name_is_unchanged(self):
        import app as app_module
        flask_app = app_module.create_app("testing")
        endpoints = {rule.endpoint for rule in flask_app.url_map.iter_rules()}
        self.assertIn("portal.document_shop_intake", endpoints)
        self.assertIn("portal.document_shop_jobs", endpoints)

    def test_the_template_filenames_are_unchanged(self):
        for name in ("document_shop_intake.html", "document_shop_jobs.html",
                     "document_shop_result.html"):
            self.assertTrue(Path("templates", name).exists(), name)

    def test_every_data_ui_ref_is_unchanged(self):
        """A ref is a registry key and a test anchor, not a label."""
        for ref in ("document-shop.page-title", "document-shop.file",
                    "document-shop.accepted-formats", "document-shop.name",
                    "document-shop.submit", "document-shop.intake"):
            self.assertIn('data-ui-ref="%s"' % ref, INTAKE_HTML, ref)

    def test_the_internal_entitlement_helper_is_unchanged(self):
        from services.auth import user_can_create_document_shop_container
        self.assertTrue(callable(user_can_create_document_shop_container))

    def test_the_internal_attach_function_is_unchanged(self):
        self.assertTrue(callable(ingestion.attach_document_shop_sources))

    def test_surfaces_that_are_not_the_upload_page_keep_their_own_name(self):
        """Section 8. The per-source bench, the jobs list and the result page
        are different surfaces, and renaming them was not asked for."""
        bench = _markup(Path("templates/case_workspace.html").read_text(encoding="utf-8"))
        self.assertIn("Document Shop", bench)
        jobs = _markup(Path("templates/document_shop_jobs.html").read_text(encoding="utf-8"))
        self.assertIn("Document Shop Jobs", jobs)
        result = _markup(Path("templates/document_shop_result.html").read_text(encoding="utf-8"))
        self.assertIn("Document Shop", result)


# ============================================================================
# C, D, E - THE PROJECT NAME FIELD
# ============================================================================

class TheProjectNameIsRequired(unittest.TestCase):
    """C, D, E - the markup half; the route half is enforced below."""

    def test_c_the_field_is_labelled_name_of_project_and_marked_required(self):
        markup = _markup(INTAKE_HTML)
        self.assertIn("Name of project", markup)
        self.assertNotIn("Name for this work (optional)", markup)
        field = [line for line in markup.splitlines()
                 if 'id="document-shop-name"' in line or 'required' in line]
        self.assertTrue(any("required" in line for line in field))

    def test_c_the_required_state_is_announced_to_assistive_technology(self):
        markup = _markup(INTAKE_HTML)
        self.assertIn('aria-required="true"', markup)
        self.assertIn("(required)", markup)

    def test_e_there_is_no_placeholder_example(self):
        """A placeholder on a required identity field looks like a value, is not
        submitted, and its shape reads as a required format."""
        markup = _markup(INTAKE_HTML)
        self.assertNotIn("placeholder", markup)
        self.assertNotIn("Warehouse conversion", markup)

    def test_e_there_is_no_hidden_default_anywhere(self):
        """Scanned against the MARKUP, not the source.

        THE NINTH PROSE-SCAN FALSE POSITIVE IN THIS PROGRAMME WAS THIS LINE. It
        read raw `INTAKE_HTML` for "Untitled" and matched the comment that was
        added in the same edit to explain that there is deliberately no
        "Untitled Project" default. `_markup()` exists in this file precisely to
        strip Jinja comments, and the first version of this test did not use it.
        """
        self.assertNotIn("Untitled", _markup(INTAKE_HTML))
        handler = _handler_source()
        self.assertNotIn("Untitled", handler)
        # The old fallback was `project_name=(...).strip() or None`, which let
        # `ingest_upload` derive identity from the filename instead.
        self.assertNotIn("or None", handler.split("project_name=")[1][:60])

    def test_the_visually_hidden_class_it_relies_on_really_exists(self):
        css = Path("static/css/main.css").read_text(encoding="utf-8")
        self.assertIn(".visually-hidden {", css)


# ============================================================================
# F, G, H - WORK-ITEM NAMING
# ============================================================================

class WorkItemNamesAreDeterministic(unittest.TestCase):
    """F and G at the unit, against section 6's own worked example."""

    def test_f_one_document_takes_the_project_name_unchanged(self):
        self.assertEqual(ingestion.work_item_names("SRPC Drawing Review", 1),
                         ["SRPC Drawing Review"])

    def test_g_three_documents_are_numbered_one_to_three(self):
        self.assertEqual(
            ingestion.work_item_names("SRPC Drawing Review", 3),
            ["SRPC Drawing Review 1", "SRPC Drawing Review 2",
             "SRPC Drawing Review 3"])

    def test_g_numbering_continues_past_nine_without_padding(self):
        names = ingestion.work_item_names("Set", 11)
        self.assertEqual(names[9], "Set 10")
        self.assertEqual(names[10], "Set 11")

    def test_the_name_is_trimmed(self):
        self.assertEqual(ingestion.work_item_names("  Spaced  ", 1), ["Spaced"])

    def test_a_blank_name_produces_nothing_rather_than_a_default(self):
        for blank in ("", "   ", None):
            with self.subTest(name=blank):
                self.assertEqual(ingestion.work_item_names(blank, 3), [])

    def test_no_count_produces_nothing(self):
        self.assertEqual(ingestion.work_item_names("Set", 0), [])

    def test_numbering_does_not_consult_filenames(self):
        """Section 5. A phone's picker hands over image.jpg five times, so a
        filename carries no order and often no distinction."""
        import inspect
        source = inspect.getsource(ingestion.work_item_names)
        for banned in ("filename", "file_storage", "suffix", "Path("):
            self.assertNotIn(banned, source.split('"""')[-1], banned)


# ============================================================================
# THE ROUTE - C, D, F, G, H, I, K end to end
# ============================================================================

def _parsed(project_id, filename):
    """A real ParsedDocument, built the way the existing hermetic tests build
    one (`tests/test_black_box_intake_door_01.py`) - never the real parser, so
    nothing here can reach an external API."""
    import uuid
    from datetime import datetime, timezone

    from services.bhive_parser import ParsedDocument
    return ParsedDocument(
        project_id=project_id or str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(),
        parser_version="test")


class TheUploadRouteEnforcesIt(unittest.TestCase):

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_docupload_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False
        with self.flask_app.app_context():
            db.session.add(User(username="boss",
                                password_hash=generate_password_hash("x"),
                                role="admin"))
            db.session.commit()

    def _client(self):
        client = self.flask_app.test_client()
        client.post("/login", data={"username": "boss", "password": "x"},
                    follow_redirects=True)
        return client

    def _post(self, name, filenames=("brief.txt",), client=None):
        """Upload with a HERMETIC parser. Never reaches a real API."""
        def fake_parse(self, file_storage, project_id=None, **kwargs):
            return _parsed(project_id, getattr(file_storage, "filename", "x.txt"))

        files = [(io.BytesIO(b"a governed document body"), n) for n in filenames]
        with patch.object(BHiveParser, "parse", fake_parse):
            return (client or self._client()).post(
                "/document-shop", data={"name": name, "file": files},
                content_type="multipart/form-data")

    # -- the page ---------------------------------------------------------
    def test_a_the_rendered_page_says_document_upload(self):
        """Scoped to the page's OWN title and heading.

        The surrounding shell still contains "Document Shop Jobs" and the
        customer brand, and both are correct: section 1 renames the label where
        it refers to the UPLOAD PAGE, and section 8 forbids renaming unrelated
        pages. An unscoped assertNotIn on the whole document would have demanded
        the opposite of what was asked.
        """
        body = self._client().get("/document-shop").get_data(as_text=True)
        self.assertIn("<title>Document Upload &mdash; Archiosk</title>", body)
        self.assertIn(">Document Upload</h1>", body)
        self.assertNotIn(">Document Shop</h1>", body)
        self.assertNotIn("<title>Document Shop", body)

    def test_c_the_rendered_field_is_required_with_no_placeholder(self):
        body = self._client().get("/document-shop").get_data(as_text=True)
        self.assertIn("Name of project", body)
        self.assertIn('aria-required="true"', body)
        self.assertNotIn("placeholder=", body.split('id="document-shop-name"')[1][:400])

    # -- refusal ----------------------------------------------------------
    def test_d_a_blank_project_name_is_rejected(self):
        response = self._post("")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Enter a name of project", response.get_data(as_text=True))

    def test_d_a_whitespace_only_project_name_is_rejected(self):
        for blank in ("   ", "\t", "\n  \n"):
            with self.subTest(name=repr(blank)):
                response = self._post(blank)
                self.assertEqual(response.status_code, 400)

    def test_d_nothing_is_created_when_the_name_is_refused(self):
        """Refusing after the first file is stored would leave a governed
        container for a work the person never named."""
        self._post("")
        self.assertEqual(sorted(p.name for p in self.tmp_dir.glob("*.workspace.json")),
                         [])
        self.assertFalse((self.tmp_dir / "workspace_sources").exists())

    def test_a_missing_file_is_still_refused_first(self):
        with patch.object(BHiveParser, "parse",
                          lambda self, f, project_id=None, **k: _parsed(project_id, "x")):
            response = self._client().post(
                "/document-shop", data={"name": "Named"},
                content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        self.assertIn("No document was provided", response.get_data(as_text=True))

    # -- naming -----------------------------------------------------------
    def _project_id(self, response):
        """The container id, read from the redirect the door issues.

        `CaseWorkspaceStore` has no `list_ids` - that belongs to
        `RequirementsRegistry` - and the redirect is the more precise source
        anyway: it names the container THIS upload created rather than whatever
        happens to be in the store.
        """
        self.assertEqual(response.status_code, 302,
                         response.get_data(as_text=True)[:400])
        location = response.headers["Location"]
        return [part for part in location.split("/") if part][-1]

    def _sources(self, response):
        store = CaseWorkspaceStore(str(self.tmp_dir))
        workspace = store.get(self._project_id(response))
        return [s for s in workspace.sources if not s.get("removed_at")]

    def test_f_one_document_is_named_with_the_project_name_only(self):
        response = self._post("SRPC Drawing Review", ("scan-001.txt",))
        names = [s["name"] for s in self._sources(response)]
        self.assertEqual(names, ["SRPC Drawing Review"])

    def test_g_three_documents_are_named_one_to_three_in_upload_order(self):
        response = self._post("SRPC Drawing Review",
                              ("first.txt", "second.txt", "third.txt"))
        sources = self._sources(response)
        self.assertEqual(len(sources), 3)
        ordered = sorted(sources, key=lambda s: s.get("intake_order") or 0)
        self.assertEqual([s["name"] for s in ordered],
                         ["SRPC Drawing Review 1", "SRPC Drawing Review 2",
                          "SRPC Drawing Review 3"])

    def test_g_the_founding_document_is_number_one_not_number_two(self):
        """The bug this test exists for: `intake_order` is set on the perception
        job but left None on the founding Source, so ordering by it alone drops
        the founding document out of the numbering and names the SECOND file 1."""
        response = self._post("Set", ("founding.txt", "second.txt"))
        founding = [s for s in self._sources(response)
                    if s.get("intake_order") in (None, 0)]
        self.assertEqual(len(founding), 1)
        self.assertEqual(founding[0]["name"], "Set 1")

    # -- H: the evidence keeps its own identity ---------------------------
    def test_h_the_original_filename_and_hash_are_untouched(self):
        response = self._post("Renamed Work", ("original-name.txt",))
        source = self._sources(response)[0]
        self.assertEqual(source["name"], "Renamed Work")
        # The stored path still carries the filename the person uploaded.
        self.assertIn("original-name", source["file_path"])
        self.assertTrue(source.get("file_hash"))
        self.assertTrue(Path(source["file_path"]).exists())

    def test_h_the_stored_bytes_are_untouched(self):
        response = self._post("Renamed Work", ("payload.txt",))
        source = self._sources(response)[0]
        self.assertEqual(Path(source["file_path"]).read_bytes(),
                         b"a governed document body")

    def test_h_renaming_the_display_name_changes_nothing_else(self):
        response = self._post("First Name", ("evidence.txt",))
        before = dict(self._sources(response)[0])
        store = CaseWorkspaceStore(str(self.tmp_dir))
        workspace = store.get(self._project_id(response))
        store.update_source_identity(workspace, before["id"], actor="boss",
                                     name="Second Name")
        after = self._sources(response)[0]
        self.assertEqual(after["name"], "Second Name")
        for field in ("file_path", "file_hash", "origin_type", "kind", "id"):
            self.assertEqual(after.get(field), before.get(field), field)

    # -- I: existing project context --------------------------------------
    def test_i_this_door_has_no_project_context_to_inherit(self):
        """Section 7. This route exists BECAUSE there is no project - it refuses
        to accept an operating environment at all - so there is no governed
        project name to prefer, and the field stays visible rather than guessed.
        """
        source = Path("routes/portal.py").read_text(encoding="utf-8")
        handler = source.split("def document_shop_intake()")[1].split("\ndef ")[0]
        self.assertIn("operating_environment=None", handler)
        self.assertIn("CONTAINER_STATE_BLACK_BOX", handler)
        # And it takes the name from the form, never from a project record.
        self.assertIn("request.form.get('name')", handler)

    def test_i_a_second_upload_of_the_same_name_is_refused_not_duplicated(self):
        """`ingest_upload` already rejects a name that is taken, which is what
        stops a second identity being created for the same work."""
        self.assertEqual(self._post("Unique Work", ("a.txt",)).status_code, 302)
        again = self._post("Unique Work", ("b.txt",))
        self.assertEqual(again.status_code, 400)

    # -- K: nothing else changed ------------------------------------------
    def test_k_the_upload_still_creates_one_container_and_redirects_to_it(self):
        response = self._post("Behaviour Unchanged", ("doc.txt",))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/document-shop/", response.headers["Location"])
        store = CaseWorkspaceStore(str(self.tmp_dir))
        workspace = store.get(self._project_id(response))
        self.assertIsNotNone(workspace)
        self.assertEqual(len(self._sources(response)), 1)

    def test_k_the_container_is_still_a_black_box_with_no_environment(self):
        response = self._post("Still A Black Box", ("doc.txt",))
        store = CaseWorkspaceStore(str(self.tmp_dir))
        workspace = store.get(self._project_id(response))
        self.assertIsNone(workspace.operating_environment)

    def test_k_the_project_display_title_is_the_name_given(self):
        response = self._post("The Work Name", ("doc.txt",))
        store = CaseWorkspaceStore(str(self.tmp_dir))
        workspace = store.get(self._project_id(response))
        self.assertEqual(workspace.display_title, "The Work Name")

    def test_k_a_non_entitled_account_is_still_refused(self):
        from models import User, db
        with self.flask_app.app_context():
            db.session.add(User(username="reader",
                                password_hash=generate_password_hash("x"),
                                role="read_only"))
            db.session.commit()
        client = self.flask_app.test_client()
        client.post("/login", data={"username": "reader", "password": "x"},
                    follow_redirects=True)
        self.assertEqual(client.get("/document-shop").status_code, 403)


class TheDisplayNameIsNotAFileType(unittest.TestCase):
    """The carry-through this rename forced, and it was already a latent defect.

    `Source.name` WAS the filename for every source that had ever existed -
    `add_source(name=filename)` on every path - so two places read a file
    FORMAT off the display name and worked by coincidence. Giving a source a
    work-item name ended the coincidence, and both places broke in ways that
    would have reached a customer:

      - `routes/workspace.py::source_image` fed the display name to
        `verify_image_bytes`, so "SRPC Drawing Review 2" verified as not-an-image
        and the person's own photo 404'd.
      - `services/document_examination.py` set `is_image` from the display
        name's suffix, so a photo stopped rendering as a photo on the result
        page the customer is sent to.

    Section 4's distinction - project name is not source filename - is exactly
    the one the codebase had never had to make.
    """

    def test_the_image_route_verifies_against_the_stored_file_not_the_label(self):
        source = Path("routes/workspace.py").read_text(encoding="utf-8")
        handler = source.split("def source_image(")[1].split("\ndef ")[0]
        self.assertIn("verify_image_bytes(raw_bytes, path.name)", handler)
        self.assertNotIn('verify_image_bytes(raw_bytes, source.get("name")', handler)

    def test_the_download_name_keeps_a_real_suffix(self):
        source = Path("routes/workspace.py").read_text(encoding="utf-8")
        handler = source.split("def source_image(")[1].split("\ndef ")[0]
        self.assertIn("Path(path.name).suffix", handler)

    def test_the_examination_reads_the_format_from_the_stored_file(self):
        from services import document_examination

        self.assertEqual(
            document_examination._stored_filename(
                {"name": "SRPC Drawing Review 2",
                 "file_path": "/store/workspace_sources/p/abc123_photo.PNG"}),
            "/store/workspace_sources/p/abc123_photo.PNG")

    def test_an_image_is_still_an_image_after_it_is_renamed(self):
        from services import document_examination

        renamed = {"name": "SRPC Drawing Review 2",
                   "file_path": "/store/x/abc_scan.png"}
        self.assertIn(document_examination._ext(
            document_examination._stored_filename(renamed)),
            document_examination._IMAGE_EXTS)

    def test_a_source_with_no_stored_bytes_behaves_as_it_did_before(self):
        """An external-connector source has `file_path is None` BY DESIGN
        (`services/external_source.py`), so the fallback must be the old
        behaviour rather than an error."""
        from services import document_examination

        self.assertEqual(
            document_examination._stored_filename(
                {"name": "diagram.png", "file_path": None}), "diagram.png")
        self.assertEqual(document_examination._stored_filename({}), "")


# ============================================================================
# J - MOBILE STRUCTURE
# ============================================================================

class TheMobileStructureIsIntact(unittest.TestCase):
    """J. Structure only - no claim is made here about rendered geometry."""

    def test_j_the_field_carries_no_fixed_width_of_its_own(self):
        markup = _markup(INTAKE_HTML)
        block = markup.split('id="document-shop-name"')[0][-400:]
        self.assertNotIn("style=", block)

    def test_j_the_page_reuses_the_existing_form_container(self):
        """`.np-group` is `max-width: 480px`, which is correct for a form -
        this page IS a form, unlike the planning result that had to stop
        borrowing it."""
        self.assertIn('class="np-group"', INTAKE_HTML)
        css = Path("static/css/main.css").read_text(encoding="utf-8")
        self.assertRegex(css, r"\.np-group\s*\{[^}]*max-width:\s*480px")

    def test_j_the_text_input_cannot_overflow_its_container(self):
        css = Path("static/css/main.css").read_text(encoding="utf-8")
        block = re.search(r"\.text-input\s*\{([^}]*)\}", css)
        self.assertIsNotNone(block)
        self.assertIn("width: 100%", block.group(1))

    def test_j_the_label_and_note_use_existing_type_classes(self):
        markup = _markup(INTAKE_HTML)
        self.assertIn('class="field-label"', markup)
        self.assertIn('class="mono field-note"', markup)


if __name__ == "__main__":
    unittest.main()
