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
        # "principal RFP/document" became "principal document" when c81536e
        # separated connected documents by source domain: a connected folder
        # can now be a client data room, a team workspace or an external-
        # reference set, and "RFP" names only one of those three cases.
        #
        # The "(required - select one to continue)" gloss went with the
        # rebuild. templates/upload.html's own comment at that line records
        # why - it was "explaining a state the disabled Upload Folder button
        # already shows" - and that button's disabled default is asserted by
        # test_folder_submit_button_still_starts_disabled below, so the
        # required-ness is still guarded, just not as a second sentence.
        body = self.client.get("/upload").get_data(as_text=True)
        self.assertIn("Which of these is the principal document for this project?", body)

    def test_the_confirm_checkbox_and_its_required_marker_are_both_gone(self):
        """Was: the confirm checkbox is also explicitly marked required.

        This tranche gave a confirmation checkbox a plain-text "(required)"
        marker so every required field on the page was marked the same way.
        53e1ca0 removed the checkbox itself, and
        tests/test_new_project_page_01.py asserts its absence by exact markup.

        The invariant survives in a different register rather than
        disappearing: required-ness on this page is now carried by control
        state - a required radio group, and a submit button that starts
        disabled - instead of by a text marker. Both already have their own
        guards (test_folder_submit_button_still_starts_disabled below, and
        tests/test_entry_redundancy_01.py for the radios), so this asserts the
        removal stayed clean rather than restating them.
        """
        body = self.client.get("/upload").get_data(as_text=True)
        self.assertNotIn("operating-environment-confirm", body)
        self.assertNotIn('aria-label="Confirm project position"', body)

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

    def test_folder_picker_wiring_still_opens_the_picker_and_gates_submit(self):
        """Was: the folder picker wiring script itself is unchanged.

        It is not unchanged, and deliberately so. c81536e replaced the single
        picker button with three source-domain buttons (Client Data Room /
        Your Workspace / External References), so the one
        `pickerButton.addEventListener(...)` line this test pinned by exact
        text became a `pickerButtons.forEach(...)` loop that also records
        which domain was chosen before opening the picker.

        The behaviour the assertion existed to protect is intact and is what
        this asserts instead: clicking a picker button opens the file picker,
        and the submit button stays gated on a real selection. That second
        line - the CLAUDE-CA1D-CSP-INLINE-SCRIPT-FIX-01 repair this test was
        written to defend - is still asserted verbatim.
        """
        body = self.client.get("/upload").get_data(as_text=True)
        self.assertIn("pickerButtons.forEach(", body)
        loop_start = body.index("pickerButtons.forEach(")
        self.assertIn("pickerInput.click();", body[loop_start:loop_start + 400])
        self.assertIn("submitButton.disabled = !relativePath;", body)


if __name__ == "__main__":
    unittest.main()
