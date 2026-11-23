"""CLI sub-commands for the Agents resource."""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from ..client import SecAIClient
from ..exceptions import SecAIError
from ..models import (
    AgentState,
    EditAgentRequest,
    Owner,
    OwnerType,
    RegisterAgentRequest,
    SearchAgentsRequest,
)
from .auth import build_token_refresher, resolve_credentials

agents_app = typer.Typer(no_args_is_help=True)
console = Console()
err_console = Console(stderr=True)


def _client() -> SecAIClient:
    tenant_url, token = resolve_credentials()
    return SecAIClient(
        tenant_url=tenant_url,
        token=token,
        timeout=float(os.environ.get("SECAI_TIMEOUT", "30")),
        max_retries=int(os.environ.get("SECAI_MAX_RETRIES", "3")),
        token_refresher=build_token_refresher(tenant_url) if tenant_url else None,
    )


def _fmt() -> str:
    return os.environ.get("SECAI_OUTPUT", "table").lower()


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


def _die(exc: SecAIError) -> None:
    err_console.print(f"[bold red]Error:[/bold red] {exc}")
    code = exc.status_code or 0
    sys.exit(1 if 400 <= code < 500 else 2)


_POSITIONAL_ARGS = {"agent_id", "server_id", "predefined_id", "state", "descriptor_id", "policy_id"}


def _help_if_missing(ctx: typer.Context, **named_values: object) -> None:
    """Print which required args are missing, then show command help and exit."""
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
# agents list
# ---------------------------------------------------------------------------


