#!/usr/bin/env bash
# Reconstruct the reviewed TemiAgent Hermes overlay from public upstream plus
# tracked patches. This script never starts a service or installs dependencies.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$ROOT/third_party/hermes/manifest.json"

if [[ "${1:---bootstrap}" != "--bootstrap" && "${1:---bootstrap}" != "--check" ]]; then
  echo "usage: ./scripts/bootstrap_hermes.sh [--bootstrap|--check]" >&2
  exit 2
fi
MODE="${1:---bootstrap}"

for command in git python3 sha256sum timeout; do
  command -v "$command" >/dev/null || {
    echo "missing required command: $command" >&2
    exit 1
  }
done
test -f "$MANIFEST" || {
  echo "missing Hermes reconstruction manifest: $MANIFEST" >&2
  exit 1
}

mapfile -t fields < <(python3 - "$MANIFEST" <<'PY'
import json
import re
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
required = (
    "format_version",
    "upstream_url",
    "base_commit",
    "runtime_path",
    "integration_branch",
    "target_tree_sha",
    "contract_semantics",
    "required_paths",
    "patches",
)
missing = [key for key in required if key not in manifest]
if missing:
    raise SystemExit("manifest missing: " + ", ".join(missing))
if manifest["format_version"] != "temiagent.hermes.reconstruction.v1":
    raise SystemExit("unsupported Hermes reconstruction manifest version")
runtime_path = manifest["runtime_path"]
if runtime_path.startswith("/") or ".." in runtime_path.split("/"):
    raise SystemExit("runtime_path must stay below the repository root")
if manifest["contract_semantics"] != "PINNED_BASE_PLUS_PATCHED_WORKTREE":
    raise SystemExit("unsupported Hermes reconstruction contract semantics")
if not isinstance(manifest["required_paths"], list) or not manifest["required_paths"]:
    raise SystemExit("manifest required_paths must be a non-empty list")
for required_path in manifest["required_paths"]:
    if (
        not isinstance(required_path, str)
        or not required_path
        or required_path.startswith("/")
        or ".." in required_path.split("/")
    ):
        raise SystemExit("manifest required_paths must stay below the runtime checkout")
expected_base_tree = manifest.get("expected_base_tree", "")
if expected_base_tree and not re.fullmatch(r"[0-9a-f]{40}", expected_base_tree):
    raise SystemExit("manifest expected_base_tree must be a lowercase Git tree ID")
print(manifest["upstream_url"])
print(manifest["base_commit"])
print(runtime_path)
print(manifest["integration_branch"])
print(manifest["target_tree_sha"])
print(expected_base_tree)
print(manifest["contract_semantics"])
for required_path in manifest["required_paths"]:
    print(f"REQUIRED\t{required_path}")
for patch in manifest["patches"]:
    print(f"PATCH\t{patch['file']}\t{patch['sha256']}")
PY
)

UPSTREAM_URL="${fields[0]}"
BASE_COMMIT="${fields[1]}"
RUNTIME_RELATIVE_PATH="${fields[2]}"
INTEGRATION_BRANCH="${fields[3]}"
EXPECTED_TREE="${fields[4]}"
EXPECTED_BASE_TREE="${fields[5]}"
CONTRACT_SEMANTICS="${fields[6]}"
RUNTIME_PATH="$ROOT/$RUNTIME_RELATIVE_PATH"

# Public GitHub access is an external prerequisite. Keep retries bounded so a
# rate-limited clone fails clearly and leaves only a resumable Git checkout.
MAX_FETCH_ATTEMPTS=2
FETCH_RETRY_DELAY_SECONDS=1
FETCH_TIMEOUT_SECONDS=20

fetch_pinned_base() {
  local attempt fetch_output fetch_status
  for ((attempt = 1; attempt <= MAX_FETCH_ATTEMPTS; attempt++)); do
    fetch_status=0
    fetch_output="$(timeout --signal=TERM "${FETCH_TIMEOUT_SECONDS}s" git -C "$RUNTIME_PATH" fetch --no-tags origin "$BASE_COMMIT" 2>&1)" || fetch_status=$?
    if ((fetch_status == 0)); then
      printf "%s\n" "$fetch_output"
      return 0
    fi

    if ((fetch_status == 124)); then
      if ((attempt < MAX_FETCH_ATTEMPTS)); then
        echo "PUBLIC_UPSTREAM_TIMEOUT: Hermes fetch attempt $attempt/$MAX_FETCH_ATTEMPTS exceeded ${FETCH_TIMEOUT_SECONDS}s; retrying after ${FETCH_RETRY_DELAY_SECONDS}s" >&2
        sleep "$FETCH_RETRY_DELAY_SECONDS"
      else
        echo "PUBLIC_UPSTREAM_TIMEOUT: Hermes public upstream did not respond within ${FETCH_TIMEOUT_SECONDS}s after $MAX_FETCH_ATTEMPTS attempts; retry later. The initialized checkout is resumable and no local fallback was used." >&2
        return 3
      fi
      continue
    fi

    if [[ "$fetch_output" =~ 429|[Rr]ate.?[Ll]imit|[Tt]oo[[:space:]]+[Mm]any[[:space:]]+[Rr]equests ]]; then
      if ((attempt < MAX_FETCH_ATTEMPTS)); then
        echo "PUBLIC_UPSTREAM_RATE_LIMITED: Hermes fetch attempt $attempt/$MAX_FETCH_ATTEMPTS was rate-limited; retrying after ${FETCH_RETRY_DELAY_SECONDS}s" >&2
        sleep "$FETCH_RETRY_DELAY_SECONDS"
      else
        echo "PUBLIC_UPSTREAM_RATE_LIMITED: Hermes public upstream was rate-limited after $MAX_FETCH_ATTEMPTS attempts; retry later. The initialized checkout is resumable and no local fallback was used." >&2
        return 2
      fi
    else
      echo "PUBLIC_UPSTREAM_FETCH_FAILED: Hermes public upstream fetch failed on attempt $attempt/$MAX_FETCH_ATTEMPTS" >&2
      printf "%s\n" "$fetch_output" >&2
      return 1
    fi
  done
}

