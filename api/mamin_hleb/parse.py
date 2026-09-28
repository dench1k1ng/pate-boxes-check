from http.server import BaseHTTPRequestHandler
import json

from parse_mamin_hleb import process


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            text = payload.get("text", "")
            if not text.strip():
                return self.send_json({"error": "empty text"}, 400)
            items = process(text, store_name=payload.get("storeName"))
            return self.send_json({
                "items": items,
                "summary": {
                    "total": len(items),
                    "ok": sum(1 for item in items if not item.get("needsReview")),
                    "review": sum(1 for item in items if item.get("needsReview")),
                    "stores": len({item.get("storeName") for item in items if item.get("storeName")}),
                },
            })
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 500)

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
