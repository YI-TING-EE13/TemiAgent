#!/usr/bin/env python3
"""Verify the formal Hermes team submodule and patch contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from bounded_process import BoundedProcessResult, run_bounded_command
except ImportError:
    from tools.bounded_process import BoundedProcessResult, run_bounded_command


AUTHORIZED_ORIGINAL_UPSTREAM = "https://github.com/NousResearch/hermes-agent.git"
AUTHORIZED_TEAM_REMOTE = "https://github.com/YI-TING-EE13/hermes-agent.git"
AUTHORIZED_BASE_COMMIT = "a0fedfbb1b7eab8db6c8aaa187f8c35cbf12f3e2"
AUTHORIZED_BASE_TREE = "bda69c575e65725bf9264dd1288a63093cea3cc3"
AUTHORIZED_FINAL_TREE = "47e9f1411e585769c055d0c6ee4417bebcdc6f70"
AUTHORIZED_LICENSE_IDENTIFIER = "MIT"
AUTHORIZED_COPYRIGHT = "Copyright (c) 2025 Nous Research"
REQUIRED_PATCH_COUNT = 10
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class HermesSubmoduleVerificationError(RuntimeError):
    """Raised when the formal Hermes dependency contract is not satisfied."""


@dataclass(frozen=True)
class SubmoduleVerificationState:
    """Git and filesystem observations used to validate one submodule."""

    configured_path: str | None
    configured_url: str | None
    configured_branch: str | None
    root_gitlink: str | None
    checkout_present: bool
    checkout_origin: str | None
    checkout_commit: str | None
    base_object_available: bool
    actual_base_tree: str | None
    checkout_tree: str | None
    base_is_ancestor: bool
    checkout_dirty: bool
    alternates_present: bool


@dataclass(frozen=True)
class HermesSubmoduleEvidence:
    """Machine-readable result of formal submodule validation."""

    path: str
    url: str
    root_gitlink: str
    checkout_commit: str
    base_tree: str
    checkout_tree: str
    state: str


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HermesSubmoduleVerificationError(
            f"HERMES_SUBMODULE_MANIFEST_INVALID: cannot read {manifest_path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: manifest must be an object"
        )
    return value


def _safe_relative_path(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value.startswith("/")
        or ".." in PurePosixPath(value).parts
    ):
        raise HermesSubmoduleVerificationError(
            f"HERMES_SUBMODULE_MANIFEST_INVALID: {field} must be a safe relative path"
        )
    return value


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate immutable identities and shape of the root manifest."""

    required = (
        "format_version",
        "upstream_url",
        "team_remote",
        "submodule_path",
        "submodule_url",
        "base_commit",
        "runtime_path",
        "integration_branch",
        "target_tree_sha",
        "expected_base_tree",
        "contract_semantics",
        "license_path",
        "license_status",
        "license_identifier",
        "copyright",
        "license_sha256",
        "license_blob_sha",
        "required_paths",
        "patch_count",
        "patches",
    )
    missing = [key for key in required if key not in manifest]
    if missing:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: missing " + ", ".join(missing)
        )
    if manifest["format_version"] != "temiagent.hermes.reconstruction.v1":
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: unsupported format_version"
        )
    if manifest["upstream_url"] != AUTHORIZED_ORIGINAL_UPSTREAM:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: original upstream URL mismatch"
        )
    if manifest["team_remote"] != AUTHORIZED_TEAM_REMOTE:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: team remote mismatch"
        )
    if manifest["submodule_url"] != AUTHORIZED_TEAM_REMOTE:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: submodule URL mismatch"
        )
    submodule_path = _safe_relative_path(manifest["submodule_path"], "submodule_path")
    runtime_path = _safe_relative_path(manifest["runtime_path"], "runtime_path")
    if submodule_path != runtime_path or submodule_path != "hermes-agent":
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: runtime and canonical submodule paths differ"
        )
    if manifest["base_commit"] != AUTHORIZED_BASE_COMMIT:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: pinned base commit mismatch"
        )
    if not _SHA1.fullmatch(str(manifest["base_commit"])):
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: base_commit must be a SHA-1"
        )
    if manifest["expected_base_tree"] != AUTHORIZED_BASE_TREE:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: expected base tree mismatch"
        )
    if not _SHA1.fullmatch(str(manifest["expected_base_tree"])):
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: expected_base_tree must be a SHA-1"
        )
    if manifest["target_tree_sha"] != AUTHORIZED_FINAL_TREE:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: expected final tree mismatch"
        )
    if not _SHA1.fullmatch(str(manifest["target_tree_sha"])):
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: target_tree_sha must be a SHA-1"
        )
    if manifest["contract_semantics"] != "PINNED_BASE_PLUS_PATCHED_WORKTREE":
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: unsupported contract semantics"
        )
    if not isinstance(manifest["integration_branch"], str) or not manifest[
        "integration_branch"
    ]:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: integration_branch is required"
        )
    license_path = _safe_relative_path(manifest["license_path"], "license_path")
    if license_path != "LICENSE":
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: license_path must be LICENSE"
        )
    if manifest["license_status"] != "VERIFIED":
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_LICENSE_UNVERIFIED: manifest license_status is not VERIFIED"
        )
    if manifest["license_identifier"] != AUTHORIZED_LICENSE_IDENTIFIER:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: license identifier mismatch"
        )
    if manifest["copyright"] != AUTHORIZED_COPYRIGHT:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: copyright identity mismatch"
        )
    if not _SHA256.fullmatch(str(manifest["license_sha256"])):
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: license_sha256 is required"
        )
    if not _SHA1.fullmatch(str(manifest["license_blob_sha"])):
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: license_blob_sha is required"
        )
    required_paths = manifest["required_paths"]
    if not isinstance(required_paths, list) or not required_paths:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: required_paths must be non-empty"
        )
    for required_path in required_paths:
        _safe_relative_path(required_path, "required_paths entry")
    if manifest["patch_count"] != REQUIRED_PATCH_COUNT:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: patch_count must be 10"
        )
    patches = manifest["patches"]
    if not isinstance(patches, list) or len(patches) != REQUIRED_PATCH_COUNT:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MANIFEST_INVALID: exactly ten patches are required"
        )
    seen: set[str] = set()
    for patch in patches:
        if not isinstance(patch, dict):
            raise HermesSubmoduleVerificationError(
                "HERMES_SUBMODULE_MANIFEST_INVALID: patch entries must be objects"
            )
        filename = _safe_relative_path(patch.get("file"), "patch file")
        if filename in seen:
            raise HermesSubmoduleVerificationError(
                "HERMES_SUBMODULE_MANIFEST_INVALID: duplicate patch file"
            )
        seen.add(filename)
        if not _SHA256.fullmatch(str(patch.get("sha256", ""))):
            raise HermesSubmoduleVerificationError(
                f"HERMES_SUBMODULE_MANIFEST_INVALID: invalid SHA-256 for {filename}"
            )
    return manifest


