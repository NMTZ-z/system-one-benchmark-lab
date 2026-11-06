# Phase 8.3A — Real StepFun Hermes H2 Shadow pilot

**Executed 2026-10-21. H2 NATIVE TASK + SHADOW OBSERVATIONS:
PASS_SCOPED. H2 physical Provider lifecycle: COMPLETE; cost/usage
attribution PARTIAL. Phase 8.3A overall: BLOCKED by original H1
unfinalized physical request. No Active authority granted.**

## 1. Provenance: never merge code revisions into one claim

- Original H1 native OFF execution: clean frozen SHA
  82993477667817c8941caa429feea576d091a424.
- The H2 native Shadow trial executed exactly once on frozen clean SHA:
  0dc626ff86038702f74027b4a988d21f096f72d9.
- H2 protocol, immutable shared physical Provider ledger reader,
  real Hermes native runner, random test nonce and independent HTTP
  correlation requirements were committed **before the H2 paid/plan
  Provider traffic**.
- New H2 post-run report and independent verification code were added
  only **after the frozen execution**; their later commit is not
  presented as the model-tested runtime SHA.
- The Phase 8.3 Draft PR and public GitHub main stay separate.
  NAS main, production Hermes Profile/Gateway and production Runtime
  on 127.0.0.1:8787 were not altered.

## 2. True native Agent + local decision Runtime, no Mock

- Native Agent: official Hermes v0.22.1, using its dedicated test Home
  under ~/.hermes/system-one-phase83lab (not the default Hermes Home).
- Main model: genuine StepFun Step Plan step-5-preview; the only
  main Provider egress was the controlled local proxy 127.0.0.1:18794,
  forwarding the Plan endpoint, not the pay-as-you-go API.
- Local decision model: actual cached Laya Typed Decisions 421M via MLX
  revision f9ab0b228f0fc0f14d873dbc99038f135c2da1b2.
- Runtime and telemetry: separately started loopback ports 18782 and
  18793 with a private ephemeral HMAC correlation key.
- Plugin policy: Shadow-only Completion/Retry observers, no authority
  to change tasks, stop execution, retry operations, downgrade the
  model, approve payment, use Canary, or modify files.
- Task: exactly one native read_file of a disposable **new random
  hidden nonce**, which the Agent prompt did not contain. The
  original private file was not changed.
- After execution, all three dedicated test services stopped and the
  isolated Hermes Home was restored to OFF. Other Profiles were
  untouched; H3 and D1-D4 were not run in this round.

## 3. Independent native task adjudication

Hermes's native Agent returned exit code 0 with no task timeout,
after a measured 29.581 seconds of native execution. An independent
SQLite/native-tool/file verifier established:

- exact one native read_file tool call and matching native tool-result
  identifier;
- original private file bytes match the actual native tool response;
- the final Agent answer matches the original file;
- the random original nonce did not appear in the user task prompt;
- native Session closed successfully and reported the local capped
  main Provider route;
- original input remained byte-for-byte unchanged.

**Native H2 task result: PASS_SCOPED.** This is a read-only, isolated,
one-task proof. It does not validate more powerful operations, real
business tasks or broader failure modes.

## 4. StepFun Provider: complete H2 physical request lifecycle

H2 and H1 used the **same** durable Provider ledger and global
physical request cap. There was no budget reset.

| Metric | Previous H1 OFF | New H2 Shadow |
|---|---:|---:|
| Physical requests reserved and attempted | 3 | 3 |
| Provider HTTP responses confirmed 200 | 2 | **3** |
| Attempted requests with missing terminal record | **1** | **0** |
| Actual proxy result records | 2 | **3** |
| Agent-reported main-model logical calls | 2 | 2 |
| Physically unattributed requests | 1 | **1** |
| Independent native task | PASS_SCOPED | PASS_SCOPED |

**Global physical request slots used: 6/24.** Specifically, slots 1-3
are immutable H1 history; slots 4-6 belong to the new H2 task.
The original H1 first-ten-row SHA-256 is unchanged:

bded2cecb79bcf22a6cdb39a4186b99fb68e881651d18142de370e3b120133de

The independent per-H2 8.2B Budget Reconciler reports:

- 3 reserved/attempted, 3 real HTTP 200, 0 unresolved;
- budget_integrity = PARTIAL, **not** BLOCKED for this run;
- why PARTIAL: Provider-confirmed token/charge provenance is absent
  and 1 physical request is not attributed to Hermes's 2
  logical self-reported calls;
- 3 physical request costs are still UNKNOWN, even with three
  HTTP 200 responses;
- **H1 budget_integrity stays BLOCKED**, due to one historical
  reserved_without_proxy_result. There is no inferred response,
  refund or retroactively repaired slot.

