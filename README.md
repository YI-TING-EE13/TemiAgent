# TemiAgent

TemiAgent is a modular, research-oriented integration project for connecting
Temi voice and camera events with local reasoning, validated robot commands,
and optional perception experiments. It is organized for academic-lab
development: contracts, safety boundaries, testable modules, and operational
evidence are kept separate from private runtime configuration and physical
device access.

The repository does not include the Temi Android application, a physical Temi
robot, private service configuration, model weights, or a guarantee of live
device behavior. It is not a medical device and does not claim emergency
notification, diagnosis, guaranteed fall detection, or unsupervised autonomous
care.

## Overview

The current design separates reasoning from hardware control:

- legacy backend integrations remain available for compatibility;
- an adapter maps legacy ASR and camera inputs to canonical events;
- the Hermes resident produces JSON-only reasoning plans;
- `hermes_temi_bridge/` validates events, paths, plans, actions, and command
  ownership before a robot-facing request is published;
- optional anomaly detection and streaming tools produce experimental
  perception events, but are not general hardware dispatchers;
- the Android application and Temi hardware remain external execution
  boundaries.

## Key Features

| Feature | Current state | Boundary |
| --- | --- | --- |
| Canonical ASR, perception-event, and action contracts | Implemented; hardware-free verification is available | Runtime schemas and validators are authoritative; documentation does not redefine them. |
| Hermes resident reasoning | Implemented; JSON-only behavior is tested in repository workflows | Hermes does not publish MQTT or control hardware directly. |
| Bridge validation and command boundary | Implemented; hardware-free verification is available | Only validated command requests may use the canonical robot-facing route. |
| Legacy ASR, video, local-VLM, and MQTT compatibility | Implemented for the legacy route | Live behavior depends on its configured external services and is not implied by a clean clone. |
| Anomaly detection and live viewer | Experimental and optional | Perception output is not a general command dispatcher; model artifacts are owner-provisioned. |
| Demo lifecycle and synthetic fixtures | Demo-only | The lifecycle supports explicit managed/external ownership; it is not a physical-device acceptance claim. |

## System Architecture

The canonical V1 path is:

```text
Temi Android ASR/camera (external)
        |
        v
tools/temi_overview_adapter.py
        |
        v
canonical events + allowlisted image paths
        |
        v
HermesTemiBridge: validate input and resolve safe paths
        |
        v
Hermes resident: return a JSON-only action plan
        |
        v
HermesTemiBridge: validate action and publish a command request
        |
        v
Temi Android executor (external) ---> command result and Bridge trace
```

The legacy backend compatibility route is maintained separately. The Bridge
is the canonical safety and dispatch boundary; new code must not bypass its
event models, image resolver, action validator, runtime schemas, or ownership
checks. See the [project overview](docs/architecture/project_overview.md) and
[contract traceability map](docs/architecture/contract_traceability.md) for
the authoritative module relationships.

## Repository Components

| Path | Purpose | Ownership and boundary |
| --- | --- | --- |
| `temi_backend/` | Legacy ASR, video, local VLM, and legacy MQTT compatibility route | Owns the legacy path; it is not the canonical Bridge dispatcher. |
| `tools/temi_overview_adapter.py` | Adapts legacy ASR and camera frames to canonical events | Produces events and allowlisted paths; it does not dispatch commands. |
| `hermes_temi_bridge/` | Canonical event validation, path resolution, Hermes-plan validation, and command requests | Owns the robot-facing safety boundary and canonical MQTT request route. |
| `hermes-agent/` | External Hermes source checkout used by the resident reasoning runtime | A formal submodule with source-owned setup; Temi-specific integration is coordinated by the root repository. |
| `hermes-skills/` | Reviewable mirror of Temi-specific skills | Runtime skills are loaded from `hermes-agent/skills/temi-*`; the mirror is for review. |
| `anomaly_detection/` | Experimental perception and streaming viewer | Optional model/viewer path; it must not become a general hardware dispatcher. |
| `temi_shared/` | Shared event metadata and allowlisted image-path conventions | Runtime images and metadata are non-source artifacts and are not published as repository content. |
| `mqtt/` | Broker configuration and topic reference | Documents ownership and topics; it does not authorize adoption or broad broker control. |
| `tools/` | Bootstrap, lifecycle, validation, mock E2E, and evidence utilities | Cross-module tooling; `demo_lifecycle.py` is the Demo lifecycle authority. |
| `scripts/` | Stable command-line entry points | `scripts/bootstrap` and `scripts/demo` delegate to the documented tooling. |
| `docs/` | Architecture, contracts, operations, governance, and evidence | Detailed authority lives in the documents linked below. |

