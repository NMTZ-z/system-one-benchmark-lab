# Search Gate v0.3 — Public Web Gate

Date: 2026-09-25
Status: calibrated Shadow + isolated hard-rule Canary

## Goal

Decide whether the **current agent task materially requires public Internet/Web information**.

The endpoint name remains `/v1/workflows/search-gate` for compatibility, but the semantics are deliberately narrower than the original v0.1 design.

The gate does **not** answer whether the task needs any tool. Local files, Git, databases, Feishu/Lark, Xiaohongshu MCP, project memory and other connected/private sources are not public Web.

## Why the semantics changed

Historical Hermes replay showed that "needs information outside the prompt" and "needs public Web" are very different questions.

Examples that may require tools but should normally be no-public-Web:

- inspect a local Git diff;
- read project files;
- query a Feishu task board;
- query Xiaohongshu through its connector;
- inspect current session/project state.

Treating all of these as Search caused severe over-searching.

## Decision policy

Search Gate v0.3 combines:

1. deterministic public-Web hard-search rules;
2. deterministic audited hard no-Web rules;
3. a 421M Noul fallback for ambiguous tasks;
4. bounded recent context only for reference resolution.

Recent context is background only. It must not trigger Search merely because an earlier turn contains words such as "today", "latest" or a current-event topic.

## Hard public-Web examples

- explicit public-Web / official online documentation research;
- current weather / forecast / live market-style facts;
- volatile public roles, price, availability or service status;
- explicit requests for public evidence, source URLs or cross-platform research.

Examples:

- 今天北京天气怎么样？
- OpenAI 的 CEO 是谁？
- 查验官方 API 文档中的当前参数说明。
- 扫描 GitHub Trending / Reddit / 官方发布并附来源链接。

## Audited hard no-Web categories

The current isolated Canary allowlist is intentionally small:

- `bounded_transform_task`
- `local_file_or_repo`
- `connected_app_data`

Examples:

- 润色这段已经提供的文字；
- review 当前本地 Git diff；
- 检查飞书任务板；
- 查看 Xiaohongshu MCP 返回的账号数据。

These decisions may still require local tools or connectors. They only mean generic public Web is unnecessary.

## Model fallback

Ambiguous tasks are converted to a Noul decision whose effective question is:

> Does the CURRENT USER TASK require PUBLIC INTERNET or WEB lookup for current/public facts?

The model is explicitly told:

- local files are not public Web;
- connected apps are not public Web;
- supplied context/conversation can satisfy a task without Web;
- background context exists only to resolve references such as "这个模型" / "继续" / "怎么样了".

The current probability threshold remains a research parameter. It is **not approved for active routing**.

## Real Hermes calibration

A deterministic 200-turn Hermes history sample was replayed repeatedly while semantics and rule precedence were corrected.

Historical tool use is only a weak label, because Hermes itself may have searched unnecessarily or skipped a needed search.

A privacy-safe manual gold set was therefore created:

- 56 reviewed task IDs;
- 27 genuine public-Web tasks;
- 29 genuine no-public-Web tasks;
- only hashed IDs + labels + rationale codes are stored;
- raw task text remains under git-ignored private storage.

Current v8 policy on the 56-task gold set:

- TP: 21
- TN: 10
- FP: 19
- FN: 6
- accuracy: 55.4%
- public-Web recall: 77.8%
- no-Web specificity: 34.5%

Conclusion: model-probability routing is not good enough for Active use.

## Threshold sweep

Holding deterministic rules fixed:

- threshold 0.30: recall 100%, specificity 31.0%
- threshold 0.35: recall 96.3%, specificity 34.5%
- threshold 0.40: recall 77.8%, specificity 34.5%
- threshold 0.45: recall 74.1%, specificity 51.7%
- threshold 0.65: recall 33.3%, specificity 89.7%

There is no useful single global threshold that simultaneously gives the required safety recall and useful no-Web specificity.

Therefore:

> **Model-based Search decisions remain Shadow-only.**

## Hard-rule evidence

On the manual gold set, audited hard no-Web decisions were:

- 8/8 correct;
- 0 false hard no-Web cases.

Across the full 200-turn replay:

- 49 hard no-Web decisions;
- 12 unique exact task templates after deduplication;
- all 12 templates manually reviewed as completable without generic public Web.

This evidence justified an isolated Canary for hard no-Web rules only.

## Hermes isolated Canary

Canary is hard-blocked outside the `systemoneeval` profile.

For eligible hard no-Web turns, Hermes middleware removes exactly the directly advertised functions:

- `web_search`
- `web_extract`

It deliberately preserves all other tools, including local tools and connectors.

Real tests:

- bounded rewrite -> Web functions removed; task completed normally;
- local Git branch lookup -> Web functions removed; local task completed normally;
- current Beijing weather -> candidate=false; no tool filtering; task completed normally.

After testing the evaluation profile was returned to `shadow` mode.

## Fail-open requirement

Any incomplete Local System One control decision must leave the original Hermes provider request unchanged.

A real Canary exposed an edge case:

- Search hard rule succeeded;
- Model Tier timed out;
- the combined recommendation was incomplete;
- the first implementation still filtered Web tools.

That behavior was rejected and fixed. Canary now requires the complete recommendation call to succeed before request mutation is allowed. A regression test covers the partial-failure case.

## Important Canary limitation

The current Canary is **direct public-Web tool exposure reduction**, not a total network sandbox.

It removes direct `web_search` / `web_extract` tool declarations. It does not remove `execute_code`, `terminal`, browser tooling or MCP/connectors. Some execution paths may still have indirect network capability.

A future strict no-public-Web mode would require enforcement on actual tool execution paths, not only request tool declarations.

## Privacy

The Local System One service does not persist raw task/context by default.

Hermes Shadow/Canary state stores decision metadata such as:

- turn/request IDs;
- route reason;
- probability/score;
- backend;
- latency;
- removed tool names.

Raw historical Hermes content used for replay remains local and git-ignored.

## Current decision

- Search hard-rule isolated Canary: technically viable.
- Search model-probability Active routing: NO-GO.
- Production Hermes profiles: unchanged and not approved for Canary.
- Continue Shadow collection and expand the manual gold set before widening any active behavior.

## Phase 6.2 update — 100-task manual gold set

The manual Public Web gold set was expanded from 56 to 100 real Hermes task IDs:

- 36 genuinely require public Web information;
- 64 do not;
- raw task text remains private and git-ignored.

Current v8 policy:

- recall: 83.3%;
- specificity: 37.5%;
- TP/TN/FP/FN: 30 / 24 / 40 / 6.

A threshold sweep again found no useful global threshold: threshold 0.30 reaches 100% recall but only 29.7% specificity, while threshold 0.65 reaches 87.5% specificity but only 36.1% recall.

The deterministic hard no-Web Canary allowlist hit 18/100 tasks and was correct on all 18, with zero manually labeled true-Web tasks blocked. It covers 28.1% of the 64 no-Web tasks in this gold set.

Decision remains:

- model-based Search routing: Shadow-only;
- hard no-Web isolated Canary: retain;
- production default: NO-GO pending more labeled/live evidence.

Full report: `docs/HERMES_PUBLIC_WEB_GOLD_100.md`.