@agents_app.command("list")
def agents_list(
    page_size: int | None = typer.Option(None, "--page-size", help="Max agents per page (1-1000)."),
    continuation_token: str | None = typer.Option(
        None,
        "--continuation-token",
        help="Continuation token from a previous response's page_info.",
    ),
    output: str | None = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """List agents in the tenant (one page; use --continuation-token for more)."""
    fmt = (output or _fmt()).lower()
    try:
        with _client() as client:
            result = client.agents.list(page_size=page_size, continuation_token=continuation_token)
    except SecAIError as exc:
        _die(exc)
        return

    agents = result.agents

    if fmt == "quiet":
        for a in agents:
            typer.echo(a.id or "")
        return

    if fmt == "json":
        import json

        from rich import print_json

        print_json(json.dumps(result.model_dump(by_alias=True), default=str))
        return

    table = Table(title=f"Agents ({len(agents)})", show_header=True, header_style="bold blue")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Owner")
    table.add_column("State")
    table.add_column("Updated")

    _state_colors = {
        "ACTIVE": "green",
        "SUSPENDED": "yellow",
        "PENDING_CONNECTION": "cyan",
        "CONNECTION_ERROR": "red",
    }

    for a in agents:
        state = a.status.state.value if a.status else "—"
        color = _state_colors.get(state, "white")
        updated = str(a.updated_at.date()) if a.updated_at else "—"
        if a.owner:
            owner_display = a.owner
        elif a.owners:
            owner_display = ", ".join(o.name or o.id for o in a.owners)
        else:
            owner_display = "—"
        table.add_row(
            a.id or "—",
            a.name or "—",
            a.type or "—",
            owner_display,
            f"[{color}]{state}[/{color}]",
            updated,
        )
    console.print(table)
    if result.page_info and result.page_info.continuation_token:
        console.print(
            f"[dim]More results available — pass "
            f"--continuation-token {result.page_info.continuation_token} for the next page.[/dim]"
        )


# ---------------------------------------------------------------------------
# agents search
# ---------------------------------------------------------------------------


@agents_app.command("search")
def agents_search(
    filter: str = typer.Argument(
        ..., help='Filter expression, e.g. "type in [AWS_BEDROCK] and origin_id is null".'
    ),
    page_size: int | None = typer.Option(None, "--page-size", help="Max agents per page (1-1000)."),
    continuation_token: str | None = typer.Option(None, "--continuation-token"),
    output: str | None = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """Search agents by filter expression (fields: id, type, origin_id, spiffeId)."""
    fmt = (output or _fmt()).lower()
    req = SearchAgentsRequest(
        filter=filter, pageSize=page_size, continuationToken=continuation_token
    )
    try:
        with _client() as client:
            result = client.agents.search(req)
    except SecAIError as exc:
        _die(exc)
        return

    if fmt == "quiet":
        for a in result.agents:
            typer.echo(a.id or "")
        return

    from rich import print_json

    print_json(json.dumps(result.model_dump(by_alias=True), default=str))


# ---------------------------------------------------------------------------
# agents summary
# ---------------------------------------------------------------------------


@agents_app.command("summary")
def agents_summary(
    output: str | None = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """Show agent counts by type, by connection status, and SPIFFE/JWT counts."""
    try:
        with _client() as client:
            result = client.agents.summary()
    except SecAIError as exc:
        _die(exc)
        return

    if (output or _fmt()).lower() == "json":
        from rich import print_json

        print_json(json.dumps(result.model_dump(by_alias=True), default=str))
        return

    console.print(f"[bold]Total agents:[/bold] {result.types.total if result.types else '—'}")
    console.print(f"  SPIFFE agents: {result.spiffe_count}")
    console.print(f"  JWT agents   : {result.jwt_count}")
    if result.types:
        console.print("  By type:")
        for item in result.types.items:
            console.print(f"    {item.display_text or item.key}: {item.total}")
    if result.statuses:
        console.print("  By status:")
        for item in result.statuses.items:
            console.print(f"    {item.display_text or item.key}: {item.total}")


# ---------------------------------------------------------------------------
# agents authn-descriptors list / delete
# ---------------------------------------------------------------------------


@agents_app.command("list-authn-descriptors")
def agents_list_authn_descriptors(
    ctx: typer.Context,
    agent_id: str | None = typer.Argument(None, help="Agent UUID. [required]"),
    output: str | None = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """List all authentication descriptors registered for an agent."""
    _help_if_missing(ctx, agent_id=agent_id)
    assert agent_id is not None
    try:
        with _client() as client:
            descriptors = client.agents.list_authn_descriptors(agent_id)
    except SecAIError as exc:
        _die(exc)
        return

    if (output or _fmt()).lower() == "quiet":
        for d in descriptors:
            typer.echo(d.id)
        return

    from rich import print_json

    print_json(json.dumps([d.model_dump(by_alias=True) for d in descriptors], default=str))


@agents_app.command("delete-authn-descriptor")
def agents_delete_authn_descriptor(
    ctx: typer.Context,
    agent_id: str | None = typer.Argument(None, help="Agent UUID. [required]"),
    descriptor_id: str | None = typer.Argument(
        None, help="Authentication descriptor UUID. [required]"
    ),
    confirm: bool = typer.Option(False, "--confirm", help="Required to proceed with deletion."),
) -> None:
    """Remove an authentication descriptor from an agent."""
    _help_if_missing(ctx, agent_id=agent_id, descriptor_id=descriptor_id)
    assert agent_id is not None
    assert descriptor_id is not None
    if not confirm:
        err_console.print("[yellow]Pass --confirm to proceed with deletion.[/yellow]")
        raise typer.Exit(1)
    try:
        with _client() as client:
            client.agents.delete_authn_descriptor(agent_id, descriptor_id)
    except SecAIError as exc:
        _die(exc)
        return
    console.print(f"[bold green]Descriptor deleted:[/bold green] {descriptor_id}")


# ---------------------------------------------------------------------------
# agents register
# ---------------------------------------------------------------------------


@agents_app.command("register")
def agents_register(
    ctx: typer.Context,
    name: str | None = typer.Option(
        None, "--name", "-n", help="Agent name, unique, alphanumeric. [required]"
    ),
    type_: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help=(
            "Agent type (free-form, 2-256 chars), e.g. CLAUDE, COPILOT, "
            "AWS_BEDROCK, CUSTOM. [required]"
        ),
    ),
    description: str | None = typer.Option(None, "--description", "-d"),
    owner: str | None = typer.Option(None, "--owner"),
    callback_url: list[str] | None = typer.Option(
        None, "--callback-url", help="Redirect callback URL (repeatable, must start with https://)."
    ),
    tag: list[str] | None = typer.Option(None, "--tag", help="Tag as KEY=VALUE (repeatable)."),
    owner_id: list[str] | None = typer.Option(
        None, "--owner-id", help="Owner user ID (repeatable)."
    ),
    output: str | None = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """Register a new AI agent and print its credentials."""
    _help_if_missing(ctx, name=name, type_=type_)
    assert name is not None
    assert type_ is not None
    fmt = (output or _fmt()).lower()
    # Only pass fields that carry real values so Pydantic treats unset fields
    # as unset — model_dump(exclude_unset=True) then omits them from the payload,
    # preventing empty-collection schema-validation errors from the server.
    req_kwargs: dict[str, Any] = {"name": name, "type": type_}
    if description is not None:
        req_kwargs["description"] = description
    if owner is not None:
        req_kwargs["owner"] = owner
    if callback_url:
        req_kwargs["redirectCallbackUrls"] = callback_url
    if tag:
        req_kwargs["tags"] = _parse_tags(tag)
    if owner_id:
        req_kwargs["owners"] = _parse_owners(owner_id)
    req = RegisterAgentRequest(**req_kwargs)
    try:
        with _client() as client:
            agent = client.agents.register(req)
    except SecAIError as exc:
        _die(exc)
        return

    if fmt == "quiet":
        typer.echo(agent.id or "")
        return

    if fmt == "json":
        from rich import print_json

        print_json(json.dumps(agent.model_dump(by_alias=True), default=str))
        return

    console.print(f"[bold green]Agent registered:[/bold green] {agent.id}")
    console.print(f"  Name        : {agent.name}")
    console.print(f"  Type        : {agent.type}")
    console.print(f"  State       : {agent.status.state.value if agent.status else '—'}")
    if agent.credentials:
        console.print(f"  Client ID   : {agent.credentials.client_id}")
        console.print(
            f"  [bold red]Client Secret[/bold red]: {agent.credentials.client_secret}  "
            "[dim](store securely — shown once)[/dim]"
        )
        console.print(f"  Gateway URL : {agent.credentials.gateway_url}")


# ---------------------------------------------------------------------------
# agents get
# ---------------------------------------------------------------------------


@agents_app.command("get")
def agents_get(
    ctx: typer.Context,
    agent_id: str | None = typer.Argument(None, help="Agent UUID. [required]"),
    output: str | None = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """Get full details for a single agent."""
    _help_if_missing(ctx, agent_id=agent_id)
    assert agent_id is not None
    fmt = (output or _fmt()).lower()
    try:
        with _client() as client:
            agent = client.agents.get(agent_id)
    except SecAIError as exc:
        _die(exc)
        return

    if fmt == "quiet":
        typer.echo(agent.id or "")
        return

    if fmt == "json":
        from rich import print_json

        print_json(json.dumps(agent.model_dump(by_alias=True), default=str))
        return

    console.print(f"[bold]Agent:[/bold] {agent.id}")
    console.print(f"  Name       : {agent.name}")
    console.print(f"  Type       : {agent.type}")
    console.print(f"  Description: {agent.description or '—'}")
    console.print(f"  Owner      : {agent.owner or '—'}")
    console.print(f"  Client ID  : {agent.client_id or '—'}")
    state = agent.status.state.value if agent.status else "—"
    console.print(f"  State      : {state}")
    if agent.tags:
        console.print(f"  Tags       : {agent.tags}")
    console.print(f"  Created    : {agent.created_at} by {agent.created_by or '—'}")
    console.print(f"  Updated    : {agent.updated_at} by {agent.updated_by or '—'}")
    if agent.authn_descriptors:
        table = Table(
            title=f"Authn descriptors ({len(agent.authn_descriptors)})",
            show_header=True,
            header_style="bold blue",
        )
        table.add_column("ID", style="dim", no_wrap=True)
        table.add_column("Type")
        table.add_column("Sub-type")
        table.add_column("Service ID")
        table.add_column("Client ID")
        table.add_column("Data")
        for d in agent.authn_descriptors:
            table.add_row(
                d.id or "—",
                d.type or "—",
                d.sub_type or "—",
                d.service_id or "—",
                d.client_id or "—",
                json.dumps(d.data, default=str) if d.data else "—",
            )
        console.print(table)
    else:
        console.print("  Authn descriptors: —")


# ---------------------------------------------------------------------------
# agents edit
# ---------------------------------------------------------------------------


@agents_app.command("edit")
def agents_edit(
    ctx: typer.Context,
    agent_id: str | None = typer.Argument(None, help="Agent UUID. [required]"),
    name: str | None = typer.Option(None, "--name", "-n"),
    description: str | None = typer.Option(None, "--description", "-d"),
    owner: str | None = typer.Option(None, "--owner"),
    tag: list[str] | None = typer.Option(
        None, "--tag", help="TAG=VALUE (repeatable). Replaces all tags."
    ),
    output: str | None = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """Edit agent metadata (name, owner, description, tags)."""
    _help_if_missing(ctx, agent_id=agent_id)
    assert agent_id is not None
    fmt = (output or _fmt()).lower()
    req = EditAgentRequest(
        name=name,
        description=description,
        owner=owner,
        tags=_parse_tags(tag) if tag else None,
    )
    try:
        with _client() as client:
            agent = client.agents.edit(agent_id, req)
    except SecAIError as exc:
        _die(exc)
        return

    if agent is None:
        if fmt == "quiet":
            typer.echo(agent_id)
            return
        console.print(
            f"[dim]No changes: request matches the stored agent {agent_id}; "
            "nothing was written.[/dim]"
        )
        return

    if fmt == "quiet":
        typer.echo(agent.id or "")
        return

    if fmt == "json":
        from rich import print_json

        print_json(json.dumps(agent.model_dump(by_alias=True), default=str))
        return

    console.print(f"[bold green]Agent updated:[/bold green] {agent.id}")
    console.print(f"  Name : {agent.name}")
    console.print(f"  Owner: {agent.owner or '—'}")


# ---------------------------------------------------------------------------
# agents delete
# ---------------------------------------------------------------------------


@agents_app.command("delete")
def agents_delete(
    ctx: typer.Context,
    agent_id: str | None = typer.Argument(None, help="Agent UUID. [required]"),
    confirm: bool = typer.Option(False, "--confirm", help="Required to proceed with deletion."),
) -> None:
    """Permanently delete an agent (must be SUSPENDED first)."""
    _help_if_missing(ctx, agent_id=agent_id)
    assert agent_id is not None
    if not confirm:
        err_console.print("[yellow]Pass --confirm to proceed with deletion.[/yellow]")
        raise typer.Exit(1)
    try:
        with _client() as client:
            client.agents.delete(agent_id)
    except SecAIError as exc:
        _die(exc)
        return
    console.print(f"[bold green]Agent deleted:[/bold green] {agent_id}")


# ---------------------------------------------------------------------------
# agents set-state
# ---------------------------------------------------------------------------


@agents_app.command("set-state")
def agents_set_state(
    ctx: typer.Context,
    agent_id: str | None = typer.Argument(None, help="Agent UUID. [required]"),
    state: AgentState | None = typer.Argument(
        None, help="Target state: ACTIVE or SUSPENDED. [required]"
    ),
    output: str | None = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """Transition an agent between ACTIVE and SUSPENDED."""
    _help_if_missing(ctx, agent_id=agent_id, state=state)
    assert agent_id is not None
    assert state is not None
    fmt = (output or _fmt()).lower()
    try:
        with _client() as client:
            result = client.agents.set_state(agent_id, state)
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

    new_state = result.status.state.value if result.status else state.value
    console.print(f"[bold green]State updated:[/bold green] {result.id}  →  {new_state}")
