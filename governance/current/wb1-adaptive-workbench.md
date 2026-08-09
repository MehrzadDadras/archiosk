# Adaptive Workbench / Conversational Operational Terminal (CLAUDE-POSTCAMEL-WB1)

**Status: FIRST BOUNDED WORKBENCH INCREMENT ESTABLISHED — LARGER
WORKBENCH GRAMMAR AUDITED AND DESIGNED, NOT IMPLEMENTED — NARROW
TARGETED RECOMMISSIONING REQUIRED.** Authorized following the Product
Owner's own acceptance of META-T01-RC1 as a bounded first establishment,
with the broader Workbench evolution (variable views, Operational
Terminal, projectable surfaces, Aggressive Overflow, Glass Engine,
contextual next actions, delegation, broader Surface Trust) named as
"separately authorized only when explicitly prompted" — this stage is
that authorization. Governing principles, preserved verbatim: **"One
workbench. One primary operational terminal. Many projectable views. No
fixed panel count."** / **"Conversation operates; views project."** /
**"The cockpit is stable. The visible instruments are not."** The prior
"six-panel cockpit" concept is explicitly reclassified here as a
historical exploratory layout, not a constitutional requirement — see
Section C.

---

## A. Verified starting state

`HEAD == origin/main == ae5e11109e907a12e30bcbe94005ba8f93d50ad7`
confirmed directly before this stage began; working tree clean except
the pre-existing untracked `tests/fixtures/nreocrc/_lab_instance_scratch_002/`
fixture.

## B. Existing shell/workbench architecture audit

Read directly, not assumed from prior conversational language:

- `static/css/main.css`'s own `.app-shell` comment names **"5
  independently-themed surfaces (Menu/Lists/Display/Toolbox/Chat)"** —
  not six.
- A real, working panel-hiding mechanism already exists:
  `html.toolbox-hidden .workspace-right-column { display: none; }`.
- Three `localStorage` keys already persist per-project workbench state
  across sessions: `beehive:panel:launcher`, `beehive:panel:toolbox:{project_id}`
  (panel visibility), and `beehive:panel:toolbox-eye:{project_id}` (a
  resizable Toolbox/Eye height split, clamped between `MAX_PCT`/`DEFAULT_PCT`).
- A "Display Layout" `<details>` topbar menu (`id="workspace-layout-menu"`)
  already offers a "Vertical divisions" control for the Display area —
  a real, if narrow, existing view-configuration mechanism.
- The Conversation dock (`macros.conversation_dock`) is, in practice,
  already a persistent, universal operational surface — confirmed both
  by code structure and by the cumulative evidence of every live
  walkthrough performed across this entire commissioning sequence,
  which consistently shows the same bottom "Ask a question, or describe
  what you want to work on…" input across every Display view tested
  (Overview, Requirements, Files, Conversation itself).

## C. Treatment of the six-panel historical concept

**Confirmed by direct grep: the phrase "six-panel" (and close variants
"six panel," "six-region") appears nowhere in this codebase's source or
in `governance/`.** It was purely conversational language used earlier
in this commissioning sequence, never persisted in code, template, or
governance text. `STATUS.md`'s own prior uses of "cockpit" are loose and
generic ("the accepted cockpit gate," "a broad cockpit redesign" as an
explicitly excluded item) — never an assertion of a fixed panel count.
**There is nothing to formally supersede in writing, because nothing in
the durable record ever asserted six as a constitutional number.** The
real, durable architecture is the 5-surface grammar in Section B, which
already supports variable visibility (Toolbox/Eye can each be hidden or
resized) — this stage extends that existing grammar rather than
replacing it.

## D–H. Operational Terminal, tabs/pages, projectable views, variable/collapsible regions, aggressive overflow

**Audited and designed at the conceptual level; not implemented as new
code this stage**, per the same "smallest coherent... supported by the
existing architecture" instruction this stage's own governing prompt
repeats, and the same audit-only precedent META-T01 itself set for its
own six-panel/workbench section:

