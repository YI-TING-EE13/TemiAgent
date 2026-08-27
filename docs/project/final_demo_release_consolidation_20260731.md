# Final Demo release consolidation record — 2026-07-31

> Status: HISTORICAL release record. Its dated worktree and evidence values do
> not replace the current status page or release handover.

Status: release-consolidation record. This is not real-device acceptance
evidence and does not authorize a service start, Android/ADB operation, Discord
delivery, or canonical-memory mutation.

## Reviewed worktree

| Field | Recorded value |
|---|---|
| Worktree | `/tmp/temiagent-worktrees/demo-backend-v1` |
| Branch | `codex/demo-operations-v1` |
| Reviewed HEAD | `444cf5b8bf5d77cda4caca5de8a6deac04b3c90b` |
| Merge base used for review | `8d93bb43ec7c847181b4c84376ba33eed152c0df` |
| Original owner task | `new-demo-v1` / **建立 Demo 操作工具** |
| Original scope | Demo operations, Media restart recovery, and the still-unfinished Care Report/adapter work |
| Review method | Read-only `git log`, `git show`, `git diff`, `range-diff`, complete tracked-path inventory, and clean-status checks. No untracked source item was found in the reviewed worktree. |

The owner confirmed that the two Media recovery commits are complete and should
be integrated. The owner also explicitly approved the following disposition for
the ten Care Report/adapter commits: **`DEFERRED_FEATURE_NOT_IN_CURRENT_RELEASE`**.
They remain on `codex/demo-operations-v1`; no commit, branch, or worktree is
discarded by this release record.

## Release decision

This release has two bounded changes only:

1. Integrate the reviewed Media restart-recovery behavior as individual,
   traceable commits.
2. Replace the two unmapped root gitlinks with ignored, bootstrap-managed
   external source checkouts pinned by tracked manifests.

It does **not** introduce a Care Report runtime, adapter, MQTT/API endpoint,
Android handoff, or a new care-decision path. That boundary follows the current
contract traceability entry: Care Report v1.0 is contract-defined while the
report service and interaction integration remain unimplemented
([`contract_traceability.md`](../architecture/contract_traceability.md)).

## Complete reviewed commit matrix

The action vocabulary is intentionally limited to this reconciliation:
`MEDIA_RESTART_INTEGRATE`, `SUPERSEDED`, and `OWNER_DECISION_REQUIRED`.
`OWNER_DECISION_REQUIRED` rows below have the owner-approved deferred disposition
stated in the Care Report section; it is not an authorization to discard them.

| Commit | Subject | Changed files reviewed | Action | Rationale / disposition |
|---|---|---|---|---|
| `e832c52367a5cc089e73de8866a74ac5bc002b81` | Fix restart terminal cached replay contract | Android/canonical contract docs; integration runbook; command-result schema and reader copy; Bridge README; `media_contract.py`; media/schema tests | `MEDIA_RESTART_INTEGRATE` | Complete. Individually integrated as `2de99ff` with `-x`. |
| `4f8290feff8fbc81a186f61962009a4740988aba` | Handle restart replay after Bridge restart | Same contract/doc/test area plus `media_registry.py` | `MEDIA_RESTART_INTEGRATE` | Complete. Individually integrated as `dfa8598` with `-x`. |
| `dd859ef9353ac551f1bcac2db6f956f4bab7ca05` | Implement feature-gated resident identity runtime | `resident_identity_backend_handoff.md`; identity contract/runtime; identity fixture/test | `SUPERSEDED` | Later integrated identity implementation on `main` supplies the current feature-gated route. |
| `70480d846efdf052912576807777d98bfb441df3` | Enforce resident identity partition binding | identity contract/runtime/test | `SUPERSEDED` | Follow-up to the older identity implementation; current `main` has the replacement boundary and tests. |
| `7940fc4eeb4e5e75ff34f9dedfbbc9c6c91e7c2f` | Implement feature-gated care report backend core | Care Report backend/Android checklist; `care_report_contract.py`; `care_report_runtime.py`; fixture/test | `OWNER_DECISION_REQUIRED` | Owner-approved `DEFERRED_FEATURE_NOT_IN_CURRENT_RELEASE`; preserved for a future bounded service implementation. |
| `6a12f72190ad6ba70252d74419d8ea7b0c1ea011` | Harden care report privacy boundaries | Care Report contract docs; runtime schema and reader copy; contract/runtime/test | `OWNER_DECISION_REQUIRED` | Same deferred feature set; privacy work must be reassessed with the current producer/consumer design. |
| `906eeb4dab1615798cdf58d01f658d0d092c9c94` | Reject unsafe care report scalar shapes | Care Report contract docs; runtime/test | `OWNER_DECISION_REQUIRED` | Same deferred feature set. |
| `f87eb71000fcbae825299bddffcfbf7976a0d46e` | Reject care report host endpoint shapes | Care Report contract docs; runtime/test | `OWNER_DECISION_REQUIRED` | Same deferred feature set. |
| `e3cf3d56de37e4805a66ec887b78df17e86c3b8e` | Refine care report endpoint detection | Care Report contract docs; runtime/test | `OWNER_DECISION_REQUIRED` | Same deferred feature set. |
| `3f2d8737e83a2bdd1325870636a19dc193878139` | Preserve RFC3339 care report timestamps | Care Report contract docs; runtime/test | `OWNER_DECISION_REQUIRED` | Same deferred feature set. |
| `32b533ad398104cfae25562037bf9fe2a95a1840` | Use documentation-safe care report fixtures | Care Report runtime test | `OWNER_DECISION_REQUIRED` | Same deferred feature set. |
| `6af398998dcc6a2fec7024a7a4fd9d829a6e92e0` | Wire identity and care report runtimes | Bridge `.env.example`; config; identity adapter; main; MQTT client; config/adapter/MQTT/wiring tests | `OWNER_DECISION_REQUIRED` | Same deferred feature set; integration would change current runtime wiring. |
| `950a0450133640933922f555c4952f3c04f9d0e4` | Document integrated care service runtimes | docs index/contract/runbook/checklists; Bridge README; Android care-report and identity fixtures/tests | `OWNER_DECISION_REQUIRED` | Same deferred feature set; its claim of an integrated runtime conflicts with current main traceability. |
| `61ae7dd2266b9234c25a7f0850766490c54b5e63` | Implement feature-gated Hermes media tool | Media contract docs/skill reference; Bridge config/action validator/media tool/main; tool test/fake E2E | `SUPERSEDED` | Main contains the later reviewed media tool implementation. |
| `4404c89580c88c4075d9295c06510ec12b064476` | Add feature-gated Demo media intent route | Media docs; Bridge config/main/fallback; fallback test/fake E2E | `SUPERSEDED` | Replaced by the current resident-native media dispatch route. |
| `f5d1ed3be50b8d3b9bd7f08c3e3fc88f162c30ad` | Add minimal partitioned Care Memory v2 | `care_memory_v2.py`; Care Memory v2 test | `SUPERSEDED` | Superseded by the current isolated Demo care-memory approach; not a release dependency. |
| `dd0fe373ba9cbe0845061e6486a6fa753a565a11` | Add repeatable synthetic Care Demo data | Care Memory v2 demo doc/test/tool | `SUPERSEDED` | Companion to superseded Care Memory v2 route. |
| `cfa4975ed344093ba54ae895c72e5e3d0a8a4310` | Connect Care Report to Care Memory v2 | docs; Care Memory v2 report adapter; Bridge config/main; adapter/config/wiring tests; fake E2E | `OWNER_DECISION_REQUIRED` | Tenth Care Report/adapter commit; owner-approved deferred feature disposition. |
| `904e294373436190c80b776ddea2ac8e38af4a84` | Add safe Demo operations lifecycle | Demo config; `demo_operations/**`; `scripts/demo` | `SUPERSEDED` | Main’s tracked lifecycle and tests replace this earlier implementation. |
| `5424dc1923939462036c75c4a31a3b3a13658d33` | Add Demo readiness and operator runbook | README/docs; `demo_operations` readiness/tests | `SUPERSEDED` | Current runbooks and lifecycle readiness are newer. |
| `23eefeefb41305b2b4c779461c40174e4b826321` | Fix Demo runtime integration gates | Demo config; `demo_operations` lifecycle/process/readiness/tests; runbook | `SUPERSEDED` | Follow-up to superseded operations implementation. |
| `9b4960939e92b155b63e93abd06e9812e0146824` | Finalize one-command Demo operations | Demo config; `demo_operations` CLI/config/operations/readiness/tests | `SUPERSEDED` | Follow-up to superseded operations implementation. |
| `444cf5b8bf5d77cda4caca5de8a6deac04b3c90b` | Add beginner Demo operator guide | README/docs; `demo_operations` docs/runbooks | `SUPERSEDED` | Current operator guide and lifecycle documentation supersede it. |

