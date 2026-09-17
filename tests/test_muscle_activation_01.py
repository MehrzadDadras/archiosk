"""CLAUDE-MUSCLE-ACTIVATION-01 - the five muscles on one governed route.

The muscles have their own isolated tests in `test_document_muscles_01.py`.
This file tests the ACTIVATION: that each one now has a production caller, that
what it writes goes through a primitive that already existed, and that the
restraint cases still hold when it is wired to real storage.
"""
import json
import unittest
from pathlib import Path

from services import package_muscles

_REPO_ROOT = Path(__file__).resolve().parent.parent


class _FakeStore:
    """Records what was written, through the same method names the real store
    exposes. A fake rather than a mock because the ASSERTION is which governed
    primitive was called - and a fake makes a call to a primitive that does not
    exist fail loudly instead of being silently absorbed."""

    def __init__(self, workspace):
        self.workspace = workspace
        self.evidence = []
        self.relationships = []
        self.supersessions = []

    def get(self, _project_id):
        return self.workspace

    def register_evidence_item(self, workspace, *, source_id, evidence_class,
                               content, content_type, extractor_version=None,
                               actor="system", governance_log=None, **kw):
        row = {"id": "ev-%d" % (len(self.evidence) + 1), "source_id": source_id,
               "evidence_class": evidence_class, "content": content,
               "content_type": content_type,
               "extractor_version": extractor_version}
        self.evidence.append(row)
        workspace.evidence_items.append(row)
        return row

    def record_evidence_relationship(self, workspace, *, from_type, from_id,
                                     to_type, to_id, relationship_type,
                                     reason=None, created_by=None,
                                     provisional=True, governance_log=None, **kw):
        row = {"from_id": from_id, "to_id": to_id, "type": relationship_type,
               "reason": reason, "provisional": provisional}
        self.relationships.append(row)
        return row

    def record_supersession(self, workspace, *, predecessor_type,
                            predecessor_id, successor_type, successor_id,
                            actor, reason=None, authority_class=None):
        row = {"predecessor_id": predecessor_id, "successor_id": successor_id,
               "reason": reason}
        self.supersessions.append(row)
        return row


class _FakeWorkspace:
    def __init__(self, sources, pages):
        self.project_id = "p1"
        self.sources = sources
        self.evidence_items = []
        self.addressable_regions = []
        self.structural_units = []
        self.change_arrival_assessments = []
        self._pages = pages


def _patch_pages(test, pages):
    """`recovered_pages_for` is the existing reader; the fake supplies text."""
    from unittest.mock import patch

    from services import sheet_identity

    patcher = patch.object(sheet_identity, "recovered_pages_for",
                           lambda ws, sid: [{"text": pages.get(sid, "")}])
    patcher.start()
    test.addCleanup(patcher.stop)


