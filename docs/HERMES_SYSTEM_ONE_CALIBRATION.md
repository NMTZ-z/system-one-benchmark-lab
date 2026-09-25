# Hermes × Local System One — Calibration & Limited Canary v0.1

Date: 2026-09-25

Status:

- reversible Hermes integration: PASS
- Search hard-rule canary on isolated profile: PASS
- Search model-based active routing: NO-GO
- Model Tier hard-fast calibration: PROMISING, NOT ACTIVE
- production Hermes profiles: UNCHANGED

## 1. Why this phase exists

The first Shadow integration proved that Local System One can observe Hermes without
changing it and can fail open when the local decision service is unavailable.

This phase asks a harder question:

> Are the decisions good enough to control real Hermes behavior?

The answer is intentionally split by decision source. Deterministic, manually audited
rules are already useful for a narrow Canary. Model-probability routing is not yet
reliable enough for active control.

## 2. Search Gate semantics were corrected

The original Search Gate blurred two different questions:

1. Does the task require information outside the current prompt?
2. Does the task require the public Web?

For an Agent, these are not the same.

Examples that may require tools but not public Web:

- read a local file;
- inspect a Git diff;
- query Feishu/Lark;
- query Xiaohongshu through its connector;
- read a project database;
- inspect current session state.

The current gate is therefore effectively a **Public Web Gate** while retaining the
existing endpoint name for compatibility.

Public Web means generic/current Internet information such as:

- current weather;
- current public product facts;
- current prices/status;
- public Web research;
- official online documentation when explicitly requested.

Connected apps and local/private resources are not classified as public Web merely
because a tool call is needed.

## 3. Historical Hermes replay

A local replay harness was added for the seven Hermes profiles.

Population observed:

- 2,355 historical turns
- 165 turns with historical public/external lookup behavior under the original weak
  tool-use detector

A 200-turn deterministic sample was repeatedly replayed while Search policy semantics
were refined.

Raw user content remains under git-ignored private storage. Processed results contain
aggregate metrics only.

Historical tool behavior is explicitly treated as a **weak label**, not correctness
ground truth. Hermes itself may have searched unnecessarily or skipped a needed search.

### Weak-label progression

| Replay | TP | FN candidate | FP candidate | TN | Recall | Specificity |
|---|---:|---:|---:|---:|---:|---:|
| v2 | 97 | 3 | 97 | 3 | 0.97 | 0.03 |
| v3 | 47 | 53 | 31 | 69 | 0.47 | 0.69 |
| v4 | 67 | 33 | 64 | 36 | 0.67 | 0.36 |
| v5-clean | 86 | 14 | 56 | 44 | 0.86 | 0.44 |
| v6-fixed | 83 | 17 | 46 | 54 | 0.83 | 0.54 |
| v7-fixed | 84 | 16 | 47 | 53 | 0.84 | 0.53 |
| v8-fixed | 84 | 16 | 48 | 52 | 0.84 | 0.52 |

These numbers are useful for detecting policy swings, but they are not Search accuracy.

## 4. Why weak historical labels are insufficient

Manual review found many historical "lookup" turns where public Web access was not
actually required.

Examples:

- a Feishu task-board query;
- Xiaohongshu connector monitoring;
- a local Git review;
- local pipeline/config inspection.

Hermes may historically have used a generic Web tool during these tasks, but disabling
generic web_search/web_extract would not prevent the requested task from being
completed through its intended local/connected source.

Therefore active-routing approval cannot be based on historical tool-use agreement
alone.

## 5. Manual Public-Web gold set

A privacy-safe manual calibration set was created:

- 56 reviewed task IDs
- 27 genuinely require public Web
- 29 do not require public Web

Stored data includes only:

- hashed private_id;
- public_web_required boolean;
- rationale category.

Raw task text remains private and git-ignored.

Artifact:

results/processed/hermes-public-web-gold-v0.1.json

### Current v8 performance on the gold set

- TP: 21
- TN: 10
- FP: 19
- FN: 6
- accuracy: 55.4%
- recall: 77.8%
- specificity: 34.5%
- precision: 52.5%

This is not good enough for model-based active tool filtering.

## 6. Threshold sweep

Keeping deterministic rules fixed and rescoring only model decisions:

| Threshold | Recall | Specificity |
|---:|---:|---:|
| 0.20 | 1.000 | 0.276 |
| 0.30 | 1.000 | 0.310 |
| 0.35 | 0.963 | 0.345 |
| 0.40 | 0.778 | 0.345 |
| 0.45 | 0.741 | 0.517 |
| 0.65 | 0.333 | 0.897 |

There is no useful global probability threshold that simultaneously achieves the
desired safety recall and useful no-Web specificity.

Conclusion:

