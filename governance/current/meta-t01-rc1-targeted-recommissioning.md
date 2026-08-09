# Territory Before Ontology Targeted Recommissioning (CLAUDE-POSTCAMEL-META-T01-RC1)

**Status: TERRITORY BEFORE ONTOLOGY RECOMMISSIONED — WORKBENCH
EVOLUTION READY FOR PRODUCT OWNER AUTHORIZATION.** Authorized following
the Product Owner's acceptance of META-T01 as a **bounded first
establishment** of Territory Before Ontology, explicitly not completion
of the larger future Workbench metamorphosis (variable views,
Operational Terminal, projectable document surfaces, Aggressive
Overflow, Glass Engine, contextual next actions, delegation, broader
Surface Trust — all remaining separately authorized only when
explicitly prompted). Reassesses the four Requirements META-T01 itself
named as its own recommended targeted subset: OPR-3.1, OPR-3.7, and
(narrowly) OPR-1.1/1.3.

---

## A. Verified starting state

`HEAD == origin/main == 6d9faffdac8fddb9b6b50747c28ad48b3651271a`
confirmed directly before this stage began; working tree clean except
the pre-existing untracked `tests/fixtures/nreocrc/_lab_instance_scratch_002/`
fixture. Also confirmed directly (not assumed): the only real discovery
path to `/upload` in this entire product is the Lists sidebar's own
`"+ New Project"` link (`base.html`, `data-ui-ref="lists.new-project"`)
— relevant to Section D below.

## B. OPR-3.1 (Listings) reassessment

**Remains Satisfied. No regression found.** Live-verified against the
real commissioning specimen, starting from sign-in: the Project
Territory-first Overview exposes an honest, live registered-material
count before any intelligence content, and every pre-existing Listings
branch (Documents, Files, Requirements, Investigations, RFI
Correspondence, Work Products, Conversation, Tasks, Tags) remained
fully visible and unobscured in the sidebar throughout. **No competing
file/project hierarchy was created** — "Project Territory" is a
projection pointer into the same real `display.files` surface, not a
second navigation tree; nothing new was added to the Lists sidebar
itself by META-T01. No previously-available governed object became
harder to reach.

## C. OPR-3.7 (Progressive Disclosure) reassessment — special scrutiny

**Remains Satisfied, with a residual named honestly.** Live-verified
the exact five-step sequence against the real commissioning specimen:

1. **Where am I?** — Project Operating Environment/Access, unchanged,
   still first.
2. **What is here?** — **Project Territory**, META-T01's own addition,
   now second, before any intelligence content.
3. **What does Archiosk know about it?** — Needs Attention through
   History, collapsed by default except where genuinely non-empty
   (`open=(needs_attention_count > 0)`, a pre-existing, unchanged
   mechanism).
4. **What can I do here?** — the register/adjudicate/revise forms
   inside each governed section, reached progressively via disclosure,
   unchanged.
5. **What needs my attention?** — Needs Attention itself, now correctly
   positioned *after* Territory rather than immediately following
   Access/Environment as it did before META-T01.

**Assessed directly, per this stage's own explicit instruction, whether
the UI still exposes materially too much permanent information:** yes,
partially — Overview still renders roughly a dozen accordion headers
(collapsed, but visible as headers) on first load, which is more
structure than a strictly minimal five-step sequence would show. This
is real, but **out of this stage's own bounded scope** — the named
future remedy is the Product Owner's own "Visual Residency / Aggressive
Overflow" programme (Section 7 of META-T01's own governing prompt),
explicitly not implemented here. Recorded as a residual pointing to
that named future programme, not as a present OPR-3.7 deficiency: the
disclosure *order* is now correct; disclosure *density* is a separate,
larger question this stage was explicitly told not to solve.

## D. OPR-1.1 (Project Creation) narrow reassessment — naming collision found and corrected

