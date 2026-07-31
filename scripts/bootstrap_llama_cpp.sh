#!/usr/bin/env bash
# Reconstruct the pinned upstream llama.cpp source checkout. This script never
# starts a service, installs dependencies, downloads models, or builds binaries.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$ROOT/third_party/llama_cpp/manifest.json"
MODE="${1:---bootstrap}"

if [[ "$MODE" != "--bootstrap" && "$MODE" != "--check" ]]; then
  echo "usage: ./scripts/bootstrap_llama_cpp.sh [--bootstrap|--check]" >&2
  exit 2
fi

for command in git python3; do
  command -v "$command" >/dev/null || {
    echo "missing required command: $command" >&2
    exit 1
  }
done
test -f "$MANIFEST" || {
  echo "missing llama.cpp bootstrap manifest: $MANIFEST" >&2
  exit 1
}

mapfile -t fields < <(python3 - "$MANIFEST" <<'PY'
import json
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
required = ("format_version", "upstream_url", "commit", "runtime_path", "target_tree_sha")
missing = [key for key in required if key not in manifest]
if missing:
    raise SystemExit("manifest missing: " + ", ".join(missing))
if manifest["format_version"] != "temiagent.llama-cpp.bootstrap.v1":
    raise SystemExit("unsupported llama.cpp bootstrap manifest version")
runtime_path = manifest["runtime_path"]
if runtime_path.startswith("/") or ".." in runtime_path.split("/"):
    raise SystemExit("runtime_path must stay below the repository root")
for key in ("upstream_url", "commit", "target_tree_sha"):
    if not isinstance(manifest[key], str) or not manifest[key]:
        raise SystemExit(f"manifest {key} must be a non-empty string")
print(manifest["upstream_url"])
print(manifest["commit"])
print(runtime_path)
print(manifest["target_tree_sha"])
PY
)

UPSTREAM_URL="${fields[0]}"
PINNED_COMMIT="${fields[1]}"
RUNTIME_RELATIVE_PATH="${fields[2]}"
EXPECTED_TREE="${fields[3]}"
RUNTIME_PATH="$ROOT/$RUNTIME_RELATIVE_PATH"

if [[ "$RUNTIME_RELATIVE_PATH" != "anomaly_detection/third_party/llama.cpp" ]]; then
  echo "llama.cpp runtime_path must be anomaly_detection/third_party/llama.cpp" >&2
  exit 1
fi

if [[ ! -e "$RUNTIME_PATH/.git" ]]; then
  if [[ -e "$RUNTIME_PATH" ]] && [[ -n "$(find "$RUNTIME_PATH" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    echo "refusing to replace a non-empty non-Git llama.cpp path: $RUNTIME_PATH" >&2
    exit 1
  fi
  [[ "$MODE" == "--bootstrap" ]] || {
    echo "llama.cpp checkout is absent; run ./scripts/bootstrap --llama-cpp or --sources" >&2
    exit 1
  }
  mkdir -p "$RUNTIME_PATH"
  git -C "$RUNTIME_PATH" init --quiet
  git -C "$RUNTIME_PATH" remote add origin "$UPSTREAM_URL"
  git -C "$RUNTIME_PATH" fetch --no-tags --depth=1 origin "$PINNED_COMMIT"
fi

git -C "$RUNTIME_PATH" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
  echo "llama.cpp runtime path is not a Git checkout: $RUNTIME_PATH" >&2
  exit 1
}
if [[ -n "$(git -C "$RUNTIME_PATH" status --porcelain)" ]]; then
  echo "refusing to reconstruct over a dirty llama.cpp checkout: $RUNTIME_PATH" >&2
  exit 1
fi
if [[ "$(git -C "$RUNTIME_PATH" remote get-url origin)" != "$UPSTREAM_URL" ]]; then
  echo "llama.cpp origin does not match the reviewed upstream URL" >&2
  exit 1
fi

if ! git -C "$RUNTIME_PATH" cat-file -e "$PINNED_COMMIT^{commit}" 2>/dev/null; then
  [[ "$MODE" == "--bootstrap" ]] || {
    echo "pinned llama.cpp commit is absent; run ./scripts/bootstrap --llama-cpp or --sources" >&2
    exit 1
  }
  git -C "$RUNTIME_PATH" fetch --no-tags --depth=1 origin "$PINNED_COMMIT"
fi
git -C "$RUNTIME_PATH" cat-file -e "$PINNED_COMMIT^{commit}"

CURRENT_COMMIT="$(git -C "$RUNTIME_PATH" rev-parse HEAD 2>/dev/null || true)"
CURRENT_TREE="$(git -C "$RUNTIME_PATH" rev-parse HEAD^{tree} 2>/dev/null || true)"
if [[ "$CURRENT_COMMIT" == "$PINNED_COMMIT" && "$CURRENT_TREE" == "$EXPECTED_TREE" ]]; then
  echo "bootstrap_llama_cpp: PASS (already reconstructed)"
  exit 0
fi

[[ "$MODE" == "--bootstrap" ]] || {
  echo "llama.cpp checkout does not match the reviewed pin" >&2
  exit 1
}

git -C "$RUNTIME_PATH" switch --detach "$PINNED_COMMIT"
if [[ "$(git -C "$RUNTIME_PATH" rev-parse HEAD^{tree})" != "$EXPECTED_TREE" ]]; then
  echo "llama.cpp checkout tree does not match the reviewed pin" >&2
  exit 1
fi
if [[ -n "$(git -C "$RUNTIME_PATH" status --porcelain)" ]]; then
  echo "llama.cpp reconstruction unexpectedly left a dirty checkout" >&2
  exit 1
fi

echo "bootstrap_llama_cpp: PASS (reconstructed)"
