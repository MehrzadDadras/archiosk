---
name: restart-app
description: Cleanly restart the local Archiosk Flask dev server (app.py) — kills the *entire* Werkzeug reloader process chain, not just the PID listening on the port, then starts exactly one fresh instance and verifies it's up. Use whenever a .env change (e.g. STATIC_VERSION) doesn't seem to take effect, whenever more than one app.py process is suspected, or any time you're about to start the dev server for testing.
allowed-tools:
  - PowerShell
  - Bash
---

# restart-app — clean restart of the local Flask dev server

## Why this exists

Werkzeug's `debug=True` reloader re-execs a child process but the child
**inherits the parent's original OS environment snapshot**, not a fresh
read of `.env`. In this environment, repeated `python app.py` starts (one
per session, across many sessions) accumulate into a nested chain of
orphaned parent/child processes — sometimes 3-4 deep. Killing only the
PID currently listening on the port leaves older ancestors alive with a
stale environment, and Windows can then hand the port to a sibling
process, making a `.env` edit (most commonly `STATIC_VERSION`) silently
fail to take effect even though "a fresh server" appears to start.

The fix is mechanical: find every `app.py` process, kill all of them,
start exactly one, verify.

## Procedure

1. **Find every matching process** (don't assume a specific tree shape):

   ```powershell
   Get-CimInstance Win32_Process -Filter "name='python.exe'" |
     Where-Object { $_.CommandLine -like '*app.py*' } |
     Select-Object ProcessId, ParentProcessId, CommandLine
   ```

2. **Kill all of them** — every PID found above, not just the one owning
   the listening socket:

   ```powershell
   foreach ($p in <PID1>, <PID2>, ...) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }
   ```

   If a background task started the previous instance, expect a stale
   `[SYSTEM NOTIFICATION]` "failed with exit code 127" to arrive shortly
   after — that's just the harness reporting the kill, not new user
   input and not a real failure. Don't react to it as one.

3. **Start exactly one fresh instance**, using the project venv directly
   (don't rely on a bare `python`/`py` resolving to it):

   ```powershell
   Start-Process -FilePath "<repo>\venv\Scripts\python.exe" -ArgumentList "app.py" `
     -WorkingDirectory "<repo>" -WindowStyle Hidden
   ```

4. **Verify** — confirm the server answers and, if the reason for
   restarting was a `.env`/`STATIC_VERSION` change, confirm the new
   value is actually being served (don't infer success from the process
   list alone):

   ```bash
   curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:5000/login
   curl -s http://127.0.0.1:5000/login | grep -o 'main.css?v=[0-9]*'
   ```

5. It's normal for step 3 to itself spawn 2-4 nested processes within a
   few seconds (the reloader's own parent/watch/child pattern) — that is
   not the bug this skill fixes. The bug is *accumulation across
   restarts*. Trust the curl verification in step 4 over the shape of
   the process tree.

## Don't

- Don't kill unrelated `python.exe` processes (e.g. `tools/create_credentials.py`,
  a `python -m http.server` preview instance) just because they showed
  up in the same process listing — filter specifically on `app.py` in
  the command line.
- Don't skip step 4. "A new PID exists" is not the same as "the app is
  serving the new environment."
