"""
CLAUDE-CALM-LAKE-SURFACE-PROTOTYPE-01 - structural tests for the Calm Lake
wireframe.

These are WIREFRAME-PHASE tests and they are deliberately narrow. They check
the things the directive says the surface must demonstrate - what is
permanently visible, what is conditional, that the disturbance is driven by a
closing window rather than by severity, that the basis vocabulary renders
distinguishably, and that one verb list renders at every width. They do not
check appearance, because appearance is what this phase is deliberately
withholding.

They are hermetic: the route reads fixture data held in its own module and
touches no store, no AnalysisRun and no external boundary, so nothing here can
reach ingest_upload/BHiveParser.parse or any network call.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from routes.calm_lake_prototype import (
    PROMINENCE_FOREGROUND,
    PROMINENCE_TRACKED,
    assess,
    evidence_is_grounded,
    window_is_closing,
    BASIS_ASSERTED,
    BASIS_LOCATED,
    BASIS_NONE,
    BASIS_READ,
    FINDINGS,
    KNOWN_CITATION_BASES,
    THRESHOLD_DAYS,
    horizon_order,
    window_spent_percent,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CSS_PATH = _REPO_ROOT / "static" / "css" / "calm_lake.css"
_JS_PATH = _REPO_ROOT / "static" / "js" / "calm_lake.js"
_TEMPLATE_PATH = _REPO_ROOT / "templates" / "calm_lake_prototype.html"


class HorizonOrderingTests(unittest.TestCase):
    """The ordering is the claim: consequence x window, never severity."""

    def test_every_fixture_finding_uses_the_closed_basis_vocabulary(self):
        for finding in FINDINGS:
            self.assertIn(finding["window"]["basis"], KNOWN_CITATION_BASES)
            for side in finding["sides"]:
                self.assertIn(side["basis"], KNOWN_CITATION_BASES)

    def test_ordering_is_not_severity_all_three_are_high(self):
        # If any fixture finding stopped being "high", this test would pass
        # for the wrong reason - so assert the premise it rests on.
        self.assertEqual({f["severity"] for f in FINDINGS}, {"high"})

    def test_closing_window_outranks_a_wide_one_at_equal_severity(self):
        order = [f["id"] for f in horizon_order(FINDINGS)]
        self.assertLess(order.index("DAMPER-SD-14"), order.index("DOOR-D-106"))

    def test_a_window_with_no_basis_sorts_last_not_first(self):
        # "We don't know when" must never be able to claim urgency by being
        # unknown. That is the fluency failure in scheduling clothes.
        order = [f["id"] for f in horizon_order(FINDINGS)]
        self.assertEqual(order[-1], "PRESSURE-STAIR-2")

    def test_only_one_finding_is_inside_the_threshold(self):
        inside = [
            f for f in FINDINGS
            if f["window"]["days_remaining"] is not None
            and f["window"]["days_remaining"] <= THRESHOLD_DAYS
        ]
        self.assertEqual([f["id"] for f in inside], ["DAMPER-SD-14"])

    def test_spent_percent_is_elapsed_fraction_of_the_original_window(self):
        self.assertEqual(window_spent_percent({"total_days": 21, "days_remaining": 4}), 81)
        self.assertEqual(window_spent_percent({"total_days": 48, "days_remaining": 31}), 35)

    def test_spent_percent_is_none_when_there_is_no_window(self):
        # Not 0 and not 100: an empty bar would read as "no time has passed",
        # which is a claim the record does not support.
        self.assertIsNone(window_spent_percent({"total_days": None, "days_remaining": None}))


class BasisRenderingTests(unittest.TestCase):
    """Bases differing in strength must not be rendered identically."""

    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")

    def _rule(self, selector):
        idx = self.css.index(selector)
        return self.css[idx:self.css.index("}", idx)]

    def test_each_basis_has_its_own_rule(self):
        for basis in KNOWN_CITATION_BASES:
            self.assertIn(f".cl-basis--{basis}", self.css, basis)

    def test_located_read_and_asserted_are_not_rendered_identically(self):
        located = self._rule(".cl-basis--located {")
        read = self._rule(".cl-basis--read {")
        asserted = self._rule(".cl-basis--asserted {")
        self.assertNotEqual(located, read)
        self.assertNotEqual(read, asserted)
        self.assertNotEqual(located, asserted)

    def test_asserted_is_distinguished_by_form_not_only_by_colour(self):
        # The whole reason this wireframe is grayscale: if the weakest basis
        # were distinguished by hue alone, the distinction would vanish in a
        # screenshot, in print, and for a colour-blind reader.
        asserted = self._rule(".cl-basis--asserted {")
        self.assertIn("dashed", asserted)
        self.assertIn("italic", asserted)
        # Not a chip at all - no filled box.
        self.assertIn("border: 0", asserted)

    def test_the_ramp_is_a_cool_near_neutral_and_never_warm(self):
        # SUPERSEDED, deliberately: the wireframe phase required a strictly
        # neutral R==G==B ramp. The polish directive asks for dark slate
        # text over cool grey metadata, so exact neutrality is no longer
        # the rule. What replaces it is the constraint that actually
        # mattered - the ramp must stay a near-neutral, and must never warm
        # up into anything that could read as a semantic accent.
        tokens = re.findall(r"(--w-[a-z0-9-]+):\s*(#[0-9A-Fa-f]{6});", self.css)
        self.assertGreaterEqual(len(tokens), 8)
        for name, value in tokens:
            r, g, b = (int(value[i:i + 2], 16) for i in (1, 3, 5))
            # Cool or neutral: blue is never the weakest channel, red never
            # the strongest. This is what excludes every warm accent.
            self.assertLessEqual(r, g, f"{name} is warm: {value}")
            self.assertLessEqual(g, b, f"{name} is warm: {value}")
            # And still near-neutral rather than a blue. For scale: amber
            # #7A4A08 spreads 122 and machine-blue #235066 spreads 67, so
            # this bound admits a slate and excludes any real accent.
            self.assertLessEqual(max(r, g, b) - min(r, g, b), 32,
                                 f"{name} is too saturated to be a neutral: {value}")

    def test_no_semantic_accent_token_exists_at_all(self):
        # Stronger than the rule it replaces. The wireframe defined
        # --w-accent/--w-authority/--w-machine as deliberately identical
        # greys; the polish pass removes them entirely, so there is no
        # token that could later be quietly given a hue. Prominence,
        # grounding and authority are carried by weight, fill and form.
        for banned in ("--w-accent", "--w-authority", "--w-machine"):
            self.assertNotIn(banned, self.css, banned)


class SurfaceStructureTests(unittest.TestCase):
    """What is permanent, what is conditional, what is absent."""

    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_calm_lake_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="lake_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="lake_reader", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client(self, username, user_id, role="admin", developer_mode=False):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
            if developer_mode:
                sess["developer_mode"] = True
        return client

    def _body(self):
        client = self._client("lake_admin", 1, developer_mode=True)
        response = client.get("/admin/calm-lake/")
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    # --- the gate -------------------------------------------------------

    def test_anonymous_cannot_reach_the_prototype(self):
        response = self.flask_app.test_client().get("/admin/calm-lake/")
        self.assertNotEqual(response.status_code, 200)

    def test_read_only_cannot_reach_the_prototype(self):
        client = self._client("lake_reader", 2, role="read_only", developer_mode=True)
        self.assertNotEqual(client.get("/admin/calm-lake/").status_code, 200)

    def test_admin_without_developer_mode_is_refused(self):
        client = self._client("lake_admin", 1, developer_mode=False)
        self.assertEqual(client.get("/admin/calm-lake/").status_code, 403)

    # --- permanently visible --------------------------------------------

    def test_project_header_names_the_project_and_the_active_drawing(self):
        body = self._body()
        self.assertIn('data-ui-ref="calm-lake-header"', body)
        self.assertIn("Project Smoke Detector", body)
        self.assertIn("M-201 Level 2 Mechanical Plan", body)

    def test_the_four_verbs_render_from_one_list(self):
        body = self._body()
        for verb in ("look", "point", "ask", "commit"):
            self.assertIn(f'data-verb="{verb}"', body, verb)
        self.assertEqual(body.count("data-verb="), 4)

    def test_commit_is_disabled_until_something_is_selected_and_says_why(self):
        body = self._body()
        idx = body.index('data-verb="commit"')
        self.assertIn("disabled", body[idx - 200:idx + 200])
        self.assertIn("Commit needs a selection", body)

    # --- the disturbance -------------------------------------------------

    def test_the_disturbance_is_the_closing_window_not_the_severest_finding(self):
        body = self._body()
        self.assertIn('data-ui-ref="calm-lake-disturbance"', body)
        banner = body[body.index('data-ui-ref="calm-lake-disturbance"'):]
        banner = banner[:banner.index("</section>")]
        self.assertIn("SD-14", banner)
        # Both other findings are severity "high" and neither may appear.
        self.assertNotIn("D-106", banner)
        self.assertNotIn("Stair 2", banner)

    def test_only_one_disturbance_banner_exists(self):
        self.assertEqual(self._body().count('data-ui-ref="calm-lake-disturbance"'), 1)

    def test_the_banner_offers_the_why_route(self):
        body = self._body()
        self.assertIn('data-ui-ref="calm-lake-why"', body)
        self.assertIn('data-open-finding="DAMPER-SD-14"', body)

    # --- progressive depth ------------------------------------------------

    def test_depth_carries_basis_what_changed_and_horizon_in_that_order(self):
        body = self._body()
        depth = body[body.index('id="cl-depth"'):]
        self.assertLess(depth.index(">Basis<"), depth.index(">What changed<"))
        self.assertLess(depth.index(">What changed<"), depth.index(">Actionability horizon<"))

    def test_every_finding_carries_its_verification_badge(self):
        # Tier 0 is never optional: an assertion that renders without its
        # badge is a fluency defect however calm the surface looks.
        body = self._body()
        self.assertEqual(body.count("cl-verification"), len(FINDINGS))

    def test_a_negative_finding_states_the_extent_of_the_check(self):
        body = self._body()
        self.assertIn("9 damper tags on M-201, 8 matched", body)
        self.assertIn("documents examined", body)

    def _side(self, body, finding_id, basis):
        """The one <li> for a given side, so an assertion about that side
        cannot accidentally pass or fail on a neighbouring side's markup."""
        card = body[body.index(f'id="finding-{finding_id}"'):]
        card = card[:card.index("</article>")]
        start = card.index(f"cl-side cl-side--{basis}")
        return card[start:card.index("</li>", start)]

    def test_an_asserted_basis_offers_no_route_to_a_document(self):
        # The Arm B failure, rendered as the surface declining to render it.
        side = self._side(self._body(), "PRESSURE-STAIR-2", BASIS_ASSERTED)
        self.assertIn(f"cl-basis--{BASIS_ASSERTED}", side)
        self.assertIn("No record to show", side)
        self.assertNotIn("data-show=", side)

    def test_only_a_located_basis_may_promise_to_show_a_place(self):
        # A `read` side knows which document, not where in it. Offering
        # "show on drawing" for one would manufacture a location - the same
        # corollary that forbids citing a location for an absent thing.
        body = self._body()
        located = self._side(body, "DAMPER-SD-14", BASIS_LOCATED)
        self.assertIn("Show on drawing", located)

        read = self._side(body, "PRESSURE-STAIR-2", BASIS_READ)
        self.assertIn("data-show=", read)          # the document is reachable
        self.assertNotIn("Show on drawing", read)  # but not as a place
        self.assertIn("Open SP-001", read)

    def test_an_absent_side_cites_the_gap_not_a_location(self):
        side = self._side(self._body(), "DAMPER-SD-14", BASIS_READ)
        self.assertIn("Show the gap in M-601", side)

    def test_a_finding_with_no_located_side_offers_no_show_on_drawing_footer(self):
        body = self._body()
        card = body[body.index('id="finding-PRESSURE-STAIR-2"'):]
        card = card[:card.index("</article>")]
        self.assertNotIn("cl-show-drawing", card)
        self.assertIn("Nothing on record locates this on a drawing", card)

    def test_no_governed_action_is_offered_on_an_asserted_basis(self):
        body = self._body()
        card = body[body.index('id="finding-PRESSURE-STAIR-2"'):]
        card = card[:card.index("</article>")]
        self.assertNotIn("data-commit=", card)
        self.assertIn("cl-commit-withheld", card)

    def test_a_grounded_finding_does_offer_the_governed_action(self):
        body = self._body()
        self.assertIn('data-commit="DAMPER-SD-14"', body)
        self.assertIn("Approval-gated", body)

    # --- what is absent ----------------------------------------------------

    def test_the_surface_carries_no_permanent_document_tree_or_chat_pane(self):
        body = self._body()
        # The document index and the Composer exist, but only as sheets that
        # start hidden. Neither may be present as a permanent pane.
        for marker in ('id="cl-index"', 'id="cl-composer"', 'id="cl-depth"'):
            idx = body.index(marker)
            self.assertIn("hidden", body[idx:idx + 200], marker)

    def test_the_prototype_declares_itself_as_fixture_on_its_own_face(self):
        self.assertIn("Nothing here is a record", self._body())

    def test_the_wireframe_does_not_load_the_application_stylesheet(self):
        # It must not be able to regress any existing page, and it must not
        # borrow the semantic palette this phase is deliberately withholding.
        body = self._body()
        self.assertIn("css/calm_lake.css", body)
        self.assertNotIn("css/main.css", body)
        self.assertNotIn("css/tokens.css", body)


