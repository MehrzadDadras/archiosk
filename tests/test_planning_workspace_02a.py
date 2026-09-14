"""CLAUDE-PLANNING-WORKSPACE-02A - a workspace that cannot launder its inputs.

    GOVERNED RESULT  |  WHAT A PERSON ADDED  |  FOLLOW-UP  |  ADMISSION

The risk this tranche introduces is specific and worth naming: until now a person
could not type into the planning result at all, so nothing they wrote could be
mistaken for a municipal record. Adding a textarea beside authority is exactly
where that mistake becomes easy - and an export makes it permanent, because a
.docx has no badges, no colour and no hover text, and arrives on someone's desk
months later with none of the page's context.

So these tests care most about two things: that the four layers stay
distinguishable everywhere including in a file, and that a human claim goes
through the SAME binding discipline a model claim does.
"""
from __future__ import annotations

import copy
import io
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from services import entity_binding
from services import go_pdz_contract as contract
from services import planning_contribution as contribution
from services import planning_export
from services import planning_posture as posture
from services import planning_result_view as view_module
from services import planning_visual

RESULT_HTML = Path("templates/planning_zoning_result.html")
MAIN_CSS = Path("static/css/main.css")

#: 573 Shuter's own family of figures - the components sum PAST the cap, so the
#: sum and the cap are different numbers with different meanings.
ZONING_FACTS = {"attributes": {"ZN_ZONE": "CR", "FSI_TOTAL": 2.0,
                               "FSI_COMMERCIAL_USE": 1.0,
                               "FSI_RESIDENTIAL_USE": 1.5, "ZN_EXCPTN": "N"}}
EVIDENCE_FACTS = {"zoning": ZONING_FACTS}

PARCEL = {"type": "Polygon",
          "coordinates": [[[0.0, 0.0], [20.0, 0.0], [20.0, 15.0], [0.0, 15.0],
                           [0.0, 0.0]]]}
ZONE = {"type": "Polygon",
        "coordinates": [[[-40.0, -30.0], [60.0, -30.0], [60.0, 50.0],
                         [-40.0, 50.0], [-40.0, -30.0]]]}
RETRIEVAL = {
    "retrieved_at": "2026-09-13T12:00:00Z",
    "runner_version": "toronto-gate01@3",
    "zoning_attributes": ZONING_FACTS["attributes"],
    "visual_geometry": {
        "parcel": {"geometry": PARCEL, "source": "cot_geospatial27/36",
                   "layer": "Property Boundary",
                   "parcel_identifier": "TOR-PARCEL-TEST",
                   "geometry_id": "sha256:parcel",
                   # CLAUDE-PLANNING-SPATIAL-SEMANTICS-01 section 2: the CRS is
                   # now EVIDENCE carried on the retrieval, not a constant the
                   # renderer asserts.
                   "spatial_reference": "EPSG:3857"},
        "zoning": {"geometry": ZONE, "source": "cot_geospatial11/3",
                   "layer": "Zoning Area", "geometry_id": "sha256:zone",
                   "feature_identifier": "77"},
    },
}


def _document():
    return {"contract": contract.CONTRACT_ID,
            "schema_version": contract.SCHEMA_VERSION,
            "gate": contract.GATE_01, "next_authorized_gate": contract.GATE_02,
            "subject": {"subject_id": "S1", "address_as_given": "573 Shuter Street",
                        "normalized_address": "573 Shuter St",
                        "municipality": "City of Toronto",
                        "parcel_identifier": "TOR-PARCEL-TEST",
                        "identity_confidence": "HIGH"},
            "authorities": [{"authority_id": "TOR-BYLAW-569-2013",
                             "name": "City of Toronto Zoning By-law 569-2013",
                             "authority_status": "IN_FORCE",
                             "effective_date": "2013-05-09",
                             "retrieved_at": "2026-09-13T12:00:00Z"}],
            "statements": [{"statement_id": "S-ZONE", "kind": "AUTHORITY_SAYS",
                            "topic": "ZONING_DESIGNATION",
                            "text": "The parcel lies within the CR zone.",
                            "authority_refs": ["TOR-BYLAW-569-2013"],
                            "statement_status": "ESTABLISHED",
                            "confidence": "HIGH"}],
            "site_specific_exceptions": [],
            "unresolved": [{"issue_id": "U-OFFICIAL-PLAN-DESIGNATION",
                            "question": "Which designation applies?",
                            "materiality": "MATERIAL",
                            "required_evidence": "The Plan's map schedules."}],
            "result_status": "UNRESOLVED"}


def _view(**overrides):
    result = {"document": _document(), "data_class": view_module.DATA_CLASS_LIVE,
              "retrieval": RETRIEVAL, "options": [], "conclusion": None}
    result.update(overrides)
    return view_module.build_view(result)


def _contribution(text, classification=None, **kwargs):
    return contribution.contribution(text, classification=classification,
                                     supplied_by="architect",
                                     submitted_at="2026-09-13T12:05:00Z", **kwargs)


# ============================================================================
# A, B, C - RESPONSIVE
# ============================================================================

