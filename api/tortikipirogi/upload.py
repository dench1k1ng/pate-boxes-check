from http.server import BaseHTTPRequestHandler
import json

from server import upload_cards


CRM_OVERRIDES = {
    "category_name": "Кондитерские изделия",
    "store_aliases": {"tortikipirogi": "Tortikipirogi"},
}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            items = payload.get("items", [])
            if not items:
                return self.send_json({"error": "empty items"}, 400)
            result = upload_cards(
                items,
                dry_run=bool(payload.get("dryRun", False)),
                force=bool(payload.get("force", False)),
                config_overrides=CRM_OVERRIDES,
            )
            return self.send_json(result)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 500)

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
