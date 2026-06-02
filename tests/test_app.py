from __future__ import annotations

import http.client
import json
import tempfile
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from app.main import create_app, validate_create_payload
from app.storage import LinkStore


class ApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "links.db"
        handler = create_app(database_path)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_host = "127.0.0.1"
        self.port = self.server.server_address[1]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()

    def request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict[str, str], bytes]:
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        conn = http.client.HTTPConnection(self.base_host, self.port, timeout=5)
        conn.request(method, path, body=payload, headers=headers)
        response = conn.getresponse()
        raw_body = response.read()
        status = response.status
        response_headers = {key: value for key, value in response.getheaders()}
        conn.close()
        return status, response_headers, raw_body

    def test_create_redirect_and_stats(self) -> None:
        status, _, raw_body = self.request("POST", "/urls", {"url": "https://example.com/docs"})

        self.assertEqual(status, 201)
        body = json.loads(raw_body)
        self.assertIn("shortUrl", body)
        self.assertEqual(len(body["code"]), 8)

        status, headers, raw_body = self.request("GET", f"/{body['code']}")
        self.assertEqual(status, 302)
        self.assertEqual(headers["Location"], "https://example.com/docs")
        self.assertEqual(raw_body, b"")

        status, _, raw_body = self.request("GET", f"/stats/{body['code']}")
        self.assertEqual(status, 200)
        stats = json.loads(raw_body)
        self.assertEqual(stats["visitCount"], 1)
        self.assertFalse(stats["expired"])

    def test_custom_alias_duplicate_returns_conflict(self) -> None:
        payload = {"url": "https://example.com", "customAlias": "docs"}
        first_status, _, _ = self.request("POST", "/urls", payload)
        second_status, _, raw_body = self.request("POST", "/urls", payload)

        self.assertEqual(first_status, 201)
        self.assertEqual(second_status, 409)
        self.assertEqual(json.loads(raw_body)["error"], "Custom alias already exists")

    def test_expired_link_returns_gone(self) -> None:
        status, _, raw_body = self.request(
            "POST",
            "/urls",
            {"url": "https://example.com", "customAlias": "short", "ttlSeconds": 1},
        )
        self.assertEqual(status, 201)
        time.sleep(1.1)

        status, _, raw_body = self.request("GET", "/short")

        self.assertEqual(status, 410)
        self.assertEqual(json.loads(raw_body)["error"], "Short URL has expired")

    def test_validation_rejects_bad_url_and_alias(self) -> None:
        errors = validate_create_payload("javascript:alert(1)", "no spaces", 0)

        self.assertIn("url must be an absolute http or https URL", errors)
        self.assertIn("customAlias must be 3-32 chars: letters, numbers, underscore, or hyphen", errors)
        self.assertIn("ttlSeconds must be a positive integer", errors)

    def test_create_endpoint_is_rate_limited(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()

        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "rate-limited-links.db"
        handler = create_app(
            database_path,
            create_rate_limit_per_minute=2,
            rate_limit_window_seconds=60,
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

        first_status, _, _ = self.request("POST", "/urls", {"url": "https://example.com/one"})
        second_status, _, _ = self.request("POST", "/urls", {"url": "https://example.com/two"})
        third_status, headers, raw_body = self.request("POST", "/urls", {"url": "https://example.com/three"})

        self.assertEqual(first_status, 201)
        self.assertEqual(second_status, 201)
        self.assertEqual(third_status, 429)
        self.assertEqual(headers["X-RateLimit-Limit"], "2")
        self.assertEqual(headers["X-RateLimit-Remaining"], "0")
        self.assertEqual(json.loads(raw_body)["error"], "Rate limit exceeded")


class LinkStoreTestCase(unittest.TestCase):
    def test_store_persists_created_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = LinkStore(Path(temp_dir) / "links.db")
            link = store.create("https://example.com")

            stored = store.get(link.code)

        self.assertIsNotNone(stored)
        self.assertEqual(stored.long_url, "https://example.com")
        self.assertEqual(stored.visit_count, 0)


if __name__ == "__main__":
    unittest.main()
