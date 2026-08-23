"""
CLAUDE-CA1D-PUBLIC-LANDING-ANIMATION-CORRECTION-01/02 - sequence the
landing entrance so the signal streak fully disappears BEFORE the whole
text family (wordmark/tagline/CTAs/mic) begins to materialize, give that
materialization a consistent "apparition emerging from ether" character
(opacity 0 -> blur+scale -> sharp) across every family member, and give
the streak itself a forward-into-depth "spear toward the vanishing
point" motion rather than a lateral sideways slide.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import re
import unittest


class _LandingCssHelpers(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def _landing_css(self):
        """The served stylesheet, with CRLF line endings normalized to LF.

        landing.css is served raw, and .gitattributes deliberately does not
        pin its line endings, so on a Windows checkout with
        core.autocrlf=true it arrives CRLF. Every newline-anchored parse
        below then fails with a bare ValueError - notably
        _keyframe_block's end marker, which looks for a closing brace
        alone on its own line. This file previously passed only where the
        working copy happened to hold LF, which is an accident of how the
        file was last written rather than the canonical checkout state.
        Normalizing here makes these assertions mean the same thing on
        every platform.
        """
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        return css.replace("\r\n", "\n")

    def _rule(self, css, selector):
        start = css.index(selector)
        end = css.index("}", start)
        return css[start:end]

    def _keyframe_block(self, css, name):
        """Returns the full `@keyframes name { ... }` block, including
        every percentage/from/to stop - `}` alone is not a safe end
        marker since inline stops (`from { ...; }`) close on the same
        line as their own content. The block's own OUTER closing brace
        is always alone on its own line, so `\\n}\\n` reliably finds it
        without matching an inner stop's inline `}`."""
        start = css.index(f"@keyframes {name}")
        end = css.index("\n}\n", start) + 2
        return css[start:end]

    def _second_time_value_seconds(self, rule_text, keyframe_name):
        """Parses the `animation: <name> <duration> <...other tokens...>
        <delay>` shorthand actually used throughout this file. The two
        keywords ("ease"/cubic-bezier/"forwards") appear in different
        relative orders across different rules in this file, so this
        matches the keyframe name, skips to the first `<num>s`
        (duration), then finds the SECOND `<num>(s|ms)` before the
        terminating `;` (delay), wherever it falls relative to any
        keyword in between."""
        pattern = re.escape(keyframe_name) + r"\s+([\d.]+)s\b([^;]*)"
        match = re.search(pattern, rule_text)
        self.assertIsNotNone(match, f"could not find an animation declaration for {keyframe_name} in: {rule_text}")
        remainder = match.group(2)
        delay_match = re.search(r"([\d.]+)(m?s)\b", remainder)
        self.assertIsNotNone(delay_match, f"could not find a delay value for {keyframe_name} in: {rule_text}")
        value, unit = float(delay_match.group(1)), delay_match.group(2)
        return value / 1000 if unit == "ms" else value

    def _duration_seconds(self, rule_text, keyframe_name):
        match = re.search(re.escape(keyframe_name) + r"\s+([\d.]+)s\b", rule_text)
        self.assertIsNotNone(match)
        return float(match.group(1))