def _git_result(checkout: Path, *arguments: str) -> BoundedProcessResult:
    try:
        result = run_bounded_command(
            ["git", "-C", str(checkout), *arguments],
            timeout_seconds=10,
            kill_grace_seconds=1,
        )
    except (OSError, ValueError) as exc:
        raise HermesSubmoduleVerificationError(
            f"HERMES_SUBMODULE_GIT_FAILED: git {' '.join(arguments)}: {exc}"
        ) from exc
    if result.timed_out:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_GIT_TIMEOUT: "
            f"git {' '.join(arguments)} exceeded 10s; owned process group cleaned"
        )
    return result


def _git_text(checkout: Path, *arguments: str) -> str:
    result = _git_result(checkout, *arguments)
    if result.returncode != 0:
        detail = result.output.strip()
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_GIT_FAILED: "
            f"git {' '.join(arguments)} failed: {detail or 'unknown error'}"
        )
    return result.output.strip()


def _git_optional_text(checkout: Path, *arguments: str) -> str | None:
    result = _git_result(checkout, *arguments)
    if result.returncode != 0:
        return None
    return result.output.strip()


def _git_is_ancestor(checkout: Path, ancestor: str, descendant: str) -> bool:
    result = _git_result(checkout, "merge-base", "--is-ancestor", ancestor, descendant)
    if result.returncode not in (0, 1):
        detail = result.output.strip()
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_GIT_FAILED: merge-base check failed: "
            f"{detail or 'unknown error'}"
        )
    return result.returncode == 0


