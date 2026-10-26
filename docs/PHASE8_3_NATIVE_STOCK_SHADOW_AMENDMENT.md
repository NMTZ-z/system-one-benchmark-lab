# Phase 8.3A stock-shell Shadow: first frozen execution, adjudicator correction

The first immutable native execution used source and protocol commit
`c154446802e9433289c357342e24b3bd5c601068` and a **synthetic** main
Provider. Its original recorded verdicts are preserved exactly:

- `off_stock_shell`: PASS_SCOPED, zero observations, genuine native tool.
- `shadow_stock_fixture`: PASS_SCOPED, 3/3 native/HMAC/HTTP links.
- `shadow_stock_mlx`: PASS_SCOPED, 3/3 links, two actual local MLX
  Completion predictions and a separately counted warmup.
- `shadow_stock_503`: **BLOCKED at original verifier**, despite the native
  failure and 3/3 HTTP 503 links; the original checker wrongly demanded
  a successful `ask_user / retry_budget_unverified` recommendation when
  the unavailable Runtime correctly returned **no decision** and the
  Adapter recorded `failed_open / retry_runtime_unavailable`.

This is an **evaluation-policy defect**, not authorization to turn 503
or missing data into a successful decision. The correction demands both
that all three failed-open observations contain **no fabricated model or
rule decision**, and that the failed Retry observation has the exact
`retry_runtime_unavailable` cause. It preserves the healthy rule-only
`ask_user` requirement and the original Completion/recovery safety rules.
New negative unit cases reject false decisions and fake Runtime-down
reason codes. The original four results and raw private evidence remain
frozen and are never overwritten or silently relabelled. The complete
four-case matrix must be re-executed on a **new source commit and new private
output directory** before reporting a passing four-case experiment.

The new experiment stays **OFF/Shadow-only, entirely isolated and without
physical Provider requests, Active rights, or production configuration
edits**. Paid StepFun, DSH real Provider and real Agent value remain out
of scope. In particular, an HTTP 503 fail-open observation is not a
successful safe-retry recommendation and may never be counted as one.