- **Operational Terminal (D):** the Conversation dock already functions
  as the de facto universal operational surface (Section B); formally
  elevating it to a first-class "primary terminal" concept — with
  operational tabs/pages (E), true view/container splitting (F/G) for
  documents and artifacts, and a Glass Engine step-tracer (Sections
  L/M of the governing prompt) — would each require new client-side
  state machinery this codebase does not yet have. Building any of
  these now, inside the same stage as everything else, would violate
  the explicit "no unrelated expansion" boundary and the repeated
  instruction to implement only the smallest real, bounded change.
- **Aggressive overflow (H):** one real, bounded first pass **was**
  implemented — see Section I.

## I. The one bounded, real implementation this stage

**Target identified by direct audit of the per-Requirement row
rendering in `templates/case_workspace.html`'s Requirements Display
body:** every governed Requirement row (all 34, on every load) already
carries two sibling controls behind collapsed-by-default disclosures —
`"+ Revise (Addendum)"` and `"Perspective"` — using the established
`macros.subdisclosure(...)` mechanism. The **Adjudicate form** (outcome
select, reasoning field, the two COMM-I5A attribution radios, optional
evidence-finding checkboxes, submit button) was the one remaining
always-visible, unconditionally-rendered control block on the same row
— five-plus form elements repeated identically 34 times on first load,
directly matching the Founder Focus Test's complaint about "unnecessary
visual competition" and Section 7/18's "capability does not earn
permanent screen space merely because it exists."

**Change made:** wrapped the existing Adjudicate form in
`{% call macros.subdisclosure('Adjudicate this Requirement') %}...{% endcall %}`
(`templates/case_workspace.html`), reusing the exact mechanism already
proven safe on the same page for its two siblings. No route, no form
field, no store method, no capability changed. The form is collapsed by
default and fully reachable and functional once expanded (live-verified,
Section Q).

## J. Recursive disclosure / Well Test

