import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "runtime"), str(ROOT / "panel")]
os.environ["LAMP_TESTING"] = "1"
from common import hostname, identifier, php_limits
from app import create_app


class ValidationTests(unittest.TestCase):
    def test_valid_hostnames(self):
        for value in ("localhost", "studio.localhost", "www.example.com", "a-b.example"):
            self.assertEqual(hostname(value), value)

    def test_rejects_host_injection(self):
        for value in (None, "", "../test", "a\nServerAlias evil", "a:80", "https://a", "UPPER.test", "-bad.test", "a..b", "127.0.0.1", "a" * 64):
            with self.subTest(value=value), self.assertRaises(ValueError):
                hostname(value)

    def test_site_ids_are_not_paths(self):
        self.assertEqual(identifier("s0123456789ab"), "s0123456789ab")
        for value in ("../etc", "s123", "s0123456789ab/../", "$(id)"):
            with self.assertRaises(ValueError):
                identifier(value)

    def test_php_boundaries(self):
        self.assertEqual(php_limits({})["memory"], 256)
        for value in (63, 1025, True, "256M", "128\nlisten=0", 64.5):
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                php_limits({"memory": value})


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.config = {"key": "test-key-not-a-runtime-secret", "host": "localhost", "mode": "development", "proxies": [], "filebrowser_key": "test"}
        self.app = create_app(self.config)
        self.app.testing = True
        self.client = self.app.test_client()

    def authenticate(self):
        with self.client.session_transaction() as session:
            session.update(authenticated=True, csrf="test-csrf")

    def test_anonymous_endpoints_denied(self):
        self.assertEqual(self.client.get("/api/overview").status_code, 401)
        for path in ("/", "/mo", "/filebrowser/", "/phpmyadmin/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 302)

    def test_csrf_denies_even_valid_session(self):
        self.authenticate()
        with patch("app.rpc") as worker:
            self.assertEqual(self.client.post("/api/actions/site.create", json={}).status_code, 403)
            worker.assert_not_called()

    def test_cross_origin_write_denied(self):
        self.authenticate()
        self.assertEqual(self.client.post("/api/actions/site.create", json={}, headers={"X-CSRF-Token": "test-csrf", "Origin": "https://evil.test"}).status_code, 403)

    def test_only_allowlisted_actions(self):
        self.authenticate()
        self.assertEqual(self.client.post("/api/actions/shell", json={}, headers={"X-CSRF-Token": "test-csrf"}).status_code, 404)

    def test_valid_action_forwarded(self):
        self.authenticate()
        with patch("app.rpc", return_value={"job": "example"}) as worker:
            response = self.client.post("/api/actions/site.create", json={"hostname": "studio.localhost"}, headers={"X-CSRF-Token": "test-csrf"})
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json, {"job": "example"})

    def test_wrong_host_and_untrusted_proxy_denied(self):
        self.assertEqual(self.client.get("/login", headers={"Host": "evil.test"}).status_code, 400)
        self.config.update(mode="hosting", proxies=["172.30.0.0/24"])
        client = create_app(self.config).test_client()
        self.assertEqual(client.get("/login", headers={"X-Lamp-Client": "192.0.2.5", "X-Forwarded-Proto": "https"}).status_code, 400)
        self.assertEqual(client.get("/login", headers={"X-Lamp-Client": "172.30.0.2", "X-Forwarded-Proto": "https"}).status_code, 200)

    def test_login_rotates_session_and_security_headers(self):
        self.client.get("/login")
        with self.client.session_transaction() as session:
            csrf = session["csrf"]
        with patch("app.rpc", return_value=True):
            response = self.client.post("/login", data={"csrf": csrf, "username": "owner", "password": "test-password"})
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertNotEqual(session["csrf"], csrf)
        self.assertIn("HttpOnly", response.headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", response.headers["Set-Cookie"])
        self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()
