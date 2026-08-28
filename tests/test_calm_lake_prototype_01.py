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

    def test_the_wireframe_ramp_is_neutral_grayscale(self):
        # Every --w-* colour token must have equal R, G and B. This is the
        # governing "do not beautify an unproven IA" constraint, enforced
        # rather than left to discipline.
        for name, value in re.findall(r"(--w-[a-z0-9-]+):\s*(#[0-9A-Fa-f]{6});", self.css):
            r, g, b = value[1:3], value[3:5], value[5:7]
            self.assertEqual({r.lower()}, {g.lower(), b.lower()}, f"{name} is not gray: {value}")

    def test_disturbance_authority_and_machine_greys_are_identical(self):
        # Deliberately the same value: if the layout only reads correctly
        # once these diverge, it was depending on colour.
        found = dict(re.findall(r"(--w-(?:accent|authority|machine)):\s*(#[0-9A-Fa-f]{6});", self.css))
        self.assertEqual(len(found), 3)
        self.assertEqual(len(set(v.lower() for v in found.values())), 1)


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

    def test_the_desktop_breakpoint_adds_no_control_and_removes_none(self):
        desktop = self.css[self.css.index("@media (min-width: 1024px)"):]
        # display:none anywhere in the desktop block would mean a control
        # exists at one width and not the other.
        self.assertNotIn("display: none", desktop.replace(".cl-scrim { display: none; }", ""))

    def test_verb_dispatch_has_no_viewport_branch(self):
        # If a verb behaved differently at 390px than at 1600px, the single
        # grammar claim would be false in the place hardest to notice.
        for banned in ("matchMedia", "innerWidth", "clientWidth >", "outerWidth"):
            self.assertNotIn(banned, self.js, banned)

    def test_the_template_renders_the_verb_bar_from_a_single_loop(self):
        self.assertEqual(self.template.count("{% for verb in verbs %}"), 1)
        self.assertEqual(self.template.count('data-verb="{{ verb.id }}"'), 1)

    def test_no_inline_style_attributes_anywhere(self):
        # app.py's CSP sets default-src 'self' with no style-src directive,
        # so a parsed inline style attribute is refused by the browser.
        self.assertNotIn('style="', self.template)


if __name__ == "__main__":
    unittest.main()
