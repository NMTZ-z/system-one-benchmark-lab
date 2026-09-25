# Hermes × Local System One — Shadow Feasibility & Rollback Report v0.1

Date: 2026-09-25
Status: Shadow feasibility PASS; Active control NOT approved

## 1. Question

Can Local System One become an automatic decision-control layer inside Hermes without requiring manual model switching, modifying Hermes core/SOUL, making Hermes depend on Local System One, risking existing production profiles, or preventing immediate rollback?

Initial answer: **yes for shadow integration, not yet for active routing**.

## 2. Current Hermes environment

- Hermes Agent: 0.21.4 (2026-09-21)
- local upstream revision: 6fa6df75
- isolated evaluation profile: systemoneeval
- evaluation model: gemini-3.8-flash-high
- messaging channels were NOT cloned
- explicit Local System One MCP was disabled in the evaluation profile so hook testing is isolated

No Hermes upgrade was required. The currently installed version already supports plugin hooks and middleware suitable for this experiment.

## 3. Safety architecture

Plugin: local-system-one-hermes v0.1.0

Only two modes exist:

### off

- registers no decision hook;
- makes no Local System One request;
- changes no Hermes request.

### shadow

- registers a pre_llm_call observer hook;
- reads Hermes' original user_message before memory/plugin sidecars are appended;
- sends only that task to local Search Gate and Model Tier Gate;
- records privacy-minimized recommendations;
- returns None to Hermes;
- injects no context;
- rewrites no LLM or tool request.

There is intentionally **no active mode** in v0.1. Unknown modes fail closed to OFF.

## 4. Integration bug discovered and fixed

The first implementation observed llm_request middleware and attempted to recover the task from provider messages.

Real Hermes testing showed:

- observed user content length hit the 4,000-character cap;
- Hermes runtime/plugin context had already been appended;
- Search Gate falsely matched current-language context;
- Model Tier saw a much more complex task than the user actually sent.

This integration point was rejected.

Hermes source inspection showed that pre_llm_call receives original_user_message before plugin context is appended. The plugin was changed to use pre_llm_call.

Retest on a 15-character sentinel prompt:

- recovered task length: 15;
- Search Gate: no_search, P(search)=0.2414;
- Model Tier: fast, difficulty=1.0259;
- Hermes final response remained BASELINE_OK.

## 5. Off-mode baseline

Hermes final response: BASELINE_OK

- Local System One request count: 5 -> 5
- request delta: 0
- no decision state created for the turn

Result: PASS.

## 6. Corrected shadow-mode test

Same sentinel prompt:

- Hermes final response: BASELINE_OK
- Local System One request count: 7 -> 9
- expected two gate calls occurred
- task chars: 15
- Search Gate: no_search
- P(search): 0.2414
- Model Tier: fast
- difficulty: 1.0259
- shadow decision latency: 125.134 ms

Result: PASS.

## 7. Fault injection: Local System One unavailable

The evaluation profile was temporarily pointed at an unused local port with a 100 ms timeout.

Hermes final response: FAILOPEN_OK

- healthy Local System One request count: 9 -> 9
- plugin recorded: URLError
- plugin-side failure handling: 2.343 ms
- Hermes failed: no

Healthy service settings were restored immediately.

Result: PASS.

## 8. Rollback tests

### Disable

- plugin disabled through Hermes plugin management
- Hermes response: DISABLE_OK
- Local System One request delta: 0
- Hermes failed: no

PASS.

### Remove

- plugin removed from the evaluation profile
- plugin directory confirmed deleted
- Hermes response: REMOVE_OK
- Local System One request delta: 0
- Hermes failed: no

PASS.

The plugin was then reinstalled in shadow mode successfully.

## 9. Existing-profile integrity

Before the test, SHA-256 fingerprints were recorded for the default, lili, sisi, susu, vivi, xixi and yaoyao config.yaml files.

After plugin development, fault injection, disable/remove and reinstall:

**all seven configuration hashes remained unchanged.**

No production profile configuration was modified.

## 10. Real Hermes shadow smoke

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

Interpretation: Search false-positive candidate. The current 0.40 no-search threshold is likely too conservative for some bounded transformation tasks when structured hints are unavailable.

### Complex multi-agent architecture

- Search: search
- P(search): 0.6546
- Model tier: strong
- difficulty: 2.1297
- shadow latency: about 0.28 s in the processed run

Interpretation: Model Tier direction is sensible. Search is debatable unless the caller explicitly requires current Hermes/project documentation, making this another false-positive candidate.

## 11. Current go/no-go

### Technical integration feasibility

PASS.

### Rollback / reversibility

PASS.

### Fail-open behavior

PASS for dead-service fault.

### Search Gate active control

**NO-GO today.**

Reason: false-positive behavior is already visible in tiny shadow samples. Active tool removal needs calibration on real Hermes tasks first.

### Model Tier active downgrade

**NO-GO today.**

Direction is promising, but task-description sensitivity has already been observed. Active downgrade should only follow paired fast-vs-baseline quality testing.

### Notification suppression

NOT YET WIRED TO THE HERMES OUTBOUND DELIVERY PATH.

Keep shadow-only until that delivery path is identified and tested.

## 12. Acceptance criteria before Canary

Reliability:

- at least 500 shadow turns;
- zero Hermes turn failures attributable to the plugin;
- fail-open success across dead service, timeout, invalid response and ANE-degraded cases;
- first-turn decision overhead p95 target <= 300 ms.

Search Gate:

- at least 200 labeled real Hermes tasks;
- false no-search rate <= 1% overall;
- zero false no-search on explicitly current/live/high-stakes tasks;
- false-search rate low enough to materially reduce unnecessary web calls, with an initial target <= 15% on clearly local/static tasks.

Model Tier Gate:

- paired baseline-vs-fast execution on a frozen real-task set;
- fast-tier redo/escalation rate < 5%;
- no material task-success degradation;
- >= 20% reduction in strong-model calls on eligible traffic;
- only low-risk, reversible tasks eligible for downgrade.

Rollback before any Canary:

- mode=off PASS;
- hermes plugins disable PASS;
- hermes plugins remove PASS;
- Hermes safe mode remains an independent emergency escape path.

## 13. Next experiment

Do not activate routing yet.

Next step is **real Hermes history replay + continued shadow observation**:

1. locally extract representative first-turn user tasks from Hermes session history;
2. keep raw content local and never commit it;
3. run Search/Model Tier recommendations;
4. derive labels from task requirements and actual Hermes behavior where possible;
5. manually review ambiguous cases;
6. freeze a privacy-safe Agent Decision Blind Set;
7. tune policy thresholds/rules;
8. only then implement Canary active mode.

## 14. Rollback commands

Safe mode switch:

    scripts/set_hermes_system_one_mode.sh <profile> off

Disable plugin:

    HERMES_HOME=~/.hermes/profiles/<profile> hermes plugins disable local-system-one-hermes

Full removal:

    scripts/uninstall_hermes_system_one_plugin.sh <profile>

Reinstall defaults to OFF:

    scripts/install_hermes_system_one_plugin.sh <profile>

## 15. Decision

Proceed with shadow/replay evaluation.

Do **not** enable active Search Gate, model downgrade, or notification suppression on production Hermes profiles yet.

The architecture is viable and reversible. The remaining question is decision quality on real Hermes workloads, not integration feasibility.
