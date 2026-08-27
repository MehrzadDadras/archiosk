"""
CLAUDE-DRAWING-REFS-02 - the blind audit that found a defect in the instrument,
kept as the regression that stops it coming back.

WHAT HAPPENED

A three-sheet vector drawing set, a door schedule and a specification excerpt
were supplied as a blind coordination exercise, with ground truth held in a
sibling `oracle/` directory that was declared non-ingestible. It was not read,
before or after. Every expectation below comes from the pipeline's own verified
output, independently confirmed correct by the Product Owner against that oracle
- so this file needs no answer key to defend the behaviour.

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

Keyword-led readings are untouched: a sheet id still resolves normally when it is
actually cited, as "Sheet A-101" or inside "3/A-501".
"""
from __future__ import annotations

import csv
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from engine.pdf_extractor import PDFVectorExtractor
from services.case_workspace import (
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
_SHEETS = {1: "A-101", 2: "S-101", 3: "A-501"}
_GRID_X = [120.0, 280.0, 440.0]      # gridlines A, B, C
_GRID_Y = [180.0, 380.0, 580.0]      # gridlines 1, 2, 3


def _document():
    return PDFVectorExtractor().extract_document(str(_PDF))


def _schedule_marks():
    with open(_CORPUS / "Door_Schedule.csv", encoding="utf-8") as handle:
        return [row["Mark"].strip() for row in csv.DictReader(handle)]


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

    def test_suppression_did_not_swallow_the_real_tags(self):
        # The failure mode on the other side: a precedence rule so eager that it
        # silences genuine door tags. Four are defined by the schedule.
        resolved = sorted(r["reference_text"] for r in
                          self._of_type(REFERENCE_TYPE_SCHEDULE_MARK, RESOLUTION_STATUS_RESOLVED_EXACT))
        self.assertEqual(resolved, ["D-101", "D-102", "D-103", "D-104"])


class TheCoordinationFindingsAreStable(_Registered):
    def test_a_callout_to_a_sheet_that_does_not_exist_is_not_found(self):
        # "3/A-502" - A-502 is not in the set. This is a finding, not an error.
        broken = [r["reference_text"] for r in
                  self._of_type(REFERENCE_TYPE_DETAIL_CALLOUT, RESOLUTION_STATUS_TARGET_NOT_FOUND)]
        self.assertEqual(broken, ["3/A-502"])

    def test_a_callout_to_a_real_detail_resolves(self):
        good = self._of_type(REFERENCE_TYPE_DETAIL_CALLOUT, RESOLUTION_STATUS_RESOLVED_EXACT)
        self.assertEqual([r["reference_text"] for r in good], ["3/A-501"])
        self.assertEqual(good[0]["resolved_target_ids"], ["A-501 Detail 3"])

    def test_an_unreferenced_schedule_row_is_found_by_query(self):
        # D-105, the janitor closet: scheduled, never tagged, and its room does
        # not appear on the plan at all. A property of the schedule, answered by
        # looking at it - deliberately not a resolution status.
        cited = {t for r in self._of_type(REFERENCE_TYPE_SCHEDULE_MARK)
                 for t in r["resolved_target_ids"]}
        self.assertEqual(sorted(set(_schedule_marks()) - cited), ["D-105"])

    def test_the_reference_count_does_not_drift(self):
        self.assertEqual(len(self.refs), 7)


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

        with open(_CORPUS / "Door_Schedule.csv", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        at_risk = [r["Mark"] for r in rows
                   if any(k in r["Location"].lower() for k in keywords)
                   and r["Fire_Rating"].strip().upper() != "NON-RATED"
                   and not re.search(r"self-clos|closer", r["Notes"], re.I)]
        self.assertEqual(at_risk, ["D-105"])


class TheCorpusIsIntact(unittest.TestCase):
    """A fixture that silently changes turns every assertion above into a lie."""

    def test_the_package_is_present_and_unmodified(self):
        import hashlib

        digest = hashlib.sha256(_PDF.read_bytes()).hexdigest()
        self.assertEqual(
            digest, "ff2041c3029f27ac394547087e526de912473995fb1b94e4cb0b15c305913121")

    def test_the_oracle_is_not_reachable_from_the_builder_corpus(self):
        # The blind test's own boundary: only builder_corpus may be ingested.
        # If an oracle file ever appears inside it, the exercise is compromised.
        names = {p.name.lower() for p in _CORPUS.iterdir()}
        self.assertEqual(names & {"oracle", "expected.json", "ground_truth.md"}, set())


if __name__ == "__main__":
    unittest.main()
