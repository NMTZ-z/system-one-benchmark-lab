# Hermes × Local System One — Shadow Feasibility & Rollback Report v0.1

Date: 2026-09-25
Status: Shadow feasibility PASS; Active control NOT approved

## 1. Question

Can Local System One become an automatic decision-control layer inside Hermes without:

- requiring users to manually switch models;
- making Hermes depend on Local System One;
- modifying Hermes core source;
- modifying agent SOUL/personality files;
- risking the existing seven production profiles;
- preventing immediate rollback?

Initial answer: **yes for shadow integration, not yet for active routing**.

## 2. External architecture references

The approach is consistent with several first-party/public patterns:

- TypeSafe describes System One / Jev as typed probabilistic decisions that act like smart if-statements for classify/route/score/branch control flow.
- Laya provides a Router and a LangGraph conditional-routing integration with confidence fallback.
- Hermes middleware explicitly supports local policy, request shaping and adaptive routing before provider/tool execution.
- OpenAI Agents SDK supports conditional and dynamic tool exposure at runtime.
- A recent third-party Hermes PII-redaction proposal uses the same public middleware surfaces for local pre-provider policy.

This project combines those ideas with a persistent local 421M MLX/ANE runtime.

## 3. Current Hermes environment

- Hermes Agent: 0.21.4 (2026-09-21)
- upstream revision reported locally: 6fa6df75
- evaluation profile: systemoneeval
- evaluation model: gemini-3.8-flash-high
- profile created by cloning the default profile
- messaging channels were NOT cloned
- Local System One explicit MCP tool was disabled in the evaluation profile so middleware/hook evaluation is isolated

No Hermes upgrade was required. The current installed version already contains plugin register(ctx), pre_llm_call observer hooks, llm/tool request/execution middleware, profile-scoped plugin management, and fail-open middleware behavior.

The user authorized an upgrade if necessary, but adding a large upstream-version change during an integration safety test would add an unnecessary variable.

## 4. Safety architecture

Plugin: local-system-one-hermes v0.1.0

Only two modes exist.

### off

- registers no decision hook;
- makes no Local System One request;
- changes no Hermes request;
- creates no evaluation state during a turn.

### shadow

- registers pre_llm_call observer hook;
- reads Hermes' original user_message before memory/plugin sidecars are appended;
- sends only that task to local Search Gate and Model Tier Gate;
- records privacy-minimized recommendations;
- returns None to Hermes;
- injects no context;
- rewrites no LLM request;
- rewrites no tool request.

There is intentionally **no active mode** in v0.1. Any unknown requested mode fails closed to OFF.

## 5. Important integration bug discovered and fixed

The first implementation observed llm_request middleware and tried to recover the task from provider messages.

Real Hermes testing showed:

- recovered user content length: 4,000 characters (capped);
- the content already included Hermes runtime/plugin context;
- Search Gate falsely matched current-language context;
- Model Tier saw a much more complex task than the user actually sent.

This integration point was rejected.

Hermes source inspection showed that pre_llm_call receives original_user_message before plugin context is appended.

The plugin was changed to use pre_llm_call.

Retest:

- original sentinel task length: 15 characters;
- recovered length: 15;
- Search Gate: no_search, P(search)=0.2414;
- Model Tier: fast, difficulty=1.0259;
- Hermes final response remained BASELINE_OK.

This demonstrates why shadow integration is necessary before active control.

## 6. Off-mode baseline test

Hermes sentinel requested exact response BASELINE_OK.

Result:

- Hermes final response: BASELINE_OK
- Local System One request count: 5 -> 5
- delta: 0
- plugin decision state created during the turn: no

Result: PASS.

## 7. Corrected shadow-mode test

Same Hermes sentinel prompt.

Result:

- Hermes final response: BASELINE_OK
- Local System One request count: 7 -> 9
- expected two gate calls occurred
- task chars: 15
- Search Gate: no_search
- P(search): 0.2414
- Model Tier: fast
- difficulty score: 1.0259
- shadow decision latency: 125.134 ms

Result: PASS.

## 8. Fault injection: Local System One unavailable

Evaluation profile service URL was temporarily changed to an unused local port and timeout reduced to 100 ms.

Hermes sentinel requested exact response FAILOPEN_OK.

Result:

- Hermes final response: FAILOPEN_OK
- healthy Local System One request count: 9 -> 9
- plugin recorded: URLError
- plugin shadow latency: 2.343 ms
- Hermes failed: no

The healthy service URL/timeout were restored immediately.

Result: PASS.

## 9. Rollback tests

### Plugin disable

- plugin disabled using Hermes plugin management
- Hermes response: DISABLE_OK
- Local System One request count: 9 -> 9
- Hermes failed: no

PASS.

### Plugin remove

