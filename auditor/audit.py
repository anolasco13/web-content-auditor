"""Runs every check across a list of URLs."""

from __future__ import annotations

from typing import Callable, List, Optional

from .checks import LANG_RE, get_hreflangs, parse, run_page_checks
from .fetch import Fetcher, Page, normalize_url
from .links import LinkChecker, check_links, extract_links
from .models import WARNING, CheckResult, PageReport


def check_return_links(page: Page, fetcher: Fetcher) -> List[CheckResult]:
    """Each translation this page lists must exist and list this page back.

    Search engines ignore hreflang pairs that aren't confirmed from both
    sides, so a one-way link means the translation may not be shown to the
    right audience.
    """
    soup = parse(page.html)
    alts = get_hreflangs(soup, page.final_url)
    me = {normalize_url(page.url), normalize_url(page.final_url)}
    others = {code: url for code, url in alts.items() if normalize_url(url) not in me}
    if not others:
        return []

    results: List[CheckResult] = []
    for code, url in sorted(others.items()):
        alt = fetcher.get(url)
        name = f"return link ({code})"
        if not alt.ok:
            results.append(CheckResult(
                name, False, f'hreflang "{code}" points to {url}, which failed ({alt.error})',
                "Point the hreflang link at the live translated page."))
            continue
        alt_soup = parse(alt.html)
        back = {normalize_url(u) for u in get_hreflangs(alt_soup, alt.final_url).values()}
        if not back & me:
            results.append(CheckResult(
                name, False, f'The "{code}" version ({url}) does not link back to this page',
                f'Add <link rel="alternate" hreflang="..." href="{page.url}"> to the "{code}" page.'))
            continue
        html_tag = alt_soup.find("html")
        alt_lang = ((html_tag.get("lang") or "").strip().lower()) if html_tag else ""
        if (code != "x-default" and alt_lang and LANG_RE.match(alt_lang)
                and alt_lang.split("-")[0] != code.split("-")[0]):
            results.append(CheckResult(
                name, False, f'hreflang "{code}" points to a page marked lang="{alt_lang}"',
                "Check that the hreflang link points to the right translation.", WARNING))
            continue
        results.append(CheckResult(name, True, f'The "{code}" version links back'))
    return results


def audit(urls: List[str], fetcher: Optional[Fetcher] = None,
          link_checker: Optional[LinkChecker] = None, check_link_status: bool = True,
          on_page: Optional[Callable[[PageReport], None]] = None) -> List[PageReport]:
    fetcher = fetcher or Fetcher()
    link_checker = link_checker or LinkChecker()
    reports: List[PageReport] = []

    for url in urls:
        page = fetcher.get(url)
        report = PageReport(url=url, status_code=page.status_code)
        if not page.ok:
            report.fetch_error = page.error
            reports.append(report)
            if on_page:
                on_page(report)
            continue

        soup = parse(page.html)
        report.results.extend(run_page_checks(page.html, page.final_url, soup))
        report.results.extend(check_return_links(page, fetcher))
        if check_link_status:
            links = extract_links(soup, page.final_url)
            report.results.extend(check_links(links, link_checker.check(links)))
        reports.append(report)
        if on_page:
            on_page(report)
    return reports
