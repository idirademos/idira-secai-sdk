"""CLI sub-commands for the Reports (activity map) resource."""

from __future__ import annotations

import json
import os
import sys
from typing import Optional

import typer
from rich.console import Console

from ..client import SecAIClient
from ..exceptions import SecAIError
from .auth import resolve_credentials

reports_app = typer.Typer(no_args_is_help=True)
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


# ---------------------------------------------------------------------------
# reports activity-map
# ---------------------------------------------------------------------------


@reports_app.command("activity-map")
def reports_activity_map(
    format: Optional[str] = typer.Option(None, "--format", "-f", help="Output file format: html (default) or json."),
    output: Optional[str] = typer.Option(None, "--output", "-o", envvar="SECAI_OUTPUT"),
) -> None:
    """Get a short-lived presigned download URL for the tenant's insights and activity map."""
    fmt = (output or _fmt()).lower()
    try:
        with _client() as client:
            report = client.reports.get_activity_map(format=format)
    except SecAIError as exc:
        _die(exc)
        return

    if fmt == "quiet":
        typer.echo(report.download_url or "")
        return

    if fmt == "json":
        from rich import print_json
        print_json(json.dumps(report.model_dump(by_alias=True), default=str))
        return

    console.print("[bold]Activity map report:[/bold]")
    console.print(f"  Download URL: {report.download_url}")
    if report.date_range:
        console.print(f"  Date range  : {report.date_range.start} to {report.date_range.end}")
    console.print("[dim]The download URL is short-lived — fetch it promptly.[/dim]")