- plugin removed from the evaluation profile
- plugin directory confirmed deleted
- Hermes response: REMOVE_OK
- Local System One request count: 9 -> 9
- Hermes failed: no

PASS.

The plugin was then reinstalled in shadow mode successfully.

## 10. Existing-profile integrity

Before creating the evaluation profile, SHA-256 fingerprints were recorded for default, lili, sisi, susu, vivi, xixi and yaoyao.

After plugin development, fault injection, disable/remove and reinstall, **all seven config.yaml hashes remained unchanged**.

No production profile configuration was modified.

## 11. Real Hermes shadow smoke

Three ordinary Hermes tasks were executed through the isolated evaluation profile.

### Weather / current information

- Search: search
- reason: current language
- P(search): 1.0
- Model tier: fast
- difficulty: 0.7563
- shadow latency: 88.78 ms

Interpretation: expected behavior.

### Local rewrite

- Search: search
- reason: conservative uncertain search
- P(search): 0.4018
- Model tier: fast
- difficulty: 1.2268
- shadow latency: 252.782 ms

Interpretation: **Search false-positive candidate.** The 0.40 no-search threshold is probably too conservative for some bounded transformation tasks when the structured provided-only hint is unavailable.

### Complex multi-agent architecture

- Search: search
- P(search): 0.6546
- Model tier: strong
- difficulty: 2.1297
- shadow latency: roughly 0.28 s in the processed run

Interpretation:

- Model Tier direction is sensible.
- Search is debatable: the task can be answered from general engineering knowledge, so this is another false-positive candidate unless the caller requires current Hermes/project documentation.

## 12. Current go/no-go

### Technical integration feasibility

PASS.

### Rollback / reversibility

PASS.

### Fail-open behavior

PASS for dead-service fault.

### Search Gate active control

**NO-GO today.**

Reason: false-positive behavior is already visible in tiny shadow samples. More importantly, active tool removal must especially avoid false no-search; threshold/rules need calibration using real Hermes tasks.

### Model Tier active downgrade

**NO-GO today.**

The initial direction is promising, but task-description sensitivity was already observed. Active downgrade should only be allowed after paired fast-vs-baseline quality testing on real tasks.

### Notification suppression

NOT YET WIRED TO HERMES OUTBOUND DELIVERY.

Keep shadow-only until the outbound delivery path is identified and tested.

## 13. Acceptance criteria before Canary

### Reliability

- at least 500 shadow turns;
- zero Hermes turn failures attributable to the plugin;
- 100% fail-open success across dead service, timeout, invalid response and ANE-degraded cases;
- plugin p95 overhead target <= 300 ms for first-turn decision calls.

### Search Gate

Build a labeled set of at least 200 real Hermes tasks.

Primary safety metric:

- false no-search rate <= 1% overall;
- zero false no-search on explicitly current/live/high-stakes tasks.

Efficiency metric:

- false-search rate target <= 15% on clearly local/static tasks.

No active tool removal before these hold.

### Model Tier Gate

Use paired execution on a frozen real-task set:

- baseline model vs proposed fast-tier model;
- same task/context/tools;
- blind outcome review.

Canary threshold proposal:

- fast-tier redo/escalation rate < 5%;
- no material drop in task success;
- >= 20% reduction in strong-model calls on eligible traffic;
- only low-risk, reversible tasks eligible for downgrade.

### Rollback

Before any Canary:

- mode=off test PASS;
- hermes plugins disable PASS;
- hermes plugins remove PASS;
- Hermes safe mode remains available as an independent emergency escape path.

## 14. Next experiment

Do not activate routing yet.

Next step is **real Hermes history replay + continued shadow observation**:

1. locally extract representative first-turn user tasks from Hermes session history;
2. keep raw content local and do not commit it;
3. run Search/Model Tier recommendations;
4. derive labels from task requirements and actual Hermes tool behavior where possible;
5. manually review ambiguous cases;
6. freeze a privacy-safe Agent Decision Blind Set;
7. tune policy thresholds/rules;
8. only then implement a Canary active mode.

## 15. Rollback commands

Safe mode switch:

    scripts/set_hermes_system_one_mode.sh <profile> off

Disable plugin:

    HERMES_HOME=~/.hermes/profiles/<profile> hermes plugins disable local-system-one-hermes

Full removal:

    scripts/uninstall_hermes_system_one_plugin.sh <profile>

Reinstall defaults to OFF:

    scripts/install_hermes_system_one_plugin.sh <profile>

Local System One remains an optional optimization layer. Removing the Hermes plugin does not require changing Hermes core, agent SOUL, model config, or existing production profiles.

## 16. Decision

Proceed with shadow/replay evaluation.

Do **not** enable active Search Gate, model downgrade, or notification suppression on production Hermes profiles yet.

The architecture is viable and reversible; the remaining question is decision quality on real Hermes workloads, not integration feasibility.
