# Specified But Unbuilt — Add Addendum Facility

**Status:** Requirement captured, not designed and not implemented.
Recorded during CLAUDE-P40-D at the product owner's request; this
document is a durable record of what was asked for, not an
architectural specification and not an implementation authorization.
The next stage that works on this must still do its own design pass
(data shape, storage boundary, route/authorization plan) before writing
code, the same way `tenancy-and-project-authorization.md` did for its
own topic.

## 0. Why this exists

The product owner identified a missing product capability while using
the application: an existing project has no explicit way to record
that a procurement addendum was issued against it. This is not a
request to implement anything in CLAUDE-P40-D - P40-D's own
authorization explicitly excludes "introducing a new Addendum
implementation, database subsystem, or storage provider." This document
exists so the requirement is not lost between now and whenever a future
stage is authorized to design and build it.

## 1. The requirement

An existing project shall provide an explicit **Add Addendum** action.
It must create a child addendum record under the existing project and
must **not** create another project.

## 2. Future capability requirements

1. **Source choices** — the addendum's source document may be:
   - a link to an existing ARCHIOSK document already in this project;
   - a link to an external procurement-portal or repository document;
   - a newly uploaded document.

2. **Storage principle:** *reference first, archive once.*

3. **An external link alone is not sufficient procurement evidence.**
   The default for an issued addendum is: link to source + one
   immutable preserved snapshot.

4. **The preserved file is stored once and referenced, not duplicated**
   inside each project record. Deduplication should use content
   identity/checksum where appropriate.

5. **The addendum record must support:**
   - project ID;
   - addendum number and title;
   - draft / issued / superseded status;
   - source link;
   - immutable snapshot reference;
   - checksum;
   - issue and effective dates;
   - affected RFP/RFQ document and version;
   - amendment summary;
   - acknowledgement status;
   - provenance and version history;
   - applicable access controls.

6. **Opening or adding an addendum must not silently apply amendments,**
   alter requirements, or overwrite the governing procurement document.
   Amendment interpretation and application require a later, separately
   governed workflow - the same "Analyze -> Review -> Apply" authority
   sequence `services/case_workspace.py`'s own module docstring already
   establishes for Findings must not be bypassed by this new record
   type.

7. This requirement does not authorize implementation. A future stage
   must be separately authorized before any of the above is designed
   (data shape, storage boundary, migration, routes) or built.

## 3. Explicitly not decided by this capture

This document deliberately does not answer, and a future design pass
must:

- Which persistence mechanism holds the addendum record itself (a new
  flat-JSON store alongside `CaseWorkspaceStore`/`RequirementsRegistry`,
  a new field on `ProjectWorkspace`, or something else) -
  `tools/dependency_fit.py`'s already-settled constraints (flat-JSON
  over a database, no new storage provider) still apply and must be
  checked before proposing anything here, per this repository's
  standing rule for any new dependency or storage pattern.
- Where the "one immutable preserved snapshot" physically lives
  relative to the existing `instance/registry/workspace_sources/`-style
  per-project source storage, and how checksum-based deduplication is
  actually implemented.
- The exact access-control model for an addendum record relative to
  the existing project-level (`services/project_access.py`) and
  Case-level (`services/case_workspace.py`'s `visible_cases_for`)
  authorization layers - whether an addendum inherits the parent
  project's access rules unconditionally or can be scoped more
  narrowly.
- The governed workflow referenced in §2 item 6 that will eventually
  let an issued addendum actually amend requirements - this capture
  covers only the record's existence and metadata, not that later
  application step.
