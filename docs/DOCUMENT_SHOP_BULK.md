# Document desk bulk management

The existing `ProjectWorkspace` owns active/archive/trash state. Archive and Trash
use its existing removed boundary, preserving source/evidence identity and
qualification. Recovery is owner-only; expired Trash cannot be restored. The
7-day expiry is persisted when the user confirms deletion. The hourly
`archiosk-document-trash.timer` runs `tools/purge_document_shop.py`, which calls
the existing permanent deletion owner. Shared file references are preserved.
The previous immediate-erasure UI policy is superseded by this recovery policy;
the qualified erasure implementation remains the purge mechanism.

`/document-shop/jobs` is the active desk; `?view=archive` and `?view=trash` are
intentional retained views. All bulk selections are validated before any action,
including for administrator sessions: access to another person's case does not
permit bulk mutation. Selection lives in tab sessionStorage under a random login
scope. Reload performs GET and preserves only still-present selected rows.
Row-level Delete remains available while bulk live proof is pending.

Re-analysis queues new run IDs in the existing perception/visual queues for images
and PDF, and the existing founding parser queue for other formats, preserving
source IDs, original bytes/hash and prior jobs/evidence. The current OCR worker
may reuse prior text evidence under its existing idempotency rules; the visual
worker distinguishes an explicit new run from a replay at both its admission and
Survey Reference boundaries. Analysis history exposes execution dates, engine,
run/job/source IDs, source digest, state and produced evidence references.
Non-image re-analysis stores the parser output as analytical EvidenceItems, retaining
the existing registry document. External AI policy is checked before provider use.
The existing founding worker is activated by `deploy/archiosk-founding.service`.
Re-analysis does not strengthen authority merely because it ran again.

Comparison supports exactly two analyses with one original raster image each.
`document_examination.compare_document_analyses` invokes `region_comparison` on
the full normalized region and surfaces its actual changed/unchanged/unresolved
result. It preserves identities and qualification, mutates neither source nor
workspace, and makes no semantic matching/conflict/supersession claim. PDF,
multi-source and semantic comparison are not supported by this existing path.

Qualification: `tests/test_document_shop_bulk.py`, updated deletion regressions,
and `WSecondGate` exercise explicit re-analysis through actual workers.
`tools/verify_document_shop_bulk.py` drives actual upload and bulk forms with
CSRF enabled; `--live` requires human-issued verification access. Live mode only
acts on the two evaluation analyses it creates, leaving them in recoverable Trash.
The hourly purge may occur up to one hour after the recovery deadline.
