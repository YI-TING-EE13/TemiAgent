# Hermes reconstruction overlay

`hermes-agent/` remains an independently-versioned upstream checkout. TemiAgent
does not vendor Hermes, alter the public upstream remote, or push a Temi branch
to that remote. Instead, this directory records the reviewed public upstream
base and the small Temi-specific patch series required by the canonical Demo.

`hermes-agent/` is an external generated dependency, not TemiAgent root source,
not vendored source, and not a current root Git submodule. The root repository
publishes the upstream URL, base commit, ordered patch files, target-tree
metadata, required paths, and the `PINNED_BASE_PLUS_PATCHED_WORKTREE` contract
semantics;
bootstrap reconstructs the nested checkout when the local environment permits it.
Current local reconstruction evidence is branch `temiagent/integration` at
`126aa304cda027679fc84212925bbd5329ada20b`; this local commit is not a promise
of a team-accessible fork or an independently reproducible public root checkout.

From a clean TemiAgent clone, run:

```bash
./scripts/bootstrap --sources
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

The generated Hermes checkout is ignored, not a root gitlink. Clean-clone
reproducibility is defined by `manifest.json` plus `patches/`, not by requiring
an unavailable private commit object. The one historical host-specific path in
the captured source was normalized to the canonical container path
`/TemiAgent/temi_shared/`; this is a documentation portability correction only.
Applying the series creates local commit IDs, so source equivalence is proven by
the manifest tree hash and nested-clean check while the root repository remains
clean.

## Upstream availability and license boundary

The Hermes bootstrap treats public upstream access as an external prerequisite.
Each invocation allows at most two fetch attempts, with a 20-second per-fetch
timeout and a one-second retry delay. A rate limit or timeout returns a named
`PUBLIC_UPSTREAM_*` failure, does not start any service, and leaves only the
initialized nested checkout so a later official fetch can resume. It never
uses a local checkout, hidden cache, or file URL as a fallback.

The expected base-tree value is intentionally not added to this candidate
manifest until the pinned commit is fetched and
`git show -s --format=%T a0fedfbb1b7eab8db6c8aaa187f8c35cbf12f3e2` independently
returns that value. Gate 3.1 review notes report
`bda69c575e65725bf9264dd1288a63093cea3cc3`, but this candidate does not treat
that external note as a local base-tree verification.

The pinned source license is likewise verified from the fetched upstream
`LICENSE` file only after that fetch succeeds. Review notes describe the
upstream notice as MIT with `Copyright (c) 2025 Nous Research`, but this
candidate records Hermes license status as unverified while public fetch is
unavailable. The tracked patch series is TemiAgent overlay material and is not
a license grant for upstream Hermes. Do not publish generated Hermes source,
credentials, local runtime data, or model assets as part of this root
repository until the pinned-source license and tree evidence are complete.

Do not edit a patch in place without updating its manifest SHA-256 and running
the clean-room reconstruction check. Do not add credentials, webhook URLs,
runtime memory, recordings, virtual environments, or downloaded model assets
to this directory.

## Documentation ownership boundary

The reconstructed `hermes-agent/README.TemiAgent.md` is the canonical nested
Hermes integration explanation. This root directory is its reproducible source:
patches `0002`, `0003`, `0004`, `0007`, and `0009` carry the documented Temi
integration history. A documentation-only root change must not edit the nested
checkout. If the nested README needs a change, update the
appropriate patch, its manifest hash, and the clean-room reconstruction evidence
in a separately scoped overlay change.
