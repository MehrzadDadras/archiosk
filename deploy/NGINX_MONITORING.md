# nginx critical-error monitoring

**CLAUDE-NGINX-CRIT-MONITOR-01.** A five-minute check that reads new
`[crit]`/`[alert]`/`[emerg]` lines out of `/var/log/nginx/error.log` and alerts
on the ones that are actually this server's fault.

## Why it exists

On 2026-08-29 a `sudo nginx -t -c /tmp/nginxtest/test.conf` chowned
`/var/lib/nginx/*` to `nobody`: that throwaway config declared no
`user www-data;`, so nginx fell back to its compiled-in default and re-owned its
own temp directories as a side effect of a **syntax check**.

nginx workers run as `www-data`. From that moment, any request body too large to
buffer in memory failed:

```
open() "/var/lib/nginx/body/00000000NN" failed (13: Permission denied)
```

nginx returned 500 **before proxying**, so gunicorn never saw the request and the
application log stayed clean. Document upload was broken for **~40 hours** and
was found only when the Product Owner tried to use it.

nginx wrote `[crit]` for all 40 of those hours. Nothing read it. That is the gap
this closes.

## What is installed

| Artifact (tracked here) | Installed to |
|---|---|
| `deploy/nginx_crit_monitor.py` | `/usr/local/bin/archiosk-nginx-monitor` (0755 root:root) |
| `deploy/archiosk-nginx-monitor.service` | `/etc/systemd/system/` (0644) |
| `deploy/archiosk-nginx-monitor.timer` | `/etc/systemd/system/` (0644) |
| — | `/var/lib/archiosk-nginx-monitor/state.json` (cursor, created on first run) |

Nothing is installed into `/var/www/archiosk`. **This is deliberate:** the
application tree is an exact export of one commit (see `DEPLOYMENT.md`), and
dropping an extra file into it would make the live tree stop matching the
deployed hash. Monitoring is infrastructure, so it lives beside `nginx.conf` and
`gunicorn.service` and is installed separately, exactly as they are.

## Install

```bash
scp deploy/nginx_crit_monitor.py deploy/archiosk-nginx-monitor.service \
    deploy/archiosk-nginx-monitor.timer ubuntu@<server>:/tmp/

ssh ubuntu@<server> "
  # A Windows checkout ships CRLF. The shebang becomes 'python3\r' and execve
  # fails with a confusing 'No such file or directory'. Strip it, every time.
  sed -i 's/\r\$//' /tmp/nginx_crit_monitor.py \
      /tmp/archiosk-nginx-monitor.service /tmp/archiosk-nginx-monitor.timer &&
  sudo install -m 0755 -o root -g root /tmp/nginx_crit_monitor.py \
      /usr/local/bin/archiosk-nginx-monitor &&
  sudo install -m 0644 -o root -g root /tmp/archiosk-nginx-monitor.service \
      /etc/systemd/system/ &&
  sudo install -m 0644 -o root -g root /tmp/archiosk-nginx-monitor.timer \
      /etc/systemd/system/ &&
  sudo mkdir -p /var/lib/archiosk-nginx-monitor &&
  rm -f /tmp/nginx_crit_monitor.py /tmp/archiosk-nginx-monitor.service \
        /tmp/archiosk-nginx-monitor.timer
"
```

Then, **in this order**:

```bash
# 1. Dry run first. Reads everything, sends nothing, writes no state.
ssh ubuntu@<server> "sudo /usr/local/bin/archiosk-nginx-monitor --dry-run --since-start"

# 2. Set the cursor to EOF so the first live run does not alert on history.
ssh ubuntu@<server> "sudo /usr/local/bin/archiosk-nginx-monitor --reset"

# 3. Enable.
ssh ubuntu@<server> "sudo systemctl daemon-reload &&
                     sudo systemctl enable --now archiosk-nginx-monitor.timer"
```

Step 2 matters. At install time the log held 52 actionable `[crit]` lines, all
of them the **already-fixed** incident above. A monitor whose very first message
is a false alarm about a solved problem has spent its credibility before it has
reported anything real.

