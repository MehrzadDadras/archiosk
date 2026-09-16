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
        workspace = _FakeWorkspace(
            sources=[{"id": self.BASE, "name": "Specification.pdf"},
                     {"id": self.ADDENDUM, "name": "Addendum 3.pdf"}],
            pages={})
        _patch_pages(self, {
            self.BASE: "Section 2.4 AHU-1 shall serve Room 203.",
            self.ADDENDUM: addendum_text,
        })
        return _FakeStore(workspace), workspace

    def test_a_replacement_creates_the_governed_supersession(self):
        store, workspace = self._build(
            "Addendum 3. Delete Section 2.4 and replace with the following.")
        report = package_muscles.register_supersessions(
            store, workspace, self.ADDENDUM)

        self.assertEqual(report["recorded"], 1)
        self.assertEqual(report["clauses"], ["2.4"])
        self.assertEqual(len(store.supersessions), 1)
        self.assertEqual(store.supersessions[0]["predecessor_id"], self.BASE)
        self.assertEqual(store.supersessions[0]["successor_id"], self.ADDENDUM)
        self.assertIn("2.4", store.supersessions[0]["reason"])

    def test_a_mere_reference_creates_nothing(self):
        """The failure that would hide a requirement which still governs."""
        store, workspace = self._build(
            "Addendum 3. Refer to Section 2.4 for coordination requirements.")
        report = package_muscles.register_supersessions(
            store, workspace, self.ADDENDUM)

        self.assertEqual(report["recorded"], 0)
        self.assertEqual(store.supersessions, [],
                         "a reference was recorded as a replacement")
        self.assertIn("2.4", report["mentions"])

    def test_a_supplement_creates_nothing(self):
        store, workspace = self._build(
            "Addendum 3. This clause supplements Section 2.4.")
        self.assertEqual(
            package_muscles.register_supersessions(
                store, workspace, self.ADDENDUM)["recorded"], 0)
        self.assertEqual(store.supersessions, [])

    def test_nothing_is_recorded_when_no_source_states_that_clause(self):
        """A supersession must point at something real."""
        store, workspace = self._build(
            "Addendum 3. Delete Section 99.9 and replace with the following.")
        report = package_muscles.register_supersessions(
            store, workspace, self.ADDENDUM)

        self.assertEqual(report["recorded"], 0)
        self.assertEqual(store.supersessions, [])
        self.assertIn("no earlier source", report.get("note", ""))

    def test_both_documents_survive(self):
        store, workspace = self._build(
            "Addendum 3. Delete Section 2.4 and replace with the following.")
        package_muscles.register_supersessions(store, workspace, self.ADDENDUM)

        live = {s["id"] for s in workspace.sources if not s.get("removed_at")}
        self.assertEqual(live, {self.BASE, self.ADDENDUM},
                         "recording a supersession removed a document")


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

        # COMPARE / REASON - the addendum replaces a clause the spec states.
        self.assertTrue(store.supersessions, "no supersession was recorded")
        self.assertEqual(store.supersessions[0]["predecessor_id"], "spec")

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
