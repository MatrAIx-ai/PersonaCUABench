#!/usr/bin/env bash
# Run every (persona x task) cell, one cell per python process.
#
# One process per cell is deliberate: process exit is what actually frees
# Chrome's memory, and a long loop inside one process ran machines out of it.
# --skip-existing makes the whole grid resumable: after any interruption, run
# this script again and only unfinished cells run.
#
#   bash odyssey/run_grid.sh                          # all personas, all tasks
#   PERSONAS="none elderly-novice" bash odyssey/run_grid.sh
#   TASKS="1 4" bash odyssey/run_grid.sh             # only your assigned tasks
#   nohup bash odyssey/run_grid.sh > grid.log 2>&1 &  # detached, survives the terminal
set -u
cd "$(dirname "$0")/.."

PERSONAS="${PERSONAS:-none travel-expert elderly-novice}"
N_TASKS=$(python3 -c "import json; print(len(json.load(open('odyssey/tasks.json'))))")
TASKS="${TASKS:-$(seq 1 "$N_TASKS")}"

for persona in $PERSONAS; do
  for t in $TASKS; do
    python3 -u odyssey/run.py --task "$t" --persona "$persona" \
      --headless --skip-existing "$@"
    # make sure this cell's Chrome is gone before the next one starts
    pkill -f "odyssey/.chrome-profile" 2>/dev/null
    for _ in $(seq 1 20); do
      pgrep -f "odyssey/.chrome-profile" >/dev/null || break
      sleep 1
    done
  done
done
echo "GRID DONE"
