# Deploying ARCHIOSK to the live environment

**CLAUDE-DEPLOY-01.** Recorded after the first controlled, Product-Owner-authorized
deployment of an exact tested commit to the live `archiosk.com` environment. This
document is the durable record of that procedure — treat it as the normal path for
routine, tested, committed, pushed, reversible application-code changes; anything
outside that envelope (infrastructure, DNS, credentials, persistent-data migrations,
destructive operations, hosting/billing changes) still requires explicit
Product-Owner authorization each time, not this document.

No credentials, private keys, or secret values are recorded here or should ever be
added here.

## Target identity

- **Live hostname:** `archiosk.com` / `www.archiosk.com`.
- **Application path on the server:** `/var/www/archiosk`, owned by the `archiosk`
  service account (not the SSH login account).
- **Service:** `archiosk-go.service` (systemd) — gunicorn workers bound to
  `127.0.0.1:8000`; nginx (`deploy/nginx.conf`, deployed separately, not part of the
  routine sync below) reverse-proxies `443` to it.
- The application directory is **not a git repository** — there is no `git pull` on
  the server. The repository's own `origin/main` on GitHub is the actual system of
  record (per `CLAUDE.md`); the server only ever receives a synced copy of one exact
  commit's tracked files.

## Persistent paths — never overwritten by a routine deploy

These live only on the server, are never part of the exact-commit export, and must
be excluded from every sync:

- `.env` — real secrets (API keys, Flask secret key, `STATIC_VERSION`, etc.).
- `instance/` — the real, live project registry and all real project data.
- `.venv/` — the server's own Python virtual environment.
- `__pycache__/` — build artifacts, regenerated on next run regardless.
- `.claude/` — local tooling state on the server, unrelated to the deployed app.

## 1. Confirm the checkpoint before packaging anything

```bash
git status --short          # must be clean (or only pre-existing, unrelated untracked items)
git rev-parse HEAD
git fetch origin main --quiet && git rev-parse origin/main   # must match HEAD
```

Only deploy a commit that is genuinely `HEAD == origin/main`, and that has already
passed this repository's normal focused/full-suite testing discipline for whatever
it changed. Never deploy uncommitted working-tree contents.

## 2. Package the exact commit (deterministic, not the mutable working tree)

```bash
git archive --format=tar --prefix=archiosk-<short-hash>/ HEAD -o /tmp/archiosk-<short-hash>.tar
```

`git archive` exports only tracked, committed files — `.env`, `instance/`, and every
other git-ignored path are structurally absent from the tarball, not merely
excluded by convention.

## 3. Transfer and stage on the server

```bash
scp /tmp/archiosk-<short-hash>.tar ubuntu@<server>:/tmp/archiosk-<short-hash>.tar
ssh ubuntu@<server> "
  mkdir -p /tmp/archiosk-deploy-staging &&
  cd /tmp/archiosk-deploy-staging &&
  tar -xf /tmp/archiosk-<short-hash>.tar --strip-components=1
"
```

## 4. Back up the currently-live application code (rollback point)

Before touching the live directory, copy the current application-code files
(excluding the persistent paths above) to a sibling directory named for the
currently-deployed commit:

```bash
ssh ubuntu@<server> "
  sudo mkdir -p /var/www/archiosk-backup-<current-short-hash> &&
  sudo rsync -a \
    --exclude='.claude/' --exclude='.env' --exclude='.venv/' \
    --exclude='__pycache__/' --exclude='instance/' \
    /var/www/archiosk/ /var/www/archiosk-backup-<current-short-hash>/
"
```

This is a flat, single-generation rollback point — not a versioned releases/symlink
scheme. Good enough for the current scale; revisit if routine deploys become
frequent enough to want automatic history.

## 5. Dry-run before the first real write

Run the sync with `-n` (dry-run) first, entirely server-side (both the staging
directory and `/var/www/archiosk` are local to the server, so this needs no local
`rsync` binary):

```bash
ssh ubuntu@<server> "
  sudo rsync -avn --delete \
    --exclude='.claude/' --exclude='.env' --exclude='.venv/' \
    --exclude='__pycache__/' --exclude='instance/' \
    /tmp/archiosk-deploy-staging/ /var/www/archiosk/
"
```

Inspect the output for:

- **Any `*deleting` line** naming something outside expected application-code
  paths — stop and understand why before proceeding.
- **Any mention of `.env`, `instance/`, `.venv/`, `.claude/`, `__pycache__/`** at
  all — the excludes should make these structurally impossible to see; if one
  appears, stop.
- Use `-i` (itemize-changes) for a clearer per-file view if needed — an `s` flag
  in the itemized output means the file's byte size actually differs (a real
  content change); files that only show timestamp/owner/group differences
  (`t`/`o`/`g`) are unchanged content re-copied with fresh metadata, from
  `git archive` never preserving original commit timestamps.

