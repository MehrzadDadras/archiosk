"""
CLAUDE-POSTCAMEL-ROOT-I2 - Requirements 3.3 Compliance rollup.

A pure projection over the SAME requirement_adjudication_state values
ROOT-I1's own "Governed Requirements" list already computed and
rendered per-item - no new canonical status field, no second
compliance record. Two counts are kept deliberately separate on every
page render: "N awaiting review" (REQUIREMENT_ADJUDICATION_STATE_
NOT_YET_ASSESSED - no RequirementAdjudication on file yet) must never
be folded into "N need attention" (Not Satisfied/Partially Satisfied -
an adverse/uncertain human determination). Each links via a real
`?status=` query parameter into the existing "Governed Requirements"
list (server-side filtered, no new JS) - drill-through reaches the
same canonical Requirement markup ROOT-I1 already tested, never a
duplicate.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.case_workspace import REQUIREMENT_REGISTRATION_HUMAN_REGISTERED, CaseWorkspaceStore
from services.requirements_registry import RequirementsRegistry


class ComplianceRollupTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_root_i2_compliance_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-root-i2-compliance"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.pdf", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.store = CaseWorkspaceStore(self.tmp_dir)

        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"

        # Registers the auto Source (#1) for rfp.pdf via get_or_create.
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _fresh_workspace(self):
        return self.store.get(self.project_id)

    def _add_source(self, name):
        workspace = self._fresh_workspace()
        source_id = f"source-{name}"
        workspace.sources.append({
            "id": source_id, "project_id": self.project_id, "kind": "rfq_rfp_document",
            "name": name, "added_at": "2026-01-01T00:00:00+00:00", "file_path": None,
        })
        self.store.save(workspace)
        return source_id

    def _register(self, source_id, identifier, text):
        response = self.client.post(
            f"/projects/{self.project_id}/workspace/requirements/register",
            data={"source_id": source_id, "original_requirement_identifier": identifier, "text_reference": text},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        return next(
            r for r in self._fresh_workspace().requirements
            if r["original_requirement_identifier"] == identifier and r["source_id"] == source_id
        )

    def _adjudicate(self, requirement_id, outcome, reasoning="Reviewed."):
        response = self.client.post(
            f"/projects/{self.project_id}/workspace/requirements/{requirement_id}/adjudicate",
            # CLAUDE-POSTCAMEL-COMM-I5A: attribution is now a mandatory,
            # never-defaulted explicit choice at this route.
            data={"outcome": outcome, "reasoning": reasoning, "case_id": "", "attribution": "human_reviewed"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

    def _requirements_page(self, **query):
        return self.client.get(
            f"/projects/{self.project_id}/workspace",
            query_string={"view": "requirements", **query},
        ).get_data(as_text=True)

    # 1 & 10 -------------------------------------------------------------

    def test_compliance_section_absent_on_a_sparse_project(self):
        body = self._requirements_page()
        self.assertNotIn('data-ui-ref="display.requirements.compliance"', body)
        self.assertIn("No Requirements have been confirmed as governed yet.", body)

    def test_compliance_section_present_once_a_requirement_is_governed(self):
        source_id = self._add_source("rfp.pdf")
        self._register(source_id, "3.1", "Contractor shall provide as-built drawings.")
        body = self._requirements_page()
        self.assertIn('data-ui-ref="display.requirements.compliance"', body)
        self.assertIn(">Compliance<", body)

    # 2 & 3 ---------------------------------------------------------------

    def test_awaiting_review_count_is_correct_before_any_adjudication(self):
        source_id = self._add_source("rfp.pdf")
        self._register(source_id, "3.1", "Contractor shall provide as-built drawings.")
        self._register(source_id, "4.2", "Contractor shall provide a commissioning report.")
        body = self._requirements_page()
        self.assertIn("2 awaiting review", body)
        self.assertIn("2 governed Requirement(s)", body)

    # 5 ---------------------------------------------------------------

    def test_unreviewed_is_never_described_as_needing_attention(self):
        source_id = self._add_source("rfp.pdf")
        self._register(source_id, "3.1", "Contractor shall provide as-built drawings.")
        body = self._requirements_page()
        self.assertIn("not a finding of non-compliance", body)
        self.assertNotIn("need attention", body)

    # 4 & 6 ---------------------------------------------------------------

    def test_mixed_status_rollup_separates_attention_from_awaiting_review(self):
        source_id = self._add_source("rfp.pdf")
        satisfied = self._register(source_id, "3.1", "Contractor shall provide as-built drawings.")
        not_satisfied = self._register(source_id, "4.2", "Contractor shall provide a commissioning report.")
        self._register(source_id, "5.1", "Contractor shall provide warranty documentation.")
        self._adjudicate(satisfied["id"], "Satisfied")
        self._adjudicate(not_satisfied["id"], "Not Satisfied")

        body = self._requirements_page()
        self.assertIn("1 Requirement(s) need attention", body)
        self.assertIn("1 awaiting review", body)
        self.assertIn("3 governed Requirement(s)", body)

    def test_partially_satisfied_also_counts_as_needing_attention(self):
        source_id = self._add_source("rfp.pdf")
        req = self._register(source_id, "6.1", "Contractor shall commission all systems.")
        self._adjudicate(req["id"], "Partially Satisfied")
        body = self._requirements_page()
        self.assertIn("1 Requirement(s) need attention", body)

    def test_not_applicable_and_accepted_alternative_are_settled_not_attention(self):
        source_id = self._add_source("rfp.pdf")
        na = self._register(source_id, "7.1", "Contractor shall provide a demolition permit.")
        alt = self._register(source_id, "7.2", "Contractor shall use the specified paint system.")
        self._adjudicate(na["id"], "Not Applicable")
        self._adjudicate(alt["id"], "Accepted Alternative")
        body = self._requirements_page()
        self.assertNotIn("need attention", body)
        self.assertNotIn("awaiting review", body)

    # 9 (source awareness) -------------------------------------------------

    def test_attention_breakdown_names_the_contributing_sources(self):
        source_a = self._add_source("rfp.pdf")
        source_b = self._add_source("addendum-1.pdf")
        req_a = self._register(source_a, "3.1", "Contractor shall provide as-built drawings.")
        req_b = self._register(source_b, "ADD-1-2", "Contractor shall extend the warranty period.")
        self._adjudicate(req_a["id"], "Not Satisfied")
        self._adjudicate(req_b["id"], "Not Satisfied")
        body = self._requirements_page()
        self.assertIn("rfp.pdf (1)", body)
        self.assertIn("addendum-1.pdf (1)", body)

    # 7 (drill-through) -----------------------------------------------------

    def test_drill_through_filters_to_only_the_matching_requirements(self):
        source_id = self._add_source("rfp.pdf")
        satisfied = self._register(source_id, "3.1", "Contractor shall provide as-built drawings.")
        not_satisfied = self._register(source_id, "4.2", "Contractor shall provide a commissioning report.")
        self._adjudicate(satisfied["id"], "Satisfied")
        self._adjudicate(not_satisfied["id"], "Not Satisfied")

        body = self._requirements_page(status="Not Satisfied")
        self.assertIn(f'id="requirement-{not_satisfied["id"]}"', body)
        self.assertNotIn(f'id="requirement-{satisfied["id"]}"', body)
        self.assertIn("Governed Requirements (1)", body)
        self.assertIn("Showing only", body)
        self.assertIn("Clear filter", body)

    def test_no_filter_still_shows_every_governed_requirement(self):
        source_id = self._add_source("rfp.pdf")
        satisfied = self._register(source_id, "3.1", "Contractor shall provide as-built drawings.")
        not_satisfied = self._register(source_id, "4.2", "Contractor shall provide a commissioning report.")
        self._adjudicate(satisfied["id"], "Satisfied")
        self._adjudicate(not_satisfied["id"], "Not Satisfied")

        body = self._requirements_page()
        self.assertIn(f'id="requirement-{not_satisfied["id"]}"', body)
        self.assertIn(f'id="requirement-{satisfied["id"]}"', body)
        self.assertIn("Governed Requirements (2)", body)
        self.assertNotIn("Showing only", body)

    # 8 --------------------------------------------------------------------

    def test_viewing_the_compliance_rollup_creates_no_duplicate_requirement(self):
        source_id = self._add_source("rfp.pdf")
        self._register(source_id, "3.1", "Contractor shall provide as-built drawings.")
        before = len(self._fresh_workspace().requirements)
        self._requirements_page()
        self._requirements_page(status="Not Yet Assessed")
        after = len(self._fresh_workspace().requirements)
        self.assertEqual(before, after)

    # 11 & 12 ----------------------------------------------------------------

    def test_existing_governed_requirements_anchor_still_present(self):
        source_id = self._add_source("rfp.pdf")
        self._register(source_id, "3.1", "Contractor shall provide as-built drawings.")
        body = self._requirements_page()
        self.assertIn('id="governed-requirements"', body)

    def test_per_requirement_adjudication_still_works_alongside_the_rollup(self):
        source_id = self._add_source("rfp.pdf")
        requirement = self._register(source_id, "3.1", "Contractor shall provide as-built drawings.")
        response = self.client.post(
            f"/projects/{self.project_id}/workspace/requirements/{requirement['id']}/adjudicate",
            data={
                "outcome": "Satisfied", "reasoning": "As-built set received.", "case_id": "",
                "attribution": "human_reviewed",
            },
        )
        self.assertIn(response.status_code, (200, 302))
        adjudications = self.store.requirement_adjudications_for(self._fresh_workspace(), requirement["id"])
        self.assertEqual(len(adjudications), 1)
        self.assertEqual(adjudications[0]["outcome"], "Satisfied")

    # 13 ----------------------------------------------------------------------

    def test_rollup_updates_when_the_canonical_requirement_is_adjudicated(self):
        source_id = self._add_source("rfp.pdf")
        requirement = self._register(source_id, "3.1", "Contractor shall provide as-built drawings.")

        before = self._requirements_page()
        self.assertIn("1 awaiting review", before)
        self.assertNotIn("need attention", before)

        self._adjudicate(requirement["id"], "Not Satisfied")

        after = self._requirements_page()
        self.assertNotIn("awaiting review", after)
        self.assertIn("1 Requirement(s) need attention", after)

    # 9 (project isolation) ----------------------------------------------------

    def test_compliance_rollup_is_strictly_project_scoped(self):
        other_project_id = "test-project-root-i2-compliance-other"
        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=other_project_id, filename="other.pdf", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client.get(f"/projects/{other_project_id}/workspace?view=overview")
        other_workspace = self.store.get(other_project_id)
        other_workspace.sources.append({
            "id": "other-source", "project_id": other_project_id, "kind": "rfq_rfp_document",
            "name": "other.pdf", "added_at": "2026-01-01T00:00:00+00:00", "file_path": None,
        })
        self.store.save(other_workspace)
        other_requirement = self.store.register_requirement(
            other_workspace, source_id="other-source", original_requirement_identifier="9.1",
            text_reference="Contractor shall provide a different deliverable.",
            created_by="owner2", registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )
        self.store.record_requirement_adjudication(
            self.store.get(other_project_id), requirement_id=other_requirement["id"],
            outcome="Not Satisfied", adjudicator="owner2", reasoning="Cross-project isolation check.",
        )

        source_id = self._add_source("rfp.pdf")
        self._register(source_id, "3.1", "Contractor shall provide as-built drawings.")

        body = self._requirements_page()
        self.assertIn("1 awaiting review", body)
        self.assertNotIn("need attention", body)
        self.assertNotIn("a different deliverable", body)


if __name__ == "__main__":
    unittest.main()
