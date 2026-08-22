# Vision / Analogy Candidate Register

Status: candidate map, version 1.0 · Index: [`README.md`](README.md)

This register reports repository evidence and recommends; **the Product Owner decides
which candidates become records.** All ten candidates below were dispositioned on
2026-08-21 — see **Product Owner dispositions** at the foot of this file. Two were
filed, one was already covered, and the rest were deliberately **not** filed. The
evidence sections are unchanged.

No corpus-wide sweep for colourful phrasing was performed, and none should be. Each
candidate below was investigated because the mission named it. Where the repository
contains no evidence, the register says so — **no provenance was invented, in either
direction.**

## Type vocabulary

`VIS` product vision · `ANA` analogy/mental model · `FORMAL TERM` already a defined
architectural mechanism, **do not demote** · `UNCLEAR` needs Product Owner input.

---

## Candidates

| # | Candidate | Type | Evidence | Why durable | Related GOV/CIC | File? | PO decision? |
|---|---|---|---|---|---|---|---|
| C-01 | **ARCHIOSK as the kiosk** | VIS | `current/developer-mode-ccn.md` "Kiosk principle" — only occurrence | Decides what the interface may become; shapes every capability-placement call | GOV-P-001; CIC-DEVELOPER-MODE, CIC-COMPOSER | ✅ **FILED [VIS-001](VIS-001.md)** | No |
| C-02 | **Composer as the service counter** | ANA | Same source, same paragraph | Explains why one entry point rather than one control per capability | CIC-COMPOSER v1.0 | ✅ **FILED [ANA-001](ANA-001.md)** | No |
| C-03 | **GO as the professional / intelligence machinery** | ANA | Same source: "GO is the intelligence and professional machinery behind that counter" | Sets the expectation that GO answers *behind* a boundary, not at it | CIC-GO-CONVERSATION, CIC-SPIN-INTELLIGENCE | ⚠️ **Already covered** by ANA-001's mapping. A separate record would duplicate | No |
| C-04 | **Tools that make tools** | VIS | `developer-mode-ccn.md` "composable tools-that-make-tools direction"; `GO-TOOL-MAKING-01` (APPROVED, generation workflow **unbuilt**) | Real recorded direction with an explicit unbuilt boundary — exactly the case where a vision record's "does not authorize" earns its keep | GO-TOOL-MAKING-01 | **Recommend VIS-002** | Yes |
| C-05 | **Minecraft-like composability** | UNCLEAR | **None.** Repository-wide search for "Minecraft" returns zero results | Cannot assess — no corpus evidence | — | ❌ **No.** Would require inventing provenance | **Yes** |
| C-06 | **Military order / canonical order** | FORMAL TERM **+** ANA | The *artifact* is formal: `current/canonical-implementation-order.md` uses the five-paragraph order structure (SITUATION · MISSION · EXECUTION · SUPPORT · COMMAND & CONTROL). The *framing* appears only in `templates/README.md` (2026-08-20, this session's lineage) | The structure is already governing; the framing explains why it looks like that | canonical-implementation-order.md | ⚠️ **Split.** Do not file a VIS/ANA that could be read as governing the order format. An ANA explaining the borrowing is safe | Yes |
| C-07 | **Beehive / organize without destroying** | UNCLEAR | **No analogy-sense evidence.** `BEEHIVE` (11 files) is the **formal kernel/product name** — "BEEHIVE Constitutional Invariants". Lowercase `beehive:` appears only as a storage-key namespace (`beehive:panel:launcher`). The governance-beehive framing exists only in Product Owner prompts | Collision risk is the finding: filing an ANA for "beehive" would sit directly beside a formal product name | constitutional-invariants.md | ⚠️ **Not as "beehive".** If filed, name it for what it means (e.g. "organize without destroying") to avoid colliding with the kernel name | **Yes** |
| C-08 | **Panels show the work; menus hold the machinery** | ANA *(rule → GOV-P)* | The phrase appears **nowhere** in the repository. The nearest governing text is `CIC-PANEL` v1.0: "Menus are the canonical machinery/restoration path where available" and "closing never deletes data, ends conversation, cancels CCN, or clears evidence" | The *rule* is real and cross-cutting; the *phrasing* is Product Owner conversational | CIC-PANEL v1.0 | ⚠️ **Rule first.** This is back-catalog **DC-04**, a `GOV-P` candidate. File the `GOV-P`; an `ANA` may then explain it | Yes |
| C-09 | **Airlock / Vestibule** | **FORMAL TERM** | `specified-unbuilt/external-intelligence-airlock.md` (617 lines, three authorized missions, an execution hold, STOP boundaries); `GO-EXTERNAL-VESTIBULE-01` | Airlock = movement boundary; Vestibule = admission/authority boundary. Both carry governed consequences | The Airlock record; GO-EXTERNAL-VESTIBULE-01 | ❌ **Do not file as analogy.** An ANA may later explain the metaphor's origin and **link** the definitions | No |
| C-10 | **CCN → CN → SI** | **FORMAL TERM** *(CCN)* **+** ANA *(the borrowing)* | `current/developer-mode-ccn.md`: `/CCN` implemented with a governed command family; "Future `CN` and `SI` instruments may formalize and authorize bounded changes while preserving the same **construction-native progression**" | CCN defines real product state and workflow. CN/SI are named-but-unbuilt successors | CIC-CCN v1.0; developer-mode-ccn.md | ⚠️ **Split.** CCN's definition stays where it is. An ANA may explain the construction-industry borrowing and note CN/SI are unbuilt | Yes |

---

## What the evidence actually showed

**Two candidates have no repository provenance at all.** C-05 (Minecraft) returns
zero results corpus-wide. C-07's "beehive" framing exists only in Product Owner
prompts — and worse, `BEEHIVE` is already the formal kernel name across 11 files, so
filing an analogy under that word would put an explanatory record beside a governing
one under the same term. Both are reported rather than reconstructed. **A concept the
Product Owner uses in conversation is perfectly real; it simply is not yet evidenced
here, and this register will not pretend otherwise.**

**One candidate is the reverse case.** C-08's phrasing appears nowhere, but the
*rule* it expresses is already governing inside `CIC-PANEL` and was independently
flagged as drift cluster DC-04 by the back-catalog audit. The right response is a
`GOV-P`, not an `ANA` — and filing the `ANA` first would let a metaphor stand in for
a rule, which is exactly what [`README.md`](README.md) forbids.

**Two are formal architecture and must not be demoted.** C-09 (Airlock/Vestibule)
and the CCN half of C-10 have governed definitions with real consequences attached.
Where a term has matured, the `ANA` record explains the origin and links the
definition — it never becomes the place the term is looked up.

**Only one candidate is a clean, evidenced, unfiled VIS.** C-04, tools that make
tools: a recorded direction with an explicit unbuilt boundary
(`GO-TOOL-MAKING-01` is APPROVED as direction with the generation workflow not
implemented). That gap is precisely what a vision record's "what it does not
authorize" field exists to hold.

---

## Recommended sequence

1. **C-08 as a `GOV-P`** — the panel-visibility rule. Back-catalog MQ-P1-02. Rule
   before metaphor.
2. **C-04 as `VIS-002`** — tools that make tools, with the unbuilt boundary stated.
3. **C-06 / C-10 as `ANA` records** — only after their formal halves are settled, and
   only if the explanatory value is real.
4. **C-05 / C-07** — hold pending Product Owner input. Nothing to file from evidence.

Filing all ten would produce ten records where four are useful and two would be
fiction. The mission's own instruction applies: do not create a record merely to
fill a template.

---

## Product Owner dispositions — DECIDED 2026-08-21

Recorded under `CLAUDE-GOVERNANCE-CLOSEOUT-01`. **A decision not to govern something
does not itself elevate that concept into governance.** These rows are audit history:
they record what was considered, what evidence existed, what was decided and why.
They confer no authority on any concept, including the ones marked NOT FILED.

| # | Candidate | Product Owner disposition | Where the outcome lives |
|---|---|---|---|
| C-01 | ARCHIOSK as the kiosk | **FILED** — [`VIS-001`](VIS-001.md) | `governance/vision/` |
| C-02 | Composer as the service counter | **FILED** — [`ANA-001`](ANA-001.md) | `governance/vision/` |
| C-03 | GO as the professional / intelligence machinery | **NOT FILED — ALREADY COVERED** by ANA-001's mapping. A separate record would duplicate | this register |
| C-04 | Tools that make tools | **FILED** — [`VIS-002`](VIS-002.md), with the unbuilt generation workflow stated explicitly | `governance/vision/` |
| C-05 | Minecraft-like composability | **NOT FILED — INSUFFICIENT GOVERNED PROVENANCE.** No corpus evidence; a conversational comparison rather than a durable governed concept. **No provenance manufactured.** If a later search discovers historical references, they are to be preserved, not deleted | this register |
| C-06 | Military order / canonical order | **NO ANA REQUIRED AT PRESENT — FORMAL STRUCTURE ALREADY GOVERNS.** The useful structure is formalized in `current/canonical-implementation-order.md`. Existing explanatory references preserved; formal governance is not duplicated by wrapping it in analogy | this register |
| C-07 | Beehive / organize without destroying | **NOT FILED — TERM COLLISION.** `BEEHIVE` is a formal kernel/system name. An explanatory analogy under the same term would blur formal architecture identity, explanatory metaphor and governance authority. Existing beehive language stays where present. Any future analogy must use a **distinct title** and must not redefine the formal BEEHIVE architecture | this register |
| C-08 | Panels show the work; menus hold the machinery | **PRINCIPLE FILED, ANALOGY NOT FILED** — [`GOV-P-002`](../records/GOV-P-002.md) v1.0 governs the durable principle. **No ANA record filed**; the slogan is not governed merely for being memorable | `governance/records/`, DC-04 outcome note |
| C-09 | Airlock / Vestibule | **NOT AN ANALOGY — FORMAL TERM.** Not demoted | this register |
| C-10 | CCN / CN / SI | **DEFER ANA UNTIL CN/SI ARE SUFFICIENTLY DEFINED.** CCN stays formal/implemented where governed; CN and SI stay named-but-unbuilt. Analogy must not imply architectural maturity they do not possess | this register |
| C-11 | **Structural Agency** | **FILED** — [`VIS-003`](VIS-003.md). Product Owner decision, 2026-08-21, correcting an earlier reading of the Bauhaus/Constructivist direction. Principle stated in conversation; the one repository precedent (`static/css/tokens.css`'s meaning-named semantic tokens) is cited without claiming it *is* the principle | `governance/vision/` |
| C-12 | **Generative coherence — one law, many truthful forms** | **FILED** — [`ANA-002`](ANA-002.md). Companion analogy. Filed **because** the design probes discussed alongside it (gravitational mass, spatial constraint, displacement, magnetic tension) needed a mandatory `DOES NOT MEAN` field to stop them hardening into rules. No corpus provenance; the record says so | `governance/vision/` |
| C-13 | **Broad cognition, selective attention, narrow authority** | **FILED** — [`VIS-004`](VIS-004.md). Product Owner decision, 2026-08-22. Most of the underlying model was already recorded in the NOT AUTHORIZED `adaptive-attention-and-context-circulation.md` (compound-eye passive/active, attention survival, human authority over significance); the record cites it rather than restating it, and explicitly does **not** lift its status. Genuinely new: attention release (zero prior coverage), reinstatement by condition rather than query, and the compact triad | `governance/vision/` |
| C-14 | **Back-of-house cognition, front-of-house voice** | **FILED** — [`ANA-003`](ANA-003.md). Companion analogy. Filed **because** the images discussed alongside it (back kitchen, ear-touch recall, Wu Wei, kiln/panopticon, unconscious/conscious) needed a mandatory `DOES NOT MEAN` field to stop them hardening into subsystem names or an attention state machine | `governance/vision/` |

**Net effect of the original six decisions: two records filed, four deliberately not
filed.** C-11 and C-12 were added later, on the separate Product Owner decision of
2026-08-21, and are recorded here for continuity rather than as part of that tally.
Four of the ten candidates were declined outright, one was declined as already
covered, and one was split so the principle was filed without the slogan. The
evidence sections above are unchanged and remain the record of what was found.

### What changed in the corpus as a result

- **Filed:** `VIS-002` (C-04) and `GOV-P-002` (C-08's principle half).
- **Not filed, recorded here only:** C-03, C-05, C-06, C-07, C-09, C-10.
- **Nothing deleted or reclassified.** No historical reference to any declined
  concept was removed, and no prior governance was marked obsolete.

---

## Superseded question list

The questions below were the open items **before** the 2026-08-21 dispositions. They
are retained for lineage; all six are now answered by the table above.



| # | Question |
|---|---|
| C-05 | Minecraft-like composability has no corpus evidence. Is it a real durable concept to state fresh, or a passing comparison? Nothing can be filed from evidence. |
| C-07 | "Beehive" collides with the formal `BEEHIVE` kernel name. Should the organizing concept be filed under a different title, or not filed? |
| C-04 | File `VIS-002` for tools that make tools now, or wait until generation work is authorized? |
| C-06 | Is an `ANA` explaining the military-order borrowing wanted, given the order format is already governing on its own? |
| C-08 | Confirm the panel rule should be a `GOV-P` (per DC-04) before any analogy record is filed for it. |
| C-10 | Should an `ANA` record explain the CCN/CN/SI construction-industry borrowing, given CN and SI remain unbuilt? |