class StreakThenTextSequenceTests(_LandingCssHelpers):
    def _streak_total_seconds(self, css):
        streak_rule = self._rule(css, ".landing-signal-streak-1 {")
        delay = self._second_time_value_seconds(streak_rule, "landingSignalStreak1")
        duration = self._duration_seconds(streak_rule, "landingSignalStreak1")
        return delay + duration

    def test_streak_fully_disappears_before_wordmark_begins(self):
        css = self._landing_css()
        streak_total = self._streak_total_seconds(css)
        wordmark_rule = self._rule(css, ".landing-wordmark {")
        wordmark_delay = self._second_time_value_seconds(wordmark_rule, "landingWordmarkArrival")
        self.assertGreater(
            wordmark_delay, streak_total,
            "the wordmark must not begin materializing until strictly after the streak has fully faded out",
        )

    def test_text_family_members_start_after_the_streak_and_stay_subtly_staggered(self):
        css = self._landing_css()
        streak_total = self._streak_total_seconds(css)

        delays = []
        for selector, keyframe in (
            (".landing-wordmark {", "landingWordmarkArrival"),
            (".landing-tagline {", "landingTextMaterialize"),
            (".landing-actions {", "landingTextMaterialize"),
            (".landing-voice {", "landingTextMaterialize"),
        ):
            rule = self._rule(css, selector)
            delay = self._second_time_value_seconds(rule, keyframe)
            self.assertGreater(delay, streak_total, f"{selector} must start after the streak fully disappears")
            delays.append(delay)

        # Non-decreasing family order: ARCHIOSK, then tagline, then
        # actions, then voice - and "very subtle" means no single gap
        # dominates the sequence (each successive start is close behind
        # the previous one, not a long separate wait).
        self.assertEqual(delays, sorted(delays))
        for earlier, later in zip(delays, delays[1:]):
            self.assertLess(later - earlier, 1.0)

    def test_text_materialize_keyframe_has_opacity_blur_and_scale(self):
        """Section: 'start at opacity: 0, with a soft blur/haze,
        slightly scaled/diffused, then transition into fully sharp'."""
        css = self._landing_css()
        keyframe = self._keyframe_block(css, "landingTextMaterialize")
        self.assertIn("opacity: 0", keyframe)
        self.assertIn("opacity: 1", keyframe)
        self.assertIn("blur(", keyframe)
        self.assertIn("scale(", keyframe)

    def test_wordmark_arrival_keyframe_unchanged_shape_still_opacity_blur_scale(self):
        css = self._landing_css()
        keyframe = self._keyframe_block(css, "landingWordmarkArrival")
        self.assertIn("opacity: 0", keyframe)
        self.assertIn("blur(16px)", keyframe)
        self.assertIn("scale(3.2)", keyframe)

    def test_old_reveal_keyframe_fully_retired(self):
        """Checks the actual @keyframes/animation usage, not bare
        substrings - a historical comment naming the retired keyframe
        for context is fine (see UI_REFERENCE_MAP.md's own precedent for
        this exact distinction)."""
        css = self._landing_css()
        self.assertNotIn("@keyframes landingWordmarkReveal", css)
        self.assertNotIn("animation: landingWordmarkReveal", css)
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        self.assertNotIn("landingWordmarkReveal", js)

    def test_reduced_motion_still_covers_every_text_family_member(self):
        css = self._landing_css()
        reduced_motion_block = css[css.index("@media (prefers-reduced-motion: reduce)"):]
        for selector in (".landing-wordmark", ".landing-tagline", ".landing-actions", ".landing-voice"):
            self.assertIn(selector, reduced_motion_block)
        self.assertIn("animation: none !important", reduced_motion_block)
        self.assertIn("opacity: 1 !important", reduced_motion_block)


class SpearIntoDepthMotionTests(_LandingCssHelpers):
    """
    CLAUDE-CA1D-PUBLIC-LANDING-ANIMATION-CORRECTION-02: the streak must
    converge on the exact center (the vanishing point / where ARCHIOSK
    is about to appear), taper via scaleX as it approaches, and hold one
    fixed rotation angle throughout (never animated) so it visually
    points along its own direction of travel rather than sliding
    sideways like a plank.
    """

    def test_streak_converges_on_exact_center_not_a_lateral_crossing(self):
        css = self._landing_css()
        keyframe = self._keyframe_block(css, "landingSignalStreak1")
        self.assertIn("100% { transform: translate3d(0, 0, 0)", keyframe)

    def test_streak_rotation_angle_is_fixed_not_animated(self):
        css = self._landing_css()
        keyframe = self._keyframe_block(css, "landingSignalStreak1")
        angles = re.findall(r"rotate\((-?[\d.]+deg)\)", keyframe)
        self.assertGreaterEqual(len(angles), 2)  # at least the 0% and 100% stops
        self.assertEqual(len(set(angles)), 1, f"rotation must stay constant across every stop, found: {angles}")

    def test_streak_tapers_via_scale_x_rather_than_a_constant_size_slide(self):
        """Section: 'perspective scaling, tapering... aligned with the
        direction of travel' - scaleX must vary meaningfully across the
        keyframe (grow through the fast-motion middle, then taper to
        near-nothing at the vanishing point), not stay near-constant
        like the old lateral-slide version."""
        css = self._landing_css()
        keyframe = self._keyframe_block(css, "landingSignalStreak1")
        scale_values = [float(v) for v in re.findall(r"scaleX\(([\d.]+)\)", keyframe)]
        self.assertGreaterEqual(len(scale_values), 3)
        self.assertGreater(max(scale_values), 1.2, "must visibly elongate during the fast-motion middle stretch")
        self.assertLess(scale_values[-1], 0.2, "must taper to near-nothing exactly as it reaches the vanishing point")

    def test_streak_still_fades_to_invisible_at_the_end(self):
        css = self._landing_css()
        keyframe = self._keyframe_block(css, "landingSignalStreak1")
        self.assertIn("100% { transform: translate3d(0, 0, 0) rotate(", keyframe)
        final_stop = keyframe[keyframe.index("100%"):]
        self.assertIn("opacity: 0", final_stop)


if __name__ == "__main__":
    unittest.main()
