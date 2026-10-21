"""Data types shared across the auditor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

ERROR = "error"
WARNING = "warning"

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


@dataclass
class CheckResult:
    """The outcome of one check on one page."""

    check: str
    passed: bool
    message: str
    fix: Optional[str] = None
    severity: str = ERROR

    @property
    def status(self) -> str:
        if self.passed:
            return PASS
        return FAIL if self.severity == ERROR else WARN


@dataclass
class PageReport:
    """Every check result for one URL."""

    url: str
    status_code: Optional[int] = None
    fetch_error: Optional[str] = None
    results: List[CheckResult] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.fetch_error:
            return FAIL
        statuses = {r.status for r in self.results}
        if FAIL in statuses:
            return FAIL
        if WARN in statuses:
            return WARN
        return PASS

    @property
    def problems(self) -> List[CheckResult]:
        return [r for r in self.results if not r.passed]
