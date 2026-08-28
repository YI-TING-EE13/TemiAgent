# Hermes external dependency

Hermes is an external reasoning runtime. The original upstream project is
[`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent),
and the team-controlled source boundary is
[`YI-TING-EE13/hermes-agent`](https://github.com/YI-TING-EE13/hermes-agent).
TemiAgent does not vendor Hermes or push Temi-specific patches to the original
upstream repository. The team fork makes the reviewed base commit available to
the project without making the fork's floating default branch the dependency
identity.

## Formal dependency contract

The root repository records one formal Git submodule:

| Field | Value |
|---|---|
| Submodule path | `hermes-agent` |
| Submodule URL | `https://github.com/YI-TING-EE13/hermes-agent.git` |
| Pinned base commit | `a0fedfbb1b7eab8db6c8aaa187f8c35cbf12f3e2` |
| Pinned base tree | `bda69c575e65725bf9264dd1288a63093cea3cc3` |
| Expected patched tree | `47e9f1411e585769c055d0c6ee4417bebcdc6f70` |
| Contract semantics | `PINNED_BASE_PLUS_PATCHED_WORKTREE` |

The root gitlink remains pinned to the base commit. The ten ordered patch
files under `third_party/hermes/patches/` are TemiAgent-owned overlay inputs.
The bootstrap applies those patches in manifest order inside the initialized
submodule and verifies the final tree. Generated local Hermes commit IDs are
not dependency authority; the base commit, base tree and final tree are the
authoritative identities.

Patch `0010` adds a bounded Hermes conversation-failure contract. Compression
exhaustion results now include an explicit `final_response: null` and bounded
failure metadata, while the simple `chat()` API raises a typed error instead of
indexing a missing response. The resident integration maps that typed error to
an allowlisted HTTP failure object without returning provider error text or
conversation content. This is a non-live failure-path remediation; the
external provider must still be provisioned with a context window compatible
with the configured Hermes limit before any live acceptance.

The manifest records the verified license identity: `LICENSE`, MIT, copyright
`Copyright (c) 2025 Nous Research`, Git blob
`75410e73319c72cd3e991a501c5455eb78f38375`, and SHA-256
`821556e6336796450ab852d375117b48a4887e71d255794fd6318d99982a5ab6`.
`tools/verify_hermes_license.py` verifies the declared content against the
pinned Git object and the checked-out file.

## Clean-clone setup

Run these commands inside the designated container from `/TemiAgent` after
cloning the TemiAgent root repository:

```bash
python3 tools/run_bounded_process.py \
  --timeout-seconds 120 \
  --kill-grace-seconds 2 \
  -- git submodule update --init --recursive --depth=1
./scripts/bootstrap --hermes
./scripts/bootstrap --hermes
```

The submodule initialization is the only Hermes source-acquisition step. It
must resolve `https://github.com/YI-TING-EE13/hermes-agent.git` and the root
gitlink must resolve to the pinned base commit. `bootstrap --hermes` validates
the URL, gitlink, base object, base tree, license, patch hashes, and alternate
object policy before applying patches. A second invocation verifies the final
tree and is a no-op.

`./scripts/bootstrap --sources` is the combined source setup command. Run the
submodule initialization above first; the command then runs Hermes setup and
the independent optional llama.cpp reconstruction. `./scripts/bootstrap
--check` remains the readiness check after the documented dependency
environments have been provisioned. None of these commands starts a service,
publishes MQTT, installs an APK, or runs model inference.

After patch reconstruction, `git status --short` may report ` m hermes-agent`.
That is expected: the root index keeps the base gitlink while the submodule
worktree contains the local patched integration branch. Do not commit the
generated final submodule commit into the root gitlink.

## Skills and ownership

The root `hermes-skills/` directory is a reviewable Temi-specific mirror. The
resident runtime reads the corresponding `hermes-agent/skills/temi-*` files
created by the tracked overlay patches. The root mirror is not copied into the
submodule during bootstrap, and the submodule does not become a hardware or
MQTT dispatcher; Hermes returns JSON-only plans to the Bridge safety boundary.

TemiAgent patches belong to the root repository. Do not push them to
`NousResearch/hermes-agent`; any future change to the team fork itself needs a
separate repository-governed review. If the team remote cannot be reached,
stop at submodule initialization and retain the named Git failure. Do not use
a local checkout, a file URL, Git alternates, a hidden cache, or the original
upstream URL as a fallback.

The root [`AGENTS.md`](../../AGENTS.md) and
[`manifest.json`](manifest.json) define the broader publication and license
boundaries. Keep this README, the manifest, bootstrap behavior and clean-clone
evidence synchronized when the external dependency contract changes.