def _gitmodules_state(root: Path, submodule_path: str) -> tuple[str, str, str | None]:
    gitmodules = root / ".gitmodules"
    if not gitmodules.is_file() or gitmodules.is_symlink():
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_MISSING: .gitmodules is absent or not a regular file"
        )
    result = _git_result(
        root,
        "config",
        "--file",
        str(gitmodules),
        "--get-regexp",
        r"^submodule\..+\.(path|url|branch)$",
    )
    if result.returncode != 0:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_INVALID: .gitmodules has no readable submodule entries"
        )
    entries: dict[str, dict[str, str]] = {}
    for line in result.output.splitlines():
        key, separator, value = line.partition(" ")
        if not separator:
            continue
        match = re.fullmatch(r"submodule\.(.+)\.(path|url|branch)", key)
        if match is None:
            continue
        entries.setdefault(match.group(1), {})[match.group(2)] = value
    matches = [
        values
        for values in entries.values()
        if values.get("path") == submodule_path
    ]
    if len(matches) != 1:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_INVALID: canonical submodule path must have exactly one entry"
        )
    values = matches[0]
    if "url" not in values:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_INVALID: canonical submodule URL is missing"
        )
    if "branch" in values:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_FLOATING_BRANCH: branch metadata is not accepted"
        )
    return values["path"], values["url"], values.get("branch")


def validate_submodule_state(
    manifest: dict[str, Any], state: SubmoduleVerificationState
) -> str:
    """Validate one observed root/submodule state without doing Git I/O."""

    validate_manifest(manifest)
    submodule_path = manifest["submodule_path"]
    if state.configured_path != submodule_path:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_PATH_MISMATCH: .gitmodules path does not match manifest"
        )
    if state.configured_url != AUTHORIZED_TEAM_REMOTE:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_REMOTE_MISMATCH: .gitmodules URL is not the authorized team remote"
        )
    if state.configured_branch is not None:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_FLOATING_BRANCH: branch metadata is not accepted"
        )
    if state.root_gitlink != manifest["base_commit"]:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_PIN_MISMATCH: root gitlink is not the pinned base commit"
        )
    if not state.checkout_present:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_UNINITIALIZED: run git submodule update --init --recursive"
        )
    if state.checkout_origin != AUTHORIZED_TEAM_REMOTE:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_REMOTE_MISMATCH: checkout origin is not the authorized team remote"
        )
    if not state.base_object_available:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_PIN_MISSING: pinned base object is unavailable"
        )
    if state.actual_base_tree != manifest["expected_base_tree"]:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_BASE_TREE_MISMATCH: fetched base tree differs from manifest"
        )
    if state.checkout_dirty:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_DIRTY: refusing to reconstruct over a dirty checkout"
        )
    if state.alternates_present:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_ALTERNATES_FORBIDDEN: object alternates are not accepted"
        )
    if state.checkout_commit is None or state.checkout_tree is None:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_INVALID: checkout identity is unavailable"
        )
    base_commit = manifest["base_commit"]
    if state.checkout_tree == manifest["expected_base_tree"]:
        if state.checkout_commit != base_commit:
            raise HermesSubmoduleVerificationError(
                "HERMES_SUBMODULE_PIN_MISMATCH: checkout is not the exact pinned base commit"
            )
        return "BASE"
    if state.checkout_tree != manifest["target_tree_sha"]:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_FINAL_TREE_MISMATCH: checkout tree is not the expected final tree"
        )
    if not state.base_is_ancestor:
        raise HermesSubmoduleVerificationError(
            "HERMES_SUBMODULE_PIN_MISMATCH: reconstructed checkout is not based on the pinned commit"
        )
    return "RECONSTRUCTED"


def _root_gitlink(root: Path, submodule_path: str) -> str | None:
    lines = _git_text(root, "ls-files", "--stage", "--", submodule_path).splitlines()
    if len(lines) != 1:
        return None
    fields = lines[0].split()
    if len(fields) < 4 or fields[0] != "160000":
        return None
    return fields[1]


