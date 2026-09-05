from http.server import BaseHTTPRequestHandler
import json

from parse_daily import process
from server import CATALOG


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
            raw_text = payload.get("text", "")
            if not raw_text.strip():
                return self.send_json({"error": "empty text"}, status=400)

            items = process(raw_text, CATALOG)
            ok_count = sum(1 for item in items if not item.get("needsReview"))
            review_count = sum(1 for item in items if item.get("needsReview"))
            store_count = len({item.get("storeName") for item in items if item.get("storeName")})

            return self.send_json(
                {
                    "items": items,
                    "summary": {
                        "total": len(items),
                        "ok": ok_count,
                        "review": review_count,
                        "stores": store_count,
                    },
                }
            )
        except Exception as exc:
            return self.send_json({"error": str(exc)}, status=500)
