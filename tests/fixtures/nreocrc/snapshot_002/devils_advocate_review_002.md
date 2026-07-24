# Independent Adversarial Review of Snapshot 002 (NREOCRC-OPR-001)

**Reviewer basis:** Independent re-reading of `immutable_original/NREOCRC-OPR-001.md` and the two Appendix OPR-2 SVGs, cross-checked line-by-line against every claim in `snapshot_002/reconstruction_002.json` and the reference-list counts in `snapshot_002/snapshot_002.json`. All section/row/line citations below were verified directly against the source text unless marked otherwise. No other files in the corpus were consulted.

---

## 1. Arithmetic Reconciliation — Appendix OPR-1 Functional Program (redone from scratch)

I recomputed every department subtotal independently, as (Σ Qty × Net Area each) per department, using only the raw row values (columns "Qty" and "Net Area (m²) each"), lines 300–341.

| Department | Rows | My computed total | Stated subtotal (table) | Match? |
|---|---|---|---|---|
| Public / Community | 1–6 | 120+180+90+(2×45)+25+110 = **615** | 570 (row 4) | **NO** (+45) |
| Municipal Administration | 7–13 | 24+160+40+(2×30)+55+20+175 = **534** | 850 (row 10) | **NO** (−316) |
| Emergency Operations Centre | 14–23 | 280+45+40+40+35+22+65+(2×12)+35+145 = **731** | 1,120 (row 17) | **NO** (−389) |
| Communications | 24–27 | 55+45+30+45 = **175** | 175 (row 25) | YES |
| Standby Power & Building Services | 28–33 | 140+60+90+160+15+80 = **545** | 545 (row 30) | YES |
| Vehicle / Service | 34–37 | 260+35+70+45 = **410** | 460 (row 35) | **NO** (−50) |
| Support | 38–42 | (2×10)+60+55+45+15 = **195** | 260 (row 39) | **NO** (−65) |

- Sum of my computed line-item totals: **3,205 m²**
- Sum of the table's own stated department subtotals: 570+850+1120+175+545+460+260 = **3,980 m²**
- Document's own stated grand total (line 343): **"Program Net Area Subtotal ... 4,105 m²"**

**Three independent layers of arithmetic failure in the source document itself:**
1. Five of seven department subtotals do not reconcile against their own room-level rows (only Communications and Standby Power reconcile).
2. The document's stated grand total (4,105) does **not** equal the sum of its own stated department subtotals (3,980) — an internal discrepancy of **+125 m²** that exists independently of the row-level errors.
3. The stated grand total (4,105) also does not equal the sum of the true room-level totals (3,205) — off by **+900 m²**.

**Verdict on Snapshot 002's reconciliation:** `reconstruction_002.json`'s `arithmetic_reconciliation_test.result` reports exactly the numbers I derived independently (615/570, 534/850, 731/1120, 175/175, 545/545, 410/460, 195/260; totals 3,205 and 3,980) — this is **accurate and matches my from-scratch recomputation exactly**. This is the strongest part of Snapshot 002.

**However, it is incomplete**, not wrong: the JSON records `stated_grand_total_found: 4105` as a separate fact but never explicitly computes or flags that 4,105 ≠ 3,980 (the sum of the very subtotals it just reconciled). A downstream consumer reading only the structured fields would have to do this last comparison themselves (as I did) to discover the grand total is *also* internally wrong. I could find no field anywhere in the reconstruction that states this third-layer discrepancy outright. This should be listed as a further reconciliation finding, and it is not currently in `gaps_still_open`.

---

## 2. Authority / Classification Accuracy

I independently tallied all 56 bracket-tagged clauses in the document body (grep for `[MANDATORY]/[RATED]/[INDICATIVE]/[REFERENCE]/[INFORMATIONAL]`, excluding the Section 2.3 legend itself):

- Mandatory: 42 (4.1,4.2,4.3,4.5,5.1,5.2,5.4,5.6,6.1,6.2,8.2,8.3,8.5,9.1,9.2,9.4,10.1,10.2,10.3,11.1,11.2,11.3,12.1,12.3,13.1,13.2,13.3,13.4,14.1,14.2,14.3,15.1,16.1,16.2,17.2,17.3,18.1,18.2,19.1,19.2,19.3,20.2)
- Rated: 8 (4.4,5.5,6.3,9.3,10.4,12.4,14.4,15.2)
- Indicative: 2 (4.6, 18.3)
- Informational: 4 (5.3, 8.4, 17.1, 20.1)

