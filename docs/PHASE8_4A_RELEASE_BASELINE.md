# Phase 8.4A — Release baseline

Integration snapshot: 2026-11-06. The candidate starts from GitHub
[`main@062d52e753e7e00d91a536dc81e9d85b8819cb12`](https://github.com/NMTZ-z/system-one-benchmark-lab/commit/062d52e753e7e00d91a536dc81e9d85b8819cb12).
Phase 8.3 is **CLOSED_LIMITED**: its evidence is historical, its real user value
is not established, and H4E is deferred. The candidate retains the frozen
research commits of PRs #9–#13 and the 8.4A changes from #14. Until the
integration is approved and merged, the public main SHA above remains actual
main; 8.4B can use the exact reviewed integration PR head in a new worktree.
Production Active/Canary remains **NOT_AUTHORIZED**.

## Current implementation and gaps

| Area | Evidence in this baseline | Gap or boundary |
|---|---|---|
| Laya 421M / MLX | `local_system_one/runtime/{sources,mlx}.py`, `cli.py`; pinned model alias | Source and tests exist; First-Run health and clean install still require 8.4B acceptance. |
| ANE | `runtime/ane.py`, `router.py`, `scripts/build_typed421_ane.sh` | Optional; converter revision is pinned. The README's Hugging Face download does not pin an artifact revision or verify its digest. Fix the release recipe before claiming reproducible delivery. |
| Five Gates | `workflows/{search_gate,model_tier_gate,notification_gate,completion_gate,retry_escalation_gate}.py`; five HTTP routes in `service.py` | Existing gate logic is retained. Completion and Retry are advisory; no automatic stop, retry or escalation. |
| Hermes | `integrations/hermes/local-system-one-hermes/{plugin.yaml,__init__.py}`, profile scripts | OFF is default. Current Shadow defaults also enable Model Tier, Notification and Completion. Search-only onboarding, effective OFF and complete lifecycle remain 8.4B work. Canary code exists; no production authority is granted. |
| DSH | `integrations/deepseek-harness/local-system-one-dsh/src/{index,policy,retry}.ts` | Main has five-Gate adapter code; the distributed `dsh-plugin` branch is older. Rebuild, test and pin a matching install artifact in 8.4C. |
| HTTP / MCP | `service.py`, `client.py`, `mcp_server.py` | HTTP exposes five Gates. MCP currently exposes Search, Model Tier, Notification and health only; Completion/Retry parity and delivery are 8.4C. |
| Model Backend Contract | `model_backends/contract.py`, `docs/MODEL_BACKEND_CONTRACT.md` | Research-only provider abstraction. No runtime provider switch or remote fallback is authorized. |
| Evidence / budget | `evidence_integrity.py`, `budget_observability.py`, `docs/PHASE8_2B_*.md` | Structural checks and bounded mock evidence do not establish real billing, actual task savings or execution authority. |

Phase 8.3's file-level disposition and dependency map is in the
[archive index](PHASE8_3_ARCHIVE_INDEX.md). Research source is retained in
the candidate while its experiment executors and Opportunity module remain
outside the product package. See the [integration review](PHASE8_4A_INTEGRATION_REVIEW.md).

The installed Hermes source's admission validator passed its checks against
the plugin in an isolated capability probe, with one warning: the optional
Kanban task resolver imports three private Hermes modules in
`integrations/hermes/local-system-one-hermes/__init__.py`. That resolver
catches failures and falls back, but private APIs can drift and may complicate
catalog review. Validate the fallback and find a supported integration seam
before advertising compatibility or requesting the 8.4D catalog update.

The earlier #14 wheel check applies to that earlier source only. Integration
must independently build and inspect its own product wheel and sdist, alongside
product and research source exports. Dependency installation, model loading
and real inference still need clean end-to-end acceptance.

## Version and distribution matrix

The target numbers are frozen for this release plan, not declarations that the
unfinished software has shipped. `null` in the
[release manifest](../release/v0.2.0-manifest.json) means pending.

| Component | Observed source / install on 2026-11-05 | v0.2.0 target and final binding |
|---|---|---|
| Runtime | `pyproject.toml`: `0.1.0`, Python `>=3.11,<3.14`; source on verified main | `0.2.0`; record release commit, wheel/source artifact URLs and SHA-256; use PEP 440 `0.2.0rc1` for the Python RC. |
| Hermes plugin | Main `plugin.yaml`: `0.9.0`; declares Hermes `>=0.21.4`. Historical bounded native test used `v0.22.1+11.gd923a5e`. [Catalog](https://hermes-agent.nousresearch.com/docs/plugins/local-system-one-hermes): `0.6.0` at `1095495019b2dff2b4231ed70ec23a3ea716e2f6`. | `0.10.0`; pin tested source commit, artifact digest and exact verified Hermes version(s). Prepare reviewed catalog re-pin only in 8.4D. Manifest's minimum version is not proof of compatibility with every later version. |
| DSH plugin | Main `package.json`: `0.6.0`; `dsh-plugin` install branch: `0.3.0@217cf89b3c9d17eb5f3178ec0de31b530f834a96`. | `0.7.0`; build the installable bundle from the tested source, record its immutable commit and artifact digest. Validate both exact DSH targets below in 8.4C; do not silently repoint the existing branch during 8.4A. |
| DSH platforms | `0.1.7-rc.2@477b4f420553e8a52c2fbccc464d7561b239c443`; `0.2.1-alpha.1@5badb15009ae1756c3afe0ae0cef1faafc290ccc`; Node `>=22.19.0` | Historical coverage differs by feature and version. Requalify the advertised feature set and exact binaries before release. |
| MLX model | `convaiinnovations/laya-typed-decisions@f9ab0b228f0fc0f14d873dbc99038f135c2da1b2`; `laya-mlx==0.2.0` | Default. Record downloaded file digests, license and tested dependency/platform versions in the final manifest. First download requires network access. |
| Optional ANE | `laya-coreml@4619e0483f07adf39068532e85b42ec2347edb83`; L512 artifact repo `NMTZ/laya-typed-decisions-421m-coreml-ane` | Artifact revision and all required file digests pending. Pin and verify the actual bundle, source checkpoint and license before presenting this optional path as reproducible. |

RC tags bind the whole tested set. 8.4B delivers `v0.2.0-rc.1`; 8.4C
delivers `v0.2.0-rc.2`; 8.4D performs owner Shadow acceptance, creates the
final release and requests the catalog update. Plugin and DSH component versions
may use their own matching prerelease identifiers. Never substitute the 8.4A
base SHA for a future release commit.

## Release integrity procedure

1. Update the manifest with the exact tested commits, artifacts, hashes,
   platform versions, model revision, defaults, enabled capabilities and
   unauthorized actions. Unavailable values remain `null`; a final release
   with any required pending field is blocked.
2. From a clean release commit, export the product using the default
   `release/product-files.txt`; export the research archive separately using
   `--allowlist release/public-files.txt`. Verify each generated
   `PUBLIC-RELEASE.json` reports the exact source SHA, `source_dirty=false`,
   the correct `source_allowlist`, `license_status=included` and
   `publish_ready=true`, and independently
   check all generated `PUBLIC-MANIFEST.sha256` entries. Inspect the wheel
   and sdist to ensure the frozen Opportunity module is absent.
3. The committed root `PUBLIC-RELEASE.json` and `PUBLIC-MANIFEST.sha256`
   describe an older `1fefe931...` bundle. They are historical artifacts,
   not an attestation of current main or a substitute for a fresh export.
4. Project code is Apache-2.0 and `LICENSE` is allowlisted. Independently
   check third-party notices, dependency/model licenses and artifact provenance
   at publication; the sanitizer checks listed file paths and text patterns,
   not the legal status of model weights or every possible secret.
5. Test the exact installation artifacts in clean environments with no old
   experiment directory, model cache or private evidence as a dependency.
   Compare the distribution entry points with the manifest and source.

At this audit, the [pinned Laya model card](https://huggingface.co/convaiinnovations/laya-typed-decisions/resolve/f9ab0b228f0fc0f14d873dbc99038f135c2da1b2/README.md)
declares Apache-2.0, and the [pinned laya-coreml source](https://github.com/mizorewww/laya-coreml/blob/4619e0483f07adf39068532e85b42ec2347edb83/LICENSE)
includes that license and a [NOTICE](https://github.com/mizorewww/laya-coreml/blob/4619e0483f07adf39068532e85b42ec2347edb83/NOTICE).
The [current ANE artifact card](https://huggingface.co/NMTZ/laya-typed-decisions-421m-coreml-ane)
also declares Apache-2.0 and points to its LICENSE/NOTICE. Final artifact-specific
notice and license verification remains pending with the artifact revision.

## Phase status

| Item | Status | Meaning |
|---|---|---|
| Main baseline | VERIFIED | GitHub main and stacked PR heads checked on 2026-11-06; integration was Draft at that snapshot. |
| Phase 8.3 archive | PARTIAL | Public frozen code and reports are indexed; completeness of all private raw evidence was not re-audited. |
| Legacy PR disposition | DOCUMENTED | Research ancestry retained in the candidate; formal mainline integration needs maintainer confirmation. |
| Release scope | FROZEN | [Product scope](V0_2_PRODUCT_SCOPE.md). |
| Component version plan | FROZEN | Target versions fixed; future commits, digests and compatibility attestations are pending. |
| Public release integrity | PASS (integration source candidate) | Product/research exports and package boundaries are verified on the clean integration candidate. Final v0.2.0 artifacts remain pending. |
| 8.4B handoff | READY | [Implementation handoff](PHASE8_4B_IMPLEMENTATION_HANDOFF.md). |
| Production / Active | NOT_AUTHORIZED | Separate explicit authorization required. |
