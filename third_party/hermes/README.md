# Hermes reconstruction overlay

`hermes-agent/` remains an independently-versioned upstream checkout. TemiAgent
does not vendor Hermes, alter the public upstream remote, or push a Temi branch
to that remote. Instead, this directory records the reviewed public upstream
base and the small Temi-specific patch series required by the canonical Demo.

From a clean TemiAgent clone, run:

```bash
./scripts/bootstrap --hermes
# After the documented Hermes and module environments are provisioned:
./scripts/bootstrap --check
```

`bootstrap_hermes.sh` initializes an independent nested checkout and fetches
the exact public upstream base when it is absent, verifies every tracked patch
hash, creates the local-only `temiagent/integration` branch, applies the series,
and verifies the resulting Git tree hash. It starts no service, installs no
dependency, and writes no private configuration. A second invocation is a
no-op tree verification.
`bootstrap --check` remains a separate local dependency-readiness gate; a fresh
source clone intentionally does not contain virtual environments.

The root gitlink is retained for local historical traceability, but clean-clone
reproducibility is defined by `manifest.json` plus `patches/`, not by requiring
an unavailable private commit object. The one historical host-specific path in
the captured source was normalized to the canonical container path
`/TemiAgent/temi_shared/`; this is a documentation portability correction only.
Applying the series creates local commit IDs, so a clean clone can report the
historical gitlink as changed even when reconstruction succeeds. Treat the
manifest tree hash and nested-clean check as the source-equivalence gate; do
not stage that generated gitlink change in a clean-room checkout.

Do not edit a patch in place without updating its manifest SHA-256 and running
the clean-room reconstruction check. Do not add credentials, webhook URLs,
runtime memory, recordings, virtual environments, or downloaded model assets
to this directory.

## Documentation ownership boundary

The reconstructed `hermes-agent/README.TemiAgent.md` is the canonical nested
Hermes integration explanation. This root directory is its reproducible source:
patches `0002`, `0003`, `0004`, `0007`, and `0009` carry the documented Temi
integration history. A documentation-only root change must not edit the nested
checkout or stage its gitlink. If the nested README needs a change, update the
appropriate patch, its manifest hash, and the clean-room reconstruction evidence
in a separately scoped overlay change.
