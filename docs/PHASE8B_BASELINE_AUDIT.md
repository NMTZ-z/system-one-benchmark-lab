# Phase 8B — Immutable Phase 8A Baseline Audit (2026-10-10)

Status: **REPRODUCED / NOT CALIBRATED / SHADOW ONLY**.

## Repository provenance

- NAS origin/main and starting working tree HEAD: `afa2512cc66400d111c28cb5fe00e9f83fdba49a`. NAS reachability verified with `git ls-remote origin`.
- Public GitHub main: `920caef1615ae08d76825b5b81ec32af5fc1e7ec`; PR #2 and #3 confirmed merged. These histories differ because the public release is sanitized/transplanted. Do not force-push.
- Starting main tree was clean apart from an unrelated untracked `uv.lock`; left untouched. Changes live in independent `feat/phase8b-completion-calibration` worktree.
- Hermes plugin manifest `0.8.0`, DSH adapter package `0.5.0`. Installed Hermes CLI `v0.21.6+153.g51609d8.dirty` (not the older v0.21.5 documented for 8A).
- Baseline corpus SHA256: `97ec6713b5d2ccf5b106902da7d27360e08cc8366798ca7f714cdeeb845507d4`.
- Original CompletionGate SHA256: `8e7e8720074a78b138dccfeba43e9830bf0e1af2f048111f81049d9a9562ad05`.
- Checkpoint model configuration `rl_agent_config.json` SHA256: `25061739243b617ad88d1219ba6f8a9c86c5881ca28df024fa2d9b3b2fcc30c6`.
- No original rules, choice instructions or safety threshold were modified before the replay.

## Independent reproduction of the *same historical* benchmark

The 120 historical cases were replayed with the current `CompletionGate` and the live, healthy generic `/v1/choice` backend, at the unchanged threshold `0.70`. This is historical reproducibility, **not** a fresh blind test.

| Source | n | Final accuracy | Macro F1 | Complete recall | Continue recall | Verify recall | Premature complete |
|---|---:|---:|---:|---:|---:|---:|---:|
| Public-outcome reconstructed (`real`) | 30 | 63.33% | 0.5308 | 0% | 90% | 100% | 0/20 |
| Synthetic | 90 | 63.33% | 0.5308 | 0% | 90% | 100% | 0/60 |

Both matrices reproduce 8A exactly. In all 120 cases, **56** were resolved by hard rules and **64** reached Laya. Of the 64 model calls, raw choices were `complete=40, verify=17, continue=7`; all 40 raw Complete choices were downgraded to Verify by the `0.70` threshold.

Across 40 labeled Complete model cases, raw `P(complete)` ranged from **0.4170 to 0.6184** (mean **0.575235**). Model-only old-corpus accuracy was **60/64 = 93.75%**; 4 Continue cases became Verify. A strictly *offline*, hard-rule-plus-raw-choice counterfactual is **116/120 = 96.67%**, with zero false Complete on this historical set. This is **not** a safe operating policy or prospective estimate.

The original 8A report did not preserve separate raw decision/probability fields; `phase8b_audit.py` captures them alongside deterministic rule, threshold and final outcome. Its output contains metadata and IDs only. Full input cases remain in their already-approved public corpus; private run output stays under ignored `private/phase8b`.

## Inference backend repeatability

Both model runs requested the same input, prompt/criteria, three labels and declared backend. 64/64 raw classifications and 120/120 final labels agreed.

| Measurement, model-only 64 calls | ANE | MLX |
|---|---:|---:|
| Observed backend | ANE 64 | MLX 64 |
| Wall P50 | 54.55 ms | 49.52 ms |
| Wall P95 | 57.31 ms | 62.30 ms |
| Wall mean | 57.10 ms | 53.77 ms |

Mean absolute backend difference in raw `P(complete)`: **0.000667**; maximum **0.0020**. These measurements include local HTTP/loopback and harness overhead; they are not GPU/ANE-only timings. The execution paths use different runtime implementations and numerical precision, so strict bitwise equivalence is **not established**. Power/energy costs were not measured.

The source checkpoint `rl_agent_config.json` ships a three-element temperature array `[1.0,1.0,1.0]`. Phase 8A warned of temperature clamping in inference; a complete causal diagnosis of the observed sub-0.70 scores remains **unproven**. Do not assume the checkpoint is probability-calibrated on Completion without a prospective reliability analysis.

## Risks and immediate verdict

- The thirty `real` cases are privacy-safe reconstructions from public engineering outcomes, **not** literal Hermes/DSH traces. The ninety synthetic cases have repeated patterns; source-separated scores being identical do not establish generalization.
- Of 80 non-complete historical cases there were zero false Completes. The one-sided exact 95% upper bound for their event rate is still approximately **3.68%** (`1 - 0.05^(1/80)`); for the 20 reconstructed real non-completes it is approximately **13.91%**. Zero is not safety proof.
- Raw model accuracy and the threshold conflict are meaningful diagnostics, **not** permission to relax the 0.70 threshold or terminate an Agent.
- End-of-turn Hermes `on_session_end` and DSH `turn/end` remain too late for Active stop control.
- Production config unchanged; no Active Completion enabled.

**8B-1 accepted as a baseline audit.** Model calibration, actual Agent E2E benefit, and Active readiness are not yet accepted.
