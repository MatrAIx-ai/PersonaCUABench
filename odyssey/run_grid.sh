#!/usr/bin/env bash
# Run every (persona x task) cell, one cell per python process.
#
# One process per cell is deliberate: process exit is what actually frees
# Chrome's memory, and a long loop inside one process ran machines out of it.
# --skip-existing makes the whole grid resumable: after any interruption, run
# this script again and only unfinished cells run.
#
#   bash odyssey/run_grid.sh                          # suite defaults + all tasks
#   PERSONAS="none elderly-novice" bash odyssey/run_grid.sh
#   TASKS="1 4" bash odyssey/run_grid.sh             # only your assigned tasks
#   TASK_SUITE=main-original bash odyssey/run_grid.sh # another registered suite
#   TASKS_FILE=/tmp/draft.json bash odyssey/run_grid.sh
#   nohup bash odyssey/run_grid.sh > grid.log 2>&1 &  # detached, survives the terminal
set -u
cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"
TASK_SUITE="${TASK_SUITE:-}"
TASKS_FILE="${TASKS_FILE:-}"
# A sentinel keeps empty-array expansion compatible with macOS Bash 3.2 under
# `set -u`; every use below slices it back out.
EXTRA_ARGS=(__sentinel__)

# Routing flags must also be used while enumerating the grid, so consume them
# here instead of forwarding a different suite only to run.py.
while (($#)); do
  case "$1" in
    --suite)
      [[ $# -ge 2 ]] || { echo "--suite needs a value" >&2; exit 2; }
      TASK_SUITE="$2"; shift 2 ;;
    --suite=*) TASK_SUITE="${1#--suite=}"; shift ;;
    --tasks-file)
      [[ $# -ge 2 ]] || { echo "--tasks-file needs a value" >&2; exit 2; }
      TASKS_FILE="$2"; shift 2 ;;
    --tasks-file=*) TASKS_FILE="${1#--tasks-file=}"; shift ;;
    --task|--task=*|--all|--persona|--persona=*)
      echo "run_grid.sh owns task/persona axes; use TASKS= and PERSONAS= instead" >&2
      exit 2 ;;
    *) EXTRA_ARGS+=("$1"); shift ;;
  esac
done

if [[ -n "$TASK_SUITE" && -n "$TASKS_FILE" ]]; then
  echo "TASK_SUITE/--suite and TASKS_FILE/--tasks-file are mutually exclusive" >&2
  exit 2
fi

ROUTE_ARGS=(__sentinel__)
[[ -z "$TASK_SUITE" ]] || ROUTE_ARGS+=(--suite "$TASK_SUITE")
[[ -z "$TASKS_FILE" ]] || ROUTE_ARGS+=(--tasks-file "$TASKS_FILE")

if [[ -z "${PERSONAS:-}" ]]; then
  PERSONAS=$("$PYTHON_BIN" odyssey/task_router.py personas "${ROUTE_ARGS[@]:1}") || exit $?
fi
if [[ -z "${TASKS:-}" ]]; then
  # Full IDs remain stable if a later shard inserts tasks before this batch.
  TASKS=$("$PYTHON_BIN" odyssey/task_router.py selectors "${ROUTE_ARGS[@]:1}") || exit $?
fi
# Keep one task per Python process even if a caller used comma notation.
TASKS="${TASKS//,/ }"

GRID_STATUS=0
for persona in $PERSONAS; do
  for t in $TASKS; do
    if ! "$PYTHON_BIN" -u odyssey/run.py "${ROUTE_ARGS[@]:1}" \
        --task "$t" --persona "$persona" --headless --skip-existing \
        "${EXTRA_ARGS[@]:1}"; then
      GRID_STATUS=1
    fi
  done
done
if [[ $GRID_STATUS -ne 0 ]]; then
  echo "GRID COMPLETED WITH FAILED CELLS" >&2
  exit "$GRID_STATUS"
fi
echo "GRID DONE"
