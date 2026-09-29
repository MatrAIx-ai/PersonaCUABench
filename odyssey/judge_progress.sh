#!/usr/bin/env bash
# Progress of judge_all.py.  Usage: bash odyssey/judge_progress.sh [-w]   (-w: refresh every 10s)
LOG="$(dirname "$0")/../judge_all.log"
show() {
  START=$(grep -m1 START "$LOG")
  TOTAL=$(sed -n 's/.*todo=\([0-9]*\).*/\1/p' <<<"$START")
  DONE=$(grep -c '^.* DONE \[' "$LOG")
  ERRS=$(grep -c -E 'ERROR|FAIL' "$LOG")
  T0=$(date -d "$(awk '{print $1}' <<<"$START")" +%s)
  NOW=$(date +%s); [ $NOW -lt $T0 ] && T0=$((T0-86400))
  EL=$((NOW-T0))
  echo "done $DONE/$TOTAL  errors $ERRS  elapsed $((EL/60))m$((EL%60))s"
  if grep -q FINISHED "$LOG"; then echo "FINISHED"
  elif [ "$DONE" -gt 0 ]; then
    ETA=$(( EL * (TOTAL-DONE) / DONE )); echo "ETA ~$((ETA/60))m$((ETA%60))s (finish ~$(date -d "@$((NOW+ETA))" +%H:%M))"
  fi
  pgrep -f judge_all.py >/dev/null && echo "process: running" || echo "process: NOT running"
  echo "--- last 5"; grep DONE "$LOG" | tail -5
}
if [ "$1" = -w ]; then while true; do clear; show; sleep 10; done; else show; fi