This matches `requirement_extraction_test.classification_distribution` (mandatory 42, rated 8, indicative 2, informational 4) **exactly**, and matches `authority_test.indicative_requirements_found: ["4.6","18.3"]` exactly. **Classification accuracy checks out completely — no distortion, no silent override toward "mandatory" despite `Source.document_authority = contractual`.**

The two "unlabeled" clauses correctly deferred to human classification (2.2 Order of Precedence, 8.1 General zoning description) were appropriately *not* force-defaulted to Mandatory even though Section 2.3's own rule says unlabeled text defaults to Mandatory "unless the surrounding text clearly indicates otherwise" — 2.2 in particular hedges itself ("current intended order... will be restated and finalized in the Project Agreement"), so deferring rather than assuming is the more defensible reading. This is good, non-overclaiming behavior.

## 3. Requirement Text Fidelity

Spot-checked via the `unresolved_qualifier_preservation_test` hedge list — since hedge phrases like "to be confirmed" and "in the order of" occur mid- or late-sentence in the source (e.g. 5.3, 15.1, 18.1), their detection proves the full clause text was captured, not truncated at the first few words. All 11 hedge entries I checked against source text are accurate:

- 4.2 "to be provided" ✓ (line 103), 5.3 "approximate"/"in the order of" ✓ (line 121), 6.1 "to be confirmed" ✓ (133), 14.3 "to be confirmed" ✓ (234), 15.1 "to be confirmed" ✓ (242), 16.1 "to be confirmed" ✓ (250), 18.1 "to be issued"/"approximate" ✓ (268), 19.3 "to be confirmed" ✓ (282), 20.1 "to be issued" ✓ (288), 20.2 "to be confirmed" ✓ (290), 2.2 "current intended order"/"will be restated" ✓ (55, 66).

