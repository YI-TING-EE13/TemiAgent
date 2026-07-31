# Demo temporary content inventory — 2026-07-30

Status: dated retention inventory. This is a source-control handoff record, not
an instruction to delete, restart, or replay a Demo. The complete machine-
readable inventory (path, type, byte count, mtime, mode and regular-file
SHA-256) is retained in the owner-only acceptance directory created for the
main integration. It is intentionally not committed because it includes
runtime-artifact paths and timestamps.

## Classification rules

- `MIGRATE_TRACKED`: source material required for the canonical repository.
- `MIGRATE_LOCAL_IGNORED`: retain locally below `.local/`; never commit.
- `ALREADY_CANONICAL`: reviewed source is already reachable from `main`.
- `ARCHIVE_REFERENCE_ONLY`: evidence retained in place; no source migration.
- `PENDING_USER_REVIEW`: a worktree or mixed artifact whose owner must decide
  retention.
- `DO_NOT_COPY_SECRET`: private configuration or credential-shaped content.
- `DUPLICATE`: a second copy of content that already has an authoritative home.
- `UNKNOWN`: content needing separate classification before any action.

## Root-level inventory

| Temporary root or file | Classification | Containment / disposition |
|---|---|---|
| `/tmp/temiagent-abnormal-mqtt-observer.3MhqqT.log` | `ARCHIVE_REFERENCE_ONLY` | Empty observer artifact; retain in place. |
| `/tmp/temiagent-contract-audit.md` | `ARCHIVE_REFERENCE_ONLY` | Historical audit note; no source migration. |
| `/tmp/temiagent-final-contract.md` | `ARCHIVE_REFERENCE_ONLY` | Historical acceptance note; no source migration. |
| `/tmp/temiagent-final-e2e.md` | `ARCHIVE_REFERENCE_ONLY` | Historical acceptance note; no source migration. |
| `/tmp/temiagent-final-local-stream.md` | `ARCHIVE_REFERENCE_ONLY` | Historical stream note; no source migration. |
| `/tmp/temiagent-final-stack.md` | `ARCHIVE_REFERENCE_ONLY` | Historical stack note; no source migration. |
| `/tmp/temiagent-final-stream.md` | `ARCHIVE_REFERENCE_ONLY` | Historical stream note; no source migration. |
| `/tmp/temiagent-lmstudio-audit.md` | `ARCHIVE_REFERENCE_ONLY` | Historical model-service audit; no source migration. |
| `/tmp/temiagent-resident-health.json` | `ARCHIVE_REFERENCE_ONLY` | Runtime health evidence; do not treat as live status. |
| `/tmp/temiagent-viewer-health.json` | `ARCHIVE_REFERENCE_ONLY` | Runtime health evidence; do not treat as live status. |
| `/tmp/temiagent-worktrees/` | `PENDING_USER_REVIEW` | Nine registered historical worktrees; preserve their branches and ownership until each owner authorizes a separate retention decision. |
| `/tmp/temiagent_abnormal_care/` | `ALREADY_CANONICAL` | Its reviewed abnormal-care commit is an ancestor of `main`; embedded virtual environments, model weights, logs and memory are non-source artifacts and are not copied. |
| `/tmp/temiagent_fast_media/` | `PENDING_USER_REVIEW` | Mixed legacy runtime root. `config/` is `DO_NOT_COPY_SECRET`; `data/{care-memory,shared}`, logs, sockets, PID records and exports are `ARCHIVE_REFERENCE_ONLY` because the canonical lifecycle uses an external owner-only runtime root. |
| `/tmp/temiagent_fast_media_demo.env` | `DO_NOT_COPY_SECRET` | Private Demo configuration; do not copy into Git or the tracked handoff. |
| `/tmp/temiagent_handover_20260730_173319/` | `ARCHIVE_REFERENCE_ONLY` | Owner-only acceptance evidence retained in place. |
| `/tmp/temiagent_handover_20260730_173319.tar.gz` | `MIGRATE_LOCAL_IGNORED` | Copied without deleting the source to `.local/acceptance/temiagent_handover_20260730_173319.tar.gz`. |
| `/tmp/temiagent_handover_current` | `ARCHIVE_REFERENCE_ONLY` | Pointer to historical handover evidence; retain in place. |
| `/tmp/temiagent_lms_daemon_help.txt` | `ARCHIVE_REFERENCE_ONLY` | Historical command help; no source migration. |
| `/tmp/temiagent_main_integration_20260731_021414/` | `ARCHIVE_REFERENCE_ONLY` | Current owner-only integration acceptance evidence; retain outside Git. |
| `/tmp/temiagent_main_integration_current` | `ARCHIVE_REFERENCE_ONLY` | Pointer to current acceptance evidence; retain outside Git. |
| `/tmp/temiagent_clean_bootstrap_20260731_021414/` | `PENDING_USER_REVIEW` | First clean-room prototype retained after a clone checkout timing experiment; do not copy or delete. |
| `/tmp/temiagent_clean_bootstrap_20260731_021414_v2/` | `PENDING_USER_REVIEW` | Second clean-room prototype retained after the same timing investigation; do not copy or delete. |
| `/tmp/temiagent_clean_bootstrap_20260731_021414_v3/` | `PENDING_USER_REVIEW` | Third clean-room prototype retained while replacing clone checkout with explicit-base reconstruction; do not copy or delete. |
| `/tmp/temiagent_clean_bootstrap_20260731_021414_v4/` | `ARCHIVE_REFERENCE_ONLY` | Final clean-room evidence: public-base reconstruction, expected tree hash, clean nested checkout and idempotent second bootstrap all passed. |

