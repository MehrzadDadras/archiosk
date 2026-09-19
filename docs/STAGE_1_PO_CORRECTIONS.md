# Stage 1 Product Owner corrections

Stage 2 remains closed pending Product Owner use and direction. This correction
extends the existing Stage 1, deployed from `900a48c1490f67b93a7a543ebc6d9fa850b9c2d6`.
No protected worker or datum file is changed. No schema migration is required.

## Product Owner entry and workflow

Sign in as administrator, enable Developer Mode, and enable **Observe my real
requests** at `/admin/survey-evaluation`.

Castille source review:
`/projects/9c00eeec-4e65-4bde-bcea-de8b09c8beb1/sources/c590314b-f7b7-491a-addc-e2217ec92da9/review`

1. Click **Re-evaluate reviewed source** to retain the current consumer result.
   This is an explicit deterministic action; it does not rerun OCR or a model.
2. Inspect the original, rectified-view status and Survey Reference. Select four
   corners of a visibly rectangular document region in TL/TR/BR/BL order, enter
   an explicit display aspect, reading rotation and reason, then create the
   qualified rectified view. Re-evaluate separately to consume that premise.
   Castille has local paper bends: one homography cannot flatten these. Some page
   edges are outside the capture. Do not invent complete-sheet corners.
3. In structured readings, inspect the anchored title-block date. Machine evidence
   `e10f76e4-7282-47d4-a4a9-2f075e2a028f` reads `DATED: JANUARY 24, 1056`.
   The retained source visibly reads 1956. Propose the source-verified correction,
   inspect before/after/diff/anchor, accept, and re-evaluate. Revert and re-evaluate
   again to demonstrate retained history and removal from current consumption.
4. Inspect **Orientation/North**, **Document frame**, and **Building front/frontage**.
   Reading orientation does not establish North; entrance evidence cannot establish
   a regulatory front lot line. Applicable municipal and parcel premises remain
   unresolved; disagreement is not automatically a contradiction.
5. Reload repeatedly. The selected source, accepted consumer result and history
   remain unchanged. The runtime-trace link identifies each fresh read request.
6. Open `/document-shop/jobs/9c00eeec-4e65-4bde-bcea-de8b09c8beb1` to inspect grouped
   unresolved findings, the ordinary consumer and concise Ask GO privacy statement.

An isolated alternative is **Photographed document frame and anchored
transcription review** (`source-review`) at `/admin/survey-evaluation`.
Its source contains `Sheet: A-203`; the explicit machine-input fixture reads
`Sheet: A-2O3`. All writes remain EVALUATION_INPUT. The **access** case supplies
reviewable public-access premises; after confirming and explicitly reviewing the
source, a candidate building front can be qualified while regulatory frontage
remains unresolved. Existing **ambiguous-north** and **missing-monument** cases
continue to expose unresolved/refusal behavior.

## Architectural changes and limits

- Capture coordinates, document display frame, sheet rotation, geographic North
  and survey geometry are distinct. The existing spatial compiler computes H;
  Pillow samples a derivative PNG. Original bytes/hash are retained.
- A rectangle/aspect is a human display premise. Rectification does not establish
  Euclidean angles, physical scale, legal boundaries or survey authority. North
  measurements remain inspectable as capture-frame observations.
- Corrections and accept/revert actions are immutable appended EvidenceItems with
  original source/page/region/object pointers, machine-content digest, reviewer,
  timestamp and reason. Arbitrary JSON/authority edits are not accepted. Structured
  regions are prioritized, with original machine readings still inspectable.
- Explicit re-evaluation uses the existing visual/currentness/access/Survey
  Reference owners. It records a qualified consumer snapshot in the same store;
  the ordinary Survey Reference content type and derivative revision convention
  remain active. The snapshot is consumption, not an independent evidence graph.
- Read certainty can improve; the original effective binding ceiling and authority,
  applicability, precedence and currentness are not automatically promoted.
  Conflicting accepted corrections and changed original readings refuse evaluation.
- Changed review premises mark the retained consumer stale; re-evaluation is
  required. Whole-page OCR is not overwritten by a region correction; downstream
  text explicitly identifies reviewed regional readings and their evidence IDs.
- Survey Evaluation GET reads a saved consumer snapshot. Legacy runs or changed
  workspace versions require explicit re-evaluation. GET does not render/write PDF
  or IFC. Currentness/admission projections elsewhere remain read-only consumers.
- Geometric reconstruction retains the observed capture positions. A display warp
  does not rebind dimensions or regenerate a parcel in a stronger geometric frame.
- Source correction is Admin + Developer Mode plus existing project/case visibility.
  Evaluation and real project storage remain separate. No source auto-promotion.

