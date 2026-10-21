"""Command-line interface: python -m auditor URL [URL ...]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .audit import audit
from .fetch import Fetcher
from .links import LinkChecker
from .models import FAIL
from .report import format_page, format_summary, render_html, write_csv


def read_url_file(path: str) -> List[str]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m auditor",
        description="Audit multilingual web pages for SEO basics, accessibility, "
                    "broken links, hreflang and leftover placeholders.")
    p.add_argument("urls", nargs="*", help="page URLs to audit")
    p.add_argument("--urls", dest="url_file", metavar="FILE",
                   help="text file with one URL per line (# for comments)")
    p.add_argument("--report", metavar="PATH",
                   help="write a report; .html or .csv, chosen by file extension")
    p.add_argument("--no-links", action="store_true", help="skip the broken link check")
    p.add_argument("--timeout", type=float, default=10.0, help="seconds per request (default 10)")
    p.add_argument("--workers", type=int, default=8, help="parallel link checks (default 8)")
    p.add_argument("-v", "--verbose", action="store_true", help="show passing checks too")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    urls = list(args.urls)
    if args.url_file:
        urls += read_url_file(args.url_file)
    urls = list(dict.fromkeys(urls))
    if not urls:
        build_parser().error("give at least one URL, or --urls FILE")

    if args.report and Path(args.report).suffix.lower() not in (".html", ".htm", ".csv"):
        build_parser().error("--report must end in .html or .csv")

    fetcher = Fetcher(timeout=args.timeout)
    checker = LinkChecker(timeout=args.timeout, workers=args.workers)
    reports = audit(urls, fetcher, checker, check_link_status=not args.no_links,
                    on_page=lambda r: print(format_page(r, args.verbose), flush=True))
    print(format_summary(reports))

    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.suffix.lower() == ".csv":
            with out.open("w", newline="", encoding="utf-8") as f:
                write_csv(reports, f)
        else:
            out.write_text(render_html(reports), encoding="utf-8")
        print(f"Report written to {out}")

    return 1 if any(r.status == FAIL for r in reports) else 0


if __name__ == "__main__":
    sys.exit(main())
