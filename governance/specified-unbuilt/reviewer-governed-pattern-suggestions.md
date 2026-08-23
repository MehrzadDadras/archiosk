# Specified But Unbuilt — Reviewer-Governed Pattern Suggestions

**Status:** Specified, not implemented. Produced during CLAUDE-P40-E's
Unified Document Workspace stage; deliberately excluded from that
stage's implementation for two independent reasons — a real
governance-authorization question this document surfaces rather than
resolves unilaterally, and genuine scope/time constraints on top of
everything else that stage already shipped.

> **Authorization update (CLAUDE-REVIEWER-PATTERN-01, 2026-08-23). The review
> this document demanded has now happened.** Section 0 below required that the
> personal/project-scoped version not be built "without that review actually
> happening"; it was conducted as a bounded authorization review and decided by
> the Product Owner.
>
> **Reviewed and found distinct.** A pattern a reviewer saves for their own
> later use inside the same project crosses no project, organizational,
> procurement/adversarial-party or authority boundary, and
> `prompt-depository/GO-EXPERIENCE-CORPUS-01.md` — a Product-Owner-accepted
> record — already lists this document under **"Related, not absorbed."** The
> reasoned position in Section 0 is therefore confirmed rather than assumed.
>
> **Authorized, narrowly:** the personal/project-local slice only —
> `scope = personal`, one reviewer, one project, deliberate authoring, no
> sharing transition of any kind. Implemented as
> `ProjectWorkspace.saved_patterns_by` with
> `CaseWorkspaceStore.save_reviewer_pattern`/`reviewer_patterns_for`/
> `retire_reviewer_pattern` (`services/case_workspace.py`), guarded by
> `tests/test_reviewer_pattern_01.py`.
>
> **Everything cross-boundary remains unauthorized, unchanged.** The Experience
> Corpus stays NOT AUTHORIZED in all forms per `STATUS.md` and
> `GO-EXPERIENCE-CORPUS-01`; the adversarial-party eligibility check,
> cross-project isolation, the no-person-ranking rule and evidence-authority
> boundaries are untouched and unweakened by this authorization. Section 1's
> unconditional exclusion of organization-wide and cross-project reuse still
> stands in full — there is still no organizational authorization boundary
> capable of enforcing "who else may see this."
>
> **Not built, deliberately:** any UI or route. This authorization covers the
> storage seam and its guards only; surfacing a pattern back to a reviewer is a
> separate, later decision.

## 0. Why this exists, and the governance tension it surfaces

CLAUDE-P40-E asked for machine-identified "recurring investigation
methods... reusable review patterns" surfaced compactly above the
conversation composer, with a reviewer choosing Save Pattern / Edit
and Save / Not Now / Dismiss — explicitly scoped down to personal/
private and current-project scope only, explicitly excluding
organization-wide or cross-project promotion "unless the repository
already contains an adequate organizational authorization boundary,"
and explicitly invoking the principle "Archiosk may learn how the
reviewer investigates without learning what the reviewer must
conclude."

That principle is a near-verbatim restatement of this repository's own
existing, ratified **Experience Corpus** concept
(`governance/specified-unbuilt/cross-boundary-architecture.md`'s own
"BEEHIVE may learn how to investigate without learning what to
believe"). Critically, `governance/STATUS.md`'s own domain-model
feature-authorization table lists **"the Experience Corpus (all
forms)" as NOT AUTHORIZED — specified only**, and this repository's
own CLAUDE.md is explicit that this table governs: "code implementing
something marked NOT AUTHORIZED is a defect, not evidence the table is
outdated." Building this feature during CLAUDE-P40-E, without first
resolving whether it falls inside that prohibition, would have risked
exactly that defect.

**The scoping distinction this document draws, for whoever picks this
back up:** `cross-boundary-architecture.md`'s own Experience Corpus
section is specifically about the CROSS-PARTY, PROMOTED, shared corpus
— its own described pipeline is "private/local investigative activity
→ generalization/abstraction → confidentiality/re-identification check
→ adversarial-party eligibility check → authorized promotion →
Experience Corpus." A pattern that a reviewer saves for themselves, or
for other reviewers already authorized on THIS SAME project, that
never leaves the project and never enters any promotion/generalization
pipeline, is not that mechanism — it never crosses the project
boundary the Experience Corpus's whole design exists to govern. But
this document does not consider that distinction self-evidently
settled; it is a reasoned position for the next stage's own explicit
review, not a unilateral green light. **Do not build the personal/
project-scoped version of this feature without that review actually
happening** — this document exists specifically so the review has
something concrete to evaluate, not so it can be skipped.

