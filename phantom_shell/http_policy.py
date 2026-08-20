"""Safety policy helpers for outbound HTTP automation.

This module provides a fail-closed URL preflight before network calls. It blocks
obvious local/private destinations, insecure schemes, embedded credentials, and
unbounded timeouts. DNS is necessarily resolved again by the HTTP client at
connection time, so this preflight is a defense layer rather than a claim of
complete DNS-rebinding resistance.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterable, Mapping
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit


class URLPolicyError(ValueError):
    """Raised when an outbound URL does not satisfy the safety policy."""


Resolver = Callable[..., Iterable[tuple[Any, ...]]]

SAFE_RESPONSE_HEADERS = {
    "content-length",
    "content-type",
    "date",
    "etag",
    "last-modified",
    "retry-after",
    "x-request-id",
}


def _is_public_address(value: str) -> bool:
    address = ipaddress.ip_address(value)
    return bool(address.is_global)


def _resolved_addresses(hostname: str, resolver: Resolver) -> set[str]:
    try:
        rows = resolver(hostname, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise URLPolicyError(f"Unable to resolve destination host: {exc}") from exc

    addresses: set[str] = set()
    for row in rows:
        if len(row) < 5:
            continue
        sockaddr = row[4]
        if not sockaddr:
            continue
        addresses.add(str(sockaddr[0]))

    if not addresses:
        raise URLPolicyError("Destination host did not resolve to an IP address")
    return addresses


def validate_outbound_url(
    raw_url: str,
    *,
    resolver: Resolver = socket.getaddrinfo,
    allow_private: bool = False,
) -> str:
    """Validate and normalize a URL before an outbound automation request.

    HTTPS is required, embedded credentials are rejected, and any private,
    loopback, link-local, multicast, reserved, or unspecified address seen in
    the DNS preflight is blocked unless ``allow_private`` is explicitly enabled.
    """

    if not isinstance(raw_url, str) or not raw_url.strip():
        raise URLPolicyError("A non-empty URL is required")

    try:
        parts: SplitResult = urlsplit(raw_url.strip())
        port = parts.port
    except ValueError as exc:
        raise URLPolicyError(f"Invalid URL: {exc}") from exc

    if parts.scheme.lower() != "https":
        raise URLPolicyError("Only HTTPS destinations are allowed")
    if not parts.hostname:
        raise URLPolicyError("Destination URL must include a hostname")
    if parts.username is not None or parts.password is not None:
        raise URLPolicyError("Credentials must not be embedded in the URL")
    if port is not None and not 1 <= port <= 65535:
        raise URLPolicyError("Destination port is outside the valid range")

    hostname = parts.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        if not allow_private:
            raise URLPolicyError("Local and private destinations are blocked")
    else:
        try:
            addresses = {hostname} if _looks_like_ip(hostname) else _resolved_addresses(hostname, resolver)
        except ValueError as exc:
            raise URLPolicyError(f"Invalid destination address: {exc}") from exc
        if not allow_private and any(not _is_public_address(value) for value in addresses):
            raise URLPolicyError("Local and private destinations are blocked")

    host_for_url = f"[{hostname}]" if ":" in hostname else hostname
    netloc = f"{host_for_url}:{port}" if port is not None else host_for_url
    return urlunsplit(("https", netloc, parts.path or "", parts.query or "", ""))


def _looks_like_ip(hostname: str) -> bool:
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return True


def bounded_timeout(value: object, *, default: float = 10.0) -> float:
    """Coerce a request timeout to a conservative 0.5-to-30-second range."""

    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return default
    return min(30.0, max(0.5, timeout))


def safe_response_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Return only low-risk diagnostic response headers."""

    return {
        str(name).lower(): str(value)
        for name, value in headers.items()
        if str(name).lower() in SAFE_RESPONSE_HEADERS
    }


def safe_display_url(url: str) -> str:
    """Remove query parameters and fragments before returning a display URL."""

    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
