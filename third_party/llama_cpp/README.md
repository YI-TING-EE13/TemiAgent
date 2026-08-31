# llama.cpp bootstrap pin

Status: CURRENT_AUTHORITY. Source identity is portable; generated build output
and the AI6 binary identity below are observed deployment evidence.

`anomaly_detection/third_party/llama.cpp/` is a generated, external upstream
checkout. It is deliberately ignored by TemiAgent and is not a Git submodule.
The reviewed upstream URL, exact commit, checkout path, and expected tree are
recorded in `manifest.json`.

From a clean TemiAgent clone, initialize the formal Hermes submodule using the
Hermes handover procedure, then reconstruct all external source checkouts with:

```bash
python3 tools/run_bounded_process.py --timeout-seconds 120 --kill-grace-seconds 2 -- git submodule update --init --recursive --depth=1
./scripts/bootstrap --sources
```

To reconstruct only this optional action-viewer source dependency, run:

```bash
./scripts/bootstrap --llama-cpp
```

The bootstrap verifies the remote URL and exact commit/tree, fetches only the
pinned source history required for that verification, and refuses a dirty or
unknown local checkout. It never starts a service, installs dependencies,
downloads models, or builds `llama-server`. Build outputs and model assets stay
outside source delivery. `./scripts/bootstrap --check` verifies the source pin
as well as the separately provisioned runtime readiness prerequisites.

## License and publication boundary

The pinned upstream commit contains `LICENSE`, which was independently fetched
and inspected during Gate 3.1 candidate verification. The manifest records
`license_path: LICENSE`, `license_spdx: MIT`, and the exact license-file
SHA-256 `94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d`.
The notice identifies `The ggml authors` and copyright years `2023-2026`.

This records the license of the pinned llama.cpp source only. It does not
license or publish model weights, build outputs, or a running inference
service. The generated checkout remains ignored and must be reconstructed from
the public URL, commit, tree, and license fields in `manifest.json`.

## Build and operator artifact boundary

Source reconstruction is not a build:

~~~bash
./scripts/bootstrap --llama-cpp
~~~

The generated `build/bin/llama-server` is required only when the selected
viewer deployment enables it. The current source contract does not pin a
compiler, CUDA toolkit, generator, GPU architecture or binary hash. The
validated AI6 cache recorded `CMAKE_BUILD_TYPE=Release`,
`CMAKE_GENERATOR=Ninja`, `GGML_CUDA=ON` and
`CMAKE_CUDA_ARCHITECTURES=native`; reproduce those settings only through an
owner-approved build procedure.

For D2A, the private operator config selected:

~~~text
DEMO_ACTION_VIEWER_LLAMA_SERVER=/opt/TemiAgent-operator/anomaly_detection/third_party/llama.cpp/build/bin/llama-server
SHA-256=6827638842194c9903da14662737b1e5c7d35effa6353506a329d31f85029585
~~~

That absolute path and SHA-256 are `OBSERVED_AI6` evidence, not a portable
requirement. A clean clone must never fall back to a binary under
`/TemiAgent` worktree; the private config must name the selected deployment
artifact and viewer health must verify the actual child.
The embedded UI is optional and its absence is non-blocking when the service
health contract passes.
