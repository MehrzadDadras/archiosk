# GO-SELF-COMMISSIONING-01 — Self-Project Commissioning — OPR, Verification, Deficiency, Recommissioning

| Field | Value |
|---|---|
| Prompt ID | GO-SELF-COMMISSIONING-01 |
| Title | Self-Project Commissioning — OPR, Verification, Deficiency, Recommissioning |
| Agent | Unassigned (governed self-project commissioning programme) |
| Status | APPROVED |
| Purpose | Preserve ARCHIOSK/GO self-project commissioning as evidence-based assessment of implemented controls against Product Owner Requirements, with governed deficiency, correction, retest, acceptance, and recommissioning. |
| Product Owner acceptance | Product Owner-adopted and substantially exercised. A 34-requirement Owner baseline, developmental commissioning method, bounded assessment tranches, corrective tranches, and Product Owner authority decisions are governed records. This is not a declaration of Final Completion: OPR-7.2 remains Partially Satisfied and independent final commissioning has not occurred. |
| Lineage | Dedicated programme anchor for retrospective OPR work and the COMM-A1 → COMM-I6 self-project commissioning sequence. Current authority and implementation truth remains [STATUS](../STATUS.md), [Self-Project Commissioning Readiness](../current/comm-a1-self-project-commissioning-readiness.md), [Owner Baseline and Developmental Commissioning](../current/comm-i2-owner-baseline-and-developmental-commissioning.md), [Final Current-Baseline Commissioning Tranche](../current/comm-i6-final-current-baseline-commissioning-tranche.md), and the later [OPR-7.2 Evidence-Boundary Audit](../current/continue-01-opr-7-2-evidence-boundary-audit.md). Related, not absorbed: [GO-TRUST-SECURITY-01](GO-TRUST-SECURITY-01.md) and [GO-SURFACE-TRUST-01](GO-SURFACE-TRUST-01.md). |
| Superseded by | None |
| Absorbed into | None |

## Governing direction

ARCHIOSK/GO should itself be commissioned against its Product Owner Requirements rather than relying only on feature completion or passing tests.

Tests and feature completion are evidence inputs. They do not, by themselves, establish that the Product Owner requirement is satisfied, that the implementation arrived at the appropriate developmental point, or that an authorized human has accepted a deficiency or residual.

## Commissioning distinctions

Preserve distinct records and meanings for:

- **requirement** — the Product Owner outcome or constraint against which the system is assessed;
- **implemented control** — the real application, process, or governance mechanism intended to satisfy it;
- **evidence** — inspectable support showing what exists and how it behaves;
- **verification** — the bounded assessment or test of evidence against the requirement;
- **deficiency** — a governed gap, contradiction, weakness, or unmet condition;
- **correction** — a separately authorized change addressing the deficiency;
- **retest** — renewed verification after correction or material change;
- **acceptance** — an evidence-based decision made by the appropriate authority.

These stages must not be collapsed into one “done” state. Agent assessment, human review, Product Owner acceptance, and independent commissioning are distinct authority levels.

## OPR discipline

- Implemented controls are evaluated against the adopted OPR rather than inferred to be sufficient because they exist.
- Requirement wording, identifiers, source anchors, and revisions remain traceable.
- Present-state conformance remains distinct from developmental or conception-point conformance.
- Uncertainty and insufficient evidence remain explicit.
- An agent may investigate, assess, classify, and recommend; it must not impersonate Product Owner or other reserved human authority.
- Current corrected conclusions govern under repository precedence while earlier records remain preserved for lineage.

The canonical self-project baseline contains 34 adopted Requirements. Exact current assessment and acceptance state must be read from the latest commissioning and correction records, not reconstructed from an older tranche in isolation.

## Deficiency, correction, and retest

Deficiencies remain governed records. A correction does not erase the prior deficiency or its evidence; it creates a traceable later state and requires proportionate retesting.

The commissioning sequence already demonstrates this pattern through separately governed deficiency findings, corrective tranches, targeted recommissioning, and later independent re-audit that weakened an earlier OPR-7.2 conclusion. That correction is evidence that commissioning is an evolving control process rather than ceremonial close-out.

Material later changes may require recommissioning of the affected requirements and dependent controls. A prior pass does not silently remain valid when its evidence, implementation, authority context, or operating conditions materially change.

## Acceptance discipline

Acceptance is evidence-based and belongs to the authority defined by the governed record. Product Owner acceptance must not be inferred from an agent recommendation or a stored record whose semantics reserve the answer to a human.

Accepted residuals remain documented, attributable, and open to later reconsideration when new operational evidence warrants it. Acceptance is not deletion of the deficiency history.

## Punch List boundary

Do not create a separate canonical `PunchListItem` or Punch List UI merely to express commissioning deficiencies. Existing `Requirement`, `RequirementAdjudication`, `Finding`, `Disposition`, and optional `Task` records already support the underlying deficiency and close-out meaning.

A future Punch List may be a projection over those canonical records if separately authorized. It must not become a parallel deficiency system.

## Relationship to Trust and Security commissioning

[GO-TRUST-SECURITY-01](GO-TRUST-SECURITY-01.md) remains distinct. Trust/Security commissioning is a specialized future commissioning domain with its own authorization, confidentiality, policy-intake, and testing boundaries. It may reuse the requirement → response → evidence → test → deficiency → correction → retest → acceptance discipline without being absorbed into general self-project commissioning.

## Relationship to Surface Trust

[GO-SURFACE-TRUST-01](GO-SURFACE-TRUST-01.md) remains distinct. Visual and interaction quality may be assessed against adopted Product Owner requirements where such requirements are actually governed, but aesthetic preference must not be retroactively converted into an OPR requirement. The accepted Deep Ocean baseline and pending Bauhaus/Constructivist live judgment retain their own authority and acceptance states.

## Current completion boundary

The current-baseline developmental commissioning sequence substantially assessed the adopted OPR and corrected identified deficiencies. It did not establish all forms of completion.

Preserve these current limits:

- OPR-7.2 is Partially Satisfied under the later evidence-boundary audit.
- Independent final commissioning remains outstanding.
- Substantial Completion and Final Completion are Product Owner or designated-authority decisions, not automatic consequences of test counts or agent assessment.
- Future material changes may reopen affected commissioning scope.

## Programme boundary

This preservation record does not authorize new commissioning runs, OPR changes, Requirement adjudications, application changes, Punch List UI, deficiency objects, security testing, or declarations of Substantial or Final Completion.

## Recovery status

**RECOVERY PENDING:**

- full original OPR prompt;
- exact original requirement-set and version history beyond the current governed adoption records;
- complete Product Owner acceptance history;
- original commissioning workflow prompts;
- historical commissioning and acceptance reports not already preserved canonically.

Do not invent these. Later recovered source material may enrich this record without replacing its stable identity, current OPR authority, correction lineage, or honest completion boundary.

## Exact prompt text

```text
ARCHIOSK/GO should itself be commissioned against its Product Owner requirements rather than relying only on feature completion or passing tests.
```

## Execution references

- Run: `CLAUDE-POSTCAMEL-COMM-A1` through `CLAUDE-POSTCAMEL-COMM-I6`, with later correction under `CLAUDE-POSTCAMEL-CONTINUE-01`
- Result: Adopted OPR and substantial developmental commissioning record established; identified corrections and retests governed; final independent commissioning remains outstanding
- Commit: See current commissioning governance and repository history; exact full acceptance history recovery pending
