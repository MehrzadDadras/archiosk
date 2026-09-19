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
