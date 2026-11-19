"""PoliciesResource — methods for the /api/policies endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from .models import (
    ListPolicyOutput,
    PolicyInput,
    PolicyOutput,
    PolicyState,
    PolicyStateResponse,
    PolicyUpdate,
)

if TYPE_CHECKING:
    from .client import _BaseClient

_ACCEPT = "application/x.policies.beta+json"


class PoliciesResource:
    """Provides access to all access-policy API operations.

    Access policies control which users and AI agents can run tools on
    registered MCP servers; access is denied by default and allowed only
    when a policy explicitly permits it.
    """

    def __init__(self, transport: "_BaseClient") -> None:
        self._t = transport

    # ------------------------------------------------------------------
    # GET /api/policies
    # ------------------------------------------------------------------

    def list(
        self,
        *,
        page_size: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> ListPolicyOutput:
        """Return a page of access policies (cursor-paginated, 50 per page by default).

        Pass the ``next_cursor`` from a previous response as *cursor* to
        fetch the next page.
        """
        params: dict[str, Any] = {}
        if page_size is not None:
            params["pageSize"] = page_size
        if cursor:
            params["cursor"] = cursor
        body = self._t._request(
            "GET", "/api/policies", accept=_ACCEPT, params=params or None
        )
        return ListPolicyOutput.model_validate(body)

    # ------------------------------------------------------------------
    # POST /api/policies
    # ------------------------------------------------------------------

    def create(self, request: PolicyInput) -> PolicyOutput:
        """Create a new access policy.

        ``request.access_type`` determines whether ``user`` is required
        (``ON_BEHALF_OF``) or must be omitted (``AUTONOMOUS``).
        """
        body = self._t._request(
            "POST",
            "/api/policies",
            accept=_ACCEPT,
            json=request.model_dump(by_alias=True, exclude_unset=True, exclude_none=True),
        )
        return PolicyOutput.model_validate(body)

    # ------------------------------------------------------------------
    # GET /api/policies/{id}
    # ------------------------------------------------------------------

    def get(self, policy_id: str) -> PolicyOutput:
        """Retrieve the details of a single access policy."""
        body = self._t._request("GET", f"/api/policies/{policy_id}", accept=_ACCEPT)
        return PolicyOutput.model_validate(body)

    # ------------------------------------------------------------------
    # PUT /api/policies/{id}
    # ------------------------------------------------------------------

    def update(self, policy_id: str, request: PolicyUpdate) -> PolicyOutput:
        """Update an existing access policy.

        All fields are optional; omitted fields are left unchanged.
        ``accessType`` is fixed at creation and cannot be changed.
        """
        body = self._t._request(
            "PUT",
            f"/api/policies/{policy_id}",
            accept=_ACCEPT,
            json=request.model_dump(by_alias=True, exclude_unset=True, exclude_none=True),
        )
        return PolicyOutput.model_validate(body)

    # ------------------------------------------------------------------
    # DELETE /api/policies/{id}
    # ------------------------------------------------------------------

    def delete(self, policy_id: str) -> None:
        """Delete an access policy.

        The policy must be ``DISABLED`` first. Deleting a policy does not
        delete the associated agents, MCP servers, or user identities.
        """
        self._t._request("DELETE", f"/api/policies/{policy_id}", accept=_ACCEPT)

    # ------------------------------------------------------------------
    # POST /api/policies/{id}/state
    # ------------------------------------------------------------------

    def set_state(self, policy_id: str, state: PolicyState | str) -> PolicyStateResponse:
        """Enable or disable an access policy.

        Disabling stops policy enforcement immediately and denies requests
        that previously matched the policy until it is re-enabled.
        """
        payload: dict[str, Any] = {"state": PolicyState(state).value}
        body = self._t._request(
            "POST",
            f"/api/policies/{policy_id}/state",
            accept=_ACCEPT,
            json=payload,
        )
        return PolicyStateResponse.model_validate(body)
