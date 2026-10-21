"""Cross-page checks (hreflang return links, broken links) and the full audit run."""

import requests

from auditor.audit import audit, check_return_links
from auditor.fetch import normalize_url
from auditor.links import extract_links
from auditor.checks import parse
from auditor.models import FAIL, PASS, WARN
from helpers import hreflang, page

EN = "https://example.com/en/"
ES = "https://example.com/es/"
BODY = "<h1>Bikes</h1>"


def pair(en_head, es_head, es_lang="es"):
    return {EN: (200, page(lang="en", head_extra=en_head, body=BODY)),
            ES: (200, page(lang=es_lang, head_extra=es_head, body=BODY))}


BOTH = hreflang("en", EN) + hreflang("es", ES)


# --- normalize_url ----------------------------------------------------------


def test_normalize_url():
    assert normalize_url("HTTPS://Example.com:443/es/#top") == "https://example.com/es/"
    assert normalize_url("http://example.com") == "http://example.com/"
    assert normalize_url("http://example.com:8080/a?b=1") == "http://example.com:8080/a?b=1"
    assert normalize_url("https://example.com/es") != normalize_url("https://example.com/es/")


# --- return links -----------------------------------------------------------


def test_return_link_ok(make_tools):
    fetcher, _, _ = make_tools(pair(BOTH, BOTH))
    results = check_return_links(fetcher.get(EN), fetcher)
    assert [r.status for r in results] == [PASS]
    assert results[0].check == "return link (es)"


def test_missing_return_link(make_tools):
    fetcher, _, _ = make_tools(pair(BOTH, hreflang("es", ES)))
    [r] = check_return_links(fetcher.get(EN), fetcher)
    assert r.status == FAIL and "does not link back" in r.message
    assert EN in r.fix


def test_return_link_to_missing_page(make_tools):
    fetcher, _, _ = make_tools({EN: (200, page(head_extra=BOTH, body=BODY))})
    [r] = check_return_links(fetcher.get(EN), fetcher)
    assert r.status == FAIL and "HTTP 404" in r.message


def test_return_link_points_to_wrong_language(make_tools):
    fetcher, _, _ = make_tools(pair(BOTH, BOTH, es_lang="en"))
    [r] = check_return_links(fetcher.get(EN), fetcher)
    assert r.status == WARN and 'lang="en"' in r.message


def test_return_link_follows_redirects(make_tools):
    # The ES page lists EN without the trailing slash; the server redirects it.
    fetcher, _, session = make_tools(pair(BOTH, hreflang("en", EN) + hreflang("es", ES)))
    page_obj = fetcher.get(EN)
    page_obj.url = "https://example.com/en"  # what the user typed
    [r] = check_return_links(page_obj, fetcher)
    assert r.passed


def test_no_alternates_means_no_return_checks(make_tools):
    fetcher, _, _ = make_tools({EN: (200, page(body=BODY))})
    assert check_return_links(fetcher.get(EN), fetcher) == []


# --- links ------------------------------------------------------------------


def test_extract_links_resolves_dedupes_and_skips():
    html = page(body="""<h1>x</h1>
      <a href="/es/">Español</a><a href="https://example.com/es/#top">again</a>
      <a href="#faq">jump</a><a href="mailto:hi@example.com">mail</a>
      <a href="tel:+15555555555">call</a><a href="javascript:void(0)">js</a>
      <a href="ftp://example.com/file">ftp</a><a href="pricing.html">Pricing</a>""")
    assert extract_links(parse(html), EN) == [ES, "https://example.com/en/pricing.html"]


def test_link_checker_reports_broken_links(make_tools):
    good, bad = "https://example.com/ok", "https://example.com/gone"
    _, checker, _ = make_tools({good: (200, ""), bad: (404, "")})
    statuses = checker.check([good, bad])
    assert statuses[good].ok and not statuses[bad].ok
    assert statuses[bad].reason == "HTTP 404"


def test_link_checker_falls_back_to_get_when_head_is_rejected(make_tools):
    url = "https://example.com/no-head"
    _, checker, session = make_tools({url: (200, "")}, head_status={url: 405})
    assert checker.check([url])[url].ok
    assert ("GET", url) in session.calls


def test_link_checker_handles_timeouts_and_connection_errors(make_tools):
    slow, down = "https://slow.example/", "https://down.example/"
    _, checker, _ = make_tools({slow: requests.Timeout(), down: requests.ConnectionError()})
    statuses = checker.check([slow, down])
    assert statuses[slow].reason == "timed out"
    assert statuses[down].reason == "connection failed"


def test_link_checker_caches_results(make_tools):
    url = "https://example.com/ok"
    _, checker, session = make_tools({url: (200, "")})
    checker.check([url])
    checker.check([url, url + "#section"])
    assert session.calls.count(("HEAD", url)) == 1


# --- full audit -------------------------------------------------------------


def test_audit_clean_pair_passes(make_tools):
    routes = pair(BOTH, BOTH)
    fetcher, checker, _ = make_tools(routes)
    reports = audit([EN, ES], fetcher, checker)
    assert [r.status for r in reports] == [PASS, PASS]


def test_audit_finds_planted_problems(make_tools):
    en = page(lang="en", head_extra=BOTH,
              body='<h1>Bikes</h1><img src="bike.png"><a href="/missing">Contact</a>')
    es = page(lang="es", head_extra=hreflang("es", ES),
              body="<h1>Bicis</h1><p>Desde {{precio}} al mes</p>")
    fetcher, checker, _ = make_tools({EN: (200, en), ES: (200, es)})
    reports = {r.url: r for r in audit([EN, ES], fetcher, checker)}

    en_problems = {p.check for p in reports[EN].problems}
    assert en_problems == {"img alt", "links", "return link (es)"}
    assert {p.check for p in reports[ES].problems} == {"placeholders"}
    assert reports[EN].status == FAIL and reports[ES].status == FAIL


def test_audit_reports_unreachable_page(make_tools):
    fetcher, checker, _ = make_tools({})
    [rep] = audit(["https://example.com/nope"], fetcher, checker)
    assert rep.status == FAIL and rep.fetch_error == "HTTP 404" and rep.results == []


def test_audit_can_skip_link_checks(make_tools):
    fetcher, checker, session = make_tools(
        {EN: (200, page(body='<h1>x</h1><a href="/gone">x</a>'))})
    [rep] = audit([EN], fetcher, checker, check_link_status=False)
    assert "links" not in {r.check for r in rep.results}
    assert not any(method == "HEAD" for method, _ in session.calls)
