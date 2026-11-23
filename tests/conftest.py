"""Shared pytest fixtures/helpers for the SecAI SDK offline test suite.

These tests invoke ``secai-cli`` in-process via Typer's ``CliRunner`` and
mock every HTTP call with ``pytest-httpx``'s ``httpx_mock`` fixture, so no
real tenant, network access, or installed console script is required. They
run by default (``pytest`` / CI) and never touch a genuine SecAI tenant.

For tests that exercise the CLI against a real tenant (opt-in smoke tests,
excluded from the default run), see ``tests/live/``.
"""

from __future__ import annotations

from typer.testing import CliRunner

from secai.cli.main import app

# Dummy credentials used for every in-process CLI invocation below. Because
# resolve_credentials() prefers SECAI_TENANT_URL/SECAI_TOKEN over any cached
# login, these always take precedence and the real keyring/credentials cache
# on the machine running the tests is never read or written.
DEFAULT_ENV: dict[str, str] = {
    "SECAI_TENANT_URL": "https://mock.secai.test",
    "SECAI_TOKEN": "mock-token",
    "SECAI_NO_KEYRING": "1",
}

_runner = CliRunner()


class CliResult:
    """subprocess.CompletedProcess-like wrapper around a Typer CliRunner Result.

    Kept intentionally minimal so test assertions written against
    ``result.returncode`` / ``result.stdout`` / ``result.stderr`` behave the
    same whether the CLI was invoked in-process or as a subprocess.
    """

    def __init__(self, exit_code: int, stdout: str, stderr: str) -> None:
        self.returncode = exit_code
        self.stdout = stdout
        self.stderr = stderr


def run_cli(*args: str, check: bool = True, env: dict[str, str] | None = None) -> CliResult:
    """Invoke secai-cli in-process; combine with the `httpx_mock` fixture to stub responses."""
    merged_env = {**DEFAULT_ENV, **(env or {})}
    result = _runner.invoke(app, list(args), env=merged_env)
    cli_result = CliResult(result.exit_code, result.stdout, result.stderr)
    if check and cli_result.returncode != 0:
        raise AssertionError(
            f"CLI exited {cli_result.returncode}\n"
            f"stdout: {cli_result.stdout}\nstderr: {cli_result.stderr}"
        )
    return cli_result