**But the hedge scan is a fixed keyword list, not exhaustive — it misses real hedges elsewhere:**
- **9.4** (line 171): "...Site geotechnical conditions **to be described in the Data Room**..." — a genuine deferral, not caught (list only catches "to be confirmed"/"to be issued"/"approximate"/"in the order of").
- **13.3** (line 222): "...final tower/antenna scope, height, and structural provision **will be addressed** in the Indicative Design Package **and confirmed through the RFP process**." — a genuine deferral, not caught.
- The entire **Section 12.2 table** (fuel type "Diesel (**assumed**)"; load "850–1,050 kW... **To be confirmed** through Design-Builder's own load calculation") is excluded from the hedge scan entirely, because 12.2 is correctly *not* registered as a bracket-tagged Requirement (it's a table). That exclusion is defensible in isolation, but it means a materially important assumption underpinning Mandatory clause 12.1 (96-hour standby power) is not linked or flagged anywhere as a caveat.

## 4. Relationship / Cross-Reference Accuracy

- `citation_validation_test` (12.3 → Section 4.5, not 4.3): **VALID.** Line 210 reads "...flood conditions associated with the Site context described in Section 4.5," and Section 4.3 is never mentioned near 12.3. This correctly resolves what the file itself notes was a Snapshot-001-era mis-target (I did not chase that file; I only verified the current claim against source text, and it holds).
- `unresolved_section_references` — I checked all 18 entries against source text; all are genuine whole-Section mentions (not fabricated), e.g. 4.3→18 (line 105 "described in Section 18"), 6.1→3 (line 133 "see Section 3"), 8.4→13 and 8.4→14 (line 157, correctly split into two edges for one sentence naming two sections). **VALID** in all 18 cases I checked.
- **Range references only partially resolved (AMBIGUOUS/INCOMPLETE):** 15.1 (line 242) says "resilience... requirements under **Sections 9 through 14** govern" but the tool only records target `"9"` — Sections 10–14 are silently dropped from the reference. Same pattern at 19.1 (line 278, "described in **Sections 10 through 14**"), recorded only as target `"10"`. Not fabricated, but incomplete: 5 of 6 named sections in each range are lost.
- **A real cross-reference is missed entirely, and inconsistently so.** Row 20's Notes column ("Room bridges Secure and Controlled Zones — see Section 14," line 319) is captured (`row_boundary_unresolved_section_refs: row 20 → 14`) — but only because row 20 was separately flagged for having a "/" in its Security Level column, and that flagging method is used to also grab its Notes text. Row 14's Notes column ("**See Section 5.3** regarding approximate area referenced in prose," line 313) contains an equally explicit cross-reference back to Section 5.3 (the informational ~250 m² prose estimate vs. the table's Mandatory 280 m²) — and this is **not captured anywhere** in the reconstruction, because row 14's Security Level is plain "Secure" (no "/"), so the narrow "/"-triggered detection method never looks at its Notes column at all. This is a real, checkable gap, not a hypothetical one: two structurally identical "see Section N" Notes-column references get different treatment purely because of an unrelated column value.

## 5. Missed Content

1. **Section 2.4** ("Precedence Between Text, Tables, and Figures Within This OPR," lines 78–80) — a substantive governance rule (more specific/later-issued statement governs; unresolved conflicts go to the RFP question period) is not bracket-tagged, and unlike 2.2/8.1 it is not even listed among the "registered_manually_unlabeled" clauses awaiting classification. It appears to be dropped entirely, despite being exactly the kind of clause that governs how the row-14/5.3 area conflict (see §4 above) and the arithmetic conflicts (see §1) should be resolved.
2. **Appendix OPR-1 footnote (a)** (line 347): the target building GFA range "9,500–11,000 m²" (attributed to the RFP main document) is never captured anywhere in the reconstruction.
3. **Appendix OPR-1 footnote (c)** (line 351): "Quantities and areas in this Appendix are Mandatory minimums under Section 2.3 unless a row is expressly noted otherwise" — this establishes that each of the 42 Functional Program rows is individually a Mandatory obligation. The reconstruction registers only one umbrella Requirement (8.2) pointing at the whole Appendix; none of the 42 rows are individually tracked as Requirements, and this granularity loss is not listed as a known gap.
4. The **12.2 table's embedded assumptions** ("Diesel (assumed)", "850–1,050 kW... to be confirmed") are excluded from both Requirement registration and the hedge-preservation scan (see §3).
5. Section 7 ("reserved") is correctly treated as not applicable — this one is *not* a gap, just noting it was checked.

## 6. False Positives / False Confidence

- **Expected-Information internal inconsistency (real finding):** row 3 of `expected_information_shadow_rerun.rows` — "Functional Program / Appendix OPR-1 (this document)," `status_as_stated: "Issued"` — is bucketed as `"ALREADY OBSERVED (present in this corpus)"`, yet its own `raw_evaluator_outcome` is `"expected_not_found"`. These two fields directly contradict each other for the same row: the human-friendly bucket label says present, the underlying raw evaluator says absent. A consumer reading only `raw_evaluator_outcome` (the actual system output) would wrongly conclude the Functional Program is missing from the corpus, when it is in fact embedded in the ingested .md file. This is the one place I found where Snapshot 002's own diagnostic layer papers over a contradiction rather than surfacing it.
- **`source_identity_test` self-contradiction:** `fields_derived_by_generic_analysis.issue_date` is shown populated as `"December 8, 2026"`, but the accompanying `issue_date_note` says the value was "left unset here deliberately." The diagnostic dict and the prose note disagree about whether the field was actually set on the registered Source. Ambiguous/self-contradictory as presented; I cannot resolve which is true from the two files given (the actual Source record content is not included, only its ID).
- **Requirement count self-inconsistency:** `requirement_extraction_test.total_requirements_registered = 58` (56 bracket-tagged + 2 unlabeled), but `snapshot_002.json.reference_lists.requirements` (and `reference_list_counts.requirements`) both list **59** IDs. I independently counted the requirements array in `snapshot_002.json` (lines 62–120) at 59 entries. This is an unexplained off-by-one between the diagnostic summary and the actual frozen snapshot content — a genuine internal-consistency gap that is not self-reported anywhere in `gaps_still_open`.
- Aside from the three items above, I found **no case** where Snapshot 002 asserts something with more certainty than the source supports. The Expected-Information bucketing of the ambiguous Accessibility Standard reference (Section 3, row 7: "Incorporated by reference; to be listed") as `"UNKNOWN"` rather than forcing it into "issued" or "future" is appropriately cautious, not overclaimed. Likewise RFP-001 ("Issued concurrently" but absent from corpus) is correctly bucketed as "CURRENTLY EXPECTED... absent," not silently downgraded to "future" — this is actually a correct, non-overclaiming treatment of a document the source says already exists.

## 7. Source-Location Citation Verdicts

| Claim checked | Verdict | Basis |
|---|---|---|
| 12.3 cross-references 4.5, not 4.3 | **VALID** | Line 210 confirms "Section 4.5"; no "4.3" nearby |
| Row 20 → Section 14 (footnote b) | **VALID** | Line 349 |
| Functional Program table: 42 rows, lines 298–341 | **VALID** | Verified row-by-row |
| Front-matter table: 8 rows, lines 8–17 | **VALID** | Verified |
| Section 3 cross-ref table: 8 rows, lines 86–95 | **VALID** | Verified |
| 12.2 sizing table: 4 rows, lines 203–208 | **VALID** | Verified |
| Appendix OPR-3: 5 rows, lines 373–379 | **VALID** | Verified |
| unresolved refs 4.3→18, 4.4→4, 4.6→4, 5.1→8, 5.2→8, 5.6→9, 6.1→3, 8.3→14, 8.4→13/14, 9.2→12, 10.3→12, 10.4→17, 11.2→12, 13.2→14, 17.2→19 | **VALID** (all 15) | Each confirmed against exact source wording |
| 15.1→"9" (source says "Sections 9 through 14") | **AMBIGUOUS/INCOMPLETE** | True but only 1 of 6 named sections captured |
| 19.1→"10" (source says "Sections 10 through 14") | **AMBIGUOUS/INCOMPLETE** | Same pattern |
| Expected-Info row 3 (Functional Program) "ALREADY OBSERVED" vs. raw outcome | **MISMATCH** | Internal contradiction, see §6 |
| Row 14 Notes "See Section 5.3" | **UNVERIFIABLE / not attempted** | No claim was made about this reference at all — it is a silent omission, not a wrong citation |
| source_identity_test issue_date shown vs. "left unset" note | **AMBIGUOUS** | Cannot determine actual stored value from the two files provided |

## 8. Expected-Information Analysis — Overall Verdict

Checked against Section 3 (lines 86–95) and `manifest.json`'s `documents_referenced_but_not_yet_issued`: all 8 rows' `status_as_stated` values are verbatim-accurate quotes from the source. The bucketing logic (issued-but-absent vs. declared-future vs. unknown) is materially correct and, notably, does **not** understate RFP-001's already-issued status by lumping it in with the "to be issued" documents — which would have been the easy, wrong shortcut. The one defect is the internal row-3 contradiction documented in §6, not a misreading of the source.

## 9. Assessment of Snapshot 002's Self-Reported Gaps

The three items in `gaps_still_open` (free-text date parsing; no sufficiency outcome for "explicitly deferred, no date stated"; maturity-type taxonomy conflating procurement stage with design maturity) are each independently verifiable as real and accurately described against the source (e.g., "December 8, 2026" is indeed free text, line 13). They are not overclaimed.

However, the self-reported gap list is **incomplete**. Based on my independent read, at least the following additional gaps exist but are not listed:
- The grand-total-vs-subtotal-sum discrepancy (4,105 vs. 3,980) is computed but never flagged as its own reconciliation failure (§1).
- Section 2.4 is dropped entirely, not even queued for human classification like 2.2/8.1 (§5.1).
- "Sections X through Y" range references only capture the first section (§4).
- The row 14 ↔ 5.3 cross-reference is missed due to an inconsistent detection method vs. row 20 (§4).
- The Requirement count self-inconsistency (58 vs. 59) is unexplained (§6).
- The Expected-Information row-3 bucket/raw-outcome contradiction is unflagged (§6).

## 10. Overall Assessment

Where Snapshot 002 makes an explicit, checkable claim, it is almost always **accurate** — the arithmetic reconciliation numbers match my from-scratch recomputation exactly, the classification distribution matches a full manual tally exactly, the 12.3→4.5 citation fix is correct, the table-extraction line ranges are all correct, and the Expected-Information bucketing avoids the easy over-claiming traps (RFP-001, the Accessibility Standard). The system is also commendably restrained about not fabricating relationships to non-existent Sources (precedence_reconstruction note) and about not escalating the arithmetic mismatch to a compliance finding against the Design-Builder.

Its weaknesses are less about wrong claims and more about **incompleteness and internal inconsistency**: it stops one arithmetic step short of the grand-total check; its generic "Section N" scanner cannot handle ranges or Notes-column references outside one narrow trigger; a governance-relevant clause (2.4) falls through the cracks entirely; and there are two clear self-contradictions (the Expected-Information row-3 label vs. raw outcome, and the 58-vs-59 requirement count) that suggest the diagnostic/summary layer is not always in sync with the actual frozen data it is describing. None of these amount to fabrication or overclaiming — they are gaps in coverage and self-consistency, not false statements about the source document.
