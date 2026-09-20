#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/.osworld"
UPSTREAM_DIR="$ROOT_DIR/.upstream"
OSWORLD_DIR="$RUNTIME_DIR/OSWorld"
ODYSSEYS_DIR="$UPSTREAM_DIR/odysseys"
PIN="$(tr -d '[:space:]' < "$ROOT_DIR/reproducibility/OSWORLD_COMMIT")"
ODYSSEYS_PIN="$(tr -d '[:space:]' < "$ROOT_DIR/reproducibility/ODYSSEYS_COMMIT")"
PYTHON_VERSION="3.12.14"
UV_VERSION="0.12.13"
PYTHON_DIR="$RUNTIME_DIR/python"
UV_CACHE="$RUNTIME_DIR/uv-cache"

command -v git >/dev/null || { echo "git is required" >&2; exit 1; }
command -v uv >/dev/null || { echo "uv is required" >&2; exit 1; }
[[ "$(uv --version)" == "uv $UV_VERSION "* ]] || {
  echo "Expected uv $UV_VERSION, got: $(uv --version)" >&2
  exit 1
}
mkdir -p "$RUNTIME_DIR" "$UV_CACHE" "$UPSTREAM_DIR"

if [[ ! -d "$OSWORLD_DIR/.git" ]]; then
  git clone https://github.com/xlang-ai/OSWorld.git "$OSWORLD_DIR"
fi

if [[ ! -d "$ODYSSEYS_DIR/.git" ]]; then
  git clone https://github.com/ljang0/Odysseys.git "$ODYSSEYS_DIR"
fi

if ! git -C "$OSWORLD_DIR" cat-file -e "$PIN^{commit}" 2>/dev/null; then
  git -C "$OSWORLD_DIR" fetch origin "$PIN"
fi

CURRENT="$(git -C "$OSWORLD_DIR" rev-parse HEAD)"
if [[ "$CURRENT" != "$PIN" ]]; then
  if [[ -n "$(git -C "$OSWORLD_DIR" status --porcelain)" ]]; then
    echo "Refusing to change a dirty OSWorld checkout at $OSWORLD_DIR" >&2
    exit 1
  fi
  git -C "$OSWORLD_DIR" checkout --detach "$PIN"
fi

if ! git -C "$ODYSSEYS_DIR" cat-file -e "$ODYSSEYS_PIN^{commit}" 2>/dev/null; then
  git -C "$ODYSSEYS_DIR" fetch origin "$ODYSSEYS_PIN"
fi

ODYSSEYS_CURRENT="$(git -C "$ODYSSEYS_DIR" rev-parse HEAD)"
if [[ "$ODYSSEYS_CURRENT" != "$ODYSSEYS_PIN" ]]; then
  if [[ -n "$(git -C "$ODYSSEYS_DIR" status --porcelain)" ]]; then
    echo "Refusing to change a dirty Odysseys checkout at $ODYSSEYS_DIR" >&2
    exit 1
  fi
  git -C "$ODYSSEYS_DIR" checkout --detach "$ODYSSEYS_PIN"
fi

PATCH_FILE="$ROOT_DIR/reproducibility/patches/osworld-b875-local.patch"
if git -C "$OSWORLD_DIR" apply --reverse --check "$PATCH_FILE" 2>/dev/null; then
  : # The complete local patch is already present.
elif git -C "$OSWORLD_DIR" apply --check "$PATCH_FILE" 2>/dev/null; then
  git -C "$OSWORLD_DIR" apply "$PATCH_FILE"
else
  echo "OSWorld has a partially applied or conflicting local patch." >&2
  echo "Inspect the dirty checkout at $OSWORLD_DIR before continuing." >&2
  exit 1
fi

ODYSSEYS_PATCH_FILE="$ROOT_DIR/reproducibility/patches/odysseys-837-local.patch"
if git -C "$ODYSSEYS_DIR" apply --reverse --check "$ODYSSEYS_PATCH_FILE" 2>/dev/null; then
  : # The complete local patch is already present.
elif git -C "$ODYSSEYS_DIR" apply --check "$ODYSSEYS_PATCH_FILE" 2>/dev/null; then
  git -C "$ODYSSEYS_DIR" apply "$ODYSSEYS_PATCH_FILE"
else
  echo "Odysseys has a partially applied or conflicting local patch." >&2
  echo "Inspect the dirty checkout at $ODYSSEYS_DIR before continuing." >&2
  exit 1
fi
install -m 0644 \
  "$ROOT_DIR/integrations/osworld/azure_foundry_agent.py" \
  "$OSWORLD_DIR/mm_agents/azure_foundry_agent.py"

UV_CACHE_DIR="$UV_CACHE" UV_PYTHON_INSTALL_DIR="$PYTHON_DIR" \
  uv python install --no-bin "$PYTHON_VERSION"
PYTHON_BIN="$(UV_CACHE_DIR="$UV_CACHE" UV_PYTHON_INSTALL_DIR="$PYTHON_DIR" \
  uv python find "$PYTHON_VERSION")"
UV_CACHE_DIR="$UV_CACHE" UV_PYTHON_INSTALL_DIR="$PYTHON_DIR" \
  uv lock --directory "$OSWORLD_DIR"
EXPECTED_LOCK_SHA="$(awk '{print $1}' "$ROOT_DIR/reproducibility/OSWORLD_UV_LOCK_SHA256")"
ACTUAL_LOCK_SHA="$(shasum -a 256 "$OSWORLD_DIR/uv.lock" | awk '{print $1}')"
[[ "$ACTUAL_LOCK_SHA" == "$EXPECTED_LOCK_SHA" ]] || {
  echo "OSWorld uv.lock hash mismatch after resolution." >&2
  echo "Expected $EXPECTED_LOCK_SHA, got $ACTUAL_LOCK_SHA" >&2
  exit 1
}
UV_CACHE_DIR="$UV_CACHE" UV_PYTHON_INSTALL_DIR="$PYTHON_DIR" \
  uv sync --directory "$OSWORLD_DIR" --frozen --python "$PYTHON_BIN"

VM_ARCHIVE="$OSWORLD_DIR/vmware_vm_data/Ubuntu-arm.zip"
if [[ -f "$VM_ARCHIVE" ]]; then
  EXPECTED_VM_SHA="$(awk '{print $1}' "$ROOT_DIR/reproducibility/UBUNTU_ARM_SHA256")"
  ACTUAL_VM_SHA="$(shasum -a 256 "$VM_ARCHIVE" | awk '{print $1}')"
  [[ "$ACTUAL_VM_SHA" == "$EXPECTED_VM_SHA" ]] || {
    echo "Ubuntu ARM VM archive hash mismatch." >&2
    echo "Expected $EXPECTED_VM_SHA, got $ACTUAL_VM_SHA" >&2
    exit 1
  }
fi

"$OSWORLD_DIR/.venv/bin/python" -m py_compile \
  "$OSWORLD_DIR/mm_agents/azure_foundry_agent.py" \
  "$OSWORLD_DIR/scripts/python/run_multienv.py" \
  "$ODYSSEYS_DIR/scripts/python/run_full_trajectory_per_rubric.py"

echo "OSWorld ready"
echo "  commit: $PIN"
echo "  Odysseys commit: $ODYSSEYS_PIN"
echo "  Python: $PYTHON_VERSION"
echo "  uv: $UV_VERSION"
echo "  python: $OSWORLD_DIR/.venv/bin/python"
