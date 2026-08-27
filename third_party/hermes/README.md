# Hermes reconstruction overlay

`hermes-agent/` remains an independently-versioned upstream checkout. TemiAgent
does not vendor Hermes, alter the public upstream remote, or push a Temi branch
to that remote. Instead, this directory records technical reconstruction input:
the reviewed public upstream base and the small Temi-specific patch series
required by the canonical Demo.

`hermes-agent/` is an external generated dependency, not TemiAgent root source,
not vendored source, and not a current root Git submodule. The root repository
publishes the upstream URL, base commit, ordered patch files, target-tree
metadata, required paths, license contract fields, and the
`PINNED_BASE_PLUS_PATCHED_WORKTREE` semantics; bootstrap can reconstruct the
nested checkout only when its external prerequisites are available.
Current local reconstruction evidence is branch `temiagent/integration` at
`126aa304cda027679fc84212925bbd5329ada20b`; this local commit is not a promise
of a team-accessible fork, formal root submodule, or handover-ready public root
checkout.

From a clean TemiAgent clone, run:

```bash
./scripts/bootstrap --sources
# After the documented Hermes and module environments are provisioned:
./scripts/bootstrap --check
```

`bootstrap_hermes.sh` initializes an independent nested checkout and fetches
the exact public upstream base when it is absent, verifies every tracked patch
hash, creates the local-only `temiagent/integration` branch, applies the series,
and verifies the resulting Git tree hash. Each fetch attempt is bounded to
20 seconds; the task-owned process group receives TERM, a two-second grace
period, and KILL if it is still alive, followed by bounded reaping. It starts
no service, installs no dependency, and writes no private configuration. A
second invocation is a no-op tree verification only after the license contract
also verifies.
`bootstrap --check` remains a separate local dependency-readiness gate; a fresh
source clone intentionally does not contain virtual environments.

The generated Hermes checkout is ignored, not a root gitlink. The manifest and
patches define technical reconstruction inputs; they do not satisfy the
repository handover gate in `AGENTS.md`. The one historical host-specific path
in the captured source was normalized to the canonical container path
`/TemiAgent/temi_shared/`; this is a documentation portability correction only.
When the pinned source is available, applying the series creates local commit
IDs and the bootstrap verifies the manifest tree hash and nested-clean check.
This candidate has not rerun a fresh Hermes reconstruction.

## Upstream availability and license boundary

The Hermes bootstrap treats public upstream access as an external prerequisite.
Each invocation allows at most two fetch attempts, with a 20-second per-fetch
timeout, a two-second cleanup grace, and a one-second retry delay. A rate limit
or timeout returns a named `PUBLIC_UPSTREAM_*` failure, does not start any
service, and leaves only the initialized nested checkout so a later official
fetch can resume. It never uses a local checkout, hidden cache, or file URL as
a fallback.

The expected base-tree value is intentionally not added to this candidate
manifest until the pinned commit is fetched and
`git show -s --format=%T a0fedfbb1b7eab8db6c8aaa187f8c35cbf12f3e2` independently
returns that value. Gate 3.1 review notes report
`bda69c575e65725bf9264dd1288a63093cea3cc3`, but this candidate does not treat
that external note as a local base-tree verification.

`manifest.json` records `license_path`, `license_status`, and, only after
independent inspection of the fetched pinned commit, may record
`license_sha256` and optional `license_blob_sha`. The current status is
`UNVERIFIED_PENDING_PUBLIC_FETCH`, so `tools/verify_hermes_license.py` fails
closed with `HERMES_LICENSE_UNVERIFIED`; it cannot report a pass. When verified,
the tool checks the Git blob at the declared base commit and the regular
checked-out file against the recorded content identity. The tracked patch
series is TemiAgent overlay material and is not a license grant for upstream
Hermes. Do not publish generated Hermes source, credentials, local runtime
data, or model assets as part of this root repository until the pinned-source
license and tree evidence are complete.

## Repository ownership and handover gate

`AGENTS.md` is authoritative for root publication. Its compliant model is
combined rather than either/or: a team-accessible Hermes fork or remote must
contain the pinned commit, the root must configure the formal Git submodule URL,
and `git submodule update --init --recursive` must succeed from a clean clone.
The current root has neither the team-accessible remote nor the formal
submodule. Therefore the generated public-upstream-plus-patches design is a
technical reconstruction capability, not publication or handover readiness:
`HERMES_DEPENDENCY_GOVERNANCE: BLOCKED / NOT YET SATISFIED`.

No remote repository is created by this task. A maintainer must provision the
team-accessible ownership boundary before the next Hermes reconstruction and
clean-clone handover gate.

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