If the dry-run proposes touching anything outside the expected application-code
surface: **stop**. Do not proceed until the reason is understood.

## 6. Deploy

```bash
ssh ubuntu@<server> "
  sudo rsync -a --delete \
    --exclude='.claude/' --exclude='.env' --exclude='.venv/' \
    --exclude='__pycache__/' --exclude='instance/' \
    --chown=archiosk:archiosk \
    /tmp/archiosk-deploy-staging/ /var/www/archiosk/
"
```

## 7. Restart and verify the service

```bash
ssh ubuntu@<server> "
  sudo systemctl restart archiosk-go.service &&
  sudo systemctl status archiosk-go.service --no-pager | head -20 &&
  sudo journalctl -u archiosk-go.service --since '2 minutes ago' --no-pager | grep -iE 'error|traceback|exception|critical'
"
```

The grep for errors should return nothing. Then:

```bash
ssh ubuntu@<server> "curl -s -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:8000/health"
curl -s -o /dev/null -w 'HTTP %{http_code}\n' https://archiosk.com/health
```

Both must return `HTTP 200`.

## 8. Bump `STATIC_VERSION` when static assets changed

**If this deploy touched `static/css/*.css` or `static/js/*.js`**, the server's own
`STATIC_VERSION` (inside its protected `.env`, untouched by the steps above) must be
incremented, or nginx's `Cache-Control: public, immutable; expires 30d` on
`/static/` means browsers keep serving the previously-cached content at the
unchanged `?v=<N>` URL indefinitely — the exact same quirk `CLAUDE.md` documents for
local dev, which applies online too and is easy to miss precisely because deploying
new template/route code succeeds and *looks* complete while the visible styling
silently stays stale.

This is the one step in this whole procedure that edits a file already on the
server rather than something shipped from the repo — treat it with the same care
as any other production `.env` edit (scoped, minimal, never printing the file's
other contents, which include real secrets):

```bash
ssh ubuntu@<server> "
  CURRENT=\$(sudo grep -oP '^STATIC_VERSION=\K[0-9]+' /var/www/archiosk/.env) &&
  NEW=\$((CURRENT + 1)) &&
  sudo sed -i \"s/^STATIC_VERSION=.*/STATIC_VERSION=\$NEW/\" /var/www/archiosk/.env
"
```

Then repeat the restart/health verification in step 7.

## 9. Verify online, in a real browser — not localhost

Open the actual `https://archiosk.com` routes and confirm the specific surfaces the
deploy changed. At minimum: sign-in, authentication, Gateway, opening a project, and
whatever else was in scope for that deploy. Confirm the deployed `STATIC_VERSION`
value actually appears in a served asset URL (e.g. inspect
`<link href="/static/css/main.css?v=...">` in the rendered page) to prove the bump
in step 8 took effect, not just that the command ran.

## 10. Confirm which commit is actually live

The systemd unit's own `Description=` field is the existing, already-established
convention for this — e.g. `Gunicorn - ArchiOSK GO (accepted build <short-hash>)`.
Update it only if doing so is a small, low-risk edit to the unit file (and reload
systemd's unit cache afterward, `sudo systemctl daemon-reload`) — never introduce
unnecessary systemd configuration risk merely to display a hash. Whatever the
mechanism, the durable requirement is: **it must always be possible to determine
exactly which git commit is live**, checkable without guessing.

## Rollback

If the service doesn't restart cleanly, `/health` fails, authentication fails, the
application can't open normally, obvious static/CSS/JS corruption appears, or
persistent data appears affected: stop immediately (do not stack further
speculative changes on a broken deploy) and restore the step-4 backup:

```bash
ssh ubuntu@<server> "
  sudo rsync -a --delete \
    --exclude='.claude/' --exclude='.env' --exclude='.venv/' \
    --exclude='__pycache__/' --exclude='instance/' \
    --chown=archiosk:archiosk \
    /var/www/archiosk-backup-<previous-short-hash>/ /var/www/archiosk/ &&
  sudo systemctl restart archiosk-go.service
"
```

Then repeat the step-7 health verification.

## What this document deliberately does not cover

- Provisioning a new server, DNS, TLS certificates, or nginx/systemd unit files
  themselves (`deploy/nginx.conf`, `deploy/gunicorn.service`,
  `deploy/gunicorn.conf.py` already exist and are deployed separately, far less
  often than application code).
- Database/schema migrations.
- Any change to `.env`'s contents beyond the single `STATIC_VERSION` line in step 8.
- A multi-generation, automatic-rollback release scheme — the current flat
  single-backup approach is a deliberately minimal first safeguard, not a
  redesign of the whole deployment system.
