"""Serve only prepared dossier assets on loopback; no operational service or publishing."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parents[1]
FILES = {
    "/projects/airspace-operations": HERE / "site-project.html",
    "/projects/airspace-operations.html": HERE / "site-project.html",
    "/assets/airspace-project.css": HERE / "site-project.css",
    "/assets/lab.css": WORKSPACE / "public/assets/lab.css",
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = unquote(urlsplit(self.path).path)
        if route == "/":
            self.send_response(302)
            self.send_header("Location", "/projects/airspace-operations")
            self.end_headers()
            return
        target = FILES.get(route)
        prefix = "/airspace-operations/media/"
        if route.startswith(prefix):
            candidate = (HERE / "media" / route[len(prefix):]).resolve()
            if candidate.is_relative_to((HERE / "media").resolve()):
                target = candidate
        if target is None or not target.is_file():
            self.send_error(404, "Local authoring preview contains only the dossier and its assets")
            return
        content = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)


if __name__ == "__main__":
    print("Prepared dossier only: http://127.0.0.1:8793/projects/airspace-operations", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8793), Handler).serve_forever()
