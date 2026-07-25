# BEEHIVE Constitutional Invariants

**Status:** Ratified. **Authority:** highest in the baseline — these rules constrain every other document in this tree, not the reverse. See `governance-of-governance/amendment-and-ratification.md` for how this list may itself change.

These are rules — timeless, context-independent statements of how BEEHIVE must behave. They are not mechanisms, dataclasses, or field names; those live in `current/kernel-object-model.md` and `specified-unbuilt/`. This list is deliberately not padded — every entry earned its place across nine rounds of adversarial review, and nothing is included merely because it sounded important.

1. **No silent mutation.** No silent overwrite, inference, authority-selection, or truth-promotion, anywhere in the system.
2. **Machine inference never silently becomes authority.** Increasing machine knowledge never automatically increases machine authority. Consequential governed-state change always requires legitimate human or contractual authority.
3. **Provenance is mandatory.** Every claim traces to its source and originator.
4. **Temporal validity is explicit.** State is versioned and time-scoped; nothing is assumed eternally current.
5. **Correction is non-destructive.** Always append a superseding or successor record; never erase.
6. **Existence ≠ compliance.** A stated obligation and a conclusion about whether it's satisfied are always distinct records.
7. **Hypothetical ≠ authoritative.** Proposed futures, candidates, and unadopted alternatives never silently become baseline truth.
8. **Project boundaries are strict.** No project's governed truth automatically transfers into another project's operative state, regardless of shared client, company, or physical asset.
9. **Cross-boundary movement is explicit and authorized.** Publication, sharing, and adoption always require a deliberate, attributed act; there is no implicit access across a project or organizational boundary.
10. **Authority conflicts surface, never resolve silently.** Where two legitimate authorities disagree, the system flags the conflict rather than picking a side.
11. **Private work stays private until deliberately shared.** Visibility is an explicit permission transition, never an automatic consequence of creating professional work.
12. **Collaborative provenance is irreversible.** Once another party has made a genuine, governed contribution, reverting shared work to private is prohibited — this preserves shared provenance, not authorship.
13. **Archive is terminal.** Archived material is dead/frozen — readable, searchable, citable, comparable, exportable, and derivable, but never mutated. New reasoning proceeds only through a newly-derived record with its own identity and explicit lineage.
14. **Perspective must never alter epistemic truth.** Who is looking may change what's shown or permitted; it never changes what a Finding, Requirement, or Relationship means.
15. **Contract DNA must never masquerade as project authority.** A delivery-model template may suggest expected obligations; only the actual, ingested project contract governs.
16. **Human professional autonomy is not surveilled.** No behavioral/activity telemetry, no automated person-level performance judgment. Identity remains legitimate for authorship, accountability, and collaboration — never for computed ranking.
17. **Post-contract project termination is never produced by ordinary viability/recovery analysis.** Economic deterioration alone never creates or authorizes project termination. A project-ending state enters BEEHIVE only through an actual governing contractual/legal event and authorized human/legal action.

---

## Why seventeen, not fewer or more

Every item above survived a specific adversarial test — several were rejected, merged, or sharpened before reaching this list (the single-authority-ladder model was rejected in favor of orthogonal dimensions; a proposed seventh "epistemic-function" axis was rejected because dataclass-type-identity already carries that distinction without redundancy; a "constitutionalGenerationId" mechanism was rejected in favor of reusing `Supersession`). This list is deliberately not a restatement of every principle discussed across nine rounds — most of what was discussed is a *mechanism implementing* one of these rules, not a rule in its own right, and belongs in `current/` or `specified-unbuilt/` instead.
