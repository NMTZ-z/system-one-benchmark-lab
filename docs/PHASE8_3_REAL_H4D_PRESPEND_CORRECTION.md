# H4D correction before the first physical StepFun request

This is a separate **pre-spend** correction to the original frozen H4D
source `8215a572be24b97110def542901796ed265507c6`.
That commit's source passed the real offline preflight but **NO paid H4D
Agent or proxy was launched**; the historical ledger SHA-256 remained
`5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb`
with 8/24 physical reservations and H1 UNKNOWN=1.

An independent code review discovered that the H4D Provider service
correctly uses a disposable `HOME` to avoid leaking user/private caches,
while the exceptional H4D **canonical original request ledger** path check
mistakenly used `Path.home()`. That would resolve inside the disposable
HOME and cause an invalid-budget startup block **before any Provider call**.
The correction derives the canonical owner path from
`pwd.getpwuid(os.getuid()).pw_dir` instead of process HOME.
The path remains exactly the original old Phase 8.3 private cumulative
Provider ledger, never any arbitrary alternate or new budget file.

A new negative test proves that changing HOME to a synthetic service HOME
cannot redirect the canonical budget path; earlier cap guards still refuse
a wrong per-case limit, 24-global limit, port, model, original 30-line
ledger-prefix hash or declared run ID. No Provider endpoint or real source
model changes were made. Existing original H4B/H4C functionality is not
relaxed, and this amendment does not permit any new Agent retries.

**The next H4D trial is NOT started on the original `8215a57` commit.**
Re-run unit/full safety regression and public sanitizer, freeze a NEW clean
source commit, update stacked Draft PR #12 without force push, and repeat
`--check-offline` against that exact new SHA before a single possible
real StepFun physical request. Failure of any renewed gate is a hard NO-GO.

Scope remains **StepFun Step Plan only, `step-5-preview`, 3 new physical
attempts maximum, 90 s one-shot native Agent, no PAYG, no automatic
repeat, OFF→Shadow test-only with verified rollback, Active unauthorized**.
