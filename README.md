# ArchiOSK / B-Hive

Flask backend + portal frontend for archiosk.com, with the B-Hive core
chassis: a modular pipeline that ingests RFP/RFQ documents and turns
them into a structured, categorized requirements registry plus a
milestone timeline (the "Agility Engine" dashboard).

## Layout

```
app.py                  Flask application factory
config.py                Env-driven settings (no secrets hardcoded)
wsgi.py                  Gunicorn entrypoint (wsgi:app)
routes/
  portal.py              HTML pages (/, /health, /upload, /dashboard)
  api.py                 JSON API (/api/v1/...)
services/
  bhive_parser.py         extract -> segment -> classify -> consistency-check -> assemble
  requirements_registry.py  JSON-file registry (swap for a DB later)
  governance.py           append-only .jsonl audit trail per project
  rfi_export.py           flagged contradictions -> RFI .docx
static/css/main.css      Blueprint/honeycomb design system
static/js/dashboard.js   Renders the milestone lattice + registry table
templates/               Jinja templates
deploy/
  nginx.conf              Reverse proxy site config for archiosk.com
  gunicorn.conf.py         Gunicorn worker/timeout settings
  gunicorn.service         systemd unit
```

## Local setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in FLASK_SECRET_KEY and ANTHROPIC_API_KEY
flask --app app run --debug
```

Visit `http://127.0.0.1:5000`. The dashboard works with demo data even
before you ingest anything — visit `/dashboard` directly.

To ingest a document:

```bash
curl -F "file=@sample_rfp.pdf" http://127.0.0.1:5000/api/v1/documents/ingest
```

The response includes a `project_id`; view its dashboard at
`/dashboard/<project_id>`.

### Without an Anthropic API key

The classifier stage falls back to a deterministic keyword-based
classifier automatically when `ANTHROPIC_API_KEY` is unset, so the
whole pipeline runs in local/dev environments without any API access.
Set the key in `.env` to switch on model-based classification.

## VPS deployment (Ubuntu + Nginx + Gunicorn)

```bash
# 1. Clone and set up the venv on the server
sudo mkdir -p /var/www/archiosk && cd /var/www/archiosk
git clone <your-repo-url> .
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # fill in real values, chmod 600 .env

# 2. Install the systemd service
sudo cp deploy/gunicorn.service /etc/systemd/system/archiosk.service
sudo systemctl daemon-reload
sudo systemctl enable --now archiosk

# 3. Install the Nginx site
sudo cp deploy/nginx.conf /etc/nginx/sites-available/archiosk.com
sudo ln -s /etc/nginx/sites-available/archiosk.com /etc/nginx/sites-enabled/
sudo certbot --nginx -d archiosk.com -d www.archiosk.com   # issue TLS certs first
sudo nginx -t && sudo systemctl reload nginx
```

`config.py` validates required env vars (`FLASK_SECRET_KEY`,
`ANTHROPIC_API_KEY`) at startup and logs a warning — rather than
crashing — if any are missing, so you can bring the box up and fix
config without a hard outage.

### Monitoring and timeout tuning

Point uptime monitoring (or a systemd timer) at `GET /health` — it's
proxied by a dedicated, quiet location in `deploy/nginx.conf` and checks
the registry store rather than the Anthropic API, so a slow/unreachable
model API won't take the app out of rotation on its own.

Ingestion timeouts are linked across three files, and they need to move
together:

- `.env` — `ANTHROPIC_TIMEOUT_SECONDS` (per-batch classify timeout,
  default 30s), `ANTHROPIC_CLASSIFY_BUDGET_SECONDS` (overall
  classify-stage ceiling regardless of document size, default 90s),
  and `ANTHROPIC_CONSISTENCY_TIMEOUT_SECONDS` (the cross-requirement
  contradiction check — see below — default 25s).
- `deploy/gunicorn.conf.py` — `GUNICORN_TIMEOUT` (worker timeout,
  default 150s).
