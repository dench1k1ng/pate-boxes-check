# -*- coding: utf-8 -*-
"""Standalone local web server for the Tortikipirogi parser."""
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from parse_tortikipirogi import process
from parse_mamin_hleb import process as process_mamin_hleb
from server import upload_cards


ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
HOST = "127.0.0.1"
PORT = 8001
CRM_OVERRIDES = {
    "category_name": "Кондитерские изделия",
    "store_aliases": {
        "tortikipirogi": "Tortikipirogi",
        "kulinar&ca": "KULINAR&CA",
    },
}
MAMIN_HLEB_OVERRIDES = {
    "category_name": "Пекарня",
    "store_aliases": {
        "аспан базар": "Мамин хлеб | Аспан базар",
        "мамин хлеб аспан базар": "Мамин хлеб | Аспан базар",
        "абая 8": "Мамин хлеб | Абая 8",
        "мамин хлеб абая 8": "Мамин хлеб | Абая 8",
        "ауэзова 42": "Мамин хлеб | Ауэзова, 42",
        "ауэзова, 42": "Мамин хлеб | Ауэзова, 42",
        "сыганак 3": "Royalty Coffee | Сыганак 3",
        "royalty coffee сыганак 3": "Royalty Coffee | Сыганак 3",
    },
}


class Handler(BaseHTTPRequestHandler):
    server_version = "TortikipirogiParser/1.0"

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path == "/":
            path = "/tortikipirogi.html"
        if path in {"/mamin-hleb", "/mamin-hleb/"}:
            path = "/mamin_hleb.html"
        if path == "/api/tortikipirogi/images":
            return self.send_json({"images": []})
        if path == "/api/mamin-hleb/images":
            return self.send_json({"images": []})
        if path.startswith("/images/") or path.startswith("/images_from_pdf/"):
            return self.serve_file(ROOT / path.lstrip("/"))
        return self.serve_file(WEB_DIR / path.lstrip("/"))

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/tortikipirogi/parse":
            return self.handle_parse()
        if parsed.path == "/api/mamin-hleb/parse":
            return self.handle_parse(process_mamin_hleb)
        if parsed.path == "/api/tortikipirogi/upload":
            return self.handle_upload()
        if parsed.path == "/api/mamin-hleb/upload":
            return self.handle_upload(MAMIN_HLEB_OVERRIDES)
        self.send_json({"error": "not found"}, status=404)

    def handle_parse(self, parser=process):
        try:
            payload = self.read_json()
            text = payload.get("text", "")
            if not text.strip():
                return self.send_json({"error": "empty text"}, status=400)
            items = parser(text, store_name=payload.get("storeName"))
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
            return self.send_json({"error": str(exc)}, status=500)

    def handle_upload(self, config_overrides=CRM_OVERRIDES):
        try:
            payload = self.read_json()
            items = payload.get("items", [])
            if not items:
                return self.send_json({"error": "empty items"}, status=400)
            store_name = str(payload.get("storeName") or "").strip()
            if store_name:
                items = [{**item, "storeName": store_name, "storeId": None} for item in items]
            report = upload_cards(
                items,
                dry_run=bool(payload.get("dryRun", False)),
                force=bool(payload.get("force", False)),
                config_overrides=config_overrides,
            )
            return self.send_json(report)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, status=500)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

    def serve_file(self, path):
        try:
            resolved = path.resolve()
            allowed_roots = [WEB_DIR.resolve(), (ROOT / "images").resolve(), (ROOT / "images_from_pdf").resolve()]
            if not any(str(resolved).startswith(str(root)) for root in allowed_roots):
                return self.send_error(403)
            if not resolved.is_file():
                return self.send_error(404)
            data = resolved.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(str(resolved))[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except OSError:
            self.send_error(404)

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Tortikipirogi parser: http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