class TheResultUsesTheWidthItHas(unittest.TestCase):
    """A, B, C. Asserted against the STYLESHEET and the MARKUP, never prose."""

    def setUp(self):
        self.css = MAIN_CSS.read_text(encoding="utf-8")
        self.html = RESULT_HTML.read_text(encoding="utf-8")

    def test_a_the_result_no_longer_borrows_the_480px_form_container(self):
        """THE REPORTED DEFECT, pinned at its cause.

        `.np-group` is `max-width: 480px` because it was built for New Project's
        form fields. Every result section used it, which is why the page text
        expanded while the cards did not.
        """
        markup = re.sub(r"\{#.*?#\}", "", self.html, flags=re.S)
        self.assertNotIn("np-group", markup,
                         "the result page must not use the form container")
        self.assertIn('class="pz-group"', markup)

    def test_a_the_form_container_is_untouched_for_the_forms_that_need_it(self):
        """Carry-through in the other direction: do not fix one page by
        restyling two others. `upload.html` and `document_shop_intake.html` are
        forms where 480px is correct."""
        self.assertRegex(self.css, r"\.np-group\s*\{[^}]*max-width:\s*480px")
        for template in ("templates/upload.html",
                         "templates/document_shop_intake.html"):
            self.assertIn("np-group",
                          Path(template).read_text(encoding="utf-8"), template)

    def test_a_the_result_container_has_no_fixed_narrow_width(self):
        block = re.search(r"\.pz-group\s*\{([^}]*)\}", self.css)
        self.assertIsNotNone(block)
        self.assertNotIn("480px", block.group(1))
        self.assertIn("width: 100%", block.group(1))

    def test_a_desktop_gives_the_main_column_the_larger_share(self):
        block = re.search(r"\.pz-workspace\s*\{([^}]*)\}", self.css)
        self.assertIsNotNone(block)
        columns = re.search(r"grid-template-columns:\s*([^;]+);", block.group(1))
        self.assertIsNotNone(columns)
        fractions = re.findall(r"([\d.]+)fr", columns.group(1))
        self.assertEqual(len(fractions), 2)
        self.assertGreater(float(fractions[0]), float(fractions[1]),
                           "the governed result must get the wider track")

    def test_a_option_and_panel_grids_expand_into_available_width(self):
        for selector in (r"\.pz-options", r"\.pz-panels"):
            block = re.search(selector + r"\s*\{([^}]*)\}", self.css)
            self.assertIsNotNone(block, selector)
            self.assertIn("auto-fit", block.group(1))

    def test_b_the_layout_collapses_to_one_column_before_it_is_cramped(self):
        self.assertRegex(
            self.css,
            r"@media \(max-width: 1100px\)\s*\{[^@]*\.pz-workspace\s*\{[^}]*"
            r"grid-template-columns:\s*minmax\(0,\s*1fr\)")

    def test_b_mobile_stacks_and_keeps_actions_reachable(self):
        mobile = self.css[self.css.rindex("@media (max-width: 640px)"):]
        self.assertIn(".pz-export-actions", mobile)
        self.assertIn("flex-direction: column", mobile)

    def test_c_nothing_can_force_the_grid_wider_than_the_viewport(self):
        """The usual cause of a horizontal scrollbar on correct-looking CSS: a
        long unbroken token in a grid track with no `min-width: 0`."""
        workspace = re.search(r"\.pz-workspace\s*\{([^}]*)\}", self.css).group(1)
        self.assertIn("minmax(0", workspace)
        columns = re.search(r"\.pz-main,\s*\.pz-aside\s*\{([^}]*)\}", self.css)
        self.assertIsNotNone(columns)
        self.assertIn("min-width: 0", columns.group(1))

    def test_c_statement_text_wraps_rather_than_overflowing(self):
        block = re.search(r"\.pz-statement\s*\{([^}]*)\}", self.css)
        self.assertIn("overflow-wrap: break-word", block.group(1))

    def test_c_the_svg_panel_cannot_exceed_its_column(self):
        block = re.search(r"\.pz-panel-svg\s*\{([^}]*)\}", self.css)
        self.assertIn("max-width: 100%", block.group(1))

    def test_the_new_rules_use_tokens_rather_than_raw_values(self):
        """main.css's own header rule: reference tokens, never duplicate them."""
        start = self.css.index("CLAUDE-PLANNING-WORKSPACE-02A")
        block = self.css[start:]
        # Colours must all be tokens. Raw hex in this block would be a second
        # definition of something tokens.css already names.
        self.assertEqual([], re.findall(r"#[0-9A-Fa-f]{3,6}\b", block))


# ============================================================================
# D, E, F, G, H - EXPORT
# ============================================================================

class TheExportCarriesWhatTheScreenCarried(unittest.TestCase):
    """D, E, F, G, H."""

    def test_d_word_export_produces_a_real_docx(self):
        stream, filename, mimetype = planning_export.export(
            _view(), "docx", generated_at="2026-09-13T12:00:00Z")
        data = stream.getvalue()
        self.assertEqual(data[:2], b"PK", "a .docx is a zip archive")
        self.assertGreater(len(data), 2000)
        self.assertTrue(filename.endswith(".docx"))
        self.assertIn("wordprocessingml", mimetype)

    def test_e_pdf_export_produces_a_real_pdf(self):
        stream, filename, mimetype = planning_export.export(
            _view(), "pdf", generated_at="2026-09-13T12:00:00Z")
        data = stream.getvalue()
        self.assertEqual(data[:5], b"%PDF-")
        self.assertGreater(len(data), 1000)
        self.assertTrue(filename.endswith(".pdf"))
        self.assertEqual(mimetype, "application/pdf")

    def test_f_every_governed_section_reaches_the_export(self):
        document = planning_export.build_export_document(_view())
        titles = " | ".join(table.title for table in document.tables)
        for fragment in ("Property Identity", "Governing Planning Framework",
                         "Permitted Development Context", "Development Envelope",
                         "Mobility / Access Context",
                         "Constraints & Opportunities",
                         "Unresolved / Municipal Confirmation",
                         "Evidence / Sources"):
            self.assertIn(fragment, titles, fragment)

    def test_f_both_formats_are_built_from_one_projection(self):
        """`document_export`'s own property: two formats, never two answers."""
        view = _view()
        first = planning_export.build_export_document(view)
        second = planning_export.build_export_document(view)
        self.assertEqual([t.title for t in first.tables],
                         [t.title for t in second.tables])
        self.assertEqual([t.rows for t in first.tables],
                         [t.rows for t in second.tables])

    def test_g_the_result_status_and_unresolved_items_survive(self):
        document = planning_export.build_export_document(_view())
        self.assertIn("Result status: UNRESOLVED", "\n".join(document.preamble))
        unresolved = [t for t in document.tables if "Unresolved" in t.title][0]
        self.assertTrue(unresolved.rows)
        self.assertIn("U-OFFICIAL-PLAN-DESIGNATION",
                      " ".join(unresolved.rows[0]))
        self.assertIn("MATERIAL", " ".join(unresolved.rows[0]))

    def test_g_the_export_never_reads_as_an_approval(self):
        preamble = "\n".join(planning_export.build_export_document(_view()).preamble)
        self.assertIn("NOT A MUNICIPAL APPROVAL", preamble)
        self.assertIn("STRUCTURE VALID is not SEMANTICALLY VALID", preamble)

    def test_g_a_fixture_exports_as_a_fixture(self):
        """The worst artifact this tranche could produce is a preview that
        exports as though it were analysis."""
        preview = _view(data_class=view_module.DATA_CLASS_DEVELOPMENT)
        preamble = "\n".join(
            planning_export.build_export_document(preview).preamble)
        self.assertIn("DEVELOPMENT FIXTURE", preamble)
        self.assertIn("NOT an analysis of any real property", preamble)

    def test_h_official_visual_provenance_travels_with_the_export(self):
        panels = planning_visual.panels_for(RETRIEVAL)
        document = planning_export.build_export_document(_view(), panels=panels)
        visual = [t for t in document.tables if "visual evidence" in t.title][0]
        self.assertEqual(len(visual.rows), 2)
        joined = " ".join(" ".join(row) for row in visual.rows)
        self.assertIn("Property Boundary", joined)
        self.assertIn("2026-09-13T12:00:00Z", joined)
        self.assertIn("Zoning Area", joined)
        # And it says the imagery itself is not in the file, rather than
        # implying it is.
        self.assertIn("provenance rather than the", visual.note)

    def test_the_contract_note_does_not_claim_go_pdz_is_ratified(self):
        """Section 24. The gap stays open, including in a file that leaves."""
        preamble = "\n".join(planning_export.build_export_document(_view()).preamble)
        self.assertIn("not a separately ratified governance standard", preamble)
        self.assertNotIn("ratified standard", preamble.replace(
            "not a separately ratified governance standard", ""))

    def test_an_unsupported_format_or_scope_is_refused_not_defaulted(self):
        for bad in ("xlsx", "html", "", None):
            with self.subTest(export_format=bad):
                with self.assertRaises(ValueError):
                    planning_export.export(_view(), bad)
        with self.assertRaises(ValueError):
            planning_export.export(_view(), "pdf", scope="EVERYTHING")

    def test_the_filename_carries_no_path_characters(self):
        name = planning_export.filename_for(
            {"address": "../../etc/passwd 573 Shuter"}, "pdf")
        self.assertNotIn("/", name)
        self.assertNotIn("..", name)
        self.assertNotIn("\\", name)
        self.assertTrue(name.endswith(".pdf"))