class SingleGrammarTests(unittest.TestCase):
    """Desktop is the 390px grammar with more bandwidth - not a second one."""

    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")
        self.js = _JS_PATH.read_text(encoding="utf-8")
        self.template = _TEMPLATE_PATH.read_text(encoding="utf-8")

    def test_the_desktop_breakpoint_hides_only_touch_affordances(self):
        # display:none in the desktop block means something exists at one
        # width and not the other, which is what would falsify the single
        # grammar. Exactly two are allowed, and neither is a control:
        #
        #   .cl-scrim - a docked sheet occludes nothing, so dimming the
        #               surface behind it would be gratuitous. Dismissal is
        #               unchanged (Close, Escape, press the drawing).
        #   .cl-grab  - a grab handle affords a swipe. There is no swipe
        #               with a mouse, and the swipe handler itself is gated
        #               on this element's visibility rather than on width.
        #
        # Any third one is a real violation.
        desktop = self.css[self.css.index("@media (min-width: 1024px)"):]
        hidden = [
            line.strip() for line in desktop.splitlines()
            if "display: none" in line
        ]
        self.assertEqual(len(hidden), 2, hidden)
        self.assertTrue(any(h.startswith(".cl-scrim") for h in hidden), hidden)
        self.assertTrue(any(h.startswith(".cl-grab") for h in hidden), hidden)

    def test_verb_dispatch_has_no_viewport_branch(self):
        # If a verb behaved differently at 390px than at 1600px, the single
        # grammar claim would be false in the place hardest to notice.
        #
        # Comments are stripped before searching. The earlier version of
        # this test matched raw source and so failed on the file's own
        # header note explaining that there is no matchMedia in it - a test
        # that punished documenting the very property it checks.
        code = re.sub(r"/\*.*?\*/", "", self.js, flags=re.S)
        code = re.sub(r"^\s*//.*$", "", code, flags=re.M)
        for banned in ("matchMedia", "innerWidth", "outerWidth", "clientWidth >"):
            self.assertNotIn(banned, code, banned)

    def test_the_template_renders_the_verb_bar_from_a_single_loop(self):
        self.assertEqual(self.template.count("{% for verb in verbs %}"), 1)
        self.assertEqual(self.template.count('data-verb="{{ verb.id }}"'), 1)

    def test_the_desktop_sheet_docks_by_insetting_rather_than_overlaying(self):
        # SUPERSEDED by a better fix for the same defect. The wireframe
        # stopped the side sheet 84px above the floor so it would not cover
        # Ask and Commit. Docking removes the problem at its root: the body
        # is inset by exactly the dock width while a sheet is open, so the
        # sheet sits BESIDE the surface and can safely run full height.
        # Nothing is occluded and the drawing is never clipped - it simply
        # has less room and refits.
        desktop = self.css[self.css.index("@media (min-width: 1024px)"):]
        self.assertIn("body.cl.is-docked", desktop)
        self.assertIn("padding-right: var(--w-dock)", desktop)
        self.assertIn("--w-dock: 380px", self.css)
        # And the JS must state the fact, without deciding what it means.
        self.assertIn('classList.toggle("is-docked"', self.js)

    def test_the_drawing_refits_when_the_dock_changes_the_space(self):
        # Otherwise docking would crop the drawing rather than make room
        # for the sheet, which is the thing docking exists to avoid.
        self.assertIn("refitSoon(SLIDE_MS", self.js)

    def test_no_uppercase_typography_anywhere(self):
        # The earlier version of this test asserted the claim OVERRODE a
        # uppercase heading rule. The polish directive removes harsh caps
        # from the surface altogether, so the override is no longer needed
        # and the stronger property is asserted instead: no rule in the
        # file transforms text to uppercase at all. Hierarchy is weight
        # and colour.
        self.assertNotIn("text-transform", self.css)
        # The specificity fix is still required - `.cl-claim` alone is
        # (0,1,0) and loses to `.cl-sheet-head h2` at (0,1,1) - because the
        # claim still needs its own weight and size against the sheet
        # headings it shares a container with.
        self.assertIn(".cl-sheet-head h2.cl-claim", self.css)

    def test_marks_counter_scale_so_provenance_stays_reachable_at_any_zoom(self):
        # LOD invariance: annotation density may thin as a drawing zooms
        # out, but the route to a finding's basis must not. Without this the
        # tags render at ~36% at 390px and are unreadable on arrival.
        self.assertIn("--w-inv", self.css)
        self.assertIn('setProperty("--w-inv", 1 / view.scale)', self.js)

    def test_the_surface_opens_fitted_rather_than_at_one_to_one(self):
        # The sheet is 1000 CSS px wide; at 390px an unfitted surface opens
        # showing a fragment of one room, which falsifies "the drawing
        # occupies the screen" on arrival.
        self.assertIn("box.width / PLAN_W", self.js)
        self.assertNotIn("view.scale = 1;", self.js)

    def test_no_inline_style_attributes_anywhere(self):
        # app.py's CSP sets default-src 'self' with no style-src directive,
        # so a parsed inline style attribute is refused by the browser.
        self.assertNotIn('style="', self.template)


