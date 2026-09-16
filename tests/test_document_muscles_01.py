"""CLAUDE-MUSCLE-F1..F5-01 - five small muscles, each tested on its own.

A muscle does not graduate because an end-to-end demonstration happened to
work. It graduates when its own small test passes, so each class below tests
exactly one capability and the mixed-package probe at the end proves only that
they compose - never that any of them works.
"""
import unittest

from services import binding, sheet_identity, subject_tags, supersession_detect
from services.visual_examination import (
    PARTIALLY_RECOVERED, RECOVERED, UNRESOLVED,
)


class F1BindConfidenceSplit(unittest.TestCase):
    """Reading a value and attaching it are two claims, and the weaker governs.

    THE REGRESSION IS THE LIVE DEFECT. On the Castille survey `144.12` is
    printed immediately above LOT LINE 3 and was stored with a single
    `certainty: RECOVERED`. That was true of reading the digits and unproven of
    the attachment, which rests on the annotation being printed nearby.
    """

    def test_the_castille_annotation_is_read_clearly_and_bound_weakly(self):
        record = binding.bind(
            144.12, read_certainty=RECOVERED,
            bind_basis=binding.BIND_BASIS_PROXIMITY, bound_to="LOT LINE 3")

        self.assertEqual(record["read_certainty"], RECOVERED,
                         "the digits are legible and that must not be lost")
        self.assertEqual(record["bind_certainty"], PARTIALLY_RECOVERED)
        self.assertEqual(binding.bound_certainty(record), PARTIALLY_RECOVERED,
                         "the binding was promoted to the reading's certainty")

    def test_proximity_can_never_reach_recovered(self):
        """Even when the extractor insists. This is the ceiling."""
        record = binding.bind(
            144.12, read_certainty=RECOVERED,
            bind_basis=binding.BIND_BASIS_PROXIMITY,
            claimed_bind_certainty=RECOVERED)
        self.assertEqual(record["bind_certainty"], PARTIALLY_RECOVERED)

    def test_a_structural_binding_may_reach_recovered(self):
        """A schedule cell belongs to its row by construction, not inference."""
        record = binding.bind(
            "480V", read_certainty=RECOVERED,
            bind_basis=binding.BIND_BASIS_STRUCTURAL, bound_to="AHU-1")
        self.assertEqual(binding.bound_certainty(record), RECOVERED)

    def test_a_poor_reading_is_not_rescued_by_a_strong_binding(self):
        record = binding.bind(
            "14?.12", read_certainty=PARTIALLY_RECOVERED,
            bind_basis=binding.BIND_BASIS_STRUCTURAL)
        self.assertEqual(binding.bound_certainty(record), PARTIALLY_RECOVERED)

    def test_no_binding_at_all_is_unresolved(self):
        record = binding.bind("x", read_certainty=RECOVERED,
                              bind_basis=binding.BIND_BASIS_NONE)
        self.assertEqual(binding.bound_certainty(record), UNRESOLVED)
        self.assertFalse(binding.is_value_bearing(record))

    def test_the_weaker_helper_never_returns_better_than_either(self):
        self.assertEqual(binding.weaker(RECOVERED, UNRESOLVED), UNRESOLVED)
        self.assertEqual(binding.weaker(UNRESOLVED, RECOVERED), UNRESOLVED)
        self.assertEqual(binding.weaker(RECOVERED, RECOVERED), RECOVERED)

    def test_the_survey_extractor_now_carries_both(self):
        """The defect's own code path, not just the primitive."""
        from services import survey_graph

        graph = survey_graph.normalise_graph({
            "nodes": [{"id": "N1", "x": 0.2, "y": 0.3},
                      {"id": "N2", "x": 0.8, "y": 0.3}],
            "segments": [{"id": "S1", "from": "N1", "to": "N2",
                          "kind": "straight", "boundary": "lot_line",
                          "certainty": RECOVERED,
                          "dimension": {"text": "144.12", "value": 144.12,
                                        "certainty": RECOVERED}}]})
        dimension = graph["segments"][0]["dimension"]

        self.assertEqual(dimension["read_certainty"], RECOVERED)
        self.assertEqual(dimension["bind_certainty"], PARTIALLY_RECOVERED)
        self.assertEqual(dimension["bound_certainty"], PARTIALLY_RECOVERED)
        self.assertEqual(dimension["bind_basis"], binding.BIND_BASIS_PROXIMITY)


