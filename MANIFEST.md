# MANIFEST

A structured catalog of every tracked file in this repository: what it
is, what it does, and what it connects to. Generated as a navigation
aid — regenerate/update it by hand when files are added, removed, or
significantly repurposed; nothing here is auto-synced from the code.

Scope: tracked application files only (`git ls-files`). `venv/`,
`__pycache__/`, `instance/`, and other git-ignored/generated paths are
excluded — see `.gitignore`.

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
static/css/main.css, static/js/dashboard.js

deploy/*  (nginx, gunicorn) — infra wrapping wsgi:app, not imported by Python
```

---

## 1. Application entrypoints

| File | Purpose | Connects to |
|---|---|---|
| `app.py` | Flask application factory (`create_app`). Registers blueprints, error handlers (404/500), and a context processor injecting `current_year` and `static_version`. Local dev entrypoint via `python app.py`. | Imports `config.get_config`; imports `routes.portal.portal_bp` and `routes.api.api_bp` inside `_register_blueprints`; renders `templates/errors/404.html` / `500.html`. |
| `wsgi.py` | Production WSGI entrypoint (`gunicorn -c deploy/gunicorn.conf.py wsgi:app`). Builds the app via `create_app()` and logs a warning (not a crash) if required env vars are missing. | Imports `app.create_app` and `config.BaseConfig`. Consumed by `deploy/gunicorn.service`'s `ExecStart`. |

## 2. Configuration

| File | Purpose | Connects to |
|---|---|---|
| `config.py` | Calls `load_dotenv(BASE_DIR / ".env")` (explicit path so it works regardless of cwd; never overrides a real env var already set) before defining env-driven settings: `BaseConfig`/`DevelopmentConfig`/`ProductionConfig`/`TestingConfig`, `get_config(name)` resolver, `BaseConfig.validate()` (returns missing required env vars). Defines `SECRET_KEY`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `DATABASE_URL`, `REGISTRY_STORE_PATH`, `MAX_CONTENT_LENGTH`, `ALLOWED_UPLOAD_EXTENSIONS`, `STATIC_VERSION` (cache-busting query string for static assets — see `deploy/nginx.conf`'s immutable `/static/` cache). | Read by `app.py` (`create_app`) and `wsgi.py` (`validate()`). Values consumed downstream via `current_app.config` in `routes/api.py`, `routes/portal.py`, `services/ingestion.py`; `STATIC_VERSION` specifically via `app.py`'s context processor into `templates/base.html`/`dashboard.html`. |
| `.env.example` | Template for local `.env` — documents every env var `config.py` reads (`FLASK_SECRET_KEY`, `PORT`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_TIMEOUT_SECONDS`, `DATABASE_URL`, `REGISTRY_STORE_PATH`, `MAX_UPLOAD_MB`). | Mirrors `config.py` and `services/bhive_parser.py`'s env reads. Never committed with real values — copy to `.env`. |
| `.gitignore` | Excludes secrets (`.env`), Python artifacts, `venv/`, the `instance/` data folder (sqlite db + JSON registry store), logs, editor dirs. | Keeps `REGISTRY_STORE_PATH` (default `instance/registry`) and `DATABASE_URL` sqlite file out of version control. |
| `requirements.txt` | Pinned Python dependencies: `Flask`, `gunicorn`, `python-dotenv`, `anthropic`, `python-docx`, `pypdf`, `Werkzeug`, `httpx` (pinned to `0.27.2` — `0.28+` breaks `anthropic==0.34.2`'s client construction). | Installed into `venv/`. `anthropic`/`httpx` versions are load-bearing for `services/bhive_parser.py`. |

## 3. Documentation

| File | Purpose | Connects to |
|---|---|---|
| `README.md` | Project overview, layout diagram, local setup, VPS deployment steps, security notes. | Describes the same file layout this manifest catalogs, from a "how do I run this" angle rather than a "what connects to what" angle. |

## 4. Backend routes (Flask blueprints)

| File | Purpose | Connects to |
|---|---|---|
| `routes/__init__.py` | Marks `routes/` as a package. Empty. | — |
| `routes/portal.py` | HTML page blueprint (`portal_bp`, no URL prefix). Routes: `/` (marketing home), `/health` (liveness/readiness probe), `/upload` (GET form + POST handler, accepts optional `actor`/`role` form fields), `/dashboard` and `/dashboard/<project_id>` (demo data when no id given, real parsed document plus its governance audit trail otherwise). | Calls `services.ingestion.ingest_upload` / `get_registry` / `get_governance_log`; reads `services.bhive_parser.REQUIREMENT_CATEGORIES`; renders `templates/index.html`, `upload.html`, `dashboard.html`; registered by `app.py`. |
| `routes/api.py` | JSON API blueprint (`api_bp`, mounted at `/api/v1`). Routes: `POST /documents/ingest` (accepts optional `actor`/`role` form fields), `GET /documents`, `GET /documents/<id>`, `GET /documents/<id>/requirements` (optional `?category=`), `GET /documents/<id>/milestones`, `GET /documents/<id>/consistency`, `GET /documents/<id>/governance` (the append-only audit-trail events), `GET /documents/<id>/rfi` (downloads a `.docx`, 409 if nothing to export), `GET /categories`. Handles `RequestEntityTooLarge` (413) for oversized uploads. | Calls `services.ingestion.ingest_upload` / `get_registry` / `get_governance_log`; calls `services.rfi_export.build_rfi_docx`; reads `services.bhive_parser.REQUIREMENT_CATEGORIES`; registered by `app.py`. |

## 5. Parsing & business logic (services)

| File | Purpose | Connects to |
|---|---|---|
| `services/__init__.py` | Marks `services/` as a package. Empty. | — |
| `services/bhive_parser.py` | The B-Hive core chassis: `BHiveParser` runs extract → segment → classify → consistency-check → assemble on an uploaded RFP/RFQ. Extract supports `.txt`/`.csv` (direct decode), `.docx` (`python-docx`, skips heading/title-styled paragraphs), `.pdf` (`pypdf`). Classify uses the Anthropic API (batches of 25 chunks, per-batch timeout via `ANTHROPIC_TIMEOUT_SECONDS`, an overall `ANTHROPIC_CLASSIFY_BUDGET_SECONDS` budget across all batches, falls back to rule-based classification on timeout/budget-exceeded/any other exception) or a deterministic keyword classifier when no API key is set. Consistency-check is a single Anthropic call reviewing all classified requirements together for cross-requirement contradictions (`ANTHROPIC_CONSISTENCY_TIMEOUT_SECONDS`, capped at 150 requirements) — requires an API key, no rule-based fallback, best-effort/never blocks ingestion. Assemble derives a milestone list from `schedule_milestone`-category requirements. Defines `REQUIREMENT_CATEGORIES` and the `ParsedDocument`/`RequirementItem`/`ConsistencyFlag` dataclasses. | Used by `services/ingestion.py`. `ParsedDocument`/`RequirementItem`/`ConsistencyFlag` are consumed by `services/requirements_registry.py` for (de)serialization and by `services/rfi_export.py` for `.docx` generation. `REQUIREMENT_CATEGORIES` is imported by both route blueprints. |
| `services/ingestion.py` | Shared upload-handling glue between the API and HTML upload form: `ingest_upload(file_storage, app, actor=None, role=None)` validates the extension against `ALLOWED_UPLOAD_EXTENSIONS`, runs `BHiveParser.parse`, saves via the registry, records a `document_ingested` governance event (defaulting to `actor="anonymous"`/`role="unspecified"` when not supplied), and raises `UploadError` on bad input. `get_registry(app)` builds a `RequirementsRegistry`; `get_governance_log(app)` builds a `GovernanceLog` — both from `app.config['REGISTRY_STORE_PATH']`. | Imported by both `routes/api.py` and `routes/portal.py` so the validate→parse→save→log sequence isn't duplicated across the JSON and HTML paths. Wraps `services.bhive_parser.BHiveParser`, `services.requirements_registry.RequirementsRegistry`, and `services.governance.GovernanceLog`. |
| `services/governance.py` | Append-only audit-trail log: `GovernanceEvent` dataclass and `GovernanceLog.append(project_id, event_type, actor, role, payload=None, predecessor_id=None)` / `.read(project_id)`. One `.jsonl` file per project (`<project_id>.governance.jsonl`, always opened in append mode — never read-modify-rewritten), so history can't be silently altered. Corrections are new events with `predecessor_id` pointing back at what they correct, never edits to the original line. Raises `GovernanceError` if `actor`/`role` are empty/whitespace-only. No real authentication backs `actor`/`role` — they're free-text fields recorded as given, not verified identity. | Used by `services/ingestion.py`. Files live alongside the registry's own JSON files under `instance/registry/` (git-ignored). |
| `services/requirements_registry.py` | Flat-file JSON persistence for `ParsedDocument` records: `save()`, `get(project_id)`, `list_ids()`. Storage-agnostic at the call site by design — swappable for a DB-backed implementation later without touching the routes. | Reads/writes `ParsedDocument`/`RequirementItem`/`ConsistencyFlag` from `services/bhive_parser.py`. Instantiated by `services/ingestion.get_registry`; store path comes from `config.py`'s `REGISTRY_STORE_PATH`. Backing files live under `instance/registry/` (git-ignored). |
| `services/rfi_export.py` | `build_rfi_docx(document)` turns a `ParsedDocument`'s flagged `ConsistencyFlag`s into a real Request for Information `.docx` via `python-docx` — one `RFI-NNN` section per flag with both requirement excerpts and the explanation. Raises `RFIExportError` (message distinguishes "checked, nothing flagged" from "never checked") when there's nothing to export. | Called by `routes/api.py`'s `GET /documents/<id>/rfi`. Consumes `ParsedDocument`/`ConsistencyFlag` from `services/bhive_parser.py`. |

## 6. Frontend templates (Jinja2)

| File | Purpose | Connects to |
|---|---|---|
| `templates/base.html` | Master layout. Blueprint-grid backdrop, header/nav (Home / Upload / Dashboard), `{% block content %}`, footer with `current_year`. Blocks: `title`, `extra_head`, `content`, `extra_scripts`. | Extended by every other template. Links use `url_for('portal.index'|'upload'|'dashboard')`. Pulls in `static/css/main.css`. |
| `templates/index.html` | Marketing home page: hero section + 4-step pipeline cell row (extract/segment/classify/assemble). | Extends `base.html`. Rendered by `routes/portal.py:index`. |
| `templates/upload.html` | Upload form (`multipart/form-data`, file input restricted to `.pdf/.docx/.txt/.csv`), plus optional free-text `actor`/`role` fields for the governance audit trail. Displays `max_upload_mb` and an inline `error` message on rejected uploads. | Extends `base.html`. Rendered by `routes/portal.py:upload` (GET and the 400 error path). |
| `templates/dashboard.html` | The "Agility Engine" dashboard: header stats, honeycomb milestone lattice (`.hex` cells styled by status), a consistency-check panel (flagged contradiction cards with an RFI `.docx` download link, a clean "no contradictions" state, or an honest not-checked note), an audit-trail table (`GovernanceEvent`s, newest first: when/actor/role/event), requirement registry table with category filter chips. | Extends `base.html`. Rendered by `routes/portal.py:dashboard` with either demo data or a real `ParsedDocument`'s fields plus its `GovernanceLog` events. Loads `static/js/dashboard.js` via `extra_scripts`. |
| `templates/errors/404.html` | Not-found error page. | Extends `base.html`. Rendered by `app.py`'s 404 handler for non-API requests. |
| `templates/errors/500.html` | Server-error page. | Extends `base.html`. Rendered by `app.py`'s 500 handler for non-API requests. |

## 7. Static assets

| File | Purpose | Connects to |
|---|---|---|
| `static/css/main.css` | The full design system: color tokens (`--ink`, `--panel`, `--amber`, `--teal`, etc.), typography, header/nav, hero, pipeline cells, dashboard header, honeycomb lattice, registry table, chips, error page. | Linked from `templates/base.html`; every template's markup is written against these class names. |
| `static/js/dashboard.js` | Vanilla JS category-chip filter for the registry table: clicking a `.chip` toggles `active` and hides/shows `<tr>` rows by `data-category`. | Loaded only by `templates/dashboard.html`; targets `#registry-table` and `.registry-filter .chip` markup from that template. |

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

---

## Request-flow reference

**Document ingestion (API):**
`POST /api/v1/documents/ingest` (`routes/api.py`) → `services.ingestion.ingest_upload` → `services.bhive_parser.BHiveParser.parse` → `services.requirements_registry.RequirementsRegistry.save` → JSON response.

**Document ingestion (HTML form):**
`POST /upload` (`routes/portal.py`) → same `ingest_upload` call → redirect to `/dashboard/<project_id>` → `templates/dashboard.html`.

**Health check:**
External monitor → `deploy/nginx.conf`'s `/health` location → `routes/portal.py:health` → `services.ingestion.get_registry(...).list_ids()` (the only real runtime dependency check; does not call the Anthropic API).

**RFI export:**
`GET /api/v1/documents/<id>/rfi` (`routes/api.py`) → `services.requirements_registry.RequirementsRegistry.get` → `services.rfi_export.build_rfi_docx` → `.docx` file download (409 if the document has no flagged contradictions to export).

**Governance audit trail:**
Every ingestion (API or form) → `services.ingestion.ingest_upload` → after the registry save, `services.governance.GovernanceLog.append` records a `document_ingested` event (`actor`/`role` from the request, defaulting to `"anonymous"`/`"unspecified"`). Read via `GET /api/v1/documents/<id>/governance` or the dashboard's audit-trail table (`GovernanceLog.read`, newest first). Corrections append a new event with `predecessor_id` pointing at what they correct — the original event is never edited.
