# Public Release Packaging

Date: 2026-09-26  
Status: pre-publication packaging

## Goal

The private research repository contains benchmark history, local experiment outputs and machine-specific evidence that should not be copied wholesale into a public project.

Public distribution therefore uses an explicit tracked-file allowlist and a sanitizer rather than copying directories manually.

## Build a review bundle

~~~bash
.venv/bin/python scripts/build_public_release.py --force
~~~

Default output:

~~~text
artifacts/public-release/local-system-one/
~~~

The builder:

1. selects files from `release/public-files.txt`;
2. expands directory prefixes from Git-tracked files only; exact allowlist entries may include a new non-ignored review-stage file, while any dirty source tree is marked non-publish-ready;
3. rejects private/model/artifact/raw-result paths;
4. rejects symlinks;
5. scans exported text for user-home paths, private-key headers and common credential/token patterns;
6. writes `PUBLIC-MANIFEST.sha256`;
7. writes `PUBLIC-RELEASE.json` with source commit, dirty-tree state and license readiness.

A scanner finding fails the build.

## Runtime installation model

The public package has a standard Python project definition:

~~~bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[mcp]'
~~~

For the L512 ANE backend:

~~~bash
python -m pip install -e '.[ane,mcp]'
~~~

Validated runtime dependencies are pinned to:

- base MLX runtime: `laya-mlx==0.2.0`;
- optional ANE runtime: `laya-coreml` from upstream commit `4619e0483f07adf39068532e85b42ec2347edb83`.

The Git pin is deliberate: the validated `laya-coreml 0.1.1` in the research environment came from that source checkout and is not currently resolvable as a normal public-index package.

The 421M model checkpoint and converted ANE package are deliberately not bundled. Users provide their local paths through `--source`, `--ane-package`, or the existing `LOCAL_SYSTEM_ONE_SOURCE` / `LOCAL_SYSTEM_ONE_ANE_PACKAGE` service variables.

For ordinary use, `--source` defaults to the `laya-typed-decisions` alias and pins the source checkpoint to `f9ab0b228f0fc0f14d873dbc99038f135c2da1b2`; MLX resolves that snapshot automatically.

The L512 ANE package is reproducible locally:

~~~bash
scripts/build_typed421_ane.sh
~~~

That wrapper checks out `mizorewww/laya-coreml` at `4619e0483f07adf39068532e85b42ec2347edb83` and invokes the exact fixed-body converter used by the frozen Phase 4 artifact. This keeps the public project from redistributing the 421M checkpoint or the roughly 742 MB converted package while still giving users a pinned build path.

## What is intentionally excluded

The public bundle does not contain:

- `private/` Hermes replay or blind-set material;
- model weights;
- Core ML build artifacts;
- raw Hermes evaluation logs;
- historical experiment directories containing machine-specific paths;
- credentials or `.env` files.

The small set of frozen reports linked directly by the public README is included only after the same sanitizer passes them. Raw benchmark evidence and replay inputs remain excluded.

The upstream Laya/CoreML provenance remains documented in `references/UPSTREAM.md`. The runtime can use the published `laya-coreml` Python package, so a source checkout of the research submodule is not required for ordinary users.

## Hermes compatibility check

For future Hermes upgrades, the repository includes a live lifecycle smoke test:

~~~bash
export PATH="$HOME/.local/bin:$PATH"
scripts/smoke_hermes_system_one_live.sh systemoneeval
~~~

It exercises OFF, Shadow, explicitly acknowledged Canary and fail-open behavior, then restores the original plugin settings.

For safety it refuses ordinary production-profile names unless `LOCAL_SYSTEM_ONE_ALLOW_PRODUCTION_SMOKE=1` is explicitly set.

The smoke test makes real Hermes provider calls. It is not a unit test and should be run only on a disposable/evaluation profile.

## 2026-09-26 isolated public-path acceptance

The public path was exercised from the sanitized bundle rather than from the private research checkout:

1. the committed public builder exported 71 allowlisted files with zero sanitizer findings;
2. the wheel built successfully from that bundle;
3. a fresh Python 3.12 environment installed the wheel with both `[ane,mcp]` extras, resolving `laya-coreml` from the pinned Git revision;
4. `scripts/build_typed421_ane.sh --prepare-only` created an independent upstream checkout and environment without using `references/laya-coreml`;
5. the full build path downloaded the five required Typed Decisions files anonymously from the pinned Hugging Face revision and produced a new fixed B1/L512/K32 Core ML package;
6. the rebuilt package is 741,823,311 bytes and its three source-file SHA-256 values exactly match the frozen Phase 4 source artifact;
7. loading the rebuilt package through the installed public Runtime passed the MLX-vs-ANE startup probe with six samples, `healthy=true`, and rolling p50 about 64.96 ms;
8. old frozen L512 and newly rebuilt L512 produced field-for-field identical outputs on the three public startup probes for choice, score and noul.

The WebCodex shell used for the full conversion has a 120-second execution ceiling, so that wrapper invocation was externally terminated after the package had already been written, while Core ML was doing its expensive initial load/plan phase. The resulting package was then loaded and validated to completion through a longer-lived AgentDock process. This is an orchestration limit, not a conversion failure.

### Known non-blocking numerical warning

Both the frozen L512 package and the newly rebuilt L512 package emit the same NumPy warnings in the existing `laya-coreml` CPU action-head matmul on the three startup probes: divide-by-zero, overflow and invalid-value warnings. Both sides emit 10 warnings total in the same comparison.

For those probes:

- choice / score / noul outputs, probabilities and confidence are identical old vs new;
- `act_probability` remains finite and equals 1.0 on all three probes;
- Local System One's Search Gate, Model Tier Gate and Notification Gate do not use `act_probability` as a routing condition.

Therefore this is recorded as an upstream/runtime numerical issue for later cleanup, **not a blocker for the first Local System One public release**. It must not be presented as a newly introduced rebuild regression.

## Publication gate

The source bundle, standard wheel, isolated dependency installation, fresh pinned checkpoint acquisition, L512 rebuild and Runtime startup correctness path have now passed.

The project is still **not publish-ready until a project license is selected and a `LICENSE` file is added to the public allowlist**.

The builder records this as `license_status: missing` and `publish_ready: false` rather than silently pretending an unlicensed repository is ready for public reuse. A second physical Mac is useful future cross-machine evidence, but it is no longer required to prove that the release bundle itself contains a complete reproducible installation and ANE build path.
