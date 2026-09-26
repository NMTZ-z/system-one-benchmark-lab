# Hermes Public Web Gold Set — 100 Tasks v0.2

Date: 2026-09-25
Status: Phase 6.2 calibration result

## Goal

Evaluate whether the Search Gate can safely decide when Hermes needs **public Internet/Web information**, rather than merely whether a task uses any external tool.

Public Web does not automatically include:

- local files / Git / NAS;
- Feishu/Lark task boards;
- Xiaohongshu MCP;
- supplied webpage context;
- existing conversation state;
- local scripts/pipelines.

## Gold set

The manually reviewed set was expanded from 56 to 100 real Hermes task IDs.

- public-Web required: 36
- no-public-Web required: 64
- raw task text: private + git-ignored
- committed artifact: hashed task ID + boolean label + rationale code only

The labels represent task requirements, not historical Hermes tool behavior.

## Current v8 Search policy on 100-task gold set

- TP: 30
- TN: 24
- FP: 40
- FN: 6
- accuracy: 54.0%
- public-Web recall: 83.3%
- no-Web specificity: 37.5%
- precision: 42.9%
- false no-Web rate among true Web tasks: 16.7%
- false Web rate among true no-Web tasks: 62.5%

Conclusion:

> Model-probability Search routing is not suitable for Active control.

## Threshold sweep

Holding deterministic rules fixed and changing only the model threshold:

| Threshold | Recall | Specificity | Accuracy |
|---:|---:|---:|---:|
| 0.30 | 100.0% | 29.7% | 55.0% |
| 0.35 | 97.2% | 35.9% | 58.0% |
| 0.40 | 83.3% | 37.5% | 54.0% |
| 0.45 | 80.6% | 45.3% | 58.0% |
| 0.50 | 72.2% | 50.0% | 58.0% |
| 0.60 | 38.9% | 75.0% | 62.0% |
| 0.65 | 36.1% | 87.5% | 69.0% |

There is no single threshold that provides both the desired safety recall and useful no-Web specificity.

## Error structure

At the current policy:

False positive Search decisions are dominated by model inference:

- `model_requires_external_information`: 25
- `model_uncertain_conservative_search`: 8

False no-Web decisions:

- `model_confident_local_answer`: 6

Hard-search rules also produced false positives in this gold set:

- `live_public_fact`: 4
- `explicit_public_web_instruction`: 2
- `volatile_public_fact`: 1

These hard-search false positives are inefficient but do not create the same safety risk as incorrectly removing Web capability.

## Hard no-Web Canary allowlist

The currently active experimental allowlist is intentionally narrow:

- `local_file_or_repo`
- `connected_app_data`
- `bounded_transform_task`

On the 100-task gold set:

- hard no-Web hits: 18
- correct no-Web labels: 18
- true-Web tasks incorrectly hard-blocked: 0
- hard no-Web precision: 100%
- coverage of all no-Web gold tasks: 18/64 = 28.1%
- coverage of the whole gold set: 18/100 = 18.0%

Interpretation:

> The rule-only path is low-coverage but currently clean on the reviewed set.

This supports keeping the isolated Canary implementation, but 18 successful rule hits are not enough evidence to make it a production default.

## Product decision

### Model Search routing

NO-GO for Active.

Keep model probabilities in Shadow only.

### Hard no-Web routing

- isolated `systemoneeval` Canary: PASS / retain;
- production profiles: NOT approved yet;
- current safety evidence: 18/18 correct hard no-Web decisions on 100-task manual gold set.

### Next evidence target

Before any production-profile Canary:

- expand manually reviewed public-Web gold set further toward 150–200 tasks;
- preserve zero known false hard no-Web decisions;
- collect live Shadow outcomes, not only historical replay;
- keep fail-open and one-command rollback tests green.

## Artifacts

- `results/processed/hermes-public-web-gold-v0.2.json`
- `results/processed/hermes-public-web-gold-eval-v0.2.json`
- `results/processed/hermes-public-web-threshold-sweep-v0.2.json`