The path descriptions above are the complete changed-file groups reviewed for
each commit. Fixture directories named in a row were reviewed recursively; no
fixture, source, or documentation content was altered or discarded by this
classification.

## Care Report v1.0 deferred-feature disposition

| Question | Release answer |
|---|---|
| Status | `DEFERRED_FEATURE_NOT_IN_CURRENT_RELEASE` |
| Owner approval | Explicit confirmation from the original `new-demo-v1` owner task during this reconciliation: defer the feature, retain the branch and all ten commits, and do not discard them. |
| Current release scope | Media restart recovery and clean-clone source reproducibility only. |
| Preserved work | `7940fc4`, `6a12f72`, `906eeb4`, `f87eb71`, `e3cf3d5`, `3f2d873`, `32b533a`, `6af3989`, `950a045`, and `cfa4975` remain reachable from `codex/demo-operations-v1`. |
| Current architecture evidence | The authoritative schema exists, while `contract_traceability.md` records the report service and interaction integration as pending. Current Bridge limitations also state that it does not implement a care-report runtime. |
| Why it is not a simple merge | The preserved series adds new Bridge runtime/config/MQTT wiring, adapter behavior, fixtures, and documentation claims. It therefore needs a fresh current-main contract review rather than release-only reconciliation. |
| Future owner and target | The original `new-demo-v1` owner retains the preserved series. A future explicitly scoped Care Report implementation must name the Bridge/memory boundary, authorized producer/consumer, Android contract owner, and privacy test owner before integration. |
| Required future evidence | Current-main schema-copy comparison; unknown-resident and cross-resident isolation tests; read-only aggregation proof; producer/consumer and invalid-input tests; endpoint/privacy review; fake Android integration; and a separate authorized external acceptance decision. |
| This release’s Care Report test status | `SKIPPED — DEFERRED_FEATURE_NOT_IN_CURRENT_RELEASE`; no Care Report runtime or adapter code is introduced. |

The deferral does not alter canonical resident memory, create a new care decision
engine, publish a robot command, loosen unknown-resident behavior, or make an
external report/notification claim.

## Worktree retention and final reconciliation rule

The old worktree is retained as a clean historical branch until a separately
authorized owner action removes it. It must not be silently merged, rebased,
stashed, restored, cleaned, or force-removed as part of this release.

Release completion requires the canonical root and the reconstructed nested
Hermes checkout to be clean, no remaining index gitlink, successful manifest
bootstrap from a disposable fresh clone, and no unresolved Demo-relevant
worktree change. Real-device acceptance begins only under a separate task after
those source-delivery gates pass.
