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
    DOCUMENTS,
    KNOWN_FACES,
    KNOWN_MINIATURE_BASES,
    MINIATURE_KIND,
    MINIATURE_LIVE,
    MINIATURE_VIEW,
    PAGE_FIELDS,
    documents_cited_by,
    composer_state,
    document_face,
    field_count,
    field_pins,
    page_fields,
    spin_trace,
    COUNT_REPLAYABLE_TRACES,
    FACE_COMPOSER,
    FACE_DOCUMENTS,
    FACE_DRAWING,
    FACE_INTAKE,
    FACE_SPIN,
)


def _field(face):
    """Select by face, never by index.

    PAGE_FIELDS is ordered for the SCREEN - Intake sits first because
    beginning is what a person arriving with nothing must be able to do - so
    an index here would silently start testing a different tile the moment
    the field is rearranged. It did, once.
    """
    return next(f for f in PAGE_FIELDS if f["face"] == face)

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


class PageFieldSpecimenTests(unittest.TestCase):
    """SCENE 1 - the Page-Field entry, specimen 01 (M-201 drawing).

    A Page-Field is a touchable miniature WINDOW INTO A SURFACE. These tests
    hold the two properties that separate it from a generic card, because both
    are invisible in a screenshot and both are the whole point:

      1. The `live` miniature is genuinely not a copy. It is the same
         plan_geometry macro the full canvas calls, so it cannot go stale.
      2. Every number the strip shows is DERIVED from the record, and is
         absent rather than zero when the record supports nothing.

    They are hermetic - the route reads fixture data from its own module and
    reaches no store, no AnalysisRun and no external boundary.
    """

    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_calm_field_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="field_admin",
                                password_hash=generate_password_hash("x"),
                                role="admin"))
            db.session.commit()
        self.findings = self._scored()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _scored(self):
        for finding in FINDINGS:
            finding["window"]["spent_percent"] = window_spent_percent(finding["window"])
            finding["prominence"] = assess(finding)
        return horizon_order(FINDINGS)

    def _body(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "field_admin"
            sess["role"] = "admin"
            sess["developer_mode"] = True
        response = client.get("/admin/calm-lake/")
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    # --- the vocabulary is closed ---------------------------------------

    def test_every_declared_field_uses_a_face_the_template_can_draw(self):
        """KNOWN_FACES is the set that RENDERS, not the set intended.

        A field declaring a face with no template branch would render an
        empty box - a card asserting a surface it cannot show, which is the
        precise failure the miniature-basis vocabulary exists to prevent.
        """
        for field in PAGE_FIELDS:
            self.assertIn(field["face"], KNOWN_FACES)

    def test_a_miniature_declares_a_basis_and_an_action_declares_none(self):
        """Intake is not a Page-Field and the model must not pretend it is.

        Every other tile is a window into an existing surface and says on
        what basis it shows it. Intake opens nothing - that is the point of
        it - so giving it a `live` or `kind` basis would be the same class of
        claim the vocabulary exists to refuse.
        """
        for field in PAGE_FIELDS:
            if field.get("action"):
                self.assertIsNone(field["miniature"])
            else:
                self.assertIn(field["miniature"], KNOWN_MINIATURE_BASES)

    def test_the_action_tile_declares_no_basis_in_the_markup_either(self):
        body = self._body()
        intake = body[body.index('id="field-INTAKE"'):]
        intake = intake[:intake.index("</button>")]
        self.assertNotIn("data-miniature", intake)

    def test_there_is_no_cached_miniature_basis(self):
        """A captured thumbnail cannot state its own age from inside itself."""
        self.assertEqual(set(KNOWN_MINIATURE_BASES), {MINIATURE_LIVE, MINIATURE_KIND})
        self.assertNotIn("cached", KNOWN_MINIATURE_BASES)

    # --- `live` means NOT A COPY, and that is structural ----------------

    def test_the_live_miniature_and_the_canvas_share_one_definition(self):
        """The claim `live` is only honest if there is one geometry source.

        Both the full canvas and the miniature call plan_geometry. If someone
        later inlines a second copy of the SVG, this fails - which is the
        moment the `live` badge would start lying.
        """
        template = _TEMPLATE_PATH.read_text(encoding="utf-8")
        self.assertIn('{% from "_calm_lake_plan.html" import plan_geometry %}', template)
        self.assertEqual(template.count("plan_geometry("), 2)
        # The geometry itself must NOT be inlined in the page template.
        self.assertNotIn('viewBox="0 0 1000 700"', template)

    def test_the_two_renderings_do_not_collide_on_svg_pattern_ids(self):
        """SVG ids are document-global.

        Rendering the same markup twice with a fixed pattern id makes the
        second instance silently reference the first one's pattern. The macro
        suffixes every id it emits; this proves the suffixes actually differ.
        """
        body = self._body()
        ids = re.findall(r'<pattern id="([^"]+)"', body)
        self.assertGreaterEqual(len(ids), 2)
        self.assertEqual(len(ids), len(set(ids)), "duplicate SVG pattern id: %r" % ids)

    def test_the_miniature_crops_the_viewport_and_never_the_geometry(self):
        """Cropping changes what is visible, never what the drawing is."""
        body = self._body()
        crop = "%s %s %s %s" % (MINIATURE_VIEW["x"], MINIATURE_VIEW["y"],
                                MINIATURE_VIEW["w"], MINIATURE_VIEW["h"])
        self.assertIn('viewBox="%s"' % crop, body)
        self.assertIn('viewBox="0 0 1000 700"', body)
        # Same room count in both renderings: the geometry is identical.
        self.assertEqual(body.count('class="cl-room"'), 12)

    def test_the_annotation_layer_is_dropped_only_in_the_miniature(self):
        """Grid refs and dimension ticks are legible at full size and mush at 170px."""
        body = self._body()
        self.assertEqual(body.count('class="cl-grid-ref"'), 6)
        self.assertEqual(body.count('class="cl-dim-tick"'), 8)

    # --- the pin is a second species, and it is positioned honestly -----

    def test_pins_are_projected_into_the_crop_not_used_raw(self):
        """A raw sheet percentage would place the pin in the wrong room.

        canvas x/y are percentages of the FULL sheet; the miniature shows a
        window onto it. This is arithmetic no screenshot review would catch.
        """
        field = _field(FACE_DRAWING)
        pins = field_pins(field, self.findings)
        self.assertTrue(pins, "specimen 01 must carry at least one pin")
        for pin in pins:
            expected_x = round(
                (pin["x"] / 100.0 * 1000.0 - MINIATURE_VIEW["x"]) / MINIATURE_VIEW["w"] * 100, 2)
            expected_y = round(
                (pin["y"] / 100.0 * 700.0 - MINIATURE_VIEW["y"]) / MINIATURE_VIEW["h"] * 100, 2)
            self.assertAlmostEqual(pin["mini_x"], expected_x, places=2)
            self.assertAlmostEqual(pin["mini_y"], expected_y, places=2)
            self.assertNotEqual(pin["mini_x"], pin["x"])

    def test_a_pin_exists_only_where_a_coordinate_space_does(self):
        """Only a drawing has somewhere for a pin to be honest about."""
        for field in PAGE_FIELDS:
            if field["face"] != FACE_DRAWING:
                self.assertEqual(field_pins(field, self.findings), [])

    def test_pin_prominence_is_carried_by_form_not_hue(self):
        """This file's ramp is monochrome; the tiers must survive greyscale."""
        css = _CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".cl-field-pin--foreground", css)
        self.assertIn(".cl-field-pin--tracked", css)
        foreground = css.split(".cl-field-pin--foreground")[1].split("}")[0]
        tracked = css.split(".cl-field-pin--tracked")[1].split("}")[0]
        # Filled vs hollow - a difference of form, not colour.
        self.assertIn("background: var(--w-ink)", foreground)
        self.assertIn("background: transparent", tracked)

    # --- every number is derived, and absent when unsupported ----------

    def test_the_strip_number_counts_grounded_citations_only(self):
        """A side at `asserted` names a document without establishing one."""
        field = _field(FACE_DRAWING)
        expected = len([f for f in self.findings
                        if field["id"] in documents_cited_by(f)])
        self.assertEqual(field_count(field, self.findings), expected)
        for finding in self.findings:
            for doc, basis in documents_cited_by(finding).items():
                self.assertIn(basis, (BASIS_LOCATED, BASIS_READ))
                self.assertNotEqual(basis, BASIS_ASSERTED)

    def test_a_field_with_nothing_countable_renders_no_number_at_all(self):
        """A zero is a measurement. Absence is the honest rendering."""
        field = dict(_field(FACE_DRAWING))
        field["counts"] = "an-unmeasured-kind"
        self.assertIsNone(field_count(field, self.findings))
        template = _TEMPLATE_PATH.read_text(encoding="utf-8")
        self.assertIn("{% if field.count is not none %}", template)

    def test_page_fields_carry_their_count_meaning(self):
        """A bare integer on a card is an unsourced claim."""
        for field in page_fields(self.findings):
            self.assertTrue(field["count_meaning"])

    # --- the field is genuinely touchable ------------------------------

    def test_the_field_is_a_real_focusable_button(self):
        """The archive's first fish was pointer-events:none and faked hits.

        See governance/proposals/fish-tank-design-archaeology.md sec 2: an
        object that LOOKS interactive and is inert to keyboard and touch is
        the failure this whole grammar is a correction of.
        """
        body = self._body()
        self.assertIn('data-ui-ref="calm-lake-page-field"', body)
        marker = body.index('data-ui-ref="calm-lake-page-field"')
        tag = body[body.rindex("<", 0, marker):marker]
        self.assertIn("<button", tag)
        self.assertIn('type="button"', tag)
        css = _CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".cl-field:focus-visible", css)

    def test_touch_and_keyboard_get_the_same_treatment(self):
        css = _CSS_PATH.read_text(encoding="utf-8")
        self.assertIn(".cl-field:hover,\n.cl-field:focus-visible", css)

    def test_an_idle_field_never_animates_transform(self):
        """CHANNEL SEPARATION, recovered from the archive (archaeology sec 3.1).

        A running animation on `transform` wins the cascade over the
        :hover/:focus-visible transform and silently deletes the focus
        affordance. Both surviving archive engines drove motion through
        layout position for exactly this reason.
        """
        css = _CSS_PATH.read_text(encoding="utf-8")
        block = css.split("SCENE 1 - THE PAGE-FIELD")[1].split("REDUCED MOTION")[0]
        self.assertNotIn("@keyframes", block)
        self.assertNotIn("animation:", block)

    def test_the_field_holds_a_deterministic_territory(self):
        """Same surface, same place, every visit - and the coordinate the
        expansion contracts back into."""
        body = self._body()
        css = _CSS_PATH.read_text(encoding="utf-8")
        for field in PAGE_FIELDS:
            row = "cl-field-slot--r%d" % field["territory"]["row"]
            col = "cl-field-slot--c%d" % field["territory"]["col"]
            self.assertIn(row, body)
            self.assertIn(col, body)
            # Enumerated, so a declared territory with no rule would silently
            # collapse to auto-placement and the field would move between
            # visits - which is the one thing a remembered coordinate cannot do.
            self.assertIn(".%s {" % row, css)
            self.assertIn(".%s {" % col, css)
        coords = {(f["territory"]["row"], f["territory"]["col"]) for f in PAGE_FIELDS}
        self.assertEqual(len(coords), len(PAGE_FIELDS), "two fields share a territory")

    def test_the_specimen_renders_its_identity_strip(self):
        body = self._body()
        self.assertIn("M201", body)
        self.assertIn("Level 02", body)

    def test_the_live_specimen_is_a_document_on_record(self):
        """The miniature may not claim `live` for a surface that is not there."""
        ids = {d["id"] for d in DOCUMENTS}
        for field in PAGE_FIELDS:
            if field["miniature"] == MINIATURE_LIVE:
                self.assertIn(field["id"], ids)


