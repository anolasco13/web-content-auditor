"""Broken link detection."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from .fetch import USER_AGENT, normalize_url
from .models import CheckResult

SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "sms:")


@dataclass
class LinkStatus:
    url: str
    status_code: Optional[int]
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and self.status_code < 400

    @property
    def reason(self) -> str:
        return self.error or f"HTTP {self.status_code}"


def extract_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    """Absolute http(s) URLs from <a href>, deduplicated, in page order."""
    seen, out = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.lower().startswith(SKIP_SCHEMES):
            continue
        absolute = urljoin(base_url, href)
        if urlsplit(absolute).scheme not in ("http", "https"):
            continue
        key = normalize_url(absolute)
        if key not in seen:
            seen.add(key)
            out.append(absolute)
    return out


class LinkChecker:
    """Checks URLs once each, in parallel, and caches the answers."""

    def __init__(self, session: Optional[requests.Session] = None, timeout: float = 10.0,
                 workers: int = 8):
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)
        self.timeout = timeout
        self.workers = workers
        self._cache: Dict[str, LinkStatus] = {}

    def _check_one(self, url: str) -> LinkStatus:
        try:
            resp = self.session.head(url, timeout=self.timeout, allow_redirects=True)
            # Some servers reject HEAD or answer it wrongly, so confirm with GET.
            if resp.status_code >= 400:
                resp = self.session.get(url, timeout=self.timeout, allow_redirects=True, stream=True)
                resp.close()
            return LinkStatus(url, resp.status_code)
        except requests.Timeout:
            return LinkStatus(url, None, "timed out")
        except requests.RequestException as exc:
            return LinkStatus(url, None, "connection failed" if isinstance(exc, requests.ConnectionError)
                              else type(exc).__name__)

    def check(self, urls: Iterable[str]) -> Dict[str, LinkStatus]:
        todo = [u for u in dict.fromkeys(urls) if normalize_url(u) not in self._cache]
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            for url, status in zip(todo, pool.map(self._check_one, todo)):
                self._cache[normalize_url(url)] = status
        return {u: self._cache[normalize_url(u)] for u in urls}


def check_links(links: List[str], statuses: Dict[str, LinkStatus]) -> List[CheckResult]:
    broken = [statuses[u] for u in links if not statuses[u].ok]
    if not broken:
        return [CheckResult("links", True, f"All {len(links)} link(s) work")]
    shown = "; ".join(f"{s.url} ({s.reason})" for s in broken[:5])
    more = f"; and {len(broken) - 5} more" if len(broken) > 5 else ""
    return [CheckResult("links", False, f"{len(broken)} of {len(links)} link(s) broken: {shown}{more}",
                        "Fix or remove each broken link, or point it to the page's new address.")]
