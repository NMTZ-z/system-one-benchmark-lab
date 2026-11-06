# Phase 8.3 — H4D real-provider admission and historical real-evidence intake

**Registration: 2026-10-26. Preparation / audit only. ZERO paid Provider calls,
no owner credentials read, no real H4D dispatch, no Active/Canary, and no new
Agent state. This is NOT authorization to run H4D.**

## Two independent questions

1. **H4D admission:** Is it safe even to contemplate the *next* separately
   authorized real Hermes missing-file/Retry Shadow case, given frozen source,
   historical Provider request accounting, existing isolated test-Home OFF state,
   source/model versions, and pending credential/billing approval?
2. **Real-data feasibility:** How many independently adjudicated real Agent
   decision opportunities exist already from original H1/H2/H3? Do not equate
   a verified native tool *task* outcome with verified correctness of a
   Completion/Retry *decision*. Do not turn historical synthetic cases into
   real, new blind evidence.

## Frozen inputs and lineage

**Experiment branch starts at** `e971889e23ecae6db54712c43772eb670c0a068d`,
stacked after PR #10, itself stacked after PR #9. Production Hermes,
NAS Forgejo main and GitHub main remain untouched.

Frozen historical public input files and SHA-256:

| Original source | SHA-256 |
|---|---|
| `results/processed/phase8_3_h1_real_stepfun_partial.json` | `d22db1cad7ede1acbda769f2362cd44ebb60806efbe5e5300edbc6f50735564a` |
| `results/processed/phase8_3_h2_real_stepfun_shadow.json` | `0d6e55d8025cb0e602804262664bcc203f552830a2b74b0adfc4e464596785f1` |
| `results/processed/phase8_3_h3_real_stepfun_runtime_down.json` | `2c4941d4ebd90e41193ff52c8d6d95adac728068ea73b933e212b26594128653` |

Historic raw private Provider ledger is read ONLY to calculate its SHA-256,
never to copy, parse or log credentials, IDs or payloads. Expected digest:
`5b93ff7c76bcf74f85cf5e955e90b1a425608287c1213b3a3fd5185bee3ab5cb`.
The known original reserved attempts H1=3, H2=3, H3=2 must add to 8/24,
with exactly one original H1 UNKNOWN outcome. UNKNOWN is a consumed attempt
for physical budget safety, **not proven billed tokens or free credit**.

Pinned **frozen exported** official Hermes source revision:
`4d04303818b61bf3aa09278af48356315515965b`, previously proved
with unmodified Bash/native file tool in OFF and three Shadow settings.
The locally installed production Hermes may be newer and MUST NOT silently
replace this pinned execution source. Pinned Laya snapshot revision:
`f9ab0b228f0fc0f14d873dbc99038f135c2da1b2`, weights digest
`4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e`.

## H4D read-only preflight

- Only a clean Git source worktree with exact expected commit passes an
  immutable admission snapshot. Inspect public source/model file hashes,
  original private request ledger SHA, test-Home filesystem metadata and
  `inspect(official_auth=False)` for NON-CREDENTIAL config only.
- Never read authentication file contents, print .env values, call
  `hermes auth status`, use stored Provider tokens, open a Provider outlet,
  restart the host Gateway, start a native Agent or launch StepFun.
- The read-only check may report that a credential file exists, but MUST
  keep credential validity and authenticated capped route **UNVERIFIED**;
  existence or old logs never implies permission/credit.
- For real H4D readiness, a fresh explicit owner approval must later pin
  a numeric physical request cap (proposed at most 3), model token/Plan
  credit or monetary limit, timeout (proposed at most 90 seconds), exact
  one-shot original source, case ID, independent missing-file oracle and
  abort criteria. Neither 16 mathematical unused original slots nor
  "continue" is a signed request/cost cap. No one may create an executable
  authorization by editing the audit report.
- No recovery transaction, OFF-to-Shadow switch or credential scan is
  permitted in this stage. The preflight binary supports **READ-ONLY ONLY**
  and must fail closed if source, private ledger, test-Home isolation or
  frozen public evidence changes.

**Expected conclusion:** Engineering pre-requisites can be PASS_SCOPED,
while actual real-provider admission remains **NOT_AUTHORIZED** for independent
credential/budget reasons. H1 UNKNOWN must remain UNKNOWN. A new real test
needs its own script, fixed admission manifest, fresh private folder and
separate owner approval, all frozen before outbound traffic.

## Historical real-Agent sample intake and gold boundary

- Read exactly H1/H2/H3 *public bounded processed aggregates* above. No
  private transcript, credential, provider payload, raw user prompt or
  uncensored native Session may enter the public sample collector.
- H1: real Hermes OFF successful independently verified native file read;
  three physical attempts, two HTTP 200 and one unresolved. No model/Rule
  paired decision gold can be reconstructed from the success alone.
- H2: real Hermes Shadow successful independent native file read;
  three terminal physical attempts, two actual local Laya Completion
  observations with native→HTTP linkage. **Two observations** do NOT imply
  two independently *correct* Completion decisions.
- H3: real Hermes Runtime-down; successful native file task with two
  independently linked HTTP 503 failures/fail-open, two terminal Provider
  attempts. No Laya decision produced while Runtime was down.
- Preserve separate denominators: real completed native tasks, real
  captured model *observations*, independently adjudicated decision labels,
  eligible rule-vs-Laya same-input comparisons, and unknown Provider
  terminal/billing data. Missing decision gold must be explicit
  `NOT_ESTABLISHED` / null, never 0% or 100% accuracy.
- Frozen synthetic/fixture stock Shadow results may be referenced only as
  technical provenance. They must **not** enlarge the real-Agent task or
  eligible decision denominators.
- Independent, externally checked
  filesystem/tool/remote state plus separately adjudicated **decision**
  gold, safe candidate set and verified retry budget are required for any
  future positive real value sample. Do not infer retry safety from
  a `File not found` string or Agent final sentence.

## Testing and publication

- Unit tests must reject source SHA tampering, unexpected input fields,
  inconsistent physical counts, forged model participation, fake real gold,
  missing UNKNOWN, wrong Home, Active mode and any report claiming paid
  authorization. A stat-only credential check may not open the auth file.
- Generate a privacy-safe aggregate only on the committed/frozen source,
  with exact original inputs checked by digest. The actual report must
  distinguish prior historical observations from new inference (none).
- Run isolated Python regression and appropriate native/DSH regressions,
  clean Git, sanitizer/allowlist scan, and publish **as an independent Draft
  stacked after PR #10**, not by modifying PR #9/#10 or auto-merging.

**No authorisation to execute real H4D, DSH, Canary or paid model calls.**