def _alternates_present(checkout: Path) -> bool:
    objects = Path(_git_text(checkout, "rev-parse", "--git-path", "objects"))
    if not objects.is_absolute():
        objects = checkout / objects
    alternate_file = objects / "info" / "alternates"
    if alternate_file.exists() or alternate_file.is_symlink():
        return True
    configured = _git_optional_text(
        checkout, "config", "--get", "core.alternateObjectDirectories"
    )
    return bool(configured)


def verify_submodule_contract(
    root: Path, manifest_path: Path
) -> HermesSubmoduleEvidence:
    """Read and validate the root gitlink and its initialized submodule."""

    manifest = validate_manifest(_load_manifest(manifest_path))
    submodule_path = manifest["submodule_path"]
    configured_path, configured_url, configured_branch = _gitmodules_state(
        root, submodule_path
    )
    runtime = root / submodule_path
    checkout_present = runtime.exists() and (runtime / ".git").exists()
    checkout_origin: str | None = None
    checkout_commit: str | None = None
    base_object_available = False
    actual_base_tree: str | None = None
    checkout_tree: str | None = None
    base_is_ancestor = False
    checkout_dirty = False
    alternates_present = False
    if checkout_present:
        if _git_optional_text(runtime, "rev-parse", "--is-inside-work-tree") != "true":
            checkout_present = False
        else:
            checkout_origin = _git_optional_text(runtime, "remote", "get-url", "origin")
            checkout_commit = _git_optional_text(runtime, "rev-parse", "HEAD")
            base_object_available = (
                _git_result(
                    runtime,
                    "cat-file",
                    "-e",
                    f"{manifest['base_commit']}^{{commit}}",
                ).returncode
                == 0
            )
            if base_object_available:
                actual_base_tree = _git_optional_text(
                    runtime, "show", "-s", "--format=%T", manifest["base_commit"]
                )
            checkout_tree = _git_optional_text(runtime, "rev-parse", "HEAD^{tree}")
            base_is_ancestor = bool(
                checkout_commit
                and _git_is_ancestor(runtime, manifest["base_commit"], checkout_commit)
            )
            checkout_dirty = bool(_git_optional_text(runtime, "status", "--porcelain"))
            alternates_present = _alternates_present(runtime)

    state = SubmoduleVerificationState(
        configured_path=configured_path,
        configured_url=configured_url,
        configured_branch=configured_branch,
        root_gitlink=_root_gitlink(root, submodule_path),
        checkout_present=checkout_present,
        checkout_origin=checkout_origin,
        checkout_commit=checkout_commit,
        base_object_available=base_object_available,
        actual_base_tree=actual_base_tree,
        checkout_tree=checkout_tree,
        base_is_ancestor=base_is_ancestor,
        checkout_dirty=checkout_dirty,
        alternates_present=alternates_present,
    )
    state_name = validate_submodule_state(manifest, state)
    return HermesSubmoduleEvidence(
        path=submodule_path,
        url=configured_url or "",
        root_gitlink=state.root_gitlink or "",
        checkout_commit=checkout_commit or "",
        base_tree=actual_base_tree or "",
        checkout_tree=checkout_tree or "",
        state=state_name,
    )


def validate_patch_contract(root: Path, manifest: dict[str, Any]) -> tuple[Path, ...]:
    """Validate all ordered root-owned patch hashes."""

    validate_manifest(manifest)
    patch_paths: list[Path] = []
    for patch in manifest["patches"]:
        path = root / "third_party" / "hermes" / "patches" / patch["file"]
        if not path.is_file() or path.is_symlink():
            raise HermesSubmoduleVerificationError(
                f"HERMES_PATCH_MISSING: {patch['file']}"
            )
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != patch["sha256"]:
            raise HermesSubmoduleVerificationError(
                f"HERMES_PATCH_HASH_MISMATCH: {patch['file']}"
            )
        patch_paths.append(path)
    return tuple(patch_paths)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        manifest = _load_manifest(args.manifest)
        evidence = verify_submodule_contract(args.root, args.manifest)
        patch_paths = validate_patch_contract(args.root, manifest)
    except HermesSubmoduleVerificationError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    print(
        "hermes_submodule: PASS "
        f"(state={evidence.state} path={evidence.path} url={evidence.url} "
        f"base={evidence.root_gitlink} base_tree={evidence.base_tree} "
        f"checkout_tree={evidence.checkout_tree} patches={len(patch_paths)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
