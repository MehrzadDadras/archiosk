# Survey runtime convergence

Starting point: `7be48db41cc65aba9b238f77645f2808243ef327`; previously deployed
application `3dfe1f8849949122fca60e5d33fbe1f48af25e7a`.

The existing Survey Evaluation surface remains the inspection entry. Enable
“Observe my real requests”, open a listed project/document, use its ordinary
controls, then return to inspect the recorded request. A trace is operational
provenance, never an EvidenceItem, admission decision or source of authority.

`runtime_observation.observed` wraps actual owned functions. It records INVOKED,
RETURNED/RAISED, existing result states and identifiers. Flask hooks record the
real endpoint and response. The provider boundary records the actual textual
input and provider output separately from final admission. API keys and image
bytes are excluded. Opt-in requires administrator access and Developer Mode;
inspection uses the same boundary. No resolver is executed by the trace reader.
Stored observations live under `instance/runtime_observations`, outside registry
and canonical evidence storage. Observed visual enqueue calls retain a bounded operational correlation marker.
The real worker entry reads that marker and records its own execution, linked
to the observed enqueue request. A queued job is never labelled INVOKED until
its worker actually executes; unrelated background work is not claimed.

## Shared admission and consumers

`CaseWorkspaceStore.admit_proposition` projects existing evidence trust,
currentness, binding and calculated geometry. Text is SOURCE_REFERENCE; an AI
reading is PROPOSAL. Neither is established merely because stored/readable.
Evaluation provenance follows premise IDs transitively. Geometry projection
continues to require scoped addressing, reviewed relationships, finite results
and current, uncontested premises. There is no second evidence graph.

Document Ask GO, workspace conversational turns and the existing project Q&A
fallback carry governed states. Free provider prose remains a proposal; the
admitted factual answer uses governed statements and explicitly attributed
source material. This intentionally bounds generative answers where proposition
admission is available. It does not turn an observation into certification.

Canonical `IFCVolumeValidator.export` and `compile_to_ifc` require current
admission covering every numeric owner field, matching plane/value, WORLD_SCALED
METRIC_SCALED qualification and applicable contractual/project-agreement source
authority. The bounded canonical path requires explicit METRE units in the model
and its premises and emits the SI length unit without conversion. Missing
coverage, uncertain premises or evaluation provenance refuse.
The project IFC route also uses the existing export security policy. A numeric
serializer remains a diagnostic implementation, not an active canonical fallback.
Explicit evaluation export remains labelled EVALUATION_INPUT and separate.

Traverse computations retain binding and unresolved authority. Every computed
primitive remains qualified; unresolved curves carry DISPLAY_APPROXIMATION on
the actual primitive/visible tag. Existing layer support is activated for all retained layers. Source-position
rendering is explicitly distinguished from calculated traverse coordinates.
SVG and PDF use the same resolver and carry qualifications.

## New deterministic capabilities in existing owners

* `survey_graph.derive_survey_operation`: identified found/recorded monument
  correspondence. Identity is required; proximity cannot replace it. Missing
  observations remain unresolved. Correspondence does not grant legal authority.
* Same owner: occupation point versus record segment, using Rule 7 projection
  in an explicitly comparable Euclidean chart. Agreement/difference is geometric,
  not a boundary adjudication. No averaging, closure adjustment or record erasure.
* `spatial_compiler.estimate_control_homography`: four coplanar, identified
  controls using existing 3x3 inverse/product primitives. Rejects non-finite,
  degenerate, weakly conditioned and failed residual/round-trip results. Tolerances
  come from `ToleranceContext`; no new geometry library or dependency.
* The evidence owner requires addressed direct correspondence evidence, image
  checksum and independent affine-frame evidence. H is calculated, persisted as
  an existing calculated EvidenceItem, related to every premise, then reviewed.
  Target frame may be affine; Rule 7B's conservative PROJECTIVE kernel level is
  preserved. Physical scale, Euclidean metric authority and legal authority are
  not earned by this producer. Automatic control extraction is not implemented.

Ordinary project routes under `/projects/<id>/workspace/survey/` register control
observations, invoke derivation and check IFC admission. Existing project access,
CSRF, administrator/Developer inspection and export policy apply. The same
`_survey_operations.html` form is used from the project and inspection surfaces.
There is no live-mode interpreter. Controlled cases call the same domain owner
in their isolated registry, retaining EVALUATION_INPUT through review.

The same project form can register explicit human observations against an
existing source page: situated object, recorded/found/missing monument, occupation
point, record segment, or an independently evidenced affine frame. It uses the
existing AddressableRegion/EvidenceItem registration methods. Defaults are
UNRESOLVED; source checksum, source region, separate read/bind declarations and
provenance are retained. Input registration grants no authority or physical scale.
No missing monument point, correspondence identity or target control is inferred.