if __name__ == "__main__":
    unittest.main()


class ProminenceTests(unittest.TestCase):
    """Multi-variable, no binary silence, and deliberately not a number."""

    def setUp(self):
        for finding in FINDINGS:
            finding["window"]["spent_percent"] = window_spent_percent(finding["window"])
            finding["prominence"] = assess(finding)

    def test_no_finding_is_ever_silenced(self):
        # The correction this model exists for. Every finding is in exactly
        # one band and both bands are visible; a long runway buys quiet, not
        # absence.
        tiers = [f["prominence"]["tier"] for f in FINDINGS]
        self.assertEqual(set(tiers), {PROMINENCE_FOREGROUND, PROMINENCE_TRACKED})
        self.assertEqual(len(tiers), len(FINDINGS))

    def test_prominence_is_not_a_score(self):
        # An earlier revision returned a weighted product and rendered
        # "0.771" on the surface. The weights were invented, so the
        # precision was manufactured - a number that looks like evidence
        # and is not, which is the fluency failure one level up from
        # citations. And a scalar cannot be argued with.
        for finding in FINDINGS:
            state = finding["prominence"]
            self.assertNotIn("score", state)
            for value in state.values():
                self.assertNotIsInstance(value, float)

    def test_every_band_placement_states_its_reasons_in_words(self):
        for finding in FINDINGS:
            reasons = finding["prominence"]["reasons"]
            self.assertTrue(reasons, finding["id"])
            for reason in reasons:
                # A sentence, not a label or a number.
                self.assertGreater(len(reason.split()), 4, reason)
                self.assertTrue(reason.endswith("."), reason)

    def test_a_long_runway_is_tracked_and_says_so(self):
        door = next(f for f in FINDINGS if f["id"] == "DOOR-D-106")
        self.assertEqual(door["prominence"]["tier"], PROMINENCE_TRACKED)
        self.assertTrue(door["prominence"]["closing"] is False)
        # Same consequence and the same grounded evidence as the finding
        # that DID escalate - only the window differs.
        self.assertTrue(door["prominence"]["grounded"])
        self.assertTrue(door["prominence"]["severe"])
        self.assertIn("not yet closing", " ".join(door["prominence"]["reasons"]))

    def test_a_partly_asserted_finding_cannot_escalate(self):
        # Weak evidence must LOWER prominence, never raise it. A claim
        # resting partly on its own sentence must not be able to shout.
        stair = next(f for f in FINDINGS if f["id"] == "PRESSURE-STAIR-2")
        self.assertEqual(stair["prominence"]["tier"], PROMINENCE_TRACKED)
        self.assertFalse(stair["prominence"]["grounded"])
        self.assertFalse(stair["prominence"]["actionable"])

    def test_grounded_requires_every_side_not_merely_one(self):
        # "any" would let one located citation launder a second leg that is
        # only a sentence, which is what the basis vocabulary exists to stop.
        self.assertTrue(evidence_is_grounded({
            "sides": [{"basis": BASIS_LOCATED}, {"basis": BASIS_READ}]}))
        self.assertFalse(evidence_is_grounded({
            "sides": [{"basis": BASIS_LOCATED}, {"basis": BASIS_ASSERTED}]}))
        self.assertFalse(evidence_is_grounded({"sides": []}))

    def test_an_unestablished_window_is_never_treated_as_closing(self):
        # "We do not know when" becoming "act now" is truth-promotion
        # wearing scheduling clothes.
        self.assertFalse(window_is_closing({
            "basis": BASIS_NONE, "days_remaining": None, "total_days": None}))

    def test_a_window_can_close_by_proportion_as_well_as_by_days(self):
        # A long window nearly exhausted and a short window barely begun are
        # the cases the two readings disagree on, and both must be caught.
        self.assertTrue(window_is_closing({
            "basis": BASIS_READ, "days_remaining": 20, "total_days": 100}))
        self.assertTrue(window_is_closing({
            "basis": BASIS_READ, "days_remaining": 3, "total_days": 400}))
        self.assertFalse(window_is_closing({
            "basis": BASIS_READ, "days_remaining": 60, "total_days": 100}))


