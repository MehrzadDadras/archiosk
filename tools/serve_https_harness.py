"""Serve a static harness directory over HTTPS, so a phone can use the mic.

WHY THIS EXISTS
===============

Browsers gate `SpeechRecognition`, `getUserMedia` and `navigator.mediaDevices`
behind a SECURE CONTEXT. `localhost` counts as one; a plain-http LAN address
does not. Measured on the exact origin a phone was using here:

    http://10.0.0.177:8642   isSecureContext false   mediaDevices undefined
    http://127.0.0.1:8642    isSecureContext true    getUserMedia present

Which is why voice worked on the machine doing the developing and was dead on
the device - and why static/js/voice_input.js now hides the mic outright on an
insecure origin instead of offering a button that cannot work
(CLAUDE-VOICE-SECURE-CONTEXT-01). Hiding it is honest, but it also means voice
CANNOT be tested on a real device over the LAN without TLS. This tool supplies
the TLS.

WHY NOT `python app.py --ssl`
=============================

app.py's `__main__` block binds 127.0.0.1 unconditionally, and its own comment
records that as deliberate rather than incidental - the same block that turned
Werkzeug's interactive debugger off by default after a real incident. Adding an
"also listen on every interface" mode to the application's dev entrypoint would
loosen exactly that constraint, for a need that is not about the application at
all: the device testing in this project has always driven the STATIC harness,
not a live Flask server. So the LAN exposure lives here, in a tool that serves
pre-rendered files and can neither authenticate anybody nor reach the database.

WHAT IT DOES
============

  1. Finds the LAN address this machine is actually reachable at.
  2. Generates a self-signed certificate naming that IP (plus 127.0.0.1 and
     localhost) in subjectAltName - modern browsers ignore CommonName, so an
     IP certificate without a matching SAN is refused outright.
  3. Serves `root` over TLS on 0.0.0.0:<port>.

The certificate is written OUTSIDE the repository by default, and is
regenerated when it expires. It is a throwaway for one machine on one LAN:
private key material must never land in a git-tracked location, which is why
--cert-dir defaults to the system temp directory rather than anywhere here.

Expect a browser warning on first visit - a self-signed certificate is
untrusted by construction, and the whole point is that YOU are the authority
attesting to it. Accepting it makes the origin secure, which is what unlocks
the microphone. The fingerprint is printed at startup so the certificate being
accepted can be checked against the one this tool actually generated.

USAGE
=====

    ./venv/Scripts/python.exe tools/serve_https_harness.py <root>
    ./venv/Scripts/python.exe tools/serve_https_harness.py <root> --port 8643

Ctrl-C stops it. Nothing is written to the served directory.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import http.server
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_PORT = 8643
CERT_LIFETIME_DAYS = 365

# Git for Windows ships OpenSSL but does not put it on the Windows PATH, so a
# bare shutil.which() finds nothing from a plain `python.exe` even though
# `openssl version` works fine in the same terminal's Git Bash.
OPENSSL_FALLBACKS = (
    r"C:\Program Files\Git\mingw64\bin\openssl.exe",
    r"C:\Program Files\Git\usr\bin\openssl.exe",
    "/usr/bin/openssl",
)


def find_openssl() -> str:
    found = shutil.which("openssl")
    if found:
        return found
    for candidate in OPENSSL_FALLBACKS:
        if os.path.isfile(candidate):
            return candidate
    raise SystemExit(
        "openssl was not found. It ships with Git for Windows; install Git or "
        "put openssl on PATH, then run this again."
    )


def lan_address() -> str:
    """The address this machine is reachable at from the phone.

    A UDP socket is opened but nothing is sent - connect() on a datagram
    socket only fixes the local endpoint, which is precisely the question
    being asked ("which of my interfaces would route to the outside world").
    gethostbyname(gethostname()) is not used: it answers 127.0.0.1 on a
    surprising number of machines.
    """
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def certificate_for(host: str, cert_dir: Path) -> tuple[Path, Path]:
    """A self-signed cert naming `host` in subjectAltName, generated once."""
    cert_dir.mkdir(parents=True, exist_ok=True)
    safe = host.replace(":", "-").replace(".", "-")
    cert = cert_dir / f"archiosk-harness-{safe}.pem"
    key = cert_dir / f"archiosk-harness-{safe}.key"

    if cert.is_file() and key.is_file():
        still_valid = subprocess.run(
            [find_openssl(), "x509", "-checkend", "86400", "-noout", "-in", str(cert)],
            capture_output=True,
        )
        if still_valid.returncode == 0:
            return cert, key
        print(f"  certificate expired or expiring; regenerating")

    # subjectAltName is not optional. Browsers stopped honouring CommonName
    # years ago, so a certificate for an IP address with no IP: SAN is
    # rejected before the interstitial is even offered.
    san = f"subjectAltName=IP:{host},IP:127.0.0.1,DNS:localhost"
    subprocess.run(
        [
            find_openssl(), "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key), "-out", str(cert),
            "-days", str(CERT_LIFETIME_DAYS),
            "-subj", "/CN=ARCHIOSK local harness",
            "-addext", san,
            "-addext", "basicConstraints=critical,CA:FALSE",
            "-addext", "keyUsage=critical,digitalSignature,keyEncipherment",
            "-addext", "extendedKeyUsage=serverAuth",
        ],
        check=True,
        capture_output=True,
    )
    try:
        os.chmod(key, 0o600)
    except OSError:
        pass  # Windows ACLs; the file is in a per-user temp directory anyway
    return cert, key


def fingerprint(cert: Path) -> str:
    """SHA-256 of the DER body, which is what a browser shows.

    Printed so the warning being accepted on the phone can be checked against
    the certificate this tool actually made, rather than accepted blind.
    """
    pem = cert.read_text(encoding="utf-8")
    body = pem.split("-----BEGIN CERTIFICATE-----")[1]
    body = body.split("-----END CERTIFICATE-----")[0]
    import base64

    digest = hashlib.sha256(base64.b64decode(body)).hexdigest().upper()
    return " ".join(digest[i:i + 2] for i in range(0, len(digest), 2))


# Vector sheets are large and enormously compressible - measured across the
# eleven rendered 5 Nipigon sheets, 77.79 MB of SVG becomes 5.50 MB gzipped, a
# 14.2x reduction (A902 alone: 20.22 MB -> 1.16 MB, 17.5x). Uncompressed, a
# single sheet is a minute of Wi-Fi; compressed it is a couple of seconds.
#
# `http.server` does not compress anything, so this handler does. It is not an
# optimisation of the harness for its own sake: it is what makes the vector
# decision (see DPL-0005) testable on a real device at all.
COMPRESSIBLE = (".svg", ".css", ".js", ".html", ".json", ".txt", ".map")
COMPRESS_MIN_BYTES = 1024


class ExclusiveHTTPServer(http.server.ThreadingHTTPServer):
    """Refuse the port if something already has it.

    `http.server` sets `allow_reuse_address = 1`, and on Windows SO_REUSEADDR
    behaves like SO_REUSEPORT: a SECOND server binds the SAME port without
    error and the two then split connections unpredictably. That is not
    theoretical - it happened here. Two orphaned instances left over from an
    earlier start were still holding 8643, serving a directory that had since
    been emptied, and every request to the "new" server returned an empty
    directory listing or a 404. The freshly rendered harness was on disk and
    correct the whole time.

    It is the same failure the restart-app skill exists for: a stale process
    quietly serving stale state through a port that looks like it belongs to
    the thing just started. Refusing the bind turns a confusing wrong answer
    into an error message naming the cause.
    """
    allow_reuse_address = False


class Handler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        """Serve a compressible file gzipped when the client will take it.

        Compression happens in memory rather than beside the file: the served
        directory is a build output that is regenerated constantly, and a
        stale .gz sitting next to a fresh .svg would serve yesterday's drawing
        with today's timestamp.
        """
        accepts = self.headers.get("Accept-Encoding", "")
        if "gzip" not in accepts.lower():
            return super().send_head()

        path = self.translate_path(self.path)
        if os.path.isdir(path) or not path.lower().endswith(COMPRESSIBLE):
            return super().send_head()
        try:
            raw = open(path, "rb").read()
        except OSError:
            return super().send_head()
        if len(raw) < COMPRESS_MIN_BYTES:
            return super().send_head()

        import gzip as _gzip
        import io as _io

        body = _gzip.compress(raw, 6)
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        # Vary matters even here: a proxy on the LAN that cached the gzipped
        # body and replayed it to a client that did not ask for gzip would
        # hand it bytes it cannot read.
        self.send_header("Vary", "Accept-Encoding")
        self.end_headers()
        return _io.BytesIO(body)

    def end_headers(self):
        # A harness is rebuilt constantly and read from a phone that caches
        # aggressively. Stale CSS on a device, while the same file looked
        # correct on the machine that changed it, has already cost real time
        # here more than once.
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s\n" % (fmt % args))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", help="directory to serve")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--cert-dir",
        default=str(Path(tempfile.gettempdir()) / "archiosk-harness-tls"),
        help="where the throwaway key/cert live. Never inside the repository.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        raise SystemExit(f"not a directory: {root}")

    cert_dir = Path(args.cert_dir).resolve()
    repo = Path(__file__).resolve().parents[1]
    if repo == cert_dir or repo in cert_dir.parents:
        raise SystemExit(
            f"refusing to write a private key inside the repository: {cert_dir}"
        )

    host = lan_address()
    print(f"ARCHIOSK HTTPS harness")
    print(f"  root         {root}")
    print(f"  certificates {cert_dir}")
    cert, key = certificate_for(host, cert_dir)
    print(f"  sha-256      {fingerprint(cert)}")

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert), keyfile=str(key))

    handler = functools.partial(Handler, directory=str(root))
    try:
        server = ExclusiveHTTPServer(("0.0.0.0", args.port), handler)
    except OSError as exc:
        raise SystemExit(
            f"port {args.port} is already in use ({exc}). Another harness is "
            f"probably still running - stop it, or pass --port."
        )
    server.socket = context.wrap_socket(server.socket, server_side=True)

    print()
    print(f"  ON THIS MACHINE   https://127.0.0.1:{args.port}/")
    print(f"  ON THE PHONE      https://{host}:{args.port}/")
    print()
    print("  The phone will warn that the certificate is untrusted - it is")
    print("  self-signed, so that warning is correct. Check the fingerprint")
    print("  above, accept it, and the origin becomes secure: that is what")
    print("  makes the microphone available at all.")
    print()
    print("  Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
