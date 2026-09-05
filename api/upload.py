from http.server import BaseHTTPRequestHandler
import json

from server import upload_cards


class handler(BaseHTTPRequestHandler):
    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        try:
            payload = self.read_json()
            items = payload.get("items", [])
            dry_run = bool(payload.get("dryRun", False))
            force = bool(payload.get("force", False))
            if not items:
                return self.send_json({"error": "empty items"}, status=400)

            report = upload_cards(items, dry_run=dry_run, force=force)
            return self.send_json(report)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, status=500)
