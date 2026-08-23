# CODEX-NORTH-BAYVIEW-TO-PROJECT-NORTH-STAR-01 — North Bayview → Project North Star Transition

| Field | Value |
|---|---|
| Prompt ID | CODEX-NORTH-BAYVIEW-TO-PROJECT-NORTH-STAR-01 |
| Title | North Bayview → Project North Star Transition |
| Agent | Codex |
| Status | RUN |
| Purpose | Authorize a later controlled transition from the current North Bayview proving project to the canonical Project North Star proving project/template after review of Claude's smarter Spin. |
| Product Owner acceptance | Explicitly approved by the Product Owner in the preserved direction below. |
| Lineage | Transition authorization related to [CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01](CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01.md); its first advancement cycle must follow that Spin-led rule. |
| Superseded by | None |
| Absorbed into | None |

## Governing interpretation

- North Bayview is the current proving project.
- After the smarter Claude Spin is reviewed, Codex should perform the controlled transition from North Bayview to **Project North Star**.
- The rename/recast must preserve repository integrity, test references, blindness protections, oracle separation, and historical lineage.
- The transition is not merely cosmetic: Project North Star is intended to become the canonical ARCHIOSK/GO proving project/template.
- The first advancement cycle after transition must begin with the issues surfaced by Claude's Spin, in accordance with `CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01`.
- Codex may continue broader repository-grounded advancement after those mandatory Spin-surfaced issues are addressed.
- This authority does not permit tuning Project North Star to oracle answers or weakening blind-discovery controls.
- This preservation operation does not perform the rename/recast or reconstruct a broader North Star programme record.

## Exact prompt text

```text
After this Spin, ask Codex to rename the project and start advancing it according to the Spin result by Claude.
```

## Execution references

- Run: Live operator transition, 2026-08-23, performed by Claude on explicit
  Product Owner direction rather than by Codex — the addressee recorded above.
  The prompt's own precondition ("After this Spin") was satisfied first: Spin was
  repaired under `PSD-SMOKE-01-D` (commit `cefcf61`, deployed), a First Spin
  completed and was frozen as run `630beea5-911f-456e-b91a-fd3ea43ea1ef`, and the
  Product Owner reviewed it before authorizing this transition.
- Result: The live proving project `547e8455-d388-467d-9e60-1bc497681c86` — named
  "North Bayview production project" in
  [`../specified-unbuilt/navigation-context-operational-map.md`](../specified-unbuilt/navigation-context-operational-map.md),
  which is what distinguished it from the temporary acceptance project
  `2e918a07-…` recorded in `CONTINUATION_CHECKPOINT.md` — had its `display_title`
  changed from "North Bayview Courthouse" to **Project North Star** through the
  existing governed `CaseWorkspaceStore.set_project_details` path
  (`POST /projects/<id>/workspace/details`). Presentation only.

  Identity proven preserved across the transition: same UUID; 55 Sources before
  and after with their own names untouched (still
  `RFP-27-114-North-Bayview-Courthouse.pdf`); same owner, allow-list and
  `operating_environment`; same 3 Spin runs (`f64383a5`, `391dde7c`, `6807954f`);
  governance history intact at 119 events plus one new, legitimate
  `project_details_updated` event. **Project North Star is the same governed
  project previously known as North Bayview — a current-identity change, not a
  reset and not historical revision.**

  Historical references to "North Bayview" throughout the repository were
  deliberately left intact: they describe work that genuinely happened under that
  name, and rewriting them would falsify provenance against constitutional
  invariant #3.
- Commit: The live transition is project data, not repository content; this record
  is its durable trace. The prerequisite Spin repair is `cefcf61`, and the first
  Spin-led advancement under
  [`CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01`](CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01.md)
  is `7e80c57` (Spin execution timing), deployed the same day.
