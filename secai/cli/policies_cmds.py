"""CLI sub-commands for the Policies resource."""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ..client import SecAIClient
from ..exceptions import SecAIError
from ..models import (
    Condition,
    ConditionGroup,
    Owner,
    OwnerType,
    PolicyAccessType,
    PolicyInput,
    PolicyState,
    PolicyUpdate,
)
from .auth import resolve_credentials

policies_app = typer.Typer(no_args_is_help=True)
console = Console()
err_console = Console(stderr=True)


def _client() -> SecAIClient:
    tenant_url, token = resolve_credentials()
    return SecAIClient(
        tenant_url=tenant_url,
        token=token,
        timeout=float(os.environ.get("SECAI_TIMEOUT", "30")),
    )


def _fmt() -> str:
    return os.environ.get("SECAI_OUTPUT", "table").lower()


def _die(exc: SecAIError) -> None:
    err_console.print(f"[bold red]Error:[/bold red] {exc}")
    code = exc.status_code or 0
    sys.exit(1 if 400 <= code < 500 else 2)


def _parse_tags(raw: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in raw:
        if "=" in item:
            k, _, v = item.partition("=")
            result[k.strip()] = v.strip()
        else:
            result[item.strip()] = ""
    return result


def _parse_owners(owner_ids: list[str]) -> list[Owner]:
    return [Owner(id=oid, name=oid, type=OwnerType.USER) for oid in owner_ids]


def _in_group(key: str, values: list[str]) -> ConditionGroup:
    return ConditionGroup(conditions=[Condition(op="in", key=key, value=list(values))])


def _match_group(key: str, value: str) -> ConditionGroup:
    return ConditionGroup(conditions=[Condition(op="match", key=key, value=value)])


def _any_group() -> ConditionGroup:
    return ConditionGroup(conditions=[Condition(op="any")])


_POSITIONAL_ARGS = {"policy_id"}


def _help_if_missing(ctx: typer.Context, **named_values: object) -> None:
    missing = [n for n, v in named_values.items() if v is None]
    if not missing:
        return

    def _label(n: str) -> str:
        if n in _POSITIONAL_ARGS:
            return n.upper()
        return f"--{n.rstrip('_').replace('_', '-')}"

    labels = ", ".join(_label(n) for n in missing)
    err_console.print(f"[bold red]Missing required:[/bold red] {labels}\n")
    typer.echo(ctx.get_help())
    raise typer.Exit(1)


# ---------------------------------------------------------------------------
# policies list
# ---------------------------------------------------------------------------


@policies_app.command("list")
def policies_list(
    page_size: Optional[int] = typer.Option(None, "--page-size", help="Max policies per page (default 50)."),
    cursor: Optional[str] = typer.Option(None, "--cursor", help="Pagination cursor from a previous response."),
    output: Optional[str] = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """List access policies in the tenant."""
    fmt = (output or _fmt()).lower()
    try:
        with _client() as client:
            resp = client.policies.list(page_size=page_size, cursor=cursor)
    except SecAIError as exc:
        _die(exc)
        return

    policies = resp.policies

    if fmt == "quiet":
        for p in policies:
            typer.echo(p.id or "")
        return

    if fmt == "json":
        from rich import print_json
        print_json(json.dumps(resp.model_dump(by_alias=True), default=str))
        return

    _state_colors = {"ENABLED": "green", "DISABLED": "yellow"}
    table = Table(title=f"Access Policies ({len(policies)})", header_style="bold blue")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Name")
    table.add_column("Access Type")
    table.add_column("State")

    for p in policies:
        state = p.state.value if p.state else "—"
        color = _state_colors.get(state, "white")
        table.add_row(
            p.id or "—",
            p.name or "—",
            p.access_type.value if p.access_type else "—",
            f"[{color}]{state}[/{color}]",
        )
    console.print(table)
    if resp.next_cursor:
        console.print(f"[dim]Next cursor: {resp.next_cursor}[/dim]")


# ---------------------------------------------------------------------------
# policies create
# ---------------------------------------------------------------------------


@policies_app.command("create")
def policies_create(
    ctx: typer.Context,
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Policy name. [required]"),
    access_type: Optional[PolicyAccessType] = typer.Option(
        None, "--access-type", help="ON_BEHALF_OF or AUTONOMOUS. [required]"
    ),
    description: Optional[str] = typer.Option(None, "--description", "-d"),
    state: PolicyState = typer.Option(PolicyState.ENABLED, "--state", help="ENABLED or DISABLED."),
    agent_id: Optional[list[str]] = typer.Option(None, "--agent-id", help="Agent ID to grant (repeatable; 'any' group used if omitted)."),
    user_role_id: Optional[list[str]] = typer.Option(None, "--user-role-id", help="User roleId to grant (required for ON_BEHALF_OF; repeatable)."),
    resource_match: Optional[list[str]] = typer.Option(None, "--resource-match", help="Resource glob match, e.g. 'mcp:reporting:*' (repeatable). [required]"),
    tag: Optional[list[str]] = typer.Option(None, "--tag", help="TAG=VALUE (repeatable)."),
    owner_id: Optional[list[str]] = typer.Option(None, "--owner-id", help="Owner user ID (repeatable)."),
    output: Optional[str] = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """Create an access policy controlling which users/agents can run tools on MCP servers."""
    _help_if_missing(ctx, name=name, access_type=access_type, resource_match=resource_match)
    fmt = (output or _fmt()).lower()

    agent_groups = [_in_group("id", agent_id)] if agent_id else [_any_group()]
    user_groups = [_in_group("roleId", user_role_id)] if user_role_id else None
    resource_groups = [_match_group("id", pattern) for pattern in resource_match]

    try:
        req = PolicyInput(
            name=name,
            description=description,
            state=state,
            accessType=access_type,
            agent=agent_groups,
            user=user_groups,
            resources=resource_groups,
            tags=_parse_tags(tag) if tag else {},
            owners=_parse_owners(owner_id) if owner_id else [],
        )
    except ValueError as exc:
        err_console.print(f"[bold red]Invalid policy:[/bold red] {exc}")
        raise typer.Exit(1)

    try:
        with _client() as client:
            policy = client.policies.create(req)
    except SecAIError as exc:
        _die(exc)
        return

    if fmt == "quiet":
        typer.echo(policy.id or "")
        return

    if fmt == "json":
        from rich import print_json
        print_json(json.dumps(policy.model_dump(by_alias=True), default=str))
        return

    console.print(f"[bold green]Policy created:[/bold green] {policy.id}")
    console.print(f"  Name      : {policy.name}")
    console.print(f"  AccessType: {policy.access_type.value if policy.access_type else '—'}")
    console.print(f"  State     : {policy.state.value if policy.state else '—'}")


# ---------------------------------------------------------------------------
# policies update
# ---------------------------------------------------------------------------


@policies_app.command("update")
def policies_update(
    ctx: typer.Context,
    policy_id: Optional[str] = typer.Argument(None, help="Policy UUID. [required]"),
    name: Optional[str] = typer.Option(None, "--name", "-n"),
    description: Optional[str] = typer.Option(None, "--description", "-d"),
    state: Optional[PolicyState] = typer.Option(None, "--state"),
    agent_id: Optional[list[str]] = typer.Option(None, "--agent-id", help="Replace agent grant with these IDs (repeatable)."),
    user_role_id: Optional[list[str]] = typer.Option(None, "--user-role-id", help="Replace user grant with these roleIds (repeatable; ON_BEHALF_OF only)."),
    resource_match: Optional[list[str]] = typer.Option(None, "--resource-match", help="Replace resource grants with these glob matches (repeatable)."),
    tag: Optional[list[str]] = typer.Option(None, "--tag", help="TAG=VALUE (repeatable). Replaces all tags."),
    owner_id: Optional[list[str]] = typer.Option(None, "--owner-id", help="Owner user ID (repeatable). Replaces all owners."),
    output: Optional[str] = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """Update an access policy. All options are optional; omitted fields are left unchanged."""
    _help_if_missing(ctx, policy_id=policy_id)
    fmt = (output or _fmt()).lower()

    req = PolicyUpdate(
        name=name,
        description=description,
        state=state,
        agent=[_in_group("id", agent_id)] if agent_id else None,
        user=[_in_group("roleId", user_role_id)] if user_role_id else None,
        resources=[_match_group("id", p) for p in resource_match] if resource_match else None,
        tags=_parse_tags(tag) if tag else None,
        owners=_parse_owners(owner_id) if owner_id else None,
    )
    try:
        with _client() as client:
            policy = client.policies.update(policy_id, req)
    except SecAIError as exc:
        _die(exc)
        return

    if fmt == "quiet":
        typer.echo(policy.id or "")
        return

    from rich import print_json
    print_json(json.dumps(policy.model_dump(by_alias=True), default=str))


# ---------------------------------------------------------------------------
# policies get
# ---------------------------------------------------------------------------


@policies_app.command("get")
def policies_get(
    ctx: typer.Context,
    policy_id: Optional[str] = typer.Argument(None, help="Policy UUID. [required]"),
    output: Optional[str] = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """Get full details for a single access policy."""
    _help_if_missing(ctx, policy_id=policy_id)
    fmt = (output or _fmt()).lower()
    try:
        with _client() as client:
            policy = client.policies.get(policy_id)
    except SecAIError as exc:
        _die(exc)
        return

    if fmt == "quiet":
        typer.echo(policy.id or "")
        return

    from rich import print_json
    print_json(json.dumps(policy.model_dump(by_alias=True), default=str))


# ---------------------------------------------------------------------------
# policies delete
# ---------------------------------------------------------------------------


@policies_app.command("delete")
def policies_delete(
    ctx: typer.Context,
    policy_id: Optional[str] = typer.Argument(None, help="Policy UUID. [required]"),
    confirm: bool = typer.Option(False, "--confirm", help="Required to proceed with deletion."),
) -> None:
    """Delete an access policy (must be DISABLED first)."""
    _help_if_missing(ctx, policy_id=policy_id)
    if not confirm:
        err_console.print("[yellow]Pass --confirm to proceed with deletion.[/yellow]")
        raise typer.Exit(1)
    try:
        with _client() as client:
            client.policies.delete(policy_id)
    except SecAIError as exc:
        _die(exc)
        return
    console.print(f"[bold green]Policy deleted:[/bold green] {policy_id}")


# ---------------------------------------------------------------------------
# policies set-state
# ---------------------------------------------------------------------------


@policies_app.command("set-state")
def policies_set_state(
    ctx: typer.Context,
    policy_id: Optional[str] = typer.Argument(None, help="Policy UUID. [required]"),
    state: Optional[PolicyState] = typer.Argument(None, help="Target state: ENABLED or DISABLED. [required]"),
    output: Optional[str] = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """Enable or disable an access policy."""
    _help_if_missing(ctx, policy_id=policy_id, state=state)
    fmt = (output or _fmt()).lower()
    try:
        with _client() as client:
            result = client.policies.set_state(policy_id, state)
    except SecAIError as exc:
        _die(exc)
        return

    if fmt == "quiet":
        typer.echo(result.id or "")
        return

    if fmt == "json":
        from rich import print_json
        print_json(json.dumps(result.model_dump(by_alias=True), default=str))
        return

    console.print(f"[bold green]State updated:[/bold green] {result.id}  →  {result.state.value if result.state else state.value}")