class TheFourLayersSurviveTheExport(unittest.TestCase):
    """Section 8, and the place flattening would be easiest."""

    def _layered(self, text="Maximum FSI is 2.5."):
        record = _contribution(text, contribution.CLASS_USER_OBSERVATION,
                               object_name="municipal email")
        review = contribution.review(record, _document(), EVIDENCE_FACTS)
        return contribution.layered(_document(), _view(), [record], [review])

    def test_the_scopes_are_two_and_the_default_is_governed_only(self):
        document = planning_export.build_export_document(_view())
        titles = " ".join(t.title for t in document.tables)
        self.assertNotIn("supplied by a person", titles)

    def test_follow_up_scope_keeps_the_layers_separately_titled(self):
        document = planning_export.build_export_document(
            _view(), scope=planning_export.SCOPE_WITH_FOLLOW_UP,
            layered=self._layered())
        titles = [t.title for t in document.tables]
        joined = " | ".join(titles)
        self.assertIn("Information supplied by a person", joined)
        self.assertIn("NOT HOST-OWNED", joined)
        self.assertIn("Deterministic follow-up review", joined)
        self.assertIn("Admission decision", joined)
        # And they are DISTINCT tables, not one merged block.
        self.assertEqual(len({t for t in titles}), len(titles))

    def test_the_preamble_warns_that_the_document_is_layered(self):
        document = planning_export.build_export_document(
            _view(), scope=planning_export.SCOPE_WITH_FOLLOW_UP,
            layered=self._layered())
        preamble = "\n".join(document.preamble)
        self.assertIn("FOUR DISTINCT LAYERS", preamble)
        self.assertIn("Only sections 1-10 are host-owned", preamble)

    def test_a_user_supplied_object_is_labelled_in_the_file(self):
        document = planning_export.build_export_document(
            _view(), scope=planning_export.SCOPE_WITH_FOLLOW_UP,
            layered=self._layered())
        block = [t for t in document.tables
                 if "supplied by a person" in t.title][0]
        self.assertIn("USER-SUPPLIED", " ".join(block.rows[0]))
        self.assertIn("not a municipal record", block.note)

    def test_the_admission_block_states_what_stays_host_owned(self):
        document = planning_export.build_export_document(
            _view(), scope=planning_export.SCOPE_WITH_FOLLOW_UP,
            layered=self._layered())
        block = [t for t in document.tables if t.title.endswith("Admission decision")][0]
        joined = " ".join(" ".join(row) for row in block.rows)
        for retained in ("PARCEL_IDENTITY", "STATUTORY_EFFECT",
                         "DETERMINISTIC_FINDINGS", "CLAIM_STRENGTH"):
            self.assertIn(retained, joined)
        self.assertIn("not admitted at a lower confidence", block.note)


# ============================================================================
# I, J, K, L - HUMAN INPUT
# ============================================================================