> Model-probability Search decisions remain Shadow-only.

## 7. Deterministic hard no-Web rules

The manually reviewed gold set contained eight hard no-Web decisions.

Result:

- 8/8 were true no-public-Web tasks
- 0 false hard no-Web decisions

Across the complete 200-turn replay:

- 49 hard no-Web decisions
- 12 unique exact task templates after deduplication

All 12 unique templates were manually reviewed.

The audited hard no-Web categories are:

- bounded_transform_task
- local_file_or_repo
- connected_app_data

These tasks may still use local tools or connectors. The Canary only removes generic
public Web tools.

## 8. Isolated Search Canary

Hermes plugin version: local-system-one-hermes v0.3.0

Canary is hard-blocked outside profile:

systemoneeval

The protection exists both:

- in plugin code;
- in the mode-control script.

For an eligible hard no-Web decision the middleware removes exactly:

- web_search
- web_extract

It deliberately preserves:

- read_file;
- terminal;
- browser_exec;
- MCP/connector tools;
- all other Hermes tools.

Only the first provider call of the turn is modified. Tool-loop follow-ups are left
unchanged.

### Real bounded-transform test

Hermes exposed 31 tools before middleware.

Decision:

- no_search
- bounded_transform_task
- rule backend

Middleware:

- candidate_found=true
- removed web_search
- removed web_extract
- retained the other 29 tools

Hermes completed the rewrite normally.

### Current-information control

Weather task:

- decision: search
- reason: live_public_fact
- candidate_found=false
- all 31 tools remained available

Hermes completed the weather task normally.

### Local-file Canary

Task read a local temporary file and returned the expected value.

Decision:

- no_search
- local_file_or_repo
- candidate_found=true

Middleware removed only web_search/web_extract.

The local file tool remained usable and the answer was correct.

### Connected-app Canary

A task explicitly framed as a connected-app/Feishu task was classified:

- no_search
- connected_app_data
- candidate_found=true

Again only web_search/web_extract were removed.

## 9. Canary fail-open

During Canary, Local System One was deliberately pointed at a dead local port.

Result:

- plugin recorded URLError
- candidate_found=false
- original 31 tools remained available
- Hermes completed the user task normally

The healthy service URL was restored immediately.

This demonstrates fail-open behavior on the actual request-mutation path, not only in
Shadow mode.

## 10. Canary implementation bug discovered

The first real Canary did not mutate any tools even though Shadow produced the expected
decision.

Root cause:

Hermes increments api_call_count before constructing the provider request. The first
real provider call is:

api_call_count = 1

not 0.

The plugin was corrected and regression-tested. Real Canary then removed the intended
tools successfully.

This is another reason production activation must be preceded by isolated Canary.

## 11. Model Tier calibration

Model Tier remains more difficult than Search hard rules.

A key sensitivity was reproduced:

A complex multi-Agent architecture task with task_type=planning scored approximately:

- 2.34 / strong

The same semantic task with an operational wrapper such as "do not call tools, only
return the plan" could fall below the 2.0 threshold and become fast.

Therefore the current 421M score is sensitive to execution-wrapper wording.

Conclusion:

> Model-based fast/strong routing remains Shadow-only.

## 12. Same-provider low/high bounded-task paired test

To determine whether a deterministic hard-fast path is worth pursuing, the same model
and provider were compared:

- provider: local-gemini
- model: gemini-3.8-flash-tiered
- effort: low vs high
- minimal Hermes toolset: clarify

Two clean runs produced seven objective paired tasks total.

Every low and high result satisfied the programmed task constraints:

- low: 7/7
- high: 7/7

Hermes turn latency was measured from the first user-message timestamp to the final
assistant-message timestamp in the isolated profile state database.

Combined result:

- low mean turn: 4.824 s
- high mean turn: 5.812 s
- low median turn: 4.351 s
- high median turn: 5.224 s
- low faster: 5/7 pairs
- high faster: 2/7 pairs
- median high/low latency ratio: 1.235×

Interpretation:

> On this small bounded-task calibration set, low preserved task success and showed a
> useful latency signal.

This is promising, but seven pairs are not enough to activate general Model Tier
downgrades.

Token accounting was not used for the decision because cache/input-token attribution
changed between otherwise comparable one-shot runs.

## 13. Current activation matrix

| Capability | Status |
|---|---|
| Hermes plugin off mode | PASS |
| Shadow mode | PASS |
| Dead-service fail-open | PASS |
| Disable/remove rollback | PASS |
| Search model-probability routing | NO-GO |
| Search hard no-Web isolated Canary | PASS |
| Search production activation | NOT APPROVED |
| Model Tier model-based routing | NO-GO |
| Model Tier bounded hard-fast hypothesis | PROMISING |
| Notification suppression | NOT WIRED / NO-GO |

