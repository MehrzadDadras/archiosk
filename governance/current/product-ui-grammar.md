# Product Owner presentation grammar

The current Product Owner directive replaces engine-first presentation with five
page shells and three density modes. This is an extension of existing Flask,
Jinja, CSS and native details/form owners. No evidence or result is recomputed.

## Shells and components

- PUBLIC / EXPLAIN: the existing landing shell and About page; purpose, context,
  capability explanation and the existing calls to action.
- WORK / START: Projects, document desk and GO task entry; objective, one dominant
  action, search and relevant saved work.
- WORK / RESULT: existing attention report, work-plan projection and result cards;
  conclusions and gaps precede supporting evidence and technical disclosures.
- COMPARE / COMPOSE: existing normalized comparison and coverage matrix. Mobile
  cells retain their actual column labels and become stacked records.
- INSPECT: existing source review, kernel mapping, developer tools, evidence,
  provenance and history. Canonical fields and raw traces remain recoverable.

PageHeader reuses `_macros.page_header`. ObjectiveComposer reuses the existing
form/plan protocol. StatusSummary, MetricStrip and Timeline render actual result
fields; ResultCard, ComparisonTable, CoverageMatrix and GapList use existing
report records. EvidenceDrawer, ProvenanceDrawer and TechnicalDrawer use native
`details`. FilterBar, ActionBar and EmptyState retain their existing form owners.
No capability-specific frontend primitive or secondary interpretation engine is
introduced. New presentation must use these shapes before adding a construct.

## Navigation and density

Primary navigation exposes actual available Projects, Review, Compare, Documents
and Search routes. Review and Compare retain admin/Developer Mode boundaries.
Existing File/Edit/View/Document/Tools/Window/Help menus remain inside a deliberate
Tools & settings disclosure, with their original IDs, actions and permissions.
Mobile project trays retain the established drawer/viewport behavior.

WORK and INSPECT change presentation only. An explicit density choice is kept in
the URL, not in project records. Reload retains it without analysis. PUBLIC is
the editorial public shell. Technical detail never becomes evidence or authority.
New sessions default to the accepted Deep Ocean appearance; explicit stored
appearance choices retain existing migration and selection behavior.

`product_ui.css` supplies hierarchy and density through existing semantic colour
tokens. Borders are reserved for interaction, table reading, critical state and
selection. Gold/amber is not a general panel outline. `product_ui.js` manages only
density and table labels, never analysis or evidence state.

## Proof

`tests/test_go_review_workspace.py` exercises task entry through the existing
plan and attention owners, with manual runtime observation disabled. The existing
runtime observer automatically captures planned task-entry requests.
`tools/verify_go_workspace_ui.py` exercises actual browser forms and records
desktop/tablet/mobile, navigation, evidence and technical disclosure, results,
read-only Reload and unchanged source/evidence proof. Production credentials are
never synthesized by the verifier.
