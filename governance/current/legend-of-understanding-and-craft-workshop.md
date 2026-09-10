# Craft Workshop, Visual Dictionary, and the Legend of Understanding

Status: current governance principle, v1.0, 2026-09-10
Authority: Product Owner `LEGEND OF UNDERSTANDING — CRAFT WORKSHOP GOVERNANCE
RATIFICATION 01`
Repository grounding SHA: `3168355d9cd8fc6c4d3c55b8cf49bbe0c723d7d7`

**NO IMPLEMENTATION AUTHORITY CREATED. NO NEW SUBSYSTEM AUTHORIZED. NO RUNTIME
BEHAVIOUR CHANGED.**

This record changes no route, schema, template, test, threshold or vocabulary in
code. It does two things and deliberately nothing else: it **names** an
environment the Product Owner has decided on, and it **writes down doctrine that
was already implemented and governed nowhere** — living only in a module
docstring, where it could be altered by any future session without anyone
noticing a governance record had changed.

---

## 1. The three layers, and why they are three

> **CRAFT WORKSHOP DISCOVERS AND REFINES MEANING.**
> **LEGEND OF UNDERSTANDING REGISTERS MEANING.**

| Layer | What it is | What it is not |
|---|---|---|
| **Craft Workshop** | The environment where a human and GO explore, teach, compare, correct and refine visual understanding. | Not a store, not an authority, not a place where anything becomes true by being discussed. |
| **Visual Dictionary** | The working vocabulary and visual exemplars **under development** inside Craft Workshop. | Not registered understanding. Working material may be wrong, partial, or superseded tomorrow. |
| **Legend of Understanding** | Registered, accepted, reusable understanding **within a declared scope**. | Not universal truth. Registration is bounded by scope, always. |

**A GO hypothesis does not become registered understanding merely because it was
proposed.** That sentence is the whole reason the layers are separate, and it is
already enforced in code: `CaseWorkspaceStore.propose_legend_item` records
`status=LEGEND_STATUS_PROPOSED` unconditionally — its own docstring reads
*"GO proposes one reading of one mark. Always PROPOSED, never decided."*

### Naming

**CRAFT WORKSHOP** is the Product Owner's name for the exploratory environment.

**The generic term WORKSHOP is not reused and not redefined.** It already means
something else in this corpus: `specified-unbuilt/architect-studio.md` lists
*"Workshop / AFT / Gym — qualification and capability measurement"* as a line
kept deliberately distinct from design production. That meaning stands
unchanged. This record adopts the qualified two-word name precisely so the two
cannot be confused, and the collision is recorded here rather than resolved by
quietly overloading a word.

---

## 2. What was already built (recovered, not designed)

`services/legend_of_understanding.py` (1,686 lines), `LegendItem` in
`services/case_workspace.py`, four routes in `routes/workspace.py`
(`drawing_understanding_review`, `decide_legend_item_route`,
`decide_legend_family_route`, `legend_item_snapshot`) and
`templates/drawing_understanding.html`, shipped as
`CLAUDE-LEGEND-OF-UNDERSTANDING-01`. Its opening line is already the doctrine:
*"GO proposes, a human confirms, meaning becomes reusable."*

This record does not redesign any of it. Everything below is a statement of what
the code already does, verified against the code at the grounding SHA.

### 2.1 Registration threshold

An interpretation crosses into the Legend of Understanding when a human decision
is recorded against a proposal. The record that results carries, and must
continue to carry:

- originating **Source** (`source_id`) and **page/sheet**
  (`page_structural_unit_id`)
- **normalized region** (`region`) in the sheet's own original frame
- **visual exemplar** (`snapshot_path`, optionally `derived_view_id`)
- **observed text** (`observed_text`)
- **GO hypothesis** (`proposed_kind`, `proposed_meaning`,
  `interpretation_method`, `confidence`)
- **human decision** (`decisions[]`, append-only)
- **scope** (`scope_kind`, `scope_id`)
- **provenance** (GovernanceLog entries, `evidence_tier`, `style_context`)
- **version/supersession** (`LEGEND_STATUS_OVERRIDDEN`, and the decision history
  itself)