## 14. Safety state after testing

After Canary and paired tests:

- systemoneeval was restored to Shadow
- Local System One service is healthy
- all seven production profile config hashes remain unchanged
- no production profile is allowed to enter Canary
- current Hermes plugin validator passes
- full project tests pass

## 15. Next step

### Search

Do not widen Search active behavior.

Continue collecting real Shadow decisions and expand the manual Public-Web gold set.

The only active experimentation allowed remains the isolated hard no-Web Canary.

### Model Tier

Before implementing a Model Tier Canary:

1. verify that the tiered/high path is behaviorally equivalent to the current
   production baseline model configuration;
2. expand the objective bounded-task paired set;
3. require zero task-success regressions on the hard-fast set;
4. require a repeatable latency or cost benefit;
5. restrict any first Canary to the isolated systemoneeval profile and deterministic
   hard-fast tasks.

### Production

Do not modify the seven production Hermes profiles yet.

The control-plane architecture is ready. The remaining work is calibration, not
plumbing.

## 16. Additional real Canary finding: partial decision failure

A later real local-Git Canary exposed a stricter fail-open edge case.

Observed sequence:

- Search Gate completed first and returned deterministic `local_file_or_repo -> no_search`;
- the subsequent Model Tier request exceeded the 500 ms plugin timeout;
- the combined recommendation object therefore had `ok=false` with `TimeoutError`;
- the first implementation still used the already-returned Search rule and removed
  `web_search` / `web_extract`.

Hermes itself completed the local Git task correctly, but this violated the intended
safety invariant:

> Any incomplete Local System One control decision must leave the original Hermes
> provider request unchanged.

The Canary condition was corrected to require the complete recommendation call to be
successful before any request mutation is permitted.

A dedicated regression test now covers this partial-failure case.

After the fix:

- full test suite: 51/51 PASS;
- Hermes plugin validator: PASS;
- bounded rewrite real Canary: PASS;
- local Git real Canary with complete decision: PASS;
- weather/current-information reverse control: PASS;
- evaluation profile returned to `shadow` after testing;
- all seven production profile config hashes remained unchanged.

This finding strengthens the case for isolated Canary before any production profile is
ever allowed to mutate requests.

## 17. Current Canary boundary

The Search Canary is deliberately a **direct public-Web tool exposure reduction**, not
a total network sandbox.

It removes only the directly advertised Hermes functions:

- `web_search`
- `web_extract`

It does not remove:

- `terminal`;
- `read_file` / `search_files`;
- `browser_exec`;
- MCP / connected-app tools;
- `execute_code`.

Hermes' `execute_code` sandbox can itself expose RPC-backed helper tools, including Web
helpers. Therefore the current Canary should not be described as an absolute no-network
guarantee.

This narrow behavior is intentional for the first Canary: it reduces direct Web-tool
exposure without disabling broad execution capabilities. A future strict no-public-Web
mode would need execution-path enforcement in addition to provider-request tool filtering.

## 18. Updated decision

Search:

- deterministic audited hard no-Web rule Canary: technically viable in isolated profile;
- model-probability Search routing: remain Shadow-only;
- production profile activation: not approved yet.

Model Tier:

- same-provider low/high bounded-task evidence is promising;
- seven pairs are insufficient for production activation;
- next useful step is a larger frozen paired set plus an isolated hard-fast Canary,
  not general model-based routing.

The `systemoneeval` profile is currently back in `shadow` mode.

## 19. Model Tier hard-fast Canary v0.1

The first isolated Model Tier active experiment is now complete.

Hermes' real request wire was verified first using non-sensitive sentinel request dumps. On the tested local-gemini route, `gemini-3.8-flash-tiered` carries reasoning depth as the top-level `reasoning_effort` field.

The plugin v0.4.0 therefore permits a single-turn `high -> low` mutation only when all of the following are true:

- profile is `systemoneeval`;
- the complete Local System One recommendation succeeds;
- Model Tier returns a deterministic rule decision;
- reason is `bounded_transform` or `bounded_structured_transform`;
- request model is exactly `gemini-3.8-flash-tiered`;
- incoming request explicitly contains `reasoning_effort=high`;
- this is the first provider API call of the turn.

Real results:

- bounded rewrite: final wire `low`, completed normally;
- bounded structured transformation: final wire `low`, completed correctly;
- model-probability fast recommendation: final wire remained `high`;
- dead Local System One service: final wire remained `high`, Hermes completed normally.

The structured-transform test also demonstrated independent control planes: Model Tier downgraded reasoning while Search did not apply a hard-rule Web-tool filter.

Processed summary:

`results/processed/hermes-model-tier-canary-v0.1.json`