class SpinFaceSpecimenTests(unittest.TestCase):
    """SPECIMEN 02 - the Spin face.

    The face draws a derivation trace, and the whole claim is that it is
    DERIVED. No Spin fixture was invented for it: the trace already exists in
    the findings, because every finding carries `sides` and every side names a
    document and the basis on which it does so.

    These tests hold that the drawing on screen is a function of the record.
    If someone hardcodes a nicer-looking tree, they fail.
    """

    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_calm_spin_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="spin_admin",
                                password_hash=generate_password_hash("x"),
                                role="admin"))
            db.session.commit()
        for finding in FINDINGS:
            finding["window"]["spent_percent"] = window_spent_percent(finding["window"])
            finding["prominence"] = assess(finding)
        self.findings = horizon_order(FINDINGS)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _body(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "spin_admin"
            sess["role"] = "admin"
            sess["developer_mode"] = True
        response = client.get("/admin/calm-lake/")
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    # --- the trace is a function of the record --------------------------

    def test_the_trace_has_one_branch_per_finding_and_one_leaf_per_side(self):
        trace = spin_trace(self.findings)
        self.assertIsNotNone(trace)
        with_sides = [f for f in self.findings if f.get("sides")]
        self.assertEqual(len(trace["branches"]), len(with_sides))
        for branch, finding in zip(trace["branches"], with_sides):
            self.assertEqual(branch["id"], finding["id"])
            self.assertEqual(len(branch["leaves"]), len(finding["sides"]))

    def test_removing_a_side_removes_a_leaf(self):
        """The face is drawn from the record, not decorated to resemble it."""
        full = spin_trace(self.findings)
        leaves = sum(len(b["leaves"]) for b in full["branches"])

        trimmed = []
        for finding in self.findings:
            copy = dict(finding)
            if copy["id"] == "DAMPER-SD-14":
                copy["sides"] = finding["sides"][:1]
            trimmed.append(copy)

        after = spin_trace(trimmed)
        self.assertEqual(sum(len(b["leaves"]) for b in after["branches"]), leaves - 1)

    def test_an_asserted_side_draws_ungrounded(self):
        """It names a document without establishing one.

        Drawing it like evidence would make the claim the basis vocabulary
        exists to refuse - so the leaf is hollow and its link is broken.
        """
        trace = spin_trace(self.findings)
        ungrounded = [leaf for b in trace["branches"] for leaf in b["leaves"]
                      if not leaf["grounded"]]
        asserted = [s for f in self.findings for s in f["sides"]
                    if s["basis"] == BASIS_ASSERTED]
        self.assertEqual(len(ungrounded), len(asserted))
        self.assertTrue(ungrounded, "the fixture must keep one asserted side")
        for leaf in ungrounded:
            self.assertEqual(leaf["basis"], BASIS_ASSERTED)

    def test_grounded_means_the_same_thing_here_as_everywhere_else(self):
        trace = spin_trace(self.findings)
        for branch in trace["branches"]:
            for leaf in branch["leaves"]:
                self.assertEqual(leaf["grounded"],
                                 leaf["basis"] in (BASIS_LOCATED, BASIS_READ))

    def test_a_branch_sits_at_the_mean_of_its_own_leaves(self):
        """Deterministic layout, with no hand-placed constant to drift."""
        trace = spin_trace(self.findings)
        for branch in trace["branches"]:
            mean = sum(leaf["y"] for leaf in branch["leaves"]) / len(branch["leaves"])
            self.assertAlmostEqual(branch["y"], round(mean, 1), places=1)

    def test_a_record_with_no_sides_draws_nothing(self):
        """An empty face beats a plausible-looking invented one."""
        self.assertIsNone(spin_trace([]))
        self.assertIsNone(spin_trace([{"id": "X", "sides": [],
                                       "prominence": {"tier": PROMINENCE_TRACKED}}]))

    def test_exactly_one_node_is_the_active_clash(self):
        trace = spin_trace(self.findings)
        foreground = [b for b in trace["branches"] if b["tier"] == PROMINENCE_FOREGROUND]
        self.assertEqual(len(foreground), 1)

    # --- what reaches the page ------------------------------------------

    def test_the_rendered_trace_matches_the_record(self):
        body = self._body()
        sides = sum(len(f["sides"]) for f in self.findings)
        asserted = len([s for f in self.findings for s in f["sides"]
                        if s["basis"] == BASIS_ASSERTED])
        self.assertEqual(body.count('class="cl-trace-leaf"'), sides - asserted)
        self.assertEqual(body.count("cl-trace-leaf cl-trace-leaf--ungrounded"), asserted)
        self.assertEqual(body.count("cl-trace-node cl-trace-node--"), len(self.findings))
        self.assertEqual(body.count('class="cl-trace-root"'), 1)

    def test_the_spin_face_is_not_a_drawing(self):
        """Same palette, different species. A drawing face answers `where is
        it`; this one answers `how was it reached`."""
        body = self._body()
        trace = body.split('class="cl-field-trace"')[1].split("</svg>")[0]
        for drawing_only in ("cl-room", "cl-wall-outer", "cl-duct", "cl-stair"):
            self.assertNotIn(drawing_only, trace)

    def test_prominence_on_the_trace_is_form_not_hue(self):
        css = _CSS_PATH.read_text(encoding="utf-8")
        foreground = css.split(".cl-trace-node--foreground")[1].split("}")[0]
        self.assertIn("fill: var(--w-ink)", foreground)
        base = css.split("\n.cl-trace-node {")[1].split("}")[0]
        self.assertIn("fill: var(--w-surface)", base)

    # --- the count, again derived ---------------------------------------

    def test_the_trace_count_excludes_a_finding_that_reaches_nothing(self):
        """A finding whose every side is `asserted` has a derivation that
        lands on nothing, and is not a replayable trace."""
        field = [f for f in PAGE_FIELDS if f["counts"] == COUNT_REPLAYABLE_TRACES][0]
        self.assertEqual(field_count(field, self.findings),
                         len([f for f in self.findings if documents_cited_by(f)]))

        floating = {"id": "FLOATING", "prominence": {"tier": PROMINENCE_TRACKED},
                    "sides": [{"role": "names", "document": "Something",
                               "basis": BASIS_ASSERTED, "at": None}]}
        self.assertEqual(field_count(field, [floating]), 0)

    # --- the box is the same box ----------------------------------------

    def test_every_face_shares_one_bounding_box(self):
        """A Page-Field's outer geometry must not depend on which face it
        carries - the grid is a field of equals, not a collage."""
        css = _CSS_PATH.read_text(encoding="utf-8")
        face_block = css.split(".cl-field-face {")[1].split("}")[0]
        self.assertIn("aspect-ratio:", face_block)
        # The aspect is declared once, on .cl-field-face, and never overridden
        # per face - so adding a face cannot change the card's shape.
        self.assertEqual(css.count("aspect-ratio:"), 1)

    def test_specimen_02_is_declared_and_drawable(self):
        spin = [f for f in PAGE_FIELDS if f["face"] == FACE_SPIN]
        self.assertEqual(len(spin), 1)
        self.assertIn(FACE_SPIN, KNOWN_FACES)
        self.assertEqual(spin[0]["miniature"], MINIATURE_KIND)
        body = self._body()
        self.assertIn("Clash Trace", body)


class SceneSeparationTests(unittest.TestCase):
    """Two scenes, and only one of them on the page at a time.

    This existed once in a broken form worth naming: the field was rendered
    as a band bolted on TOP of the workspace, which made the entry
    environment a header row inside the very surface it is an entry to.
    These tests hold the corrected shape.
    """

    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_calm_scene_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="scene_admin",
                                password_hash=generate_password_hash("x"),
                                role="admin"))
            db.session.commit()
        for finding in FINDINGS:
            finding["window"]["spent_percent"] = window_spent_percent(finding["window"])
            finding["prominence"] = assess(finding)
        self.findings = horizon_order(FINDINGS)
        self.css = _CSS_PATH.read_text(encoding="utf-8")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _body(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "scene_admin"
            sess["role"] = "admin"
            sess["developer_mode"] = True
        response = client.get("/admin/calm-lake/")
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def test_the_page_lands_on_the_field(self):
        self.assertIn('data-scene="field"', self._body())

    def test_the_workspace_is_absent_not_merely_offscreen(self):
        """A hidden workspace still in the tab order is worse than an absent
        one: a phone user swiping through controls walks into a canvas they
        cannot see, and a screen reader announces a disturbance banner for a
        surface nobody opened."""
        self.assertIn('body.cl[data-scene="field"] .cl-surface { display: none; }', self.css)
        self.assertIn('body.cl[data-scene="surface"] .cl-scene { display: none; }', self.css)

    def test_the_workspace_is_wrapped_so_it_can_be_absent_as_one_thing(self):
        body = self._body()
        self.assertIn('<div class="cl-surface" id="cl-surface">', body)
        surface = body[body.index('id="cl-surface"'):]
        # Everything the working surface is made of lives inside the wrapper.
        for part in ('class="cl-header"', 'id="cl-lake"', 'class="cl-verbs"'):
            self.assertIn(part, surface)
        # ...and the field does not.
        scene = body[body.index('data-ui-ref="calm-lake-scene-1"'):body.index('id="cl-surface"')]
        for part in ('class="cl-verbs"', 'id="cl-lake"', 'class="cl-disturbance"'):
            self.assertNotIn(part, scene)

    def test_scene_one_carries_no_workspace_furniture(self):
        """No disturbance banner, no closing-window bar, no verb bar."""
        body = self._body()
        scene = body[body.index('data-ui-ref="calm-lake-scene-1"'):body.index('id="cl-surface"')]
        for banned in ("Closing window", "cl-halflife", "cl-disturbance",
                       "cl-verb", "cl-lake"):
            self.assertNotIn(banned, scene)

    def test_there_is_a_way_back(self):
        """A surface entered from the field must be leaveable from itself,
        not by a browser gesture the phone may not have."""
        body = self._body()
        self.assertIn('data-ui-ref="calm-lake-return"', body)
        surface = body[body.index('id="cl-surface"'):]
        self.assertIn('id="cl-return"', surface)
        self.assertIn(".cl-return:focus-visible", self.css)

    def test_the_field_fills_the_viewport(self):
        # Split on the rule at column 0: `.cl-scene {` also appears inside
        # body.cl[data-scene="surface"] .cl-scene { display: none; }, and
        # matching that one made this test pass against the wrong rule.
        block = self.css.split("\n.cl-scene {")[1].split("}")[0]
        self.assertIn("100dvh", block)

    def test_the_return_restores_focus_to_the_tile_that_was_opened(self):
        js = _JS_PATH.read_text(encoding="utf-8")
        self.assertIn('document.getElementById("field-" + openedFieldId)', js)
        self.assertIn("origin.focus()", js)

    def test_every_field_holds_a_distinct_territory(self):
        coords = [(f["territory"]["row"], f["territory"]["col"]) for f in PAGE_FIELDS]
        self.assertEqual(len(set(coords)), len(coords))
        self.assertEqual(len(PAGE_FIELDS), 5)


class ComposerAndDocumentFaceTests(unittest.TestCase):
    """SPECIMEN 03 and 04."""

    def setUp(self):
        for finding in FINDINGS:
            finding["window"]["spent_percent"] = window_spent_percent(finding["window"])
            finding["prominence"] = assess(finding)
        self.findings = horizon_order(FINDINGS)

    def test_the_composer_invents_no_exchange(self):
        """There is no conversation anywhere in the fixture module.

        The face may draw turn SHAPES; it may not draw sentences. If an
        exchange fixture is ever added, this test should be replaced
        deliberately rather than deleted quietly.
        """
        import routes.calm_lake_prototype as module
        for name in dir(module):
            self.assertNotIn(name.lower(), ("exchange", "messages", "turns",
                                            "conversation", "transcript"))

    def test_the_composer_is_bound_to_a_real_document(self):
        field = _field(FACE_COMPOSER)
        state = composer_state(field, self.findings)
        self.assertIsNotNone(state)
        self.assertIn(state["bound_id"], {d["id"] for d in DOCUMENTS})

    def test_the_composer_citations_are_the_bound_documents_own_sides(self):
        field = _field(FACE_COMPOSER)
        state = composer_state(field, self.findings)
        expected = [s for f in self.findings for s in f["sides"]
                    if s["basis"] in (BASIS_LOCATED, BASIS_READ)
                    and s["document"].split(" ")[0] == state["bound_id"]]
        self.assertEqual(len(state["citations"]), len(expected))
        for citation in state["citations"]:
            self.assertIn(citation["basis"], (BASIS_LOCATED, BASIS_READ))

    def test_an_unbound_composer_draws_nothing(self):
        self.assertIsNone(composer_state({"bound_to": None}, self.findings))
        self.assertIsNone(composer_state({"bound_to": "NOT-A-DOC"}, self.findings))

    def test_the_composer_qualifier_is_derived_from_its_binding(self):
        """Written twice, the two drift."""
        rendered = {f["id"]: f for f in page_fields(self.findings)}
        self.assertEqual(rendered["COMPOSER"]["qualifier"],
                         rendered["M-201"]["qualifier"])

    def test_the_document_stack_never_exaggerates_the_sheet_count(self):
        field = _field(FACE_DOCUMENTS)
        face = document_face(field)
        document = next(d for d in DOCUMENTS if d["id"] == field["id"])
        self.assertLessEqual(face["stack"], document["sheets"])
        self.assertEqual(face["sheets"], document["sheets"])

    def test_the_document_strip_reports_the_true_sheet_count(self):
        field = _field(FACE_DOCUMENTS)
        document = next(d for d in DOCUMENTS if d["id"] == field["id"])
        self.assertEqual(field_count(field, self.findings), document["sheets"])

    def test_the_intake_tile_counts_nothing(self):
        self.assertIsNone(field_count(_field(FACE_INTAKE), self.findings))
