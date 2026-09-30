#!/usr/bin/env bash
# How far along is judge_all, and when will it finish?
#
#   python src/judge_all.py > logs/judge_all.log 2>&1 &
#   bash src/judge_progress.sh logs/judge_all.log
#
# Reads the log judge_all writes: one START line with the total, one DONE line
# per record. The arithmetic is in python because `date -d` is GNU-only and this
# is run on macOS as often as on the server.
set -u
LOG="${1:-logs/judge_all.log}"
[[ -f "$LOG" ]] || { echo "no log at $LOG" >&2; exit 2; }

"${PY:-python3}" - "$LOG" <<'PY'
import re, sys, time
from pathlib import Path

lines = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
start = next((l for l in lines if " START " in l), None)
if not start:
    raise SystemExit("the log has no START line yet")
total = int(re.search(r"todo=(\d+)", start).group(1))
done = sum(1 for l in lines if " DONE [" in l)
failed = sum(1 for l in lines if "FAIL" in l or "ERROR:" in l)


def stamp(line: str) -> float | None:
    match = re.match(r"(\d{2}):(\d{2}):(\d{2})", line)
    if not match:
        return None
    h, m, s = (int(g) for g in match.groups())
    return h * 3600 + m * 60 + s


t0, last = stamp(start), next((stamp(l) for l in reversed(lines) if " DONE [" in l), None)
print(f"{done}/{total} judged, {failed} with an error")
if done and t0 is not None and last is not None:
    elapsed = (last - t0) % 86400          # wraps at midnight
    per = elapsed / done
    left = per * (total - done)
    finish = time.strftime("%H:%M", time.localtime(time.time() + left))
    print(f"{per:.1f}s per record, ~{left / 60:.0f}m left, finishing about {finish}")
if "FINISHED" in "\n".join(lines[-3:]):
    print("FINISHED")
PY
