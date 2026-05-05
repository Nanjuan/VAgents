"""
Capability-scoped HTTP helpers for MCP — no shell execution.

Optional env HTTP_LAB_ALLOWED_HOSTS: comma-separated hostnames or suffixes (case-insensitive).
If set, request hostname must equal one entry or end with .suffix when suffix starts with '.'.
"""
from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("http-lab-tools")

_MAX_BODY_CHARS = 80_000
_DEFAULT_TIMEOUT = 30.0


def _parse_allowed_hosts() -> list[str]:
    raw = (os.environ.get("HTTP_LAB_ALLOWED_HOSTS") or "").strip()
    if not raw:
        return []
    return [h.strip().lower() for h in raw.split(",") if h.strip()]


def _host_allowed(hostname: str) -> bool:
    host = hostname.lower().strip()
    allowed = _parse_allowed_hosts()
    if not allowed:
        return True
    for entry in allowed:
        if host == entry:
            return True
        if entry.startswith(".") and host.endswith(entry):
            return True
        if entry.startswith("*."):
            suf = entry[2:]
            if host == suf or host.endswith("." + suf):
                return True
    return False


def _validate_http_url(url: str) -> tuple[str | None, str | None]:
    """Returns (hostname, error_message). hostname None means invalid."""
    if not url or not isinstance(url, str):
        return None, "url is required"
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return None, f"only http and https are allowed, got scheme={parsed.scheme!r}"
    if not parsed.hostname:
        return None, "missing hostname"
    if not _host_allowed(parsed.hostname):
        return None, f"host {parsed.hostname!r} is not allowed by HTTP_LAB_ALLOWED_HOSTS"
    return parsed.hostname, None


@mcp.tool()
def http_fetch(url: str) -> dict:
    """Fetch a URL with HTTP GET. Returns status_code, truncated text body, and selected response headers. Only http/https."""
    _, err = _validate_http_url(url)
    if err:
        return {"status": "error", "error": err}
    try:
        with httpx.Client(
            timeout=_DEFAULT_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "VAgents-http-lab/1.0"},
        ) as client:
            r = client.get(url)
        text = r.text
        if len(text) > _MAX_BODY_CHARS:
            text = text[:_MAX_BODY_CHARS] + f"\n[truncated at {_MAX_BODY_CHARS} chars]"
        pick_headers = {
            k: v
            for k, v in r.headers.items()
            if k.lower()
            in (
                "content-type",
                "content-length",
                "server",
                "date",
                "location",
            )
        }
        return {
            "status": "success",
            "url": str(r.url),
            "status_code": r.status_code,
            "headers": pick_headers,
            "text": text,
        }
    except httpx.HTTPError as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def http_head(url: str) -> dict:
    """Send HTTP HEAD. Returns status_code and response headers. Only http/https."""
    _, err = _validate_http_url(url)
    if err:
        return {"status": "error", "error": err}
    try:
        with httpx.Client(
            timeout=_DEFAULT_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "VAgents-http-lab/1.0"},
        ) as client:
            r = client.head(url)
        return {
            "status": "success",
            "url": str(r.url),
            "status_code": r.status_code,
            "headers": dict(r.headers),
        }
    except httpx.HTTPError as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
def dns_resolve(hostname: str) -> dict:
    """Resolve a hostname to IPv4/IPv6 addresses using getaddrinfo (no subprocess)."""
    if not hostname or not isinstance(hostname, str):
        return {"status": "error", "error": "hostname is required"}
    h = hostname.strip()
    if not h:
        return {"status": "error", "error": "hostname is empty"}
    if not _host_allowed(h):
        return {"status": "error", "error": "hostname not allowed by HTTP_LAB_ALLOWED_HOSTS"}
    try:
        infos = socket.getaddrinfo(h, None)
    except socket.gaierror as e:
        return {"status": "error", "error": str(e)}
    seen: set[tuple[str, str]] = set()
    addresses: list[dict[str, str]] = []
    for family, _, _, _, sockaddr in infos:
        if len(sockaddr) >= 1:
            addr = sockaddr[0]
            fam = "ipv6" if family == socket.AF_INET6 else "ipv4"
            key = (fam, addr)
            if key not in seen:
                seen.add(key)
                addresses.append({"family": fam, "address": addr})
    return {"status": "success", "hostname": h, "addresses": addresses}


if __name__ == "__main__":
    mcp.run()
