"""CLI sub-commands for authenticating ``secai-cli`` against a tenant."""

from __future__ import annotations

import os
from typing import Optional

import typer
from httpx import HTTPError
from rich.console import Console

from ..client import SecAIClient
from ..exceptions import SecAIError
from .auth import (
    TokenFetchError,
    active_backend,
    clear_credentials,
    fetch_access_token,
    load_credentials,
    save_credentials,
)

console = Console()
err_console = Console(stderr=True)


def login(
    tenant_url: Optional[str] = typer.Option(
        None,
        "--tenant-url",
        help="Secure AI API tenant base URL, e.g. https://mytenant.aigw.cyberark.cloud "
        "(default: $SECAI_TENANT_URL)",
    ),
    token: Optional[str] = typer.Option(
        None,
        "--token",
        help="Bearer token, if you already have one. Skips the OAuth2 exchange below.",
    ),
    identity_url: Optional[str] = typer.Option(
        None,
        "--identity-url",
        help="CyberArk Identity API base URL, e.g. https://mytenant.cyberark.cloud/api/idadmin "
        "(default: $IDIRA_IDENTITY_URL)",
    ),
    client_id: Optional[str] = typer.Option(
        None,
        "--client-id",
        help="OAuth service account client ID (default: $IDIRA_ADMIN_USER)",
    ),
    client_secret: Optional[str] = typer.Option(
        None,
        "--client-secret",
        help="OAuth service account client secret (default: $IDIRA_ADMIN_PWD)",
    ),
) -> None:
    """Authenticate and cache credentials locally.

    Credentials are stored in the OS keyring when available (macOS Keychain,
    Windows Credential Locker, or a Linux Secret Service daemon), falling
    back to a 0600 plaintext file at ~/.config/secai/credentials.json
    otherwise — see `secai-cli whoami` for where they ended up.

    By default this exchanges a service account's client_id/client_secret for a
    bearer access token via OAuth2 client_credentials, so you never need to
    paste a raw JWT. Pass --token directly instead if you already have a
    bearer token from elsewhere.

    Once logged in, SECAI_TENANT_URL/SECAI_TOKEN no longer need to be set for
    every command. Explicit env vars, if present, still take precedence.
    """
    tenant_url = tenant_url or os.environ.get("SECAI_TENANT_URL")
    if not tenant_url:
        tenant_url = typer.prompt("Tenant URL")

    used_oauth = token is None

    if not token:
        identity_url = identity_url or os.environ.get("IDIRA_IDENTITY_URL")
        client_id = client_id or os.environ.get("IDIRA_ADMIN_USER")
        client_secret = client_secret or os.environ.get("IDIRA_ADMIN_PWD")

        if not identity_url:
            identity_url = typer.prompt(
                "Identity URL (e.g. https://mytenant.cyberark.cloud/api/idadmin)"
            )
        if not client_id:
            client_id = typer.prompt("Client ID")
        if not client_secret:
            client_secret = typer.prompt("Client secret", hide_input=True)

        try:
            token = fetch_access_token(identity_url, client_id, client_secret)
        except TokenFetchError as exc:
            err_console.print(f"[bold red]Login failed:[/bold red] {exc}")
            raise typer.Exit(code=1) from exc

    with SecAIClient(tenant_url=tenant_url, token=token, timeout=15.0) as client:
        try:
            client.agents.list(page_size=1)
        except SecAIError as exc:
            err_console.print(f"[bold red]Login failed:[/bold red] {exc}")
            raise typer.Exit(code=1) from exc
        except HTTPError as exc:
            err_console.print(
                f"[bold red]Login failed:[/bold red] could not reach {tenant_url} ({exc})."
            )
            raise typer.Exit(code=1) from exc

    if used_oauth:
        # Cache the service-account identity too, so an expired token can be
        # silently refreshed later without re-running `login` (see
        # auth.build_token_refresher).
        save_credentials(
            tenant_url,
            token,
            identity_url=identity_url,
            client_id=client_id,
            client_secret=client_secret,
        )
    else:
        save_credentials(tenant_url, token)
    console.print(f"[bold green]Logged in[/bold green] to {tenant_url}")
    console.print(f"Credentials stored via {active_backend()}")


def logout() -> None:
    """Remove cached credentials."""
    if clear_credentials():
        console.print("[bold green]Logged out.[/bold green] Cached credentials removed.")
    else:
        console.print("No cached credentials found.")


def whoami() -> None:
    """Show the currently cached tenant (does not make an API call)."""
    cached = load_credentials()
    if not cached:
        console.print(
            "Not logged in. Run [bold]secai-cli login[/bold] or set SECAI_TENANT_URL/SECAI_TOKEN."
        )
        raise typer.Exit(code=1)
    masked = cached["token"][:8] + "…" if len(cached["token"]) > 8 else "***"
    console.print(f"Tenant URL: {cached['tenant_url']}")
    console.print(f"Token:      {masked}")
    console.print(f"Source:     {active_backend()}")
    auto_refresh = "yes" if cached.get("client_id") else "no"
    console.print(f"Auto-refresh on expiry: {auto_refresh}")
