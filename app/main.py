from __future__ import annotations

import argparse
import json
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.storage import DuplicateAliasError, LinkStore


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_DATABASE = "data/links.db"
ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
RESERVED_PATHS = {"", "healthz", "urls", "stats"}


def create_app(database_path: str | Path) -> type[BaseHTTPRequestHandler]:
    store = LinkStore(database_path)

    class UrlShortenerHandler(BaseHTTPRequestHandler):
        server_version = "UrlShortenerDemo/1.0"

        def do_GET(self) -> None:
            path = self._path()

            if path == "":
                self._send_html(self._index_page())
                return

            if path == "healthz":
                self._send_json({"status": "ok"})
                return

            if path.startswith("stats/"):
                self._handle_stats(path.removeprefix("stats/"))
                return

            self._handle_redirect(path)

        def do_POST(self) -> None:
            path = self._path()

            if path != "urls":
                self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                return

            payload = self._read_json()
            if payload is None:
                self._send_json({"error": "Request body must be valid JSON"}, HTTPStatus.BAD_REQUEST)
                return

            long_url = payload.get("url")
            custom_alias = payload.get("customAlias")
            ttl_seconds = payload.get("ttlSeconds")

            errors = validate_create_payload(long_url, custom_alias, ttl_seconds)
            if errors:
                self._send_json({"error": "Validation failed", "details": errors}, HTTPStatus.BAD_REQUEST)
                return

            try:
                link = store.create(
                    long_url,
                    custom_alias=custom_alias,
                    ttl_seconds=ttl_seconds,
                )
            except DuplicateAliasError:
                self._send_json({"error": "Custom alias already exists"}, HTTPStatus.CONFLICT)
                return

            self._send_json(
                {
                    "code": link.code,
                    "shortUrl": f"{self._base_url()}/{link.code}",
                    "longUrl": link.long_url,
                    "expiresAt": link.expires_at,
                },
                HTTPStatus.CREATED,
            )

        def log_message(self, format: str, *args: Any) -> None:
            print(f"{self.address_string()} - {format % args}")

        def _handle_redirect(self, code: str) -> None:
            link = store.get(code)
            if link is None:
                self._send_json({"error": "Short URL not found"}, HTTPStatus.NOT_FOUND)
                return

            if link.expired:
                self._send_json({"error": "Short URL has expired"}, HTTPStatus.GONE)
                return

            store.increment_visits(code)
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", link.long_url)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

        def _handle_stats(self, code: str) -> None:
            link = store.get(code)
            if link is None:
                self._send_json({"error": "Short URL not found"}, HTTPStatus.NOT_FOUND)
                return

            self._send_json(
                {
                    "code": link.code,
                    "longUrl": link.long_url,
                    "createdAt": link.created_at,
                    "expiresAt": link.expires_at,
                    "visitCount": link.visit_count,
                    "expired": link.expired,
                }
            )

        def _path(self) -> str:
            return urlparse(self.path).path.strip("/")

        def _base_url(self) -> str:
            host = self.headers.get("Host", f"{DEFAULT_HOST}:{DEFAULT_PORT}")
            return f"http://{host}"

        def _read_json(self) -> dict[str, Any] | None:
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return None

            body = self.rfile.read(content_length)
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None

            return payload if isinstance(payload, dict) else None

        def _send_json(
            self,
            payload: dict[str, Any],
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _index_page(self) -> str:
            return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>URL Shortener Demo</title>
  <style>
    :root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; min-height: 100vh; background: #f7f7f4; color: #20201d; }
    main { width: min(920px, calc(100vw - 32px)); margin: 0 auto; padding: 42px 0; }
    header { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 28px; }
    h1 { font-size: clamp(28px, 4vw, 44px); line-height: 1.05; margin: 0; letter-spacing: 0; }
    .status { font-size: 14px; color: #676761; }
    section { background: #ffffff; border: 1px solid #deded8; border-radius: 8px; padding: 22px; box-shadow: 0 12px 30px rgba(38, 38, 32, 0.08); }
    form { display: grid; grid-template-columns: 1fr auto; gap: 12px; }
    input { height: 44px; border: 1px solid #bcbcb4; border-radius: 6px; padding: 0 12px; font-size: 15px; min-width: 0; }
    button { height: 44px; border: 0; border-radius: 6px; padding: 0 18px; background: #2457a6; color: #fff; font-weight: 700; cursor: pointer; }
    button:hover { background: #1c4789; }
    .options { grid-column: 1 / -1; display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    .result { margin-top: 18px; border-top: 1px solid #ecece7; padding-top: 18px; min-height: 28px; overflow-wrap: anywhere; }
    .result a { color: #2457a6; font-weight: 700; }
    .error { color: #a33425; }
    .api { margin-top: 22px; color: #5c5c55; font-size: 14px; line-height: 1.55; }
    code { background: #eeeeea; border-radius: 4px; padding: 2px 5px; color: #242420; }
    @media (max-width: 680px) {
      header { align-items: flex-start; flex-direction: column; }
      form, .options { grid-template-columns: 1fr; }
      button { width: 100%; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>URL Shortener Demo</h1>
      <span class="status">SQLite-backed local service</span>
    </header>
    <section>
      <form id="shorten-form">
        <input id="url" name="url" type="url" placeholder="https://example.com/a/very/long/url" required>
        <button type="submit">Shorten</button>
        <div class="options">
          <input id="customAlias" name="customAlias" placeholder="custom alias, optional">
          <input id="ttlSeconds" name="ttlSeconds" type="number" min="1" placeholder="TTL seconds, optional">
        </div>
      </form>
      <div id="result" class="result"></div>
      <p class="api">API: <code>POST /urls</code>, <code>GET /{code}</code>, <code>GET /stats/{code}</code>, <code>GET /healthz</code></p>
    </section>
  </main>
  <script>
    const form = document.querySelector("#shorten-form");
    const result = document.querySelector("#result");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      result.textContent = "Creating short URL...";
      const payload = { url: form.url.value.trim() };
      if (form.customAlias.value.trim()) payload.customAlias = form.customAlias.value.trim();
      if (form.ttlSeconds.value) payload.ttlSeconds = Number(form.ttlSeconds.value);
      const response = await fetch("/urls", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      if (!response.ok) {
        result.innerHTML = `<span class="error">${data.error}</span>`;
        return;
      }
      result.innerHTML = `Short URL: <a href="${data.shortUrl}" target="_blank" rel="noopener">${data.shortUrl}</a>`;
    });
  </script>
</body>
</html>
"""

    return UrlShortenerHandler


def validate_create_payload(
    long_url: Any,
    custom_alias: Any,
    ttl_seconds: Any,
) -> list[str]:
    errors: list[str] = []

    if not isinstance(long_url, str) or not long_url.strip():
        errors.append("url is required")
    else:
        parsed = urlparse(long_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append("url must be an absolute http or https URL")

    if custom_alias is not None:
        if not isinstance(custom_alias, str) or not ALIAS_PATTERN.fullmatch(custom_alias):
            errors.append("customAlias must be 3-32 chars: letters, numbers, underscore, or hyphen")
        elif custom_alias in RESERVED_PATHS:
            errors.append("customAlias uses a reserved path")

    if ttl_seconds is not None:
        if not isinstance(ttl_seconds, int) or ttl_seconds <= 0:
            errors.append("ttlSeconds must be a positive integer")

    return errors


def run_server(host: str, port: int, database_path: str | Path) -> None:
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
    handler = create_app(database_path)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"URL shortener listening on http://{host}:{port}")
    print(f"SQLite database: {database_path}")
    server.serve_forever()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the URL shortener demo server")
    parser.add_argument("--host", default=os.getenv("HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", str(DEFAULT_PORT))))
    parser.add_argument("--database", default=os.getenv("DATABASE_URL", DEFAULT_DATABASE))
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_server(args.host, args.port, args.database)