Hermes separately self-reported 7,258 input tokens and 509 output
tokens for 2 main model calls. These are Agent-side summaries,
not independently verified Provider token or Step Plan credit records.

The revised H2 proxy remained alive for bounded closeout **after**
the native Agent exited; all H2 physical requests were finalized.
This supports the engineering correction in the new scoped run,
but does not prove that every possible transport fault is fixed,
nor identify the source of the third request.

## 5. Actual Laya MLX Shadow observations and exact causal links

The privacy-safe Runtime/HTTP collector observed **two** Completion
workflow requests, each with:

- HTTP 200 from the isolated real System One Runtime;
- decision_source=model and backend=mlx, not hard-rule or Mock;
- echoed request identity matched by the HTTP observer;
- HMAC native event-to-Adapter-to-HTTP correlation verified against
  the actual isolated Hermes SQLite records;
- no missing, duplicate or conflicting exact causal link.

Strictly verified native ↔ Adapter ↔ Runtime decisions: **2/2 PASS**.
This is actual local MLX inference during real StepFun Agent
execution, and it is **observation only**.

The native Agent's behaviour was not modified by any Completion
suggestion. No active stopping, automatic retry or escalation was
authorized or observed.

## 6. Measured one-off times and limits

H1 OFF Agent elapsed: 27.343 s.
H2 Shadow Agent elapsed: 29.581 s.

These are **one nonrandomized run per mode**, with different hidden
fixture values and potentially different main-model output lengths.
They cannot establish added runtime latency, equality of performance,
generalization or an economically meaningful time difference.
Do not compute a headline speedup from them.

No StepFun credit balance, confirmed bill, Provider-level token
accounting, real Agent token saving or charge reduction was measured.
A Shadow model cannot itself reduce the main Agent's token use
without a separately approved active, reversible policy experiment.

## 7. Release verdict and remaining acceptance gates

| Required decision | Verdict |
|---|---|
| H2 native successful read, independently verified | **PASS_SCOPED** |
| H2 local model invokes real MLX | **2 real Completion model decisions** |
| H2 native ↔ Adapter ↔ HTTP identity join | **2/2 PASS** |
| H2 physical Provider response lifecycle | **3/3 complete** |
| H2 logical attribution and Provider billing | **PARTIAL / UNKNOWN** |
| Original H1 missing Provider terminal record | **BLOCKED, unchanged** |
| H3 Runtime-down/fail-open real native control | NOT RUN |
| H4 failed-read real native control | NOT RUN |
| D1-D4 true post-8.2B DSH StepFun tasks | NOT RUN |
| Phase 8.3A global Provider integrity | **BLOCKED_HISTORICAL_H1_REQUEST** |
| Production Canary/Active | **NOT AUTHORIZED** |
| Real-world model benefit and saving | **NOT ESTABLISHED / NOT MEASURED** |

H2 has not been rerun to improve metrics. The remaining 18
mathematical global Provider reservation slots are NOT extra
authorization or proof of subscription credits. No more paid
Provider calls were made after H2 in this report's work.

An independently recomputed, allowlisted public H2 aggregate is at
results/processed/phase8_3_h2_real_stepfun_shadow.json.
The raw SDK/native SQLite data, live credential pool, HMAC secret,
original file content and Provider request bodies remain private.

**Recommendation:** before pursuing H3/D1-D4, understand why physical
StepFun requests exceed main Agent-reported calls, and require better
Provider usage provenance. H2's success is real, but the full
Phase 8.3A engineering gate and active readiness remain BLOCKED.


## 8. Post-run code and public release checks

After the original real H2 execution, an independently rerunnable
adjudicator, frozen H2 aggregate and explicit synthetic tamper tests
were added. The post-run Python suite passed **1121/1121**,
DSH Vitest passed **64/64**, TypeScript typecheck and build PASS.
These tests generated **zero additional real StepFun requests**.

The public evidence contains only consented, bounded source/mode
labels, exact integer counts, elapsed native timing, sanitized
independent outcomes and ledger hashes. The original file nonce,
raw Agent/Provider messages, Session/Turn IDs, private HMAC key,
live credential, Provider Authorization headers and private
OS file paths are not committed.

The complete final source release sanitizer and clean-tree
attestation must be performed after the post-run commit. No change
to the frozen H2 native implementation in the later report commit
is represented as having received a second real Provider run.

This report does not authorize H3/H4, DSH real Provider tests or
Active until separately scoped physical budget and evidence checks
are satisfied; the user-approved outer 24-request cap alone does
not establish actual subscription cost or clean historical H1 billing.
