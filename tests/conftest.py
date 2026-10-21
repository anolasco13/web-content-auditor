import pytest

from auditor.fetch import Fetcher
from auditor.links import LinkChecker
from helpers import FakeSession


@pytest.fixture
def make_tools():
    """Build a Fetcher and LinkChecker that share one offline FakeSession."""
    def _make(routes, head_status=None):
        session = FakeSession(routes, head_status)
        return Fetcher(session=session), LinkChecker(session=session, workers=2), session
    return _make
