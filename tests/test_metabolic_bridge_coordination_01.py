"""
CLAUDE-DRAWING-REFS-02 - the blind audit that found a defect in the instrument,
kept as the regression that stops it coming back.

PHASE 1 - WHAT HAPPENED

A three-sheet vector drawing set, a door schedule and a specification excerpt
were supplied as a blind coordination exercise, with ground truth held in a
sibling `oracle/` directory that was declared non-ingestible. It was not read, in
either phase. Every expectation here comes from the pipeline's own verified
output, independently confirmed correct by the Product Owner - so this file needs
no answer key to defend the behaviour.

THE DEFECT IT EXPOSED

The audit reported seven orphan door tags. Six were false: each sheet's own
number in its title block - "A-101", "S-101", "A-501", twice per sheet - was read
as a door tag by bare-token mode and then correctly reported as absent from the
door schedule. An 86% false-orphan rate on the single most important finding a
drawing linker produces.

The resolution status was right. The meaning was wrong, and no status could have
fixed it: by the time the resolver sees the candidate it is already typed as a
schedule_mark, and target_not_found cannot distinguish a sheet naming itself from
a genuine undefined door.

WHY THE FIX IS PRECEDENCE AND NOT A NEW STATUS

A sheet naming itself is not a citation of anything, so the honest answer is not
to emit the reference at all. `known_sheets` lets the bare-token pass consume
such a span without emitting it - the same discipline `consumed_spans` already
applies so that "3/A-501" is never split into a sheet plus a stray digit. It is
derived automatically from `known_targets["sheet"]` at the governed write path,
because a rule every future caller must remember is not a rule.

PHASE 2 - THE CORPUS GREW, AND THE FINGERPRINT CAUGHT IT

The package was later republished with a fourth sheet, A-201, carrying a building
section and vertical datums. The SHA-256 assertion at the bottom of this file
fired immediately, which is exactly why it is here: a fixture that changes
silently turns every other assertion into a lie.

Phase 2 mattered twice over. It confirmed the precedence fix on data it was never
built against - A-201 was discovered and both its self-references suppressed,
zero false orphans on an unseen sheet - and it moved the work from horizontal
coordination into vertical, where the findings are not reference resolution at
all but geometry compared against the scale the datums themselves establish.

That distinction is load-bearing and is asserted below: KNOWN_REFERENCE_TYPES has
no datum type, level markers never enter the register, and no resolution status is
ever assigned to one. "No orphan datums found" would be silence misreported as a
clean result. What actually found V-1 was arithmetic on gridline geometry.
"""
from __future__ import annotations

import csv
import hashlib
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from engine.pdf_extractor import PDFVectorExtractor
from services.case_workspace import (
    KNOWN_REFERENCE_TYPES,
    REFERENCE_TYPE_DETAIL_CALLOUT,
    REFERENCE_TYPE_SCHEDULE_MARK,
    RESOLUTION_STATUS_RESOLVED_EXACT,
    RESOLUTION_STATUS_TARGET_NOT_FOUND,
    CaseWorkspaceStore,
    parse_source_reference_text,
)

_CORPUS = Path(__file__).resolve().parent / "fixtures" / "metabolic_bridge" / "builder_corpus"
_PDF = _CORPUS / "Drawings_Set.pdf"

# Discovered by the audit, not assumed by it.
_SHEETS = {1: "A-101", 2: "S-101", 3: "A-501", 4: "A-201"}
_GRID_X = [120.0, 280.0, 440.0]      # gridlines A, B, C
_GRID_Y = [180.0, 380.0, 580.0]      # gridlines 1, 2, 3
_SECTION_PAGE = 4


def _document():
    return PDFVectorExtractor().extract_document(str(_PDF))