class F3SubjectKeysActivated(unittest.TestCase):
    """AHU-1 in a requirement and AHU-1 on a schedule reach one key, stored."""

    SPEC = "spec-1"
    SHEET = "sheet-1"

    def setUp(self):
        self.workspace = _FakeWorkspace(
            sources=[{"id": self.SPEC, "name": "Specification.pdf"},
                     {"id": self.SHEET, "name": "M-501.pdf"}],
            pages={})
        _patch_pages(self, {
            self.SPEC: "Section 2.4 AHU-1 shall serve Room 203.",
            self.SHEET: "MECHANICAL SCHEDULE | AHU 01 | serves RM 203",
        })
        self.store = _FakeStore(self.workspace)

    def test_both_sources_register_the_same_normalised_key(self):
        for source_id in (self.SPEC, self.SHEET):
            package_muscles.register_subject_keys(
                self.store, self.workspace, source_id)

        spec_keys = set(package_muscles.subjects_of(self.workspace, self.SPEC))
        sheet_keys = set(package_muscles.subjects_of(self.workspace, self.SHEET))

        self.assertIn("equipment:AHU-1", spec_keys)
        self.assertIn("equipment:AHU-1", sheet_keys,
                      "the drawing schedule did not reach the same key")
        self.assertIn("room:203", spec_keys & sheet_keys)

    def test_the_bridge_uses_the_relationship_that_already_existed(self):
        from services.case_workspace import RELATIONSHIP_TYPE_SAME_SUBJECT_AS

        for source_id in (self.SPEC, self.SHEET):
            package_muscles.register_subject_keys(
                self.store, self.workspace, source_id)
        report = package_muscles.link_shared_subjects(
            self.store, self.workspace, self.SHEET)

        self.assertEqual(report["links"], 1)
        self.assertIn("equipment:AHU-1", report["shared"])
        self.assertEqual(self.store.relationships[0]["type"],
                         RELATIONSHIP_TYPE_SAME_SUBJECT_AS)
        self.assertTrue(self.store.relationships[0]["provisional"],
                        "a detected link was recorded as settled fact")

    def test_subjects_are_stored_as_a_proposal_not_as_truth(self):
        from services.case_workspace import EVIDENCE_CLASS_AI_GENERATED_PROPOSAL

        package_muscles.register_subject_keys(
            self.store, self.workspace, self.SPEC)
        self.assertEqual(self.store.evidence[0]["evidence_class"],
                         EVIDENCE_CLASS_AI_GENERATED_PROPOSAL)

    def test_unrelated_sources_are_not_linked(self):
        _patch_pages(self, {self.SPEC: "AHU-1 shall serve Room 203.",
                            self.SHEET: "ELECTRICAL PANEL SCHEDULE PNL-7"})
        for source_id in (self.SPEC, self.SHEET):
            package_muscles.register_subject_keys(
                self.store, self.workspace, source_id)
        report = package_muscles.link_shared_subjects(
            self.store, self.workspace, self.SHEET)
        self.assertEqual(report["links"], 0)


