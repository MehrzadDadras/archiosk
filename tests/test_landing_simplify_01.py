"""CLAUDE-LANDING-SIMPLIFY-01 - the landing composition, and how the brand is said.

Live Product Owner review found three things on the public front door: a
category subtitle the page does not need, a wordmark in a serif face that
appears nowhere else on the surface, and speech synthesis reading the brand
as something unrelated to its actual name.

The accepted composition is now just the wordmark and the three entry
actions. ARCHIOSK is Architecture + Kiosk, said approximately AR-kee-osk.

Static/rendered assertions only. No external boundary is reachable.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING_HTML = ROOT / "templates" / "landing.html"
LANDING_SHELL = ROOT / "templates" / "landing_shell.html"


class LandingCompositionTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.client = app_module.create_app("testing").test_client()
        self.body = self.client.get("/").get_data(as_text=True)

    def test_the_wordmark_is_still_there(self):
        self.assertIn("landing-wordmark", self.body)
        self.assertIn("Archiosk", self.body)

    def test_the_category_subtitle_is_gone(self):
        self.assertNotIn("Data Room Intelligence", self.body)

    def test_it_was_not_replaced_with_another_category_label(self):
        """Removing one slogan and installing another would miss the point:
        Archiosk does not need to define its category on its own front door."""
        lowered = self.body.lower()
        for label in (
            "construction procurement ecosystem", "procurement ecosystem",
            "project intelligence", "ai procurement", "data room",
        ):
            with self.subTest(label=label):
                self.assertNotIn(label, lowered)

    def test_no_tagline_element_is_rendered(self):
        self.assertNotIn('class="landing-tagline"', self.body)

    def test_the_three_entry_actions_are_intact(self):
        for ref, href in (
            ("landing.explore", "/explore"),
            ("landing.start-trial", "/start-trial"),
            ("landing.sign-in", "/login"),
        ):
            with self.subTest(action=ref):
                self.assertIn(f'data-ui-ref="{ref}"', self.body)
                self.assertIn(f'href="{href}"', self.body)

    def test_no_unsolicited_conversational_content_renders(self):
        """The voice affordance is a deliberate, icon-only button and its
        response card starts hidden - nothing conversational appears unless a
        visitor asks for it."""
        self.assertIn('id="landing-voice-result"', self.body)
        result = self.body[self.body.index('id="landing-voice-result"'):]
        self.assertIn("hidden", result[: result.index(">")])

    def test_the_background_and_motion_are_preserved(self):
        for marker in (
            "landing-page", "landing-field-canvas", "landing-knowledge-field",
            "landing-signal-streak", "js/ocean_field.js", "js/landing.js",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

    def test_the_page_title_carries_no_category_suffix(self):
        self.assertIn("<title>Archiosk</title>", self.body)
        for template in (LANDING_HTML, LANDING_SHELL):
            with self.subTest(template=template.name):
                text = template.read_text(encoding="utf-8")
                self.assertNotIn("Archiosk &mdash; Data Room Intelligence", text)


class OneTypographicLanguageTests(unittest.TestCase):
    """The wordmark is the strongest expression of the page's own type, not a
    second typeface."""

    def setUp(self):
        import app as app_module

        self.client = app_module.create_app("testing").test_client()
        # CRLF-normalized: .gitattributes does not pin this file's line
        # endings, so a Windows checkout serves it CRLF.
        raw = self.client.get("/static/css/landing.css").get_data(as_text=True).replace("\r\n", "\n")
        # Comments stripped before any substring scan: this section's own prose
        # names both the face it replaced and the one it deliberately avoided,
        # so scanning raw text would match the documentation, not the CSS.
        self.css = re.sub(r"/\*.*?\*/", " ", raw, flags=re.S)
        start = self.css.index(".landing-wordmark {")
        self.rule = self.css[start: self.css.index("}", start)]

    def test_the_wordmark_is_no_longer_serif(self):
        self.assertNotIn("Georgia", self.rule)
        self.assertNotIn("serif;", self.rule.replace("sans-serif;", ""))

    def test_it_uses_the_same_family_as_the_page_itself(self):
        page_start = self.css.index(".landing-page {")
        page_rule = self.css[page_start: self.css.index("}", page_start)]
        page_family = re.search(r"font-family:([^;]+);", page_rule).group(1).strip()
        wordmark_family = re.search(r"font-family:([^;]+);", self.rule).group(1).strip()
        self.assertEqual(wordmark_family, page_family)

    def test_distinction_comes_from_weight_scale_and_tracking(self):
        self.assertIn("font-weight: 600", self.rule)
        self.assertIn("letter-spacing", self.rule)
        self.assertIn("clamp(", self.rule)

    def test_no_second_display_face_was_introduced(self):
        """main.css's own test asserts "Space Grotesk" appears exactly once in
        this codebase, and no font file is shipped for it."""
        self.assertNotIn("Space Grotesk", self.css)


class BrandPronunciationTests(unittest.TestCase):
    """ARCHIOSK = Architecture + Kiosk, said approximately AR-kee-osk."""

    def setUp(self):
        import app as app_module

        self.client = app_module.create_app("testing").test_client()
        self.js = self.client.get("/static/js/landing.js").get_data(as_text=True)

    def test_the_spoken_greeting_is_spelled_phonetically(self):
        self.assertIn("Ar-kee-osk", self.js)

    def test_the_written_brand_is_not_handed_to_the_speech_engine(self):
        section = self.js[self.js.index("setUpSpokenWelcome"):]
        section = section[: section.index("})();")]
        self.assertNotIn("Welcome to Archiosk", section)

    def test_the_phonetic_spelling_is_never_shown_to_a_reader(self):
        """Audio-only. The visible wordmark and every accessible name keep the
        real spelling - a phonetic respelling on screen would be worse than
        the mispronunciation it fixes."""
        body = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("Ar-kee-osk", body)
        self.assertIn("Speak to Archiosk", body)

    def test_this_is_the_only_speech_synthesis_seam(self):
        """One authoritative source, so pronunciation is corrected centrally
        rather than patched per reply."""
        hits = [
            p for p in (ROOT / "static" / "js").glob("*.js")
            if "SpeechSynthesisUtterance" in p.read_text(encoding="utf-8")
        ]
        self.assertEqual([p.name for p in hits], ["landing.js"])


if __name__ == "__main__":
    unittest.main()