Generated environments, model caches, logs, memory, images, checkpoints, and
private runtime state are not repository modules. They must remain outside the
published source and follow the retention and access rules in `AGENTS.md`.

## Installation

### Prerequisites

- Git and access to the repository's formal Hermes submodule source.
- Python 3.12 or newer for the root-supported module environments, plus
  [`uv`](https://docs.astral.sh/uv/).
- The designated development container described in [`AGENTS.md`](AGENTS.md)
  for repository reads, edits, tests, builds, and runtime inspection.

  ```text
  DESIGNATED_CONTAINER=yiting.TemiAgent_gpu_all
  PROJECT_ROOT_IN_CONTAINER=/TemiAgent
  DEFAULT_SHELL_COMMAND=docker exec -it yiting.TemiAgent_gpu_all bash
  ```

- Mosquitto only when running the corresponding broker-backed checks. A live
  LM Studio provider, Android application, or Temi robot is not required for
  source setup or hardware-free validation.

Observed tool versions and environment assumptions are maintained in the
[developer setup guide](docs/operations/developer_setup.md); they are not all
locked by this repository.

### Clone and reconstruct published sources

From an empty clone parent inside the designated container:

```bash
docker exec -it yiting.TemiAgent_gpu_all bash
export TEMIAGENT_REPO_URL=https://github.com/YI-TING-EE13/TemiAgent.git
export REPO_ROOT="$PWD/TemiAgent"
git clone --branch main --single-branch "$TEMIAGENT_REPO_URL" "$REPO_ROOT"
cd "$REPO_ROOT"
python3 tools/run_bounded_process.py --timeout-seconds 120 --kill-grace-seconds 2 -- git submodule update --init --recursive --depth=1
git submodule status --recursive
./scripts/bootstrap --sources
```

`bootstrap --sources` reconstructs the reviewed external source pins and the
generated llama.cpp source checkout when its prerequisites are available. It
does not install every runtime environment, build every executable, download
model weights, configure a private deployment, or contact Android.

### Provision module environments

Use the source-defined and locked setup commands:

```bash
(cd hermes_temi_bridge && uv sync --frozen --extra mqtt)
(cd temi_backend && uv sync --frozen)
(cd anomaly_detection && uv sync --frozen)
(cd hermes-agent && ./setup-hermes.sh)
./scripts/bootstrap --check
```

The Hermes setup entry point owns the required `hermes-agent/venv` layout.
Do not replace it with a bare `uv sync`, copy an environment from another
checkout, or use a canonical dirty worktree as a dependency source. If
required artifacts are absent, follow the [developer setup and provisioning
procedure](docs/operations/developer_setup.md) and stop at its documented
readiness boundary.

## Configuration

Keep deployment values, credentials, and owner-specific paths out of Git.
The [Demo configuration reference](docs/operations/demo_configuration_reference.md)
is the authority for keys and secrets.

| Configuration or artifact | Owner | Repository expectation |
| --- | --- | --- |
| Tracked config templates and manifests | Repository maintainers | Safe defaults and schemas only; no secrets or private endpoints. |
| Private Demo environment created by `./scripts/demo init-config` | Runtime owner | Ignored, owner-only state under the checkout's `.runtime/`; use a private production config for live deployment. |
| Python/uv environments and Hermes runtime environment | Source/bootstrap owner | Generated from the documented lockfiles and `hermes-agent/setup-hermes.sh`; not copied from an unrelated checkout. |
| llama.cpp build, model weights, caches, and GPU setup | Perception/runtime owner | Generated or externally provisioned; a clean clone does not imply that the binary or weights exist. |
| LM Studio and its model/cache/GPU | External service owner | The production lifecycle checks an external provider and does not start, stop, reconfigure, or adopt it. |
| MQTT broker | Explicit configuration owner | May be an external/reused broker or an explicitly lifecycle-managed mock; unknown listeners are never adopted. |
| Android application, Temi device, and device assets | External device owner | Outside this repository and outside ordinary source validation. |

The default `newcomer_mock` profile is intended for controlled local doubles.
It is not evidence that production dependencies, a physical device, or a
model-backed deployment are ready.

## Usage

### Development validation

After source and dependency provisioning, use read-only readiness checks and
the repository's validators:

```bash
cd "$REPO_ROOT"
./scripts/bootstrap --check
./scripts/demo init-config --profile newcomer_mock
./scripts/demo --config "$REPO_ROOT/.runtime/demo/demo.env" --json doctor
python3 tools/validate_documentation.py
python3 -m unittest tools.tests.test_validate_documentation
git diff --check
```

The `doctor` command is diagnostic and does not start services or publish
MQTT. Do not start long-running services merely to validate documentation or
source changes. The [verification and acceptance guide](docs/operations/verification_and_acceptance.md)
defines the broader hardware-free, integration, runtime, and external test
matrix.

### Explicitly authorized Demo runtime

The `scripts/demo` lifecycle is for an owner-configured and separately
authorized runtime only. Its complete ownership, identity, health, rollback,
and `start → status → stop` procedure is defined by the
[Demo operator guide](docs/operations/DEMO_OPERATOR_GUIDE.md). Reading this
README does not authorize a live service transition, MQTT publication,
external-provider operation, Android/Temi action, or physical movement.

## Project Structure

```text
.
├── anomaly_detection/       # experimental perception and viewer
├── hermes-agent/             # formal Hermes submodule
├── hermes-skills/            # reviewable Temi skill mirror
├── hermes_temi_bridge/       # canonical safety and dispatch boundary
├── temi_backend/             # legacy compatibility route
├── temi_shared/              # event metadata and shared-path contracts
├── tools/                    # validators, bootstrap, lifecycle, and E2E tools
├── scripts/                  # stable CLI entry points
├── mqtt/                     # broker configuration/topic reference
├── docs/                     # architecture, operations, governance, evidence
└── AGENTS.md                 # contributor and agent safety contract
```

## Testing and Validation

Use the repository-defined commands and record exact commands and results in
the relevant handover or Pull Request packet.

| Evidence level | Meaning | Representative checks |
| --- | --- | --- |
| `SOURCE / UNIT` | Deterministic source, schema, validator, and module tests | Documentation validator, Bridge tests, backend tests, anomaly tests, and tools tests. |
| `INTEGRATION` | Hardware-free composition with mocks or synthetic fixtures | `tools/e2e_test_runner.py` and `tools/media_v11_fake_e2e.py`. |
| `RUNTIME` | A configured host lifecycle and its exact ownership/health evidence | `bootstrap --check`, `demo ... doctor`, and an explicitly authorized lifecycle rehearsal. |
| `DEVICE / EXTERNAL` | External LM/MQTT, Android, Temi, GPU, or physical evidence | Separate authorization, environment, and evidence are required. |
| `NOT VERIFIED` | No executable evidence has been established for the claim | Do not infer live or physical behavior from source or hardware-free tests. |

Useful hardware-free commands include:

```bash
python3 -m unittest tools.tests.test_validate_documentation
(cd hermes_temi_bridge && uv run --locked --offline python -m unittest discover -s tests)
(cd temi_backend && uv run --locked --offline pytest)
(cd anomaly_detection && uv run --locked --offline python -m unittest discover -s tests)
python3 -m unittest discover -s tools/tests
python3 tools/e2e_test_runner.py
python3 tools/media_v11_fake_e2e.py
```

This repository currently has no configured GitHub Actions workflow. The
validation model is conditional:

```ini
CI_MODEL=CONDITIONAL
CURRENT_REPO_CI=NOT_CONFIGURED
LOCAL_VALIDATION_REQUIRED_WITHOUT_CI=YES
```

When CI is configured, required CI checks must pass before merge. Until then,
the authoritative repository-local validators and tests are required and
their exact results must be reported. `NO_CHECKS_REPORTED` is not a successful
CI result and is not, by itself, a CI failure.

## Academic-Lab Workflow

The concise governance path is:

```text
PROJECT-01 research direction
  -> GitHub Issue
  -> change classification
  -> development branch
  -> maintainer-owned implementation
  -> required repository validation
  -> handoff to PROJECT-01 for PR/review management
  -> merge
  -> runtime/integration/device acceptance when required
```

The full role, change-class, evidence, and merge model is in the
[Academic-Lab development workflow](docs/project/DEVELOPMENT_WORKFLOW.md).
The Codex/successor maintainer path is branch → implementation → validation →
commit → push. PROJECT-01 owns Pull Request creation, review coordination,
and the merge decision. The [student handover](docs/project/STUDENT_HANDOVER.md)
provides the operational reading path.

## Requirements and Limitations

Interpret repository claims using the following state vocabulary:

| State | Meaning |
| --- | --- |
| `IMPLEMENTED` | The corresponding source path exists; it does not imply live or physical acceptance. |
| `HARDWARE_FREE_VERIFIED` | Repository tests or mock evidence passed without Android/Temi hardware. |
| `EXPERIMENTAL` / `OPTIONAL` | Research or viewer behavior is available only under its provisioned configuration and is not a general safety path. |
| `DEMO_ONLY` | Synthetic fixtures or bounded demonstrations; not a clinical, emergency, or production-care capability. |
| `EXTERNAL` / `CONFIG_DEPENDENT` | The result depends on an owner-controlled service, model, device, or private configuration. |
| `NOT_VERIFIED` | The repository has no sufficient executable evidence for the claim. |

Important limitations:

- A clean clone contains source and tracked contracts, not private configs,
  model weights, generated runtime artifacts, logs, or device assets.
- Hermes submodule access, locked environments, the optional llama-server,
  external LM Studio, MQTT, Android, Temi, and GPU resources each have their
  own provisioning and acceptance boundaries.
- Physical Android/Temi behavior, broad live media/viewer behavior, and broad
  end-to-end care workflows are not implied by hardware-free checks.
- The system does not implement or verify medical diagnosis, emergency
  notification, guaranteed fall detection, or unsupervised autonomous care.
- The root repository intentionally has no published open-source license;
  see [License](#license).

## Evidence and Current Boundaries

Use the [documentation index](docs/README.md) to select the current authority:

- [`docs/CURRENT_STATUS.md`](docs/CURRENT_STATUS.md) owns date-sensitive
  acceptance and capability status.
- [`docs/REPOSITORY_MAP.md`](docs/REPOSITORY_MAP.md) owns repository layout and
  ownership orientation.
- [`docs/DOCUMENT_AUTHORITY_MAP.md`](docs/DOCUMENT_AUTHORITY_MAP.md) defines
  documentation precedence and synchronization obligations.
- The [verification guide](docs/operations/verification_and_acceptance.md)
  owns evidence classification and coverage gaps.
- The [Demo operator guide](docs/operations/DEMO_OPERATOR_GUIDE.md) owns live
  lifecycle procedures; this README is not a substitute for it.

Acceptance snapshots are scoped to the exact source, artifact, configuration,
host, and authorization that produced them. They are not portable defaults or
permission to operate a device.

## Future Work

Possible future work includes stronger clean-clone reproducibility, additional
hardware-free contract coverage, separately authorized Android/Temi
acceptance, and further evaluation of optional perception and media paths.
These are research directions, not promises of current capability.

## Contributing

Read [`AGENTS.md`](AGENTS.md), the [Academic-Lab workflow](docs/project/DEVELOPMENT_WORKFLOW.md),
and the [student handover](docs/project/STUDENT_HANDOVER.md) before making a
change. The normal path is:

```text
Issue -> change classification -> development branch -> implementation
      -> required validation and evidence -> commit -> push
      -> PROJECT-01 PR/review/merge management
```

Keep source, runtime, schema, dependency, lockfile, and device changes within
their documented ownership. A contract change must update its authoritative
runtime definition, producers, consumers, validators, tests, and reader
documentation together; do not change runtime behavior from README text.
Never commit secrets, private endpoints, credentials, identifiable media, or
runtime data.

## License

`NO_LICENSE`: the root repository does not currently publish an open-source
license. Do not infer reuse rights or add a license statement without a
maintainer decision. External Hermes, llama.cpp, and other dependency licenses
remain governed by their respective source and manifest files.

## Acknowledgements

Temi, Hermes, and llama.cpp are external projects or platforms used at their
documented integration boundaries. Their provenance and licensing information
is maintained in the relevant dependency documentation and manifests.