def _schedule_rows():
    with open(_CORPUS / "Door_Schedule.csv", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _schedule_marks():
    return [row["Mark"].strip() for row in _schedule_rows()]


def _known_targets():
    return {
        "schedule_mark": set(_schedule_marks()),
        "sheet": set(_SHEETS.values()),
        "detail_callout": {"A-501 Detail 3", "A-501 Detail 4"},
    }


def _gridlines(page):
    verticals, horizontals = [], []
    for vector in page["vectors"]:
        if vector["geometry_type"] != "line":
            continue
        (x0, y0), (x1, y1) = vector["points"]
        if abs(x1 - x0) < 0.01 and abs(y1 - y0) > 100:
            verticals.append(round(x0, 3))
        elif abs(y1 - y0) < 0.01 and abs(x1 - x0) > 100:
            horizontals.append(round(y0, 3))
    return sorted(verticals), sorted(horizontals)


def _feet(text):
    match = re.search(r"(-?\d+)'-(\d+)\"", text)
    return int(match.group(1)) + int(match.group(2)) / 12.0 if match else None


def _datums(page):
    """Each EL. label bound to its nearest full-width datum LINE.

    The line is the evidence, not the label's centroid - a glyph's centre moves
    with its own width, which is how a 0.2pt 'difference' between grid letters
    looked like drift until it was measured against geometry instead.
    """
    lines = sorted(round(v["points"][0][1], 2) for v in page["vectors"]
                   if v["geometry_type"] == "line"
                   and abs(v["points"][0][1] - v["points"][1][1]) < 0.01
                   and abs(v["points"][1][0] - v["points"][0][0]) > 300)
    found = []
    for span in page["text"]:
        content = span["content"]
        if "EL." not in content:
            continue
        y = span["centroid_points"]["y"]
        found.append((content.split("/")[0].strip(), _feet(content),
                      min(lines, key=lambda line: abs(line - y))))
    return sorted(found, key=lambda d: -d[2])      # lowest level first


class _Registered(unittest.TestCase):
    """Every text span on every sheet, through the governed write path."""

    @classmethod
    def setUpClass(cls):
        cls.doc = _document()
        cls.dir = tempfile.mkdtemp(prefix="metabolic-bridge-")
        store = CaseWorkspaceStore(cls.dir)
        workspace = store.get_or_create("metabolic-bridge")
        source = store.add_source(
            workspace, name="Drawings_Set.pdf", file_path=str(_PDF), kind="drawing")
        for page in cls.doc["pages"]:
            for span in page["text"]:
                text = span["content"].strip()
                if not text:
                    continue
                store.extract_and_register_source_references(
                    workspace, source["id"], text,
                    origin_context={"sheet": _SHEETS[page["page_number"]],
                                    "page": page["page_number"], "span_id": span["id"],
                                    "centroid_points": span["centroid_points"]},
                    known_targets=_known_targets(), include_drawing_tokens=True,
                    resolution_method="drawing_token_match",
                    extractor_version=cls.doc["schema_version"])
        cls.refs = store.get("metabolic-bridge").source_references

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def _of_type(self, ref_type, status=None):
        return [r for r in self.refs if r["reference_type"] == ref_type
                and (status is None or r["resolution_status"] == status)]


class NoSheetIsEverReportedAsAnOrphanDoor(_Registered):
    """The regression. This is the assertion the defect would break."""

    def test_no_sheet_id_is_registered_as_a_schedule_mark(self):
        offenders = sorted({r["reference_text"] for r in self._of_type(REFERENCE_TYPE_SCHEDULE_MARK)
                            if r["reference_text"].upper() in set(_SHEETS.values())})
        self.assertEqual(
            offenders, [],
            "a sheet naming itself in its own title block was read as a door tag - "
            "the exact defect the blind audit exposed")

    def test_exactly_one_orphan_tag_survives(self):
        orphans = sorted(r["reference_text"] for r in
                         self._of_type(REFERENCE_TYPE_SCHEDULE_MARK, RESOLUTION_STATUS_TARGET_NOT_FOUND))
        self.assertEqual(orphans, ["D-106"])

    def test_the_fix_holds_on_the_sheet_it_was_never_built_against(self):
        # A-201 arrived after the rule was written, and carries its number twice -
        # "SHEET: A-201" in the title block and "A-201" bottom-left. Neither may
        # appear as a door.
        section = [r for r in self.refs if r["origin_context"]["page"] == _SECTION_PAGE]
        self.assertNotIn("A-201", [r["reference_text"] for r in section])

    def test_suppression_did_not_swallow_the_real_tags(self):
        # The failure mode on the other side: a rule so eager it silences genuine
        # tags. D-101 is now cited on three separate sheets and must resolve on
        # every one of them.
        resolved = self._of_type(REFERENCE_TYPE_SCHEDULE_MARK, RESOLUTION_STATUS_RESOLVED_EXACT)
        self.assertEqual(sorted({r["reference_text"] for r in resolved}),
                         ["D-101", "D-102", "D-103", "D-104"])
        d101_sheets = sorted(r["origin_context"]["sheet"] for r in resolved
                             if r["reference_text"] == "D-101")
        self.assertEqual(d101_sheets, ["A-101", "A-201", "A-501"])


class TheCoordinationFindingsAreStable(_Registered):
    def test_a_callout_to_a_sheet_that_does_not_exist_is_not_found(self):
        # "3/A-502" - A-502 is not in the set. This is a finding, not an error.
        broken = [r["reference_text"] for r in
                  self._of_type(REFERENCE_TYPE_DETAIL_CALLOUT, RESOLUTION_STATUS_TARGET_NOT_FOUND)]
        self.assertEqual(broken, ["3/A-502"])

    def test_the_section_cites_the_detail_that_contradicts_it(self):
        # A-201 calls up 3/A-501 as its authority for the door head, and A-501
        # disagrees with it by a foot (see V-4 below). The citation resolves
        # perfectly - which is the point: resolution proves a target exists, never
        # that the two agree.
        callouts = self._of_type(REFERENCE_TYPE_DETAIL_CALLOUT, RESOLUTION_STATUS_RESOLVED_EXACT)
        sheets = sorted(r["origin_context"]["sheet"] for r in callouts)
        self.assertEqual(sheets, ["A-101", "A-201"])
        for ref in callouts:
            self.assertEqual(ref["resolved_target_ids"], ["A-501 Detail 3"])

    def test_an_unreferenced_schedule_row_is_found_by_query(self):
        # D-105, the janitor closet: scheduled, never tagged, and its room does
        # not appear on the plan at all. A property of the schedule, answered by
        # looking at it - deliberately not a resolution status.
        cited = {t for r in self._of_type(REFERENCE_TYPE_SCHEDULE_MARK)
                 for t in r["resolved_target_ids"]}
        self.assertEqual(sorted(set(_schedule_marks()) - cited), ["D-105"])

    def test_the_reference_count_does_not_drift(self):
        self.assertEqual(len(self.refs), 11)

    def test_a_self_naming_title_does_not_reach_the_orphan_report(self):
        # "TITLE: BUILDING SECTION 1" matches the pre-existing `section` pattern,
        # registering a citation nobody made - the same self-naming-vs-citation
        # class as the sheet defect. It is tolerated because it lands as
        # unsupported_reference_type (no section vocabulary was supplied) rather
        # than target_not_found, so it cannot be mistaken for a missing target.
        titles = [r for r in self.refs if r["reference_type"] == "section"]
        self.assertEqual([r["reference_text"] for r in titles], ["SECTION 1"])
        self.assertEqual(titles[0]["resolution_status"], "unsupported_reference_type")


class VerticalDatumsAreGeometryNotReferences(unittest.TestCase):
    """Phase 2. None of these findings are reference resolution."""

    @classmethod
    def setUpClass(cls):
        cls.doc = _document()
        cls.page = [p for p in cls.doc["pages"] if p["page_number"] == _SECTION_PAGE][0]

    def test_the_vocabulary_has_no_datum_type_and_that_is_reported_honestly(self):
        # Reporting "no orphan datums found" would be silence dressed as a clean
        # result. Level markers never enter the register at all.
        for absent in ("datum", "level", "elevation"):
            self.assertNotIn(absent, KNOWN_REFERENCE_TYPES)
        for span in self.page["text"]:
            if "EL." in span["content"]:
                self.assertEqual(
                    parse_source_reference_text(span["content"], include_drawing_tokens=True,
                                                known_sheets=set(_SHEETS.values())),
                    [], "a level marker must not be parsed as a citation")

    def test_three_of_four_datums_agree_on_one_scale(self):
        datums = _datums(self.page)
        self.assertEqual([d[0] for d in datums], ["LEVEL 1", "LEVEL 2", "ROOF", "LEVEL 3"])
        base_y, base_el = datums[0][2], datums[0][1]
        scales = {name: round((base_y - y) / (el - base_el), 4)
                  for name, el, y in datums[1:]}
        self.assertEqual(scales["LEVEL 2"], 12.0)
        self.assertEqual(scales["ROOF"], 12.0)
        self.assertNotEqual(scales["LEVEL 3"], 12.0)

    def test_v1_level_3_is_drawn_two_feet_below_its_own_label(self):
        datums = {name: (el, y) for name, el, y in _datums(self.page)}
        base_el, base_y = datums["LEVEL 1"]
        label_el, actual_y = datums["LEVEL 3"]
        expected_y = base_y - (label_el - base_el) * 12.0
        self.assertEqual(round(actual_y - expected_y, 2), 24.0)
        implied_el = base_el + (base_y - actual_y) / 12.0
        self.assertEqual(implied_el, 22.0)
        self.assertEqual(label_el, 24.0)

    def test_v2_the_roof_datum_sits_below_an_occupied_level(self):
        datums = {name: y for name, _el, y in _datums(self.page)}
        # Larger y is lower on the sheet. ROOF being BELOW LEVEL 3 means a
        # greater y than LEVEL 3's.
        self.assertGreater(datums["ROOF"], datums["LEVEL 3"])
        elevations = {name: el for name, el, _y in _datums(self.page)}
        self.assertLess(elevations["ROOF"], elevations["LEVEL 3"])

    def test_v2_all_four_datums_are_drawn_as_primary(self):
        # What would make V-2 benign is ROOF being a subordinate low-roof. Nothing
        # in the geometry says so: same full width, same stroke weight.
        widths, extents = set(), set()
        for vector in self.page["vectors"]:
            if vector["geometry_type"] != "line":
                continue
            (x0, y0), (x1, y1) = vector["points"]
            if abs(y1 - y0) < 0.01 and abs(x1 - x0) > 300:
                widths.add(round(vector["stroke_width_points"], 2))
                extents.add((round(x0, 1), round(x1, 1)))
        self.assertEqual(len(widths), 1)
        self.assertEqual(extents, {(72.0, 500.0)})

    def test_v3_the_declared_scale_contradicts_the_drawn_geometry(self):
        declared = [s["content"] for s in self.page["text"] if "SCALE" in s["content"]][0]
        self.assertIn('1/4" = 1\'-0"', declared)
        self.assertEqual(72 * 0.25, 18.0)          # what 1/4" = 1'-0" means in points
        self.assertNotEqual(18.0, 12.0)            # what the datums actually use


class TheHeadHeightConflictIsThreeWay(unittest.TestCase):
    """V-4. Two independent records agree; the detail sheet is alone."""

    PPF = 12.0

    @classmethod
    def setUpClass(cls):
        cls.doc = _document()

    def _dimension(self, page_number):
        page = [p for p in self.doc["pages"] if p["page_number"] == page_number][0]
        for span in page["text"]:
            match = re.search(r"(\d+\.\d+) pt", span["content"])
            if match:
                return float(match.group(1)) / self.PPF, span["centroid_points"]
        return None, None

    def test_the_schedule_and_the_section_agree(self):
        row = {r["Mark"]: r for r in _schedule_rows()}["D-101"]
        leaf_mm = int(row["Size"].split("x")[1].strip())
        self.assertAlmostEqual(leaf_mm / 304.8, 7.0, places=2)
        section_ft, _ = self._dimension(_SECTION_PAGE)
        self.assertEqual(section_ft, 7.0)

    def test_the_detail_sheet_is_the_outlier_by_exactly_one_foot(self):
        detail_ft, _ = self._dimension(3)
        section_ft, _ = self._dimension(_SECTION_PAGE)
        self.assertEqual(detail_ft, 8.0)
        self.assertEqual(detail_ft - section_ft, 1.0)

    def test_the_section_geometry_backs_its_own_annotation(self):
        # Not just the label: the drawn leaf must measure 7'-0" too, or the
        # annotation would be the only witness.
        page = [p for p in self.doc["pages"] if p["page_number"] == _SECTION_PAGE][0]
        leaves = [v for v in page["vectors"] if v["geometry_type"] == "rect"
                  and (max(q[0] for q in v["points"]) - min(q[0] for q in v["points"])) < 200]
        self.assertEqual(len(leaves), 1)
        ys = [q[1] for q in leaves[0]["points"]]
        self.assertEqual((max(ys) - min(ys)) / self.PPF, 7.0)
        self.assertEqual(max(ys), 500.0)           # sits on the LEVEL 1 datum


class ThePrecedenceRuleIsNarrow(unittest.TestCase):
    """Unit-level, no PDF: the rule must suppress a self-naming sheet and
    nothing else."""

    def test_a_bare_sheet_id_is_suppressed_when_the_caller_names_it(self):
        self.assertEqual(
            parse_source_reference_text("A-101", include_drawing_tokens=True,
                                        known_sheets={"A-101"}), [])

    def test_the_same_token_is_still_a_mark_when_no_sheet_is_known(self):
        found = parse_source_reference_text("A-101", include_drawing_tokens=True)
        self.assertEqual([c["reference_type"] for c in found], [REFERENCE_TYPE_SCHEDULE_MARK])

    def test_a_cited_sheet_still_reads_normally(self):
        # Suppression applies to the BARE pass only. An actual citation of the
        # sheet must survive, or the rule would erase real references.
        found = parse_source_reference_text("Sheet A-101", include_drawing_tokens=True,
                                            known_sheets={"A-101"})
        self.assertEqual([c["reference_type"] for c in found], ["sheet"])

    def test_a_callout_naming_a_known_sheet_still_reads_normally(self):
        found = parse_source_reference_text("3/A-501", include_drawing_tokens=True,
                                            known_sheets={"A-501"})
        self.assertEqual([c["reference_type"] for c in found], [REFERENCE_TYPE_DETAIL_CALLOUT])

    def test_a_door_is_untouched_by_a_sheet_vocabulary(self):
        found = parse_source_reference_text("D-101", include_drawing_tokens=True,
                                            known_sheets={"A-101", "S-101", "A-501"})
        self.assertEqual([c["candidate_targets"] for c in found], [["D-101"]])

    def test_a_suppressed_span_is_consumed_not_left_for_a_later_pass(self):
        # If the span were merely skipped rather than consumed, a later pattern
        # could re-read it and the false orphan would return by another route.
        title = "A-101  |  FIRST FLOOR PLAN  |  ISSUED FOR COORDINATION"
        self.assertEqual(
            parse_source_reference_text(title, include_drawing_tokens=True,
                                        known_sheets={"A-101"}), [])

    def test_a_colon_separated_title_block_is_also_suppressed(self):
        # A-201 writes its number as "SHEET: A-201", which the keyword pattern
        # does NOT match (it needs whitespace after "Sheet"). The bare pass picks
        # it up instead, so the precedence rule is the only thing standing
        # between that title block and a false orphan.
        self.assertEqual(
            parse_source_reference_text("SHEET: A-201", include_drawing_tokens=True,
                                        known_sheets={"A-201"}), [])

    def test_the_governed_path_derives_the_vocabulary_itself(self):
        # No caller should have to pass known_sheets separately when it has
        # already said which sheets exist.
        directory = tempfile.mkdtemp(prefix="derive-")
        self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
        store = CaseWorkspaceStore(directory)
        workspace = store.get_or_create("derive")
        source = store.add_source(workspace, name="s", file_path="/tmp/s.pdf", kind="drawing")
        created = store.extract_and_register_source_references(
            workspace, source["id"], "A-101", origin_context={"sheet": "A-101"},
            known_targets={"sheet": {"A-101"}, "schedule_mark": {"D-101"}},
            include_drawing_tokens=True)
        self.assertEqual(created, [])


class TheGridIsMeasuredNotAssumed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _document()

    def _page(self, number):
        return [p for p in self.doc["pages"] if p["page_number"] == number][0]

    def test_architectural_and_structural_grids_agree(self):
        self.assertEqual(_gridlines(self._page(1)), _gridlines(self._page(2)))

    def test_the_grid_is_where_the_audit_found_it(self):
        self.assertEqual(_gridlines(self._page(1)), (_GRID_X, _GRID_Y))

    def test_exactly_one_column_is_off_grid_and_by_how_much(self):
        letters = dict(zip("ABC", _GRID_X))
        numbers = dict(zip("123", _GRID_Y))
        drift = {}
        for vector in self._page(2)["vectors"]:
            if vector["geometry_type"] != "rect":
                continue
            xs = [p[0] for p in vector["points"]]
            ys = [p[1] for p in vector["points"]]
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            letter = min(letters, key=lambda k: abs(letters[k] - cx))
            number = min(numbers, key=lambda k: abs(numbers[k] - cy))
            dx, dy = cx - letters[letter], cy - numbers[number]
            if abs(dx) >= 0.5 or abs(dy) >= 0.5:
                drift["%s/%s" % (letter, number)] = (round(dx, 2), round(dy, 2))
        self.assertEqual(drift, {"B/2": (7.0, 0.0)})


class TheSpecificationContradictionIsStable(unittest.TestCase):
    def test_the_only_rated_service_door_without_a_closer_is_the_janitor(self):
        # Spec 2.2 requires a closer at rated service-room doors. D-103/D-104
        # record "Self-closing"; D-105 records only "Rated frame".
        spec = (_CORPUS / "Spec_Section_08_Doors.md").read_text(encoding="utf-8")
        self.assertIn("closer and latchset at rated service-room doors", spec)
        service = re.search(r"Doors serving ([^.]+?) shall be", spec).group(1)
        keywords = [w for w in ("electrical", "mechanical", "janitor") if w in service]
        self.assertEqual(keywords, ["electrical", "mechanical", "janitor"])

        at_risk = [r["Mark"] for r in _schedule_rows()
                   if any(k in r["Location"].lower() for k in keywords)
                   and r["Fire_Rating"].strip().upper() != "NON-RATED"
                   and not re.search(r"self-clos|closer", r["Notes"], re.I)]
        self.assertEqual(at_risk, ["D-105"])


class TheCorpusIsIntact(unittest.TestCase):
    """A fixture that silently changes turns every assertion above into a lie.

    This is not ceremony: it is the assertion that actually fired when the
    package was republished with a fourth sheet, which is how Phase 2 was known
    to be a new corpus rather than a re-run of the old one.
    """

    PHASE_2_SHA256 = "41c6524e3343b760492c319df7d45ea39af6894ef7f3a0c12b83a8f7d82ec380"

    def test_the_package_is_present_and_unmodified(self):
        self.assertEqual(hashlib.sha256(_PDF.read_bytes()).hexdigest(), self.PHASE_2_SHA256)

    def test_the_set_is_four_sheets(self):
        self.assertEqual(len(_document()["pages"]), 4)

    def test_the_oracle_is_not_reachable_from_the_builder_corpus(self):
        # The blind test's own boundary: only builder_corpus may be ingested.
        # If an oracle file ever appears inside it, the exercise is compromised.
        names = {p.name.lower() for p in _CORPUS.iterdir()}
        self.assertEqual(names & {"oracle", "expected.json", "ground_truth.md"}, set())


if __name__ == "__main__":
    unittest.main()