After testing, `systemoneeval` was returned to Shadow and all seven production-profile configuration hashes remained unchanged.

### Decision

The deterministic hard-fast path is technically viable in the isolated profile.

It is **not yet approved for production profiles**. The next evidence target is a larger frozen paired set of bounded real tasks, with zero quality regressions and a repeatable latency benefit.

## 20. Phase 6.1 — 32-pair hard-fast expansion

The same-provider Model Tier calibration was expanded from seven pairs to a corrected 32-pair frozen set.

Method:

- profile: `systemoneeval`
- Local System One Hermes plugin: `off` during low/high latency measurement
- provider/model: `local-gemini` / `gemini-3.8-flash-tiered`
- comparison: `reasoning_effort=low` vs `reasoning_effort=high`
- toolset: `clarify`
- seeded counterbalanced low/high order
- deterministic programmatic validators; no LLM judge
- categories: JSON construction, sort/deduplicate, date normalization, field extraction, CSV→JSON, key/value formatting, bounded summaries, constrained rewrites

The first rewrite prompts allowed optional alternatives, so their length validator rejected otherwise valid answers. Those four items were corrected to require exactly one output sentence and rerun; the ambiguous original rewrite runs are excluded from v1.1.

### Quality

- low: 32/32 PASS
- high: 32/32 PASS
- both pass: 32/32
- low-only failures: 0
- high-only failures: 0

On this bounded set, low preserved the tested objective constraints as reliably as high.

### Latency

Turn latency:

- low mean: 7.159 s
- high mean: 7.030 s
- low median: 6.326 s
- high median: 6.392 s
- low faster: 14/32 pairs
- high faster: 18/32 pairs
- mean paired delta (high - low): -0.050 s
- bootstrap 95% CI for mean paired delta: [-0.935 s, +0.813 s]

The larger sample does **not** reproduce a stable general latency advantage for low reasoning. The earlier seven-pair positive signal was too small to justify broad activation.

### Local System One control overhead

The exact two-gate control path used by the Hermes plugin was measured over the same 32 tasks for three repetitions each, for 96 combined Search + Model Tier decisions:

- 96/96 successful
- mean: 64.6 ms
- median: 56.9 ms
- P95: 112.5 ms
- P99: 117.3 ms
- max: 130.8 ms

Because the raw low/high latency delta is already inconclusive, adding control overhead cannot create a broad latency win.

### Exploratory category signals

Three categories showed positive mean high-minus-low deltas after subtracting mean control overhead:

- field extraction: about +1.32 s estimated net saving
- CSV→JSON: about +1.79 s estimated net saving
- sort/deduplicate: about +0.40 s estimated net saving

Each currently has only four pairs. These are exploration targets, not production claims. Several other categories favored high or showed no useful difference, including constrained rewrite, bounded summary, date normalization, generic JSON construction and formatting.

### Decision

**Broad hard-fast production Canary: NO-GO.**

The isolated `systemoneeval` Canary remains useful as an engineering reference and safety harness, but current evidence does not justify general `high -> low` routing on production Hermes profiles.

If optimization continues, expand only the three positive-signal categories before changing production policy.

Artifacts:

- `results/processed/hermes-model-tier-hard-fast-v1.1-tasks.json`
- `results/processed/hermes-model-tier-hard-fast-v1.1-summary.json`
- `results/processed/hermes-system-one-hard-fast-control-overhead-v0.1.json`

The evaluation profile was returned to `shadow` after measurement.


## 20. Phase 6.1 final paired-set result

The expanded hard-fast benchmark now contains 32 task pairs / 64 real Hermes calls with deterministic, programmatic scoring. After correcting a benchmark-design flaw in four constrained-rewrite prompts, final quality was:

- low: 32/32 PASS;
- high: 32/32 PASS.

Across all 32 pairs, latency did not show a reliable low-effort advantage. The 24 pairs actually eligible for the current hard-fast deterministic allowlist showed a weak positive signal after control overhead:

- 24/24 quality parity;
- low faster 13/24, high faster 11/24;
- raw mean high-minus-low +0.212 s;
- mean control overhead 65.6 ms;
- estimated net mean advantage +0.146 s for controlled-low;
- bootstrap 95% CI -1.027 s to +1.245 s.

Therefore production-default hard-fast routing remains NO-GO. The isolated Canary mechanism stays useful for experimentation, but its value on local-gemini is currently architectural/reversible rather than a proven latency optimization.

Artifacts:

- `docs/HERMES_MODEL_TIER_PAIRED_32.md`
- `results/processed/hermes-model-tier-hard-fast-v1.1-summary.json`
- `results/processed/hermes-model-tier-hard-fast-eligible-v1.1.json`
- `results/processed/hermes-system-one-hard-fast-control-overhead-v0.1.json`
