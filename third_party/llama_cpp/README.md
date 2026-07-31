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