class F4SupersessionActivated(unittest.TestCase):
    """An addendum that replaces creates the record; one that refers does not."""

    BASE = "spec-1"
    ADDENDUM = "add-3"

    def _build(self, addendum_text):
        import tempfile
        from services.case_workspace import CaseWorkspaceStore
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = CaseWorkspaceStore(Path(tmp.name))
        workspace = store.get_or_create("scope-qualification")
        base = store.add_source(workspace, name="Specification.pdf", file_path=None,
                                kind="project_document", document_authority="contractual")
        addendum = store.add_source(workspace, name="Addendum 3.pdf", file_path=None,
                                    kind="project_document", document_authority="contractual")
        self.BASE, self.ADDENDUM = base["id"], addendum["id"]
        store.register_pdf_page_structure(workspace, self.BASE,
            ["Section 2.4 AHU-1 shall serve Room 203.\n\nSection 2.5 Doors shall remain locked."])
        store.register_pdf_page_structure(workspace, self.ADDENDUM, [addendum_text])
        return store, workspace

    def test_replacement_requires_acceptance_and_preserves_exact_scope_after_reload(self):
        from services import change_application as ca
        store, workspace = self._build(
            "Replace Section 2.4 with: AHU-1 shall serve Room 204.")
        report = package_muscles.register_supersessions(
            store, workspace, self.ADDENDUM)

        self.assertEqual(report["recorded"], 0)
        self.assertEqual(report["proposed"], 1)
        self.assertEqual(workspace.supersessions, [])
        assessment_id = report["assessment_ids"][0]
        original = {e["id"]: dict(e) for e in workspace.evidence_items}
        with self.assertRaises(ca.ChangeApplicationError):
            ca.apply_accepted_change(store, workspace, assessment_id, actor="reviewer")
        store.review_change_arrival_assessment(workspace, assessment_id, actor="reviewer", outcome="accepted")
        workspace = store.get(workspace.project_id)
        ca.apply_accepted_change(store, workspace, assessment_id, actor="reviewer")
        workspace = store.get(workspace.project_id)
        link = workspace.supersessions[0]
        self.assertEqual(link["predecessor_type"], "evidence_item")
        self.assertEqual(link["successor_type"], "evidence_item")
        self.assertEqual(original[link["predecessor_id"]]["content"], "Section 2.4 AHU-1 shall serve Room 203.")
        self.assertEqual(original[link["successor_id"]]["content"], "Replace Section 2.4 with: AHU-1 shall serve Room 204.")
        self.assertEqual(link["authority_class"], "contractual")
        for item in workspace.evidence_items:
            self.assertEqual(item, original[item["id"]])
            if "2.5" in item["content"]:
                self.assertEqual(store.supersessions_for(workspace, "evidence_item", item["id"]), [])
        self.assertEqual(store.supersessions_for(workspace, "source", self.BASE), [])
        self.assertTrue(ca.apply_accepted_change(store, workspace, assessment_id, actor="reviewer")["already_applied"])
        package_muscles.register_supersessions(store, workspace, self.ADDENDUM)
        self.assertEqual(len(workspace.supersessions), 1)
        self.assertEqual(len(workspace.change_arrival_assessments), 1)

    def test_a_mere_reference_creates_nothing(self):
        """The failure that would hide a requirement which still governs."""
        store, workspace = self._build(
            "Refer to Section 2.4 for coordination requirements.")
        report = package_muscles.register_supersessions(
            store, workspace, self.ADDENDUM)

        self.assertEqual(report["recorded"], 0)
        self.assertEqual(workspace.supersessions, [],
                         "a reference was recorded as a replacement")
        self.assertEqual(report["proposed"], 0)

    def test_a_supplement_creates_nothing(self):
        store, workspace = self._build(
            "This clause supplements Section 2.4.")
        self.assertEqual(
            package_muscles.register_supersessions(
                store, workspace, self.ADDENDUM)["recorded"], 0)
        self.assertEqual(workspace.supersessions, [])

    def test_nothing_is_recorded_when_no_source_states_that_clause(self):
        """A supersession must point at something real."""
        store, workspace = self._build(
            "Replace Section 99.9 with: Use new equipment.")
        report = package_muscles.register_supersessions(
            store, workspace, self.ADDENDUM)

        self.assertEqual(report["recorded"], 0)
        self.assertEqual(workspace.supersessions, [])
        self.assertEqual(report["unresolved"], 1)

    def test_both_documents_survive(self):
        store, workspace = self._build(
            "Replace Section 2.4 with: AHU-1 shall serve Room 204.")
        package_muscles.register_supersessions(store, workspace, self.ADDENDUM)

        live = {s["id"] for s in workspace.sources if not s.get("removed_at")}
        self.assertEqual(live, {self.BASE, self.ADDENDUM},
                         "recording a supersession removed a document")

    def test_ambiguous_predecessor_cannot_be_accepted(self):
        from services.case_workspace import CaseWorkspaceError
        store, workspace = self._build("Replace Section 2.4 with: New requirement.")
        other = store.add_source(workspace, name="Other.pdf", file_path=None, kind="project_document")
        store.register_pdf_page_structure(workspace, other["id"], ["Section 2.4 Another requirement."])
        report = package_muscles.register_supersessions(store, workspace, self.ADDENDUM)
        self.assertEqual(report["unresolved"], 1)
        assessment = workspace.change_arrival_assessments[0]
        _, proposal = package_muscles.supersession_proposal(workspace, assessment["supersession_proposal_id"])
        self.assertIsNone(proposal["predecessor"])
        self.assertEqual(len(proposal["predecessor_candidates"]), 2)
        with self.assertRaises(CaseWorkspaceError):
            store.review_change_arrival_assessment(workspace, assessment["id"], actor="reviewer", outcome="accepted")
        self.assertEqual(workspace.supersessions, [])

    def test_explicit_whole_document_replacement_only_after_acceptance(self):
        from services import change_application as ca
        store, workspace = self._build('This document replaces "Specification.pdf" in its entirety.')
        report = package_muscles.register_supersessions(store, workspace, self.ADDENDUM)
        self.assertEqual(workspace.supersessions, [])
        self.assertEqual(report["unresolved"], 0)
        aid = report["assessment_ids"][0]
        store.review_change_arrival_assessment(workspace, aid, actor="reviewer", outcome="accepted")
        ca.apply_accepted_change(store, workspace, aid, actor="reviewer")
        link = store.get(workspace.project_id).supersessions[0]
        self.assertEqual((link["predecessor_type"], link["predecessor_id"]), ("source", self.BASE))
        self.assertEqual((link["successor_type"], link["successor_id"]), ("source", self.ADDENDUM))
        self.assertEqual(workspace.sources[0]["superseded_by_source_id"], self.ADDENDUM)
        self.assertEqual(workspace.sources[1]["supersedes_source_id"], self.BASE)

    def test_rejection_or_deferral_never_applies(self):
        from services import change_application as ca
        for outcome in (None, "rejected"):
            with self.subTest(outcome=outcome):
                store, workspace = self._build("Section 2.4 is amended to read: New requirement.")
                aid = package_muscles.register_supersessions(store, workspace, self.ADDENDUM)["assessment_ids"][0]
                if outcome:
                    store.review_change_arrival_assessment(workspace, aid, actor="reviewer", outcome=outcome)
                with self.assertRaises(ca.ChangeApplicationError):
                    ca.apply_accepted_change(store, workspace, aid, actor="reviewer")
                self.assertEqual(workspace.supersessions, [])

    def test_missing_authority_or_ocr_target_is_unresolved(self):
        for weak in ("authority", "ocr"):
            with self.subTest(weak=weak):
                store, workspace = self._build("Replace Section 2.4 with: New requirement.")
                if weak == "authority":
                    workspace.sources[1]["document_authority"] = None
                else:
                    workspace.evidence_items[0]["evidence_class"] = "ai_generated_proposal"
                report = package_muscles.register_supersessions(store, workspace, self.ADDENDUM)
                self.assertEqual(report["unresolved"], 1)
                self.assertEqual(workspace.supersessions, [])

    def test_changed_evidence_after_acceptance_is_refused(self):
        from services import change_application as ca
        store, workspace = self._build("Replace Section 2.4 with: New requirement.")
        aid = package_muscles.register_supersessions(store, workspace, self.ADDENDUM)["assessment_ids"][0]
        store.review_change_arrival_assessment(workspace, aid, actor="reviewer", outcome="accepted")
        workspace.evidence_items[0]["content"] = "Section 2.4 Changed text at the same clause id."
        with self.assertRaises(ca.ChangeApplicationError):
            ca.apply_accepted_change(store, workspace, aid, actor="reviewer")
        self.assertEqual(workspace.supersessions, [])

    def test_nearby_replacement_verb_does_not_promote_a_mention(self):
        store, workspace = self._build("Refer to Section 2.4. Replace damaged equipment promptly.")
        report = package_muscles.register_supersessions(store, workspace, self.ADDENDUM)
        self.assertEqual(report["proposed"], 0)
        self.assertEqual(workspace.supersessions, [])

    def test_multiple_clause_headings_in_one_paragraph_require_finer_scope(self):
        store, workspace = self._build("Replace Section 2.4 with: New requirement.")
        workspace.evidence_items[0]["content"] += "\nSection 2.6 Keep this separate clause."
        report = package_muscles.register_supersessions(store, workspace, self.ADDENDUM)
        self.assertEqual(report["unresolved"], 1)
        self.assertEqual(workspace.supersessions, [])

    def test_replacement_without_its_body_is_unresolved(self):
        store, workspace = self._build("Delete Section 2.4 and replace with the following.")
        report = package_muscles.register_supersessions(store, workspace, self.ADDENDUM)
        self.assertEqual(report["unresolved"], 1)
        self.assertEqual(workspace.supersessions, [])

    def test_runtime_accept_and_apply_routes_keep_the_same_human_gate(self):
        import app as app_module
        from unittest.mock import patch
        from routes import workspace as routes
        store, workspace = self._build("Replace Section 2.4 with: New requirement.")
        aid = package_muscles.register_supersessions(store, workspace, self.ADDENDUM)["assessment_ids"][0]
        app = app_module.create_app("testing")
        from models import db, User
        from werkzeug.security import generate_password_hash
        with app.app_context():
            db.create_all()
            user = User.query.filter_by(username="scope-reviewer").first()
            if user is None:
                user = User(username="scope-reviewer", role="customer")
                user.password_hash = generate_password_hash("scope-test-password")
                db.session.add(user)
                db.session.commit()
        client = app.test_client()
        client.post("/login", data={"username": "scope-reviewer", "password": "scope-test-password"})
        root = "/projects/%s/workspace/change-arrival/%s" % (workspace.project_id, aid)
        with patch.object(routes, "_load_workspace_or_404", side_effect=lambda _: (None, store, store.get(workspace.project_id))), \
                patch.object(routes, "_reviewer", return_value="human-reviewer"), \
                patch.object(routes, "_log", return_value=None):
            self.assertEqual(client.post(root + "/apply").status_code, 302)
            self.assertEqual(store.get(workspace.project_id).supersessions, [])
            self.assertEqual(client.post(root + "/review", data={"outcome": "accepted"}).status_code, 302)
            self.assertEqual(store.get(workspace.project_id).supersessions, [])
            self.assertEqual(client.post(root + "/apply").status_code, 302)
            reloaded = store.get(workspace.project_id)
            self.assertEqual(len(reloaded.supersessions), 1)
            self.assertEqual(reloaded.supersessions[0]["predecessor_type"], "evidence_item")

    def test_interrupted_assessment_stamp_reuses_the_authoritative_edge(self):
        from unittest.mock import patch
        from services import change_application as ca
        store, workspace = self._build("Replace Section 2.4 with: New requirement.")
        aid = package_muscles.register_supersessions(store, workspace, self.ADDENDUM)["assessment_ids"][0]
        store.review_change_arrival_assessment(workspace, aid, actor="reviewer", outcome="accepted")
        with patch.object(store, "mark_change_arrival_applied", side_effect=RuntimeError("interrupted")):
            with self.assertRaises(RuntimeError):
                ca.apply_accepted_change(store, workspace, aid, actor="reviewer")
        workspace = store.get(workspace.project_id)
        ca.apply_accepted_change(store, workspace, aid, actor="reviewer")
        self.assertEqual(len(workspace.supersessions), 1)

    def test_conflicting_accepted_successors_are_not_silently_branched(self):
        from services import change_application as ca
        store, workspace = self._build("Replace Section 2.4 with: First replacement.")
        second = store.add_source(workspace, name="Second.pdf", file_path=None,
                                  kind="project_document", document_authority="contractual")
        store.register_pdf_page_structure(workspace, second["id"], ["Replace Section 2.4 with: Second replacement."])
        aids = [package_muscles.register_supersessions(store, workspace, sid)["assessment_ids"][0]
                for sid in (self.ADDENDUM, second["id"])]
        for aid in aids:
            store.review_change_arrival_assessment(workspace, aid, actor="reviewer", outcome="accepted")
        ca.apply_accepted_change(store, workspace, aids[0], actor="reviewer")
        with self.assertRaises(ca.ChangeApplicationConflict):
            ca.apply_accepted_change(store, workspace, aids[1], actor="reviewer")
        self.assertEqual(len(ca.pending_conflicts(store, workspace)), 1)
        self.assertFalse(ca.transition_brief(store, workspace, aids[1])["applicable"])