## Verify

```bash
systemctl list-timers archiosk-nginx-monitor.timer
systemctl show archiosk-nginx-monitor.service -p Result --value     # success
sudo journalctl -u archiosk-nginx-monitor.service -n 20 --no-pager
sudo cat /var/lib/archiosk-nginx-monitor/state.json
```

To prove detection end to end without writing into the production log, point the
installed binary at a scratch file:

```bash
T=$(mktemp -d)
printf '2026/01/01 00:00:00 [crit] 1#1: *1 open() "/var/lib/nginx/body/1" failed (13: Permission denied)\n' > $T/error.log
ARCHIOSK_NGINX_ERROR_LOG=$T/error.log ARCHIOSK_MONITOR_STATE=$T/s.json \
  /usr/local/bin/archiosk-nginx-monitor
rm -rf $T
```

## Alert routing

Set **one** in the `.service` file, then `daemon-reload`:

| Sink | Set | Notes |
|---|---|---|
| Journal | *(neither variable)* | Default. Works, but nobody watches a journal — the weakest sink, and honest about it. |
| Webhook | `ARCHIOSK_ALERT_WEBHOOK` | POSTs `{"text": ...}`. Needs no access to `.env`. |
| Email | `ARCHIOSK_ALERT_EMAIL` | Reuses `SMTP_*` from `/var/www/archiosk/.env`. **Also requires uncommenting the two `CAP_DAC_READ_SEARCH` lines** — `.env` is `0600 archiosk:archiosk` and the unit holds no capability that overrides file permissions. |

## Design properties worth not breaking

**It must not lose an alert.** The cursor advances only *after* delivery
succeeds. A failed send leaves it where it was, so the next run re-reports the
same lines. Duplicate alerts are an annoyance; a dropped one recreates the exact
blindness this exists to end.

**It must not invent one.** Rotation is detected by **inode**, not size.
logrotate runs daily here with `create 0640 www-data adm`, so a fresh file
legitimately starts at 0 bytes — a size-only check would replay the entire
previous day, every night.

**It fails closed.** Unreadable log, unwritable or corrupt state, bad ignore
regex, failed delivery: all exit non-zero *without* advancing the cursor, and
systemd records the failure. It never reports "ok" when it could not actually
look. (This is not theoretical: the first real timer run failed with `EACCES`
because an empty `CapabilityBoundingSet` drops `CAP_DAC_OVERRIDE` and
`error.log` is `www-data:adm 0640`. `SupplementaryGroups=adm` is the fix. A
monitor that swallowed that error would have reported "no critical lines"
forever, which is worse than not having one.)

**It suppresses noise without hiding it.** Scanner TLS handshake failures
(`SSL_do_handshake() failed`) are `[crit]` to nginx but are not this server's
fault, and they arrive forever — 19 of the 71 lines present at install. They
never raise an alert alone, but their count appears in every alert that is
raised. Extend via `ARCHIOSK_ALERT_IGNORE` (regexes, one per line) rather than
editing the script.

**It writes nothing except its own state.** `ProtectSystem=strict` with a single
`ReadWritePaths=/var/lib/archiosk-nginx-monitor`, enforced by systemd rather than
trusted to the script.

## Tests

`tests/test_nginx_crit_monitor_01.py` — 22 tests, in the normal suite. Loads the
script by path (same approach as `tests/test_storage_bridge_agent_04.py` for
`tools/storage_bridge_agent.py`) and asserts the properties above against real
behaviour, including that the shipped unit files still match the installed paths.

## What this deliberately does not do

- **Read rotated history.** On rotation it starts at the new file's beginning; it
  does not chase `error.log.1.gz`. The window it can miss is bounded by one
  logrotate interval, and reading compressed history is a materially larger
  program.
- **Watch anything but nginx.** gunicorn already logs into the journal, and the
  application's own errors were never the blind spot.
- **Page anyone.** There is no escalation, no on-call rotation, no deduplication
  window beyond the cursor. This is a smoke detector, not a monitoring system.
