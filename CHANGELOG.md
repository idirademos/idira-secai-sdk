# Changelog

All notable changes to this project are documented here. Versioning follows
[SemVer](https://semver.org/); since the package is pre-1.0, any `0.x` bump
may include breaking changes.

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
