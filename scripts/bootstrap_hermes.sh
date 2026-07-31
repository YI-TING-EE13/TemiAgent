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

for command in git python3 sha256sum; do
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
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
required = ("format_version", "upstream_url", "base_commit", "runtime_path", "integration_branch", "target_tree_sha", "patches")
missing = [key for key in required if key not in manifest]
if missing:
    raise SystemExit("manifest missing: " + ", ".join(missing))
if manifest["format_version"] != "temiagent.hermes.reconstruction.v1":
    raise SystemExit("unsupported Hermes reconstruction manifest version")
runtime_path = manifest["runtime_path"]
if runtime_path.startswith("/") or ".." in runtime_path.split("/"):
    raise SystemExit("runtime_path must stay below the repository root")
print(manifest["upstream_url"])
print(manifest["base_commit"])
print(runtime_path)
print(manifest["integration_branch"])
print(manifest["target_tree_sha"])
for patch in manifest["patches"]:
    print(f"PATCH\t{patch['file']}\t{patch['sha256']}")
PY
)

UPSTREAM_URL="${fields[0]}"
BASE_COMMIT="${fields[1]}"
RUNTIME_RELATIVE_PATH="${fields[2]}"
INTEGRATION_BRANCH="${fields[3]}"
EXPECTED_TREE="${fields[4]}"
RUNTIME_PATH="$ROOT/$RUNTIME_RELATIVE_PATH"

patch_files=()
for field in "${fields[@]:5}"; do
  IFS=$'\t' read -r marker file expected_sha <<< "$field"
  [[ "$marker" == "PATCH" ]] || continue
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
done

[[ "${#patch_files[@]}" -gt 0 ]] || {
  echo "Hermes reconstruction manifest has no patches" >&2
  exit 1
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
  mkdir -p "$(dirname "$RUNTIME_PATH")"
  git clone --no-checkout "$UPSTREAM_URL" "$RUNTIME_PATH"
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

CURRENT_TREE=""
if git -C "$RUNTIME_PATH" rev-parse --verify HEAD^{tree} >/dev/null 2>&1; then
  CURRENT_TREE="$(git -C "$RUNTIME_PATH" rev-parse HEAD^{tree})"
fi
if [[ "$CURRENT_TREE" == "$EXPECTED_TREE" ]]; then
  echo "bootstrap_hermes: PASS (already reconstructed)"
  exit 0
fi

[[ "$MODE" == "--bootstrap" ]] || {
  echo "Hermes checkout tree does not match the reviewed reconstruction" >&2
  exit 1
}

if ! git -C "$RUNTIME_PATH" cat-file -e "$BASE_COMMIT^{commit}" 2>/dev/null; then
  git -C "$RUNTIME_PATH" fetch --no-tags origin "$BASE_COMMIT"
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

echo "bootstrap_hermes: PASS (reconstructed)"