**A real semantic collision was found, exactly as this stage's own
instruction anticipated, and corrected — not defended.** Per "rectify
the names before trusting the relationships": the only real discovery
path to the entry point is the sidebar's own `"+ New Project"` link
(confirmed directly, Section A). The mechanism it leads to
(`ingest_upload`) **always generates a brand-new project id** — it
never reopens, resumes, or attaches to an existing Archiosk project
record. META-T01's own "Open a Project" heading, chosen to serve the
Territory-Before-Ontology principle, collided with this: "Open"
plausibly implies resuming something that already exists in Archiosk,
which this route can never do — an internally inconsistent pairing
with the very link that leads to it ("+ New Project" → "Open a
Project").

**Corrected to "Establish a Project."** This was judged necessary, not
merely nice-to-have, because a user reading "+ New Project" and then
"Open a Project" on the very next screen receives two different claims
about the same action in immediate succession — a real, if modest,
misrepresentation risk, not a hypothetical one. "Establish" was
chosen because the Product Owner's own META-T01 prompt (Section 4)
already named it as an acceptable alternative candidate, it is
consistent with "+ New Project" (establishing is creating), and it
preserves the Territory framing (a project is established *in*
Archiosk, not moved into it) without implying resumption. Applied
consistently: page `<title>`, `<h1>`, and the one in-copy reference to
"open this project" (now "establish this project"). No other wording
was changed merely for elegance.

## E. OPR-1.3 (Project Switching) narrow reassessment

**Remains Satisfied.** Live-verified a real round-trip switch against
two genuinely different, pre-existing real projects (the ARCHIOSK
commissioning specimen, Client/Owner, 4 registered Sources; "Test 2," a
separate Design-Builder/Proponent project, 1 registered Source):

- After switching to "Test 2," Project Territory showed its own honest,
  correct, *different* count (1 registered) — no leakage from the
  ARCHIOSK specimen's own 4.
- After switching back to the ARCHIOSK specimen, its own state (4
  registered, 34 governed Requirements, 4 Conversation messages) was
  fully intact, byte-identical to before the round trip.
- The user could identify which Project they were in at every step
  (the topbar's own project-name breadcrumb, unchanged by this stage).
- Territory-first presentation survived the round trip in both
  directions without modification.

## F. Semantic-integrity observations — continuity, nothing dropped

All four items META-T01 named are carried forward unchanged, not
re-derived, not silently allowed to lapse:

- **File / Document / Source three-way collision** — unresolved,
  unchanged.
- **Documents / Files sidebar redundancy** — unresolved, unchanged; see
  Section G below for its Latent-Regression classification, also
  carried forward.
- **Archive collision** (`CASE_STATUS_ARCHIVED` vs. whole-project
  archive/restoration) — unresolved, unchanged; already independently
  reconfirmed across multiple prior COMM stages.
- **Trust collision** (Surface Trust visual-polish programme vs. the
  real, implemented Trustworthy Answer Contract) — unresolved,
  unchanged.

**One new, small semantic finding this stage** (Section D above):
"Open" vs. "Establish" for the entry-point heading — found and
corrected, not merely named, because it was judged a material (if
modest) misrepresentation risk rather than a stylistic preference.

## G. Regression/latent-risk observations — continuity, nothing dropped

- **META-T01's own discovered regression, preserved as developmental
  evidence, not re-litigated:** a change that appeared to be
  copy/presentation-only (one sentence of reassurance text) altered
  real click-reachability in an existing interaction
  (`test_p40vw9a_files_cockpit_closeout.py`'s own folder-menu proof).
  This stage does not generalize beyond that evidence or launch any
  broader archaeology — it is recorded here specifically as the
  concrete example the Product Owner's own Section 7 asked to have
  preserved for future latent-regression investigation.
- **`record_relationship`'s missing cross-project guard** (COMM-I6) —
  unaffected, unchanged, carried forward.
- **Two near-identical Source-revision routes** (COMM-I4A) —
  unaffected, unchanged, carried forward.
- **Documents/Files sidebar redundancy** (META-T01) — unaffected,
  unchanged, carried forward as a low-severity dormant-risk candidate.

No new latent-regression candidate was found by this stage's own
narrow reassessment work.

## H. Future-Prompt Watch continuity

Every item from META-T01's own Future-Prompt Watch table remains open
and is explicitly re-affirmed here, not allowed to quietly disappear:
File/Document/Source collision (Back-Burner); Documents/Files
redundancy (Latent-Regression/Dormant-Risk, low severity); Trust
collision (Back-Burner); VS Code Workbench precedent (Existing Future
Programme — this stage's own Section L recommendation directly engages
it); Bug Eye's own territorial foundation (Existing Future Programme —
unaffected, Territory Before Ontology's now-recommissioned status
continues to support it exactly as before); the outstanding genuine
OPR-7.2 representative-user test (Existing Future Programme — still
explicitly deferred, per Section 8 below). No item was implemented.

## I. Tests/live verification

**Live verification**, starting from sign-in, against the real
commissioning specimen and a second genuinely different real project
("Test 2"): Project Territory ordering, honest per-project counts, full
Listings-sidebar accessibility, and a real cross-project round-trip
switch with zero state leakage in either direction — all confirmed
directly, not inferred. **Tests**: the existing ten
`test_meta_t01_territory_before_ontology.py` tests updated for the
"Establish a Project" correction (one assertion changed) and re-run
clean; the real-browser `test_p40vw9a_files_cockpit_closeout.py` suite,
`test_p40vw8qa_upload_capacity.py`, and
`test_p40vw7a_ui_reference_map.py` all re-run clean (51 passed) as a
direct, targeted regression check on the exact area this stage
touched. Full suite re-run genuinely fresh after the naming fix:
**2997 passed, 0 failed, 65 subtests passed** (14m55s).

## J. Commits / HEAD / origin/main / working tree

Committed as `ae5e11109e907a12e30bcbe94005ba8f93d50ad7` ("CLAUDE-POSTCAMEL-META-T01-RC1:
targeted recommissioning of the four Territory-affected Requirements"),
covering `templates/upload.html` (the "Establish a Project" correction),
`tests/test_meta_t01_territory_before_ontology.py` (the matching
assertion update), this document, and the `governance/STATUS.md` row.
Pushed to `origin/main` (`6d9faff..ae5e111`). Working tree clean
afterward except the pre-existing untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/` fixture. The
`2997 passed, 0 failed, 65 subtests passed` result recorded in Section
I above (895.83s / 14m55s) is the genuinely fresh full-suite run
verified against this exact commit's own tree, confirmed clean before
finalizing this record.

## K. Whether Territory Before Ontology remains safely established

**Yes.** All four reassessed Requirements remain Satisfied under live,
repository-grounded verification, not merely re-asserted from memory.
The one real issue this reassessment found (the "Open"/"Establish"
naming collision) was corrected, not merely noted, closing the gap
before it could compound into the future Workbench evolution stage.
No new deficiency, regression, or state-leakage was found.

## L. Recommendation on proceeding to the broader Workbench evolution

**Ready for Product Owner authorization, not begun automatically.**
Territory Before Ontology now stands on a reassessed, corrected,
live-verified foundation (this stage) built on a previously-live-
verified establishment (META-T01). The broader Workbench evolution
(variable views, Operational Terminal, projectable surfaces, Aggressive
Overflow, Glass Engine, contextual next actions, delegation, broader
Surface Trust) was not begun and remains exactly as the Product Owner's
own instruction scoped it — separately authorized only when explicitly
prompted. The genuine OPR-7.2 representative-user Zero-Founder test
remains correctly deferred, per the Product Owner's own stated intent
to complete further material interface refinement first.
