"""CLAUDE-FACET-ROUTING-01 - the three separations, each with a test.

    FACET SELECTION != FINDING ACCEPTANCE
    PROJECT CREATION != AUTHORITY PROMOTION
    UNSELECTED FACETS REMAIN VISIBLE AND UNPROMOTED
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import (
    DISPOSITIONS,
    REVIEWER_VALIDATION_STATES,
    CaseWorkspaceError,
    CaseWorkspaceStore,
)
from services.facet_routing import (
    FACET_ACTIVE,
    FACET_DECLINED,
    FACET_DEFERRED,
    FACET_MONITOR,
    FACET_RESOLVED,
    KNOWN_FACET_ROUTINGS,
    create_project_from_investigation,
    current_routing,
    facet_export_document,
    facets_of,
    route_facet,
    routing_history,
)


class _Fixture(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.store = CaseWorkspaceStore(self.root / "registry")
        self.workspace = self.store.get_or_create("proj-facets")
        self.ref = "study-001"

    def _route(self, key, routing, rationale=None):
        return route_facet(self.store, self.workspace, investigation_ref=self.ref,
                           facet_key=key, routing=routing, actor="reviewer",
                           rationale=rationale)


class TheRoutingAxisIsItsOwn(_Fixture):
    def test_routing_shares_no_value_with_the_finding_vocabularies(self):
        """The drift this module exists to prevent, asserted directly."""
        routings = {r.lower() for r in KNOWN_FACET_ROUTINGS}
        self.assertFalse(routings & {d.lower() for d in REVIEWER_VALIDATION_STATES})
        overlap = routings & {d.lower() for d in DISPOSITIONS}
        # "Deferred" is the one word both axes legitimately use; it must still
        # be a different field, which the disjoint storage below proves.
        self.assertLessEqual(overlap, {"deferred"})

    def test_routing_writes_nothing_into_findings_or_dispositions(self):
        self._route("Height limit", FACET_ACTIVE)
        self.assertEqual(self.workspace.findings, [])
        self.assertEqual(self.workspace.reviewer_validations, [])
        self.assertEqual(self.workspace.dispositions, [])
        self.assertEqual(len(self.workspace.facet_routings), 1)

    def test_an_unknown_routing_is_refused(self):
        with self.assertRaises(CaseWorkspaceError):
            self._route("Height limit", "PROBABLY")

    def test_all_five_routings_are_accepted(self):
        for index, routing in enumerate(KNOWN_FACET_ROUTINGS):
            record = self._route(f"facet-{index}", routing)
            self.assertEqual(record["routing"], routing)


class RoutingIsAppendOnly(_Fixture):
    def test_a_rerouting_supersedes_and_preserves_the_earlier_decision(self):
        first = self._route("Parking ratio", FACET_ACTIVE, "Looks material")
        second = self._route("Parking ratio", FACET_DEFERRED, "Waiting on survey")

        self.assertEqual(second["supersedes_id"], first["id"])
        self.assertEqual(current_routing(self.workspace, self.ref, "Parking ratio")["routing"],
                         FACET_DEFERRED)

        history = routing_history(self.workspace, self.ref, "Parking ratio")
        self.assertEqual([h["routing"] for h in history], [FACET_ACTIVE, FACET_DEFERRED])
        # The original rationale survives - "why was this not pursued" is
        # exactly what gets asked six months later.
        self.assertEqual(history[0]["rationale"], "Looks material")
        self.assertEqual(history[0]["superseded_by_id"], second["id"])

    def test_an_unrouted_facet_is_none_not_a_default(self):
        self.assertIsNone(current_routing(self.workspace, self.ref, "never-touched"))


class UnselectedFacetsRemainVisible(_Fixture):
    def test_facets_of_returns_every_facet_regardless_of_routing(self):
        self._route("A", FACET_ACTIVE)
        self._route("B", FACET_DECLINED)
        self._route("C", FACET_MONITOR)
        self._route("D", FACET_RESOLVED)

        keys = {f["facet_key"] for f in facets_of(self.workspace, self.ref)}
        self.assertEqual(keys, {"A", "B", "C", "D"})


class ProjectCreationIsNotAuthorityPromotion(_Fixture):
    def _investigation(self):
        self._route("Height limit", FACET_ACTIVE, "Governs the massing")
        self._route("Heritage overlay", FACET_ACTIVE)
        self._route("Parking ratio", FACET_DEFERRED, "Waiting on survey")
        self._route("Noise study", FACET_DECLINED, "Out of scope for this stage")

    def test_only_active_facets_become_cases(self):
        self._investigation()
        result = create_project_from_investigation(
            self.store, self.workspace, investigation_ref=self.ref,
            new_project_id="proj-promoted", title="Promoted Study", actor="reviewer")

        target = self.store.get("proj-promoted")
        self.assertEqual({c["title"] for c in target.cases},
                         {"Height limit", "Heritage overlay"})
        self.assertEqual(len(result["cases"]), 2)

    def test_nothing_operative_crosses_the_boundary(self):
        """The property the whole step turns on."""
        self._investigation()
        create_project_from_investigation(
            self.store, self.workspace, investigation_ref=self.ref,
            new_project_id="proj-promoted", title="Promoted Study", actor="reviewer")

        target = self.store.get("proj-promoted")
        self.assertEqual(target.findings, [])
        self.assertEqual(target.reviewer_validations, [])
        self.assertEqual(target.dispositions, [])
        self.assertEqual(target.sources, [])
        self.assertEqual(target.evidence_items, [])
        # The new Cases hold a question, not a conclusion.
        for case in target.cases:
            self.assertEqual(case["finding_ids"], [])

    def test_the_unpromoted_facets_are_named_on_the_promotion_record(self):
        self._investigation()
        result = create_project_from_investigation(
            self.store, self.workspace, investigation_ref=self.ref,
            new_project_id="proj-promoted", title="Promoted Study", actor="reviewer")

        left = {f["facet_key"]: f["routing"] for f in result["promotion"]["unpromoted_facets"]}
        self.assertEqual(left, {"Parking ratio": FACET_DEFERRED,
                                "Noise study": FACET_DECLINED})

    def test_the_source_investigation_is_untouched(self):
        self._investigation()
        before = [dict(r) for r in self.workspace.facet_routings]
        create_project_from_investigation(
            self.store, self.workspace, investigation_ref=self.ref,
            new_project_id="proj-promoted", title="Promoted Study", actor="reviewer")
        self.assertEqual(self.workspace.facet_routings, before)

    def test_both_sides_record_the_crossing(self):
        """Invariant #9: deliberate and attributed, on both sides."""
        self._investigation()
        create_project_from_investigation(
            self.store, self.workspace, investigation_ref=self.ref,
            new_project_id="proj-promoted", title="Promoted Study", actor="reviewer")

        source = self.store.get("proj-facets")
        target = self.store.get("proj-promoted")
        self.assertEqual(len(source.investigation_promotions), 1)
        self.assertEqual(len(target.investigation_promotions), 1)
        self.assertEqual(source.investigation_promotions[0]["id"],
                         target.investigation_promotions[0]["id"])
        self.assertEqual(source.investigation_promotions[0]["promoted_by"], "reviewer")

    def test_promotion_refuses_when_no_facet_is_active(self):
        self._route("Parking ratio", FACET_DEFERRED)
        with self.assertRaises(CaseWorkspaceError) as caught:
            create_project_from_investigation(
                self.store, self.workspace, investigation_ref=self.ref,
                new_project_id="proj-none", title="No", actor="reviewer")
        self.assertIn("does not decide one", str(caught.exception))

    def test_promotion_refuses_to_overwrite_an_existing_project(self):
        self._investigation()
        self.store.get_or_create("proj-taken")
        with self.assertRaises(CaseWorkspaceError):
            create_project_from_investigation(
                self.store, self.workspace, investigation_ref=self.ref,
                new_project_id="proj-taken", title="Taken", actor="reviewer")


