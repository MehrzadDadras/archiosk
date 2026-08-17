"""
CLAUDE-HYBRID-ENTRY-01 - make the current New Project folder-establishment
UI honest about what it actually does (permanently uploads a copy to
Archiosk's own server) rather than reading as a local/company-storage
folder-link.

Product Owner finding: "Choose Project Folder" / "Establish Project from
Folder" triggered Chrome's native "Upload N files to this site?" dialog
and was reasonably read as folder-linking, when the actual operation
(services/ingestion.py's ingest_folder_upload) writes a permanent,
indefinitely-retained byte copy of every eligible file to
instance/registry/workspace_sources/{project_id}/. This is a wording/
labeling-only correction - no route, no JS logic, no persistence
behavior was touched. The underlying mechanism (and its own dedicated
UX, tests/test_ca1d_folder_establish_clarity_01.py) is kept, not removed,
per the Product Owner's own "do not remove a useful legacy/test
capability unless necessary" instruction.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        import shutil
        import tempfile
        from pathlib import Path
        from models import User, db
        from werkzeug.security import generate_password_hash

        # Own isolated registry dir, same discipline every other test
        # base class in this suite uses - config.py's own REGISTRY_STORE_PATH
        # default otherwise falls through to the REAL local instance/registry/
        # directory, which a first draft of this file actually did (caught
        # and cleaned up manually before this fix landed).
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_hybrid_entry_01_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="hybrid_entry_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "hybrid_entry_admin"
            sess["role"] = "admin"
        self._rmtree = shutil.rmtree

    def tearDown(self):
        self._rmtree(self.tmp_dir, ignore_errors=True)

    def _body(self):
        return self.client.get("/upload").get_data(as_text=True)


class FolderPathNoLongerReadsAsLinkingTests(_BaseTestCase):
    def test_old_misleading_labels_are_gone(self):
        body = self._body()
        self.assertNotIn("Choose Project Folder", body)
        self.assertNotIn("Establish Project from Folder", body)

    def test_folder_path_is_explicitly_labeled_legacy_full_upload(self):
        # CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01 addendum (Storage
        # Grammar): supersedes the "Legacy" framing this test asserted -
        # the Product Owner's own Part 1/3 replaced "Upload Folder
        # Contents (Legacy - full server upload)" with a plain, enduring
        # Link-vs-Upload choice ("Upload to Storage"), no longer framed
        # as a demoted/legacy path. The underlying mechanism this test
        # family exists to protect (folder upload is a real, kept
        # capability, not silently removed) is now covered by
        # test_upload_option_present_and_functional below instead.
        body = self._body()
        self.assertIn("Upload Folder Contents", body)
        self.assertIn("Upload to Storage", body)
        self.assertIn("configured managed storage", body)

    def test_folder_path_explicitly_states_it_is_not_a_folder_link(self):
        # CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01 addendum (Storage
        # Grammar, Part 4): the literal sentence this test asserted was
        # HYBRID-ENTRY-01's own inline disclaimer, now moved behind the
        # Upload option's own "Details" subdisclosure (Part 1: "do not
        # fill the normal surface with lengthy custody explanations").
        # The invariant itself - never claiming this is a live link -
        # is preserved by the DISTINCT "Link to Storage" option being
        # honestly labeled "(not yet configured)" rather than by this
        # exact sentence appearing inline.
        body = self._body()
        self.assertIn("not yet configured", body)
        self.assertIn("Link to Storage", body)
        self.assertIn("local files are not watched, referenced, or left in place", body)

    def test_folder_submit_button_no_longer_styled_as_the_primary_recommended_action(self):
        body = self._body()
        button_start = body.index('id="folder-submit-button"')
        button_end = body.index(">", button_start)
        button_tag = body[button_start:button_end]
        self.assertNotIn("btn-primary", body[body.rindex("<button", 0, button_start):button_end])
        self.assertIn("btn-ghost", body[body.rindex("<button", 0, button_start):button_end])

    def test_folder_submit_button_still_starts_disabled(self):
        # Unchanged behavior - this stage only relabels/demotes, never
        # touches the founding-document-required disabled-state logic
        # CLAUDE-CA1D-FOLDER-ESTABLISH-CLARITY-01 already covers.
        body = self._body()
        button_start = body.index('id="folder-submit-button"')
        button_end = body.index(">", button_start)
        self.assertIn("disabled", body[button_start:button_end])

    def test_hero_copy_no_longer_claims_files_stay_in_place(self):
        body = self._body()
        self.assertNotIn("your files stay wherever they already are", body)

    def test_hero_copy_states_current_honest_behavior_and_future_direction(self):
        # CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01 addendum (Storage
        # Grammar, Part 1): the long inline disclaimer this test asserted
        # is deliberately gone - the Product Owner's own instruction was
        # "do not fill the normal surface with lengthy custody
        # explanations." The hero is now a short framing sentence; the
        # "future direction" claim now lives in the Link option's own
        # Details disclosure (test_link_option_present_but_disabled_and_
        # honest below), not inline hero copy.
        body = self._body()
        self.assertIn("Choose how this Project's documents connect to Archiosk.", body)


class SingleFilePathWordingTests(_BaseTestCase):
    def test_single_file_path_explicitly_states_permanent_server_storage(self):
        body = self._body()
        fieldset_start = body.index('class="single-file-establish-fieldset"')
        fieldset_end = body.index("</fieldset>", fieldset_start)
        fieldset = body[fieldset_start:fieldset_end]
        self.assertIn("permanently stores a copy of this file on Archiosk's own server", fieldset)

    def test_single_file_capability_itself_is_not_removed(self):
        body = self._body()
        self.assertIn('data-ui-ref="upload.file"', body)
        self.assertIn('data-ui-ref="upload.submit"', body)
        self.assertIn("Create project and parse document", body)

    def test_form_disables_both_submit_buttons_on_actual_submission(self):
        # CLAUDE-CLIENT-RFP-PROJECT-CREATION-01 (Game E): a real
        # double-submit was reproduced live during this stage's own
        # verification - a slow request left a window where a second
        # click fired a second identical request before the first had
        # finished committing, creating two real, identically-named
        # projects (services/ingestion.py's _reject_if_name_taken only
        # sees already-persisted projects). Static-content check only -
        # the actual dynamic behavior needs live-browser verification,
        # which this stage's own report records separately.
        body = self._body()
        self.assertIn("form.addEventListener('submit', function () {", body)
        self.assertIn("singleButton.disabled = true;", body)
        self.assertIn("folderButton.disabled = true;", body)

    def test_single_file_submit_button_starts_disabled(self):
        # CLAUDE-CLIENT-RFP-PROJECT-CREATION-01: a real Product Owner
        # pressed this button with no file chosen and only learned "No
        # file was provided" after a full server round trip - the same
        # "disabled until valid" discipline folder-submit-button already
        # uses (test_folder_submit_button_still_starts_disabled, above)
        # now applies here too, so the misleading ready state can never
        # be reached at all.
        body = self._body()
        button_start = body.index('id="single-file-submit-button"')
        button_end = body.index(">", button_start)
        self.assertIn("disabled", body[button_start:button_end])


class MechanismNotRemovedRegressionTests(_BaseTestCase):
    """CLAUDE-HYBRID-ENTRY-01 is a wording/labeling correction only - the
    real folder-establishment mechanism, its founding-document selection,
    and every existing data-ui-ref must all still be present and
    functionally reachable."""

    def test_every_pre_existing_folder_ui_reference_still_present(self):
        body = self._body()
        for ref in (
            "upload.folder.picker-button", "upload.folder.picker-input",
            "upload.folder.summary", "upload.folder.founding-picker",
            "upload.folder.error", "upload.folder.submit",
        ):
            self.assertIn(f'data-ui-ref="{ref}"', body)

    def test_folder_picker_wiring_script_still_unchanged(self):
        body = self._body()
        self.assertIn("pickerButton.addEventListener('click', function () { pickerInput.click(); });", body)
        self.assertIn("submitButton.disabled = !relativePath;", body)

    def test_folder_route_still_functions_end_to_end(self):
        # A real POST through portal.upload_folder must still succeed -
        # this stage never touched routes/portal.py or services/ingestion.py.
        import io
        import uuid
        from unittest.mock import patch
        from datetime import datetime, timezone
        from werkzeug.datastructures import FileStorage
        from services.bhive_parser import BHiveParser, ParsedDocument

        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            resp = self.client.post(
                "/upload/folder",
                data={
                    "operating_environment": "client_owner",
                    "folder_files": [
                        FileStorage(stream=io.BytesIO(b"hello"), filename="Project/spec.pdf"),
                    ],
                    "founding_relative_path": "Project/spec.pdf",
                    "project_name": "Hybrid Entry Regression Project",
                },
                content_type="multipart/form-data",
            )
        self.assertEqual(resp.status_code, 302, resp.get_data(as_text=True)[:500])


if __name__ == "__main__":
    unittest.main()
