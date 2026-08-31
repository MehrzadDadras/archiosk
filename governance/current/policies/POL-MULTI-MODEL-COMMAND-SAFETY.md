# POL-MULTI-MODEL-COMMAND-SAFETY — Model Independence and Command Safety

- **POLICY ID:** POL-MULTI-MODEL-COMMAND-SAFETY
- **TITLE:** Model Independence and Command Safety
- **VERSION:** v1.0
- **STATUS:** CURRENT
- **SCOPE:** The relationship between external model engines and this system's
  authority, storage, decision mechanics, and egress boundary.
- **APPLIES WHEN:** A model provider is added, swapped, or removed; a model
  output is proposed as a basis for action; a delivery-model risk framing is
  applied; or anything is transmitted outside this machine.
- **DOES NOT APPLY WHEN:** No external engine and no external transmission is
  involved, and no authority claim is being made from a model output.
- **AUTHORITY:** Product Owner directive, 2026-08-30. Subordinate to
  [`../../constitutional-invariants.md`](../../constitutional-invariants.md),
  which governs wherever this policy and it overlap.
- **SUPERSEDES:** None.
- **SUPERSEDED BY:** None.
- **LAST REVIEWED:** 2026-08-30.

## How to read the status markers

Every substantive claim below carries one of three markers, because this
repository already maintains exactly this distinction in code
(`services/security_policy.py`'s `SECURITY_CLAIMS_REGISTRY`) and a policy that
blurred it would be less honest than the code it governs:

- **[IMPLEMENTED]** — true of the code today, with the reference named.
- **[SPECIFIED-UNBUILT]** — governed intent, no implementation yet.
- **[NOT CLAIMABLE]** — must not be asserted in documentation, UI copy, or
  sales material, because the system does not deliver it.

A policy is not a place to describe the system as one wishes it were.
Constitutional invariant 7 (*hypothetical is not authoritative*) applies to
this document as much as to project data.

---

## 1. Model-Agnostic Utility Principle

**The principle.** External LLM and vision engines — Anthropic, Google Gemini,
any future local or open-weights engine — are **stateless, interchangeable
utilities**. They are asked a bounded question and they return text. They hold
no state between calls, carry no memory this system treats as knowledge, and
are never the residence of anything the product depends on being true.

**[IMPLEMENTED] The dispatcher is real.** `services/llm_gateway.py` is a
genuine two-provider boundary: `PROVIDER_ANTHROPIC` and `PROVIDER_GEMINI` are
members of `KNOWN_PROVIDERS`, `call_provider_json` dispatches between
`call_llm_json` and `call_gemini_json`, and each provider SDK is imported
lazily so an absent optional dependency degrades rather than breaks
(`_import_google_genai` raises `ImportError`, which becomes a named
`skipped_reason`, not a failed read).

**[IMPLEMENTED] Core logic is local and does not live in the model.**
Extraction is local PyMuPDF vector and text work in `engine/pdf_extractor.py`,
driven by `services/sheet_vision.py`, which always completes its local
extraction and returns it whether or not any external call happens at all.
Coordinate logic, decision mechanics, and the governed object model are Python
and contracts in this repository, not prompt behaviour.

**Storage — stated accurately, because the directive's shorthand is not what
this repository actually runs.** Storage is **two** things, and neither is
PostgreSQL:

- **Flat JSON files** for the requirements registry and governance store
  (`services/requirements_registry.py`, `services/governance.py`). A
  SQLite-backed rewrite of this was **explicitly proposed and explicitly
  rejected**; `tools/dependency_fit.py`'s `flat-json-storage` rule encodes that
  decision and will `WARN` on any dependency requiring a database.
- **SQLite** via SQLAlchemy for the relational half — users, tokens, and the
  other `models.py` tables — at `instance/bhive.db` (`config.py`'s
  `DATABASE_URL`).

**PostgreSQL is not used anywhere in this system.** [NOT CLAIMABLE] as a
description of current storage. The only occurrences in the repository are an
illustrative CLI example in `tools/dependency_fit.py --database-type postgres`
and a mocked URI in `tests/test_backup_restore.py`. Naming it here would have
made this document assert an architecture that does not exist, and would have
sat awkwardly against the flat-JSON constraint above, which is a live decision
rather than an accident.

**The bounded exception to model-agnosticism, stated rather than hidden.**
Swapping a provider is *mostly* an adapter change, but it is **not** true that
it never touches governance. `services/security_policy.py` defines
`ACTION_GEMINI_VISION_REQUEST` as a **deliberately provider-named** action,
additional to `ACTION_EXTERNAL_AI_REQUEST` and never a replacement for it. That
was a considered choice: a new egress destination deserves its own gate rather
than inheriting one. So the honest rule is:

> Swapping the **engine behind an existing governed capability** requires only
> an adapter in `services/llm_gateway.py`. Introducing a **new external
> destination** requires its own governed action, its own gate, and its own
> entry in `SECURITY_CLAIMS_REGISTRY` — and always will.

Anyone reading "models are interchangeable" as "adding a provider is ungoverned
plumbing" has read this section backwards.

## 2. Command Hierarchy and the Anti-Politics Invariant

**The formal invariant.**

```
Model output  ->  Intelligence / Evidence / Proposal
Model output  -/->  Authority
```

A model's output may inform, evidence, or propose. It never authorizes. This is
not new policy; it is the operational restatement of **constitutional invariant
2** — *machine inference never silently becomes authority; increasing machine
knowledge never automatically increases machine authority* — and this policy is
subordinate to that invariant wherever they overlap.

**[IMPLEMENTED] AI models hold no administrative rank.** No model adjudicates
authority, modifies a governance contract, or promotes its own output to
governed truth. `CIC-SPIN-INTELLIGENCE v1.2` carries `no model-memory
authority` as a mandatory invariant, and
`current/situational-attributes-are-not-authority.md` governs the related
confusion of *what is selected or attached* with *what is authorized*.

**Bounded execution invariant.**

```
Execute  <->  Authority_human  OR  Authority_delegated        (E _|_ A)
```

Execution is permitted **if and only if** human authority or explicitly
delegated authority exists. The companion reading of `E _|_ A` is the one that
matters in practice: **capability is orthogonal to authority.** That a system
*can* perform an act contributes nothing toward permission to perform it, and
growing capability never narrows the gap. Consequential acts remain behind the
Approval Gate (`routes/workspace.py::_require_approval`) regardless of how
confident any model is.

**Model divergence is an analytical signal, never a vote.** Where two engines
disagree, the disagreement is evidence about the question — not a tie to be
broken by majority, seniority, or provider reputation. There is no quorum, no
casting vote, and no notion of a model being outranked. This is why the concept
is **Multi-Observer Shear** and not consensus: per `CIC-SPIN-INTELLIGENCE
v1.2`, Shear *"maps where distinct rational positions diverge and never
adjudicates between them, so divergence is not error, a party's position is not
scored, and no observer frame is ranked above another."* Constitutional
invariant 10 governs the same shape for authorities generally: conflicts
**surface**, they do not resolve silently.

**[SPECIFIED-UNBUILT] Multi-Observer Shear has no implementation.**
`CIC-SPIN-INTELLIGENCE v1.2` states this in its own words — *"Multi-Observer
Shear has no reference implementation yet — this contract governs a layer that
does not exist."* This policy governs how Shear must behave if built; it does
not report that anything computes Shear today. Note also the boundary that
contract draws: Shear is never Helix, must not share a name, vocabulary,
persisted field, or parser with it, and observer frames derive from a project's
own ingested contracts and roles — never from a hard-coded party set or a
delivery-model template, which is the direct constraint on section 3 below.

## 3. Delivery-Model Aware Risk Weighting

GO's risk framing varies with the delivery model, because the same fact carries
different consequence under different commercial structures:

- **RFP / Tender** — trace **unpriced obligation**:
  `Requirement -> Interpretation -> Risk -> Fee`. The question is what has been
  asked for that nobody has costed.
- **Construction Management** — trace **sequence integrity and downstream
  cascade**: e.g. `Geotechnical finding -> Caisson design -> Critical path`.
  The question is what a change here does three steps later.
- **IPD** — trace **interface shear across multi-party boundaries**. The
  question is where two parties' rational readings of the same interface
  diverge.

**[SPECIFIED-UNBUILT] as an automatic runtime behaviour.** Delivery-model DNA
is specified in `specified-unbuilt/perspective-and-contract-dna.md` and is not
a shipped engine that classifies a project and selects a risk lens on its own.
Recorded here as governed framing, not as a description of running code.

**The constraint that binds all three, and is not negotiable.**
Constitutional invariant 15: *Contract DNA must never masquerade as project
authority. A delivery-model template may suggest expected obligations; only the
actual, ingested project contract governs.* A delivery-model lens may direct
**attention**. It may never supply an obligation the project's own contract
does not contain, and a risk surfaced by the lens is a **proposal for human
attention**, which section 2 has already established is not authority.
Invariant 14 adds the matching limit: perspective may change what is shown or
permitted; it never changes what a Finding or Requirement *means*.

## 4. Data Sovereignty and Zero-Egress Safeguards

**This section states the target regimes and then reports honestly against
them. It does not assert compliance, and must not be read or quoted as a
compliance claim.**

### The safeguards that are real

**[IMPLEMENTED] Local-first extraction.** `services/sheet_vision.py` always
completes local PyMuPDF vector and text extraction first, and returns that
result whether or not `google-genai` is installed, whether or not
`GEMINI_API_KEY` is set, and whether or not the gate permits transmission. An
absent provider yields an honest `skipped_reason` on an otherwise successful
local read — never an import error, never a failed sheet read. The application
runs fully offline.

**[IMPLEMENTED] Fail-closed egress gating.** `ACTION_EXTERNAL_AI_REQUEST`
carries a floor of `DECISION_DENY`. `ACTION_GEMINI_VISION_REQUEST` is a
separate, additional, provider-named action with a floor of
`require_approval`. Installing the package and setting the key does **not** by
itself cause anything to be transmitted. `"external AI request gating (kill
switch)"` is `CLAIM_IMPLEMENTED_AND_TESTED` in the claims registry.

**[IMPLEMENTED] Egress minimization — and it is an allowlist, not a strip.**
The directive described stripping paths, client names, and project metadata
before an external call. The implementation is stronger than that, and the
difference is worth preserving precisely: `build_egress_digest` in
`services/sheet_vision.py` constructs the outbound payload from an **explicit
allowlist** — page ordinal, page dimensions, vector count, and for each span
its bounding box, font size, rotation, and content. That is all. A denylist
omits what someone remembered to omit; an allowlist cannot leak a field nobody
thought of.

What is deliberately excluded, each considered rather than merely absent:
`pdf_filename` and any path (*"a drawing filename is routinely the client's or
the project's real name"*), the document `sha256`, and span internals
(`font_name`, `color`, block/line/span indices). And `project_id`, Source id,
actor, and username are **not reachable from that module at all** — which the
code itself identifies as a stronger guarantee than remembering to leave them
out. Drawing content is fence-stripped against prompt injection
(`_strip_fence_tokens`) but never otherwise rewritten, because sanitizing a
drawing's own words would corrupt the evidence.

This serves the same control as the synthetic project identity in `CLAUDE.md`:
keeping the real client and project identity out of durable artifacts is
defeated if the same name is handed to a third-party API from the other end.

### The safeguard that is NOT real, stated plainly

**[NOT CLAIMABLE] Canadian data residency compliance.** PBMM, the TBS Cloud
Direction, Quebec Law 25, and FIPPA are legitimate **target regimes** for this
product's market. This system does not currently satisfy their residency
requirements, and this policy must not be cited as evidence that it does.

The repository is already explicit about this, in code, under test:

| Claim | Registry status |
|---|---|
| `regional/data-residency processing control` | `CLAIM_UNSUPPORTED` |
| `data never leaves a specific country` | `CLAIM_PROHIBITED_FROM_CLAIMING` |
| `no AI provider retention` | `CLAIM_PROHIBITED_FROM_CLAIMING` |
| `local AI only` | `CLAIM_PROHIBITED_FROM_CLAIMING` |
| `air-gapped operation` | `CLAIM_PROHIBITED_FROM_CLAIMING` |
| `external AI processing (Anthropic API)` | `CLAIM_CONFIGURED_DEPENDENT_ON_PROVIDER` |
| `external AI vision processing (Google Gemini API)` | `CLAIM_CONFIGURED_DEPENDENT_ON_PROVIDER` |

`SECURITY_CLAIMS_REGISTRY`'s own rule is that *"a claim not listed here should
not be made in UI copy, docs, or sales material"* — this document is docs, and
is bound by it. The Gemini entry goes further and names the exact trap:
nothing claims that drawing content is *"withheld, regionally confined, or
unretained by Google."* `tests/test_gemini_provider_01.py` and
`tests/test_security_policy_engine.py` assert these statuses, so a future
session cannot quietly upgrade one.

**What would close the gap** is named in
`specified-unbuilt/organizational-security-department.md`: *"genuinely routing
external AI calls through a region-pinned endpoint."* Until that exists,
residency is achieved only by the operator declining external transmission
altogether — which the fail-closed default already makes the resting state, and
which is a genuine and honest answer, but is **zero-egress operation, not
residency compliance**. The two must not be conflated: one is a deployment
choice, the other is an infrastructure control this system does not have.

---

## Compliance obligations

1. Adding a model provider requires an adapter in `services/llm_gateway.py`, a
   governed action and gate in `services/security_policy.py`, and a
   `SECURITY_CLAIMS_REGISTRY` entry. Never only the first.
2. No model output is promoted to authority, and no model divergence is
   resolved by consensus, ranking, or provider preference.
3. No residency, retention, or locality claim is made anywhere in the product
   or its documentation unless `SECURITY_CLAIMS_REGISTRY` supports it. If the
   registry and a document disagree, **the registry governs and the document is
   the defect.**
4. Any change to the egress allowlist is a governed change to the security
   boundary, not a refactor.
