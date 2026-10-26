# H4E proposed one-shot real experiment — NOT AUTHORIZED

Prepared 2026-10-26 after the H4D credential compatibility repair.
**Planning readiness: GO. Execution readiness: NO-GO.** This document is
an approval proposal, not a runnable command, credential grant or budget
reservation. No H4E case or evidence directory has been created.

## Purpose and fixed limits

Verify whether a fresh real Hermes task can use the repaired isolated
credential path, perform one exact native missing-file read and emit
correlated advisory Shadow evidence, with independent verification of
Provider accounting and restoration. This is one engineering experiment,
not a statistical model-value or cost-savings claim.

| Item | Fixed proposed boundary |
| --- | --- |
| Case identity | `h4e_missing_read`; H4D is permanently consumed |
| Provider/model | StepFun Step Plan, `step-5-preview` only |
| Physical upstream budget | At most 3 new requests, counting main and auxiliary traffic and uncertain attempts |
| Time | One shared monotonic 90-second deadline for the native task, Provider requests and bounded drain; cleanup can stop/restore but cannot send more requests |
| Upstream | `https://api.stepfun.com/step_plan/v1/chat/completions` |
| Local Provider outlet | Fixed capped proxy `http://127.0.0.1:18794` |
| Tools | Only one native `read_file`, one preregistered absent target; no shell/browser/write tools |
| Control | Shadow advisory only; Active/Canary prohibited |
| Retries | No automatic task restart, Provider/SDK transport retry, fallback Provider/model/endpoint, or rerun after failure |
| Paid routes | No PAYG, new subscription, recharge or automatic budget increase |

All three requests remain behind the fsynced physical-request reservation
and result ledger. The existing 8/24 history and original H1 UNKNOWN are
immutable; the remaining global slots confer no authority. If that exact
baseline is unchanged when separately approved, H4E may reserve only slots
9–11. If it has changed, stop and re-evaluate the proposal without resetting
the ledger. Actual subscription credit debit remains unknown without
independent billing evidence.

## Separate identity and evidence

The proposed new owner-only root is
`private/phase8_3_h4e_real/`. It must not exist before admission. Proposed
children are `runs/h4e_missing_read/`, `recovery/`, `logs/`, `observer/`,
`source/`, `service_home/` and `tmp/`. Creation is exclusive, with directories
0700 and evidence files 0600; reject existing paths, symlinks, wrong owners
or any alias of an old H1–H4D path.

Use a new `h4e_absent_<24hex>.txt` manifest, prompt, HMAC key, native Session,
SQLite post-run archive and PID/PGID/UID/start-time process receipts. Keep
the file absent; any target mutation, second tool call or alternate target
blocks acceptance. All restore checkpoints and terminal evidence belong
to this new root. Do not delete, rename, rewrite or recycle H4D records.

The only shared durable state is the already designated owner-global
physical-request ledger and the manually authenticated nonproduction test
Home. The latter starts OFF and is checkpointed anew without reading,
copying or backing up auth bytes. Runtime credential access uses the
official Hermes resolver under the unchanged restricted file/network
policy; global credential contents remain denied. No environment API key
injection, production Home/config/plugin change or NAS/main update.

## Prerequisites before asking to execute

1. The H4D repair is committed, Draft PR #12 is updated, and a clean
   allowlisted release has `publish_ready=true` with a verified SHA-256
   manifest. These establish source release readiness only.
2. Implement H4E's explicit case binding in a separate approved development
   slice, then freeze and review that exact source. The current code
   intentionally accepts only H4B/H4C/H4D; do not rename H4D to bypass it.
   Cover child/runner identity, transaction and owned-process paths,
   sandbox scope, physical budget proxy, transport accounting and oracle.
   Extend the auth guard to H4E deliberately; it currently scopes itself
   to H4D only. Reuse the existing checks without permitting generic cases.
3. Prove zero-network admission on synthetic credentials and a fresh
   synthetic H4E fixture under real Seatbelt. Require profile-only
   credential resolution, fixed proxy route and sanitized errors. Verify
   empty/denied credentials, global fallback, route drift, reused evidence,
   cap/deadline violation and second tool call all fail closed. Pin and
   test zero automatic SDK/transport retries before any real run.
4. Bind the approved H4E source SHA, release-manifest SHA-256, unchanged
   Hermes archive revision/digests and local model revision/weights to the
   admission receipt. The H4D repair's source SHA alone cannot authorize
   an H4E executor added later.
5. Obtain a fresh explicit owner approval for that exact case and frozen
   SHA, Step Plan route/model, at most 3 physical requests and one 90-second
   attempt. Earlier H4D approval and this closeout instruction do not
   satisfy this requirement.
6. Immediately before the separately approved run, recheck unused evidence
   paths, OFF test Home, unchanged old evidence/ledger, free test ports,
   official authentication and every pooled credential's proxy pinning.
   Any drift or unproven check keeps NO-GO. Do not repair credentials,
   widen permissions or retry the real task as part of admission.

## Proposed single execution and independent acceptance

After explicit approval and all prerequisites, create the durable test-only
checkpoint and the new absent-target manifest, switch the isolated Home
to Shadow, and perform the real same-policy credential/tool admission.
Start only the owned local Laya runtime, observer and capped Step Plan
proxy; verify their identities and initial budget before the single Agent
task. All new physical requests share the same cap and deadline. Any
failure stops the experiment without a second attempt.

An independent read-only adjudicator must require:

- Native Session, exactly one same-ID `read_file` request/result for the
  frozen target, genuine `not_found` error, no target mutation and native
  closure. Agent prose alone is insufficient.
- Native → plugin → HTTP correlation using this case's HMAC; two actual
  local Completion observations and the advisory Retry observation.
  Preserve rule-only `ask_user` when retry budget is unverified; do not
  relabel that event as model inference.
- Between 1 and 3 new physical Step Plan attempts, all terminal outcomes
  accounted for. Unknown outcomes still consume reservations and block
  success; original H1 UNKNOWN stays unchanged.
- All owned groups stopped; post-run evidence archived; original OFF
  config, SQLite and plugin state restored; credential metadata unchanged;
  no production/old-evidence changes. Never kill by name/port or restore
  state underneath a process whose ownership is uncertain.

If restoration fails, preserve evidence and request manual action. Do not
retry Provider calls. Local rollback cannot undo spent physical requests.

## New approval request — pending, for the next window

The approval request must be completed with the future H4E executor's exact
SHA and release-manifest digest, then presented to the owner. It is not
valid with placeholders or an uncommitted executor:

> 请确认是否授权下一窗口执行独立案例 `h4e_missing_read` 一次。执行器和发布清单须先提供准确 SHA；仅使用 StepFun Step Plan `step-5-preview`，最多新增 3 次物理请求，单次 90 秒，所有请求计入原全局账本；禁止 PAYG、自动重试、生产修改及 Active/Canary。失败即停止并核验回滚，H4D 不再执行。

Until the exact-source approval and admission are complete: **H4E NO-GO**.
