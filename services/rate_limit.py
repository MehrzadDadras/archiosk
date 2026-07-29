"""
Flask-Limiter instance (CLAUDE-P27-B), created unbound like models.py's
`db = SQLAlchemy()` -- a module-level singleton so route decorators in
routes/portal.py and routes/api.py can import and use it directly,
bound to a real Flask app later via limiter.init_app(app) in app.py.
key_func is the real client IP as seen through ProxyFix (app.py), not
the nginx hop's own address.

Storage: in-memory (Flask-Limiter's own default), matching this app's
existing "no new infrastructure dependency unless genuinely needed"
stance (tools/dependency_fit.py). The one real caveat, stated plainly
rather than left implicit: under Gunicorn with GUNICORN_WORKERS > 1,
each worker process holds its OWN in-memory counter, so the effective
ceiling across the whole app is (configured limit x worker count), not
a single shared one. Still a real improvement over no limiting at all,
and exactly correct for a single-worker dev server -- a shared backend
(Redis) would close this gap but is a genuinely new infrastructure
dependency, out of scope for this fix.

Disabled entirely under TestingConfig (RATELIMIT_ENABLED=False,
config.py) so the existing test suite's real HTTP requests against
/login, /forgot-password, etc. across many test methods never
accumulate toward a shared limit and produce a spurious 429 -- tests
that specifically want to exercise rate limiting turn it back on and
call limiter.reset() first (see tests/test_rate_limiting.py).
"""
from __future__ import annotations

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
