#!/usr/bin/env python3
"""Serve the offline game explorer on loopback; no model calls or file writes."""

from __future__ import annotations

import argparse
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit

from utility_threshold.game_explorer import analyze, catalog

STATIC_ROOT = Path(__file__).resolve().parent / "web" / "game-explorer"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/ocean.svg": ("ocean.svg", "image/svg+xml"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
}
MAX_BODY_BYTES = 16_384


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON fields are not allowed")
        obj[key] = value
    return obj


def _decimal(token: str) -> Decimal:
    if len(token) > 128:
        raise ValueError("JSON number has too many digits")
    value = Decimal(token)
    if not value.is_finite() or abs(value.as_tuple().exponent) > 400:
        raise ValueError("JSON number is outside supported precision")
    return value


def _reject_constant(_token):
    raise ValueError("non-finite JSON values are not allowed")


def strict_json(body: bytes):
    """Reject duplicates, non-finite values, and unbounded numeric exponents."""
    return json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object,
                      parse_float=_decimal, parse_int=_decimal,
                      parse_constant=_reject_constant)


class ExplorerHandler(BaseHTTPRequestHandler):
    server_version = "GameExplorer/1"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def _send(self, status: int, payload: bytes, content_type: str, *, head=False):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        if not head:
            self.wfile.write(payload)

    def _json(self, status: int, obj, *, head=False):
        self._send(status, json.dumps(obj, allow_nan=False, separators=(",", ":")).encode(),
                   "application/json; charset=utf-8", head=head)

    def _error(self, status: int, message: str):
        self.close_connection = True
        self._json(status, {"error": message}, head=self.command == "HEAD")

    def _local_request(self) -> str | None:
        # A fixed Host/Origin policy prevents a website from treating this
        # read-only loopback service as one of its same-origin endpoints.
        port = self.server.server_address[1]
        allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if port == 80:
            allowed_hosts.update({"127.0.0.1", "localhost"})
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1 or hosts[0].lower() not in allowed_hosts:
            self._error(403, "local Host header required")
            return None
        origins = self.headers.get_all("Origin", [])
        if origins and (len(origins) != 1 or origins[0].lower() != "http://" + hosts[0].lower()):
            self._error(403, "same-origin requests required")
            return None
        try:
            target = urlsplit(self.path)
        except ValueError:
            self._error(400, "invalid request target")
            return None
        if target.scheme or target.netloc or target.fragment:
            self._error(400, "invalid request target")
            return None
        return target.path

    def do_GET(self, *, head=False):
        path = self._local_request()
        if path is None:
            return
        if path == "/api/catalog":
            self._json(200, catalog(), head=head)
            return
        asset = STATIC_FILES.get(path)
        if asset is None:
            self._error(404, "not found")
            return
        root = self.server.static_root
        candidate = (root / asset[0]).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            self._error(404, "not found")
            return
        try:
            payload = candidate.read_bytes()
        except OSError:
            self._error(404, "not found")
            return
        self._send(200, payload, asset[1], head=head)

    def do_HEAD(self):
        self.do_GET(head=True)

    def do_POST(self):
        path = self._local_request()
        if path is None:
            return
        if path != "/api/analyze":
            self._error(404, "not found")
            return
        if self.headers.get_all("Transfer-Encoding", []):
            self._error(400, "transfer encoding is not supported")
            return
        types = self.headers.get_all("Content-Type", [])
        if len(types) != 1 or types[0].split(";", 1)[0].strip().lower() != "application/json":
            self._error(415, "application/json is required")
            return
        lengths = self.headers.get_all("Content-Length", [])
        if not lengths:
            self._error(411, "Content-Length is required")
            return
        if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
            self._error(400, "invalid Content-Length")
            return
        # Bound before int conversion as well as before reading the body.
        if len(lengths[0]) > 6 or int(lengths[0]) > MAX_BODY_BYTES:
            self._error(413, "JSON request is too large")
            return
        length = int(lengths[0])
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("incomplete JSON body")
            result = analyze(strict_json(body))
        except (ValueError, UnicodeError, RecursionError):
            self._error(400, "invalid analysis request; check the six fields, allowed axis range, and finite JSON numbers")
            return
        except TimeoutError:
            self._error(408, "request timed out")
            return
        self._json(200, result)


class ExplorerServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, static_root=STATIC_ROOT):
        if address[0] not in {"127.0.0.1", "localhost"}:
            raise ValueError("the explorer must bind to 127.0.0.1 or localhost")
        self.static_root = Path(static_root).resolve()
        super().__init__(address, ExplorerHandler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("127.0.0.1", "localhost"), default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    with ExplorerServer((args.host, args.port)) as server:
        print(f"Game explorer: http://{args.host}:{server.server_address[1]}", flush=True)
        print("Local calculations only. Press Ctrl+C to stop.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