class FacetReportsUseTheExistingExportPath(_Fixture):
    def test_a_facet_report_is_an_ExportDocument(self):
        from services.document_export import ExportDocument, build

        self._route("Height limit", FACET_ACTIVE, "Governs the massing")
        self._route("Parking ratio", FACET_DEFERRED)

        document = facet_export_document(self.workspace, self.ref, "Height limit")
        self.assertIsInstance(document, ExportDocument)
        # And the real writers accept it, in all three formats.
        for fmt in ("docx", "xlsx", "pdf"):
            self.assertTrue(build(document, fmt).getvalue())

    def test_a_single_facet_report_still_names_what_it_left_out(self):
        self._route("Height limit", FACET_ACTIVE)
        self._route("Parking ratio", FACET_DEFERRED)
        self._route("Noise study", FACET_DECLINED)

        document = facet_export_document(self.workspace, self.ref, "Height limit")
        excluded = next(t for t in document.tables
                        if t.title == "Not covered by this report")
        self.assertEqual({row[0] for row in excluded.rows},
                         {"Parking ratio", "Noise study"})

    def test_the_report_says_routing_is_not_validation(self):
        self._route("Height limit", FACET_ACTIVE)
        document = facet_export_document(self.workspace, self.ref)
        self.assertTrue(any("not a validation" in line for line in document.preamble))

    def test_routing_changes_appear_as_their_own_table(self):
        self._route("Height limit", FACET_ACTIVE, "Governs the massing")
        self._route("Height limit", FACET_RESOLVED, "Confirmed against by-law")
        document = facet_export_document(self.workspace, self.ref, "Height limit")
        changes = next(t for t in document.tables if t.title == "Routing changes")
        self.assertEqual([row[1] for row in changes.rows], [FACET_RESOLVED])

    def test_an_unrouted_facet_cannot_be_reported_on(self):
        with self.assertRaises(CaseWorkspaceError):
            facet_export_document(self.workspace, self.ref, "never-routed")


if __name__ == "__main__":
    unittest.main()
