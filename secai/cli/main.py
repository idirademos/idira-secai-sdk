"""secai-cli — CyberArk Secure AI command-line interface."""

from __future__ import annotations

import json
import os
import shlex
import sys
from enum import Enum
from typing import Any

import typer
from dotenv import load_dotenv
from rich import print_json
from rich.console import Console

from ..exceptions import SecAIError

load_dotenv()

app = typer.Typer(
    name="secai-cli",
    help="CyberArk Secure AI API — agent and MCP server management.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

console = Console()
err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


class OutputFormat(str, Enum):
    table = "table"
    json = "json"
    quiet = "quiet"


def _output_fmt() -> OutputFormat:
    raw = os.environ.get("SECAI_OUTPUT", "table").lower()
    try:
        return OutputFormat(raw)
    except ValueError:
        return OutputFormat.table


def print_output(data: Any, *, fmt: OutputFormat | None = None, quiet_value: str = "") -> None:
    f = fmt or _output_fmt()
    if f == OutputFormat.quiet:
        if quiet_value:
            typer.echo(quiet_value)
        return
    if f == OutputFormat.json:
        print_json(json.dumps(data, default=str))
        return
    # table is handled per command


def handle_error(exc: SecAIError) -> None:
    err_console.print(f"[bold red]Error:[/bold red] {exc}")
    code = exc.status_code or 0
    sys.exit(1 if 400 <= code < 500 else 2)


# ---------------------------------------------------------------------------
# Sub-command groups
# ---------------------------------------------------------------------------

from .agents_cmds import agents_app  # noqa: E402
from .auth_cmds import login, logout, whoami  # noqa: E402
from .policies_cmds import policies_app  # noqa: E402
from .reports_cmds import reports_app  # noqa: E402
from .targets_cmds import targets_app  # noqa: E402

app.command("login")(login)
app.command("logout")(logout)
app.command("whoami")(whoami)
app.add_typer(agents_app, name="agents", help="Agent inventory and lifecycle management.")
app.add_typer(targets_app, name="targets", help="MCP server target registry management.")
app.add_typer(policies_app, name="policies", help="Access policy management.")
app.add_typer(reports_app, name="reports", help="Insights and activity map reporting.")


def _preprocess_argv() -> None:
    """Re-parse sys.argv with shlex when literal quote characters are present.

    Needed when the CLI is invoked from a non-shell context (e.g. a subprocess
    call without shell=True, an LLM tool runner, or a UI) where the shell never
    had a chance to strip the quotes.  For example:

        argv arrives as: ['--description', '"testing', 'SDK', 'CLI"']
        shlex reassembles: ['--description', 'testing SDK CLI']

    When no quote characters are present the function is a no-op, so normal
    shell invocations are unaffected.
    """
    args = sys.argv[1:]
    if any('"' in arg or "'" in arg for arg in args):
        try:
            sys.argv[1:] = shlex.split(" ".join(args))
        except ValueError:
            pass  # malformed quoting — leave argv alone and let Click report it


def main() -> None:
    """Installed entry point: pre-process argv then hand off to Typer."""
    _preprocess_argv()
    app()


if __name__ == "__main__":
    main()
