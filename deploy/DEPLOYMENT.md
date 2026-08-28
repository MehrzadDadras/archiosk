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
  Also the SQLite database, which the code rollback in step 4 does NOT cover:
  a schema change needs its own backup, see step 8.
- `.venv/` — the server's own Python virtual environment. Never overwritten by the
  sync, but see step 7: a commit that changes `requirements.txt` requires a
  deliberate, pinned install into it.
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

## 7. Reconcile pinned dependencies when `requirements.txt` changed

**CLAUDE-DRAWING-REFS-02.** The sync above deliberately excludes `.venv/` as a
persistent path, and nothing else in this procedure installs anything — so a
commit that ADDS a dependency ships a `requirements.txt` naming it and leaves the
server venv without it. This was found before it caused an outage, but only
because the deploy was being checked against the diff rather than run by rote.

First, ask whether anything changed at all:

```bash
git diff <currently-live-hash>..<new-hash> -- requirements.txt
```

If that is empty, skip this section entirely — most deploys do.

If it is not empty, note what the failure would actually look like before
deciding urgency. A dependency imported at application start makes the service
fail to boot; one imported lazily (as `engine/pdf_extractor.py` is — nothing in
`app.py`/`routes/`/`services/` imports it) leaves the app healthy and the
capability silently inert, which `/health` will NOT catch.

Install the specific pinned packages that changed — **never**
`pip install -r requirements.txt`:

```bash
ssh ubuntu@<server> "
  /var/www/archiosk/.venv/bin/pip install --dry-run <package>==<version> 2>&1 | tail -5
"
```

The dry run first, always. Read it for two things: that a real wheel is being
resolved for the server's own interpreter and architecture (`cp310`,
`manylinux…x86_64` — a source build here means a compiler dependency this
document does not cover), and that the `Would install` line names ONLY the
package you intended.

`pip install -r requirements.txt` is the tempting shortcut and is wrong: it
re-resolves every pin in the file, so an unrelated transitive upgrade can land in
the same breath as a deploy and there is nothing in the diff that would show it.
Install what changed, pinned, and nothing else.

The install itself must run **as the venv's owner**, not as the SSH login:

```bash
ssh ubuntu@<server> "
  sudo -u archiosk /var/www/archiosk/.venv/bin/pip install <package>==<version> &&
  sudo -u archiosk /var/www/archiosk/.venv/bin/python -c 'import <module>; print(<module>.__version__)'
"
```

`sudo -u archiosk`, and specifically NOT bare `sudo`. `/var/www/archiosk/.venv` is owned
by `archiosk:archiosk` (the same account `archiosk-go.service` runs as), so the `ubuntu`
login cannot write to it — the first real attempt at this step failed with
`[Errno 13] Permission denied: .../site-packages/pymupdf`. Note the dry run does NOT
fail that way: it only reads, so it will happily report `Would install` for a package
the next command cannot actually place.

Reaching for plain `sudo` fixes the error message and leaves root-owned files inside a
venv every other package in which belongs to `archiosk` — which then fails later, at
uninstall or upgrade, far from the change that caused it. Confirm ownership matches its
neighbours afterwards:

```bash
ssh ubuntu@<server> "stat -c '%U:%G %n' /var/www/archiosk/.venv/lib/python3.10/site-packages/<module>"
```

The import check is the point — `pip` reporting success only proves files were
written, not that the module loads on this machine. Do this BEFORE the restart in
the next section, so the workers come up against the finished environment rather
than being restarted twice.

Then prove the CAPABILITY, not just the import — run the real entry point against real
data, as the service account, from the deployed tree:

```bash
ssh ubuntu@<server> "cd /var/www/archiosk && sudo -u archiosk .venv/bin/python -c \"
from engine.pdf_extractor import PDFVectorExtractor
d = PDFVectorExtractor().extract_document('tests/fixtures/metabolic_bridge/builder_corpus/Drawings_Set.pdf')
print('pages', len(d['pages']))
\""
```