Protected `perception_worker.py` and `datum_corroboration.py` remain untouched.
No migration or unrelated Planning/Feasibility changes are included.

Qualification/deployment results are recorded after the frozen-tree gate and
live verification, not inferred from the implementation description above.

## Qualified and deployed result — 2026-09-19

Implementation and deployed SHA: `c1ffa6c82de2cce205379741c1c149e6f5235924`.
The increment starts at `7be48db41cc65aba9b238f77645f2808243ef327` and comprises
`9b46eff`, `bb3757b`, `5f06a9d`, and `c1ffa6c`. All are pushed to origin/main.
This proof documentation is a later documentation-only commit, not a new deployed
application build.

### Qualification

The final clean committed tree was frozen throughout the authoritative gate:
`pytest -q -n 8 --dist loadfile` returned **9,520 passed, 3 skipped, 14 warnings,
10,035 subtests passed; PYTEST_EXIT=0**, in 789.74 seconds. Local retained log:
`instance/convergence-full-04.log`. No implementation edits occurred during it.
An earlier complete gate on `5f06a9d` also passed with the same totals.

Focused green lanes are overlapping checks, not additive unique-test totals:

| Lane | Passed |
| --- | ---: |
| Workspace, IFC and runtime | 128 |
| Operational convergence | 20 |
| Conversation, runtime, evaluation and provider failure | 155 |
| Project input, runtime, evaluation and provider | 130 |
| Expanded ordinary project input route | 1 |
| Final rendering, runtime and evaluation | 102 |
| Projection, evidence and Survey Reference | 81 |

Candidate failures were classified before proceeding. Direct Ask GO callers with
a lightweight app object exposed an app-context compatibility issue; optional
explicit app configuration repaired it while preserving provider-failure behavior.
An earlier full gate encountered an existing Windows multiprocess storage-bridge
unlink sharing violation (WinError 32). No bridge implementation or test was
changed or skipped: its focused recheck passed 25 tests/7 subtests and both later
full gates passed it. The first live verifier expected PARTIALLY_RECOVERED traverse
admission; actual admission correctly remained the stricter UNRESOLVED because
authority was unresolved. Only the verifier expectation changed. The calculated
record still preserves PARTIALLY_RECOVERED and CALCULATED_FROM_QUALIFIED_INPUT.

### Deployment integrity

The existing archive/rsync deployment mechanism deployed the exact committed
application. Archive SHA256:
`7d618037ecf9054041d2d72bed1c35429bbeefed6173a3d2ac781efdecf44623`.
All **1,122 archive files** matched deployed bytes; zero mismatches. The final
deployment dry run contained the two expected follow-up files and zero deletions.
Environment bytes remained identical to the original deployed backup; instance
data, environment, virtualenv and protected static content were excluded from sync.
No migrations, dependency changes or protected-worker edits were included.

GO, perception and visual services are active. Public `/health` returned **200**.
Service build description identifies the full deployed SHA above. Rollback copies
of `3dfe1f8` and `5f06a9d` remain outside the active application tree. Their retained
environment files are access-restricted; they are not alternate active runtimes.

### Actual live requests

The final browser verification passed **12/12 affected cases**, with zero browser
errors. It exercised real creation, review, consumer and inspection routes.
Anonymous evaluation access redirected (302); administrator access without
Developer Mode was refused (403). Temporary verification access was revoked and
its account residue checked to be zero.

