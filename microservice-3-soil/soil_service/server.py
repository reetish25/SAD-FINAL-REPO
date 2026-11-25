"""HTTP server built on the standard library. Serves the JSON API and the web app from /static."""
import json
import logging
import mimetypes
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, unquote, urlsplit

from . import config
from .api import Request, dispatch
from .errors import ApiError

log = logging.getLogger("http")
MAX_BODY = 64 * 1024
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")


class Handler(BaseHTTPRequestHandler):
    server_version = f"{config.SERVICE_NAME}/{config.SERVICE_VERSION}"

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def log_message(self, fmt, *args):
        log.info("%s %s", self.address_string(), fmt % args)

    def _handle(self, method):
        request_id = uuid.uuid4().hex[:12]
        parts = urlsplit(self.path)
        path = unquote(parts.path)
        if not (path.startswith("/api/") or path == "/health"):
            if method == "GET":
                return self._static(path, request_id)
            return self._send(404, {"error": {"code": "NOT_FOUND", "message": "Not found."}}, request_id)

        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._send(413, {"error": {"code": "TOO_LARGE", "message": "Request is too large."}}, request_id)
        body = None
        if length:
            raw = self.rfile.read(length)
            try:
                body = json.loads(raw.decode("utf-8"))
            except ValueError:
                return self._send(400, {"error": {"code": "BAD_JSON", "message": "Body must be valid JSON."}},
                                  request_id)
        req = Request(method, path, dict(parse_qsl(parts.query)), body,
                      {k.lower(): v for k, v in self.headers.items()}, request_id)
        try:
            status, payload = dispatch(req)
        except ApiError as exc:
            status, payload = exc.status, {"error": {"code": exc.code, "message": exc.message}}
        except Exception:
            log.exception("unhandled error request=%s", request_id)
            status = 500
            payload = {"error": {"code": "INTERNAL", "message": "Something went wrong. Quote the request ID."}}
        if isinstance(payload, dict) and "error" in payload:
            payload["error"]["requestId"] = request_id
        self._send(status, payload, request_id)

    def _send(self, status, payload, request_id, content_type="application/json; charset=utf-8", raw=None):
        data = raw if raw is not None else json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Request-ID", request_id)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(data)

    def _static(self, path, request_id):
        rel = "index.html" if path in ("", "/") else path.lstrip("/")
        root = os.path.realpath(config.STATIC_DIR)
        full = os.path.realpath(os.path.join(root, rel))
        if not full.startswith(root + os.sep) or not os.path.isfile(full):
            return self._send(404, {"error": {"code": "NOT_FOUND", "message": "Not found."}}, request_id)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        with open(full, "rb") as fh:
            data = fh.read()
        return self._send(200, None, request_id, content_type=ctype, raw=data)


def make_server():
    ThreadingHTTPServer.daemon_threads = True
    return ThreadingHTTPServer((config.HOST, config.PORT), Handler)
