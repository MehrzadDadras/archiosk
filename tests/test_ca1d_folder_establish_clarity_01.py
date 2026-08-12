"""
CLAUDE-CA1D-FOLDER-ESTABLISH-CLARITY-01 - make the folder-establishment
flow's required founding-document selection visible.

Covers a live user report ("Establish Project from Folder does
nothing") traced to a real folder (multiple eligible top-level files,
e.g. a .docx/.pdf RFP pair plus a Schedule) landing in
upload.html's own "explicit choice required" branch
(static/js's own upload.html inline script, unchanged by this
tranche) with zero CSS anywhere for the founding-document radio list
or the submit button's disabled state -- #folder-submit-button:disabled
was pixel-identical to its own enabled state, and the plain, unstyled
radio list gave no visual signal it was an actionable, required
control. Fixed with CSS only (main.css) plus one wording addition
(upload.html) -- no JS logic touched.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest


class FolderEstablishClarityTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        from werkzeug.security import generate_password_hash

        self.flask_app = app_module.create_app("testing")
        with self.flask_app.app_context():
            db.session.add(User(username="fec_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "fec_admin"
            sess["role"] = "admin"

    def test_upload_page_names_the_required_selection_explicitly(self):
        body = self.client.get("/upload").get_data(as_text=True)
        self.assertIn("Which of these is the principal RFP/document for this project?", body)
        self.assertIn("(required", body)
        self.assertIn("select one to continue", body)

    def test_confirm_checkbox_is_also_explicitly_marked_required(self):
        """Matches this form's own existing convention (Project
        Operating Environment already says '(required)') - every
        required field on this page uses the same plain-text marker,
        no new color introduced (tokens.css's own semantic-color
        grammar reserves --highlight-orange narrowly for "current
        step in a sequence", not general "required")."""
        body = self.client.get("/upload").get_data(as_text=True)
        confirm_start = body.index("operating-environment-confirm")
        confirm_end = body.index("</label>", confirm_start)
        self.assertIn("(required)", body[confirm_start:confirm_end])

    def test_folder_submit_button_still_starts_disabled(self):
        """Unchanged behavior - this tranche only makes the existing
        disabled state visible, never changes when it applies."""
        body = self.client.get("/upload").get_data(as_text=True)
        button_start = body.index('id="folder-submit-button"')
        button_end = body.index(">", button_start)
        self.assertIn("disabled", body[button_start:button_end])

    def test_main_css_gives_the_disabled_folder_submit_button_its_own_visual_state(self):
        css = self.client.get("/static/css/main.css").get_data(as_text=True)
        self.assertIn("#folder-submit-button:disabled", css)
        rule_start = css.index("#folder-submit-button:disabled")
        rule_end = css.index("}", rule_start)
        rule = css[rule_start:rule_end]
        self.assertIn("opacity", rule)
        self.assertIn("cursor: not-allowed", rule)

    def test_main_css_styles_the_founding_candidate_list_as_selectable_rows(self):
        css = self.client.get("/static/css/main.css").get_data(as_text=True)
        self.assertIn(".folder-founding-candidates label {", css)
        rule_start = css.index(".folder-founding-candidates label {")
        rule_end = css.index("}", rule_start)
        rule = css[rule_start:rule_end]
        self.assertIn("cursor: pointer", rule)
        self.assertIn("border", rule)
        # Selected-state feedback, matching this app's own existing
        # .project-card-selectable precedent for "pick one from a list".
        self.assertIn(".folder-founding-candidates label:has(input:checked)", css)

    def test_folder_picker_wiring_script_itself_is_unchanged(self):
        """This tranche is CSS/wording only - the actual selection/
        submit-enabling logic (already fixed by
        CLAUDE-CA1D-CSP-INLINE-SCRIPT-FIX-01) must not be touched
        again here."""
        body = self.client.get("/upload").get_data(as_text=True)
        self.assertIn("pickerButton.addEventListener('click', function () { pickerInput.click(); });", body)
        self.assertIn("submitButton.disabled = !relativePath;", body)


if __name__ == "__main__":
    unittest.main()
