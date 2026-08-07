# Independent Expert Pilot Readiness (CLAUDE-POSTCAMEL-P01)

**Status:** Assessment complete. This is the first post-Camel programme,
authorized following the accepted Camel MM1–MM9 close-out (`d7df9a3`). It
is explicitly **not** a capability-build stage — its objective was to
determine, through live evidence rather than assumption, whether ARCHIOSK
is ready to be placed in front of a real independent Design Manager or
pursuit/preconstruction professional without the founder present.

This document is the canonical record of that assessment: what was
tested, what was found, what was fixed, what remains open, and the
resulting Go/No-Go recommendation. It does not restate the Camel record
(`camel-multimodal-programme.md`, `current/kernel-object-model.md`) —
only what this stage's own audit added or changed.

---

## 1. Method

A repository-grounded audit (templates, routes, flash messages, JS) was
performed first, from the stated posture of "I have been given this
application. What do I do?" — followed by three live-browser Zero-Founder
walkthroughs against a freshly restarted dev server, using a throwaway
`pilot_audit` admin account and two throwaway projects, both fully,
permanently removed at close-out:

- **Scenario A (procurement):** a real, hand-built minimal RFP PDF
  ("Riverside Pump Station Upgrade") — ingest → MM9 registration →
  investigation Q&A → abstention → Project Briefing.
- **Scenario B (Design Manager):** a real openpyxl-written risk-register
  workbook and a real PNG drawing added to a project seeded from a
  **coordination report**, not a procurement document — investigation →
  drawing analysis → machine Findings → human Reviewer Validation → a
  governed `risk_register`-shaped Work Product with a real Risk section.
- **Scenario C (non-RFP start):** satisfied by the same project as
  Scenario B — "Mechanical Coordination Review" was created from a
  Coordination Report PDF, never framed as procurement, proving project
  creation and the whole downstream product make sense starting from
  non-RFP material.

A separate "Elephant Test" / clear-eyes pass then re-examined the same
evidence from the perspective of an intelligent outsider with minimal
construction-domain assumptions, asking the nine hierarchy/state
questions in Section 6 below, and specifically looking for cases where a
professional's own domain fluency was silently compensating for an
unclear product hierarchy — the outsider is not meant to complete
professional construction work, only to answer whether the application's
state, evidence boundaries, and next actions are self-evident.

---

## 2. Fixes made this stage

All four are bounded, reversible, and either purely cosmetic (wording)
or pure front-end (template/JS) — no domain-model, route, or schema
change; no new dependency.

1. **Founder/prototype language leak** (`routes/workspace.py`,
   `add_drawing_source`): the unsupported-drawing-format error literally
   read *"Use PNG or JPG for this prototype."* — inappropriate for a
   paying pilot user to see. Changed to *"Use PNG or JPG for a drawing
   Source."* A repository-wide grep confirmed this was the only instance
   of `prototype`/similar developer-facing language reaching user-visible
   flash/error text; every `CLAUDE-P40-*`/`MM*`/`VW*` stage-codename
   reference elsewhere is inside a Jinja/JS comment block, never rendered.

2. **MM9 registration-panel discoverability** (`templates/case_workspace.html`):
   the "Register this document"/"Register this workbook" control MM9
   added was positioned *after* the fully-rendered document — on
   anything longer than one page, entirely below the fold. A first-time
   user had to scroll past the whole document to discover the one
   control that makes it usable evidence. Moved directly under the
   document title, matching the mature document-tool convention (Acrobat/
   Bluebeam show a needs-attention status banner under the toolbar,
   never after the content) — same element, same behavior, just visible
   without scrolling.

