# Operational convergence record mapping

The optional operation-level derivation is documented in
[OPERATION_EVIDENCE_RULES.md](OPERATION_EVIDENCE_RULES.md). Export it with
`--frontier`; the default legacy snapshot and normalized records remain unchanged.

Status: read-only foundation; Flight Deck health UI gated on material evidence.
Authority for this tranche: Product Owner, OPERATIONAL CONVERGENCE RECORD MAPPING
+ PLUGIN SEAM + FLIGHT DECK FOUNDATION 01. No Assessment or promotion authority.

## Reader contract

Adapt the reader to history. Evaluator paths, names, seals and malformed outputs
are immutable. `services/convergence_projection.py` is the Gym-owned adapter,
called by the existing `services/cognitive_gym.py` projection and exporter. It
uses the same bounded Reader and has no registry, provider or execution API.
No new persistent authority store is introduced.

Discovery includes `GO-COGNITIVE-GYM*`, `COGNITIVE-GYM-*`, and other immediate
evaluator directories explicitly containing `records/development-record.json`,
`frontier-ledgers.json` or `stage-checkpoints.json`. It does not recursively
ingest unrelated application registries, private assessment stimuli or tools.
Discovery is a declared boundary, not a claim that arbitrary future formats
will be understood without an adapter.

## Record-family taxonomy

| Family | Recognized retained surfaces | Interpretation |
|---|---|---|
| ENCOUNTER | `records/*-result.json`, `examiner/*-complete.json`, first `examiner/development-record.json` with `raw_response` | One response observation; invalid remains unscored |
| DEVELOPMENT_SUMMARY | `development-record.json`, per-exercise development records, `cycle-results.json` | Summary, never counted as duplicate encounters |
| OBSERVATION | `*-observation.json`, behavioral feedback | Examiner task/content observations separate from execution form |
| APPRENTICESHIP | `intervention-record.json` | Explicit GO/GOtex action capsules; teaching causation not inferred |
| STAGE_CLOSEOUT | `*-stage-closeout.json`, `stage-checkpoints.json` | Bounded stage evidence and limits; not certification |
| STOPPED | `*-STOP.json`, `stopped-result.json`, `termination.json`, `authority-boundary.json` | Instrument, material and governance stops preserved |
| QUALIFICATION | qualification results, preflight, qualification final results | Instrument proof, never cognitive Assessment |
| SPECIMEN | specimen verification/acquisition records, approval-gate presentation | Application specimen/provenance; no GO encounter implied |
| SEAL | root/examiner/records seal JSON | References to preserved seals; displaying a seal is not requalification |
| INSTRUMENT_FINDING | instrument/baseline, contract verification, teaching review | Instrument and response-form limits |
| FRONTIER | `frontier-ledgers.json` | Explicit recorded frontier statements; narrative is not a matrix coordinate |
| HANDOFF | retained `stable-handoff-evidence.json` and handoff summaries | Captured handoff evidence; repository presence/deployment is not trainability |
| TRANSFER | `transfer-record.json` | Recorded attempt/activity, not transfer competence |
| ASSESSMENT | explicit `assessment-record.json` | Only explicit completed/valid Assessment records count |
| ADAPTIVE_DECISION | `*next-developmental-move.json` | Recorded proposals, not execution |

Supporting material/observation/dispatch/plan records are joined to encounters.
Source references are relative paths with content hashes. Seals can refer to
files outside the display allowlist; those files are not opened for display.
Root/examiner reports remain accessible in the legacy authorized surface.

## Attribution

Explicit result, material and observation attribution must agree. Conflicting
or unsupported values resolve to UNRESOLVED, never C01. For older records only,
an explicit C01-C28 directory token may supply a labelled **legacy association**;
it never overrides explicit record evidence. A block's `primary` is not assigned
to all its encounters. Multi-capability sessions appear under their actual bars.

Actor aliases GO, GOTEX/GOtex and GO teaching modes are normalized. Legacy
intervention action capsules can establish actor only when the audited request
identity, exact raw text and its SHA256 match the result. Raw equality or phase
names alone do not establish actor. Summary
records are EVALUATOR; this does not attribute an underlying model encounter.

## Normalized schema and limits

Each row carries: `record_family`, `record_id`, `capability`, `actor`,
`application_capability`, `task_kind`, `control_type`, `task_content_result`,
`contract_compliance`, `instrument_validity`, `application_defect`,
`governance_boundary`, `model_baseline`, `handoff_reference`,
`application_frontier_state`, `go_development_frontier_state`,
`shared_frontier_state`, `gap_owner`, `timestamp`, `evidence_refs`,
`qualitative_band`, `unresolved_fields`. Additional fields retain attribution
basis, source statements, raw response, band reason and operator-risk evidence.

Missing properties remain UNRESOLVED. Narratives are retained as narratives;
they are not silently converted to STABLE or RELIABLE. Contract INVALID always
suppresses task alignment and marks scoring UNSCORED. Delivery validity remains
separate: a malformed response does not itself mean an application defect.
Unrecognized instrument narratives are INDETERMINATE with exact text retained.

Operator risk PREMATURE COMMITMENT is supported only by an explicit examiner
observation describing compound commitment and recognition of unsupported
options. It is not inferred by mining raw model prose or made into a new bar.

Bands are per-observation diagnostic labels, not capability promotions:

- BLOCKED: explicit invalid response contract; reason and source linked.
- FRAGILE: valid negative/null encounter explicitly marked misaligned.
- UNRESOLVED: insufficient governed evidence for a stronger interpretation.
- EXCELLENT, GOOD, ADEQUATE, POOR and UNTESTED are reserved vocabulary. No
  thresholds or invented averages manufacture these bands in this tranche.

## Determinism / snapshots

Same source bytes produce the same projection. File modification time is not
evidence time. Missing recorded timestamps stay unresolved. `generated_at` now
means latest recorded evidence timestamp, not wall-clock scan time. The exporter
reports separate `snapshot_captured_at` and `snapshot_sha256` on stdout; preserve
that receipt with operational publication records. Normalized content also has
its own canonical `projection_sha256`. Neither hash confers authority.

The existing export command remains valid. Publication stays manual, outside the
evaluator. Old schema-1 snapshots still render the Gym but receive an explicit
warning if the convergence payload is absent. No production snapshot is
automatically overwritten. No static asset or customer route changes occur.

## UI eligibility

The gate derives blockers from missing/narrative frontier coordinates, absent
operation/shared-state evidence, unreadable records and unresolved encounter
attribution. The retained C11 frontier ledger records a real bottleneck but
does not supply per-operation stability/readiness coordinates, acceptance of
relevant negative controls or an auditable shared-state mapping for the full
product spine. A polished health matrix would invent those relationships.

Therefore the current tranche stops before Flight Deck UI. Preserve the three
frontier statements and unresolved fields for inspection. The next owner is
Codex for remaining read-model attribution work, with Claude supplying explicit
stable operation handoffs and Product Owner/governance defining any required
operation-readiness acceptance boundary. No training call is authorized here.
