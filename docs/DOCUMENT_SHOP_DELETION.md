# Document Shop deletion lifecycle

The reported Castille URL identifies a Black Box workspace, not a separate job
table row. Source removal previously marked the original and generated Survey
Reference removed, then returned to My Documents without retiring the container.
The list enumerates registry containers and counted zero active sources. Its
"Could not complete" summary did not establish that no retained content existed.

Read-only production inspection found two removed sources, one structural unit,
40 addressable regions, 42 evidence items (40 extracted and two AI proposals),
six conversation entries, the legacy registry record, workspace, stored original
and derivative files, governance history, one completed perception job and two
completed visual jobs. The container itself was active. No other workspace
referenced its ID. No separate recent/search index was found: these surfaces
project the existing registry and workspace lifecycle.

## Bounded disposable-case deletion

The Product Owner amendment authorizes complete deletion of user-created analysis
cases, including their private source and derived evidence. Black Box containers
use `CaseWorkspaceStore.delete_document_shop_job`; established projects continue
through their existing lifecycle. Retained private content does not block erasure.

The owner removes the registry/workspace records, private source/artifact files,
view state, perception/visual/founding jobs, chunks and reconciliation staging.
Files referenced by another registry/workspace (including by source identity) are
preserved, as are all external records. The disposable case itself is removed.
Runtime observations owned by the case are deleted and late observations are
rejected. Survey Evaluation runs own separate isolated registries and are not
owned by Document Shop cases; deleting a case does not delete independent runs.

The existing internal deleted-ID guard commits before cleanup and prevents stale
registry, workspace, worker, upload and derived-reference writes from recreating
the case. Interrupted cleanup is retryable. Existing audit storage remains
internal and does not surface erased cases. No new archive or retention policy.

Deleting the final source also deletes its disposable analysis, including its
private generated Survey Reference. Removing one source from a multi-source case
keeps the existing source-removal semantics. Established projects are unchanged.

Open `/document-shop/jobs`, choose Delete, and confirm. The response immediately
returns a fresh list. Reload is a GET; authenticated responses prohibit cached
reuse. Registry enumeration drives search and recents, without a second index.
The old job/status/workspace URLs return not found without recreating a shell.

## Qualification

`tests/test_document_shop_deletion.py` exercises the failed/zero-document list,
confirmation, deletion, Reload, search/project/recent listings, direct URLs,
private evidence erasure, unauthorized callers, shared references, stale writers,
interrupted cleanup, unreadable dependent storage, and the legacy delete door.
Existing removal, source/derivative, search, recent-list, chunk, worker and view
state tests remain part of qualification. Run the authoritative full suite on
the frozen implementation after focused qualification.

`tools/verify_document_shop_deletion.py --output instance/document-shop-deletion-ui`
drives real browser login and CSRF-protected deletion forms against isolated
storage. It records the actual owner invocation, response trace references,
Reload absence, and 404. `--live` performs read-only Castille checks and requires
an existing human-issued `ARCHIOSK_VERIFICATION_URL`; it never creates production
credentials. Deployment and gate results must be reported separately as executed
evidence, not inferred from this implementation document.

Protected perception worker and datum corroboration implementation files are
unchanged. No new interpreter, evidence store, or search/list projection exists.

Full-suite qualification also exposed a repeatable Windows sharing violation in
the existing bridge queue: a claim committed successfully but pending-file cleanup
raised while another claimant held a reader open. `bridge_queue.claim_pending`
now retries that cleanup briefly, preserving exclusive-create ownership and
raising persistent faults. The durable bridge tests cover transient and permanent
cleanup faults in addition to their existing real-process race test.
