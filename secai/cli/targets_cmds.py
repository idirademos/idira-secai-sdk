"""CLI sub-commands for the Targets resource."""

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
    ApiKeyEntry,
    AuthMethodUpdate,
    EditMcpServerRequest,
    McpAuthMethod,
    McpAuthType,
    McpCategory,
    McpSource,
    McpSourceType,
    McpState,
    McpUpstream,
    Owner,
    OwnerType,
    RegisterCustomMcpServerRequest,
    RegisterPredefinedMcpServerRequest,
    UpstreamHeader,
)
from .auth import build_token_refresher, resolve_credentials

targets_app = typer.Typer(no_args_is_help=True)
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


def _parse_headers(raw: list[str]) -> list[UpstreamHeader]:
    """Parse ``NAME=VALUE_TEMPLATE`` pairs, e.g. ``Authorization=Bearer {{apiKey}}``."""
    headers = []
    for item in raw:
        if "=" not in item:
            raise typer.BadParameter(f"Expected NAME=VALUE_TEMPLATE, got: {item}")
        name, _, value_template = item.partition("=")
        headers.append(UpstreamHeader(name=name.strip(), valueTemplate=value_template.strip()))
    return headers


def _die(exc: SecAIError) -> None:
    err_console.print(f"[bold red]Error:[/bold red] {exc}")
    code = exc.status_code or 0
    sys.exit(1 if 400 <= code < 500 else 2)


_POSITIONAL_ARGS = {"agent_id", "server_id", "predefined_id", "state"}


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
# targets list
# ---------------------------------------------------------------------------