class HumanInputIsVisiblyClassified(unittest.TestCase):
    """I, J, K, L."""

    def test_i_typed_input_carries_a_visible_classification(self):
        record = _contribution("Owner wants six units.",
                               contribution.CLASS_OWNER_INTENT)
        self.assertEqual(record["classification"], contribution.CLASS_OWNER_INTENT)
        self.assertEqual(record["classification_label"], "Owner intent")
        self.assertFalse(record["is_host_owned"])

    def test_i_the_default_is_the_weakest_value(self):
        self.assertEqual(_contribution("Something.")["classification"],
                         contribution.CLASS_USER_INPUT)

    def test_j_a_host_class_can_never_be_requested(self):
        """Section 11's prohibition, against every host class in turn."""
        for attempted in contribution.HOST_ONLY_CLASSES:
            with self.subTest(attempted=attempted):
                record = _contribution("The by-law requires 2.0.", attempted)
                self.assertEqual(record["classification"],
                                 contribution.CLASS_USER_INPUT)
                self.assertNotIn(record["classification"],
                                 contribution.HOST_ONLY_CLASSES)

    def test_j_every_permitted_subtype_is_accepted_and_labelled(self):
        for value in contribution.CLASSIFICATIONS:
            with self.subTest(classification=value):
                record = _contribution("text", value)
                self.assertEqual(record["classification"], value)
                self.assertTrue(record["classification_label"])

    def test_k_a_supplied_object_retains_its_provenance(self):
        record = _contribution(
            "Here is a municipal email.",
            contribution.CLASS_USER_SUPPLIED_EVIDENCE,
            object_name="reply-from-planner.pdf", object_kind="email",
            object_bytes=b"from: planning@toronto.ca")
        supplied = record["supplied_object"]
        self.assertEqual(supplied["name"], "reply-from-planner.pdf")
        self.assertEqual(supplied["kind"], "email")
        self.assertEqual(supplied["byte_count"], 25)
        self.assertTrue(supplied["sha256"])
        self.assertEqual(supplied["label"], "USER-SUPPLIED")
        self.assertEqual(supplied["provenance"],
                         contribution.PROVENANCE_SUPPLIED_BY_USER)
        self.assertEqual(supplied["authority_status"],
                         contribution.AUTHORITY_STATUS_UNVERIFIED)

    def test_k_supplying_an_object_is_not_supplying_an_authority(self):
        record = _contribution("Municipal email attached.",
                               contribution.CLASS_USER_SUPPLIED_EVIDENCE,
                               object_name="email.pdf")
        self.assertEqual(record["authority_status"],
                         contribution.AUTHORITY_STATUS_UNVERIFIED)
        self.assertEqual(record["provenance"],
                         contribution.PROVENANCE_SUPPLIED_BY_USER)

    def test_k_a_user_visual_is_labelled_and_carries_no_pixels(self):
        panel = planning_visual.user_supplied_panel(
            name="sketch.png", kind="image/png", byte_count=1024,
            digest="sha256:abc")
        self.assertEqual(panel["label"], "USER-SUPPLIED")
        self.assertFalse(panel["is_official"])
        self.assertTrue(panel["is_user_supplied"])
        self.assertIsNone(panel["svg"])
        self.assertIn("screenshot is not an authority", panel["limitation"])

    def test_l_a_user_assertion_cannot_mutate_a_host_fact(self):
        facts = copy.deepcopy(EVIDENCE_FACTS)
        document = _document()
        before_facts = copy.deepcopy(facts)
        before_document = copy.deepcopy(document)
        record = _contribution("The total FSI is actually 9.0.",
                               contribution.CLASS_PROFESSIONAL_JUDGMENT)
        contribution.review(record, document, facts)
        self.assertEqual(facts, before_facts)
        self.assertEqual(document, before_document)
        self.assertEqual(facts["zoning"]["attributes"]["FSI_TOTAL"], 2.0)

    def test_l_the_admission_layer_names_what_the_host_keeps(self):
        layers = contribution.layered(_document(), _view(), [], [])
        for retained in ("PARCEL_IDENTITY", "AUTHORITY_CURRENTNESS",
                         "STATUTORY_EFFECT", "DETERMINISTIC_FINDINGS",
                         "EXCEPTION_STATE", "CLAIM_STRENGTH",
                         "GOVERNED_RELEASE"):
            self.assertIn(retained, layers["admission"]["host_retains"])


# ============================================================================
# M, N, O, P - ENTITY BINDING FOR HUMAN CONTRIBUTIONS
# ============================================================================

