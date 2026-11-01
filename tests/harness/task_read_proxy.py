"""Isolated browser fault harness, not an application integration or live feed.

Only a provenance-marked local software-review snapshot may be used. The first
successful authenticated saved-task read becomes a503; later reads preserve real
upstream bytes. No operational record is invented. Only the existing login POST
is forwarded. Events contain route categories/statuses, never bodies or identity.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlsplit

LIMIT, LOGIN_LIMIT, TIMEOUT = 16 * 1024 * 1024, 16 * 1024, 20
HOP = {"connection", "host", "content-length", "transfer-encoding", "proxy-authorization", "proxy-connection", "te", "trailer", "upgrade", "expect"}


def validate_snapshot(value: str, events: str) -> Path:
    snapshot = Path(value).resolve(strict=True)
    target, runtime = snapshot.parent, snapshot.parent.parent
    if snapshot.name != "SNAPSHOT.json" or runtime.name != "runtime" or target.name != "candidate033-review":
        raise ValueError("An isolated candidate033-review/SNAPSHOT.json is required")
    with snapshot.open("rb") as stream:
        raw = stream.read(16385)
    if len(raw) > 16384:
        raise ValueError("Snapshot provenance exceeds its bound")
    data = json.loads(raw)
    source = (runtime / "review-v3").resolve(strict=True)
    if (not isinstance(data, dict) or data.get("kind") != "software_review_snapshot"
            or type(data.get("api_port")) is not int or data["api_port"] != 8788
            or data.get("source_runtime") != source.as_posix()
            or data.get("target_runtime") != target.as_posix()
            or not source.is_dir() or not target.is_dir() or source == target):
        raise ValueError("Snapshot source, target, kind or fixed API port differs")
    event_path = Path(events).resolve()
    if event_path.parent != target or event_path.suffix not in {".ndjson", ".jsonl"} or Path(events).is_symlink():
        raise ValueError("Explicit private event output must be inside the isolated target")
    return event_path


def route_category(path: str) -> str:
    if path in {"/api/v1/session", "/api/v1/health", "/api/v1/companion/tasks"}:
        return path
    return "/api/v1/*" if path.startswith("/api/v1/") else "/static/*"


def handler(events: Path):
    lock, injected_once = threading.Lock(), False

    class Proxy(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, body, headers=()):
            self.send_response(status)
            for name, value in headers:
                if name.lower() not in HOP:
                    self.send_header(name, value)
            head_length = next((value for name, value in headers if name.lower() == "content-length"), None)
            self.send_header("Content-Length", head_length if self.command == "HEAD" and head_length is not None else str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def forward(self):
            nonlocal injected_once
            path, upstream_status, injected = urlsplit(self.path).path, None, False
            status, body, headers = 502, b'{"detail":"Isolated upstream unavailable."}', [("Content-Type", "application/json")]
            allowed = self.command in {"GET", "HEAD"} or (self.command == "POST" and self.path == "/api/v1/session")
            try:
                if not allowed:
                    status, body = 403, b'{"detail":"Mutations are blocked by the isolated read harness."}'
                elif not self.path.startswith("/") or self.path.startswith("//") or self.headers.get("Transfer-Encoding"):
                    status, body = 400, b'{"detail":"Unsupported isolated request framing."}'
                else:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length < 0 or length > (LOGIN_LIMIT if self.command == "POST" else 0):
                        status, body = 413, b'{"detail":"Isolated request body exceeds its bound."}'
                    else:
                        payload = self.rfile.read(length) if length else None
                        deadline = time.monotonic() + TIMEOUT
                        with closing(http.client.HTTPConnection("127.0.0.1", 8788, timeout=TIMEOUT)) as connection:
                            connection.request(self.command, self.path, body=payload, headers={k: v for k, v in self.headers.items() if k.lower() not in HOP})
                            sock = connection.sock
                            response = connection.getresponse()
                            upstream_status, headers, chunks, total = response.status, response.getheaders(), [], 0
                            while self.command != "HEAD":
                                remaining = deadline - time.monotonic()
                                if remaining <= 0:
                                    raise TimeoutError()
                                sock.settimeout(remaining)
                                chunk = response.read1(min(65536, LIMIT + 1 - total))
                                if not chunk:
                                    break
                                chunks.append(chunk); total += len(chunk)
                                if total > LIMIT:
                                    raise ValueError("Response bound exceeded")
                            body, status = b"".join(chunks), response.status
                        if self.command == "GET" and path == "/api/v1/companion/tasks" and upstream_status == 200 and self.headers.get("Authorization"):
                            with lock:
                                if not injected_once:
                                    injected_once, injected = True, True
                            if injected:
                                status, body, headers = 503, b'{"detail":"Isolated test: saved-task read temporarily unavailable."}', [("Content-Type", "application/json")]
            except (OSError, ValueError, http.client.HTTPException):
                status, body, headers = 502, b'{"detail":"Isolated upstream unavailable."}', [("Content-Type", "application/json")]
            with lock:
                with events.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"route": route_category(path), "method": self.command, "upstreamStatus": upstream_status, "status": status, "injected": injected}) + "\n")
            self.respond(status, body, headers)

        do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = forward

    return Proxy


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--events", required=True)
    args = parser.parse_args(argv)
    events = validate_snapshot(args.snapshot, args.events)
    with ThreadingHTTPServer(("127.0.0.1", 8789), handler(events)) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