This is the check `/health` structurally cannot perform, and the reason this whole
section exists.

Removals and version CHANGES (as opposed to additions) are not routine: they can
break code still running from the previous release during the window between sync
and restart. Treat those as outside this document and get explicit authorization.

## 8. Schema changes: `flask db stamp`, NOT `flask db upgrade`

**CLAUDE-STORAGE-BRIDGE-05.** Written after the first deploy that carried a
migration, from what actually happened rather than from what the tooling implies.

First, does this deploy change the schema at all?

```bash
git diff <currently-live-hash>..<new-hash> -- migrations/ models.py
```

Empty? Skip this section — most deploys do.

### Back the database up before anything else

The code rollback in step 4 excludes `instance/`, so it does NOT protect the
database. A schema change needs its own backup:

```bash
ssh ubuntu@<server> "
  STAMP=\$(date -u +%Y%m%dT%H%M%SZ)
  sudo mkdir -p /var/www/archiosk-db-backups
  sudo -u archiosk /var/www/archiosk/.venv/bin/python -c \"
import sqlite3
src = sqlite3.connect('/var/www/archiosk/instance/bhive.db')
dst = sqlite3.connect('/tmp/bhive-pre-<hash>.db')
with dst:
    src.backup(dst)
dst.close(); src.close()
c = sqlite3.connect('/tmp/bhive-pre-<hash>.db')
print('integrity:', list(c.execute('PRAGMA integrity_check'))[0][0])
\"
  sudo cp -p /tmp/bhive-pre-<hash>.db /var/www/archiosk-db-backups/bhive-pre-<hash>-\$STAMP.db
  sudo rm -f /tmp/bhive-pre-<hash>.db
"
```

**Python's `sqlite3.Connection.backup()`, NOT the `sqlite3` command-line tool.**
That distinction is the entire point of this block, and it was got wrong once:
an earlier version of this document prescribed
`sudo -u archiosk sqlite3 ... ".backup '...'"`, and **the `sqlite3` binary is not
installed on this server**. The command failed with `sudo: sqlite3: command not
found`. Worse, the first deploys that ran it had a `|| sudo cp -p` fallback, so
they silently produced plain file copies while the runbook claimed a write-safe
online backup. The copies happened to be fine — the database was idle — but the
document was asserting a safety property it was not delivering.

`Connection.backup()` is the same online-backup API the CLI's `.backup` command
wraps, and it ships with the interpreter the application already runs on, so
there is nothing to install. It is safe against a live database with writers
attached; a plain `cp` of a file mid-write is a corrupt file.

Always print `PRAGMA integrity_check` on the copy, as above. A backup nobody
verified is a belief, not a rollback point.

Then check what is actually in it before trusting it:

```bash
ssh ubuntu@<server> "sudo -u archiosk /var/www/archiosk/.venv/bin/python -c \"
import sqlite3
c = sqlite3.connect('/var/www/archiosk-db-backups/<file>.db')
print('tables:', len(list(c.execute(\\\"SELECT name FROM sqlite_master WHERE type='table'\\\"))))
print('users :', list(c.execute('SELECT COUNT(*) FROM users'))[0][0])
\""
```

Note also that the cleanup in the last section runs unprivileged and cannot
remove the root-owned `/tmp` artefact `sudo cp` leaves behind — hence the
explicit `sudo rm -f` above rather than leaving it for the sweep.

### Why `flask db upgrade` cannot be used here

`app.py`'s `_register_database()` calls `db.create_all()` inside `create_app`, on
**every boot and every CLI invocation**. So any `flask db ...` command loads the
app, creates every missing table from the models, and only then hands control to
Alembic — which immediately tries to `CREATE TABLE` something that now exists.

This was verified against a COPY of the production database before touching the
real one, and it fails in both directions:

- `flask db upgrade` straight away → `table diagnostic_reports already exists`
  (production was stamped at `d67fbff1ba5e` while that table already existed —
  `a3f1c07d92b4` had never actually run; `create_all()` made it).
- Correcting the stamp first and retrying → `table storage_agent_enrolments
  already exists`, because merely running `flask db stamp` had already created
  it via `create_all()`.

There is no ordering that avoids this. `create_all()` always wins the race.

### What actually works

`create_all()` builds the new table correctly during the restart in the next
section, and Alembic is then told the truth:

```bash
ssh ubuntu@<server> "cd /var/www/archiosk &&
  sudo -u archiosk .venv/bin/python -m flask db stamp head &&
  sudo -u archiosk .venv/bin/python -m flask db current"
```

Run this AFTER the restart, because that is what creates the table. Confirm
`flask db current` reports the new head, and that a following `flask db upgrade`
now does nothing at all.

This is sound only because `tests/test_flask_migrate_baseline.py` asserts that a
migrated database and a `create_all()` database have identical schemas. That test
is what makes `create_all()` an acceptable substitute for running the migration,
and it is why a migration whose shape drifts from its model is a genuine failure
rather than a cosmetic one — it caught exactly that in this very change.

### The limits of this

Fine for CREATE TABLE, which `create_all()` handles. It does NOT handle an ALTER:
a new column on an existing table, a type change, a rename, or any data migration
is invisible to `create_all()` and will silently not happen. Note that `app.py`
already carries three hand-written `_migrate_users_*` column-adders for exactly
this reason. Anything of that kind is outside this document — stop, and get
explicit Product Owner authorization.

## 9. Restart and verify the service

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

## 10. Bump `STATIC_VERSION` when static assets changed

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

Then repeat the restart/health verification in step 9.

## 11. Verify online, in a real browser — not localhost

Open the actual `https://archiosk.com` routes and confirm the specific surfaces the
deploy changed. At minimum: sign-in, authentication, Gateway, opening a project, and
whatever else was in scope for that deploy. Confirm the deployed `STATIC_VERSION`
value actually appears in a served asset URL (e.g. inspect
`<link href="/static/css/main.css?v=...">` in the rendered page) to prove the bump
in step 10 took effect, not just that the command ran.

## 12. Confirm which commit is actually live

The systemd unit's own `Description=` field is the existing, already-established
convention for this — e.g. `Gunicorn - ArchiOSK GO (accepted build <short-hash>)`.
Update it only if doing so is a small, low-risk edit to the unit file (and reload
systemd's unit cache afterward, `sudo systemctl daemon-reload`) — never introduce
unnecessary systemd configuration risk merely to display a hash. Whatever the
mechanism, the durable requirement is: **it must always be possible to determine
exactly which git commit is live**, checkable without guessing.

## 13. Clean up this deploy's own scratch (do this every time, not just when it piles up)

`CLAUDE-DEV-CLEANUP-01` found eight superseded deploy tarballs (~21.5MB) sitting in
`/tmp` from prior sessions, none ever cleaned up after its own deploy succeeded —
routine hygiene that was never made an explicit step, so it silently never happened.
Once step 11's online verification passes:

```bash
ssh ubuntu@<server> "rm -rf /tmp/archiosk-<short-hash>.tar /tmp/archiosk-deploy-staging"
```

The step-4 backup (`/var/www/archiosk-backup-<hash>`) is the real rollback point,
not this scratch — it's safe to remove immediately, not "eventually." Keep at most
the current deploy's own backup and the previous one if you want one extra rollback
generation; remove older `archiosk-backup-<hash>` directories once you're confident
the current deploy is stable (a separate, deliberate decision each time, not part of
routine per-deploy cleanup — don't automate away your only rollback point).

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
- Any change to `.env`'s contents beyond the single `STATIC_VERSION` line in step 10.
- A multi-generation, automatic-rollback release scheme — the current flat
  single-backup approach is a deliberately minimal first safeguard, not a
  redesign of the whole deployment system.