class HumanFactsBindBeforeAdmission(unittest.TestCase):
    """M, N, O, P - through the SAME layer committed at 64ddd93."""

    def _review(self, text, classification=None):
        return contribution.review(_contribution(text, classification),
                                   _document(), EVIDENCE_FACTS)

    def test_no_parallel_binding_engine_was_built(self):
        """Section 28. The binder is imported, not reimplemented."""
        source = Path("services/planning_contribution.py").read_text(
            encoding="utf-8")
        self.assertIn("from services import entity_binding", source)
        self.assertIn("entity_binding.bind_statement", source)
        for reinvention in ("def bind_statement", "ROLE_TOTAL_FSI_CAP =",
                            "def host_roles", "FAILURE_ROLE_MISMATCH ="):
            self.assertNotIn(reinvention, source, reinvention)

    def test_m_a_correct_value_in_the_correct_role_is_admitted(self):
        review = self._review("The total FSI of 2.0 is the cap here.")
        self.assertEqual(review["binding_failures"], [])
        self.assertEqual(review["admission"], contribution.ADMISSION_ADMITTED)
        self.assertEqual(review["contradictions"], [])

    def test_n_the_directives_worked_case_is_quarantined(self):
        """Section 13's example, verbatim: 2.5 is the computed sum, not the cap."""
        review = self._review("Maximum FSI is 2.5.")
        self.assertEqual(review["admission"], contribution.ADMISSION_QUARANTINED)
        self.assertEqual([f["failure"] for f in review["binding_failures"]],
                         [entity_binding.FAILURE_ROLE_MISMATCH])
        contradiction = review["contradictions"][0]
        self.assertEqual(contradiction["kind"], "ROLE_CONTRADICTION")
        self.assertEqual(contradiction["host_role"],
                         entity_binding.ROLE_COMPUTED_COMPONENT_SUM)
        self.assertEqual(contradiction["asserted_role"],
                         entity_binding.ROLE_TOTAL_FSI_CAP)

    def test_n_the_quarantine_is_not_a_confidence_reduction(self):
        """Section 7 of 64ddd93's direction, restated for human input: there is
        no confidence field to lower and deliberately no mechanism to add one."""
        review = self._review("Maximum FSI is 2.5.")
        self.assertNotIn("confidence", review)
        source = Path("services/planning_contribution.py").read_text(
            encoding="utf-8")
        self.assertNotIn("confidence=", source)

    def test_o_a_novel_number_is_quarantined(self):
        review = self._review("The total FSI is 4.0.")
        self.assertEqual(review["admission"], contribution.ADMISSION_QUARANTINED)
        self.assertEqual([f["failure"] for f in review["binding_failures"]],
                         [entity_binding.FAILURE_UNBOUNDED_NUMERIC])
        self.assertEqual(review["contradictions"][0]["kind"],
                         "UNSUPPORTED_FIGURE")

    def test_p_an_unknown_exception_reference_is_quarantined(self):
        document = _document()
        document["site_specific_exceptions"] = [
            {"exception_id": "TOR-EXCEPTION-2382", "indicated_by": "ZN_EXCPTN=Y",
             "text_retrieved": True}]
        review = contribution.review(
            _contribution("Exception TOR-EXCEPTION-9999 removes the setback."),
            document, EVIDENCE_FACTS)
        self.assertEqual(review["admission"], contribution.ADMISSION_QUARANTINED)
        self.assertEqual([f["failure"] for f in review["binding_failures"]],
                         [entity_binding.FAILURE_UNBOUND_EXCEPTION])

    def test_p_a_declared_exception_reference_binds(self):
        document = _document()
        document["site_specific_exceptions"] = [
            {"exception_id": "TOR-EXCEPTION-2382", "indicated_by": "ZN_EXCPTN=Y",
             "text_retrieved": True}]
        review = contribution.review(
            _contribution("Exception TOR-EXCEPTION-2382 applies."),
            document, EVIDENCE_FACTS)
        self.assertEqual(review["binding_failures"], [])

    def test_a_question_asserts_nothing_and_admits_nothing(self):
        review = self._review("What is the frontage?",
                              contribution.CLASS_USER_QUESTION)
        self.assertEqual(review["admission"],
                         contribution.ADMISSION_NOT_APPLICABLE)

    def test_a_question_containing_a_wrong_figure_is_still_checked(self):
        """A question mark is not a way past the binder."""
        review = self._review("Is the maximum FSI 2.5?",
                              contribution.CLASS_USER_QUESTION)
        self.assertEqual(review["admission"], contribution.ADMISSION_QUARANTINED)

    def test_every_contradiction_names_the_confirmation_it_needs(self):
        review = self._review("Maximum FSI is 2.5.")
        self.assertTrue(review["needs_confirmation"])
        self.assertTrue(any("2.5" in item
                            for item in review["needs_confirmation"]))


# ============================================================================
# Q, R - STATUTORY EFFECT ON USER MATERIAL
# ============================================================================

class SilenceFromAPersonIsStillSilence(unittest.TestCase):
    """Q, R - reusing the committed vocabulary, not a parallel enum."""

    def test_no_parallel_statutory_effect_enum_was_created(self):
        source = Path("services/planning_contribution.py").read_text(
            encoding="utf-8")
        self.assertIn("go_pdz_contract", source)
        for reinvention in ("EFFECT_EXPLICIT_PERMISSION =",
                            "STATUTORY_EFFECTS =", "EFFECT_ADMISSIBLE_BASES ="):
            self.assertNotIn(reinvention, source, reinvention)

    def test_q_a_person_reasoning_from_silence_to_permission_is_refused(self):
        effect = contribution.declared_statutory_effect(
            "The by-law says nothing about parking, so it is permitted.")
        self.assertEqual(effect["statutory_effect"], contract.EFFECT_UNRESOLVED)
        self.assertEqual(effect["effect_basis"], contract.BASIS_UNRESOLVED)
        self.assertEqual(effect["asserted_effect"],
                         contract.EFFECT_EXPLICIT_PERMISSION)
        self.assertTrue(effect["overreach"])

    def test_q_that_contribution_is_quarantined(self):
        review = contribution.review(
            _contribution("No express provision applies, so it is permitted."),
            _document(), EVIDENCE_FACTS)
        self.assertEqual(review["admission"], contribution.ADMISSION_QUARANTINED)
        self.assertTrue(review["effect_overreach"])
        self.assertEqual([c["kind"] for c in review["contradictions"]],
                         ["EFFECT_OVERREACH"])

    def test_q_a_permission_asserted_without_any_basis_is_refused(self):
        effect = contribution.declared_statutory_effect(
            "A six-storey building is permitted here.")
        self.assertEqual(effect["statutory_effect"], contract.EFFECT_UNRESOLVED)
        self.assertTrue(effect["overreach"])

    def test_q_a_contribution_may_never_be_granted_explicit_permission(self):
        """Only an instrument can supply a governing basis, and an instrument
        does not arrive through a textarea."""
        for text in ("It is permitted.", "This is as-of-right.",
                     "No parking requirement applies, so parking is permitted.",
                     "There is no limit, so it is allowed."):
            with self.subTest(text=text):
                effect = contribution.declared_statutory_effect(text)
                self.assertNotEqual(effect["statutory_effect"],
                                    contract.EFFECT_EXPLICIT_PERMISSION)

    def test_r_reporting_an_absence_is_recorded_as_an_absence(self):
        effect = contribution.declared_statutory_effect(
            "The by-law says nothing about bicycle parking.")
        self.assertEqual(effect["statutory_effect"],
                         contract.EFFECT_NO_EXPRESS_PROVISION)
        self.assertFalse(effect["overreach"])

    def test_r_a_removed_requirement_stays_distinct_from_a_prohibition(self):
        """The vocabulary keeps them apart and the basis table keeps them
        honest - both from 64ddd93, neither redefined here."""
        self.assertNotEqual(contract.EFFECT_REQUIREMENT_REMOVED,
                            contract.EFFECT_EXPLICIT_PROHIBITION)
        self.assertFalse(contract.basis_supports_effect(
            contract.EFFECT_REQUIREMENT_REMOVED, contract.BASIS_UNRESOLVED))
        self.assertFalse(contract.basis_supports_effect(
            contract.EFFECT_EXPLICIT_PROHIBITION, contract.BASIS_UNRESOLVED))

    def test_ordinary_text_types_no_effect_at_all(self):
        effect = contribution.declared_statutory_effect(
            "Owner wants to test six units.")
        self.assertIsNone(effect["statutory_effect"])
        self.assertFalse(effect["overreach"])


