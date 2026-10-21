"""Console, CSV and HTML output."""

from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime, timezone
from html import escape
from typing import List, TextIO

from .models import FAIL, PASS, WARN, PageReport

SYMBOL = {PASS: "✓", WARN: "!", FAIL: "✗"}


def summarize(reports: List[PageReport]) -> dict:
    pages = Counter(r.status for r in reports)
    issues = sum(len(r.problems) + (1 if r.fetch_error else 0) for r in reports)
    by_check = Counter(p.check.split(" (")[0] for r in reports for p in r.problems)
    return {"pages": len(reports), PASS: pages[PASS], WARN: pages[WARN], FAIL: pages[FAIL],
            "issues": issues, "by_check": by_check}


# --- Console ----------------------------------------------------------------


def format_page(report: PageReport, verbose: bool = False) -> str:
    lines = [f"{report.status:<4}  {report.url}"]
    if report.fetch_error:
        lines.append(f"  ✗ page could not be loaded: {report.fetch_error}")
    for r in report.results:
        if verbose or not r.passed:
            lines.append(f"  {SYMBOL[r.status]} {r.check}: {r.message}")
    return "\n".join(lines)


def format_summary(reports: List[PageReport]) -> str:
    s = summarize(reports)
    return (f"\n{s['pages']} page(s) audited: {s[PASS]} pass, {s[WARN]} warn, {s[FAIL]} fail; "
            f"{s['issues']} issue(s) found")


# --- CSV --------------------------------------------------------------------

CSV_FIELDS = ["url", "page_status", "check", "status", "severity", "message", "fix"]


def write_csv(reports: List[PageReport], out: TextIO) -> None:
    w = csv.DictWriter(out, fieldnames=CSV_FIELDS)
    w.writeheader()
    for rep in reports:
        if rep.fetch_error:
            w.writerow({"url": rep.url, "page_status": rep.status, "check": "fetch",
                        "status": FAIL, "severity": "error",
                        "message": f"Page could not be loaded: {rep.fetch_error}",
                        "fix": "Check the URL is correct and the page is live."})
        for r in rep.results:
            w.writerow({"url": rep.url, "page_status": rep.status, "check": r.check,
                        "status": r.status, "severity": r.severity, "message": r.message,
                        "fix": r.fix or ""})


# --- HTML -------------------------------------------------------------------

_CSS = """
:root{--bg:#fafaf9;--card:#fff;--text:#1c1917;--muted:#78716c;--line:#e7e5e4;
--pass:#15803d;--pass-bg:#dcfce7;--warn:#a16207;--warn-bg:#fef9c3;--fail:#b91c1c;--fail-bg:#fee2e2}
@media (prefers-color-scheme:dark){:root{--bg:#0c0a09;--card:#1c1917;--text:#f5f5f4;--muted:#a8a29e;
--line:#292524;--pass:#4ade80;--pass-bg:#14532d55;--warn:#facc15;--warn-bg:#713f1255;--fail:#f87171;--fail-bg:#7f1d1d55}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:980px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:24px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 24px;font-size:13px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin-bottom:28px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.stat b{display:block;font-size:26px;font-variant-numeric:tabular-nums}.stat span{color:var(--muted);font-size:13px}
.badge{display:inline-block;min-width:44px;text-align:center;font-size:12px;font-weight:600;padding:2px 8px;border-radius:99px}
.PASS{color:var(--pass);background:var(--pass-bg)}.WARN{color:var(--warn);background:var(--warn-bg)}
.FAIL{color:var(--fail);background:var(--fail-bg)}
details{background:var(--card);border:1px solid var(--line);border-radius:10px;margin-bottom:10px}
summary{cursor:pointer;padding:12px 16px;display:flex;gap:12px;align-items:center;list-style:none}
summary::-webkit-details-marker{display:none}
summary .url{flex:1;min-width:0;overflow-wrap:anywhere;font-family:ui-monospace,Menlo,monospace;font-size:13px}
summary .count{color:var(--muted);font-size:13px;white-space:nowrap}
.body{padding:0 16px 16px;border-top:1px solid var(--line)}
h3{font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:16px 0 8px}
ol.fixes{margin:0;padding-left:20px}ol.fixes li{margin-bottom:8px}ol.fixes .why{color:var(--muted);font-size:13px}
table{width:100%;border-collapse:collapse;font-size:13px}
td{padding:6px 8px;border-top:1px solid var(--line);vertical-align:top}
td:first-child{width:56px}td:nth-child(2){width:150px;font-weight:600}td:last-child{overflow-wrap:anywhere}
footer{color:var(--muted);font-size:12px;margin-top:32px}
"""


def render_html(reports: List[PageReport], title: str = "Web Content Audit") -> str:
    s = summarize(reports)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    stats = "".join(
        f'<div class="stat"><b>{v}</b><span>{label}</span></div>'
        for v, label in [(s["pages"], "pages audited"), (s[PASS], "pass"), (s[WARN], "warnings only"),
                         (s[FAIL], "fail"), (s["issues"], "issues to fix")])

    pages = []
    order = {FAIL: 0, WARN: 1, PASS: 2}
    for rep in sorted(reports, key=lambda r: order[r.status]):
        fixes = []
        if rep.fetch_error:
            fixes.append(f"<li><b>Page could not be loaded ({escape(rep.fetch_error)}).</b> "
                         "Check the URL is correct and the page is live.</li>")
        for p in rep.problems:
            fixes.append(f'<li><span class="badge {p.status}">{p.status}</span> <b>{escape(p.check)}:</b> '
                         f'{escape(p.fix or "")}<div class="why">{escape(p.message)}</div></li>')
        rows = "".join(
            f'<tr><td><span class="badge {r.status}">{r.status}</span></td>'
            f"<td>{escape(r.check)}</td><td>{escape(r.message)}</td></tr>" for r in rep.results)
        n = len(rep.problems) + (1 if rep.fetch_error else 0)
        body = (f'<h3>Fix list</h3><ol class="fixes">{"".join(fixes)}</ol>' if fixes else "")
        if rows:
            body += f"<h3>All checks</h3><table>{rows}</table>"
        pages.append(
            f'<details{" open" if rep.status == FAIL else ""}><summary>'
            f'<span class="badge {rep.status}">{rep.status}</span>'
            f'<span class="url">{escape(rep.url)}</span>'
            f'<span class="count">{n} issue{"s" if n != 1 else ""}</span></summary>'
            f'<div class="body">{body}</div></details>')

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>{_CSS}</style></head>
<body><main>
<h1>{escape(title)}</h1><p class="sub">Generated {stamp} by web-content-auditor</p>
<div class="stats">{stats}</div>
{"".join(pages)}
<footer>Checks: title, meta description, h1, image alt text, html lang, hreflang tags,
hreflang return links, leftover placeholders, broken links.</footer>
</main></body></html>
"""
