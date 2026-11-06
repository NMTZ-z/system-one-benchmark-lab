# Phase 8.4C — integration and RC2 qualification

The candidate depends on the still-open Draft PR #16 at `1a380eb0b26c527eae4174cc01720a72dc055ae2`. The component artifacts were built from the sanitized source at `d6c420d7a8c9bce7edc26eaa3770d5f09babad3b`. The later release-record commit changes only this report, the allowlists and the release manifest. Artifact names, versions, SHA-256 values and local-only availability are in [the release manifest](../release/v0.2.0-manifest.json); no formal release or remote artifact hosting is implied.

## What was verified

- **Legacy Hermes OFF:** The real Hermes 0.23.0 plugin loader exercised an old v0.9 session, candidate upgrade, reload, Shadow, OFF and uninstall in an isolated profile. The old loaded session continued observations until unloaded, so configured OFF alone remains `PENDING_RELOAD` / `UNKNOWN`. Registered v0.10 sessions were also tested with queued and in-flight observation fencing, repeated OFF and Runtime-down fallback. The earlier 8.4B plugin also used version 0.10.0 but lacks this authentication; install the exact RC2 source and reload existing sessions.
- **HTTP and MCP:** Loopback-only service, random private per-profile credentials, authenticated clients, single-connection listener identity verification, request size, inference concurrency, overload and timeouts were exercised. MCP discovery covered five Gates and health; calls were compared with HTTP results and Completion/Retry remained advisory. A real pinned Laya MLX decision ran through MCP, including from the installed candidate wheel.
- **DSH:** The installed 0.7.0 bundle was exercised with native SDK hooks at exactly `0.1.7-rc.2@477b4f420553e8a52c2fbccc464d7561b239c443` and `0.2.1-alpha.1@5badb15009ae1756c3afe0ae0cef1faafc290ccc`. Both retained default OFF, first Shadow Search-only, explicit five-Gate observations, native mock-provider request parity, Runtime-down fail-open and reversible uninstall. The main provider was a local mock. Existing running DSH sessions require reload or termination before OFF can be assumed effective.
- **Regression and packaging:** 286 selected Python tests passed. DSH typecheck, build and 68 Vitest tests passed. The product and separate research allowlists were sanitized; wheel, sdist, Hermes source and DSH bundle were compared to their source and checked for privacy patterns. Product wheel and sdist exclude H4D/H4E and research opportunity modules. The optional LaunchAgent credential setup and failure/cleanup paths were tested with mocked `launchctl`; no production LaunchAgent was exercised.
- **Security review:** An independent diff review of `7ce1fbf` reproduced a medium-severity local availability issue: unauthenticated persistent identity connections could hold all eight slots beyond the inactivity timeout. Commit `a8acf69` adds a 15-second total connection deadline and rejects a second identity challenge on the same connection; a focused slow-traffic regression verifies slots recover. Continued active local flooding can still produce overload responses. Independent follow-up review confirmed the fix and conservative LaunchAgent cleanup; sustained local connection flooding remains a documented overload risk.

## Limits and next phase

The validated Runtime environment was macOS 27.0.1 on Apple Silicon, Python 3.12.14, `laya-mlx` 0.2.0 and MLX 0.32.4. Hermes 0.23.0 used its Python 3.14.9 host. DSH used Node 26.6.0 and pnpm 11.7.0. The fixed model revision is `f9ab0b228f0fc0f14d873dbc99038f135c2da1b2`; its model file SHA-256 is recorded in the manifest.

No real remote provider was called. Optional ANE artifact provenance is not frozen. A cold, isolated Hermes tool root attempted to bootstrap its Python toolchain; the network policy blocked that attempt, and the qualified native runs reused an existing toolchain. The optional LaunchAgent now owns a dedicated credential and refuses to overwrite unknown existing installations; migration from an old unowned LaunchAgent needs review. The MCP wrapper uses offline dependency resolution and requires its dependency to be provisioned beforehand.

For 8.4D, review the two Draft PRs in dependency order, exercise the candidate with explicitly authorized real users and their own isolated profiles, verify any intended LaunchAgent deployment, and prepare catalog/DSH distribution and final publication decisions separately. No production Active or Canary permission is granted by this candidate.

## Files changed since PR #16

```text
M	README.md
M	docs/MCP_DEPLOYMENT.md
A	integrations/deepseek-harness/local-system-one-dsh/LICENSE
M	integrations/deepseek-harness/local-system-one-dsh/README.md
M	integrations/deepseek-harness/local-system-one-dsh/cordis.patch.yml
M	integrations/deepseek-harness/local-system-one-dsh/package-lock.json
M	integrations/deepseek-harness/local-system-one-dsh/package.json
M	integrations/deepseek-harness/local-system-one-dsh/src/client.ts
M	integrations/deepseek-harness/local-system-one-dsh/src/index.ts
M	integrations/deepseek-harness/local-system-one-dsh/src/policy.ts
A	integrations/deepseek-harness/local-system-one-dsh/src/transport.ts
M	integrations/deepseek-harness/local-system-one-dsh/tests/adapter.test.ts
M	integrations/deepseek-harness/local-system-one-dsh/tests/evidence.test.ts
M	integrations/deepseek-harness/local-system-one-dsh/tests/retry.test.ts
A	integrations/deepseek-harness/local-system-one-dsh/tests/security.test.ts
A	integrations/deepseek-harness/local-system-one-dsh/tests/setup.ts
M	integrations/hermes/local-system-one-hermes/README.md
M	integrations/hermes/local-system-one-hermes/__init__.py
M	local_system_one/cli.py
M	local_system_one/client.py
M	local_system_one/first_run.py
M	local_system_one/mcp_server.py
A	local_system_one/security.py
M	local_system_one/service.py
M	local_system_one/workflows/completion_gate.py
M	pyproject.toml
M	release/product-files.txt
M	release/public-files.txt
M	release/v0.2.0-manifest.json
M	scripts/install_hermes_system_one_plugin.sh
M	scripts/install_local_system_one_launchd.sh
A	scripts/local_system_one_launchd_credentials.py
M	scripts/local_system_one_status.sh
M	scripts/run_local_system_one_mcp.sh
M	scripts/set_hermes_system_one_mode.sh
M	scripts/uninstall_local_system_one_launchd.sh
A	tests/native_dsh_mock.mjs
M	tests/native_hermes_first_run.py
A	tests/native_hermes_legacy_migration.py
M	tests/native_hermes_mock_provider.py
A	tests/native_mlx_mcp.py
M	tests/test_completion_gate.py
M	tests/test_first_run.py
M	tests/test_hermes_system_one_plugin.py
A	tests/test_http_security.py
A	tests/test_launchd_credentials.py
A	tests/test_mcp_proxy.py
M	tests/test_retry_http.py
A	docs/PHASE8_4C_COMPLETION_REPORT.md
```