class LivenessTests(unittest.TestCase):
    """Restrained motion: emergence and feedback, never decoration."""

    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")
        self.js = _JS_PATH.read_text(encoding="utf-8")

    def test_no_animation_loops(self):
        # A permanently animated element is permanent chrome by another
        # name, and an alert that keeps moving is not calm.
        self.assertNotIn("infinite", self.css)
        self.assertNotIn("alternate", self.css)

    def test_every_animation_runs_exactly_once(self):
        for decl in re.findall(r"animation:\s*([^;]+);", self.css):
            self.assertTrue(decl.rstrip().endswith("1"), decl)

    def test_reduced_motion_is_respected(self):
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)
        block = self.css[self.css.index("@media (prefers-reduced-motion: reduce)"):]
        self.assertIn("animation-duration", block)
        self.assertIn("transition-duration", block)

    def test_pins_do_not_transition_the_property_that_carries_zoom(self):
        # `transition: all` would animate the counter-scale transform on
        # every zoom tick and make the pins swim behind the drawing.
        rule = self.css[self.css.index(".cl-mark {"):]
        rule = rule[:rule.index("}")]
        self.assertIn("transition:", rule)
        self.assertNotIn("transition: all", rule)
        self.assertNotIn("transform", rule.split("transition:")[1].split(";")[0])

    def test_show_on_drawing_pans_to_the_coordinate(self):
        # Not merely a fit-and-pulse: the surface travels to the evidence,
        # which is what keeps it one continuous space rather than a jump.
        self.assertIn("function focusOnMark", self.js)
        self.assertIn("view.x = -dx * scale", self.js)
        self.assertIn("view.y = -dy * scale", self.js)

    def test_sheets_transition_rather_than_appear(self):
        # `hidden` cannot be transitioned, so the open path must clear
        # hidden first and add the class on a later frame.
        self.assertIn("requestAnimationFrame", self.js)
        self.assertIn('classList.add("is-open")', self.js)
        self.assertIn(".cl-sheet.is-open", self.css)
        self.assertIn("transform: translateY(100%)", self.css)

    def test_swipe_dismissal_is_gated_on_the_handle_not_on_width(self):
        self.assertIn("grab.offsetHeight", self.js)