class F5ManifestGapActivated(unittest.TestCase):
    """not_found stops being a log count and becomes governed evidence."""

    INDEX = "idx-1"

    def setUp(self):
        self.workspace = _FakeWorkspace(
            sources=[{"id": self.INDEX, "name": "Drawing List.pdf"},
                     {"id": "s-a201", "name": "A-201 Plan.pdf"}],
            pages={})
        _patch_pages(self, {
            self.INDEX: "DRAWING INDEX  A-201  A-203",
            "s-a201": "floor plan",
        })
        self.store = _FakeStore(self.workspace)

    def test_a_declared_but_absent_sheet_is_registered(self):
        report = package_muscles.register_manifest_gaps(
            self.store, self.workspace, self.INDEX)

        self.assertEqual(report["registered"], 1)
        self.assertEqual(report["missing"], ["A203"])
        self.assertEqual(self.store.evidence[0]["content_type"],
                         package_muscles.MANIFEST_GAP_CONTENT_TYPE)

    def test_nothing_is_invented_about_the_missing_sheet(self):
        package_muscles.register_manifest_gaps(
            self.store, self.workspace, self.INDEX)
        payload = json.loads(self.store.evidence[0]["content"])
        entry = payload["missing"][0]

        self.assertIsNone(entry["contents_claim"])
        for word in ("probably", "likely", "would have", "should contain"):
            self.assertNotIn(word, entry["statement"].lower())

    def test_a_delivered_sheet_is_not_reported_missing(self):
        report = package_muscles.register_manifest_gaps(
            self.store, self.workspace, self.INDEX)
        self.assertNotIn("A201", report["missing"])


