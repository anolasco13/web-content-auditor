# Web Content Auditor

A Python command-line tool that audits multilingual web pages for content quality, SEO basics, and localization issues, then writes a pass/fail report with a fix list for each page.

> **Status:** in development. The checks below describe the planned scope.

## Why

Localized websites break in quiet ways. A translated page loses its `hreflang` return link, a `{{placeholder}}` ships unfilled, or an image goes out without alt text. Each issue is small, but together they hurt user experience, accessibility, and search visibility. Checking by hand across many pages and languages is slow and error-prone.

This tool automates those checks so pages can be verified before and after launch.

## What it checks

| Category | Check |
| --- | --- |
| **SEO basics** | Page `<title>` present and within recommended length |
| | Meta description present and within recommended length |
| | Exactly one `<h1>` per page |
| **Accessibility** | Every `<img>` has meaningful `alt` text |
| **Links** | No broken internal or external links (4xx/5xx, timeouts) |
| **Localization** | `<html lang>` attribute present and valid |
| | `hreflang` tags present and valid |
| | Each language version links back to the others (return-link check) |
| **Content integrity** | No leftover template text such as `{{placeholder}}` in the rendered page |

## Usage (planned)

```bash
# Audit a single page
python -m auditor https://example.com/en/

# Audit a list of URLs and write an HTML report
python -m auditor --urls urls.txt --report report.html

# Write CSV instead
python -m auditor --urls urls.txt --report report.csv
```

## Report

Each page gets an overall **PASS** or **FAIL**, a row per check, and a fix list explaining what to change, for example:

```
FAIL  https://example.com/es/
  ✗ hreflang: no return link to en (https://example.com/en/)
  ✗ placeholder: "{{product_name}}" found in <p> near "Compra tu..."
  ✓ title (52 chars)
  ✓ one <h1>
```

## Demo site

A small English/Spanish test site, hosted on GitHub Pages, includes intentional errors (a missing return link, an unfilled placeholder, a missing alt attribute, a broken link) to show the auditor catching each one.

## Tech stack

- Python 3
- [requests](https://requests.readthedocs.io/) for fetching pages and checking links
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) for HTML parsing
- [pytest](https://pytest.org/) for tests, which run against saved HTML samples so they don't need network access

## Roadmap

- [ ] Core checks: title, meta description, `<h1>`, alt text
- [ ] Broken link checker
- [ ] `lang` / `hreflang` validation and return-link check
- [ ] Placeholder detection
- [ ] CSV and HTML reports
- [ ] pytest suite
- [ ] Demo EN/ES site on GitHub Pages

## Responsible use

Only audit sites you own or have permission to test. The link checker sends one request per link; keep URL lists small and respect each site's terms of use.
