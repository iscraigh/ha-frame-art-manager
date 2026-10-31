#!/usr/bin/env python3
import os, sys, json, subprocess, re
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PY = os.path.join(DIR, ".venv", "bin", "python")
PYTHON_BIN = VENV_PY if os.path.exists(VENV_PY) else sys.executable
TOKEN_FILE = os.path.join(DIR, "tv-token.txt")

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        ip = qs.get("ip", [""])[0].strip()

        if parsed.path == "/show":
            cid = qs.get("id", [""])[0].strip()
            if not ip or not cid:
                self.send_response(400)
                self._cors()
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "Missing ip or id"}).encode())
                return

            try:
                from samsungtvws import SamsungTVWS
                if cid.startswith("F"):
                    cid = "MY_" + cid
                tv = SamsungTVWS(host=ip, port=8002, token_file=TOKEN_FILE)
                tv.art().select_image(cid, show=True)
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "id": cid}).encode())
            except Exception as e:
                self.send_response(500)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
            return

        if parsed.path == "/sync":
            if not ip:
                self.send_response(400)
                self._cors()
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No TV IP provided"}).encode())
                return

            proc = subprocess.run(
                [PYTHON_BIN, os.path.join(DIR, "sync_thumbs.py"), ip],
                cwd=DIR, capture_output=True, text=True
            )

            thumbs = {}
            cache_file = os.path.join(DIR, "thumbs_cache.js")
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    m = re.search(r"window\.FAM_PRELOADED_THUMBS\s*=\s*(\{.*?\});", f.read(), re.S)
                    if m:
                        try:
                            thumbs = json.loads(m.group(1))
                        except Exception:
                            pass

            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "ok": proc.returncode == 0,
                "count": len(thumbs),
                "thumbs": thumbs,
                "log": (proc.stdout + "\n" + proc.stderr).strip()
            }).encode())
            return

        self.send_response(404)
        self.end_headers()

if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8766), Handler).serve_forever()
