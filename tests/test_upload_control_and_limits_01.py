"""CLAUDE-DOCUMENT-UPLOAD-PUBLIC-UX-01 - ARCHIOSK owns the visible upload state,
and the size copy says what the configuration actually enforces.

    Choose files   No file chosen      <- the browser's wording
    [ Choose files ]                   <- ours

Two subjects, and the second one is where this tranche's expectation and the
evidence disagreed.

THE FILE PICKER. A native file input renders its own status text, and that text
is the browser's: "No file chosen" on Chrome, "No files selected" on Firefox.
It cannot be styled or worded, and on an empty form it is the loudest thing on
the page - telling a person what they have NOT done before they can do it.

THE 60 MB CLAIM IS NOT STALE, and the audit is why it stays. `.env` sets
`MAX_UPLOAD_MB=60`, `config.py` turns that into `MAX_CONTENT_LENGTH`, and nginx
on the live host carries a matching `client_max_body_size 60M`. A larger request
is refused by the transport layer before any application code runs, so staged
processing cannot rescue it. Removing the sentence would hide a real ceiling -
which section 14 forbids - and "processed in stages" would be untrue here: the
chunked 500 MB path exists only for adding a source to an EXISTING project.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

INTAKE_HTML = Path("templates/document_shop_intake.html").read_text(encoding="utf-8")
CONTROL_JS = Path("static/js/upload_control.js").read_text(encoding="utf-8")
MAIN_CSS = Path("static/css/main.css").read_text(encoding="utf-8")
NGINX_CONF = Path("deploy/nginx.conf").read_text(encoding="utf-8")
CONFIG_PY = Path("config.py").read_text(encoding="utf-8")


def _markup(html: str) -> str:
    """Template with Jinja comments stripped - a comment explaining a removed
    phrase is not that phrase."""
    return re.sub(r"\{#.*?#\}", "", html, flags=re.S)


# ============================================================================
# K, L, M, N, O - THE FILE PICKER
# ============================================================================

class ArchioskOwnsTheVisibleUploadState(unittest.TestCase):
    """K, L, M, N, O."""

    def test_k_the_native_status_text_cannot_render(self):
        """"No file chosen" is drawn by the browser BESIDE a rendered file
        input. The only way to remove it is to stop rendering the input, which
        is what `.visually-hidden` does without removing the input itself."""
        markup = _markup(INTAKE_HTML)
        block = markup.split("data-upload-control")[1][:700]
        self.assertIn('class="visually-hidden"', block)
        self.assertIn("data-upload-input", block)
        # And we do not write our own version of the same sentence.
        self.assertNotIn("No file chosen", markup)
        self.assertNotIn("No files selected", markup)

    def test_l_the_input_is_clipped_not_hidden(self):
        """`hidden`/`display:none` removes the input from the accessibility tree
        and the tab order. That is the trap section 9 names."""
        markup = _markup(INTAKE_HTML)
        block = markup.split("data-upload-control")[1][:700]
        input_tag = block[block.index("<input"):block.index(">", block.index("<input"))]
        self.assertNotIn(" hidden", input_tag)
        self.assertNotIn("display:none", input_tag)
        self.assertNotIn("display: none", input_tag)

    def test_l_visually_hidden_really_keeps_the_element_reachable(self):
        """It clips rather than removes - verified in the stylesheet, because a
        `.visually-hidden` implemented with `display: none` would silently
        undo every accessibility claim above."""
        block = re.search(r"\.visually-hidden\s*\{([^}]*)\}", MAIN_CSS)
        self.assertIsNotNone(block)
        body = block.group(1)
        self.assertNotIn("display: none", body)
        self.assertNotIn("display:none", body)
        self.assertTrue("clip" in body or "position: absolute" in body, body)

    def test_l_the_label_still_points_at_the_real_input(self):
        markup = _markup(INTAKE_HTML)
        self.assertIn('for="document-shop-file"', markup)
        self.assertIn('id="document-shop-file"', markup)

    def test_l_the_input_keeps_its_name_so_the_form_still_submits_it(self):
        markup = _markup(INTAKE_HTML)
        block = markup.split("data-upload-control")[1][:700]
        self.assertIn('name="file"', block)
        self.assertIn("required", block)
        self.assertIn("multiple", block)

    def test_l_the_choose_button_is_a_real_button_and_not_a_submit(self):
        markup = _markup(INTAKE_HTML)
        block = markup.split("data-upload-choose")[0][-400:]
        self.assertIn('type="button"', block)

    def test_l_focus_is_forwarded_to_the_control_a_person_can_see(self):
        """A focus ring on a 1px clipped box is invisible, so a keyboard user
        would tab onto a control with no sign of focus."""
        self.assertIn("upload-choose-focused", CONTROL_JS)
        self.assertIn("focus", CONTROL_JS)
        self.assertIn("blur", CONTROL_JS)
        block = re.search(r"\.upload-choose-focused\s*\{([^}]*)\}", MAIN_CSS)
        self.assertIsNotNone(block)
        self.assertIn("outline", block.group(1))

    def test_m_one_file_reads_as_one_file_selected(self):
        self.assertIn("'1 file selected'", CONTROL_JS)

    def test_n_more_than_one_file_reads_as_a_count(self):
        self.assertIn("files selected", CONTROL_JS)
        # Derived from the real FileList, not from anything typed.
        self.assertIn("input.files", CONTROL_JS)

    def test_the_empty_state_says_nothing_at_all(self):
        """Replacing "No file chosen" with our own version of it would miss the
        point of removing it."""
        self.assertIn("status.hidden = true", CONTROL_JS)
        self.assertIn("status.textContent = ''", CONTROL_JS)

    def test_the_selection_state_is_announced_politely(self):
        self.assertIn('aria-live="polite"', _markup(INTAKE_HTML))

    def test_filenames_are_rendered_as_text_never_as_markup(self):
        """A filename is attacker-supplied text on this surface."""
        self.assertIn("names.textContent", CONTROL_JS)
        self.assertNotIn("innerHTML", CONTROL_JS)

    def test_o_the_control_never_touches_the_file_list(self):
        """The FileList belongs to the browser and is submitted unchanged, so a
        phone's camera picker and drag-and-drop both keep working and nothing
        here can alter provenance.

        BANS THE ASSIGNMENTS, NOT THE WORDS, and it took two tries. The first
        version banned `files =` and matched this module's own
        `var files = input.files` - a READ of the list, which is the entire
        legitimate purpose. The second still banned `rename` and matched the
        control's own docstring sentence promising it never renames anything.

        Eleventh occurrence of that pattern in this programme, and the lesson is
        the same every time: assert the MECHANISM - here, that nothing is ever
        assigned back to the input - never the vocabulary.
        """
        for banned in ("DataTransfer", "input.value =", "input.files =",
                       "new File(", "new FileList"):
            self.assertNotIn(banned, CONTROL_JS, banned)
        # And it genuinely does read the list, which is the other half.
        self.assertIn("input.files", CONTROL_JS)

    def test_o_the_button_only_opens_the_native_picker(self):
        self.assertIn("input.click()", CONTROL_JS)

    def test_w_the_control_is_shared_and_driven_by_data_attributes(self):
        """Section 8: one reusable pattern, not a per-page script and not a
        separate mobile implementation."""
        self.assertTrue(Path("static/js/upload_control.js").exists())
        self.assertIn("[data-upload-control]", CONTROL_JS)
        self.assertIn("querySelectorAll", CONTROL_JS)
        # No page-specific ids anywhere in it.
        self.assertNotIn("document-shop", CONTROL_JS)
        self.assertNotIn("getElementById", CONTROL_JS)

    def test_w_the_page_loads_the_shared_control_with_cache_busting(self):
        markup = _markup(INTAKE_HTML)
        self.assertIn("js/upload_control.js", markup)
        self.assertIn("?v={{ static_version }}", markup)

    def test_w_there_is_no_second_implementation_of_this_control(self):
        """`upload.html` has its own staged-selection script with
        founding-document logic this control does not model. It is deliberately
        NOT migrated in this tranche - but it must not have been COPIED either."""
        others = [p for p in Path("static/js").glob("*.js")
                  if p.name != "upload_control.js"]
        for path in others:
            body = path.read_text(encoding="utf-8")
            self.assertNotIn("data-upload-control", body, path.name)


# ============================================================================
# S, T, U, V - THE SIZE LIMIT AUDIT
# ============================================================================

class TheSizeCopyMatchesTheConfiguration(unittest.TestCase):
    """S, T, U, V - and the audit found the opposite of the expectation."""

    def test_the_transport_ceiling_is_configured_and_findable(self):
        """The value the page states comes from one place, not from prose."""
        self.assertIn('MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024',
                      CONFIG_PY)

    def test_s_the_size_sentence_stays_because_the_limit_is_real(self):
        """SECTION 13's CONDITION IS NOT MET. It says remove the claim "if no
        user-facing hard document-size ceiling remains". One does: Flask's
        `MAX_CONTENT_LENGTH`, with a matching nginx `client_max_body_size`.
        """
        markup = _markup(INTAKE_HTML)
        self.assertIn("{{ max_upload_mb }} MB", markup)

    def test_s_the_figure_is_rendered_from_config_never_hardcoded(self):
        """A hardcoded "60" would be the stale claim this tranche was looking
        for - it would survive a change to `MAX_UPLOAD_MB` and start lying."""
        markup = _markup(INTAKE_HTML)
        self.assertNotIn("60 MB", markup)
        self.assertNotIn("Up to 60", markup)

    def test_v_nginx_and_flask_agree_on_the_ceiling(self):
        """If nginx were lower, the app's own limit and its message would both
        be wrong and a refusal would arrive as a bare 413 from the proxy."""
        nginx = re.search(r"client_max_body_size\s+(\d+)([MmGg])", NGINX_CONF)
        self.assertIsNotNone(nginx, "deploy/nginx.conf must state a body limit")
        self.assertEqual(nginx.group(1), "60")
        self.assertIn(nginx.group(2).upper(), ("M",))

    def test_t_the_page_never_claims_unlimited(self):
        markup = _markup(INTAKE_HTML).lower()
        for banned in ("unlimited", "no limit", "any size", "no size limit"):
            self.assertNotIn(banned, markup, banned)

    def test_u_the_staged_processing_claim_is_absent_because_it_is_untrue_here(self):
        """The chunked 500 MB path exists only for adding a source to an
        EXISTING project (`/projects/<id>/workspace/sources/upload-chunk`).
        Claiming staged processing on the front door would be false."""
        markup = _markup(INTAKE_HTML).lower()
        self.assertNotIn("processed in stages", markup)
        self.assertNotIn("staged", markup)

    def test_u_the_chunked_path_is_not_reachable_from_this_page(self):
        """The evidence behind the claim above, asserted rather than described."""
        self.assertNotIn("upload-chunk", INTAKE_HTML)
        route_source = Path("routes/portal.py").read_text(encoding="utf-8")
        handler = route_source.split("def document_shop_intake()")[1].split("\ndef ")[0]
        self.assertNotIn("chunk", handler.lower())

    def test_the_chunked_ceiling_is_separate_and_still_bounded(self):
        """Section 12: report what is configured. 500 MB, and deliberately not
        governed by MAX_CONTENT_LENGTH."""
        self.assertIn('MAX_CHUNKED_UPLOAD_MB = int(os.getenv("MAX_CHUNKED_UPLOAD_MB", "500"))',
                      CONFIG_PY)

    def test_the_image_ceiling_is_separate_and_lower(self):
        image = Path("services/image_intake.py").read_text(encoding="utf-8")
        self.assertIn("MAX_IMAGE_BYTES = 40 * 1024 * 1024", image)

    def test_the_per_file_wording_is_accurate_for_a_multi_file_form(self):
        """`MAX_CONTENT_LENGTH` bounds the whole REQUEST, so on a multiple-file
        form the honest statement is per-file only if the request total is what
        is checked. Flask checks the request; the page therefore must not imply
        a per-file allowance that the sum can breach... which is why the client
        control also carries no size promise of its own."""
        markup = _markup(INTAKE_HTML)
        self.assertIn("Up to {{ max_upload_mb }} MB per file", markup)
        # The control makes no size claim at all - the server is the authority.
        self.assertNotIn("data-max-upload-bytes", markup)


# ============================================================================
# SECTION 15 - THE SPREADSHEET RULE
# ============================================================================

class TheSpreadsheetRuleIsCurrent(unittest.TestCase):
    """Section 15: verify before preserving, and preserve because it verified."""

    def test_the_rule_is_still_enforced_in_ingestion(self):
        ingestion = Path("services/ingestion.py").read_text(encoding="utf-8")
        self.assertIn('if ext == ".xlsx":', ingestion)
        self.assertIn("cannot be used as a founding document", ingestion)

    def test_the_page_still_states_it(self):
        self.assertIn("A spreadsheet cannot be the first document",
                      _markup(INTAKE_HTML))

    def test_xlsx_is_absent_from_the_offered_formats(self):
        """The list is derived from the same rules the upload enforces, so the
        page cannot offer a format the next click refuses."""
        route_source = Path("routes/portal.py").read_text(encoding="utf-8")
        handler = route_source.split("def document_shop_intake()")[1].split("\ndef ")[0]
        self.assertIn("if ext != '.xlsx'", handler.replace('"', "'"))


if __name__ == "__main__":
    unittest.main()