# ============================================================================
# S, T - POSTURE
# ============================================================================

class PostureTravelsFromThePremise(unittest.TestCase):
    """S, T - reusing planning_posture, not a parallel ladder."""

    def test_no_parallel_posture_engine_was_created(self):
        source = Path("services/planning_contribution.py").read_text(
            encoding="utf-8")
        self.assertIn("from services import planning_posture", source)
        for reinvention in ("POSTURE_LADDER =", 'POSTURE_AS_OF_RIGHT = "'):
            self.assertNotIn(reinvention, source, reinvention)

    def test_owner_intent_the_envelope_does_not_establish_is_speculative(self):
        record = _contribution("Test an 8-storey building.",
                               contribution.CLASS_OWNER_INTENT)
        self.assertEqual(contribution.implied_posture(record),
                         posture.POSTURE_SPECULATIVE_TEST)

    def test_text_conceding_relief_carries_relief_dependent(self):
        record = _contribution("Planner advised this may require relief.",
                               contribution.CLASS_PROFESSIONAL_JUDGMENT)
        self.assertEqual(contribution.implied_posture(record),
                         posture.POSTURE_RELIEF_DEPENDENT)

    def test_s_a_speculative_premise_cannot_become_as_of_right_downstream(self):
        review = {"implied_posture": posture.POSTURE_SPECULATIVE_TEST}
        outcome = contribution.derive_posture([review],
                                              posture.POSTURE_AS_OF_RIGHT)
        self.assertEqual(outcome["posture"], posture.POSTURE_SPECULATIVE_TEST)
        self.assertTrue(outcome["refused"])
        self.assertEqual(outcome["reason"], posture.REFUSED_NO_AUTHORITY)

    def test_s_a_relief_dependent_premise_cannot_become_as_of_right(self):
        outcome = contribution.derive_posture(
            [{"implied_posture": posture.POSTURE_RELIEF_DEPENDENT}],
            posture.POSTURE_AS_OF_RIGHT)
        self.assertEqual(outcome["posture"], posture.POSTURE_RELIEF_DEPENDENT)
        self.assertTrue(outcome["refused"])

    def test_s_the_most_conservative_premise_governs_a_set(self):
        """Two premises are no stronger than the weaker one. Taking the maximum
        rather than the minimum is how a qualification gets dropped."""
        outcome = contribution.derive_posture([
            {"implied_posture": posture.POSTURE_AS_OF_RIGHT},
            {"implied_posture": posture.POSTURE_SPECULATIVE_TEST}])
        self.assertEqual(outcome["posture"], posture.POSTURE_SPECULATIVE_TEST)

    def test_derived_work_may_be_more_conservative_freely(self):
        outcome = contribution.derive_posture(
            [{"implied_posture": posture.POSTURE_RELIEF_DEPENDENT}],
            posture.POSTURE_UNSUPPORTED)
        self.assertEqual(outcome["posture"], posture.POSTURE_UNSUPPORTED)
        self.assertFalse(outcome["refused"])

    def test_no_contributions_means_nothing_is_supported(self):
        self.assertEqual(contribution.derive_posture([])["posture"],
                         posture.POSTURE_UNSUPPORTED)

    def test_t_a_governed_authority_event_may_still_improve_posture(self):
        """T, through the committed gate - this module adds no bypass."""
        outcome = posture.authorize_transition(
            posture.POSTURE_RELIEF_DEPENDENT, posture.POSTURE_APPROVED_RELIEF,
            authority_event={"authority_ref": "TOR-COA-2026-114",
                             "decided_by": "Committee of Adjustment",
                             "decision": "MINOR_VARIANCE_GRANTED",
                             "decided_at": "2026-09-01"})
        self.assertEqual(outcome["posture"], posture.POSTURE_APPROVED_RELIEF)
        self.assertFalse(outcome["refused"])

    def test_t_a_contribution_is_not_an_authority_event(self):
        record = _contribution("The committee granted the variance.",
                               contribution.CLASS_PROFESSIONAL_JUDGMENT)
        self.assertFalse(posture.is_governed_authority_event(record))


# ============================================================================
# U, V, W, X - THE LAYERS
# ============================================================================

class TheLayersStayDistinguishable(unittest.TestCase):
    """U, V, W, X."""

    def _layered(self, *texts):
        records = [_contribution(text) for text in texts]
        reviews = [contribution.review(record, _document(), EVIDENCE_FACTS)
                   for record in records]
        return contribution.layered(_document(), _view(), records, reviews)

    def test_u_the_raw_contribution_is_preserved_even_when_quarantined(self):
        layered = self._layered("Maximum FSI is 2.5.")
        self.assertEqual(layered["admission"]["quarantined"], 1)
        self.assertEqual(len(layered["contributions"]), 1)
        self.assertEqual(layered["contributions"][0]["record"]["text"],
                         "Maximum FSI is 2.5.")

    def test_v_the_governed_result_is_a_separate_labelled_layer(self):
        layered = self._layered("Maximum FSI is 2.5.")
        self.assertEqual(layered["layers"],
                         ("GOVERNED_RESULT", "USER_CONTRIBUTION",
                          "GO_FOLLOW_UP", "ADMISSION_DECISION"))
        self.assertTrue(layered["governed_result"]["host_owned"])
        self.assertTrue(layered["governed_result"]["immutable_for_interaction"])
        self.assertFalse(layered["contributions"][0]["host_owned"])
        self.assertFalse(layered["follow_up"][0]["host_owned"])

    def test_v_a_contribution_never_appears_inside_the_governed_statements(self):
        document = _document()
        before = copy.deepcopy(document["statements"])
        layered = contribution.layered(
            document, _view(), [_contribution("Maximum FSI is 2.5.")],
            [contribution.review(_contribution("Maximum FSI is 2.5."),
                                 document, EVIDENCE_FACTS)])
        self.assertEqual(document["statements"], before)
        governed = layered["governed_result"]["view"]
        serialised = repr(governed)
        self.assertNotIn("Maximum FSI is 2.5", serialised)

    def test_w_host_facts_are_unchanged_through_the_whole_layering(self):
        document, facts = _document(), copy.deepcopy(EVIDENCE_FACTS)
        before_document, before_facts = copy.deepcopy(document), copy.deepcopy(facts)
        records = [_contribution("Maximum FSI is 2.5."),
                   _contribution("The total FSI is 4.0."),
                   _contribution("It is permitted because nothing prohibits it.")]
        reviews = [contribution.review(r, document, facts) for r in records]
        contribution.layered(document, _view(), records, reviews)
        self.assertEqual(document, before_document)
        self.assertEqual(facts, before_facts)

    def test_x_a_nonmaterial_quarantine_still_leaves_a_releasable_result(self):
        """Section 18/X. A quarantined contribution removes nothing from the
        governed result - the result is exactly as releasable as it was before
        anybody typed."""
        layered = self._layered("Maximum FSI is 2.5.")
        self.assertEqual(layered["admission"]["quarantined"], 1)
        self.assertEqual(layered["governed_result"]["result_status"],
                         "UNRESOLVED")
        self.assertTrue(layered["governed_result"]["view"]["identity"]["statements"]
                        or layered["governed_result"]["view"]["framework"]["statements"])

    def test_x_a_mixed_set_reports_both_counts(self):
        layered = self._layered("The total FSI of 2.0 is the cap.",
                                "Maximum FSI is 2.5.")
        self.assertEqual(layered["admission"]["admitted"], 1)
        self.assertEqual(layered["admission"]["quarantined"], 1)


