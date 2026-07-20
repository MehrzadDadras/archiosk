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
  portal.py              HTML pages (/, /dashboard)
  api.py                 JSON API (/api/v1/...)
services/
  bhive_parser.py         extract -> segment -> classify -> assemble pipeline
  requirements_registry.py  JSON-file registry (swap for a DB later)
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

## Security notes

- `.env` and any local `*.db` / `instance/` files are excluded via
  `.gitignore` — never commit real secrets.
- Every module that needs the Anthropic key reads it via
  `os.getenv("ANTHROPIC_API_KEY")` through `config.py` / `BHiveParser`
  — it is never hardcoded or passed as a literal.
- Uploads are capped (`MAX_UPLOAD_MB`, default 25MB) and restricted to
  `.pdf`, `.docx`, `.txt`, `.csv`.