class SpatialContinuityTests(unittest.TestCase):
    """Travelling to evidence, not jumping to a different page."""

    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")
        self.js = _JS_PATH.read_text(encoding="utf-8")
        self.template = _TEMPLATE_PATH.read_text(encoding="utf-8")

    def test_the_refit_guard_is_checked_when_the_timer_fires(self):
        # Show-on-drawing dismisses the sheet, which SCHEDULES a refit, and
        # then focuses the coordinate a few milliseconds later. With the
        # guard evaluated at schedule time the refit still ran afterwards
        # and reset the view to fit, so the surface travelled nowhere.
        # Confirmed in-browser: before and after were identical.
        body = self.js[self.js.index("function refitSoon"):]
        body = body[:body.index("\n    }")]
        guard = body.index("readerAdjustedView")
        timer = body.index("setTimeout")
        self.assertLess(timer, guard,
                        "the guard must sit inside the timer callback, not before it")

    def test_focus_centres_the_mark_rather_than_merely_fitting(self):
        # Verified in-browser at 1600x800: the pin's centre lands on the
        # lake's centre exactly, and the scale rises from fit to a reading
        # zoom rather than staying put.
        self.assertIn("function focusOnMark", self.js)
        self.assertIn("view.x = -dx * scale", self.js)
        self.assertIn("view.y = -dy * scale", self.js)

    def test_overlay_affordances_share_one_anchor_box(self):
        # The instrumentation toggle was fixed to the viewport while the
        # selection readout and the Look controls are absolute within the
        # drawing area, so the two were measured from different boxes and
        # overlapped by 19px at 1600x800.
        for selector in (".cl-instrument-toggle", ".cl-selection", ".cl-look"):
            rule = self.css[self.css.index(selector + " {"):]
            rule = rule[:rule.index("}")]
            self.assertIn("position: absolute", rule, selector)
        # And it must live inside the lake for that anchor to be the lake.
        lake = self.template[self.template.index('id="cl-lake"'):]
        lake = lake[:lake.index("</main>")]
        self.assertIn('id="cl-instrument-toggle"', lake)

    def test_mobile_sheets_sit_above_the_anchored_verb_bar(self):
        # Verified in-browser at 390x844 by rectangle intersection: a
        # full-height bottom sheet covered all four verbs. Keeping the bar
        # reachable is what lets a reader go from Why straight to Ask.
        rule = self.css[self.css.index(".cl-sheet {"):]
        rule = rule[:rule.index("}")]
        self.assertIn("var(--w-anchor-h)", rule)
        self.assertIn("--w-anchor-h", self.css)
