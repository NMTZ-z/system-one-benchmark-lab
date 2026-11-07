# Phase 8.4D — isolated engineering pilot

Status: **OWNER_NOT_RUN; RELEASE_NO_GO**. The owner has not authorized a real
task set, remote provider, budget, or data scope. The checks below use synthetic
inputs and cannot establish real-user benefit or savings.

## Source and candidate boundaries

- GitHub `main` was `81e2792e2bc0be491af4c08a945ec2412aabf2a4` when checked.
  Draft #16 was `1a380eb0b26c527eae4174cc01720a72dc055ae2`; Draft #17 was
  `e54d053327a79698e62ea45c84727b93f1041235` and targets #16's branch.
- The original RC2 components were built from
  `d6c420d7a8c9bce7edc26eaa3770d5f09babad3b`. The recorded wheel and sdist
  were reproduced byte-for-byte offline. Their Python files, the Hermes
  archive, and DSH source files matched that Git tree; all 27 compiled DSH
  files matched an offline rebuild.
- This 8.4D change fixes a missing Runtime error category and corrects two
  installation/provenance instructions. The original RC2 manifest and hashes
  still describe the original RC2. Do not substitute the revised local wheel
  for that artifact under the same name: freeze a new source commit, version,
  manifest and artifacts before publication.

## Engineering evidence

- On Apple Silicon, a fresh Python 3.12.14 environment installed the candidate
  wheel and hash-locked Runtime dependencies. The existing pinned model passed
  its digest check and performed real offline MLX inference. The Runtime used
  loopback, a mode-0600 token, and rejected an unauthenticated request; a
  missing model was reported without downloading it.
- A fresh, named Hermes profile installed the candidate plugin in OFF mode.
  Its installed files matched the tested wheel. The first Shadow enabled Search
  alone. A real Hermes Agent with a local mock main provider sent identical
  model, messages and tools with Shadow and OFF and returned the same mock
  answer. This is a mock-provider engineering check, not an owner task.
- Ten synthetic hook cases covered known facts, local-file requests, rewriting,
  public-current information, translation, calculation, failure, multi-step
  planning, completion and approval. All ten produced Search observations:
  one `search` and nine `no_search`; four used rules and six used MLX. The
  observed hook latency was 0.6–64.8 ms in the final run. These cases exercise
  routing only; the described files, tools and public searches were not run.
- A live registered session produced no new observation after OFF. With the
  Runtime stopped, Hermes failed open and the revised status exposed
  `Runtime unavailable or credential missing` without recording private data.
  Stop and uninstall completed; synthetic session files, another plugin and
  another profile remained intact.
- The existing native legacy-migration assertions exercised a v0.9 session:
  configured OFF remained `PENDING_RELOAD` while it was loaded; after unload,
  the candidate's OFF, Shadow and uninstall checks passed.
- The MCP SDK 2.3.0 discovered and called all five Gates and health against
  the owned Runtime; Completion and Retry remained advisory. DSH typecheck,
  build and 68 tests passed. Native DSH compatibility at the two pinned
  versions remains the evidence recorded in the 8.4C report, not a rerun here.
- Focused Python regression passed 76 tests before the fix and 59 relevant
  tests after it. A local mock provider was used; no real provider was called.

## Limits and release work

The isolated Hermes toolchain was provisioned from existing local copies. A
cold offline profile attempted to provision its package-manager dependencies
and was blocked by the network policy; after the isolated dependency cache was
warmed, installation passed. The macOS Metal compiler required a dedicated
test-only application cache. Neither observation proves cold installation on
every user's machine. The test Hermes launcher was an isolated wrapper, so
Doctor could not identify its version and reported `NEEDS_SETUP` before install.

The optional ANE artifact and actual launchd deployment remain unqualified and
must not be advertised as verified. Existing unregistered Hermes sessions and
already-loaded DSH sessions require reload or termination before effective OFF
can be established. A process running as the same user can access that user's
local Runtime token; sustained local connection flooding can still cause 503.

Before release: complete separately authorized Owner tasks; bind all final
components and their hashes to the reviewed release source; merge #16, then
#17, then this change only after maintainer authorization; create the tag and
Release only after separate authorization. The Hermes Catalog and DSH
distribution source must then be updated to that same released source under
their own authorization. Production Active/Canary is not authorized.