No root was classified `MIGRATE_TRACKED`: all source changes needed for the
canonical Demo were integrated through Git history or the tracked Hermes patch
overlay. No temporary root was deleted, moved, reset, cleaned or overwritten.

## Local archive and runtime references

The only copied temporary artifact is the historical handover archive:

```text
source:      /tmp/temiagent_handover_20260730_173319.tar.gz
destination: .local/acceptance/temiagent_handover_20260730_173319.tar.gz
sha256:      59460671198833901f6c80c125a8923b55e8e157d770a0410afd1f62f9bf1151
result:      PASS (source and destination match)
```

`.local/` is Git-ignored and is for owner-only acceptance archives, private
migration records and local retention only. It is not a runtime source of
truth. The active lifecycle requires `TEMIAGENT_RUNTIME_ROOT`, `MEMORY_DIR`,
Bridge logs, shared media and callback sockets to remain below an external
owner-only runtime root; private config and Discord credential files remain
outside every Git worktree.

The Hermes overlay verifies source equivalence by tree hash. A clean-room
checkout can display only the historical nested gitlink as modified after a
successful reconstruction because patch application creates local commit IDs;
the generated gitlink must not be staged. The canonical `/TemiAgent` checkout
is the clean source-of-record for `main`.

## Duplicates, risks and deferred ownership

- The canonical source on `main` supersedes the reviewed source portions of
  `temiagent_abnormal_care`; it does not absorb that worktree's model, virtual
  environment, memory or logs.
- `temiagent_fast_media` is not an authoritative configuration source. Its
  private env and mixed runtime state must not be committed or bulk-copied.
- Historical reports may contain machine-specific observations. They remain
  reference evidence and require owner review before any disclosure or move.
- The registered worktrees remain `PENDING_USER_REVIEW`; their branches and
  directories were intentionally left untouched.

Suggested read-only post-acceptance checks (not executed here):

```bash
git worktree list --porcelain
sha256sum /tmp/temiagent_handover_20260730_173319.tar.gz \
  .local/acceptance/temiagent_handover_20260730_173319.tar.gz
tar -tf .local/acceptance/temiagent_handover_20260730_173319.tar.gz
```

Any future deletion, archive relocation, private-config rotation or worktree
cleanup requires the data owner to authorize a separate task with a recovery
plan. Do not use broad `rm`, `git clean`, `git reset` or worktree pruning as a
handoff shortcut.