| Case | Observed result | Retained run |
| --- | --- | --- |
| Qualified traverse | UNRESOLVED admission; qualified calculation retained | [Open](https://archiosk.com/admin/survey-evaluation/270812e8302f484890356792b6036b99) |
| Identified monument | ESTABLISHED scoped correspondence, no legal authority | [Open](https://archiosk.com/admin/survey-evaluation/97a74a0a9d044a669e102fdd2e8e741d) |
| Missing monument | UNRESOLVED; no invented point | [Open](https://archiosk.com/admin/survey-evaluation/60678a60a1ce49d787265790c088b09e) |
| Occupation versus record | Established geometric difference, no boundary adjudication | [Open](https://archiosk.com/admin/survey-evaluation/6125b50d37ae4778abc20636f951a79f) |
| Calculated H | Real estimator invoked; five premises; physical scale NOT_ESTABLISHED | [Open](https://archiosk.com/admin/survey-evaluation/287369d4b4af47dc8ddaf2e49aa9cb0e) |
| Degenerate controls | DEGENERATE | [Open](https://archiosk.com/admin/survey-evaluation/8abcd2d161054bb3b71d354d07a4390f) |
| Explicit evaluation H | Labelled evaluation IFC download 200 | [Open](https://archiosk.com/admin/survey-evaluation/c4b81618c47d403694bdb43a3ef01149) |
| No H | Refusal retained; IFC unavailable (404) | [Open](https://archiosk.com/admin/survey-evaluation/28b00943f9074d0fb67550898298ab7c) |
| Non-finite geometry | IFC unavailable; provider-backed Ask GO preserves height refusal | [Open](https://archiosk.com/admin/survey-evaluation/37b7db8fab60479fb7b31f0e3fcd9b9b) |
| Unresolved curve | Qualified actual SVG and PDF | [Open](https://archiosk.com/admin/survey-evaluation/5ca45192873641bf9e568ba96b10ed62) |
| Survey Reference | Actual SVG and PDF | [Open](https://archiosk.com/admin/survey-evaluation/317f4d95450d4cca83defcee483d2694) |
| Ambiguous North | Governed uncertainty retained | [Open](https://archiosk.com/admin/survey-evaluation/c1a027b1206a44a78e72739d2f275be2) |

These controlled cases remain EVALUATION_INPUT, including the calculated-H case.
The ordinary project routes invoke the same producers against real addressed
project premises; calculation does not promote their source authority.

The actual eligible project **226104 1 Castille** was opened through its ordinary
[document result](https://archiosk.com/document-shop/jobs/9c00eeec-4e65-4bde-bcea-de8b09c8beb1).
A real ordinary Ask GO request invoked the provider and returned an admitted
answer distinguishing attributed source material from unresolved propositions.
Its [recorded request](https://archiosk.com/admin/survey-evaluation?observation=7955fb51d66f400a94746ab395fc4de0)
exposes invocation, context, provider input/output and final admission. Result
request observation: `0c38cec1edec4ed983502ad8776dd7f0`.

Observed owners include proposition admission/trust, document examination,
document conversation, the LLM gateway, True North, access interpretation and
Survey Reference. Inspection reads these recorded transitions; it does not run
another interpreter. This live proof used existing recovered project evidence;
it does not claim a new live worker extraction. Worker correlation is separately
tested at the actual worker entry. Positive canonical customer IFC admission is
covered by focused tests, not claimed as a live customer export: the live positive
download is explicitly evaluation-only.

Local proof artifacts are retained under `instance/live-convergence-c1ffa6c/`:
`live-proof.json`, browser screenshots, `survey-reference.pdf` (4,653 bytes) and
`curve-reference.pdf` (4,842 bytes). The verifier is the committed
`tools/verify_survey_evaluation_live.py`. The established 61-case baseline was not
gratuitously repeated; the current catalog has 67 cases and the final affected
live selection above contains 12.

### Cutover, retained qualifications and scope

The numeric-only canonical IFC behavior is UNSAFE and retired from active
canonical use. `export_numeric_diagnostic` is a REQUIRED_FALLBACK serialization
primitive behind governed admission or isolated labelled evaluation, not a
competing authority route. Existing provider prose is retained for inspection as
a proposal; it no longer bypasses deterministic final admission. Source-position
rendering no longer claims to depict calculated traverse coordinates. No second
Survey engine, evidence graph, Ask GO channel or rendering engine was created.

Intentional qualifications remain visible: source quotations are not established
facts; computable traverses may remain UNRESOLVED; unresolved curves may be display
approximations; identity correspondence and geometric offsets are not legal
determinations. The H producer requires explicitly evidenced controls and an
independent frame. It does not automatically extract controls, calibrate a camera,
earn physical scale or certify a survey. There is no claim of universal professional
certification or proof of every possible project workflow.

### Product Owner workflow

1. Sign in as administrator, enable Developer Mode, then open **Developer Tools →
   Survey Evaluation** at `/admin/survey-evaluation`.
2. Enable **Observe my real requests** and select an eligible live project/source.
   Use its ordinary document result, Ask GO or Survey Reference controls.
3. Return to Survey Evaluation and open the recorded request. Inspect source and
   evidence references, actual invoked resolver, governed state, consumer result,
   and readable final admitted answer. Expand provider/context provenance as needed.
4. For new human observations, use the existing project survey form against a
   real source/page, retain explicit read/bind uncertainty, then use the existing
   review workflow. Derivation and IFC consult the same governed evidence.
5. Use controlled cases for repeatable positive/refusal conditions. Their isolated
   evaluation provenance remains visible and cannot authorize project IFC.