3. **Work Product "Add a section" — silent field-group mismatch**
   (`templates/case_workspace.html`, `static/js/case_workspace.js`):
   every field from every section type (risk description/probability/
   impact/mitigation/owner, team_member name/role/company/contact, and a
   narrative text box) was rendered simultaneously with no indication
   that only the group matching the selected "section_type" dropdown is
   actually persisted (`routes/workspace.py`'s own
   `_WORK_PRODUCT_SECTION_FIELDS`). A reviewer filling in risk fields
   while "Narrative" (the default) was still selected had that entire
   input silently discarded on save — reproduced live during Scenario B.
   Fixed with **progressive enhancement**: fields stay unconditionally
   present in the DOM (the form's own existing, deliberate "works with
   JavaScript disabled" guarantee — see that form's own template comment
   — is unchanged), and a small script hides the non-matching groups when
   JavaScript is available, which is the common case. Live-verified:
   selecting "Risk" now shows exactly the risk fields; the submitted
   section correctly persisted real description/probability/impact/
   mitigation/owner values.

4. **Work Product "Edit this section" — identical problem, fixed more
   simply:** since an existing section's own type is already fixed and
   known server-side, this needed no JS at all — a pure Jinja conditional
   now renders only the fields `section.section_type` actually owns.
   Covered by a new regression test (`tests/test_mm8_work_products.py::
   test_edit_section_form_only_renders_its_own_section_type_fields`).

`STATIC_VERSION` bumped to 62 for the template/JS changes, per this
repository's own `.env`/`config.py` discipline.

---

## 3. Real findings, documented but deliberately not built this stage

These are genuine, live-verified gaps or limitations. None were fixed,
because each would require new capability (new UI surface, new route
wiring, or a cross-tenancy redesign) beyond "wording/discoverability" —
exactly the class of change this stage's own governing instructions
reserve for a fast-follow or a separate future programme, not a hardening
audit.

- **The MM7 formal Claim/"Investigate" trust engine (confidence
  percentage, contradiction detection, human Reviewer Validation gate)
  is wired only to drawing/image Sources** (`static/js/
  drawing_image_viewer.js`) — there is no equivalent trigger for PDF or
  spreadsheet evidence. A PDF/spreadsheet-based investigation instead
  gets a real, working, honestly-labeled grounded Q&A
  (`services/project_qa.py`) with inline "Source grounding" citations —
  functionally answering "what evidence supports this" for the pilot's
  practical needs, but it does **not** produce a formal `Claim`/Finding
  object or feed the "Apply Confirmed Findings" mechanism the
  Investigations panel otherwise centers on. This is the single clearest
  Elephant-Test finding of this stage — see Section 6.
- **MM3's bounded single-cell spreadsheet edit
  (`apply_bounded_cell_edit`, `POST .../spreadsheet-cell`) has zero UI
  trigger anywhere in the app** — the same "real, tested, invisible"
  shape MM9 closed for registration, but MM9's own authorized scope
  covered registration only. Not a hard blocker: the actual governed
  Design-Manager risk-register path this pilot needs is the MM8
  `WorkProduct` (`risk_register` artifact type), fully built and
  live-verified this stage (Section 1), not raw spreadsheet cell editing.
- **Project creation remains restricted to PDF/DOCX/TXT/CSV/MD** —
  drawings, images, and native spreadsheets can only be *added to* an
  already-created project, never used to start one. This is a
  pre-existing, deliberate MM1–MM5 architecture decision, already
  honestly disclosed in the upload page's own copy ("Scanned drawing
  packages, native spreadsheets, and images are not yet supported").
  Not a defect and not changed — Scenario C's actual requirement (a
  non-RFP-framed *text* start) is fully satisfied by the existing
  report/spec/contract/meeting-minutes wording.
- **Requirements extraction produced zero Requirements for the synthetic
  single-clause test PDF used in Scenario A.** This is most likely a
  property of the minimal test fixture (one short clause, no clearly
  itemized requirements list for `BHiveParser` to extract with
  confidence) rather than a defect — flagged for re-verification with a
  real, requirements-rich RFP during the actual pilot, not claimed as
  broken.
- **`ConcurrentModificationError`'s message** ("expected version N,
  found M on disk") is mildly internal-versioning language reaching the
  user. Low severity, low likelihood (requires two concurrent edits to
  the same project) — still explains what happened and what to do
  ("reload and retry"). Classified cosmetic/fast-follow, not fixed.