## 1. What's already ruled out, unconditionally

Organization-wide or cross-project pattern reuse is out of scope until
`governance/specified-unbuilt/tenancy-and-project-authorization.md`'s
`Organization`/`OrganizationMembership` model actually exists — per
CLAUDE-P40-E's own instruction, and independently confirmed by
`STATUS.md` marking that whole model **NOT AUTHORIZED** alongside
Experience Corpus. There is currently no organizational authorization
boundary in this codebase capable of enforcing "who else may see this"
honestly beyond a single project's own owner/allow-list.

## 2. Domain model (proposed, not built)

```python
@dataclass
class SavedPattern:
    id: str
    project_id: str
    scope: str  # "personal" | "project" - see #1, never wider
    title: str
    description: str
    investigation_trigger: str          # what situation this pattern applies to
    proposed_sequence: list[str]        # the reusable steps/cross-checks themselves
    source_conversation_refs: list[str] # ConversationMessage ids this was drawn from - provenance, not a copy
    created_by: str
    created_at: str
    version: int = 1
    status: str = "active"  # reusable investigation METHOD - never "requirement"/"finding"/"decision"
```

`status` is deliberately restricted to a closed vocabulary that can
never collide with `Finding.claim_status`, `RequirementAdjudication.
outcome`, or `Disposition.disposition` — Section H's own explicit
requirement that a saved pattern is "a reusable investigation method,
not a requirement, Finding, decision, or conclusion" needs to be
structurally true, not just documented.

## 3. What must NOT exist, structurally

- No automated promotion of a Dismissed/Not-Now suggestion into
  anything persisted — Section H: "Dismissed or rejected suggestions
  must not become accepted knowledge or hidden learning signals." A
  real implementation must not even log a rejected suggestion's
  CONTENT anywhere queryable later, only (at most) that a suggestion
  was shown and dismissed, for the same reason `services/
  learning_governance.py`'s own docstring already establishes for a
  different but structurally similar concern.
- No field that lets a `SavedPattern` be cited as evidence in a
  `RequirementAdjudication`, applied to a `Finding`, or referenced by
  `apply_findings` — it is real content a reviewer can consult, never
  governed project truth.

## 4. Suggestion generation - the part CLAUDE-P40-E's own instruction
already anticipated staying unbuilt

Section H itself: "If genuine suggestion generation requires an
external-AI path or governance decision beyond this stage, implement
the reviewer-controlled proposal/save structure and use deterministic
test suggestions only in tests. Do not simulate production
intelligence." No heuristic or AI-based "recurring pattern detector"
exists in this codebase, and building one - even a simple deterministic
keyword-repetition heuristic - is real product/AI-integration work of
its own, not a byproduct of building the save/approve persistence
layer. Whichever stage builds this should default production behavior
to "no suggestions surfaced yet" (an honest empty state) rather than a
weak, half-real heuristic presented as if it were considered
suggestion generation.

## 5. Route/template wiring (proposed)

`routes/workspace.py`: `save_pattern` (POST, manual reviewer-authored
save - title/description/trigger/sequence entered directly by the
reviewer from a conversation excerpt, no auto-generated suggestion
required to exercise this path at all), `list_saved_patterns`,
`edit_saved_pattern`. All gated through `_load_workspace_or_404`
(Section H: "Support only scopes that existing authorization can
enforce honestly" - project-level access is the ceiling; "personal"
scope would need to additionally filter by `created_by == reviewer`,
enforceable today without any new authorization primitive). A new
"Saved Patterns" entry belongs in the unified nav's Decisions &
Governance group (`templates/base.html`), alongside Accepted
Knowledge.

## 6. Tests a real implementation would need

A saved pattern requires all of title/description/trigger/sequence/
source refs/reviewer identity/timestamp/scope/version (Section H's own
field list) - a partial save is rejected, not silently defaulted.
Personal-scope patterns are invisible to a different authorized-but-
non-creating reviewer; project-scope patterns are visible to every
project-authorized reviewer, never beyond. Dismissing a suggestion
persists nothing queryable. No route or store method allows a
`SavedPattern` to be referenced from `RequirementAdjudication.
evidence_finding_ids`-equivalent fields or `apply_findings`. Production
`GET` shows no suggestions unless a real (future) generation path
explicitly provides them; a deterministic canned suggestion is used
only in tests, clearly out of the production code path.
