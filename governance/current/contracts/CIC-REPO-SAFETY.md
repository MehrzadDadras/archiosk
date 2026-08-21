# CIC-REPO-SAFETY — Repository / Working-Tree Safety Contract

- **CONTRACT ID:** CIC-REPO-SAFETY
- **TITLE:** Repository / Working-Tree Safety Contract
- **VERSION:** v1.0
- **STATUS:** CURRENT
- **SCOPE:** Every repository implementation, governance edit, commit, and push.
- **APPLIES WHEN:** Always.
- **DOES NOT APPLY WHEN:** Never; a read-only report may omit mutation steps but still verifies context when possible.
- **MANDATORY INVARIANTS:** Verify root, HEAD, branch, and status; confirm `C:\Archiosk\Research\archiosk`; preserve unrelated changes; stage only bounded task files; run `git diff --check`; do not trust the shell footer path; avoid destructive commands without explicit authorization.
- **OPTIONAL / CONTEXTUAL REQUIREMENTS:** Verify `HEAD == origin/main` before a push/deploy and record remaining uncommitted files.
- **REFERENCE IMPLEMENTATIONS:** Repository workflow instructions and `CLAUDE.md`.
- **REFERENCE TESTS:** Git checks and task-appropriate focused lanes.
- **KNOWN LIMITATIONS:** The working tree may contain intentionally unrelated Product Owner changes.
- **SUPERSEDES:** None.
- **SUPERSEDED BY:** None.
- **LAST REVIEWED:** 2026-08-20.
- **GOVERNANCE SOURCE:** `CLAUDE.md`, deployment procedure, and current task safety instructions.
