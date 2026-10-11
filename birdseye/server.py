"""Tiny dashboard server (stdlib http.server). Reads post files on every request.

GET  /              dashboard HTML
GET  /api/posts     all posts + waiting-on-you list
POST /api/approve   {"id"}                    acts as human (dashboard session = human)
POST /api/reject    {"id","comment","return_to"?}
Prototype: no auth. Real build must bind localhost and check the human key.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from . import core, status

HTML = Path(__file__).resolve().parent.parent / "dashboard" / "index.html"


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ("/", "/index.html"):
            return self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
        if path == "/api/posts":
            posts = core.all_posts()
            return self._send(200, {"stages": core.STAGES, "posts": posts,
                                    "waiting": core.waiting_on_human(posts)})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        try:
            if self.path == "/api/approve":
                post = core.approve(body["id"], core.HUMAN, body.get("comment"))
            elif self.path == "/api/reject":
                post = core.reject(body["id"], core.HUMAN, body.get("comment"), body.get("return_to"))
            else:
                return self._send(404, {"error": "not found"})
            status.write()
            self._send(200, post)
        except core.BirdsEyeError as e:
            self._send(400, {"error": e.code, "message": e.message})


def serve(port=8787):
    core.ensure_human_key()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Birds Eye dashboard on http://localhost:{port}  (root: {core.root()})")
    httpd.serve_forever()
