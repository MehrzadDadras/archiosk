"""Gunicorn config for the archiosk.com VPS deployment."""
import multiprocessing
import os

bind = os.getenv("GUNICORN_BIND", "127.0.0.1:8000")
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
# Must stay comfortably above ANTHROPIC_CLASSIFY_BUDGET_SECONDS (default 90s
# in .env.example) plus extraction/segmentation/save overhead, or a worker
# mid-classification on a large document gets SIGKILLed before it can fall
# back to rule-based classification. Keep in sync with nginx's
# proxy_read_timeout on location / in deploy/nginx.conf.
timeout = int(os.getenv("GUNICORN_TIMEOUT", "120"))
graceful_timeout = 30
keepalive = 5

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Restart workers periodically to shed memory bloat, with jitter so all
# workers don't recycle at once.
max_requests = 1000
max_requests_jitter = 100
