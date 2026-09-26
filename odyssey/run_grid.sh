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
#   JOBS=4 bash odyssey/run_grid.sh                   # four cells at a time
#   nohup bash odyssey/run_grid.sh > grid.log 2>&1 &  # detached, survives the terminal
#
# JOBS>1 runs that many cells concurrently, each in its own Chrome profile so the
# instances cannot fight over one user-data-dir. Budget roughly 1.5 GB of RAM per
# worker -- Chrome, not the model, is what runs a machine out of memory -- and
# expect the provider to rate-limit; 429s are retried with backoff. Per-cell
# output goes to logs/cells/<suite>-<persona>-<task>.log so concurrent runs do
# not interleave into one unreadable stream.
set -u
cd "$(dirname "$0")/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"
JOBS="${JOBS:-1}"
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
FAILED_MARK="logs/cells/.failed"
cell_profile() {   # one Chrome per worker, or two workers corrupt one profile
  printf 'artifacts/chrome-profiles/parallel/%s/%s/%s' \
    "${TASK_SUITE:-adhoc}" "$1" "$2"
}

run_cell() {
  local persona="$1" task="$2" extra=()
  if [[ "$JOBS" -gt 1 ]]; then
    extra=(--profile "$(cell_profile "$persona" "$task")")
    mkdir -p logs/cells
    local log="logs/cells/${TASK_SUITE:-adhoc}-$persona-${task:0:12}.log"
    if "$PYTHON_BIN" -u odyssey/run.py "${ROUTE_ARGS[@]:1}" \
        --task "$task" --persona "$persona" --headless --skip-existing \
        "${extra[@]}" "${EXTRA_ARGS[@]:1}" > "$log" 2>&1; then
      grep -E '^score|^skip|^UNSCORED|^UNJUDGED' "$log" | tail -1 |
        sed "s|^|$persona ${task:0:12}: |"
      return 0
    fi
    echo "FAILED $persona ${task:0:12} (see $log)" >&2
    # A background job's status is not waited on individually (bash 3.2 has no
    # `wait -n`), so failures are collected through this marker instead.
    : > "$FAILED_MARK"
    return 1
  fi
  "$PYTHON_BIN" -u odyssey/run.py "${ROUTE_ARGS[@]:1}" \
    --task "$task" --persona "$persona" --headless --skip-existing \
    "${EXTRA_ARGS[@]:1}"
}

if [[ "$JOBS" -gt 1 ]]; then
  mkdir -p logs/cells
  rm -f "$FAILED_MARK"
fi
for persona in $PERSONAS; do
  for t in $TASKS; do
    if [[ "$JOBS" -gt 1 ]]; then
      # Wait for a free slot. Polling rather than `wait -n` keeps this working
      # on the bash 3.2 that macOS still ships.
      while (( $(jobs -rp | wc -l) >= JOBS )); do sleep 2; done
      run_cell "$persona" "$t" &
    else
      run_cell "$persona" "$t" || GRID_STATUS=1
    fi
  done
done
if [[ "$JOBS" -gt 1 ]]; then
  wait
  [[ -f "$FAILED_MARK" ]] && GRID_STATUS=1
  rm -f "$FAILED_MARK"
fi
if [[ $GRID_STATUS -ne 0 ]]; then
  echo "GRID COMPLETED WITH FAILED CELLS" >&2
  exit "$GRID_STATUS"
fi
echo "GRID DONE"
