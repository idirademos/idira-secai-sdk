"""Unit tests for the SDK-level ``iter_all*`` pagination helpers.

Like ``test_auth.py`` and ``test_client_resilience.py``, these tests run fully
offline against a mocked HTTP transport (``pytest-httpx``) — no live tenant
required.
"""

from __future__ import annotations

from typing import Any

from pytest_httpx import HTTPXMock

from secai.client import SecAIClient


def _client() -> SecAIClient:
    return SecAIClient(tenant_url="https://tenant.example.com", token="test-token")


class TestAgentsIterAll:
    def test_yields_items_across_multiple_pages(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents",
            json={
                "agents": [{"id": "a1"}, {"id": "a2"}],
                "pageInfo": {"continuationToken": "tok-1"},
            },
        )
        httpx_mock.add_response(
            url="https://tenant.example.com/api/agents?continuationToken=tok-1",
            json={"agents": [{"id": "a3"}], "pageInfo": {"continuationToken": None}},
        )

        client = _client()
        ids = [agent.id for agent in client.agents.iter_all()]
        assert ids == ["a1", "a2", "a3"]

    def test_stops_on_single_page(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            json={"agents": [{"id": "only"}], "pageInfo": None},
        )

        client = _client()
        ids = [agent.id for agent in client.agents.iter_all()]
        assert ids == ["only"]

    def test_stops_on_empty_first_page(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"agents": [], "pageInfo": None})

        client = _client()
        assert list(client.agents.iter_all()) == []

    def test_passes_through_page_size(self, httpx_mock: HTTPXMock) -> None:
        def callback(request: Any) -> Any:
            assert request.url.params["pageSize"] == "50"
            import httpx

            return httpx.Response(200, json={"agents": [], "pageInfo": None})

        httpx_mock.add_callback(callback)

        client = _client()
        list(client.agents.iter_all(page_size=50))

    def test_stops_if_token_repeats_without_new_items(self, httpx_mock: HTTPXMock) -> None:
        """A server bug returning an empty page with a token must not loop forever."""
        httpx_mock.add_response(
            json={"agents": [], "pageInfo": {"continuationToken": "tok-1"}},
        )

        client = _client()
        assert list(client.agents.iter_all()) == []


class TestTargetsIterAllMcpServers:
    def test_yields_items_across_multiple_pages(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/targets/mcp-servers",
            json={"mcpServers": [{"id": "s1"}], "nextCursor": "cur-1"},
        )
        httpx_mock.add_response(
            url="https://tenant.example.com/api/targets/mcp-servers?nextCursor=cur-1",
            json={"mcpServers": [{"id": "s2"}], "nextCursor": None},
        )

        client = _client()
        ids = [server.id for server in client.targets.iter_all_mcp_servers()]
        assert ids == ["s1", "s2"]

    def test_stops_on_empty_page(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"mcpServers": [], "nextCursor": None})

        client = _client()
        assert list(client.targets.iter_all_mcp_servers()) == []


class TestPoliciesIterAll:
    def test_yields_items_across_multiple_pages(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url="https://tenant.example.com/api/policies",
            json={"policies": [{"id": "p1"}], "nextCursor": "cur-1"},
        )
        httpx_mock.add_response(
            url="https://tenant.example.com/api/policies?cursor=cur-1",
            json={"policies": [{"id": "p2"}], "nextCursor": None},
        )

        client = _client()
        ids = [policy.id for policy in client.policies.iter_all()]
        assert ids == ["p1", "p2"]

    def test_stops_on_empty_page(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"policies": [], "nextCursor": None})

        client = _client()
        assert list(client.policies.iter_all()) == []