# ============================================================================
# VISUAL EVIDENCE
# ============================================================================

class VisualEvidenceIsTheEvidence(unittest.TestCase):
    """Section 9. A panel a reader cannot trace is decoration."""

    def test_panels_are_drawn_from_the_retrieved_geometry(self):
        panels = planning_visual.panels_for(RETRIEVAL)
        self.assertEqual([p["kind"] for p in panels],
                         [planning_visual.PANEL_PARCEL,
                          planning_visual.PANEL_ZONING])
        for panel in panels:
            self.assertTrue(panel["drawn"])
            self.assertIn("<svg", panel["svg"])
            self.assertTrue(panel["is_official"])
            self.assertFalse(panel["is_user_supplied"])

    def test_every_panel_carries_source_layer_retrieval_and_parcel(self):
        panel = planning_visual.panels_for(RETRIEVAL)[0]
        self.assertTrue(panel["source"])
        self.assertTrue(panel["layer"])
        self.assertEqual(panel["retrieved_at"], "2026-09-13T12:00:00Z")
        self.assertEqual(panel["parcel_identifier"], "TOR-PARCEL-TEST")
        # SUPERSEDED DELIBERATELY - CLAUDE-PLANNING-SPATIAL-SEMANTICS-01 section
        # 2, Product Owner authorized. This asserted `panel["crs"]`, a constant
        # the renderer stated on its own authority. It was CORRECT and
        # UNVERIFIABLE at once: nothing tied it to what the City answered in, so
        # a service changing its output SR would have been misdescribed by a
        # panel that still looked right. The panel now carries the source
        # reference it was GIVEN, and names the display transform separately.
        self.assertEqual(panel["source_crs"], "EPSG:3857")
        self.assertEqual(panel["display_crs"], "EPSG:3857")
        self.assertIn("no reprojection", panel["display_transform"])
        self.assertTrue(panel["evidence_ref"])

    def test_the_panel_cites_the_same_geometry_the_engine_related(self):
        """What makes a panel evidence rather than a picture: the drawing and
        the finding reference one geometry hash."""
        tokens = {"zoning_area": {"provenance": {
            "subject_geometry_id": "sha256:from-the-token",
            "layer_geometry_id": "sha256:layer-from-the-token"}}}
        panels = planning_visual.panels_for(RETRIEVAL, tokens=tokens)
        self.assertEqual(panels[0]["evidence_ref"], "sha256:from-the-token")
        self.assertEqual(panels[1]["evidence_ref"], "sha256:layer-from-the-token")

    def test_a_panel_declines_rather_than_simplifying_a_complex_boundary(self):
        """A simplified boundary shown as evidence is a different boundary."""
        ring = [[float(i), float(i % 7)] for i in
                range(planning_visual.MAX_PANEL_VERTICES + 10)]
        panel = planning_visual.panel(
            planning_visual.PANEL_ZONING,
            {"type": "Polygon", "coordinates": [ring]},
            title="huge", source="s", layer="l")
        self.assertFalse(panel["drawn"])
        self.assertEqual(panel["declined_reason"],
                         planning_visual.DECLINED_TOO_COMPLEX)
        self.assertIsNone(panel["svg"])

    def test_a_missing_geometry_declines_with_a_reason(self):
        panel = planning_visual.panel(planning_visual.PANEL_PARCEL, None,
                                      title="t", source="s", layer="l")
        self.assertFalse(panel["drawn"])
        self.assertEqual(panel["declined_reason"],
                         planning_visual.DECLINED_NO_GEOMETRY)

    def test_a_retrieval_with_no_geometry_produces_no_panels(self):
        self.assertEqual(planning_visual.panels_for({"retrieved_at": "x"}), [])

    def test_the_panel_is_not_offered_as_a_survey(self):
        panel = planning_visual.panels_for(RETRIEVAL)[0]
        self.assertIn("not a survey", panel["limitation"])
        self.assertIn("no dimension may be scaled", panel["limitation"])

    def test_northing_is_not_drawn_upside_down(self):
        """A mirrored parcel is wrong in a way that looks entirely plausible."""
        panel = planning_visual.panel(
            planning_visual.PANEL_PARCEL,
            {"type": "Polygon",
             "coordinates": [[[0, 0], [10, 0], [10, 100], [0, 100], [0, 0]]]},
            title="t", source="s", layer="l", size=100, pad=0)
        points = re.findall(r"[ML]([\d.]+) ([\d.]+)", panel["svg"])
        ys = [float(y) for _x, y in points]
        # The first vertex is the SOUTH-WEST corner, so in SVG space it must be
        # the LARGEST y (furthest down the page), not the smallest.
        self.assertEqual(max(ys), ys[0])

    def test_this_module_cannot_reach_the_network(self):
        """Asserted against the IMPORT GRAPH and the call names, never the words.

        THE EIGHTH PROSE-SCAN FALSE POSITIVE IN THIS PROGRAMME WAS THIS TEST.
        It banned the substring "reader" and then matched the module's own
        docstring sentence "it has no reader, no URL and no network import" -
        the very claim the test exists to verify. Written, for the avoidance of
        doubt, in the same tranche as a commit message naming this pattern.
        """
        import ast

        tree = ast.parse(Path("services/planning_visual.py").read_text(
            encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        for banned in ("requests", "urllib", "urllib.request", "httpx",
                       "http.client", "socket", "services.toronto_planning_source"):
            self.assertNotIn(banned, imported, banned)

        # And no parameter named `reader` anywhere: that is how every other
        # module in this programme receives a network seam.
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names = [arg.arg for arg in node.args.args + node.args.kwonlyargs]
                self.assertNotIn("reader", names, node.name)

    def test_only_small_geometries_are_surfaced_for_drawing(self):
        """The Natural Heritage layer alone is 281,023 vertices. Surfacing the
        overlays would put megabytes into a response to draw an unreadable shape."""
        source = Path("services/toronto_gate01.py").read_text(encoding="utf-8")
        block = source[source.index('"visual_geometry"'):]
        block = block[:block.index("return outcome")]
        self.assertIn('"parcel"', block)
        self.assertIn('"zoning"', block)
        self.assertNotIn("overlays", block)
        self.assertNotIn("witness_geometry", block)


# ============================================================================
# ROUTES
# ============================================================================

class TheWorkspaceIsReachable(unittest.TestCase):

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_pzwork_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False
        with self.flask_app.app_context():
            db.session.add(User(username="planner",
                                password_hash=generate_password_hash("x"),
                                role="user"))
            db.session.commit()

    def _client(self):
        client = self.flask_app.test_client()
        client.post("/login", data={"username": "planner", "password": "x"},
                    follow_redirects=True)
        return client

    def test_the_result_page_renders_the_workspace(self):
        response = self._client().get("/planning-zoning/result")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('data-ui-ref="planning-zoning.result.workspace"', body)
        self.assertIn('data-ui-ref="planning-zoning.result.aside"', body)
        self.assertIn('data-ui-ref="planning-zoning.result.contribute.form"', body)

    def test_the_classification_control_offers_every_permitted_subtype(self):
        body = self._client().get("/planning-zoning/result").get_data(as_text=True)
        for value in contribution.CLASSIFICATIONS:
            self.assertIn('value="%s"' % value, body, value)
        for banned in contribution.HOST_ONLY_CLASSES:
            self.assertNotIn('value="%s"' % banned, body, banned)

    def test_the_export_controls_are_present(self):
        body = self._client().get("/planning-zoning/result").get_data(as_text=True)
        self.assertIn('data-ui-ref="planning-zoning.result.export.docx"', body)
        self.assertIn('data-ui-ref="planning-zoning.result.export.pdf"', body)

    def test_exporting_the_fixture_returns_a_word_file(self):
        response = self._client().post("/planning-zoning/export",
                                       data={"format": "docx", "address": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[:2], b"PK")
        self.assertIn("attachment", response.headers["Content-Disposition"])

    def test_exporting_the_fixture_returns_a_pdf_file(self):
        response = self._client().post("/planning-zoning/export",
                                       data={"format": "pdf", "address": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[:5], b"%PDF-")

    def test_an_unsupported_export_format_is_refused(self):
        for bad in ("xlsx", "exe", ""):
            with self.subTest(export_format=bad):
                response = self._client().post("/planning-zoning/export",
                                               data={"format": bad})
                self.assertEqual(response.status_code, 400)

    def test_export_requires_a_signed_in_session(self):
        response = self.flask_app.test_client().post(
            "/planning-zoning/export", data={"format": "pdf"})
        self.assertIn(response.status_code, (302, 401, 403))

    def test_the_fixture_export_is_labelled_as_a_fixture(self):
        """A preview must not produce a file that reads as analysis."""
        from services import planning_result_view
        document = planning_export.build_export_document(
            planning_result_view.development_view())
        self.assertIn("DEVELOPMENT FIXTURE", "\n".join(document.preamble))

    def test_a_posted_host_classification_is_downgraded_not_honoured(self):
        """The route resolves the classification through `classify`, so a
        crafted POST cannot mint an AUTHORITY_SAYS contribution."""
        from routes import planning_zoning

        class _Form(dict):
            def get(self, key, default=None):
                return dict.get(self, key, default)

        records = planning_zoning._contributions_from(_Form({
            "contribution": "The by-law requires 9.0.",
            "contribution_class": "AUTHORITY_SAYS"}))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["classification"],
                         contribution.CLASS_USER_INPUT)


class NothingWasPersisted(unittest.TestCase):
    """Section 22, asserted against the CALL SURFACE rather than a promise."""

    def test_no_workspace_module_can_write_anything(self):
        import ast

        for name in ("services/planning_contribution.py",
                     "services/planning_export.py",
                     "services/planning_visual.py"):
            tree = ast.parse(Path(name).read_text(encoding="utf-8"))
            calls = {ast.unparse(node.func) for node in ast.walk(tree)
                     if isinstance(node, ast.Call)}
            for banned in ("open", "io.open", "get_registry", "db.session.add",
                           "json.dump", "shutil.copy"):
                self.assertNotIn(banned, calls, "%s in %s" % (banned, name))

    def test_no_store_or_session_is_imported_by_the_workspace_modules(self):
        for name in ("services/planning_contribution.py",
                     "services/planning_visual.py"):
            source = Path(name).read_text(encoding="utf-8")
            for banned in ("from flask import session", "case_workspace",
                           "get_registry", "sqlalchemy"):
                self.assertNotIn(banned, source, "%s in %s" % (banned, name))


if __name__ == "__main__":
    unittest.main()
