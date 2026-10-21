"""Offline stand-ins for requests, so tests never touch the network."""

from typing import Dict, Tuple, Union

Route = Union[Tuple[int, str], Exception]

class FakeResponse:
    def __init__(self, url: str, status_code: int, text: str = ""):
        self.url = url
        self.status_code = status_code
        self.text = text
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"

    def close(self):
        pass

class FakeSession:
    """Answers from a dict of url -> (status, html), or raises a stored exception."""

    def __init__(self, routes: Dict[str, Route], head_status: Dict[str, int] = None):
        self.routes = routes
        self.head_status = head_status or {}
        self.headers: Dict[str, str] = {}
        self.calls = []

    def _answer(self, method: str, url: str):
        self.calls.append((method, url))
        route = self.routes.get(url, (404, "Not Found"))
        if isinstance(route, Exception):
            raise route
        status, html = route
        if method == "HEAD" and url in self.head_status:
            status = self.head_status[url]
        return FakeResponse(url, status, html)

    def get(self, url, **kwargs):
        return self._answer("GET", url)

    def head(self, url, **kwargs):
        return self._answer("HEAD", url)

def page(lang="en", title="Lumen Bikes | Electric bikes for city riding",
         desc="Lightweight electric bikes built for daily city commutes, with free test rides and delivery.",
         head_extra="", body="<h1>Electric bikes</h1><p>Ride further.</p>"):
    """A valid HTML page that individual tests can break on purpose."""
    return f"""<!doctype html><html lang="{lang}"><head>
<title>{title}</title><meta name="description" content="{desc}">{head_extra}
</head><body>{body}</body></html>"""

def hreflang(code: str, href: str) -> str:
    return f'<link rel="alternate" hreflang="{code}" href="{href}">'
