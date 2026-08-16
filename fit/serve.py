#!/usr/bin/env python3
"""
Development server for the template-fitting UI.

Serves the repository root (so the UI can load the template image) and
accepts POST /save with the letters.json content, which is written to
fit/letters.json. Run from anywhere:

    python3 fit/serve.py [port]

then open http://localhost:8477/fit/
"""

import http.server
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LETTERS = os.path.join(HERE, "letters.json")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8477


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_POST(self):
        if self.path != "/save":
            self.send_error(404)
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(n)
            json.loads(body)  # must be valid JSON
            tmp = LETTERS + ".tmp"
            with open(tmp, "wb") as f:
                f.write(body)
            os.replace(tmp, LETTERS)
            out = b'{"ok": true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
        except Exception as e:
            self.send_error(500, str(e))

    def log_message(self, fmt, *args):
        # The base class also calls this for errors (log_error), where args[0]
        # is the status code, not a request line; only check strings.
        if args and isinstance(args[0], str) and "POST /save" in args[0]:
            print("saved fit/letters.json")


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Serving on http://localhost:{PORT}/fit/")
    server.serve_forever()
