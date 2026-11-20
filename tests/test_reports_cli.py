"""Offline tests for the 'secai-cli reports' command group.

These tests invoke the CLI in-process and mock every HTTP response with
`pytest-httpx`'s `httpx_mock` fixture — no real tenant or network access is
required. For live-tenant smoke tests, see tests/live/test_reports_cli.py.
"""

from __future__ import annotations

import json

from .conftest import run_cli

_ACTIVITY_MAP_URL = "https://mock.secai.test/api/files/activity-map"
_ACTIVITY_MAP_BODY = {
    "downloadUrl": "https://example-bucket.s3.amazonaws.com/activity-map.html?sig=abc",
    "dateRange": {"from": "2024-01-01", "to": "2024-01-31"},
}


class TestReportsActivityMap:
    def test_activity_map_exits_zero(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=_ACTIVITY_MAP_URL, json=_ACTIVITY_MAP_BODY)
        result = run_cli("reports", "activity-map")
        assert result.returncode == 0

    def test_activity_map_json_is_valid(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=_ACTIVITY_MAP_URL, json=_ACTIVITY_MAP_BODY)
        result = run_cli("reports", "activity-map", "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "downloadUrl" in data

    def test_activity_map_quiet_outputs_url(self, httpx_mock) -> None:
        httpx_mock.add_response(method="GET", url=_ACTIVITY_MAP_URL, json=_ACTIVITY_MAP_BODY)
        result = run_cli("reports", "activity-map", "--output", "quiet")
        assert result.returncode == 0
        url = result.stdout.strip()
        assert url.startswith("http")

    def test_activity_map_json_format_option(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_ACTIVITY_MAP_URL}?format=json",
            json=_ACTIVITY_MAP_BODY,
        )
        result = run_cli("reports", "activity-map", "--format", "json", "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "downloadUrl" in data

    def test_activity_map_html_format_option(self, httpx_mock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_ACTIVITY_MAP_URL}?format=html",
            json=_ACTIVITY_MAP_BODY,
        )
        result = run_cli("reports", "activity-map", "--format", "html", "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "downloadUrl" in data
