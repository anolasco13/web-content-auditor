"""Checks that only need a single page's HTML."""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment

from .fetch import normalize_url
from .models import ERROR, WARNING, CheckResult

TITLE_MIN, TITLE_MAX = 10, 60
DESC_MIN, DESC_MAX = 50, 160

# Language tags like "en", "es", "es-MX", "zh-Hant-TW". Not a full BCP 47
# parser, but catches common mistakes like "english", "es_MX" or "e".
LANG_RE = re.compile(r"^[a-zA-Z]{2,3}(-[a-zA-Z0-9]{2,8})*$")

# Template text that should never reach a live page.
PLACEHOLDER_RES = [
    re.compile(r"\{\{\s*[^{}]{1,60}?\s*\}\}"),  # {{name}}  (Handlebars, Jinja, Smartling)
    re.compile(r"\$\{\s*[\w.]{1,60}\s*\}"),  # ${name}   (JS template literals)
    re.compile(r"%\(\w{1,60}\)[sd]"),  # %(name)s  (Python format strings)
]
# Code and unrendered templates legitimately contain template syntax.
SKIP_TAGS = ["script", "style", "noscript", "template"]
PLACEHOLDER_ATTRS = ("alt", "title", "placeholder", "aria-label", "content", "value")


def parse(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _text(tag) -> str:
    return " ".join(tag.get_text(" ", strip=True).split()) if tag else ""


def _snippet(text: str, limit: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


# --- SEO basics -------------------------------------------------------------


def check_title(soup: BeautifulSoup, url: str) -> List[CheckResult]:
    title = _text(soup.title)
    if not title:
        return [CheckResult("title", False, "No <title> found",
                            "Add a unique, descriptive <title> to the <head>.")]
    n = len(title)
    if n < TITLE_MIN or n > TITLE_MAX:
        return [CheckResult(
            "title", False, f'Title is {n} characters: "{_snippet(title)}"',
            f"Keep the title between {TITLE_MIN} and {TITLE_MAX} characters so search results don't cut it off.",
            WARNING,
        )]
    return [CheckResult("title", True, f"Title is {n} characters")]


def check_meta_description(soup: BeautifulSoup, url: str) -> List[CheckResult]:
    tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
    desc = " ".join((tag.get("content") or "").split()) if tag else ""
    if not desc:
        return [CheckResult("meta description", False, "No meta description found",
                            'Add <meta name="description" content="..."> summarizing the page.')]
    n = len(desc)
    if n < DESC_MIN or n > DESC_MAX:
        return [CheckResult(
            "meta description", False, f"Meta description is {n} characters",
            f"Keep the meta description between {DESC_MIN} and {DESC_MAX} characters.",
            WARNING,
        )]
    return [CheckResult("meta description", True, f"Meta description is {n} characters")]


def check_h1(soup: BeautifulSoup, url: str) -> List[CheckResult]:
    h1s = soup.find_all("h1")
    if len(h1s) == 1:
        return [CheckResult("h1", True, f'One <h1>: "{_snippet(_text(h1s[0]))}"')]
    if not h1s:
        return [CheckResult("h1", False, "No <h1> found",
                            "Add one <h1> that states the main topic of the page.")]
    found = "; ".join(f'"{_snippet(_text(h), 30)}"' for h in h1s)
    return [CheckResult("h1", False, f"{len(h1s)} <h1> tags found: {found}",
                        "Keep one <h1> and change the others to <h2> or lower.")]


# --- Accessibility ----------------------------------------------------------


def check_img_alt(soup: BeautifulSoup, url: str) -> List[CheckResult]:
    imgs = soup.find_all("img")
    missing = [img for img in imgs if img.get("alt") is None]
    if not missing:
        return [CheckResult("img alt", True, f"All {len(imgs)} image(s) have alt text")]
    srcs = ", ".join(img.get("src", "(no src)") for img in missing[:5])
    more = f" and {len(missing) - 5} more" if len(missing) > 5 else ""
    return [CheckResult(
        "img alt", False, f"{len(missing)} of {len(imgs)} image(s) missing alt: {srcs}{more}",
        'Add alt text that describes each image, or alt="" if the image is purely decorative.',
    )]


# --- Localization -----------------------------------------------------------


def check_html_lang(soup: BeautifulSoup, url: str) -> List[CheckResult]:
    html = soup.find("html")
    lang = (html.get("lang") or "").strip() if html else ""
    if not lang:
        return [CheckResult("html lang", False, "<html> has no lang attribute",
                            'Set the page language, e.g. <html lang="es-MX">.')]
    if not LANG_RE.match(lang):
        return [CheckResult("html lang", False, f'lang="{lang}" is not a valid language code',
                            'Use a language code such as "en", "es" or "es-MX" (hyphen, not underscore).')]
    return [CheckResult("html lang", True, f'lang="{lang}"')]


def get_hreflangs(soup: BeautifulSoup, base_url: str) -> Dict[str, str]:
    """Map each hreflang code (lowercased) to its absolute URL."""
    out: Dict[str, str] = {}
    for link in soup.find_all("link", hreflang=True):
        rel = [r.lower() for r in (link.get("rel") or [])]
        if "alternate" in rel and link.get("href"):
            out.setdefault(link["hreflang"].strip().lower(), urljoin(base_url, link["href"].strip()))
    return out


def check_hreflang_tags(soup: BeautifulSoup, url: str) -> List[CheckResult]:
    links = [l for l in soup.find_all("link", hreflang=True)
             if "alternate" in [r.lower() for r in (l.get("rel") or [])]]
    if not links:
        return [CheckResult("hreflang", False, "No hreflang alternate links",
                            "If this page has translations, list each one with "
                            '<link rel="alternate" hreflang="..." href="...">.', WARNING)]

    problems: List[str] = []
    seen: Dict[str, int] = {}
    for link in links:
        code = link["hreflang"].strip()
        seen[code.lower()] = seen.get(code.lower(), 0) + 1
        if code.lower() != "x-default" and not LANG_RE.match(code):
            problems.append(f'invalid code "{code}"')
        if not link.get("href"):
            problems.append(f'hreflang="{code}" has no href')
    problems += [f'"{c}" listed {n} times' for c, n in seen.items() if n > 1]

    if problems:
        return [CheckResult("hreflang", False, "hreflang problems: " + "; ".join(problems),
                            "Use valid language codes, one link per language, each with an href.")]

    alts = get_hreflangs(soup, url)
    if normalize_url(url) not in {normalize_url(u) for u in alts.values()}:
        return [CheckResult("hreflang", False,
                            f"{len(alts)} hreflang link(s), but none points to this page itself",
                            "Add a self-referencing hreflang link for this page's own language.",
                            WARNING)]
    return [CheckResult("hreflang", True, f"{len(alts)} hreflang link(s): {', '.join(sorted(alts))}")]


def check_lang_matches_hreflang(soup: BeautifulSoup, url: str) -> List[CheckResult]:
    """The page's own hreflang entry should agree with <html lang>."""
    html = soup.find("html")
    lang = ((html.get("lang") or "").strip().lower()) if html else ""
    alts = get_hreflangs(soup, url)
    self_codes = [c for c, u in alts.items()
                  if normalize_url(u) == normalize_url(url) and c != "x-default"]
    if not lang or not LANG_RE.match(lang) or not self_codes:
        return []  # Covered by the html lang / hreflang checks.
    if any(c == lang or c.split("-")[0] == lang.split("-")[0] for c in self_codes):
        return [CheckResult("lang match", True, f'lang="{lang}" matches hreflang')]
    return [CheckResult("lang match", False,
                        f'<html lang="{lang}"> but this page lists itself as hreflang "{self_codes[0]}"',
                        "Make <html lang> and the page's own hreflang use the same language.")]


# --- Content integrity ------------------------------------------------------


def find_placeholders(soup: BeautifulSoup) -> List[str]:
    """Return "token in <tag>" descriptions for leftover template text."""
    hits: List[str] = []
    for node in soup.find_all(string=True):
        if isinstance(node, Comment) or node.find_parent(SKIP_TAGS):
            continue
        for rx in PLACEHOLDER_RES:
            for m in rx.finditer(node):
                hits.append(f'"{m.group(0)}" in <{node.parent.name}>')
    for tag in soup.find_all(True):
        if tag.name in SKIP_TAGS or tag.find_parent(SKIP_TAGS):
            continue
        for attr in PLACEHOLDER_ATTRS:
            val = tag.get(attr)
            if isinstance(val, str):
                for rx in PLACEHOLDER_RES:
                    for m in rx.finditer(val):
                        hits.append(f'"{m.group(0)}" in <{tag.name} {attr}>')
    return hits


def check_placeholders(soup: BeautifulSoup, url: str) -> List[CheckResult]:
    hits = find_placeholders(soup)
    if not hits:
        return [CheckResult("placeholders", True, "No leftover template placeholders")]
    shown = "; ".join(hits[:5]) + (f"; and {len(hits) - 5} more" if len(hits) > 5 else "")
    return [CheckResult("placeholders", False,
                        f"{len(hits)} unfilled placeholder(s): {shown}",
                        "Replace each placeholder with real content, or fix the template "
                        "variable that failed to render.")]


PAGE_CHECKS: List[Callable[[BeautifulSoup, str], List[CheckResult]]] = [
    check_title,
    check_meta_description,
    check_h1,
    check_img_alt,
    check_html_lang,
    check_hreflang_tags,
    check_lang_matches_hreflang,
    check_placeholders,
]


def run_page_checks(html: str, url: str, soup: Optional[BeautifulSoup] = None) -> List[CheckResult]:
    soup = soup or parse(html)
    results: List[CheckResult] = []
    for check in PAGE_CHECKS:
        results.extend(check(soup, url))
    return results
