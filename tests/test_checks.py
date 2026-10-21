"""Single-page checks: SEO basics, accessibility, lang/hreflang tags, placeholders."""

import pytest

from auditor import checks
from auditor.models import ERROR, FAIL, PASS, WARN, WARNING
from helpers import hreflang, page

URL = "https://example.com/en/"


def run(check, html, url=URL):
    return check(checks.parse(html), url)


def only(results):
    assert len(results) == 1, results
    return results[0]


# --- title ------------------------------------------------------------------


def test_title_ok():
    r = only(run(checks.check_title, page()))
    assert r.passed and "characters" in r.message


def test_title_missing_is_error():
    r = only(run(checks.check_title, page(title="")))
    assert not r.passed and r.severity == ERROR and r.status == FAIL


@pytest.mark.parametrize("title", ["Home", "x" * 61])
def test_title_bad_length_is_warning(title):
    r = only(run(checks.check_title, page(title=title)))
    assert not r.passed and r.severity == WARNING and r.status == WARN


def test_title_length_boundaries_pass():
    assert only(run(checks.check_title, page(title="x" * 10))).passed
    assert only(run(checks.check_title, page(title="x" * 60))).passed


def test_title_whitespace_is_collapsed():
    r = only(run(checks.check_title, page(title="  Lumen   Bikes\n  Home  ")))
    assert r.passed and "16 characters" in r.message


# --- meta description -------------------------------------------------------


def test_meta_description_ok():
    assert only(run(checks.check_meta_description, page())).passed


def test_meta_description_missing():
    html = page().replace('<meta name="description"', '<meta name="keywords"')
    r = only(run(checks.check_meta_description, html))
    assert not r.passed and r.severity == ERROR


def test_meta_description_empty_counts_as_missing():
    r = only(run(checks.check_meta_description, page(desc="   ")))
    assert not r.passed and r.severity == ERROR


def test_meta_description_too_long_is_warning():
    r = only(run(checks.check_meta_description, page(desc="word " * 40)))
    assert r.status == WARN


def test_meta_description_name_is_case_insensitive():
    html = page().replace('name="description"', 'name="Description"')
    assert only(run(checks.check_meta_description, html)).passed


# --- h1 ---------------------------------------------------------------------


def test_one_h1_passes():
    assert only(run(checks.check_h1, page())).passed


def test_no_h1_fails():
    r = only(run(checks.check_h1, page(body="<h2>Hi</h2>")))
    assert not r.passed and "No <h1>" in r.message


def test_two_h1_fails_and_names_them():
    r = only(run(checks.check_h1, page(body="<h1>First</h1><h1>Second</h1>")))
    assert not r.passed and "2 <h1>" in r.message and "Second" in r.message


# --- img alt ----------------------------------------------------------------


def test_img_alt_ok_including_decorative_empty_alt():
    body = '<h1>x</h1><img src="a.png" alt="A bike"><img src="line.svg" alt="">'
    assert only(run(checks.check_img_alt, page(body=body))).passed


def test_img_missing_alt_lists_src():
    body = '<h1>x</h1><img src="a.png" alt="A bike"><img src="b.png">'
    r = only(run(checks.check_img_alt, page(body=body)))
    assert not r.passed and "1 of 2" in r.message and "b.png" in r.message


def test_page_without_images_passes():
    r = only(run(checks.check_img_alt, page()))
    assert r.passed and "All 0" in r.message


# --- html lang --------------------------------------------------------------


@pytest.mark.parametrize("lang", ["en", "es", "es-MX", "zh-Hant-TW", "fil"])
def test_valid_lang(lang):
    assert only(run(checks.check_html_lang, page(lang=lang))).passed


@pytest.mark.parametrize("lang", ["es_MX", "english", "e", "en-"])
def test_invalid_lang(lang):
    r = only(run(checks.check_html_lang, page(lang=lang)))
    assert not r.passed and "not a valid" in r.message


def test_missing_lang():
    html = page().replace(' lang="en"', "")
    r = only(run(checks.check_html_lang, html))
    assert not r.passed and "no lang" in r.message


# --- hreflang tags ----------------------------------------------------------

EN, ES = "https://example.com/en/", "https://example.com/es/"