patch_files=()
required_paths=()
for field in "${fields[@]:7}"; do
  IFS=$'\t' read -r marker file expected_sha <<< "$field"
  if [[ "$marker" == "REQUIRED" ]]; then
    required_paths+=("$file")
  elif [[ "$marker" == "PATCH" ]]; then
    patch_path="$ROOT/third_party/hermes/patches/$file"
    test -f "$patch_path" || {
      echo "missing tracked Hermes patch: $file" >&2
      exit 1
    }
    actual_sha="$(sha256sum "$patch_path" | awk '{print $1}')"
    [[ "$actual_sha" == "$expected_sha" ]] || {
      echo "Hermes patch checksum mismatch: $file" >&2
      exit 1
    }
    patch_files+=("$patch_path")
  fi
done

[[ "${#required_paths[@]}" -gt 0 ]] || {
  echo "Hermes reconstruction manifest has no required paths" >&2
  exit 1
}
[[ "${#patch_files[@]}" -gt 0 ]] || {
  echo "Hermes reconstruction manifest has no patches" >&2
  exit 1
}

verify_required_paths() {
  local required_path
  for required_path in "${required_paths[@]}"; do
    test -f "$RUNTIME_PATH/$required_path" || {
      echo "Hermes reconstruction is missing required path: $required_path" >&2
      return 1
    }
  done
}

if [[ ! -e "$RUNTIME_PATH/.git" ]]; then
  if [[ -e "$RUNTIME_PATH" ]] && [[ -n "$(find "$RUNTIME_PATH" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    echo "refusing to replace a non-empty non-Git Hermes path: $RUNTIME_PATH" >&2
    exit 1
  fi
  [[ "$MODE" == "--bootstrap" ]] || {
    echo "Hermes checkout is absent; run without --check to reconstruct it" >&2
    exit 1
  }
  mkdir -p "$RUNTIME_PATH"
  git -C "$RUNTIME_PATH" init --quiet
  git -C "$RUNTIME_PATH" remote add origin "$UPSTREAM_URL"
  fetch_pinned_base
fi

git -C "$RUNTIME_PATH" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "Hermes runtime path is not a Git checkout: $RUNTIME_PATH" >&2
  exit 1
}
if [[ -n "$(git -C "$RUNTIME_PATH" status --porcelain)" ]]; then
  echo "refusing to reconstruct over a dirty Hermes checkout: $RUNTIME_PATH" >&2
  exit 1
fi
if [[ "$(git -C "$RUNTIME_PATH" remote get-url origin)" != "$UPSTREAM_URL" ]]; then
  echo "Hermes origin does not match the reviewed upstream URL" >&2
  exit 1
fi

if [[ -n "$EXPECTED_BASE_TREE" ]]; then
  if ! git -C "$RUNTIME_PATH" cat-file -e "$BASE_COMMIT^{commit}" 2>/dev/null; then
    [[ "$MODE" == "--bootstrap" ]] || {
      echo "Hermes pinned base commit is absent; run without --check to reconstruct it" >&2
      exit 1
    }
    fetch_pinned_base
  fi
  ACTUAL_BASE_TREE="$(git -C "$RUNTIME_PATH" show -s --format=%T "$BASE_COMMIT")"
  if [[ "$ACTUAL_BASE_TREE" != "$EXPECTED_BASE_TREE" ]]; then
    echo "Hermes pinned base tree does not match the reviewed manifest" >&2
    exit 1
  fi
fi

CURRENT_TREE=""
if git -C "$RUNTIME_PATH" rev-parse --verify HEAD^{tree} >/dev/null 2>&1; then
  CURRENT_TREE="$(git -C "$RUNTIME_PATH" rev-parse HEAD^{tree})"
fi
if [[ "$CURRENT_TREE" == "$EXPECTED_TREE" ]]; then
  verify_required_paths
  echo "bootstrap_hermes: PASS (already reconstructed)"
  exit 0
fi

[[ "$MODE" == "--bootstrap" ]] || {
  echo "Hermes checkout tree does not match the reviewed reconstruction" >&2
  exit 1
}

if ! git -C "$RUNTIME_PATH" cat-file -e "$BASE_COMMIT^{commit}" 2>/dev/null; then
  fetch_pinned_base
fi
git -C "$RUNTIME_PATH" cat-file -e "$BASE_COMMIT^{commit}"
git -C "$RUNTIME_PATH" switch --detach "$BASE_COMMIT"
git -C "$RUNTIME_PATH" switch -C "$INTEGRATION_BRANCH" "$BASE_COMMIT"
git -C "$RUNTIME_PATH" am --3way "${patch_files[@]}"

if [[ "$(git -C "$RUNTIME_PATH" rev-parse HEAD^{tree})" != "$EXPECTED_TREE" ]]; then
  echo "Hermes reconstructed tree did not match the reviewed manifest" >&2
  exit 1
fi
if [[ -n "$(git -C "$RUNTIME_PATH" status --porcelain)" ]]; then
  echo "Hermes reconstruction unexpectedly left a dirty checkout" >&2
  exit 1
fi
verify_required_paths

echo "bootstrap_hermes: PASS (reconstructed)"
