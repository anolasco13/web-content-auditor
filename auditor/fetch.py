"""Fetching pages, with a cache so each URL is downloaded at most once."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import urldefrag, urlsplit, urlunsplit

import requests

USER_AGENT = (
    "web-content-auditor/0.1 (+https://github.com/anolasco13/web-content-auditor)"
)


def normalize_url(url: str) -> str:
    """Normalize a URL so the same page compares equal.

    Drops the #fragment, lowercases the scheme and host, removes default
    ports, and turns an empty path into "/". Trailing slashes are kept,
    because /es and /es/ can be different pages.
    """
    url, _ = urldefrag(url.strip())
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    if port and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        host = f"{host}:{port}"
    path = parts.path or "/"
    return urlunsplit((scheme, host, path, parts.query, ""))


@dataclass
class Page:
    url: str
    final_url: str
    status_code: Optional[int]
    html: str = ""
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and self.status_code < 400


class Fetcher:
    """Downloads pages and remembers them."""

    def __init__(self, session: Optional[requests.Session] = None, timeout: float = 10.0):
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)
        self.timeout = timeout
        self._cache: Dict[str, Page] = {}

    def get(self, url: str) -> Page:
        key = normalize_url(url)
        if key in self._cache:
            return self._cache[key]
        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            resp.encoding = resp.encoding or resp.apparent_encoding
            page = Page(
                url=url,
                final_url=resp.url,
                status_code=resp.status_code,
                html=resp.text,
                error=None if resp.status_code < 400 else f"HTTP {resp.status_code}",
            )
        except requests.RequestException as exc:
            page = Page(url=url, final_url=url, status_code=None, error=_short_error(exc))
        self._cache[key] = page
        self._cache.setdefault(normalize_url(page.final_url), page)
        return page


def _short_error(exc: Exception) -> str:
    name = type(exc).__name__
    if isinstance(exc, requests.Timeout):
        return "timed out"
    if isinstance(exc, requests.ConnectionError):
        return "connection failed"
    return name
