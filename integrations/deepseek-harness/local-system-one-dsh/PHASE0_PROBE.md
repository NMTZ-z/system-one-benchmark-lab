# DeepSeek Harness Phase 0 Probe

Date: 2026-09-27

Decision: **PROBE_PASS**

The probe established a real, reversible integration seam for Local System One Search Gate without modifying DeepSeek Harness core or any Hermes provider/profile configuration.

## Environment

| Item | Frozen value |
|---|---|
| DSH tag | `dsh-v0.1.7-rc.2` |
| DSH version | `0.1.7-rc.2` |
| DSH commit | `477b4f420553e8a52c2fbccc464d7561b239c443` |
| Node | `v26.6.0` |
| package manager | `pnpm 11.7.0` |
| macOS | `27.0 (26A428)` |
| architecture | `arm64` |
| install | `pnpm install --frozen-lockfile` |
| build | `pnpm run build` |
| build result | PASS |

The upstream checkout and DSH home/profile were isolated under git-ignored probe storage and can be deleted as a unit.

## Provider

| Item | Result |
|---|---|
| provider | Nova |
| endpoint | verified from Hermes; public configuration uses `${NOVA_BASE_URL}` |
| auth | environment-provided credential; public configuration uses `${NOVA_API_KEY}` |
| model | `deepseek-v4-flash` |
| baseline request | PASS |
| streaming | PASS |
| local tools | PASS |
| native Web fetch | PASS at tool/network layer |
| native Web search | tool identity PASS; default backend unavailable without a separate `DEEPSEEK_API_KEY` |
| MCP Tavily search | PASS |

A real isolated headless request returned the required baseline response through DSH -> Nova -> DeepSeek V4.1 Flash. Session facts recorded provider `nova` and model `deepseek-v4-flash`.

No credential value was written to the repository, report, fixture, DSH patch, or probe log.

### Search capability note

DSH's default native `web_search` provider uses its own DeepSeek search credential and did not inherit the Nova chat credential. The environment did not contain `DEEPSEEK_API_KEY`, so a native `web_search` call reached the tool and failed at the search-provider credential boundary.

A separate real MCP path was therefore tested with the existing Tavily credential through DSH's official MCP client. The package was pinned to the npm-published `tavily-mcp@0.2.22`. The model successfully executed real public-Web searches.

## Lifecycle

### agent/pre-step

Observed on a real DeepSeek V4.1 Flash tool turn:

```text
turn 1 / step 1: messages = [user]
tool executes
turn 1 / step 2: messages = []
```

Therefore Search Gate must run only on `step === 1` for one decision per user intent.

### tools/pre-execute

Real model calls exposed these exact names:

```text
read
web_fetch
web_search
mcp__tavily__tavily_search
```

Observed argument-key shapes included:

```text
read -> file_path
web_fetch -> url
web_search -> queries
mcp__tavily__tavily_search -> query, max_results, optional include_domains
```

The frozen DSH contract supports `allow`, `deny`, `cancel`, and `ask` pre-tool decisions. Upstream tests verify that `{ kind: "deny", reason }` blocks execution.

Only verified public-Web names are eligible for Phase 1 Canary. Generic tools such as `bash` are deliberately outside the deny allowlist.

### session/event

Observed stable events include:

```text
turn/start
step/start
assistant/message
tool/call
tool/result
step/end
turn/end
```

`turn/start` arrives before the first `agent/pre-step`. The same session identity remains available through the pre-step and tool execution objects. `turn/end` therefore provides a deterministic cleanup point for turn-scoped decisions.

## Local System One runtime

The existing loopback runtime reported healthy service and healthy ANE state during the probe.

Real Search Gate calls confirmed all three audited hard no-Web categories:

```text
bounded_transform_task
local_file_or_repo
connected_app_data
```

A deliberately less explicit local README prompt fell through to `decision_source=model`. This is expected to remain Shadow-only and is useful evidence that the adapter must check authority fields rather than merely the final `no_search` label.

## Phase 1 adapter E2E

The built `dist/index.js` was loaded by the same frozen DSH checkout and exercised against Nova / DeepSeek V4.1 Flash.

| Case | Result | Evidence |
|---|---|---|
| Native baseline | PASS | DSH -> Nova -> `deepseek-v4-flash` returned the required response |
| OFF | PASS | turn succeeded; Local System One request counter delta was exactly `0` |
| Shadow | PASS | Search Gate request counter delta was exactly `1`; subsequent local `read` executed normally |
| Canary hard rule | PASS | `rule/local_file_or_repo` denied real `web_search`; local `read` in the same step succeeded |
| Model probability cannot deny | PASS | `model/ane` no-search decision allowed `web_search` through to DSH's native search backend |
| Service unavailable | PASS | unreachable Local System One endpoint failed open and the turn returned `FAILOPEN_OK` |
| Timeout | PASS | a local slow endpoint received the request, exceeded `timeout_ms=100`, and the turn still returned `TIMEOUT_OK` |
| Cross-turn leakage | PASS | turn 1 hard rule denied `web_search`; resumed turn 2 did not inherit it and reached the native search backend |

The native search backend in the model-authority and cross-turn checks then reported its own missing `DEEPSEEK_API_KEY`. That downstream error is useful evidence: the calls had already passed Local System One Canary rather than being denied by it.

The cross-turn test also covered an error-terminated first turn caused by an intermittent Nova 429 after the hard-rule tool decision. Resuming the same persisted session produced turn 2 and did not reuse the previous hard decision.

## Automated regression

- Local System One Python suite: `78 passed`.
- DSH adapter TypeScript suite: `14 passed`.
- Adapter TypeScript typecheck: PASS.
- Adapter build: PASS.
- Adapter npm audit after pinning Vitest `4.1.11`: 0 known vulnerabilities.
- Public release builder: PASS, 85-file review bundle.
- Hermes integration tree: unchanged.

## Safety conclusions

- Adapter seam is native DSH plugin lifecycle, not a core fork.
- Search Gate is one call per user turn, not one call per tool-loop step.
- Tool enforcement occurs at `tools/pre-execute`, after exact tool identity is known.
- Model-probability decisions have zero Canary authority.
- Failure or timeout leaves the original tool execution path untouched.
- Turn-end cleanup prevents cross-turn decision leakage.
- Adapter state stores decision metadata only, never raw task/transcript content.
- Hermes configuration was read-only throughout the probe.

## Probe caveats

Nova rate limiting produced intermittent HTTP 429 responses during repeated probing. Those failures were treated as provider throttling and were not counted as successful requests.

One later Tavily query encountered a TLS disconnect after earlier Tavily searches in the same run had already completed successfully. The successful tool executions establish the MCP search path; the later transient failure is retained here rather than hidden.

## Decision

```text
PROBE_PASS
```

The exact DSH version is frozen, the real Nova/DeepSeek V4.1 Flash baseline works, lifecycle seams and tool identities are verified, a real MCP public-Web search path works, and the adapter can proceed without modifying DSH core or Hermes.