- **effective meaning**, derived at read time by
  `legend_of_understanding.effective_meaning`

**Registration means the interpretation has been accepted sufficiently to be
reusable within its declared scope. It never means the interpretation is
universally true.**

### 2.2 The exemplar is not decoration

`propose_legend_item` **refuses a proposal with no snapshot**:

> *"A legend item needs a snapshot. A reviewer must see the mark…"*

Asking a person to confirm "section reference" as a detached label invites them
to agree with a plausible sentence. Showing them the mark asks a question they
can actually answer. It is also the only thing that makes an UNKNOWN row useful:
an unreadable squiggle with its picture attached is a real question; the word
"unknown" alone is not.

### 2.3 Authority and precedence — current document evidence has first claim

`LEGEND_PRECEDENCE_ORDER`, walked by `resolve_meaning`:

1. `explicit_legend`
2. `confirmed_project`
3. `confirmed_discipline`
4. `confirmed_source_set`
5. `generic_inference`
6. `unresolved`

**An explicit current legend, key or convention outranks previously learned
similarity, always.** Previously confirmed exemplars may inform the possibility
cloud; they may never override explicit current evidence. This is the property
that makes a symbol library safe on a real drawing set instead of dangerous.

**Style context informs confidence, never meaning.** `style_context` records
drafting era, office and discipline and may raise or lower confidence. *"1970s
hand-drafted structural"* is evidence about **how to read** a sheet, never a
licence to assert **what it contains**.

### 2.4 Append-only history

**HUMAN CORRECTION DOES NOT ERASE GO'S ORIGINAL HYPOTHESIS.**

`decide_legend_item` appends; it never edits an earlier entry and never touches
`proposed_meaning`. `effective_meaning` derives the current reading from the
newest decision **at read time and stores nothing**, so proposal →
correction/confirmation → effective meaning stays fully reconstructable. A
reviewer who changes their mind twice leaves three legible states.

This is `CURRENT STATE MUST NOT LAUNDER HISTORY` applied literally.

### 2.5 Scope, narrow first

`KNOWN_LEGEND_SCOPES`, narrowest first: `instance`, `page`, `source`,
`discipline`, `project`. `decide_legend_item` defaults to
`LEGEND_SCOPE_INSTANCE` — the narrowest — and the store says why: *"a convention
confirmed on one sheet is not evidence about a consultant's whole office until
somebody says it is."*

> **CORRECT THE EXEMPLAR ONCE.**
> **REUSE THE LESSON MANY TIMES.**
> **REVALIDATE IT IN EACH NEW CONTEXT.**

Promotion to a wider scope is explicit and governed. Nothing is promoted by
repetition, by confidence, or by having been confirmed once somewhere else.

### 2.6 Identity and target are separate conclusions

`PROPOSITION_IDENTITY` and `PROPOSITION_TARGET` divide *what a mark signifies*
from *what it points at*, and each is decided separately. Visual clustering
(`family_signature`, `cluster_candidates`, `confirm_family`) **proposes**
equivalence and organises evidence; it never establishes that two marks mean the
same thing. `RELATIONSHIP_TYPE_SAME_SUBJECT_AS` is recorded when a human has
confirmed the source proposition and the evidence supports it — *"a
carry-forward nobody can audit is a guess with better manners."*

---

## 3. Text, shape, and binding

> **TEXT IS SEQUENTIAL. SHAPE IS RELATIONAL.**
> **DRAWING MEANING EMERGES FROM THEIR BINDING.**

**OCR alone does not establish drawing meaning.** Recovered text is a reading of
an image in reading order; it is not layout, not relationship, and not
significance. The Legend of Understanding may register accepted relationships
among visual mark ↔ text ↔ spatial context ↔ meaning ↔ referent. It registers
them because a human accepted them, never because they were extracted.

This is not abstract. Measured on a real customer photograph, whole-image OCR
returned 114 words at a legible-token ratio of 0.123, and crop-and-re-read
verification recovered **0 of 12** sampled lines — while an ink-density control
showed the boxes carried 3.8x the ink of random controls with none on blank
paper. **The geometry was sound and the reading was not stable.** Where a mark
is and what it says are different questions with different reliability.