- **Error messages generally embed raw internal object ids** (e.g.
  `"Source {source_id} was not found."`) — grammatically fine, but the
  UUID adds nothing for a professional user. Cosmetic/fast-follow.
- **Admin accounts see every project on the deployment, not only their
  own** — an already-documented, deliberate `CLAUDE-P32` boundary
  ("project-level access control within one deployment, not
  multi-organization tenancy"), not something this stage changed. Real
  pilot-operational consequence: **do not grant the pilot user an admin
  account on a server that also hosts other real client projects** —
  either use a clean, isolated pilot deployment, or accept that an
  upload-capable pilot account can browse every other project on that
  same server. This is an operational/deployment decision for whoever
  runs the pilot, not a code defect.

---

## 4. What worked well (verified, not assumed)

- Sign-in error handling ("Invalid username or password.") is clean,
  gives away nothing about which field was wrong, and uses no internal
  language.
- The project-creation page's own copy already lists RFPs/RFQs/specs/
  contracts/reports/meeting minutes — it never implied procurement-only
  scope, before or after this stage.
- The Project Operating Environment choice explicitly warns of its own
  irreversibility before the user commits to it.
- **Project Briefing** (a real Anthropic-model call, not a stub) produces
  an honestly-labeled executive summary, objectives, and "Matters
  Requiring Early Attention" list, each grounded in extracted evidence,
  explicitly marked *"Machine-assisted observations — not confirmed
  until governed through Findings and Adjudication"* and stamped with
  model name, timestamp, and generating user — a genuinely strong,
  live-verified instance of the fact/AI-suggestion boundary doctrine.
- Grounded conversational Q&A shows exact quoted "Source grounding"
  citations inline, and honestly abstains when the evidence doesn't
  cover the question ("This evidence alone isn't enough to answer fully
  - treat this as a starting point, not a complete answer") — exactly
  the "protecting me from a weak conclusion" framing this stage's own
  abstention-UX test asked for, not "the AI is broken."
- The drawing-based Investigation → machine Finding
  (`CONFIDENCE 55%` / `UNVERIFIED`) → human **Reviewer Validation**
  (Correct/Incorrect/Partial/Needs Evidence/Not Applicable + Add
  Correction) chain is real, complete, and live-verified end to end —
  a full, honest AI-proposal-to-human-adoption pipeline.
- Work Products (`report`/`risk_register`/`team_list`) provide a genuine
  create → section → review → approve → issue → export pipeline; real
  DOCX/XLSX downloads were confirmed live in prior Camel-stage testing
  and the section-creation path was re-verified this stage.
- Tab strip, breadcrumb, and "← Back to Overview" links closely mirror
  familiar browser-tab/IDE conventions — no special domain knowledge was
  needed to navigate back to a previous state at any point in any
  scenario.

---

## 5. Zero-Founder scenario notes

**Scenario A (procurement).** No point of confusion in sign-in, project
creation, or document opening. The MM9 registration link was undiscoverable
before this stage's fix (Section 2.2). The Investigation's own "Analyze…"
trigger does not work for a plain PDF ("There's no drawing Source attached
to this Case yet."); the Project Briefing's automatic "Matters Requiring
Early Attention" list substantially covers the same underlying need
one level up, but the connection between the two is not obvious from the
UI alone.

**Scenario B (Design Manager).** Drawing analysis, machine Findings, human
review, and risk-register Work Product creation all worked end to end.
The Work Product section-field bug (Section 2.3–2.4) was found and fixed
here — before the fix, a first attempt at recording the risk genuinely lost
the data with a "success" message and no warning.

**Scenario C (non-RFP start).** No blocker. Creating a project from a
Coordination Report, then adding a spreadsheet and drawing to it, worked
identically to the procurement path — nothing in the product assumed or
required an RFP origin.

---

## 6. Elephant Test — clear-eyes hierarchy audit

Answered from the audit evidence gathered above, not additional testing:

| Question | Verdict | Evidence |
|---|---|---|
| What is the project? | Clear | Name in top breadcrumb, sidebar header, and an explicit "PROJECT OPERATING ENVIRONMENT" badge on Overview. |
| What is the active document/artifact? | Clear | Bold tab in the tab strip, breadcrumb segment, "FOCUSED" badge on the active Investigation tab. |
| What is selected? | Clear | Highlighted row in the Documents/Investigations sidebar list. |
| What belongs under what? | Mostly clear, one real gap | Documents/Investigations/RFIs/Work Products/Chats/Tasks/Tags sit as flat sibling branches with count badges — easy to scan. **Requirements are the exception**: they live only inside Overview's "Requirement Compliance" disclosure, never as a sibling branch, so whether a Requirement is a first-class object (like a Document) or a subordinate concept is genuinely ambiguous from the UI alone. |
| What came from source evidence vs. an interpretation/proposal? | Strong | Repeatedly and explicitly labeled: "Source grounding," "MACHINE FINDING · CONFIDENCE 55% · UNVERIFIED," "Machine-assisted observations — not confirmed until governed through Findings and Adjudication," model/timestamp/author stamps. One of the product's clearest strengths. |
| What is saved vs. unsaved? | Fixed this stage | Architecturally strong in general (classic form-POST + redirect, no client-side draft state to desync) — but the Work-Product section bug (Section 2.3) was exactly the dangerous inverse case: a *successful-looking* save that silently kept the wrong (empty) data. Now fixed. |
| What can I do next? | Mostly clear | Inline "+"/action links are generally discoverable. The MM9 registration link (fixed) and the drawing-only "Analyze…" trigger (documented, not fixed) were the two real exceptions found. |
| How do I return to source/previous state? | Strong | Tab-close (×), breadcrumb, and "← Back to Overview" all present and behave like familiar browser/IDE patterns in every scenario tested. |

**The one case where expert domain fluency was compensating for a real
hierarchy gap** (the stronger warning this audit was specifically asked
to surface): a Design Manager reviewing a **drawing** succeeds fluently at
Investigation → Finding, because the UI itself grows a helpful example
prompt ("Analyze this drawing for datum inconsistencies…") the instant a
drawing is attached — their own professional instinct ("I should analyze
this drawing for clashes") happens to land exactly on the phrasing the
product needs. A user working from a **procurement PDF or spreadsheet**
gets no equivalent prompt, no discoverable trigger phrase, and would
reasonably conclude the Investigation feature "doesn't do anything" for
their document — even though an equivalent capability (Project Briefing's
automatic risk/ambiguity flagging) genuinely exists one level up. The
expert's fluency with drawings, not the product's own hierarchy, is what
makes that specific path legible.

**Universal vs. role-specific.** Project identity, selection state,
evidence/interpretation labeling, and the save/navigation model above are
all universal — they must stay identical regardless of who is looking at
them. Panel arrangement, which Lists branches are pinned open by default,
Display Layout division counts, and Appearance theme are already
role-agnostic *preferences*, not hierarchy — a legitimate seam for future
per-role emphasis (Section 7).

---

## 7. Future workspace-template extension point (not built)

ARCHIOSK already cleanly separates **Display Layout** (multi-division
arrangement) and **Appearance** (theme) as their own top-bar controls,
explicitly documented in `templates/base.html`'s own comments as
device/browser-level preferences — never project state, never session
state, and never part of the governed domain model
(`CaseWorkspaceStore`/`ProjectWorkspace`). This is already the correct
seam for a future named, saveable workspace template (Design Manager /
Estimating / Field / Structural Review / Executive / Investigation
Review / user-defined): such a template could be nothing more than a
named bundle of {Display Layout arrangement, Appearance theme, which
Lists branches are pinned/expanded by default} — none of which touch
evidence identity, provenance, project isolation, authority, security,
approval rules, or issued-history integrity, all of which live entirely
inside the domain model this preference layer never reaches today.

**Not implemented this stage**, per this stage's own explicit
instruction — reported as a safe, real, already-present extension point
only.

---

## 8. Tests

One focused regression test added:
`tests/test_mm8_work_products.py::WorkProductRouteTests::
test_edit_section_form_only_renders_its_own_section_type_fields` —
proves a risk section's own edit form renders risk fields (with real
saved values) and never a team_member-only field name, and vice versa.
No other new tests — the remaining three fixes are either pure wording
(no logic to test) or pure CSS/HTML repositioning (no behavior change to
assert beyond what a human/live-browser check already confirmed).

## 9. Full-suite result

One controlled full-suite run after all fixes and the new regression
test landed, with the dev-server process chain and any prior background
test runs stopped first: **2,889 passed, 0 failed, 65 subtests passed**
in 2204.60s (36m44s) — exactly one more than the Camel MM9 close-out's
own last confirmed count (2,888), matching the one new test added this
stage. Zero regressions. (Wall-clock duration varied well beyond this
repository's usual ~3–4 minutes, consistent with `CLAUDE.md`'s own
documented caveat that duration has occasionally spiked for reasons
unrelated to any specific code change — pass/fail is the signal, not
wall-clock time.)

---

## 10. Pilot Readiness Matrix

| Task | Result | Evidence | Pilot impact |
|---|---|---|---|
| Sign-in | PASS | Clean error message, no jargon, no stale-session confusion when starting fresh. | None. |
| Project creation | PASS | Copy already lists RFP/RFQ/spec/contract/report/meeting-minutes; environment choice warns of irreversibility. | None. |
| Non-RFP project start | PASS | "Mechanical Coordination Review" created from a Coordination Report; whole product remained coherent. | None. |
| Project open / reopen | PASS | Every project reopened correctly across navigation and fresh page loads in all three scenarios. | None. |
| Documents / Files navigation | PASS | Flat, count-badged sibling branches; easy to scan. | None. |
| PDF workflow | PASS | Real PDF.js rendering, page nav, zoom, search all functional. | None. |
| Spreadsheet workflow | CONDITIONAL PASS | Opens and registers for citation; no in-app grid view or cell-edit UI exists (deliberate MM3 scope, still true) — bounded edit only reachable via direct API. | Design Manager must use the WorkProduct risk-register path for in-app editing, not raw spreadsheet cells. |
| Drawing workflow | PASS | Zoom/pan/rotate/mirror/reset/region/citation and independent comparison all real (verified in Camel-stage testing, re-confirmed via the Investigation flow this stage). | None. |
| Image/Eye workflow | NOT CLAIMED | Not re-tested live this stage (no file-input target for the paste/drop-only Eye pane under browser automation); no new evidence gathered. | Should be spot-checked once by a human before the pilot, not assumed from this report alone. |
| Evidence registration (MM9) | PASS (after fix) | Discoverability fixed this stage; both PDF and XLSX registration produce correct citable counts, confirmed persistent across reload. | None remaining. |
| Investigation / trustworthy answer | CONDITIONAL PASS | Excellent for drawings (formal Claim/confidence/review engine); PDFs/spreadsheets get a real but simpler grounded-Q&A path instead, with no formal Finding produced. | Real, documented gap — see Section 3. Fast-follow, not a blocker (the practical need is still met). |
| Abstention UX | PASS | Live-verified: "not covered by this project's extracted evidence... treat this as a starting point, not a complete answer." | None. |
| Relationship / "this supports/contradicts that" | NOT CLAIMED | Not re-exercised live this stage; covered by existing MM6 test suite and prior Camel-stage live verification, not repeated here. | Low risk — already proven capability, simply outside this stage's own walkthroughs. |
| Finding / DerivedObservation terminology | PASS | Both terms appear in context with enough surrounding language (MACHINE FINDING / CONFIDENCE / UNVERIFIED) that the distinction did not block comprehension during live use. | None material. |
| Work Product creation/edit/review | PASS (after fix) | Real risk section created, saved, and displayed correctly after this stage's field-scoping fix; review/approve/issue/export chain proven in prior Camel-stage testing. | None remaining. |
| Save / unsaved state | PASS (after fix) | The one real failure mode found (silent field-group data loss) is fixed and regression-tested. | None remaining. |
| Export / reopen | PASS | DOCX/XLSX export proven in prior Camel-stage testing; not repeated live this stage beyond section-save verification. | None. |
| Revision (WorkProduct) | NOT CLAIMED | Not re-exercised live this stage; proven in MM8's own testing, not repeated here. | Low risk — already-proven capability. |
| Project switch | NOT CLAIMED | Not directly exercised as an isolated test this stage (each scenario used its own project); no evidence of cross-project state confusion was observed incidentally. | Should be spot-checked once before the pilot. |
| Restart / recovery | PASS | The dev server was restarted mid-session (for the `STATIC_VERSION` bump) and every project/document/investigation reopened correctly afterward with no special procedure. | None. |
| Issue reporting / trust-challenge flow | PASS | The Reviewer Validation gate (Correct/Incorrect/Partial/Needs Evidence/Not Applicable + "Add Correction…") is a real, working way to flag "I don't trust this," preserving the challenged claim, source, and reviewer note. | None. |

---

## 11. Blocker classification

**A. Must fix before independent pilot:** none identified. Every genuine
defect found this stage was fixed within the stage itself.

**B. Pilot fast-follow (safe to learn/refine during the pilot):**
- Wire a discoverable trigger (or at minimum a UI hint) for producing a
  formal Finding from PDF/spreadsheet evidence, or explicitly document
  for the pilot user that "Analyze…" is drawing-specific and the Project
  Briefing is the equivalent for text/structured evidence.
- Give Requirements their own sidebar branch (or clearly subordinate
  label) so "what belongs under what" is unambiguous.
- Consider a minimal UI trigger for the bounded single-cell spreadsheet
  edit, or explicitly scope the pilot to the WorkProduct risk-register
  path instead.

**C. Post-pilot product enhancement:**
- Strip raw internal object ids from user-facing error text.
- Rephrase `ConcurrentModificationError`'s versioning language.
- Saved workspace/layout templates (Section 7).

**D. Separate future programmes (explicitly not begun here):** Monte
Carlo/quantitative risk engine, External Intelligence Airlock, Navisworks/
model coordination, drone/micro-drone field-reality stream, Learning
Vessel/public-learning branch, remaining cockpit/product-polish work.

---

## 12. Pilot safety and data notes

- **Local vs. external:** project data, documents, and the flat-JSON
  registry are stored locally. Project Briefing and conversational Q&A
  make a real call to the configured Anthropic API (a real key was
  active during this session's testing) — evidence text relevant to the
  user's question is sent to that service. No other external service is
  contacted by anything exercised this stage.
- **Recommended pilot dataset:** synthetic or deliberately-selected,
  non-sensitive material — a representative PDF (spec/report/RFP),
  a small risk-register workbook, and one drawing or site photo. Real
  confidential client data is not required for a first independent test
  and was not used in this stage's own verification (all fixtures were
  hand-built or synthetically generated, never real project content).
- **Account/tenancy note:** see Section 3's admin-visibility finding —
  do not give the pilot user an admin account on a deployment that also
  holds other real client projects.

---

## 13. Go / No-Go

**GO — READY FOR INDEPENDENT EXPERT PILOT**, with the fast-follow items
in Section 11.B tracked, not blocking.

- **Intended user:** a Design Manager or pursuit/preconstruction
  professional, construction-document-literate, not a software developer.
- **Supported environment:** desktop browser, one deployment per pilot
  (see the admin-visibility note above); no claim of mobile/narrow-viewport
  support is made.
- **Recommended first pilot project:** a real or representative
  Coordination Report or specification (not an RFP, to directly exercise
  the non-RFP path) plus one drawing and one small risk-register
  workbook — the Scenario B shape, which exercised the most real
  capability end to end.
- **Feedback to collect:** whether the drawing-vs-text Investigation
  asymmetry (Section 3/6) is noticed and how the user reacts to it;
  whether the Project Briefing's "Matters Requiring Early Attention" is
  discovered and trusted; whether the Reviewer Validation gate is used to
  challenge a machine Finding at least once; general first-open
  comprehension of project/evidence/trust state without coaching.