class F2SheetIdentityAndDiscipline(unittest.TestCase):
    """Which sheet this is, and whose discipline - or an honest absence."""

    def test_a_readable_sheet_number_yields_its_discipline(self):
        for token, expected in (("A-201", "architectural"),
                                ("S-101", "structural"),
                                ("M-501", "mechanical"),
                                ("E-401", "electrical"),
                                ("C-100", "civil")):
            self.assertEqual(sheet_identity.discipline_of(token), expected,
                             "%s misread" % token)

    def test_an_unknown_prefix_is_unresolved_not_guessed(self):
        for token in ("ZZ-9", "", None, "not a sheet"):
            self.assertEqual(sheet_identity.discipline_of(token),
                             sheet_identity.DISCIPLINE_UNRESOLVED)

    def test_an_unreadable_title_block_gives_unresolved_identity(self):
        identity = sheet_identity.sheet_identity_of({"name": "scan0001.pdf"})

        self.assertIsNone(identity["sheet_token"])
        self.assertEqual(identity["identity_certainty"], "UNRESOLVED")
        self.assertEqual(identity["discipline"],
                         sheet_identity.DISCIPLINE_UNRESOLVED)
        self.assertEqual(identity["basis"], "none")

    def test_a_recovered_token_identifies_the_sheet_more_weakly(self):
        identity = sheet_identity.sheet_identity_of({"name": "A-201 Plan.pdf"})
        if identity["sheet_token"] is None:
            self.skipTest("this Source shape carries no recovered token")
        self.assertEqual(identity["identity_certainty"], PARTIALLY_RECOVERED)
        self.assertEqual(identity["discipline"], "architectural")


class F3SubjectTagExtraction(unittest.TestCase):
    """The shared key that lets a clause and a schedule row meet."""

    def test_the_same_equipment_in_both_modalities_resolves_to_one_key(self):
        """The acceptance test as written: a spec sentence and a drawing
        schedule row, differently spelled, must land on one key."""
        shared = subject_tags.shared_subjects(
            "AHU-1 shall be provided with a variable frequency drive.",
            "MECHANICAL SCHEDULE | AHU 01 | ROOFTOP | 4000 CFM")

        self.assertEqual([s["key"] for s in shared], ["equipment:AHU-1"])

    def test_spelling_variants_normalise_together(self):
        keys = set()
        for text in ("AHU-1", "AHU 1", "ahu-01", "AHU.1"):
            keys |= {s["key"] for s in subject_tags.subjects_in(text)}
        self.assertEqual(keys, {"equipment:AHU-1"})

    def test_a_room_needs_a_room_word(self):
        self.assertEqual(
            [s["key"] for s in subject_tags.subjects_in("Room 203")],
            ["room:203"])
        self.assertEqual(subject_tags.subjects_in("203"), [],
                         "a bare number became a subject")

    def test_equipment_is_not_mistaken_for_a_sheet(self):
        """AHU-1 is sheet-SHAPED. A sheet matcher claims it happily and puts a
        sheet that does not exist into the evidence graph."""
        keys = [s["key"] for s in subject_tags.subjects_in("Provide AHU-1")]
        self.assertIn("equipment:AHU-1", keys)
        self.assertNotIn("sheet:AHU1", keys)

    def test_a_real_sheet_is_still_recognised(self):
        keys = [s["key"] for s in subject_tags.subjects_in("See sheet A-201")]
        self.assertIn("sheet:A201", keys)

    def test_a_detail_reference_resolves(self):
        keys = [s["key"] for s in subject_tags.subjects_in("per 3/A-401")]
        self.assertIn("detail:A401:3", keys)

    def test_the_verbatim_survives_normalisation(self):
        found = subject_tags.subjects_in("ahu-01 serves the space")
        self.assertEqual(found[0]["identifier"], "AHU-1")
        self.assertEqual(found[0]["verbatim"], "ahu-01")

    def test_no_subjects_in_ordinary_prose(self):
        self.assertEqual(
            subject_tags.subjects_in("The contractor shall coordinate work."),
            [])


