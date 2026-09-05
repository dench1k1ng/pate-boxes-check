from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class handler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            image_dirs = [ROOT / "images", ROOT / "images_from_pdf"]
            files = []
            for image_dir in image_dirs:
                if image_dir.exists():
                    rel = image_dir.name
                    files.extend(
                        f"{rel}/{entry.name}"
                        for entry in image_dir.iterdir()
                        if entry.is_file() and not entry.name.startswith(".")
                    )

            return self.send_json({"images": sorted(files)})
        except Exception as exc:
            return self.send_json({"error": str(exc)}, status=500)
