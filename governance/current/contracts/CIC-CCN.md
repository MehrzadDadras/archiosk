# CIC-CCN — Contemplated Change Notice Contract

- **CONTRACT ID:** CIC-CCN
- **TITLE:** Contemplated Change Notice Contract
- **VERSION:** v1.0
- **STATUS:** CURRENT
- **SCOPE:** `/CCN` command family and contemplated-change context.
- **APPLIES WHEN:** CCN parsing, state, context attachment, comparison, or lifecycle is touched.
- **DOES NOT APPLY WHEN:** A normal conversation has no active or requested CCN.
- **MANDATORY INVARIANTS:** CCN is contemplated intent, not implementation authorization; `/CCN`, inline and colon intent, status/show/compare/finalize/cancel remain governed; CCN is a lens, not a chat gate; chat and CCN lifecycles are distinct; selection never authorizes mutation.
- **OPTIONAL / CONTEXTUAL REQUIREMENTS:** Preserve future CN/SI compatibility without implementing them prematurely.
- **REFERENCE IMPLEMENTATIONS:** `services/developer_ccn.py`; `routes/portal.py` and workspace Composer routes.
- **REFERENCE TESTS:** `tests/test_developer_mode_ccn_01.py`, Developer Composer tests.
- **KNOWN LIMITATIONS:** CN/SI are not implemented by this contract.
- **SUPERSEDES:** None.
- **SUPERSEDED BY:** None.
- **LAST REVIEWED:** 2026-08-20.
- **GOVERNANCE SOURCE:** `governance/current/developer-mode-ccn.md`; `GO-COMPOSER-01`.
