# MANIFEST

A structured catalog of every tracked file in this repository: what it
is, what it does, and what it connects to. Generated as a navigation
aid — regenerate/update it by hand when files are added, removed, or
significantly repurposed; nothing here is auto-synced from the code.

Scope: tracked application files only (`git ls-files`). `venv/`,
`__pycache__/`, `instance/`, and other git-ignored/generated paths are
excluded — see `.gitignore`. Individual `tests/*.py` files and
`governance/*.md` documents are deliberately not catalogued here —
tests have no separate index (there are 65+ of them; read the test
file itself), and `governance/` is its own system with its own index
(`governance/STATUS.md`, `governance/history-mapping.md`) per
`CLAUDE.md`'s "does not contain" list.

**Known gap, not yet fixed:** this manifest predates the multi-user
`User`/`PasswordResetToken` auth system (`models.py`,
`services/auth.py`'s real shape, `services/password_reset.py`,
`services/email.py`), the entire Case Workspace subsystem
(`routes/workspace.py`, `services/case_workspace.py`,
`templates/case_workspace.html`), and more — several entries below
(marked inline) describe an earlier, superseded state. Treat any
specific behavioral claim below with suspicion and verify against the
actual file before relying on it; a full refresh is real, separate
future work, not attempted here (CLAUDE-P27-D only added entries for
files it introduced and corrected one claim that had become
factually false).

## Quick map

```
wsgi.py / app.py (entrypoints)
        |
        v
   config.py  <---- .env / .env.example
        |
        v
routes/portal.py --+--> services/ingestion.py --+--> services/bhive_parser.py
routes/api.py    ---'                            '--> services/requirements_registry.py
                                                  '--> services/rfi_export.py (consistency flags -> .docx)
                                                  '--> services/governance.py (append-only audit trail, .jsonl per project)
        |
        v
templates/*.html (Jinja, extend base.html)
        |
        v
static/css/main.css, static/js/case_workspace.js

deploy/*  (nginx, gunicorn) — infra wrapping wsgi:app, not imported by Python
```

---

## 1. Application entrypoints

