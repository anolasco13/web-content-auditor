"""Report output and the command-line interface."""

import csv
import io

import pytest

from auditor import __main__ as cli
from auditor.models import ERROR, WARNING, CheckResult, PageReport
from auditor.report import format_page, format_summary, render_html, summarize, write_csv


def sample_reports():
    ok = PageReport("https://example.com/en/", 200, results=[
        CheckResult("title", True, "Title is 40 characters")])
    warn = PageReport("https://example.com/es/", 200, results=[
        CheckResult("title", False, "Title is 72 characters", "Shorten it.", WARNING)])
    bad = PageReport("https://example.com/es/about", 200, results=[
        CheckResult("placeholders", False, '1 unfilled placeholder(s): "{{x}}" in <p>',
                    "Replace it.", ERROR),
        CheckResult("h1", True, "One <h1>")])
    down = PageReport("https://example.com/gone", 404, fetch_error="HTTP 404")
    return [ok, warn, bad, down]


def test_page_status_rollup():
    ok, warn, bad, down = sample_reports()
    assert (ok.status, warn.status, bad.status, down.status) == ("PASS", "WARN", "FAIL", "FAIL")


def test_summary_counts():
    s = summarize(sample_reports())
    assert (s["pages"], s["PASS"], s["WARN"], s["FAIL"], s["issues"]) == (4, 1, 1, 2, 3)
    assert "4 page(s) audited: 1 pass, 1 warn, 2 fail; 3 issue(s)" in format_summary(sample_reports())


def test_console_hides_passing_checks_unless_verbose():
    bad = sample_reports()[2]
    assert "h1" not in format_page(bad)
    assert "h1" in format_page(bad, verbose=True)


def test_csv_has_one_row_per_check_plus_fetch_failures():
    buf = io.StringIO()
    write_csv(sample_reports(), buf)
    rows = list(csv.DictReader(io.StringIO(buf.getvalue())))
    assert len(rows) == 5
    assert rows[-1]["check"] == "fetch" and rows[-1]["status"] == "FAIL"
    assert rows[2]["fix"] == "Replace it."


def test_html_report_escapes_content_and_lists_fixes():
    html = render_html(sample_reports())
    assert "<!doctype html>" in html
    assert "&lt;p&gt;" in html and "{{x}}" in html  # page text is escaped, not injected
    assert "Replace it." in html and "Shorten it." in html
    assert html.index("es/about") < html.index("example.com/en/")  # failures first


def test_cli_writes_html_and_returns_1_on_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "audit", lambda urls, *a, on_page=None, **k: sample_reports())
    out = tmp_path / "reports" / "audit.html"
    code = cli.main(["https://example.com/en/", "--report", str(out)])
    assert code == 1
    assert out.exists() and "Fix list" in out.read_text()
    assert "Report written" in capsys.readouterr().out


def test_cli_returns_0_when_nothing_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "audit", lambda urls, *a, on_page=None, **k: sample_reports()[:2])
    assert cli.main(["https://example.com/en/", "--report", str(tmp_path / "a.csv")]) == 0
    assert (tmp_path / "a.csv").read_text().startswith("url,page_status")


def test_cli_reads_url_file_and_skips_comments(tmp_path, monkeypatch):
    seen = {}

    def fake_audit(urls, *a, on_page=None, **k):
        seen["urls"] = urls
        return []

    monkeypatch.setattr(cli, "audit", fake_audit)
    f = tmp_path / "urls.txt"
    f.write_text("# demo\nhttps://a.example/\n\nhttps://b.example/\nhttps://a.example/\n")
    cli.main(["--urls", str(f)])
    assert seen["urls"] == ["https://a.example/", "https://b.example/"]


@pytest.mark.parametrize("argv", [[], ["https://a.example/", "--report", "out.pdf"]])
def test_cli_rejects_bad_arguments(argv):
    with pytest.raises(SystemExit):
        cli.main(argv)
