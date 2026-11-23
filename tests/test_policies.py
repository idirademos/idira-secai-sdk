"""Unit tests for ``secai.policies.PoliciesResource``.

Like ``test_pagination.py`` and ``test_client_resilience.py``, these tests
exercise the resource directly through a real ``SecAIClient`` instance and
mock all HTTP with ``pytest-httpx`` — no live tenant or CLI involvement.

``client.policies.list()`` and ``client.policies.iter_all()`` are already
covered in ``test_pagination.py``; this file focuses on ``create``, ``get``,
``update``, ``delete``, and ``set_state``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError
from pytest_httpx import HTTPXMock

from secai.client import SecAIClient
from secai.exceptions import ConflictError, NotFoundError
from secai.models import (
    ConditionGroup,
    PolicyAccessType,
    PolicyInput,
    PolicyOutput,
    PolicyState,
    PolicyStateResponse,
    PolicyUpdate,
)

_FAKE_ID = "11111111-1111-1111-1111-111111111111"
_BASE = "https://tenant.example.com/api/policies"


def _client() -> SecAIClient:
    return SecAIClient(tenant_url="https://tenant.example.com", token="test-token")


def _policy_json(
    policy_id: str = _FAKE_ID,
    *,
    name: str = "test-policy",
    access_type: str = "AUTONOMOUS",
    state: str = "ENABLED",
    description: str | None = "a test policy",
    user: list[dict] | None = None,
    resources: list[dict] | None = None,
    tags: dict[str, str] | None = None,
) -> dict:
    return {
        "id": policy_id,
        "name": name,
        "description": description,
        "tags": tags or {},
        "owners": [],
        "state": state,
        "accessType": access_type,
        "agent": [{"conditions": [{"op": "any"}]}],
        "user": user,
        "resources": resources
        or [{"conditions": [{"op": "match", "key": "id", "value": "mcp:test:*"}]}],
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-01-01T00:00:00Z",
        "createdBy": "tester",
        "updatedBy": "tester",
    }


def _agent_any() -> list[ConditionGroup]:
    return [ConditionGroup.model_validate({"conditions": [{"op": "any"}]})]


def _resources_match() -> list[ConditionGroup]:
    return [
        ConditionGroup.model_validate(
            {"conditions": [{"op": "match", "key": "id", "value": "mcp:test:*"}]}
        )
    ]


# ---------------------------------------------------------------------------
# list() smoke test (full coverage lives in test_pagination.py)
# ---------------------------------------------------------------------------


class TestPoliciesList:
    def test_list_returns_policies(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(url=_BASE, json={"policies": [_policy_json()], "nextCursor": None})

        result = _client().policies.list()
        assert len(result.policies) == 1
        assert result.policies[0].id == _FAKE_ID
        assert result.next_cursor is None


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------


class TestPoliciesCreate:
    def test_create_autonomous(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="POST",
            url=_BASE,
            json=_policy_json(access_type="AUTONOMOUS", name="autonomous-policy"),
        )

        request = PolicyInput(
            name="autonomous-policy",
            description="a test policy",
            state=PolicyState.ENABLED,
            access_type=PolicyAccessType.AUTONOMOUS,
            agent=_agent_any(),
            resources=_resources_match(),
        )
        result = _client().policies.create(request)

        assert isinstance(result, PolicyOutput)
        assert result.id == _FAKE_ID
        assert result.name == "autonomous-policy"
        assert result.access_type == PolicyAccessType.AUTONOMOUS
        assert result.user is None

    def test_create_on_behalf_of_with_user(self, httpx_mock: HTTPXMock) -> None:
        user_group = [{"conditions": [{"op": "in", "key": "id", "value": ["user-1"]}]}]
        httpx_mock.add_response(
            method="POST",
            url=_BASE,
            json=_policy_json(
                access_type="ON_BEHALF_OF", name="obo-policy", user=user_group
            ),
        )

        request = PolicyInput(
            name="obo-policy",
            description="a test policy",
            state=PolicyState.ENABLED,
            access_type=PolicyAccessType.ON_BEHALF_OF,
            agent=_agent_any(),
            user=[
                ConditionGroup.model_validate(
                    {"conditions": [{"op": "in", "key": "id", "value": ["user-1"]}]}
                )
            ],
            resources=_resources_match(),
        )
        result = _client().policies.create(request)

        assert result.access_type == PolicyAccessType.ON_BEHALF_OF
        assert result.user == [
            ConditionGroup.model_validate(
                {"conditions": [{"op": "in", "key": "id", "value": ["user-1"]}]}
            )
        ]

    def test_on_behalf_of_without_user_raises_pydantic_validation_error(self) -> None:
        with pytest.raises(PydanticValidationError, match="user is required"):
            PolicyInput(
                name="obo-policy",
                state=PolicyState.ENABLED,
                access_type=PolicyAccessType.ON_BEHALF_OF,
                agent=_agent_any(),
                resources=_resources_match(),
            )

    def test_autonomous_with_user_raises_pydantic_validation_error(self) -> None:
        with pytest.raises(PydanticValidationError, match="must not be set"):
            PolicyInput(
                name="autonomous-policy",
                state=PolicyState.ENABLED,
                access_type=PolicyAccessType.AUTONOMOUS,
                agent=_agent_any(),
                user=[
                    ConditionGroup.model_validate(
                        {"conditions": [{"op": "in", "key": "id", "value": ["user-1"]}]}
                    )
                ],
                resources=_resources_match(),
            )


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------


class TestPoliciesGet:
    def test_get_returns_policy_output(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/{_FAKE_ID}",
            json=_policy_json(name="fetched-policy"),
        )

        result = _client().policies.get(_FAKE_ID)

        assert isinstance(result, PolicyOutput)
        assert result.id == _FAKE_ID
        assert result.name == "fetched-policy"
        assert result.state == PolicyState.ENABLED

    def test_get_not_found_raises_not_found_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="GET",
            url=f"{_BASE}/{_FAKE_ID}",
            status_code=404,
            json={"message": "policy not found"},
        )

        with pytest.raises(NotFoundError) as exc_info:
            _client().policies.get(_FAKE_ID)

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# update()
# ---------------------------------------------------------------------------


class TestPoliciesUpdate:
    def test_update_reflects_edited_fields(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="PUT",
            url=f"{_BASE}/{_FAKE_ID}",
            json=_policy_json(
                name="renamed-policy",
                description="updated description",
                tags={"env": "prod"},
            ),
        )

        request = PolicyUpdate(
            name="renamed-policy",
            description="updated description",
            tags={"env": "prod"},
        )
        result = _client().policies.update(_FAKE_ID, request)

        assert isinstance(result, PolicyOutput)
        assert result.name == "renamed-policy"
        assert result.description == "updated description"
        assert result.tags == {"env": "prod"}


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------


class TestPoliciesDelete:
    def test_delete_returns_none(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(method="DELETE", url=f"{_BASE}/{_FAKE_ID}", status_code=204)

        result = _client().policies.delete(_FAKE_ID)

        assert result is None

    def test_delete_conflict_raises_conflict_error(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="DELETE",
            url=f"{_BASE}/{_FAKE_ID}",
            status_code=409,
            json={"message": "policy must be DISABLED before deletion"},
        )

        with pytest.raises(ConflictError) as exc_info:
            _client().policies.delete(_FAKE_ID)

        assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# set_state()
# ---------------------------------------------------------------------------


class TestPoliciesSetState:
    def test_set_state_with_enum_value(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/{_FAKE_ID}/state",
            json={"id": _FAKE_ID, "state": "DISABLED"},
        )

        result = _client().policies.set_state(_FAKE_ID, PolicyState.DISABLED)

        assert isinstance(result, PolicyStateResponse)
        assert result.id == _FAKE_ID
        assert result.state == PolicyState.DISABLED

    def test_set_state_with_plain_string(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            method="POST",
            url=f"{_BASE}/{_FAKE_ID}/state",
            json={"id": _FAKE_ID, "state": "ENABLED"},
        )

        result = _client().policies.set_state(_FAKE_ID, "ENABLED")

        assert result.state == PolicyState.ENABLED
