"""Functional tests for the 'secai-cli reports' command group.

These tests invoke the CLI as a subprocess against a live tenant.
Set SECAI_TENANT_URL and SECAI_TOKEN (or add a .env.test file) before
running.

Run with:
    pytest tests/test_reports_cli.py -v
"""

from __future__ import annotations

import json

from .conftest import run_cli

# ---------------------------------------------------------------------------
# reports activity-map
# ---------------------------------------------------------------------------


class TestReportsActivityMap:
    def test_activity_map_exits_zero(self) -> None:
        result = run_cli("reports", "activity-map")
        assert result.returncode == 0

    def test_activity_map_json_is_valid(self) -> None:
        result = run_cli("reports", "activity-map", "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "downloadUrl" in data

    def test_activity_map_quiet_outputs_url(self) -> None:
        result = run_cli("reports", "activity-map", "--output", "quiet")
        assert result.returncode == 0
        url = result.stdout.strip()
        assert url.startswith("http")

    def test_activity_map_json_format_option(self) -> None:
        result = run_cli("reports", "activity-map", "--format", "json", "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "downloadUrl" in data

    def test_activity_map_html_format_option(self) -> None:
        result = run_cli("reports", "activity-map", "--format", "html", "--output", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "downloadUrl" in data
