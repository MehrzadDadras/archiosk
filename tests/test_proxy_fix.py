"""
CLAUDE-P27-B: deploy/nginx.conf is the one reverse proxy in front of
Gunicorn -- without ProxyFix, request.remote_addr is always nginx's own
address for every request, which would silently break any future
per-IP control (rate limiting, abuse blocking) rather than merely being
imprecise. Trusts exactly one X-Forwarded-* hop (x_for=1), matching
that single-proxy topology.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest

from werkzeug.middleware.proxy_fix import ProxyFix


class ProxyFixTests(unittest.TestCase):
    def test_create_app_wraps_wsgi_app_with_proxy_fix(self):
        import app as app_module

        flask_app = app_module.create_app("testing")
        self.assertIsInstance(flask_app.wsgi_app, ProxyFix)

    def test_health_route_sees_real_client_ip_through_proxy_fix(self):
        import app as app_module
        from flask import request

        flask_app = app_module.create_app("testing")
        with flask_app.test_client() as client:
            client.get(
                "/health",
                headers={"X-Forwarded-For": "203.0.113.7"},
                environ_overrides={"REMOTE_ADDR": "10.0.0.1"},  # simulating nginx's own address
            )
            self.assertEqual(request.remote_addr, "203.0.113.7")

    def test_health_route_falls_back_to_direct_remote_addr_with_no_proxy_header(self):
        # Local dev (no nginx in front): the header is simply absent,
        # and remote_addr behaves exactly as it already did before this.
        import app as app_module
        from flask import request

        flask_app = app_module.create_app("testing")
        with flask_app.test_client() as client:
            client.get("/health", environ_overrides={"REMOTE_ADDR": "127.0.0.1"})
            self.assertEqual(request.remote_addr, "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
