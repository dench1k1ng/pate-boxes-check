from http.server import BaseHTTPRequestHandler
import json

from server import upload_cards


CRM_OVERRIDES = {
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


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            items = payload.get("items", [])
            if not items:
                return self.send_json({"error": "empty items"}, 400)
            store_name = str(payload.get("storeName") or "").strip()
            if store_name:
                items = [{**item, "storeName": store_name, "storeId": None} for item in items]
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
