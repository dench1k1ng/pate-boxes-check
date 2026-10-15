"""Smoke check the protected local endpoint without printing credentials."""

import base64
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE = "http://127.0.0.1:18001"
PASSWORD = Path.home() / "pate-runtime/secrets/operator-password.txt"


def request(path, *, method="GET", payload=None, authenticated=False):
    headers = {}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if authenticated:
        password = PASSWORD.read_text(encoding="utf-8").strip()
        token = base64.b64encode(f"operator:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    data = None if payload is None else json.dumps(payload).encode()
    req = Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=15) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


def main():
    checks = [
        ("site without password", request("/")[0], 401),
        ("publish without password", request("/api/upload", method="POST", payload={"items": [{}]})[0], 401),
        ("site with password", request("/", authenticated=True)[0], 200),
        ("Tortikipirogi with password", request("/tortikipirogi", authenticated=True)[0], 200),
        ("Mamin Hleb with password", request("/mamin-hleb", authenticated=True)[0], 200),
        (
            "parse with password",
            request("/api/tortikipirogi/parse", method="POST", payload={"text": "Трайфл медовый-760"}, authenticated=True)[0],
            200,
        ),
    ]
    for label, actual, expected in checks:
        print(f"{label}: {actual} (expected {expected})")
    if any(actual != expected for _, actual, expected in checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
