# Cognitive Gym read-only dashboard

Route: `/admin/cognitive-gym`, linked in the existing Developer Mode menu.
Both the existing admin role and enabled Developer Mode are required, including
for direct URL access. There are no execution or mutation endpoints.

`services/cognitive_gym.py` rebuilds the board from the accepted capability
catalog and evaluator summaries on each request when the evaluator is mounted.
Set application config `COGNITIVE_GYM_EVALUATOR_ROOT` for a different mount.
It reads summary/result/material records and report/seal references, never tools,
keys, provider credentials, request dumps or assessment stimuli. Raw responses
are escaped and credential-shaped strings are redacted. Unrecognized sessions
remain visible through their reports; missing/corrupt records produce gaps.
Seal references do not claim that this dashboard requalified the evidence.

Completed `records/*-result.json`, legacy `examiner/*-complete.json` and the
first `examiner/development-record.json` are separate encounters. Summary copies
are not counted again. GOtex is never pooled into GO performance. Assessment
preflight and qualification are not assessment executions. The projection can
read explicit `assessment-record.json` (mode ASSESSMENT, completed and valid),
`transfer-record.json` (executed with named source/destination realms), and
`capability-status.json` (authorized with authority_ref and an established status).
Unknown future schemas need a reader adapter; the dashboard does not guess.

On hosts without the evaluator, rebuild a derived snapshot outside the evaluator:

```powershell
venv\Scripts\python.exe -B tools\export_cognitive_gym.py --source C:\Archiosk\FlightTests\evaluator --output $env:TEMP\cognitive-gym-projection.json
```

Publish that file atomically to `instance/cognitive_gym/projection.json` using
the established deployment connection. It is derived, replaceable, not source
authority, and excluded from git. Rebuild/publish after new evaluator records;
no application code edit or restart is needed. The UI labels snapshot capture
time so reload is never mistaken for a new evaluator synchronization. No timer
or provider-triggering hook is introduced. Empty-source export fails rather
than replacing a valid snapshot. Mounted-source refresh is automatic per GET.

Counts are factual counts within recognized records, not intelligence scores.
DEVELOPMENT ONLY is an activity label, not a governed capability status. Changes
of challenge are proposals unless recorded as executed. Displaying a status,
raw response, stop or intervention creates no promotion or causal learning claim.

The board uses categorical actor bands and chronological encounters; it has no
numeric performance axis. Mobile uses a focus-first layout with a bounded table
scroll region and native disclosure details.