class F4SupersessionDetection(unittest.TestCase):
    """Replacing a clause, told apart from merely referring to one."""

    def test_a_replacement_is_detected(self):
        found = supersession_detect.supersessions_in(
            "Delete Section 2.4 in its entirety and replace with the following.")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["clause"], "2.4")
        self.assertTrue(found[0]["supersedes"])

    def test_an_amendment_is_detected(self):
        found = supersession_detect.supersessions_in(
            "Section 11.4.2 is amended to read as follows.")
        self.assertEqual([f["clause"] for f in found], ["11.4.2"])

    def test_a_mention_is_not_a_supersession(self):
        """The failure that would price the wrong job, in reverse: claiming a
        clause was replaced when it still governs."""
        entries = supersession_detect.detect(
            "Refer to Section 2.4 for coordination requirements.")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["action"],
                         supersession_detect.ACTION_MENTIONS)
        self.assertFalse(entries[0]["supersedes"])
        self.assertEqual(supersession_detect.supersessions_in(
            "Refer to Section 2.4 for coordination requirements."), [])

    def test_a_supplement_does_not_supersede(self):
        """It changes the total requirement without replacing the earlier text,
        which must stay visible to a reader."""
        entries = supersession_detect.detect(
            "This clause supplements Section 2.4.")
        self.assertFalse(entries[0]["supersedes"])
        self.assertEqual(entries[0]["action"], supersession_detect.ACTION_ADDS)

    def test_the_proposal_writes_nothing_and_says_so(self):
        proposal = supersession_detect.proposal(
            "Delete Section 2.4 and replace with the following.",
            addendum_source_id="add-3")
        self.assertEqual(len(proposal["supersessions_proposed"]), 1)
        self.assertIn("ai_generated_proposal",
                      proposal["evidence_class_note"])

    def test_both_versions_are_preserved_by_construction(self):
        """The detector returns a proposal and holds no text, so it has no
        means of overwriting either clause."""
        proposal = supersession_detect.proposal(
            "Section 2.4 is deleted.", addendum_source_id="add-3")
        self.assertNotIn("replacement_text", proposal)
        self.assertNotIn("base_text", proposal)


class F5ExpectedButAbsent(unittest.TestCase):
    """Declared on the index, not delivered in the package."""

    def test_one_declared_sheet_absent_yields_one_finding(self):
        findings = sheet_identity.missing_sheet_findings({
            "source_id": "idx-1",
            "not_found": [{"sheet_token": "A203", "reference_text": "A-203"}]})

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["sheet_token"], "A203")
        self.assertEqual(findings[0]["discipline"], "architectural")
        self.assertIn("A203", findings[0]["statement"])

    def test_nothing_is_inferred_about_the_missing_sheet(self):
        finding = sheet_identity.missing_sheet_findings({
            "source_id": "idx-1",
            "not_found": [{"sheet_token": "A203"}]})[0]

        self.assertIsNone(finding["contents_claim"])
        for word in ("probably", "likely", "would have", "should contain",
                     "withheld", "incomplete"):
            self.assertNotIn(word, finding["statement"].lower(),
                             "the finding speculates about the absence")

    def test_an_empty_package_check_yields_nothing(self):
        self.assertEqual(sheet_identity.missing_sheet_findings({}), [])
        self.assertEqual(sheet_identity.missing_sheet_findings(
            {"not_found": []}), [])


class PromotedReasoningReachesAskGo(unittest.TestCase):
    """The four mature Spin behaviours, promoted as behaviour not as verbs."""

    def setUp(self):
        from services import conversational_turn

        self.contract = conversational_turn.CONVERSATIONAL_TURN_BEHAVIORAL_CONTRACT

    def test_the_four_behaviours_are_present(self):
        for phrase in ("Know when to stop",
                       "what was knowable when it was made",
                       "observable constraints",
                       "never means its own content became more authoritative"):
            self.assertIn(phrase, self.contract, "%r was not promoted" % phrase)

    def test_no_named_game_verbs_reach_the_user_experience(self):
        """GO-SPIN-GAMES-01.md: the catalogue is illustrative and must not be
        hard-coded. Several names are still recovery-pending."""
        for verb in ("Change Game", "Conflict Game", "Propagation Game",
                     "Authority Game", "Convergence Game", "games_played",
                     "Missing Evidence Game", "GOtex", "Cognitive Gym"):
            self.assertNotIn(verb, self.contract,
                             "%r leaked into the ordinary experience" % verb)