## Qualification record

Implementation SHA, deployment SHA, frozen full gate and live verification are
recorded in the delivery closeout after qualification. Local browser proof is
explicitly distinguished from authenticated deployed browser proof.

Local browser command:
`python tools/verify_source_review_ui.py --output instance/source-review-ui`

Live command, only with an existing human-issued `ARCHIOSK_VERIFICATION_URL`:
`python tools/verify_source_review_ui.py --live --output instance/source-review-live`

The live verifier mutates isolated evaluation data only and reads Castille. It
never issues verification credentials. Operational traces are not evidence.

## Delivery closeout — 2026-09-19

Implementation and deployed SHA:
`73b8d752d4d798f04724b8161f68026f5c3de763`.
This closeout is a subsequent documentation-only update.

Qualification:

- Focused run: **351 passed, 87 subtests passed**. Final-change checks:
  **32 passed, 20 subtests passed**.
- Frozen authoritative full gate, parallel `-n 8 --dist loadfile`:
  **9,538 passed, 5 skipped, 14 warnings, 10,067 subtests passed**, 785.07 seconds,
  `PYTEST_EXIT=0`. All **1,136 frozen file hashes** were unchanged after the gate.
- Two skips were sandbox-denied symlink creation. Both containment tests passed
  with the required filesystem access: **2 passed**. The other three skips match
  the baseline count. No implementation/test edits were made during the full gate.
- A separate pixel check mapped four distinctly colored skewed-source landmarks
  to their expected rectangle corners and preserved the source bytes.
- Chromium exercised actual Flask forms in an isolated local runtime: sign-in,
  evaluation creation, four-corner picking, persisted preview display, correction
  proposal, accept, explicit re-evaluation, Reload, revert and re-evaluation.
  No browser errors. Reload preserved both visible state and persisted workspace
  bytes. The trace records actual invocation of image_intake, spatial/reference
  consumers, document_examination and CaseWorkspaceStore owners.

Retained local proof:

- `instance/stage1-focused-final.log`
- `instance/stage1-focused-delta.log`
- `instance/stage1-full-gate.log`
- `instance/stage1-frozen-tree.json`
- `instance/source-review-ui/proof.json`
- `instance/source-review-ui/runtime-traces.json`
- `instance/source-review-ui/source-review.png`

Example **local** UI re-evaluation trace:
`a63840852dd34d419f488b48ab707cb6`, in the retained runtime-traces file. This is
not a production trace or project evidence. Local temporary evaluation IDs are
not live links.

Deployment and live checks:

- Exact archive SHA-256:
  `616aea0c07be7f1ca8d74cefaf13637676558fd723c6079b25531b07e39ff19b`.
- **1,132 deployed archive files checked; zero mismatches.** Environment bytes
  preserved. No schema migration or canonical-project backfill was performed.
- Web, perception and visual services restarted and active. Service description
  reports the implementation SHA above. Public health returns 200; new source
  review JavaScript returns 200. Both protected review routes return 302 to sign-in
  without an authenticated session.
- Read-only inspection through the deployed document_examination owner found
  **54 structured Castille fields**. Source/evidence counts remain **2 / 42**.
  Its document frame is `UNRECTIFIED`, angles `UNRESOLVED`, metric scale
  `NOT_ESTABLISHED`, as required before new premises enter.
- Castille original SHA-256 before and after deployment:
  `3b2dd9dcca1ae79a55d2f91d9fb1acc24edf6b2b857ea9606e31a0147a301e98`.
- Rollback retained at
  `/var/www/archiosk-backup-900a48c1490f67b93a7a543ebc6d9fa850b9c2d6-before-kernel-73b8d752d4d798f04724b8161f68026f5c3de763`.

Activation ladder:

| Level | Proof and scope |
|---|---|
| IMPLEMENTED | Qualified exact implementation SHA above |
| REACHABLE | Real/evaluation routes; local signed-in browser; deployed sign-in gates |
| INVOKED | Actual local UI actions and retained owned-call traces; live read-only owner inspection |
| CONSUMED | Explicit review result and ordinary Survey Reference consumers exercised locally |
| SURFACED | Actual browser previews, correction/diff history, states and groups |
| END-TO-END OBSERVABLE | Proven in local browser runtime; authenticated deployed browser proof pending |

Authenticated production UI invocation is **not claimed**. No maintainer-issued
verification URL was supplied. `services/verification_access.py` reserves issuance
to a human maintainer; no account, token or production session was manufactured.
The Product Owner can now perform the workflow above with their ordinary account.
Stage 1 acceptance remains pending that re-test; Stage 2 has not begun.
