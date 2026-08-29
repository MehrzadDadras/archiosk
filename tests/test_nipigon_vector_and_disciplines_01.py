"""CLAUDE-VECTOR-STANDARD-01 / CLAUDE-VOICE-SECURE-CONTEXT-01.

The 5 Nipigon coordination surface had no test file at all. Everything it
proves - that a pane serves a vector, that a discipline count came off the
source material, that a microphone is hidden where it cannot work - was
guarded only by whoever last looked at it.

Three invariants are worth the file, and each one has already been violated
once during development:

  1. VECTOR ONLY WHERE A READER ZOOMS. A cropped raster at a fixed dpi turns
     to mush past its ceiling, and a second picture of a region can disagree
     with the first about what the drawing says - which is not hypothetical:
     cropping after the native rotation silently moved the washroom crop onto
     AUTOMOBILE ELEV. 110, and the raster was the only place that lie lived.

  2. A DISCIPLINE COUNT IS EVIDENCE. The numbers on those cards were counted
     off the source directory and read off the A100 drawing index. A test that
     lets them drift lets the screen make a claim the project does not
     support.

  3. A MICROPHONE THAT CANNOT WORK MUST NOT APPEAR. The constructor is defined
     on an insecure origin, so a symbol-only check reveals a button whose
     first press fails.

These assert against rendered output and source text rather than running JS,
which this suite cannot do - but in every case the thing asserted is the thing
that was wrong.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = (ROOT / "routes" / "nipigon_coordination.py").read_text(encoding="utf-8")
TEMPLATE = (ROOT / "templates" / "nipigon_coordination.html").read_text(encoding="utf-8")
RENDER_TOOL = (ROOT / "tools" / "render_nipigon_assets.py").read_text(encoding="utf-8")
VOICE_JS = (ROOT / "static" / "js" / "voice_input.js").read_text(encoding="utf-8")


def _strip_comments(src: str) -> str:
    """Comments here quote the defects verbatim, so a naive absence check
    would be satisfied by the prose describing the thing it forbids."""
    src = re.sub(r"\{#.*?#\}", "", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"^\s*#.*$", "", src, flags=re.M)
    return src


class _Rendered(unittest.TestCase):
    """The real page, rendered through the real route."""

    def setUp(self):
        import app as app_module

        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = "admin"
            session["is_admin"] = True
            session["developer_mode"] = True
        response = self.client.get("/admin/nipigon/")
        self.assertEqual(response.status_code, 200)
        self.body = response.get_data(as_text=True)


class TheDualPaneDeskServesVectors(_Rendered):
    def test_pane_one_serves_an_svg_not_a_raster(self):
        match = re.search(r'id="np-pane1-img"[^>]*?src="([^"]*)"', self.body, re.S)
        self.assertIsNotNone(match, "pane 1 image not found")
        self.assertTrue(match.group(1).endswith(".svg"), match.group(1))

    def test_the_go_target_is_a_vector_too(self):
        match = re.search(r'data-go-asset="([^"]*)"', self.body)
        self.assertIsNotNone(match, "GO carries no asset")
        self.assertTrue(match.group(1).endswith(".svg"), match.group(1))

    def test_no_fixed_dpi_crop_raster_is_referenced_anywhere(self):
        """A crop is a viewBox VIEW onto the one vector asset. Any `<sheet>_
        <label>.png` in the output means a second, lower-fidelity picture of a
        region came back, free to disagree with the vector."""
        crops = re.findall(r'[A-Z]{1,2}\d{3}_(?!page|thumb)[a-z0-9-]+\.png', self.body)
        self.assertEqual(crops, [], f"raster crops referenced: {crops}")

    def test_the_render_tool_no_longer_emits_crop_rasters(self):
        """Guarded at the source, not only at the output: a pipeline that
        still writes them would refill the directory on the next run."""
        body = _strip_comments(RENDER_TOOL)
        self.assertNotIn("pix.save(dest)", body)
        self.assertIn("get_svg_image()", body)

    def test_focus_rectangles_replaced_them_and_are_carried_to_the_page(self):
        """The crop did not just go - it became a rectangle the viewport
        frames, which is what keeps the crop and the full sheet incapable of
        disagreeing."""
        self.assertIn("data-focus=", self.body)
        self.assertIn("data-view=", self.body)
        self.assertIn('def _asset_focus', ROUTE)

    def test_sibling_sheets_are_vectors(self):
        self.assertIn('"asset": "%s.svg" % sheet_id', ROUTE)

    def test_thumbnails_stay_raster_because_a_tile_has_no_zoom(self):
        """The rule is not "vector everywhere" - parsing 57,906 paths to fill
        a 175px box would be wasted work. It is vector where a reader zooms."""
        self.assertIn("_thumb.png", self.body)

    def test_the_go_block_guards_on_the_vector_it_actually_serves(self):
        """It used to test go.chosen.asset - a raster crop - while rendering
        target_svg.file. Retiring the crops would then have silently deleted
        the whole GO affordance with its vector present and usable."""
        self.assertIn("{% if go.chosen and target_svg %}", TEMPLATE)


class DisciplineContainersCarryCountedEvidence(_Rendered):
    def test_every_discipline_named_on_the_cover_index_gets_a_card(self):
        """Four of these delivered nothing. They are still shown, because a
        project page listing only the disciplines that happen to have files
        would hide the most useful fact on the screen."""
        for name in ("Architectural", "Structural", "Mechanical",
                     "Electrical", "Landscape", "Civil"):
            with self.subTest(discipline=name):
                self.assertIn(f">{name}</span>", self.body)

    def test_the_delivered_counts_are_the_measured_ones(self):
        """39 A-series and 10 RS-series PDFs, counted off the source
        directory."""
        self.assertIn("39 sheets", self.body)
        self.assertIn("10 sheets", self.body)

    def test_an_undelivered_discipline_says_so_rather_than_showing_a_picture(self):
        self.assertEqual(self.body.count("none delivered"), 4)
        self.assertIn("np-absent", self.body)

    def test_no_plumbing_or_c_series_container_was_invented(self):
        """A directive asked for a "Plumbing / Civil (P / C-Series)" card. The
        A100 index has no P-series at all - plumbing is the TITLE of M1 and M2,
        inside MECHANICAL - and the only C1 on the sheet is a zoning
        designation in the project-data block, not a drawing number. Civil is
        numbered SP1.

        Building the card anyway would put a container on screen standing for
        a series this project does not have: the same defect as accepting
        "A201 is the Level 2 floor plan" when its title block says FIRE
        SCHEMATIC LAYOUT."""
        self.assertNotIn(">Plumbing<", self.body)
        self.assertIn("SP1", self.body)
        self.assertIn("There is no separate P-series", ROUTE)

    def test_structural_is_inferred_because_the_source_disagrees_with_itself(self):
        """A100 names TWO structural sets under two numbering systems - S1-S10
        and RS501-RS510 - and only the RS framing series arrived. Calling that
        `direct` would assert a completeness the source does not support."""
        self.assertIn('"named": "S1-S10 and RS501-RS510"', ROUTE)
        self.assertIn("np-disc--inferred", self.body)

    def test_a_discipline_opens_into_its_own_sheets_and_nothing_else(self):
        self.assertIn('aria-controls="sheets-ARCH"', self.body)
        self.assertIn('id="sheets-ARCH"', self.body)
        # RS501 is the only rendered structural sheet, and it must sit under
        # Structural rather than in the architectural set.
        struct = self.body[self.body.index('id="sheets-STRUCT"'):]
        struct = struct[: struct.index("</ol>")]
        self.assertIn("RS501", struct)
        self.assertNotIn("A204", struct)

    def test_the_grid_axis_follows_orientation_not_a_width_breakpoint(self):
        """A landscape phone and a narrow desktop window can be the same
        number of pixels wide and want opposite layouts."""
        css = (ROOT / "static" / "css" / "nipigon.css").read_text(encoding="utf-8")
        self.assertIn("(max-width: 720px) and (orientation: portrait)", css)
        self.assertIn("(max-height: 560px) and (orientation: landscape)", css)


class TheMicrophoneIsHiddenWhereItCannotWork(_Rendered):
    def test_the_shared_engine_tests_the_capability_not_the_symbol(self):
        """On a plain http LAN origin `webkitSpeechRecognition` is a function
        and `navigator.mediaDevices` is undefined. A symbol-only check
        therefore PASSES, reveals the button, and the first press fails - the
        reported "voice fails to respond"."""
        self.assertIn("!SpeechRecognitionCtor || !window.isSecureContext", VOICE_JS)

    def test_this_surface_uses_the_shared_engine_rather_than_its_own(self):
        js = (ROOT / "static" / "js" / "nipigon.js").read_text(encoding="utf-8")
        self.assertIn("window.ArchioskVoiceInput", js)
        for engine_token in ("new SpeechRecognition", "recognition.start()",
                             "webkitSpeechRecognition"):
            with self.subTest(token=engine_token):
                self.assertNotIn(engine_token, _strip_comments(js))

    def test_the_mic_is_hidden_by_default_and_revealed_only_by_the_engine(self):
        button = self.body[self.body.index('id="np-voice-button"'):]
        button = button[: button.index(">")]
        self.assertIn("hidden", button)

    def test_voice_only_ever_dispatches_controls_that_are_already_on_the_page(self):
        """The authority boundary: voice cannot reach anything a tap cannot,
        so it inherits every guard the visible control already carries."""
        js = _strip_comments((ROOT / "static" / "js" / "nipigon.js").read_text(encoding="utf-8"))
        dispatch = js[js.index("function dispatch("):]
        dispatch = dispatch[: dispatch.index("\n    var heard")]
        self.assertIn("fire(", dispatch)
        self.assertIn("el.click()", js)
        # No route, no state change, no fetch - only presses.
        for forbidden in ("fetch(", "XMLHttpRequest", "location.href"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, dispatch)

    def test_an_unrecognised_sentence_does_nothing_and_says_what_it_heard(self):
        js = (ROOT / "static" / "js" / "nipigon.js").read_text(encoding="utf-8")
        self.assertIn("no control here matches that", js)

    def test_go_back_reaches_the_return_control_not_ask_go(self):
        """Ordering in the command table is load-bearing: the first match
        wins, and "go back" contains a bare "go". With GO listed first, the
        commonest navigation phrase on this screen opened a coordination pane
        instead of leaving."""
        js = (ROOT / "static" / "js" / "nipigon.js").read_text(encoding="utf-8")
        table = js[js.index("var COMMANDS = ["):]
        table = table[: table.index("];")]
        self.assertLess(table.index("np-return"), table.index("np-ask-go"))


if __name__ == "__main__":
    unittest.main()
