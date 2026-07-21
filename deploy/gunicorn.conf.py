"""Gunicorn config for the archiosk.com VPS deployment."""
import multiprocessing
import os

bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8000")
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
# sync workers handle one request at a time; a slow ingest can legitimately
# hold one for up to GUNICORN_TIMEOUT (150s), so a handful of concurrent
# large uploads could exhaust every worker and start queuing even a fast
# /health check. gthread gives each worker a thread pool instead, so a
# request blocked on Anthropic/disk I/O doesn't block everything else in
# that worker -- the right fit here since nothing in this app is CPU-bound
# (checked: BHiveParser, the Anthropic client, RequirementsRegistry, and
# GovernanceLog are all constructed fresh per request with no shared
# mutable state, so there's nothing thread-unsafe being introduced).
worker_class = os.getenv("GUNICORN_WORKER_CLASS", "gthread")
threads = int(os.getenv("GUNICORN_THREADS", "4"))
# Must stay comfortably above ANTHROPIC_CLASSIFY_BUDGET_SECONDS (default 90s)
# plus ANTHROPIC_CONSISTENCY_TIMEOUT_SECONDS (default 25s) -- the consistency
# check runs as a second sequential Anthropic call in the same request --
# plus extraction/segmentation/save overhead, or a worker mid-request on a
# large document gets SIGKILLed before it can fall back gracefully. Keep in
# sync with nginx's proxy_read_timeout on location / in deploy/nginx.conf.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "150"))
graceful_timeout = 30
keepalive = 5

# Sync workers heartbeat via a temp file so the arbiter can detect hangs;
# on a slow/loaded disk that write can lag enough to trigger a false-
# positive "worker timed out" kill, unrelated to the actual request.
# tmpfs sidesteps that — not affected by systemd's PrivateTmp, which only
# isolates /tmp and /var/tmp.
worker_tmp_dir = os.getenv("GUNICORN_WORKER_TMP_DIR", "/dev/shm")

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Restart workers periodically to shed memory bloat, with jitter so all
# workers don't recycle at once.
max_requests = 1000
max_requests_jitter = 100