The Adjudicate form's new subdisclosure sits at the same depth as its
two existing siblings — one level, not a deepened hierarchy. The Well
Test ("if the user can continue expanding indefinitely without a
meaningful stopping point, the UI has failed") is not violated: the
form now converts into a single named decision ("Adjudicate this
Requirement"), consistent with the Requirement row's existing pattern.
No new depth was added anywhere else this stage.

## K. Contextual next-step offerings, delegation, Glass Engine

**Not implemented — audited and explicitly deferred**, per Section 23's
own "no unrelated expansion" list and the repeated "smallest coherent"
instruction. Each of these (Sections 10–13 of the governing prompt)
requires new conversational/state machinery beyond a template change;
building any of them in the same stage as the one bounded, tested,
committed change above would risk exactly the kind of large,
insufficiently-verified surface area this commissioning sequence has
consistently avoided. Recorded as designed-not-built, matching the
precedent META-T01 itself set for its own Section 7.

## L. Perimeter policy / few stable entrances

**Not implemented.** The existing 5-surface grammar (Menu/Lists/Display/Toolbox/Chat,
Section B) already substantially matches the "center = work, edges =
orientation/context/state" perimeter policy in spirit — Lists is the
edge navigation surface, Toolbox/Eye are contextual edge panes, Chat is
the universal terminal. No rail/navigation consolidation was performed
this stage; a full audit against VS Code's precedent (explicitly not
its visual identity) is future work, not begun.

## M. Semantic-integrity findings — continuity, nothing dropped, one new note

All prior findings carried forward unchanged: File/Document/Source
three-way collision; Documents/Files sidebar redundancy; Archive
collision; Trust collision (Surface Trust vs. the real Trustworthy
Answer Contract); Open/Establish (resolved META-T01-RC1). **One new
naming note, not a correction:** the governing prompt's own Section 4
names a future "Technical/Admin Terminal Eye" privileged mode — this is
a **different concept** from the real, existing "Eye" pane (MM5's
image/drawing evidence viewer, confirmed present and unchanged in this
session's own live screenshots). Two things share the word "Eye" and
are not the same; worth naming honestly before either is built or
discussed further, not resolved here.

## N. Latent-regression watch — continuity, one new observation

All prior items carried forward unchanged: `record_relationship`'s
missing cross-project guard; the two near-identical Source-revision
routes; the META-T01 browser-click regression (preserved as
developmental evidence, not re-litigated). **New observation, not a
regression:** the Adjudicate form's new `<details>` disclosure has no
`localStorage`-backed open/closed persistence the way Toolbox/Eye
visibility does (Section B) — collapsing and reopening it does not
survive a page reload. This is consistent with its two pre-existing
siblings ("+ Revise (Addendum)", "Perspective"), which behave
identically and were never flagged as a defect; recorded here only for
completeness, not as a new deficiency.

## O. Founder Focus walkthrough

Live-verified against the real commissioning specimen, starting from
sign-in: on OPR-1.3's Requirement row, the Adjudicate form is now a
single collapsed line ("Adjudicate this Requirement") rather than a
five-element form rendered in full — a direct, visible reduction in
permanent visual competition across all 34 rows, with zero capability
removed (confirmed by expanding it: full outcome/reasoning/attribution
controls present and functional).

## P. Builder usability walkthrough (labeled truthfully — not the outstanding OPR-7.2 test)

Performed by this Builder, simulating review of the commissioning
specimen: signed in as `archiosk_commissioning`, navigated to
`?view=requirements`, expanded "Governed Requirements (34)", located
OPR-1.3 and OPR-1.4 rows, confirmed the "Adjudicate this Requirement"
disclosure renders collapsed, expanded it, confirmed the full form
(including the pre-existing COMM-I5A attribution radios and OPR-1.4's
own honestly-badged `AGENT ASSESSMENT` history line) is present and
reachable. This is a Builder-operated walkthrough, not a genuine
representative-user test — OPR-7.2 remains explicitly deferred (Section
S below).

## Q. Live verification detail

Confirmed directly, not inferred: Project Territory, Listings sidebar
(Documents 4/Files/Requirements 34/Investigations/RFI
Correspondence/Work Products/Conversation 4/Tasks/Tags), and the
Compliance rollup (30 not yet assessed, 4 satisfied) all render
unchanged on the real commissioning specimen after this stage's change
— confirming the one active-project context remains intact and
isolated, and no prior Territory-Before-Ontology work was disturbed.

## R. Future-Prompt Watch

All items from META-T01/META-T01-RC1's own tables remain open and are
re-affirmed, not allowed to lapse: File/Document/Source collision
(Back-Burner); Documents/Files redundancy (Latent-Regression/Dormant-Risk,
low severity); Trust collision (Back-Burner); Bug Eye's own territorial
foundation (Existing Future Programme); the outstanding genuine OPR-7.2
representative-user test (Existing Future Programme, still deferred).
**New items this stage:** the full Operational Terminal/tabs/projectable-view/Glass
Engine/delegation/perimeter-consolidation grammar (Sections D–L above) —
classified **Existing Future Programme, now formally scoped and
partially designed** rather than merely conceptual; the "Eye"/"Terminal
Eye" naming collision (Section M) — classified **NEW FUTURE-PROMPT
CANDIDATE**, worth resolving before either concept is built further.

## S. Targeted recommissioning impact map

**Not all 34 reassessed — only those with real, evidenced impact from
the one actual code change.** The Adjudicate-form disclosure wrap is a
pure presentation/interaction change (no route, store method, or form
field changed) — the large majority of the candidate list the governing
prompt named (OPR-3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 4.4, 6.1, 7.2) has no
evidenced touchpoint with this change and is **not reassessed**, per
the explicit "determine actual impact from evidence" instruction:

- **OPR-3.7 (Progressive Disclosure)** — directly, materially engaged:
  the change is itself a new instance of progressive disclosure on the
  same page META-T01-RC1 already examined under this Requirement.
  **Remains Satisfied**, live-confirmed (Section Q); if anything, this
  stage's change is additional positive evidence for OPR-3.7, not a
  risk to it — it reduces, rather than adds, permanent visible
  complexity.
- **OPR-5.3 (Human Authority)** — narrowly, adjacently engaged: the
  exact form COMM-I5A instrumented (the mandatory attribution radios)
  is the one now moved behind a disclosure. **Remains Satisfied**,
  live-confirmed (Section P/Q): the two radios, their `required`
  attributes, and the historical `AGENT ASSESSMENT` badge on OPR-1.4 are
  all present and functioning unchanged — only their permanent
  visibility, not their mandatory-choice enforcement, changed.

No other Requirement is judged to have real, evidenced impact from this
stage's one code change.

## T. Tests / full regression result

Three new focused tests (`tests/test_wb1_adaptive_workbench.py`): the
Adjudicate form is present verbatim behind the new `<details>`
disclosure (a `<details>` element's content is always in the raw HTML
response, only visually collapsed — the same established pattern
`test_meta_t01_territory_before_ontology.py` already documented for the
"+ New Folder" disclosure); the form remains fully functional (both
attribution values, submit control) behind the disclosure; the two
pre-existing sibling disclosures ("+ Revise (Addendum)", "Perspective")
and "Discuss this Requirement" are unaffected. Targeted regression
(`test_meta_t01_territory_before_ontology.py`,
`test_comm_i5a_adjudication_attribution.py`,
`test_requirement_promotion.py`, `test_foundation_batch_k.py`): 49
passed. **No real-browser (Playwright) test touches the Requirements
view or the Adjudicate form** (confirmed by direct grep for
`RealBrowser`/`selenium`/`playwright`/`webdriver` across `tests/`) — the
click-reachability risk category that caused META-T01's own regression
does not apply here. Full suite genuinely fresh: **3000 passed, 0
failed, 65 subtests** (15m15s).

## U. Commits / HEAD / origin/main / working tree

See the final chat report for exact values, recorded after this
document and the code/test changes are committed together.

## V. Remaining Workbench/Surface Trust work

Everything in Sections D–L above (true view/container grammar, formal
Operational Terminal elevation, operational tabs/pages, projectable-view
splitting, Glass Engine, delegation architecture, perimeter/rail
consolidation) remains audited-and-designed only. The broader "Visual
Residency / Aggressive Overflow" programme META-T01-RC1 itself named
(Overview's roughly a dozen collapsed accordion headers) also remains
unaddressed — this stage's one change is a first pass restricted to the
Requirements view, not a project-wide overflow pass. Full Surface Trust
polishing remains untouched.

## W. Recommendation for targeted recommissioning

**OPR-3.7 and OPR-5.3 only, both reassessed Satisfied above (Section
S).** No broader recommissioning is warranted from this stage's actual
evidence.

## X. Recommendation on readiness for genuine representative-user OPR-7.2 testing

**Not ready to begin automatically, and not begun.** This stage
implemented one narrow, real Aggressive-Overflow change and audited a
large future Workbench grammar without building most of it — the
"intended product for actual pilot use" the Product Owner's own
META-T01 disposition named as the reason for deferring OPR-7.2 is still
mid-evolution, not stabilized. OPR-7.2 remains **Partially Satisfied —
genuine representative-user validation pending**, per CONTINUE-01 and
carried forward unchanged through every subsequent stage.

---

**Deliberately NOT done this stage:** Bug Eye; Sovereign AI;
Body-of-Knowledge/PMBOK architecture; broad Surface Trust polishing;
independent final commissioning; portfolio/multi-project simultaneous
cockpit; external communications integrations; exposing any private
model chain-of-thought; rebuilding document engines; modifying the
adopted Gemini OPR; declaring OPR-7.2 satisfied; declaring Substantial
Completion; building the Operational Terminal, Glass Engine, delegation
architecture, or true view/container grammar as new code (audited and
designed only); a project-wide Aggressive Overflow pass beyond the one
Requirements-view change described in Section I.
