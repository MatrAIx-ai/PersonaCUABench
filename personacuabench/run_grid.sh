#!/usr/bin/env bash
# Run selected (persona x task) cells, one isolated OSWorld run at a time.
#
#   PERSONAS="none smoke_budget_mobile" bash personacuabench/run_grid.sh
#   PERSONAS="none" TASKS="1 4" bash personacuabench/run_grid.sh
#   PERSONAS="none" RUN_ARGS="--force" bash personacuabench/run_grid.sh
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEFAULT_PYTHON="python3"
if [[ -x "$ROOT_DIR/.osworld/OSWorld/.venv/bin/python" ]]; then
  DEFAULT_PYTHON="$ROOT_DIR/.osworld/OSWorld/.venv/bin/python"
fi
PYTHON_BIN="${PYTHON_BIN:-$DEFAULT_PYTHON}"
TASKS_FILE="$ROOT_DIR/personacuabench/tasks.json"

if [[ -z "${PERSONAS:-}" ]]; then
  echo "PERSONAS is required (for example: PERSONAS=\"none expert novice\")" >&2
  exit 2
fi
if [[ ! -f "$TASKS_FILE" ]]; then
  echo "Task file not found: $TASKS_FILE" >&2
  exit 2
fi
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python executable not found: $PYTHON_BIN" >&2
  exit 2
fi

# Deliberately use whitespace splitting without eval: persona names and extra
# arguments must each be one shell word. This keeps environment input from
# being interpreted as shell code.
read -r -a PERSONA_LIST <<< "$PERSONAS"
if (( ${#PERSONA_LIST[@]} == 0 )); then
  echo "PERSONAS did not contain any persona names" >&2
  exit 2
fi

RUN_ARGV=()
if [[ -n "${RUN_ARGS:-}" ]]; then
  read -r -a RUN_ARGV <<< "$RUN_ARGS"
fi

TASK_COUNT="$($PYTHON_BIN - "$TASKS_FILE" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    tasks = json.load(handle)
if not isinstance(tasks, list) or not tasks:
    raise SystemExit(f"{path} must contain a non-empty JSON array")
print(len(tasks))
PY
)"

if [[ -n "${TASKS:-}" ]]; then
  read -r -a TASK_LIST <<< "$TASKS"
else
  TASK_LIST=()
  for ((TASK_NUMBER = 1; TASK_NUMBER <= TASK_COUNT; TASK_NUMBER++)); do
    TASK_LIST+=("$TASK_NUMBER")
  done
fi
if (( ${#TASK_LIST[@]} == 0 )); then
  echo "TASKS did not contain any task numbers" >&2
  exit 2
fi
for TASK_NUMBER in "${TASK_LIST[@]}"; do
  if [[ ! "$TASK_NUMBER" =~ ^[0-9]+$ ]] \
    || (( TASK_NUMBER < 1 || TASK_NUMBER > TASK_COUNT )); then
    echo "Invalid task number in TASKS: $TASK_NUMBER (expected 1-$TASK_COUNT)" >&2
    exit 2
  fi
done

TOTAL=$((${#TASK_LIST[@]} * ${#PERSONA_LIST[@]}))
CURRENT=0

echo "Running $TOTAL cells serially (${#TASK_LIST[@]} tasks x ${#PERSONA_LIST[@]} personas)."
for TASK_NUMBER in "${TASK_LIST[@]}"; do
  for PERSONA in "${PERSONA_LIST[@]}"; do
    CURRENT=$((CURRENT + 1))
    printf '[%d/%d] task=%d persona=%s\n' \
      "$CURRENT" "$TOTAL" "$TASK_NUMBER" "$PERSONA"
    PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}" \
      "$PYTHON_BIN" -m personacuabench.run \
      --task "$TASK_NUMBER" \
      --persona "$PERSONA" \
      --headless \
      "${RUN_ARGV[@]}"
  done
done

echo "Grid complete: $TOTAL/$TOTAL cells invoked successfully."
