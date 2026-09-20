#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PERSONA_DIR="${MATRAIX_PERSONA_REPO:-${MATRIX_PERSONA_REPO:-$ROOT_DIR/MatrAIx-Persona-8B}}"
PIN="$(tr -d '[:space:]' < "$ROOT_DIR/reproducibility/PERSONA8B_COMMIT")"

command -v git >/dev/null || {
  echo "git is required" >&2
  exit 1
}

if [[ ! -d "$PERSONA_DIR/.git" ]]; then
  git clone https://github.com/MatrAIx-ai/MatrAIx-Persona-8B.git "$PERSONA_DIR"
fi

if ! git -C "$PERSONA_DIR" cat-file -e "$PIN^{commit}" 2>/dev/null; then
  git -C "$PERSONA_DIR" fetch origin "$PIN"
fi

CURRENT="$(git -C "$PERSONA_DIR" rev-parse HEAD)"
if [[ "$CURRENT" != "$PIN" ]]; then
  if [[ -n "$(git -C "$PERSONA_DIR" status --porcelain)" ]]; then
    echo "Refusing to change dirty Persona-8B checkout: $PERSONA_DIR" >&2
    exit 1
  fi
  git -C "$PERSONA_DIR" checkout --detach "$PIN"
fi

echo "Persona-8B ready"
echo "  path: $PERSONA_DIR"
echo "  commit: $PIN"
