#!/usr/bin/env bash
# One unattended pass: every replicate, then every judge, then the reports.
#
# Safe to re-run: finished cells are skipped, and a judged run is not re-judged,
# so an interrupted night resumes by running this again.
#
#   bash odyssey/run_all.sh                       # r1 r2 r3
#   REPLICATES="r1" bash odyssey/run_all.sh       # one replicate
#   SUITE=shopping bash odyssey/run_all.sh        # another suite
#
# Logs land in logs/<replicate>.log and logs/<phase>.log.
set -u
cd "$(dirname "$0")/.."

SUITE="${SUITE:-main-original}"
REPLICATES="${REPLICATES:-r1 r2 r3}"
PY="${PY:-python}"
mkdir -p logs

say() { printf '\n=== %s  %s\n' "$(date '+%F %T')" "$*"; }
failed=""

for r in $REPLICATES; do
  say "replicate $r"
  # A failing cell must not take the night with it: the runner exits non-zero
  # when any cell failed, and the remaining replicates are still worth having.
  if ! $PY odyssey/run_matched_pairs.py --suite "$SUITE" --replicate-id "$r" \
       --headless --execute >> "logs/$r.log" 2>&1; then
    failed="$failed $r"
    say "replicate $r reported failed cells (see logs/$r.log)"
  fi
  tail -n 3 "logs/$r.log"
done

# Judges read finished runs, so they come after every replicate. The fidelity
# judge needs the inline R1-Rn verdicts that run.py already wrote: its coverage
# guardrail is computed from judgement.communicated.
say "experience judge"
$PY odyssey/experience_judge.py > logs/experience_judge.log 2>&1 \
  || say "experience judge reported errors (see logs/experience_judge.log)"

say "persona fidelity judge"
$PY odyssey/persona_fidelity_judge.py > logs/fidelity_judge.log 2>&1 \
  || say "fidelity judge reported errors (see logs/fidelity_judge.log)"

say "pair separation"
$PY odyssey/pair_separation.py --evidence 2>&1 | tee logs/pair_separation.log

say "report"
$PY odyssey/report.py 2>&1 | tee logs/report.log

say "done${failed:+; replicates with failed cells:$failed}"
