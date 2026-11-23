# Changelog

All notable changes to this project are documented here. Versioning follows
[SemVer](https://semver.org/); since the package is pre-1.0, any `0.x` bump
may include breaking changes.

## Releasing a new version

1. Bump the `version` field in `pyproject.toml` — this is the **only** place the version number
   is written by hand. `secai.__version__` (and `secai-cli --version`) read it automatically at
   runtime via `importlib.metadata`, so nothing in `secai/` needs to change.
2. Regenerate the lockfile so it records the new version: `uv lock`.
3. Add a new entry at the top of this file describing what changed, following the existing
   entries' format (group by **Breaking changes** / new features / fixes as applicable).
4. Reinstall locally to pick up the new version in your dev environment: `pip install -e .` (or
   `uv sync`), then spot-check with `secai-cli --version`.
5. Commit `pyproject.toml`, `uv.lock`, and `CHANGELOG.md` together, then tag the release
   (e.g. `git tag v0.3.0 && git push --tags`).

## 0.2.1

- **Lint/type debt cleanup**: resolved all 385 pre-existing `ruff` findings (full rule set
  `E,F,I,UP,B,SIM`) and all 54 pre-existing `mypy --strict` errors that CI had been surfacing
  but not enforcing (see 0.2.0's CI workflow). No CLI/API behavior changes — this was internal
  code quality work:
  - Mechanically rewrote all `Optional[X]`/`Union[X, Y]` annotations to `X | None`/`X | Y`
    (272 + 2 occurrences).
  - Reflowed long `--help` strings and f-strings in the CLI modules to fit the 100-char limit.
  - Added `[tool.ruff.lint.flake8-bugbear] extend-immutable-calls = ["typer.Option",
    "typer.Argument"]` so Typer's required `param: T = typer.Option(...)` pattern no longer
    trips the `B008` mutable-default-argument check (ruff's own documented fix for this exact
    FastAPI/Typer pattern).
  - Fixed a `mypy`/pydantic interaction quirk where `Field(None, alias=...)` (positional
    default) was read as a *required* constructor argument by mypy's `dataclass_transform`
    inference, even though the field has a default; switched all 65 occurrences in
    `secai/models.py` to `Field(default=None, alias=...)`, which mypy infers correctly.
  - Added `assert ... is not None` right after the CLI's existing `_help_if_missing()` calls so
    mypy can see what was already true at runtime: once that check passes, the corresponding
    CLI arguments are guaranteed non-`None`.
  - Fixed two latent cosmetic-only type mismatches that happened to be runtime-safe already
    (via Pydantic's `populate_by_name`/string-enum coercion), now using the canonical
    alias/enum forms: `SearchAgentsRequest(pageSize=..., continuationToken=...)` instead of the
    snake_case kwargs, and `Condition(op=ConditionOp.IN)` instead of the raw string `"in"`.
  - Bumped `[tool.mypy] python_version` from the no-longer-supported `"3.9"` to `"3.10"`,
    matching the Python versions CI actually tests against.
- **CI tightened** (`.github/workflows/ci.yml`): `ruff check` now runs with the full configured
  rule set (no `--select`/`--extend-exclude` overrides) across all files, and the `mypy` job
  is blocking (`continue-on-error` removed) instead of informational.

## 0.2.0

**Breaking changes** — the SDK was rewritten to match a new version of the
underlying Secure AI API:

- `AgentsResource.list()` now returns a `ListAgentsResponse` (`agents`,
  `page_info`, `total_count`) instead of a bare `list[Agent]`, and supports
  `page_size`/`continuation_token` cursor pagination.
- `AgentsResource.edit()` now issues `PUT` instead of `PATCH`, and returns
  `Optional[Agent]` (`None` on an HTTP 204 no-op when the request matches the
  stored agent exactly).
- `AgentsResource.delete()`'s documented precondition state changed from
  `PENDING_CONFIGURATION` to `PENDING_CONNECTION`.
- Several request/response models were renamed, restructured, or replaced to
  match the new API schema (e.g. `RegisterMcpServerRequest` was split into
  `RegisterCustomMcpServerRequest`/`RegisterPredefinedMcpServerRequest`;
  `get_predefined_mcp_server()` now returns `PredefinedMcpTargetDetail`
  instead of `PredefinedMcpTarget`).
- New resources/models were added to cover new API surface: agent search
  (`AgentsResource.search()`) and summary (`AgentsResource.summary()`),
  authn descriptors, policies (`PoliciesResource`), and reports
  (`ReportsResource`).

**New since the rewrite:**

- `secai-cli login`/`logout`/`whoami` for interactive or service-account
  authentication, replacing manual `SECAI_TENANT_URL`/`SECAI_TOKEN` exports
  as the primary workflow (env vars still work and take precedence).
- Automatic retry with exponential backoff (honoring `Retry-After`) for
  `429`/`5xx` responses in `_BaseClient._request`.
- Automatic token refresh on `401` when the CLI cached a service-account
  login, so an expired token no longer requires re-running `login` manually.
- `iter_all()` / `iter_all_mcp_servers()` pagination-helper generators on
  `AgentsResource`, `TargetsResource`, and `PoliciesResource`.
- OS-keyring credential storage (`keyring` is now a required dependency):
  `login`/`logout`/`whoami` prefer the OS keychain/credential store and
  transparently fall back to the existing `0600` plaintext file when no
  keyring backend is usable (e.g. headless Linux), with opportunistic
  migration and a `SECAI_NO_KEYRING` opt-out.
- A GitHub Actions CI workflow (`.github/workflows/ci.yml`) running ruff and
  the offline test suite on every push/PR, plus an informational mypy job.

## 0.1.0

Initial internal release.