- `deploy/nginx.conf` — `location /`'s `proxy_read_timeout` (150s;
  covers waiting on Gunicorn's response). `proxy_send_timeout` and
  `client_body_timeout` (120s) are a separate concern — upload
  transfer speed, not backend processing time — and don't need to
  move with the other two.

The classify budget plus the consistency-check timeout must stay
comfortably below `GUNICORN_TIMEOUT`/`proxy_read_timeout` — both run
as sequential Anthropic calls in the same request, so a large
document's classify stage (up to 90s) followed by the consistency
check (up to 25s) can get SIGKILLed mid-request before either reaches
its own fallback if you raise one without raising the others. Leave
at least 20-30s of headroom for extraction, segmentation, and the
registry save.

### Cross-requirement consistency check

After classification, a single Anthropic call reviews all extracted
requirements together looking for contradictions a per-line classifier
can't catch — e.g. a technical spec requiring a 30-day cure time next
to a milestone scheduling occupancy 10 days later. This requires
`ANTHROPIC_API_KEY`; there's no rule-based fallback, since it needs
actual reasoning across lines, not per-line keyword matching. It's
best-effort and never blocks ingestion — a document's
`consistency_checked` field distinguishes "checked, found nothing"
from "didn't actually check" (no API key, a timeout, or a malformed
model response), with a human-readable `consistency_note` explaining
which. Very large documents are capped at the first 150 requirements
to keep the prompt bounded; `consistency_note` says so when truncated.

### Governance audit trail

Every ingestion — via the API or the upload form — records a
`document_ingested` event in an append-only log (`services/governance.py`),
one `.jsonl` file per project (`instance/registry/<project_id>.governance.jsonl`),
always opened in append mode and never read-modify-rewritten. A
correction is recorded as a *new* event whose `predecessor_id` points
back at the event it corrects — the original line is never edited.
Read it via `GET /api/v1/documents/<id>/governance` or the dashboard's
audit-trail table.

**This app has no authentication system.** The upload form's optional
`actor`/`role` fields (and the API's matching form fields) are
free-text, defaulting to `"anonymous"`/`"unspecified"` when left
blank. They're recorded honestly as given — this is a labeled audit
trail, not verified identity or real access control. Don't rely on it
for anything that needs actual authorization.

`deploy/nginx.conf` serves `/static/` with a 30-day immutable cache.
That's only safe because `STATIC_VERSION` is appended as a `?v=`
query string on every static asset reference in `base.html` — bump
`STATIC_VERSION` in `.env` any time `main.css` or `dashboard.js`
changes, or browsers that already cached the old file won't see the
update for up to 30 days.

After bumping it, run `sudo systemctl restart archiosk` — **not**
`reload`. `EnvironmentFile` is only read by systemd when the unit
starts; `ExecReload`'s `SIGHUP` just tells gunicorn to reload its own
config and re-fork workers, it doesn't make systemd re-read `.env`. A
`reload` here will silently keep serving the old `STATIC_VERSION`.

## Security notes

- `.env` and any local `*.db` / `instance/` files are excluded via
  `.gitignore` — never commit real secrets.
- Every module that needs the Anthropic key reads it via
  `os.getenv("ANTHROPIC_API_KEY")` through `config.py` / `BHiveParser`
  — it is never hardcoded or passed as a literal.
- Uploads are capped (`MAX_UPLOAD_MB`, default 25MB) and restricted to
  `.pdf`, `.docx`, `.txt`, `.csv`.
- `deploy/nginx.conf` sends `Strict-Transport-Security`,
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin`, and a
  `Content-Security-Policy` (`default-src 'self'` with no exceptions —
  the app has no inline styles/scripts and no external resources of
  any kind) on every response (repeated inside `location /static/`
  since it already sets its own `add_header` for caching — nginx
  doesn't inherit a parent's `add_header` directives once a location
  defines any of its own). These are edge-only; the Flask app itself
  doesn't set them, since nginx already owns TLS/edge concerns here.