| File | Purpose | Connects to |
|---|---|---|
| `app.py` | Flask application factory (`create_app`). Registers blueprints, error handlers (404/500), and a context processor injecting `current_year`, `static_version`, and `authenticated` (so every template's nav can reflect login state). Local dev entrypoint via `python app.py`. | Imports `config.get_config`; imports `routes.portal.portal_bp` and `routes.api.api_bp` inside `_register_blueprints`; imports `services.auth.is_authenticated`; renders `templates/errors/404.html` / `500.html`. |
| `wsgi.py` | Production WSGI entrypoint (`gunicorn -c deploy/gunicorn.conf.py wsgi:app`). Builds the app via `create_app()` and logs a warning (not a crash) if required env vars are missing. | Imports `app.create_app` and `config.BaseConfig`. Consumed by `deploy/gunicorn.service`'s `ExecStart`. |

## 2. Configuration

| File | Purpose | Connects to |
|---|---|---|
| `config.py` | Calls `load_dotenv(BASE_DIR / ".env")` (explicit path so it works regardless of cwd; never overrides a real env var already set) before defining env-driven settings: `BaseConfig`/`DevelopmentConfig`/`ProductionConfig`/`TestingConfig`, `get_config(name)` resolver, `BaseConfig.validate()` (returns missing required env vars). Defines `SECRET_KEY`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `DATABASE_URL`, `REGISTRY_STORE_PATH`, `MAX_CONTENT_LENGTH`, `ALLOWED_UPLOAD_EXTENSIONS`, `STATIC_VERSION`, `AUTH_USERNAME`/`AUTH_PASSWORD_HASH` (unset means the login gate fails closed — see `services/auth.py`), and the session cookie flags (`SESSION_COOKIE_SECURE` off in dev/testing since local dev is plain HTTP). | Read by `app.py` (`create_app`) and `wsgi.py` (`validate()`). Values consumed downstream via `current_app.config` in `routes/api.py`, `routes/portal.py`, `services/ingestion.py`, `services/auth.py`; `STATIC_VERSION` specifically via `app.py`'s context processor into `templates/base.html`/`dashboard.html`. |
| `.env.example` | Template for local `.env` — documents every env var `config.py` reads (`FLASK_SECRET_KEY`, `PORT`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_TIMEOUT_SECONDS`, `DATABASE_URL`, `REGISTRY_STORE_PATH`, `MAX_UPLOAD_MB`). | Mirrors `config.py` and `services/bhive_parser.py`'s env reads. Never committed with real values — copy to `.env`. |
| `.gitignore` | Excludes secrets (`.env`), Python artifacts, `venv/`, the `instance/` data folder (sqlite db + JSON registry store), logs, editor dirs. | Keeps `REGISTRY_STORE_PATH` (default `instance/registry`) and `DATABASE_URL` sqlite file out of version control. |
| `requirements.txt` | Pinned Python dependencies, by category rather than an exact list here (an exact duplicate list drifts — see the "Known gap" note above for exactly this failure mode; read `requirements.txt` directly for current pins): web framework + ORM (`Flask`, `Flask-SQLAlchemy`, `SQLAlchemy`), WSGI server (`gunicorn`), security/hardening (`Flask-Limiter`, `Flask-WTF`, `Flask-Migrate` — all added CLAUDE-P27-B), AI client (`anthropic`, `httpx` pinned to `0.27.2` — `0.28+` breaks `anthropic==0.34.2`'s client construction), document parsing (`python-docx`, `pypdf`, `Pillow`), config (`python-dotenv`). | Installed into `venv/`. `anthropic`/`httpx` versions are load-bearing for `services/bhive_parser.py`. |

## 3. Documentation

| File | Purpose | Connects to |
|---|---|---|
| `README.md` | Project overview, layout diagram, local setup, VPS deployment steps, security notes. | Describes the same file layout this manifest catalogs, from a "how do I run this" angle rather than a "what connects to what" angle. |

## 4. Backend routes (Flask blueprints)

| File | Purpose | Connects to |
|---|---|---|
| `routes/__init__.py` | Marks `routes/` as a package. Empty. | — |
| `routes/portal.py` | HTML page blueprint (`portal_bp`, no URL prefix). Routes: `/` (marketing home, public), `/health` (liveness/readiness probe, public), `/login` (GET form + POST handler, generic error message, same-site-only `?next=` redirect — defaults to `/gateway` when no `next` is given), `/logout`, `/gateway` (`@login_required` — post-login landing, one action card: open an existing project; admins also see ingest), `/upload` (`@login_required` — GET form + POST handler, accepts optional `actor`/`role` form fields, redirects into Case Workspace on success), `/dashboard` and `/dashboard/<project_id>` (`@login_required` — retired as a page, now just redirects into `workspace.show_workspace` / `portal.projects_list`). | Calls `services.auth.check_credentials`/`log_in`/`log_out`/`login_required`; `services.ingestion.ingest_upload` / `get_registry` / `get_governance_log`; renders `templates/index.html`, `login.html`, `gateway.html`, `upload.html`; registered by `app.py`. |
| `routes/api.py` | JSON API blueprint (`api_bp`, mounted at `/api/v1`). All routes require the same session-cookie login as `routes/portal.py`, enforced blueprint-wide via a `before_request` hook (not per-route decorators) — `POST /documents/ingest` additionally requires the admin role, mirroring `/upload`'s `@admin_required`. Routes: `POST /documents/ingest` (accepts optional `actor`/`role` form fields), `GET /documents`, `GET /documents/<id>`, `GET /documents/<id>/requirements` (optional `?category=`), `GET /documents/<id>/milestones`, `GET /documents/<id>/consistency`, `GET /documents/<id>/governance` (the append-only audit-trail events), `GET /documents/<id>/rfi` (downloads a `.docx`, 409 if nothing to export), `GET /categories`. Handles `RequestEntityTooLarge` (413) for oversized uploads. | Calls `services.auth.is_authenticated`/`is_admin`; `services.ingestion.ingest_upload` / `get_registry` / `get_governance_log`; calls `services.rfi_export.build_rfi_docx`; reads `services.bhive_parser.REQUIREMENT_CATEGORIES`; registered by `app.py`. |

## 5. Parsing & business logic (services)

| File | Purpose | Connects to |
|---|---|---|
| `services/__init__.py` | Marks `services/` as a package. Empty. | — |
| `services/bhive_parser.py` | The B-Hive core chassis: `BHiveParser` runs extract → segment → classify → consistency-check → assemble on an uploaded RFP/RFQ. Extract supports `.txt`/`.csv`/`.md` (direct decode), `.docx` (`python-docx`, skips heading/title-styled paragraphs), `.pdf` (`pypdf`). Segment is table-aware (Batch H): `extract_markdown_tables()` (a minimal GFM pipe-table parser — module-level, pure) finds tables first; their raw lines are excluded from the naive per-line pass (each data row instead becomes its own header-labeled chunk, e.g. `"Functional Group: ...; Room / Space: ..."`), and markdown ATX headings (`## ...`) are excluded the same way `.docx` already excludes heading-styled paragraphs. Classify uses the Anthropic API (batches of 25 chunks, per-batch timeout via `ANTHROPIC_TIMEOUT_SECONDS`, an overall `ANTHROPIC_CLASSIFY_BUDGET_SECONDS` budget across all batches, falls back to rule-based classification on timeout/budget-exceeded/any other exception) or a deterministic keyword classifier when no API key is set. Consistency-check is a single Anthropic call reviewing all classified requirements together for cross-requirement contradictions (`ANTHROPIC_CONSISTENCY_TIMEOUT_SECONDS`, capped at 150 requirements) — requires an API key, no rule-based fallback, best-effort/never blocks ingestion. Assemble derives a milestone list from `schedule_milestone`-category requirements. Defines `REQUIREMENT_CATEGORIES` and the `ParsedDocument`/`RequirementItem`/`ConsistencyFlag` dataclasses; `ParsedDocument.tables` (Batch H) carries the raw structured tables (headers + rows) separately from `requirements`, for a future reconciliation/arithmetic-check capability that isn't built yet. | Used by `services/ingestion.py`. `ParsedDocument`/`RequirementItem`/`ConsistencyFlag` are consumed by `services/requirements_registry.py` for (de)serialization and by `services/rfi_export.py` for `.docx` generation. `REQUIREMENT_CATEGORIES` is imported by both route blueprints. |
| `services/ingestion.py` | Shared upload-handling glue between the API and HTML upload form: `ingest_upload(file_storage, app, actor=None, role=None)` validates the extension against `ALLOWED_UPLOAD_EXTENSIONS`, runs `BHiveParser.parse`, saves via the registry, records a `document_ingested` governance event (defaulting to `actor="anonymous"`/`role="unspecified"` when not supplied), and raises `UploadError` on bad input. `get_registry(app)` builds a `RequirementsRegistry`; `get_governance_log(app)` builds a `GovernanceLog` — both from `app.config['REGISTRY_STORE_PATH']`. | Imported by both `routes/api.py` and `routes/portal.py` so the validate→parse→save→log sequence isn't duplicated across the JSON and HTML paths. Wraps `services.bhive_parser.BHiveParser`, `services.requirements_registry.RequirementsRegistry`, and `services.governance.GovernanceLog`. |
| `services/governance.py` | Append-only audit-trail log: `GovernanceEvent` dataclass and `GovernanceLog.append(project_id, event_type, actor, role, payload=None, predecessor_id=None)` / `.read(project_id)`. One `.jsonl` file per project (`<project_id>.governance.jsonl`, always opened in append mode — never read-modify-rewritten), so history can't be silently altered. Corrections are new events with `predecessor_id` pointing back at what they correct, never edits to the original line. Raises `GovernanceError` if `actor`/`role` are empty/whitespace-only. No real authentication backs `actor`/`role` — they're free-text fields recorded as given, not verified identity (unrelated to `services/auth.py`'s login gate — this is an audit label, not a permission check). | Used by `services/ingestion.py`. Files live alongside the registry's own JSON files under `instance/registry/` (git-ignored). |
| `services/auth.py` | **Stale entry, superseded shape** — this row still describes the original single-shared-credential design. The real, current mechanism is a `User`-table-backed session login (`models.py`, multi-user, `admin`/`read_only` roles, provisioned via `tools/create_credentials.py`) — `check_credentials`, `is_authenticated()`, `log_in`/`log_out`, `login_required`/`admin_required` decorators. **`routes/api.py` now also requires this same session login**, enforced blueprint-wide (CLAUDE-P27-B) — the "does not touch routes/api.py" claim this row previously made is false as of commit `c2db13f`. Full current behavior not re-documented here; read `services/auth.py` directly. | Used by `routes/portal.py`, `routes/api.py` (session auth added CLAUDE-P27-B), `routes/workspace.py`, and `app.py`'s context processor. |
| `services/rate_limit.py` | (CLAUDE-P27-B) Module-level Flask-Limiter singleton (`limiter = Limiter(key_func=get_remote_address)`), created unbound like `models.py`'s `db = SQLAlchemy()` and bound via `limiter.init_app(app)` in `app.py`. In-memory storage — under multiple Gunicorn workers each worker holds its own counter, so the effective ceiling is (configured limit × worker count), not one shared limit. Disabled under `TestingConfig` (`RATELIMIT_ENABLED=False`). | Imported by `routes/portal.py` (`/login`, `/forgot-password`, `/reset-password`, `/upload`) and `routes/api.py` (`/documents/ingest`) to decorate specific routes with `@limiter.limit(...)`. |
| `services/requirements_registry.py` | Flat-file JSON persistence for `ParsedDocument` records: `save()`, `get(project_id)`, `list_ids()`. Storage-agnostic at the call site by design — swappable for a DB-backed implementation later without touching the routes. | Reads/writes `ParsedDocument`/`RequirementItem`/`ConsistencyFlag` from `services/bhive_parser.py`. Instantiated by `services/ingestion.get_registry`; store path comes from `config.py`'s `REGISTRY_STORE_PATH`. Backing files live under `instance/registry/` (git-ignored). |
| `services/rfi_export.py` | `build_rfi_docx(document)` turns a `ParsedDocument`'s flagged `ConsistencyFlag`s into a real Request for Information `.docx` via `python-docx` — one `RFI-NNN` section per flag with both requirement excerpts and the explanation. Raises `RFIExportError` (message distinguishes "checked, nothing flagged" from "never checked") when there's nothing to export. | Called by `routes/api.py`'s `GET /documents/<id>/rfi`. Consumes `ParsedDocument`/`ConsistencyFlag` from `services/bhive_parser.py`. |

## 6. Frontend templates (Jinja2)

| File | Purpose | Connects to |
|---|---|---|
| `templates/_macros.html` | Shared page-geometry macros: `page_header` (title-left/controls-right page header), `accordion` (top-level `<details class="accordion-section">` disclosure), `subdisclosure` (nested "+ Add X" / "View Y" disclosure). Introduced to stop three geometries (page headers, accordions, sub-disclosures) from being hand-copied per template with accidental drift each time. | Imported (`{% import "_macros.html" as macros %}`) by `projects.html` and `case_workspace.html`. Not a page on its own - never rendered directly. |
| `templates/base.html` | Master layout. Blueprint-grid backdrop, header/nav (Home always shown; Upload/Dashboard/Sign out when `authenticated`, Sign in otherwise), `{% block content %}`, footer with `current_year`. Blocks: `title`, `extra_head`, `content`, `extra_scripts`. | Extended by every other template. Links use `url_for('portal.index'|'login'|'logout'|'upload'|'dashboard')`. Pulls in `static/css/main.css`. |
| `templates/index.html` | Marketing home page (public): hero section (CTA reflects `authenticated` — "Sign in to get started" vs. "Ingest a document"/"View dashboard") + 4-step pipeline cell row (extract/segment/classify/assemble). | Extends `base.html`. Rendered by `routes/portal.py:index`. |
| `templates/login.html` | Sign-in form (username/password, generic invalid-credentials message), styled as a centered `.gateway-card.gateway-card-compact` — logo/brand lockup, section label, no subtitle/heading/footer, geometry and turquoise background matched to the archiosk-explorer (port 5173) welcome card. | Extends `base.html`. Rendered by `routes/portal.py:login` (GET and the 401 error path). |
| `templates/gateway.html` | Post-login landing page: one `.gateway-action` card ("Open an existing project"; admins also see "Ingest a new document") instead of redirecting straight into one. Extends `gateway_base.html`, the shared Entry/gateway family base also used by `login.html`. | Rendered by `routes/portal.py:gateway`. Links to `portal.upload`/`portal.projects_list`. |
| `templates/upload.html` | Upload form (`multipart/form-data`, file input restricted to `.pdf/.docx/.txt/.csv/.md`), plus optional free-text `actor`/`role` fields for the governance audit trail. Displays `max_upload_mb` and an inline `error` message on rejected uploads. | Extends `base.html`. Rendered by `routes/portal.py:upload` (GET and the 400 error path). |
| ~~`templates/dashboard.html`~~ | **Retired.** Case Workspace (`case_workspace.html`) absorbed every real piece of content this had (extracted/governed Requirements, the actual consistency-flag cards in RFI Export, audit trail in History) except the milestone lattice, which was dropped outright - confirmed non-functional for real projects (`_derive_milestones` in `bhive_parser.py` only ever produces `status="pending"`; "done"/"active" only ever appeared in this route's own hardcoded demo data). `routes/portal.py`'s `dashboard()` is now a redirect into Case Workspace, kept so old bookmarks/links still land somewhere real. | n/a |
| `templates/errors/error.html` | The one dead-end error page (403/404/500 share it - same shape, different `code`/`heading`/`message`/`action_url`/`action_label`). | Extends `base.html`. Rendered by `app.py`'s `_render_error` helper from the 403/404/500 handlers, non-API requests only. |
| `templates/confirm_base.html` | Confirm-page family base: one centered card, one question, one action set, one way back. Blocks: `confirm_title`, `confirm_label`, `confirm_heading`, `confirm_body`, `confirm_actions`, `confirm_back_url`, `confirm_back_label`. | Extends `base.html`. Extended by `confirm_action.html` (Approval Gate) and `confirm_delete_project.html`. |

## 7. Static assets

| File | Purpose | Connects to |
|---|---|---|
| `static/css/main.css` | The full design system: color tokens (`--ink`, `--panel`, `--amber`, `--teal`, etc.), typography, header/nav, hero, pipeline cells, dashboard header, honeycomb lattice, registry table, chips, error page. | Linked from `templates/base.html`; every template's markup is written against these class names. |

## 8. Deployment (infra config, not imported by Python)

| File | Purpose | Connects to |
|---|---|---|
| `deploy/nginx.conf` | Reverse-proxy site config for archiosk.com. HTTP→HTTPS redirect, TLS server block, `/static/` alias with far-future immutable caching (safe only because of `STATIC_VERSION`'s `?v=` cache-busting — see `config.py`), security headers (HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and a `Content-Security-Policy` of `default-src 'self'` with no exceptions — the app has no inline styles/scripts or external resources) on every response — repeated inside `location /static/` since nginx stops inheriting a parent's `add_header` once a location defines its own — dedicated quiet `/health` location (tight timeouts, no access log) for external monitors, upstream passive health check (`max_fails=3 fail_timeout=30s`) against the single gunicorn backend, and `location /`'s `proxy_read_timeout`/`proxy_send_timeout`/`client_body_timeout` (150s/120s/120s) sized to the classify + consistency-check budget. | Proxies to `127.0.0.1:8000`, matching `deploy/gunicorn.conf.py`'s default `bind`. The `/health` location targets `routes/portal.py`'s `/health` route. `client_max_body_size 25M` mirrors `MAX_UPLOAD_MB` in `config.py`; `proxy_read_timeout` mirrors `GUNICORN_TIMEOUT`. |
| `deploy/gunicorn.conf.py` | Gunicorn worker settings: bind address, `worker_class` (`gthread`, not `sync` — each worker gets a thread pool via `threads`, default 4, so a request blocked on Anthropic/disk I/O doesn't block everything else in that worker; safe since `BHiveParser`, its Anthropic clients, `RequirementsRegistry`, and `GovernanceLog` are all constructed fresh per request with no shared mutable state), worker count, `timeout` (150s, sized to the classify + consistency-check budget), `worker_tmp_dir` (defaults to `/dev/shm` — workers heartbeat via a temp file, and tmpfs avoids a slow-disk false-positive "worker timed out" kill), request-based worker recycling (`max_requests`/`max_requests_jitter`). | Loaded via `gunicorn -c deploy/gunicorn.conf.py wsgi:app`; `bind` must match what `deploy/nginx.conf`'s `upstream` proxies to; `timeout` must stay in sync with `deploy/nginx.conf`'s `proxy_read_timeout`. |
| `deploy/gunicorn.service` | systemd unit — runs gunicorn as the `archiosk` user/group, loads `.env` via `EnvironmentFile`, `Environment=PYTHONUNBUFFERED=1` (so a killed worker's last log lines aren't lost to buffering), `Type=simple` (gunicorn doesn't implement systemd's `sd_notify` protocol, so `Type=notify` would hang), restarts on failure, `TimeoutStopSec=45` (must exceed gunicorn's own 30s `graceful_timeout` so its graceful drain finishes before systemd SIGKILLs), applies sandboxing (`NoNewPrivileges`, `PrivateTmp`, `ProtectSystem`). | `ExecStart` points at `deploy/gunicorn.conf.py` and `wsgi:app`. Bumping `STATIC_VERSION` in `.env` requires `systemctl restart`, not `reload` — `EnvironmentFile` is only read at unit start. |

## 9. Development tools (not imported by the app)

| File | Purpose | Connects to |
|---|---|---|
| `tools/dependency_fit.py` | Standalone CLI (argparse, no Flask import) — checks a proposed library/tool/pattern against constraints this project has actually and deliberately established: no client-side build step, flat-JSON storage (SQLite was explicitly proposed and rejected), `gthread` not async workers, no new required cloud dependency, no background-worker infra, Python-native. Rule-based PASS/WARN/FAIL report; exit code 1 if anything FAILs. | Standalone — reads no app config, imports nothing from `services/`/`routes/`. Run directly: `python tools/dependency_fit.py --name ... [flags]`. |
| `tools/create_credentials.py` | CLI to create/update a `User` row (username/password/role/email), including `--suspend`/`--activate` (CLAUDE-P27-B, sets `User.is_active`) and `--keep-password` (update role/email without touching the password). Provisioning is CLI-only — no self-registration route exists. | Imports `app.create_app`, `models.User`/`db`. Run directly: `python tools/create_credentials.py --username ... [flags]`. |
| `tools/backup_data.py` | (CLAUDE-P27-B) Bundles the SQLite DB file and the whole `REGISTRY_STORE_PATH` tree into one timestamped `.tar.gz` under `backups/` (git-ignored). Read-only with respect to source data. Resolves paths the same way `config.py` does (not hardcoded), so it honors a real `DATABASE_URL`/`REGISTRY_STORE_PATH` override. | Run directly: `python tools/backup_data.py [--output-dir ...]`. Pairs with `tools/restore_data.py`. |
| `tools/restore_data.py` | (CLAUDE-P27-B) Extracts a `tools/backup_data.py` archive into an explicit `--target-dir` — refuses a non-empty target (a restore silently overwriting live, newer data would itself be a data-loss incident) and has no default pointing at `instance/`. | Run directly: `python tools/restore_data.py --archive ... --target-dir ...`. |

## 10. Database migrations (CLAUDE-P27-B)

| File | Purpose | Connects to |
|---|---|---|
| `migrations/` (Flask-Migrate/Alembic scaffold: `alembic.ini`, `env.py`, `script.py.mako`, `README`, `versions/`) | Adopted for the **next** schema change onward — does not replace `app.py`'s existing hand-rolled `create_all()` + `_migrate_users_*` functions, which remain what actually creates/migrates the already-deployed schema at every boot. `versions/f8620fa70917_..._baseline_schema...py` is hand-written, not autogenerated (`create_all()` always runs first, even under the `flask db` CLI, so autogenerate never sees a diff) — verified to produce byte-identical schema to the real boot path. The already-deployed local database was `flask db stamp head`-ed to this revision, not migrated through it. Full rationale in `migrations/README`. | `Migrate(app, db)` registered in `app.py`'s `_register_database`. |

---

## Request-flow reference

**Document ingestion (API):**
`POST /api/v1/documents/ingest` (`routes/api.py`) → `services.ingestion.ingest_upload` → `services.bhive_parser.BHiveParser.parse` → `services.requirements_registry.RequirementsRegistry.save` → JSON response.

**Document ingestion (HTML form):**
`POST /upload` (`routes/portal.py`) → same `ingest_upload` call → redirect straight into `workspace.show_workspace` (Case Workspace).

**Health check:**
External monitor → `deploy/nginx.conf`'s `/health` location → `routes/portal.py:health` → `services.ingestion.get_registry(...).list_ids()` (the only real runtime dependency check; does not call the Anthropic API).

**RFI export:**
`GET /api/v1/documents/<id>/rfi` (`routes/api.py`) → `services.requirements_registry.RequirementsRegistry.get` → `services.rfi_export.build_rfi_docx` → `.docx` file download (409 if the document has no flagged contradictions to export).

**Governance audit trail:**
Every ingestion (API or form) → `services.ingestion.ingest_upload` → after the registry save, `services.governance.GovernanceLog.append` records a `document_ingested` event (`actor`/`role` from the request, defaulting to `"anonymous"`/`"unspecified"`). Read via `GET /api/v1/documents/<id>/governance` or the dashboard's audit-trail table (`GovernanceLog.read`, newest first). Corrections append a new event with `predecessor_id` pointing at what they correct — the original event is never edited.

**Web UI login:**
`GET /upload` while unauthenticated → `@login_required` (`services/auth.py`) → redirect to `/login?next=<original path>` → `POST /login` with correct credentials → `services.auth.check_credentials` (`werkzeug.security.check_password_hash`) → `log_in()` sets the session → redirect to `next` (same-site paths only) if one was given, otherwise `/gateway` → the originally-requested page (or the gateway's action card(s)). `/logout` clears the session and redirects to `/`. **`routes/api.py` shares this same session login as of CLAUDE-P27-B** (corrected — this line previously claimed the opposite).