def test_hreflang_ok_with_self_reference():
    head = hreflang("en", EN) + hreflang("es", ES) + hreflang("x-default", EN)
    r = only(run(checks.check_hreflang_tags, page(head_extra=head)))
    assert r.passed and "en, es, x-default" in r.message


def test_hreflang_relative_hrefs_are_resolved():
    head = hreflang("en", "/en/") + hreflang("es", "/es/")
    assert only(run(checks.check_hreflang_tags, page(head_extra=head))).passed


def test_no_hreflang_is_warning():
    r = only(run(checks.check_hreflang_tags, page()))
    assert r.status == WARN


def test_hreflang_without_self_reference_is_warning():
    r = only(run(checks.check_hreflang_tags, page(head_extra=hreflang("es", ES))))
    assert r.status == WARN and "none points to this page" in r.message


def test_hreflang_invalid_code():
    head = hreflang("en", EN) + hreflang("es_MX", ES)
    r = only(run(checks.check_hreflang_tags, page(head_extra=head)))
    assert r.status == FAIL and "es_MX" in r.message


def test_hreflang_duplicate_code():
    head = hreflang("en", EN) + hreflang("es", ES) + hreflang("es", "https://example.com/mx/")
    r = only(run(checks.check_hreflang_tags, page(head_extra=head)))
    assert r.status == FAIL and "listed 2 times" in r.message


def test_hreflang_ignores_non_alternate_links():
    head = hreflang("en", EN) + '<link rel="stylesheet" hreflang="es" href="/es.css">'
    assert checks.get_hreflangs(checks.parse(page(head_extra=head)), EN) == {"en": EN}


# --- lang vs. hreflang ------------------------------------------------------


def test_lang_matches_hreflang_region_variant():
    head = hreflang("es-mx", EN)
    r = only(run(checks.check_lang_matches_hreflang, page(lang="es", head_extra=head)))
    assert r.passed


def test_lang_mismatch_with_own_hreflang():
    head = hreflang("es", EN)
    r = only(run(checks.check_lang_matches_hreflang, page(lang="en", head_extra=head)))
    assert not r.passed and 'hreflang "es"' in r.message


def test_lang_match_skipped_when_lang_invalid():
    head = hreflang("es", EN)
    assert run(checks.check_lang_matches_hreflang, page(lang="es_MX", head_extra=head)) == []


# --- placeholders -----------------------------------------------------------


@pytest.mark.parametrize("token", ["{{product_name}}", "{{ price }}", "${user.name}", "%(count)s"])
def test_placeholder_in_text(token):
    r = only(run(checks.check_placeholders, page(body=f"<h1>Hi</h1><p>Buy {token} today</p>")))
    assert not r.passed and token in r.message and "<p>" in r.message


def test_placeholder_in_attribute():
    body = '<h1>Hi</h1><img src="a.png" alt="{{hero_alt}}">'
    r = only(run(checks.check_placeholders, page(body=body)))
    assert not r.passed and "<img alt>" in r.message


def test_placeholder_in_meta_description():
    r = only(run(checks.check_placeholders, page(desc="Buy {{product}} now")))
    assert not r.passed and "<meta content>" in r.message


def test_placeholders_in_scripts_styles_and_comments_are_ignored():
    body = ("<h1>Hi</h1><script>const t = `${name}`; const h = '{{x}}';</script>"
            "<style>/* {{y}} */</style><!-- {{z}} -->"
            "<template><p>{{row.label}}</p><img alt='{{row.alt}}'></template>")
    assert only(run(checks.check_placeholders, page(body=body))).passed


def test_plain_braces_are_not_placeholders():
    body = "<h1>Hi</h1><p>Use {curly} or { } or a set {1, 2}.</p>"
    assert only(run(checks.check_placeholders, page(body=body))).passed


# --- all together -----------------------------------------------------------


def test_clean_page_has_no_failures():
    head = hreflang("en", EN) + hreflang("es", ES)
    body = '<h1>Electric bikes</h1><img src="bike.png" alt="Lumen city bike">'
    results = checks.run_page_checks(page(head_extra=head, body=body), EN)
    assert all(r.passed for r in results), [r for r in results if not r.passed]
    assert {r.status for r in results} == {PASS}
