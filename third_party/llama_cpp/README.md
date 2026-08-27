# llama.cpp bootstrap pin

`anomaly_detection/third_party/llama.cpp/` is a generated, external upstream
checkout. It is deliberately ignored by TemiAgent and is not a Git submodule.
The reviewed upstream URL, exact commit, checkout path, and expected tree are
recorded in `manifest.json`.

From a clean TemiAgent clone, reconstruct all external source checkouts with:

```bash
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
