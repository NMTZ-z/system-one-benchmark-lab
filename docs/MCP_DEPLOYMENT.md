# Local System One — MCP and macOS Deployment

Date: 2026-09-24

## Architecture

The persistent model service and MCP host integration are intentionally separate:

~~~text
AgentDock / Hermes / other MCP host
              |
              | stdio MCP
              v
  Local System One MCP proxy
              |
              | loopback HTTP
              v
  Local System One persistent service
      |                    |
      v                    v
     MLX                L512 ANE
~~~

The MCP proxy does not load the 421M model. This avoids duplicate model memory and repeated Core ML AOT compilation when multiple agent hosts connect.

## Persistent service

Manual launch:

~~~bash
scripts/run_local_system_one_service.sh
~~~

Defaults:

- source: the pinned `laya-typed-decisions` alias, unless the service wrapper finds the legacy local research checkout at `models/typed-decisions-source`;
- public ANE package path: `artifacts/models/typed421-body512-fp16/model.mlpackage`;
- an existing private-research package at `experiments/phase4a/typed421-body512-fp16/model.mlpackage` is still preferred by the service wrapper for backward compatibility;
- host: 127.0.0.1;
- port: 8787.

Build the public L512 ANE package locally with:

~~~bash
scripts/build_typed421_ane.sh
~~~

The builder pins both the `laya-coreml` source revision and the original Typed Decisions checkpoint revision.

Environment overrides:

- LOCAL_SYSTEM_ONE_SOURCE
- LOCAL_SYSTEM_ONE_ANE_PACKAGE
- LOCAL_SYSTEM_ONE_HOST
- LOCAL_SYSTEM_ONE_PORT
- LOCAL_SYSTEM_ONE_AUTH_TOKEN

If the ANE package is missing, the service starts in MLX-only fallback mode.

## launchd

Install for the current macOS user:

~~~bash
scripts/install_local_system_one_launchd.sh
~~~

The installer creates:

~~~text
~/Library/LaunchAgents/ai.localsystemone.service.plist
~~~

Logs:

~~~text
~/Library/Logs/LocalSystemOne/stdout.log
~/Library/Logs/LocalSystemOne/stderr.log
~~~

The service binds only to loopback by default.

Uninstall:

~~~bash
scripts/uninstall_local_system_one_launchd.sh
~~~

## MCP v2 proxy

The optional MCP server uses the official Python MCP SDK v2 and exposes:

- search_gate
- model_tier_gate
- notification_gate
- system_one_health

Run manually:

~~~bash
scripts/run_local_system_one_mcp.sh
~~~

The wrapper uses uv to provide the optional MCP dependency without adding it to the benchmark virtual environment.

Optional dependency specification:

~~~text
requirements-mcp.txt
~~~

The MCP proxy talks to:

~~~text
http://127.0.0.1:8787
~~~

by default. Override with LOCAL_SYSTEM_ONE_URL.

## Generic MCP host command

For a local stdio MCP host, configure the host to launch the absolute wrapper path:

~~~text
/absolute/path/to/local-system-one/scripts/run_local_system_one_mcp.sh
~~~

The wrapper changes to the repository itself before starting the MCP server, so the host does not need to inherit the user's shell working directory.

Do not point each host directly at the model runtime. The persistent HTTP service should own the models once.

## Verified MCP behavior

The official MCP v2 in-memory Client successfully:

- discovered all four tools;
- called search_gate against the real persistent 421M service;
- called model_tier_gate;
- called notification_gate;
- called system_one_health;
- received structured tool output for every call.

## Operational rule

MCP host failure should not affect the model service.

Model-service failure is surfaced through system_one_health and tool-call errors. The host can then fall back to its existing behavior.

The decision service is therefore an optimization/control layer, not a single point of failure for the agent ecosystem.

## Verified current deployment state

The Mac mini current-user launchd service is installed as:

```text
ai.localsystemone.service
```

Verified launchd state: running.

A real startup using the L512 ANE package produced:

- startup probe state: healthy;
- startup probe P50: 53.95 ms;
- health threshold: 125 ms;
- rolling P50 after the first real MCP-routed ANE decision: about 54.5 ms.

This contrasts with an earlier manual startup that produced 166.5 ms and was correctly marked degraded. The service therefore keeps the health gate enabled rather than assuming a package is always fast after it once passed.

Verified full path:

```text
official MCP v2 Client
  -> Local System One MCP proxy
  -> persistent launchd HTTP service
  -> token-length router
  -> L512 ANE
```

A 342-token planning task:

- was routed as ane_suitable;
- used backend ane;
- completed the decision call in 103.8 ms;
- returned model tier strong.

This validates the intended single-model-service / many-agent-host architecture.