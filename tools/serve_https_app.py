"""Run the REAL Flask application over HTTPS on the LAN, for device testing.

WHY THIS IS A SEPARATE FILE AND NOT `python app.py --ssl`

`app.py`'s `__main__` binds `127.0.0.1` unconditionally, and its own comment
records that as a deliberate decision rather than an incident — the same block
that turned Werkzeug's interactive debugger off by default after a real
security incident. Adding an "also listen on every interface" mode there would
loosen exactly that constraint for every future reader of that file.

So the LAN exposure lives here instead, in a tool whose name says what it does
and which nothing imports. `app.py` is untouched.

`tools/serve_https_harness.py` serves STATIC files and cannot execute a route,
which is why it could not test this: `/project/<id>/sheet/<id>`,
`/project/<id>/friction` and `/project/<id>/escalation` are real Flask routes
and need the real application.

WHAT THIS EXPOSES, STATED PLAINLY

The whole application, with whatever data the configured database and registry
store actually contain, to every device on the local network, for as long as it
runs. That is the point — a phone has to reach it — and it is also the risk.
Three things narrow it:

  - The interactive debugger is OFF and cannot be turned on from here.
  - It refuses to start against a production configuration.
  - It prints the certificate fingerprint, so the warning accepted on the
    phone can be checked rather than accepted blind.

Ctrl-C stops it. Nothing is written to the repository.

USAGE

    ./venv/Scripts/python.exe tools/serve_https_app.py
    ./venv/Scripts/python.exe tools/serve_https_app.py --port 8643
"""
from __future__ import annotations

import argparse
import os
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.serve_https_harness import certificate_for, fingerprint, lan_address

DEFAULT_PORT = 8643


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", default="0.0.0.0",
                        help="default 0.0.0.0 - the whole point is LAN reach")
    parser.add_argument(
        "--cert-dir",
        default=str(Path(os.environ.get("TEMP", "/tmp")) / "archiosk-harness-tls"),
        help="throwaway key/cert location. Never inside the repository.")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[1]
    cert_dir = Path(args.cert_dir).resolve()
    if repo == cert_dir or repo in cert_dir.parents:
        raise SystemExit(
            f"refusing to write a private key inside the repository: {cert_dir}")

    from app import create_app

    config_name = os.getenv("FLASK_ENV") or "development"
    if config_name.lower().startswith("prod"):
        raise SystemExit(
            "refusing to serve a PRODUCTION configuration on the LAN. This tool "
            "is for local device testing against local data; production is "
            "reached over its own TLS at archiosk.com.")

    application = create_app(config_name)

    host = lan_address()
    cert, key = certificate_for(host, cert_dir)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert), keyfile=str(key))

    print("ARCHIOSK application over HTTPS - LOCAL DEVICE TESTING")
    print(f"  config       {config_name}")
    print(f"  registry     {application.config.get('REGISTRY_STORE_PATH')}")
    print(f"  assets       {application.config.get('PROJECT_ASSET_PATH')}")
    print(f"  sha-256      {fingerprint(cert)}")
    print()
    print(f"  ON THIS MACHINE   https://127.0.0.1:{args.port}/")
    print(f"  ON THE PHONE      https://{host}:{args.port}/")
    print()
    print("  This exposes the running application to every device on this")
    print("  network until you stop it. The certificate is self-signed, so the")
    print("  phone will warn - check the fingerprint above, then accept it.")
    print("  Accepting it also makes the origin SECURE, which is what makes")
    print("  the microphone available (see static/js/voice_input.js).")
    print()
    print("  Ctrl-C to stop.")

    # debug=False and use_debugger=False are not defaults to rely on here -
    # they are stated, because this socket is reachable from other machines and
    # Werkzeug's console on such a socket is remote code execution.
    application.run(
        host=args.host,
        port=args.port,
        ssl_context=context,
        debug=False,
        use_debugger=False,
        use_evalex=False,
        use_reloader=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
