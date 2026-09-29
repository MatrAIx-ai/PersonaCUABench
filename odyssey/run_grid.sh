#!/usr/bin/env bash
# Run every (persona x task) cell, one cell per python process.
#
# One process per cell is deliberate: process exit is what actually frees
# Chrome's memory, and a long loop inside one process ran machines out of it.
# --skip-existing makes the whole grid resumable: after any interruption, run
# this script again and only unfinished cells run.
#
#   bash odyssey/run_grid.sh                          # each task's 3 assigned personas
#   PERSONAS="none event-pro" bash odyssey/run_grid.sh  # explicit override
#   TASKS="1 4" bash odyssey/run_grid.sh             # only your assigned tasks
#   CONDITION=c2 bash odyssey/run_grid.sh            # c1 (default) | c2 state | c3 oracle
#   TASK_SET=real bash odyssey/run_grid.sh           # all (default) | odysseys | real
#   SHARD_COUNT=4 SHARD_INDEX=0 bash odyssey/run_grid.sh # one parallel shard
#   nohup bash odyssey/run_grid.sh > grid.log 2>&1 &  # detached, survives the terminal
set -u
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-.venv/bin/python}"
PROFILE="${PROFILE:-$PWD/odyssey/.chrome-profile}"
SHARD_COUNT="${SHARD_COUNT:-1}"
SHARD_INDEX="${SHARD_INDEX:-0}"
CONDITION="${CONDITION:-c1}"
if ! [[ "$SHARD_COUNT" =~ ^[1-9][0-9]*$ ]] ||
   ! [[ "$SHARD_INDEX" =~ ^[0-9]+$ ]] ||
   (( SHARD_INDEX >= SHARD_COUNT )); then
  echo "invalid shard: SHARD_INDEX=$SHARD_INDEX SHARD_COUNT=$SHARD_COUNT" >&2
  exit 2
fi
# Same list and numbering as run.py: tasks.json, then tasks_real.json if present.
LIST_TASKS='
import json, os, sys
t = json.load(open("odyssey/tasks.json"))
if os.path.exists("odyssey/tasks_real.json"):
    t += json.load(open("odyssey/tasks_real.json"))
if sys.argv[1] == "ids":
    print(t[int(sys.argv[2]) - 1]["task_id"])
else:
    keep = {"all": lambda x: True, "real": lambda x: "real" in x,
            "odysseys": lambda x: "real" not in x}[sys.argv[2]]
    print(" ".join(str(i) for i, x in enumerate(t, 1) if keep(x)))
'
TASK_SET="${TASK_SET:-all}"
TASKS="${TASKS:-$($PYTHON -c "$LIST_TASKS" set "$TASK_SET")}"

cell_index=0
for t in $TASKS; do
  task_id=$($PYTHON -c "$LIST_TASKS" ids "$t")
  if [ -n "${PERSONAS:-}" ]; then
    task_personas="$PERSONAS"
  else
    task_personas="$($PYTHON -c "import json,sys; print(' '.join(json.load(open('odyssey/persona_assignments.json'))[sys.argv[1]]))" "$task_id")"
  fi
  for persona in $task_personas; do
    if (( cell_index % SHARD_COUNT != SHARD_INDEX )); then
      ((cell_index += 1))
      continue
    fi
    $PYTHON -u odyssey/run.py --task "$t" --persona "$persona" --condition "$CONDITION" \
      --headless --skip-existing --profile "$PROFILE" "$@"
    # make sure this cell's Chrome is gone before the next one starts
    # Match only a browser process.  Matching the bare profile path also kills
    # a sharded runner whose command line contains PROFILE=... .
    pkill -f -- "chrome.*--user-data-dir=$PROFILE" 2>/dev/null
    for _ in $(seq 1 20); do
      pgrep -f -- "chrome.*--user-data-dir=$PROFILE" >/dev/null || break
      sleep 1
    done
    ((cell_index += 1))
  done
done
echo "GRID DONE"
