# CIC-DEPLOYMENT — Deployment / Live Verification Contract

- **CONTRACT ID:** CIC-DEPLOYMENT
- **TITLE:** Deployment / Live Verification Contract
- **VERSION:** v1.0
- **STATUS:** CURRENT
- **SCOPE:** Accepted commit synchronization, deployment, restart, cache, and live checks.
- **APPLIES WHEN:** Work is pushed for live use or a live build is inspected.
- **DOES NOT APPLY WHEN:** A repository-only governance change is explicitly not deployed.
- **MANDATORY INVARIANTS:** Deploy exact accepted committed trees; never deploy unrelated working-tree content; protect `.env`, `instance/`, `.venv`, and other persistent paths; verify service/build marker/health; bump static cache version for changed static assets; distinguish repository correctness from live correctness; perform bounded live verification.
- **OPTIONAL / CONTEXTUAL REQUIREMENTS:** Maintain rollback backup and clean deployment scratch according to `deploy/DEPLOYMENT.md`.
- **REFERENCE IMPLEMENTATIONS:** `deploy/DEPLOYMENT.md`; `archiosk-go.service` accepted-build marker.
- **REFERENCE TESTS:** Deployment-specific live checks and affected focused tests.
- **KNOWN LIMITATIONS:** Authenticated browser verification may require a Product Owner session.
- **SUPERSEDES:** None.
- **SUPERSEDED BY:** None.
- **LAST REVIEWED:** 2026-08-20.
- **GOVERNANCE SOURCE:** `deploy/DEPLOYMENT.md` and repository deployment instructions.
