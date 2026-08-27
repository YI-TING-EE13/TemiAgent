#!/usr/bin/env bash
# Reconstruct the reviewed TemiAgent Hermes overlay from the formal submodule
# plus tracked patches. This script never fetches a replacement source tree,
# starts a service, or installs dependencies.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$ROOT/third_party/hermes/manifest.json"

if [[ "${1:---bootstrap}" != "--bootstrap" && "${1:---bootstrap}" != "--check" ]]; then
  echo "usage: ./scripts/bootstrap_hermes.sh [--bootstrap|--check]" >&2
  exit 2
fi
MODE="${1:---bootstrap}"

for command in git python3; do
  command -v "$command" >/dev/null || {
    echo "missing required command: $command" >&2
    exit 1
  }
done
test -f "$MANIFEST" || {
  echo "missing Hermes reconstruction manifest: $MANIFEST" >&2
  exit 1
}
test -f "$ROOT/tools/verify_hermes_submodule.py" || {
  echo "missing formal Hermes submodule verifier: $ROOT/tools/verify_hermes_submodule.py" >&2
  exit 1
}
test -f "$ROOT/tools/verify_hermes_license.py" || {
  echo "missing Hermes license verifier: $ROOT/tools/verify_hermes_license.py" >&2
  exit 1
}

# The submodule is the only source-acquisition mechanism. Its URL, root
# gitlink, pinned object, base tree, patch hashes and alternate-object policy
# are checked before any patch is applied.
python3 "$ROOT/tools/verify_hermes_submodule.py" \
  --root "$ROOT" \
  --manifest "$MANIFEST"

mapfile -t fields < <(python3 - "$MANIFEST" <<'PY'
import json
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
print(manifest["base_commit"])
print(manifest["runtime_path"])
print(manifest["integration_branch"])
for required_path in manifest["required_paths"]:
    print(f"REQUIRED\t{required_path}")
for patch in manifest["patches"]:
    print(f"PATCH\t{patch['file']}")
PY
)

BASE_COMMIT="${fields[0]}"
RUNTIME_RELATIVE_PATH="${fields[1]}"
INTEGRATION_BRANCH="${fields[2]}"
RUNTIME_PATH="$ROOT/$RUNTIME_RELATIVE_PATH"

required_paths=()
patch_files=()
for field in "${fields[@]:3}"; do
  IFS=$'\t' read -r marker value <<< "$field"
  if [[ "$marker" == "REQUIRED" ]]; then
    required_paths+=("$value")
  elif [[ "$marker" == "PATCH" ]]; then
    patch_files+=("$ROOT/third_party/hermes/patches/$value")
  fi
done

verify_required_paths() {
  local required_path
  for required_path in "${required_paths[@]}"; do
    test -f "$RUNTIME_PATH/$required_path" || {
      echo "Hermes reconstruction is missing required path: $required_path" >&2
      return 1
    }
  done
}

verify_hermes_license() {
  local verifier_mode="${1-}"
  local -a verifier_args=(
    --manifest "$MANIFEST"
    --checkout "$RUNTIME_PATH"
    --base-commit "$BASE_COMMIT"
  )
  if [[ "$verifier_mode" == "--base-only" ]]; then
    verifier_args+=(--base-only)
  elif [[ -n "$verifier_mode" ]]; then
    echo "invalid Hermes license verifier mode: $verifier_mode" >&2
    return 2
  fi
  python3 "$ROOT/tools/verify_hermes_license.py" "${verifier_args[@]}"
}

verify_hermes_license --base-only

CURRENT_TREE="$(git -C "$RUNTIME_PATH" rev-parse HEAD^{tree})"
if [[ "$CURRENT_TREE" == "$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["target_tree_sha"])' "$MANIFEST")" ]]; then
  verify_hermes_license
  verify_required_paths
  echo "bootstrap_hermes: PASS (already reconstructed from formal submodule)"
  exit 0
fi

[[ "$MODE" == "--bootstrap" ]] || {
  echo "Hermes submodule is at the pinned base; run --bootstrap to apply the reviewed patch series" >&2
  exit 1
}

CURRENT_COMMIT="$(git -C "$RUNTIME_PATH" rev-parse HEAD)"
[[ "$CURRENT_COMMIT" == "$BASE_COMMIT" ]] || {
  echo "Hermes submodule is neither the pinned base nor the expected reconstruction" >&2
  exit 1
}

git -C "$RUNTIME_PATH" switch --detach "$BASE_COMMIT"
git -C "$RUNTIME_PATH" switch -C "$INTEGRATION_BRANCH" "$BASE_COMMIT"
git -C "$RUNTIME_PATH" am --3way "${patch_files[@]}"

python3 "$ROOT/tools/verify_hermes_submodule.py" \
  --root "$ROOT" \
  --manifest "$MANIFEST"
verify_hermes_license
verify_required_paths

if [[ -n "$(git -C "$RUNTIME_PATH" status --porcelain)" ]]; then
  echo "Hermes reconstruction unexpectedly left a dirty submodule checkout" >&2
  exit 1
fi

echo "bootstrap_hermes: PASS (reconstructed from formal submodule)"
