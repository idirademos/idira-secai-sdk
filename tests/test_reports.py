"""Unit tests for the SDK-level ``ReportsResource``.

Like ``test_pagination.py`` and ``test_client_resilience.py``, these tests
call ``client.reports`` methods directly through a real ``SecAIClient``
instance against a mocked HTTP transport (``pytest-httpx``) — no live tenant
required, and no CLI involvement.
"""

from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from secai.client import SecAIClient
from secai.exceptions import NotFoundError
from secai.models import ActivityMapReport


def _client() -> SecAIClient:
    return SecAIClient(tenant_url="https://tenant.example.com", token="test-token")


class TestGetActivityMap:
    def test_returns_report_with_default_format(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/files/activity-map",
            json={
                "downloadUrl": "https://example-bucket.s3.amazonaws.com/activity-map.html",
                "dateRange": {"start": "2024-01-01", "end": "2024-01-31"},
            },
        )

        report = _client().reports.get_activity_map()

        assert isinstance(report, ActivityMapReport)
        assert report.download_url == "https://example-bucket.s3.amazonaws.com/activity-map.html"
        assert report.date_range is not None
        assert report.date_range.start == "2024-01-01"
        assert report.date_range.end == "2024-01-31"

    def test_passes_through_json_format(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/files/activity-map?format=json",
            json={
                "downloadUrl": "https://example-bucket.s3.amazonaws.com/activity-map.json",
                "dateRange": None,
            },
        )

        report = _client().reports.get_activity_map(format="json")

        assert report.download_url == "https://example-bucket.s3.amazonaws.com/activity-map.json"
        assert report.date_range is None

    def test_passes_through_html_format(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/files/activity-map?format=html",
            json={"downloadUrl": "https://example-bucket.s3.amazonaws.com/activity-map.html"},
        )

        report = _client().reports.get_activity_map(format="html")

        assert report.download_url == "https://example-bucket.s3.amazonaws.com/activity-map.html"

    def test_not_found_raises_not_found_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/files/activity-map",
            status_code=404,
            json={"message": "No activity map available for this tenant"},
        )

        with pytest.raises(NotFoundError) as exc_info:
            _client().reports.get_activity_map()

        assert exc_info.value.status_code == 404