---

## 4. The possibility cloud

Before registration, GO may preserve multiple candidate meanings, candidate
referents, unresolved symbols and open ambiguity. `ConversationMessage.
candidate_referents` already exists for exactly this, and `LEGEND_KIND_UNKNOWN_
SYMBOL` / `LEGEND_KIND_UNKNOWN_ANNOTATION` give an unreadable mark a name
without giving it a meaning.

**A good first approximation may remain a bounded cloud until evidence justifies
narrowing.** Premature certainty is a defect, not progress, and
`LEGEND_STATUS_DEFERRED` exists so that declining to decide is itself a
recordable act.

---

## 5. The Indexer

**INDEXER** is recorded as the current **working** human role term for visual
indexing work. An Indexer may inspect candidate slices, identify, classify,
confirm, correct, reject, mark uncertain, or defer.

> **THE INDEXING ACT IS SEPARATE FROM THE AUTHORITY OF THE MEANING.**

Indexing does not confer professional or Project authority. Higher-consequence
interpretation may later require a stronger reviewer or expert authority; **that
workflow is not designed and not authorized here.** No role, permission,
entitlement or route is created by this record.

---

## 6. Spatial legend detection — detection evidence only

`services/legend_detection.py` (`CLAUDE-GO-PERCEPTION-LEGEND-DETECT-01`,
implemented and deployed) runs:

> positioned OCR → candidate legend heading → spatial support → candidate legend
> region

Its output is **DETECTION EVIDENCE ONLY**. It establishes none of: a confirmed
legend, a symbol meaning, registered understanding, or a project convention. It
creates no `LegendItem`, assigns no meaning, and never enters
`resolve_meaning`'s precedence. Every candidate carries
`status="candidate_only"`, and strength is a **named** judgement with its counts
attached — never a probability, which would imply a calibration nobody has
performed.

### Intended next technical path

> CANDIDATE LEGEND REGION → PROPOSED ENTRY SLICES → GO HYPOTHESIS → INDEXER
> CONFIRM/CORRECT → LEGEND OF UNDERSTANDING REGISTRATION

**Slicing is proposal-only. No registration occurs merely because an entry was
sliced.** Each arrow is a real transition; none of them is automatic.

---

## 7. One implementation divergence, reported and not fixed

The Product Owner's §8 direction — that the indexing act is separate from the
authority of the meaning — **is not yet enforced in code**, and this record
states that rather than implying a gate exists.

`decide_legend_item_route` and `decide_legend_family_route` are `@login_required`
only, and `scope_kind` is taken from the submitted form. Any authenticated user
who can reach a project — including a Document Shop `ROLE_CUSTOMER` on a
container they own — can therefore record a decision at `project` or
`discipline` scope. Nothing distinguishes the act of indexing from the authority
of the meaning being registered.

This is a **conflict between ratified direction and current implementation**, not
a defect introduced by this record, and it was found by reading the routes rather
than assumed. **No code was changed in this task**, per the direction's own
instruction. It is the natural subject of a separate, bounded authorization.

A smaller observation, recorded without a judgement: `decide_legend_family_route`
defaults `scope_kind` to `source` where the single-item route defaults to
`instance`. A family spans a source, so that may be its correct narrowest — but
it is one level wider than the narrow-first default and is worth a deliberate
decision rather than inheritance.

---

## 8. What this record does not do

It authorizes no implementation, creates no route, schema, role, permission,
threshold or vocabulary, and changes no runtime behaviour. It does not alter
spatial legend detection, positioned OCR, Legend of Understanding runtime
behaviour, RFP/procurement, Document Shop, or any Cognitive Gym material.

**It is deliberately not placed under `cognitive-gym/`.** The Gym develops and
measures capability; the Legend of Understanding governs reusable knowledge.
Those are different subjects, and the Gym's own material is under concurrent
authorship. The related capability bars remain **C02** (visual form recognition)
and **C09** (*"symbolic meaning and reference binding… keeps IDENTITY and TARGET
distinct"*) — which this subsystem already implements under those exact two
names — and that relationship is a cross-reference, not a dependency.
