from __future__ import annotations

import socket
import unittest

from phantom_shell.http_policy import (
    URLPolicyError,
    bounded_timeout,
    safe_display_url,
    safe_response_headers,
    validate_outbound_url,
)


def resolver_for(*addresses: str):
    def resolve(hostname, port, *, type):  # noqa: A002, ARG001
        return [
            (socket.AF_INET6 if ":" in value else socket.AF_INET, type, 6, "", (value, 0))
            for value in addresses
        ]

    return resolve


class OutboundURLPolicyTests(unittest.TestCase):
    def test_accepts_public_https_and_removes_fragment(self):
        result = validate_outbound_url(
            "https://API.Example.com:8443/v1/items?q=1#secret",
            resolver=resolver_for("93.184.216.34"),
        )
        self.assertEqual(result, "https://api.example.com:8443/v1/items?q=1")

    def test_rejects_plain_http(self):
        with self.assertRaisesRegex(URLPolicyError, "HTTPS"):
            validate_outbound_url("http://example.com", resolver=resolver_for("93.184.216.34"))

    def test_rejects_embedded_credentials(self):
        with self.assertRaisesRegex(URLPolicyError, "embedded"):
            validate_outbound_url(
                "https://user:secret@example.com",
                resolver=resolver_for("93.184.216.34"),
            )

    def test_rejects_loopback_literal(self):
        with self.assertRaisesRegex(URLPolicyError, "private"):
            validate_outbound_url("https://127.0.0.1/admin")

    def test_rejects_hostname_if_any_preflight_answer_is_private(self):
        with self.assertRaisesRegex(URLPolicyError, "private"):
            validate_outbound_url(
                "https://mixed.example.test",
                resolver=resolver_for("93.184.216.34", "10.0.0.7"),
            )

    def test_private_destination_requires_explicit_override(self):
        result = validate_outbound_url(
            "https://10.0.0.7/internal",
            allow_private=True,
        )
        self.assertEqual(result, "https://10.0.0.7/internal")


class OutputSafetyTests(unittest.TestCase):
    def test_timeout_is_bounded(self):
        self.assertEqual(bounded_timeout(-5), 0.5)
        self.assertEqual(bounded_timeout(500), 30.0)
        self.assertEqual(bounded_timeout("invalid"), 10.0)

    def test_sensitive_headers_are_removed(self):
        result = safe_response_headers(
            {
                "Content-Type": "application/json",
                "Set-Cookie": "session=secret",
                "Authorization": "Bearer secret",
                "X-Request-ID": "req-123",
            }
        )
        self.assertEqual(
            result,
            {"content-type": "application/json", "x-request-id": "req-123"},
        )

    def test_display_url_removes_query_secrets(self):
        self.assertEqual(
            safe_display_url("https://api.example.com/v1/items?token=secret#fragment"),
            "https://api.example.com/v1/items",
        )


if __name__ == "__main__":
    unittest.main()
