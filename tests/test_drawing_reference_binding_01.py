"""
CLAUDE-DRAWING-REFS-01 - a drawing set cites itself, and the register already
knows how to hold that.

THE CLAIM BEING TESTED

A door tag on a plan pointing at a row in a door schedule is the same act as a
clause citing a Section: a reference from one part of the evidence to another.
So drawing tokens needed new PATTERNS and new TARGETS, not a second resolver.
KNOWN_REFERENCE_TYPES is open-world by design; RESOLUTION_STATUS_* is closed and
evaluator-owned. Nothing here changes the second one.

WHAT I GOT WRONG FIRST, AND WHY IT IS RECORDED HERE

I told the Product Owner that a duplicate mark - the same D-101 against two
different schedule rows - would surface as resolved_multiple or ambiguous. It
does not, and cannot. `known_targets` maps a reference type to a SET of
identifier strings, so two rows sharing a mark collapse into one entry before
the resolver ever sees them; the outcome is a confident resolved_exact.

The resolver is not defective for this. It answers "does this citation point at
something that exists", and by that question the answer is genuinely yes. Whether
the schedule contains two rows fighting over one mark is a property of the
SCHEDULE, not of the citation - so it is a query over registered rows, exactly
like an unreferenced schedule row is. Both are findings; neither is a status.

That distinction is the useful part, and it is only visible because the claim was
measured instead of asserted.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from collections import Counter

from services.case_workspace import (
    KNOWN_REFERENCE_TYPES,
    REFERENCE_TYPE_DETAIL_CALLOUT,
    REFERENCE_TYPE_GRID_INTERSECTION,
    REFERENCE_TYPE_SCHEDULE_MARK,
    REFERENCE_TYPE_SHEET,
    RESOLUTION_STATUS_RESOLVED_EXACT,
    RESOLUTION_STATUS_TARGET_NOT_FOUND,
    RESOLUTION_STATUS_UNKNOWN,
    RESOLUTION_STATUS_UNSUPPORTED_REFERENCE_TYPE,
    CaseWorkspaceStore,
    parse_source_reference_text,
    resolve_source_reference_candidate,
)


def _types(text, **kw):
    return [c["reference_type"] for c in parse_source_reference_text(text, **kw)]


def _one(text, **kw):
    found = parse_source_reference_text(text, **kw)
    assert len(found) == 1, "expected exactly one candidate, got %r" % (found,)
    return found[0]


class TheParserReadsHowADrawingCitesItself(unittest.TestCase):
    def test_a_detail_callout_is_read_as_one_reference(self):
        # "3/A-501" is detail 3 ON sheet A-501 - one citation, not a stray digit
        # next to a sheet. Same compound discipline as "Table 3, Row 5".
        candidate = _one("See 3/A-501 for the head detail.")
        self.assertEqual(candidate["reference_type"], REFERENCE_TYPE_DETAIL_CALLOUT)
        self.assertEqual(candidate["reference_text"], "3/A-501")
        self.assertEqual(candidate["candidate_targets"], ["A-501 Detail 3"])

    def test_the_callout_keeps_its_sheet_as_container(self):
        # The Table/Row compound records `container` so the citation can be
        # traced to the thing it lives inside. A callout has the same need.
        self.assertEqual(_one("Detail 12 / S-201A applies.")["container"], "S-201A")

    def test_a_callout_is_never_split_into_a_bare_sheet(self):
        # The failure this guards: reading the "A-501" half as its own sheet
        # reference registers a citation nobody wrote.
        self.assertEqual(_types("See 3/A-501."), [REFERENCE_TYPE_DETAIL_CALLOUT])

    def test_sheets_are_read_when_named_as_sheets(self):
        self.assertEqual(
            _types("Refer to Sheet A-501 and Drawing M-101."),
            [REFERENCE_TYPE_SHEET, REFERENCE_TYPE_SHEET])

    def test_marks_are_read_when_named_as_marks(self):
        self.assertEqual(
            _types("Door D-101 and Window W-05 are fire rated."),
            [REFERENCE_TYPE_SCHEDULE_MARK, REFERENCE_TYPE_SCHEDULE_MARK])

    def test_grid_intersections_normalise_their_separator(self):
        # "A-1" and "A/1" are the same intersection written two ways; the
        # candidate target must not depend on which the drafter typed.
        for text in ["Located at Grid A-1.", "Located at Grid A/1."]:
            with self.subTest(text=text):
                self.assertEqual(_one(text)["candidate_targets"], ["A-1"])

    def test_every_new_type_is_declared_known(self):
        for ref_type in (REFERENCE_TYPE_SHEET, REFERENCE_TYPE_DETAIL_CALLOUT,
                         REFERENCE_TYPE_SCHEDULE_MARK, REFERENCE_TYPE_GRID_INTERSECTION):
            with self.subTest(ref_type=ref_type):
                self.assertIn(ref_type, KNOWN_REFERENCE_TYPES)


class ABareMarkNeedsTheCallerToVouchForIt(unittest.TestCase):
    """A sheet id and a schedule mark are the same shape. Nothing syntactic
    separates "A-501" the sheet from "D-101" the door, and prefix-letter
    conventions differ between offices - so the parser does not guess."""

    def test_prose_does_not_turn_letter_dash_number_into_a_door(self):
        # The noise this prevents: a specification saying "clause D-101" is not
        # a door schedule citation.
        self.assertEqual(parse_source_reference_text("Clause D-101 applies."), [])

    def test_a_caller_that_knows_it_came_off_a_sheet_gets_the_mark(self):
        candidate = _one("D-101", include_drawing_tokens=True)
        self.assertEqual(candidate["reference_type"], REFERENCE_TYPE_SCHEDULE_MARK)
        self.assertEqual(candidate["candidate_targets"], ["D-101"])

    def test_a_keyword_led_mark_is_not_read_twice(self):
        # With bare matching on, "Door D-101" must still yield ONE reference -
        # the keyword form claims the span first, exactly like the compound
        # patterns do.
        self.assertEqual(len(parse_source_reference_text(
            "Door D-101 is rated.", include_drawing_tokens=True)), 1)


class ExistingReferenceReadingIsUnchanged(unittest.TestCase):
    """The drawing work must not move a single existing reading.

    These are the shapes the register was already built on; if adding drawing
    patterns disturbed them, the patterns are ordered wrongly.
    """

    def test_document_citations_still_read_as_before(self):
        self.assertEqual(
            _types("Section 4.1 and Figure 2 remain intact."), ["section", "figure"])

    def test_the_table_row_compound_still_wins_its_span(self):
        self.assertEqual(_types("Table 3, Row 5 remains intact."), ["table_row"])

    def test_drawing_patterns_are_off_by_default(self):
        # Every pre-existing caller passes no flag, so nothing they feed in can
        # start producing schedule marks it did not produce yesterday.
        self.assertEqual(parse_source_reference_text("Item D-101 in the list."), [])


class TheTaxonomyAlreadyCarriesEveryDrawingFinding(unittest.TestCase):
    """Resolution outcomes, measured rather than predicted."""

    SCHEDULE = {"schedule_mark": {"D-101", "D-102"}}

    def _status(self, text, known):
        return resolve_source_reference_candidate(
            _one(text, include_drawing_tokens=True), known)["resolution_status"]

    def test_a_tag_that_matches_a_row_resolves_exactly(self):
        self.assertEqual(self._status("D-101", self.SCHEDULE),
                         RESOLUTION_STATUS_RESOLVED_EXACT)

    def test_an_orphan_tag_is_target_not_found(self):
        # The headline finding: a door tagged on the plan that no schedule row
        # defines. It is not an error - it is the thing worth reporting.
        self.assertEqual(self._status("D-999", self.SCHEDULE),
                         RESOLUTION_STATUS_TARGET_NOT_FOUND)

    def test_an_ingested_but_empty_schedule_still_orphans_the_tag(self):
        # Key present, no rows: we HAVE the schedule and the tag is not in it.
        self.assertEqual(self._status("D-101", {"schedule_mark": set()}),
                         RESOLUTION_STATUS_TARGET_NOT_FOUND)

    def test_a_missing_schedule_is_not_reported_as_an_orphan(self):
        # Key absent: no schedule has been ingested, so we cannot say the tag is
        # undefined - only that we are not yet able to judge. Collapsing this
        # into target_not_found would manufacture findings out of missing data.
        self.assertEqual(self._status("D-101", {"section": {"4.1"}}),
                         RESOLUTION_STATUS_UNSUPPORTED_REFERENCE_TYPE)

    def test_no_new_status_was_invented(self):
        # RESOLUTION_STATUS_* is the resolver's own CLOSED vocabulary - the
        # module comment says "never open-world, never supplied by a caller".
        # Adding drawing findings must not widen it, so this enumerates what is
        # actually declared rather than trusting the intention.
        import services.case_workspace as cw

        declared = {v for k, v in vars(cw).items()
                    if k.startswith("RESOLUTION_STATUS_") and isinstance(v, str)}
        self.assertEqual(
            declared,
            {"resolved_exact", "resolved_range", "resolved_multiple", "ambiguous",
             "target_not_found", "unsupported_reference_type", "partially_resolved",
             "unknown"},
            "the drawing work must not extend the closed resolution vocabulary")


class TwoFindingsAreQueriesNotStatuses(unittest.TestCase):
    """The correction, kept as an executable statement of it.

    A duplicate mark and an unreferenced schedule row are both real findings and
    neither is a resolution outcome, because neither is a property of the
    citation. They are properties of the schedule, answered by looking at it.
    """

    SCHEDULE_ROWS = ["D-101", "D-101", "D-102", "D-103"]   # D-101 defined twice
    TAGS_ON_PLAN = ["D-101", "D-102", "D-999"]             # D-103 never cited

    def test_a_duplicate_mark_is_invisible_to_the_resolver(self):
        # Recorded because I claimed the opposite. The resolver is asked "does
        # this point at something real", and the honest answer is yes.
        known = {"schedule_mark": set(self.SCHEDULE_ROWS)}
        self.assertEqual(
            resolve_source_reference_candidate(
                _one("D-101", include_drawing_tokens=True), known)["resolution_status"],
            RESOLUTION_STATUS_RESOLVED_EXACT)

    def test_a_duplicate_mark_is_found_by_looking_at_the_schedule(self):
        duplicates = [m for m, n in Counter(self.SCHEDULE_ROWS).items() if n > 1]
        self.assertEqual(duplicates, ["D-101"])

    def test_an_unreferenced_row_is_found_the_same_way(self):
        # A schedule row nothing points at - the inverse of an orphan tag, and
        # the one drawing finding with no existing status slot. It needs none.
        unreferenced = set(self.SCHEDULE_ROWS) - set(self.TAGS_ON_PLAN)
        self.assertEqual(unreferenced, {"D-103"})


class AnOrphanTagSurvivesInTheRegister(unittest.TestCase):
    """Persistence, not just parsing.

    Prompt 18 #18: a reference is persisted even when it resolves to nothing,
    "rather than silently discarded". An orphan tag is precisely that case, and
    it is the case a linker exists to report - so losing it would be the worst
    possible failure mode.
    """

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="drawing-refs-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.store = CaseWorkspaceStore(self.dir)
        self.ws = self.store.get_or_create("proj-drawing")
        self.source = self.store.add_source(
            self.ws, name="A-501 Floor Plan", file_path="/tmp/a501.pdf", kind="drawing")

    def _register(self, text, known_targets):
        return self.store.extract_and_register_source_references(
            self.ws, self.source["id"], text,
            origin_context={"sheet": "A-501"},
            known_targets=known_targets,
            include_drawing_tokens=True,
            resolution_method="drawing_token_match",
            extractor_version="pdf_geometry_semantics_v1")

    def test_the_orphan_is_persisted_not_dropped(self):
        created = self._register("D-999", {"schedule_mark": {"D-101"}})
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["resolution_status"],
                         RESOLUTION_STATUS_TARGET_NOT_FOUND)

    def test_the_verbatim_tag_text_is_kept(self):
        created = self._register("D-999", {"schedule_mark": {"D-101"}})
        self.assertEqual(created[0]["reference_text"], "D-999")
        self.assertEqual(created[0]["reference_type"], REFERENCE_TYPE_SCHEDULE_MARK)

    def test_it_is_readable_back_off_the_saved_workspace(self):
        self._register("D-999", {"schedule_mark": {"D-101"}})
        reloaded = self.store.get("proj-drawing")
        orphans = [r for r in reloaded.source_references
                   if r["resolution_status"] == RESOLUTION_STATUS_TARGET_NOT_FOUND]
        self.assertEqual([r["reference_text"] for r in orphans], ["D-999"])

    def test_with_no_schedule_at_all_it_is_held_as_unknown(self):
        # known_targets omitted entirely - the schedule has not been ingested
        # yet. The tag is still recorded, so re-running once the schedule lands
        # is a re-resolution, not a re-extraction.
        created = self.store.extract_and_register_source_references(
            self.ws, self.source["id"], "D-999",
            origin_context={"sheet": "A-501"}, include_drawing_tokens=True)
        self.assertEqual(created[0]["resolution_status"], RESOLUTION_STATUS_UNKNOWN)

    def test_a_mixed_sheet_registers_each_kind_once(self):
        created = self._register(
            "Door D-101 at Grid A-1, see 3/A-501 and Sheet M-101.",
            {"schedule_mark": {"D-101"}})
        self.assertEqual(
            Counter(r["reference_type"] for r in created),
            Counter({REFERENCE_TYPE_SCHEDULE_MARK: 1, REFERENCE_TYPE_GRID_INTERSECTION: 1,
                     REFERENCE_TYPE_DETAIL_CALLOUT: 1, REFERENCE_TYPE_SHEET: 1}))


if __name__ == "__main__":
    unittest.main()