class MixedPackageProbe(unittest.TestCase):
    """ONE bounded probe: a clause, a sheet, an addendum, an issue list.

    This proves the five COMPOSE. It is not evidence that any of them works -
    each has its own test above, and this one would still pass if a muscle were
    subtly wrong, which is exactly why it is not allowed to stand in for them.
    """

    SPEC = "Section 2.4 AHU-1 shall serve Room 203 as shown on sheet M-501."
    ADDENDUM = ("Addendum 3: Delete Section 2.4 and replace with the "
                "following: AHU-1 shall serve Room 203 and Room 205.")
    SCHEDULE = "MECHANICAL EQUIPMENT SCHEDULE | AHU 01 | serves RM 203"
    INDEX = {"source_id": "idx-1",
             "not_found": [{"sheet_token": "A203", "reference_text": "A-203"}]}

    def test_situate_bind_compare_reason_govern(self):
        # SITUATE - what sheet, whose discipline.
        self.assertEqual(sheet_identity.discipline_of("M-501"), "mechanical")

        # BIND - the spec clause and the drawing schedule name one subject.
        shared = subject_tags.shared_subjects(self.SPEC, self.SCHEDULE)
        self.assertIn("equipment:AHU-1", [s["key"] for s in shared])

        # COMPARE - the addendum acts on a clause the spec states.
        superseded = supersession_detect.supersessions_in(self.ADDENDUM)
        self.assertEqual([s["clause"] for s in superseded], ["2.4"])

        # REASON - a declared sheet is absent from the package.
        missing = sheet_identity.missing_sheet_findings(self.INDEX)
        self.assertEqual(len(missing), 1)

        # GOVERN - a value attached by proximity stays qualified.
        value = binding.bind(4000, read_certainty=RECOVERED,
                             bind_basis=binding.BIND_BASIS_PROXIMITY,
                             bound_to="AHU-1")
        self.assertEqual(binding.bound_certainty(value), PARTIALLY_RECOVERED)

    def test_the_finding_can_be_reconstructed(self):
        """Source identity, subject binding, supersession state and uncertainty
        must all be recoverable from what the muscles returned."""
        finding = {
            "sheet": sheet_identity.sheet_token("M-501"),
            "discipline": sheet_identity.discipline_of("M-501"),
            "subject": subject_tags.shared_subjects(
                self.SPEC, self.SCHEDULE)[0]["key"],
            "supersession": supersession_detect.supersessions_in(
                self.ADDENDUM)[0],
            "missing_sources": sheet_identity.missing_sheet_findings(
                self.INDEX),
            "value": binding.bind(4000, read_certainty=RECOVERED,
                                  bind_basis=binding.BIND_BASIS_PROXIMITY),
        }

        self.assertEqual(finding["sheet"], "M501")
        self.assertEqual(finding["discipline"], "mechanical")
        self.assertEqual(finding["subject"], "equipment:AHU-1")
        self.assertTrue(finding["supersession"]["supersedes"])
        self.assertEqual(finding["missing_sources"][0]["sheet_token"], "A203")
        self.assertEqual(binding.bound_certainty(finding["value"]),
                         PARTIALLY_RECOVERED)

    def test_the_addendum_does_not_erase_the_base_clause(self):
        proposal = supersession_detect.proposal(
            self.ADDENDUM, addendum_source_id="add-3", base_source_id="spec-1")
        self.assertEqual(proposal["base_source_id"], "spec-1")
        self.assertEqual(proposal["addendum_source_id"], "add-3")
        # Both ends are named; neither text is held or rewritten here.
        self.assertNotIn("base_text", proposal)


if __name__ == "__main__":
    unittest.main()
