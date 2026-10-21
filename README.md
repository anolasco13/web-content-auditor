# Web Content Auditor

A Python command-line tool that audits multilingual web pages for content quality, SEO basics, accessibility and localization issues, then writes a pass/fail report with a fix list for each page.

**[View the sample report →](https://anolasco13.github.io/web-content-auditor/sample-report.html)** · **[Demo site →](https://anolasco13.github.io/web-content-auditor/)**

## Why

Localized websites break in quiet ways. A translated page loses its `hreflang` return link, a `{{placeholder}}` ships unfilled, or an image goes out without alt text. Each issue is small, but together they hurt user experience, accessibility and search visibility. Checking by hand across many pages and languages is slow and easy to get wrong.

This tool automates those checks so pages can be verified before and after launch.

## What it checks

| Category | Check | Severity |
| --- | --- | --- |
| **SEO basics** | `<title>` present | Fail |
| | Title is 10–60 characters | Warning |
| | Meta description present | Fail |
| | Meta description is 50–160 characters | Warning |
| | Exactly one `<h1>` | Fail |
| **Accessibility** | Every `<img>` has an `alt` attribute (`alt=""` is accepted for decorative images) | Fail |
| **Links** | No broken links (4xx/5xx, timeouts, connection errors) | Fail |
| **Localization** | `<html lang>` present and a valid language code (`es-MX`, not `es_MX`) | Fail |
| | `hreflang` codes valid, not duplicated, each with an `href` | Fail |
| | Page includes a self-referencing `hreflang` | Warning |
| | `<html lang>` agrees with the page's own `hreflang` | Fail |
| | **Return links:** every translation the page lists exists and links back | Fail |
| | Each translation's `lang` matches the `hreflang` that points to it | Warning |
| **Content integrity** | No leftover template text: `{{name}}`, `${name}`, `%(name)s` in visible text or attributes like `alt` and `content` (code in `<script>`, `<style>` and `<template>` is ignored) | Fail |

A page is **FAIL** if any check fails, **WARN** if it only has warnings, and **PASS** otherwise.

The return-link check matters because search engines ignore `hreflang` pairs that aren't confirmed from both sides. If the Spanish page doesn't point back to the English one, the right version may not be shown to the right audience. The auditor fetches each listed translation, even ones not in your URL list, to confirm the link back.

## Install

```bash
git clone https://github.com/anolasco13/web-content-auditor.git
cd web-content-auditor
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Requires Python 3.9+.

## Usage

```bash
# Audit one or more pages
python -m auditor https://example.com/en/ https://example.com/es/

# Audit a list of URLs (one per line, # for comments) and write an HTML report
python -m auditor --urls urls.txt --report report.html

# CSV instead (one row per check, for spreadsheets or tracking tickets)
python -m auditor --urls urls.txt --report report.csv

# Skip the broken link check, or show passing checks too
python -m auditor --urls urls.txt --no-links -v
```

The command exits with code `1` if any page fails, so it can run as a check in CI before a launch.

## Example: the demo site

The [demo site](https://anolasco13.github.io/web-content-auditor/) is a fictional English/Spanish e-bike shop with **8 intentional errors** spread across 5 pages. Running the auditor against it:

```
$ python -m auditor --urls urls.txt --report docs/sample-report.html
PASS  https://anolasco13.github.io/web-content-auditor/
PASS  https://anolasco13.github.io/web-content-auditor/en/
FAIL  https://anolasco13.github.io/web-content-auditor/es/
  ✗ meta description: No meta description found
  ✗ placeholders: 1 unfilled placeholder(s): "{{precio_mensual}}" in <p>
FAIL  https://anolasco13.github.io/web-content-auditor/en/about.html
  ✗ img alt: 1 of 1 image(s) missing alt: ../assets/bike.svg
  ✗ return link (es): The "es" version (.../es/about.html) does not link back to this page
  ✗ links: 1 of 4 link(s) broken: .../en/contact.html (HTTP 404)
FAIL  https://anolasco13.github.io/web-content-auditor/es/about.html
  ! title: Title is 85 characters: "Acerca de Lumen Bikes | Nuestra historia y nuestro compromi…"
  ✗ h1: 2 <h1> tags found: "Acerca de Lumen Bikes"; "Nuestra historia"
  ✗ html lang: lang="es_MX" is not a valid language code

5 page(s) audited: 2 pass, 0 warn, 3 fail; 8 issue(s) found
```

All 8 planted errors were caught, with no false alarms on the two clean pages. The [HTML report](https://anolasco13.github.io/web-content-auditor/sample-report.html) lists failing pages first, each with a fix list.

| Planted error | Page | Caught by |
| --- | --- | --- |
| Unfilled `{{precio_mensual}}` price | `es/` | placeholders |
| Missing meta description | `es/` | meta description |
| Image without alt text | `en/about.html` | img alt |
| Link to a page that doesn't exist | `en/about.html` | links |
| Spanish page doesn't link back to English | `es/about.html` → reported on `en/about.html` | return link |
| `lang="es_MX"` (underscore) | `es/about.html` | html lang |
| Two `<h1>` tags | `es/about.html` | h1 |
| 85-character title | `es/about.html` | title (warning) |

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

72 tests cover every check, the return-link logic, the link checker (including HEAD-to-GET fallback, timeouts and caching), the reports and the CLI. They use a fake HTTP session, so they run offline in well under a second.

## Project layout

```
auditor/
  checks.py    single-page checks (SEO, accessibility, lang/hreflang, placeholders)
  audit.py     runs all checks across URLs, including the hreflang return-link check
  links.py     extracts links and checks them in parallel, with caching
  fetch.py     page fetching with a cache and URL normalization
  report.py    console, CSV and HTML output
  __main__.py  command-line interface
tests/         pytest suite
docs/          demo site and sample report (served by GitHub Pages)
urls.txt       demo site URLs
```

## Responsible use

Only audit sites you own or have permission to test. The tool identifies itself with a `web-content-auditor` User-Agent and checks each link once per run, but keep URL lists small and respect each site's terms of use.