@targets_app.command("list")
def targets_list(
    page_size: Optional[int] = typer.Option(None, "--page-size", help="Max items per page."),
    next_cursor: Optional[str] = typer.Option(None, "--next-cursor", help="Pagination cursor from a previous response."),
    output: Optional[str] = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """List all registered MCP servers."""
    fmt = (output or _fmt()).lower()
    try:
        with _client() as client:
            resp = client.targets.list_mcp_servers(page_size=page_size, next_cursor=next_cursor)
    except SecAIError as exc:
        _die(exc)
        return

    servers = resp.mcp_servers

    if fmt == "quiet":
        for s in servers:
            typer.echo(s.id or "")
        return

    if fmt == "json":
        from rich import print_json
        print_json(json.dumps(
            {"mcpServers": [s.model_dump(by_alias=True) for s in servers],
             "nextCursor": resp.next_cursor},
            default=str,
        ))
        return

    _state_colors = {"ENABLED": "green", "DISABLED": "yellow"}

    table = Table(title=f"MCP Servers ({len(servers)})", header_style="bold blue")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Name")
    table.add_column("Source")
    table.add_column("Category")
    table.add_column("Auth")
    table.add_column("State")

    for s in servers:
        state = s.state.value if s.state else "—"
        color = _state_colors.get(state, "white")
        src = s.source.type.value if s.source else "—"
        cat = s.category.value if s.category else "—"
        auth = s.auth_method.type.value if s.auth_method else "—"
        table.add_row(s.id or "—", s.name or "—", src, cat, auth, f"[{color}]{state}[/{color}]")

    console.print(table)
    if resp.next_cursor:
        console.print(f"[dim]Next cursor: {resp.next_cursor}[/dim]")


# ---------------------------------------------------------------------------
# targets register
# ---------------------------------------------------------------------------


@targets_app.command("register")
def targets_register(
    ctx: typer.Context,
    source: Optional[McpSourceType] = typer.Option(None, "--source", help="CUSTOM or PREDEFINED. [required]"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="MCP server name. [required for CUSTOM]"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="[required for CUSTOM]"),
    category: Optional[McpCategory] = typer.Option(None, "--category", "-c", help="Server category. [required for CUSTOM]"),
    url: Optional[str] = typer.Option(None, "--url", help="Upstream MCP server URL. [required for CUSTOM]"),
    auth_type: Optional[McpAuthType] = typer.Option(None, "--auth-type", help="OAUTH2.1, NONE, API_KEY, or PAT."),
    auth_server: Optional[str] = typer.Option(None, "--auth-server", help="Authorization server URL (OAUTH2.1)."),
    jwks: Optional[str] = typer.Option(None, "--jwks", help="JWKS URL for token validation (OAUTH2.1)."),
    client_id: Optional[str] = typer.Option(None, "--client-id", help="OAuth client ID (OAUTH2.1)."),
    client_secret: Optional[str] = typer.Option(None, "--client-secret", help="OAuth client secret (OAUTH2.1)."),
    auth_header: Optional[list[str]] = typer.Option(None, "--auth-header", help="Upstream header as NAME=VALUE_TEMPLATE (repeatable; API_KEY/PAT)."),
    api_key: Optional[list[str]] = typer.Option(None, "--api-key", help="API key value to store (repeatable, write-only; API_KEY)."),
    predefined_id: Optional[str] = typer.Option(None, "--predefined-id", help="Predefined template UUID. [required for PREDEFINED]"),
    predefined_version: Optional[int] = typer.Option(None, "--predefined-version", help="Template version (defaults to latest)."),
    tag: Optional[list[str]] = typer.Option(None, "--tag", help="TAG=VALUE (repeatable)."),
    owner_id: Optional[list[str]] = typer.Option(None, "--owner-id", help="Owner user ID (repeatable)."),
    output: Optional[str] = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """Register a custom or predefined MCP server target."""
    _help_if_missing(ctx, source=source)
    fmt = (output or _fmt()).lower()

    auth: Optional[McpAuthMethod] = None
    if auth_type:
        auth = McpAuthMethod(
            type=auth_type,
            authorizationServer=auth_server,
            JWKS=jwks,
            clientId=client_id,
            clientSecret=client_secret,
            headers=_parse_headers(auth_header) if auth_header else [],
            apiKeys=[ApiKeyEntry(apiKey=k) for k in api_key] if api_key else [],
        )

    try:
        if source == McpSourceType.CUSTOM:
            if not (name and description and category and url):
                _help_if_missing(ctx, name=name, description=description, category=category, url=url)
            req = RegisterCustomMcpServerRequest(
                name=name,
                description=description,
                category=category,
                upstream=McpUpstream(url=url),
                authMethod=auth,
                tags=_parse_tags(tag) if tag else {},
                owners=_parse_owners(owner_id) if owner_id else [],
            )
        else:
            if not predefined_id:
                _help_if_missing(ctx, predefined_id=predefined_id)
            req = RegisterPredefinedMcpServerRequest(
                source=McpSource(
                    type=McpSourceType.PREDEFINED,
                    predefinedTargetId=predefined_id,
                    predefinedTargetVersion=predefined_version,
                ),
                description=description,
                authMethod=auth,
                tags=_parse_tags(tag) if tag else {},
                owners=_parse_owners(owner_id) if owner_id else [],
            )
    except ValueError as exc:
        err_console.print(f"[bold red]Invalid request:[/bold red] {exc}")
        raise typer.Exit(1)

    try:
        with _client() as client:
            server = client.targets.register_mcp_server(req)
    except SecAIError as exc:
        _die(exc)
        return

    if fmt == "quiet":
        typer.echo(server.id or "")
        return

    if fmt == "json":
        from rich import print_json
        print_json(json.dumps(server.model_dump(by_alias=True), default=str))
        return

    console.print(f"[bold green]MCP server registered:[/bold green] {server.id}")
    console.print(f"  Name      : {server.name}")
    console.print(f"  Category  : {server.category.value if server.category else '—'}")
    console.print(f"  State     : {server.state.value if server.state else '—'}")
    console.print(f"  Gateway   : {server.gateway_url or '—'}")


# ---------------------------------------------------------------------------
# targets get
# ---------------------------------------------------------------------------


@targets_app.command("get")
def targets_get(
    ctx: typer.Context,
    server_id: Optional[str] = typer.Argument(None, help="MCP server ID. [required]"),
    output: Optional[str] = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """Get details of a registered MCP server."""
    _help_if_missing(ctx, server_id=server_id)
    fmt = (output or _fmt()).lower()
    try:
        with _client() as client:
            server = client.targets.get_mcp_server(server_id)
    except SecAIError as exc:
        _die(exc)
        return

    if fmt == "quiet":
        typer.echo(server.id or "")
        return

    if fmt == "json":
        from rich import print_json
        print_json(json.dumps(server.model_dump(by_alias=True), default=str))
        return

    console.print(f"[bold]MCP Server:[/bold] {server.id}")
    console.print(f"  Name       : {server.name}")
    console.print(f"  Description: {server.description or '—'}")
    console.print(f"  Source     : {server.source.type.value if server.source else '—'}")
    console.print(f"  Category   : {server.category.value if server.category else '—'}")
    console.print(f"  Upstream   : {server.upstream.url if server.upstream else '—'}")
    console.print(f"  Gateway    : {server.gateway_url or '—'}")
    console.print(f"  Callback   : {server.callback_url or '—'}")
    console.print(f"  Auth       : {server.auth_method.type.value if server.auth_method else '—'}")
    console.print(f"  State      : {server.state.value if server.state else '—'}")
    if server.tags:
        console.print(f"  Tags       : {server.tags}")


# ---------------------------------------------------------------------------
# targets edit
# ---------------------------------------------------------------------------


@targets_app.command("edit")
def targets_edit(
    ctx: typer.Context,
    server_id: Optional[str] = typer.Argument(None, help="MCP server ID. [required]"),
    description: Optional[str] = typer.Option(None, "--description", "-d"),
    category: Optional[McpCategory] = typer.Option(None, "--category", "-c", help="Custom targets only."),
    tag: Optional[list[str]] = typer.Option(None, "--tag", help="TAG=VALUE (repeatable). Replaces all tags."),
    owner_id: Optional[list[str]] = typer.Option(None, "--owner-id", help="Owner user ID (repeatable)."),
    auth_header: Optional[list[str]] = typer.Option(None, "--auth-header", help="Rotate upstream header as NAME=VALUE_TEMPLATE (repeatable; API_KEY/PAT targets only)."),
    api_key: Optional[list[str]] = typer.Option(None, "--api-key", help="Rotate API key value (repeatable, write-only; API_KEY targets only)."),
    output: Optional[str] = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """Edit MCP server metadata (description, owners, tags, category for custom, auth credentials for API_KEY/PAT)."""
    _help_if_missing(ctx, server_id=server_id)
    fmt = (output or _fmt()).lower()
    auth_update = None
    if auth_header or api_key:
        auth_update = AuthMethodUpdate(
            headers=_parse_headers(auth_header) if auth_header else None,
            apiKeys=[ApiKeyEntry(apiKey=k) for k in api_key] if api_key else None,
        )
    req = EditMcpServerRequest(
        description=description,
        category=category,
        tags=_parse_tags(tag) if tag else None,
        owners=_parse_owners(owner_id) if owner_id else None,
        authMethod=auth_update,
    )
    try:
        with _client() as client:
            server = client.targets.edit_mcp_server(server_id, req)
    except SecAIError as exc:
        _die(exc)
        return

    if fmt == "quiet":
        typer.echo(server.id or "")
        return

    if fmt == "json":
        from rich import print_json
        print_json(json.dumps(server.model_dump(by_alias=True), default=str))
        return

    console.print(f"[bold green]MCP server updated:[/bold green] {server.id}")
    console.print(f"  Description: {server.description or '—'}")
    if server.tags:
        console.print(f"  Tags: {server.tags}")


# ---------------------------------------------------------------------------
# targets delete
# ---------------------------------------------------------------------------


@targets_app.command("delete")
def targets_delete(
    ctx: typer.Context,
    server_id: Optional[str] = typer.Argument(None, help="MCP server ID. [required]"),
    confirm: bool = typer.Option(False, "--confirm", help="Required to proceed with deletion."),
) -> None:
    """Delete a custom MCP server (must be DISABLED first; predefined targets cannot be deleted)."""
    _help_if_missing(ctx, server_id=server_id)
    if not confirm:
        err_console.print("[yellow]Pass --confirm to proceed with deletion.[/yellow]")
        raise typer.Exit(1)
    try:
        with _client() as client:
            client.targets.delete_mcp_server(server_id)
    except SecAIError as exc:
        _die(exc)
        return
    console.print(f"[bold green]MCP server deleted:[/bold green] {server_id}")


# ---------------------------------------------------------------------------
# targets set-state
# ---------------------------------------------------------------------------


@targets_app.command("set-state")
def targets_set_state(
    ctx: typer.Context,
    server_id: Optional[str] = typer.Argument(None, help="MCP server ID. [required]"),
    state: Optional[McpState] = typer.Argument(None, help="Target state: ENABLED or DISABLED. [required]"),
    output: Optional[str] = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """Set the state of a registered MCP server to ENABLED or DISABLED."""
    _help_if_missing(ctx, server_id=server_id, state=state)
    fmt = (output or _fmt()).lower()
    try:
        with _client() as client:
            server = client.targets.set_mcp_server_state(server_id, state)
    except SecAIError as exc:
        _die(exc)
        return

    if fmt == "quiet":
        typer.echo(server.id or "")
        return

    if fmt == "json":
        from rich import print_json
        print_json(json.dumps(server.model_dump(by_alias=True), default=str))
        return

    new_state = server.state.value if server.state else state.value
    console.print(f"[bold green]State updated:[/bold green] {server.id}  →  {new_state}")


# ---------------------------------------------------------------------------
# targets list-predefined
# ---------------------------------------------------------------------------


@targets_app.command("list-predefined")
def targets_list_predefined(
    output: Optional[str] = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """List all predefined MCP server templates from the catalog."""
    fmt = (output or _fmt()).lower()
    try:
        with _client() as client:
            resp = client.targets.list_predefined_mcp_servers()
    except SecAIError as exc:
        _die(exc)
        return

    targets = resp.targets

    if fmt == "quiet":
        for t in targets:
            typer.echo(t.id or "")
        return

    if fmt == "json":
        from rich import print_json
        print_json(json.dumps(
            {"targets": [t.model_dump(by_alias=True) for t in targets]},
            default=str,
        ))
        return

    table = Table(title=f"Predefined MCP Servers ({len(targets)})", header_style="bold blue")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Name")
    table.add_column("Category")
    table.add_column("Auth")
    table.add_column("Version")

    for t in targets:
        cat = t.category.value if t.category else "—"
        auth = t.auth_method.type.value if t.auth_method else "—"
        table.add_row(t.id or "—", t.name or "—", cat, auth, str(t.predefined_target_version or "—"))

    console.print(table)


# ---------------------------------------------------------------------------
# targets get-predefined
# ---------------------------------------------------------------------------


@targets_app.command("get-predefined")
def targets_get_predefined(
    ctx: typer.Context,
    predefined_id: Optional[str] = typer.Argument(None, help="Predefined MCP server UUID. [required]"),
    output: Optional[str] = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """Get details of a specific predefined MCP server template, including its tools."""
    _help_if_missing(ctx, predefined_id=predefined_id)
    fmt = (output or _fmt()).lower()
    try:
        with _client() as client:
            tmpl = client.targets.get_predefined_mcp_server(predefined_id)
    except SecAIError as exc:
        _die(exc)
        return

    if fmt == "quiet":
        typer.echo(tmpl.id or "")
        return

    if fmt == "json":
        from rich import print_json
        print_json(json.dumps(tmpl.model_dump(by_alias=True), default=str))
        return

    console.print(f"[bold]Predefined Template:[/bold] {tmpl.id}")
    console.print(f"  Name       : {tmpl.name}")
    console.print(f"  Description: {tmpl.description or '—'}")
    console.print(f"  Category   : {tmpl.category.value if tmpl.category else '—'}")
    console.print(f"  Upstream   : {tmpl.upstream.url if tmpl.upstream else '—'}")
    console.print(f"  Auth       : {tmpl.auth_method.type.value if tmpl.auth_method else '—'}")
    console.print(f"  Version    : {tmpl.predefined_target_version or '—'}")
    console.print(f"  Callback   : {tmpl.callback_url or '—'}")
    if tmpl.tags:
        console.print(f"  Tags       : {tmpl.tags}")
    if tmpl.tools:
        console.print("  Tools:")
        for tool in tmpl.tools:
            console.print(f"    - {tool.name}: {tool.description}")