class ActivationIsReachableFromProduction(unittest.TestCase):
    """The chain step that the muscle map kept finding broken: a caller."""

    def test_the_examination_path_calls_the_hook(self):
        source = (_REPO_ROOT / "services" / "visual_classification.py").read_text(
            encoding="utf-8")
        self.assertIn("package_muscles.activate", source,
                      "the muscles have no production caller")

    def test_activation_never_fails_an_examination(self):
        """The reading is worth more than the enrichment."""
        source = (_REPO_ROOT / "services" / "visual_classification.py").read_text(
            encoding="utf-8")
        hook = source[source.index("package_muscles.activate") - 400:
                      source.index("package_muscles.activate") + 400]
        self.assertIn("except Exception", hook)

    def test_no_new_storage_primitive_was_invented(self):
        """Every write goes through something that already existed."""
        source = (_REPO_ROOT / "services" / "package_muscles.py").read_text(
            encoding="utf-8")
        for primitive in ("register_evidence_item",
                          "record_evidence_relationship",
                          "record_supersession"):
            self.assertIn(primitive, source)
        for invented in ("def create_", "class .*Store", "open(", "sqlite"):
            self.assertNotIn(invented, source,
                             "%r looks like new storage" % invented)


class MixedPackageActivated(unittest.TestCase):
    """One bounded package, end to end, through the activated route."""

    def test_situate_bind_compare_reason_govern(self):
        from services import sheet_identity

        workspace = _FakeWorkspace(
            sources=[{"id": "spec", "name": "Specification.pdf"},
                     {"id": "m501", "name": "M-501.pdf"},
                     {"id": "add3", "name": "Addendum 3.pdf"},
                     {"id": "idx", "name": "Drawing List.pdf"}],
            pages={})
        _patch_pages(self, {
            "spec": "Section 2.4 AHU-1 shall serve Room 203.",
            "m501": "MECHANICAL SCHEDULE | AHU 01 | serves RM 203",
            "add3": "Delete Section 2.4 and replace with the following.",
            "idx": "DRAWING INDEX  M-501  A-203",
        })
        store = _FakeStore(workspace)

        for source_id in ("spec", "m501", "add3", "idx"):
            package_muscles.activate(store, workspace, source_id)

        # SITUATE - the sheet declares its discipline.
        self.assertEqual(sheet_identity.discipline_of("M-501"), "mechanical")

        # BIND - the clause and the schedule share a subject key.
        self.assertIn("equipment:AHU-1",
                      package_muscles.subjects_of(workspace, "spec"))
        self.assertIn("equipment:AHU-1",
                      package_muscles.subjects_of(workspace, "m501"))

        # Unanchored test strings do not prove a clause endpoint or authorize lineage.
        self.assertEqual(store.supersessions, [])

        # REASON - a declared sheet was not delivered.
        gaps = [json.loads(e["content"])["missing"] for e in store.evidence
                if e["content_type"] == package_muscles.MANIFEST_GAP_CONTENT_TYPE]
        self.assertIn("A203", [g["sheet_token"] for group in gaps for g in group])

        # GOVERN - nothing was promoted past a proposal.
        from services.case_workspace import EVIDENCE_CLASS_AI_GENERATED_PROPOSAL
        for row in store.evidence:
            self.assertEqual(row["evidence_class"],
                             EVIDENCE_CLASS_AI_GENERATED_PROPOSAL)
        for row in store.relationships:
            self.assertTrue(row["provisional"])

    def test_the_finding_is_reconstructable(self):
        """Source identity, subject binding, supersession state and certainty
        must all be recoverable from what was stored."""
        from services import binding, sheet_identity

        self.assertEqual(sheet_identity.discipline_of("M-501"), "mechanical")
        value = binding.bind(4000, read_certainty="RECOVERED",
                             bind_basis=binding.BIND_BASIS_PROXIMITY,
                             bound_to="AHU-1")
        self.assertEqual(binding.bound_certainty(value), "PARTIALLY_RECOVERED")


if __name__ == "__main__":
    unittest.main()
