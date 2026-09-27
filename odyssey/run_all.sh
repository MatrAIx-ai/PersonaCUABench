#!/usr/bin/env bash
# One unattended pass for one setting over one or more CUA models, then the
# judges, then the reports.
#
# Setting 1 = group personas (tens of dimensions at once, one persona per group).
# Setting 2 = matched pairs (one dimension flipped, everything else held).
# The two never share a results directory: every run is written under
# odyssey/results/<setting>/ and carries the setting in its record.
#
# Safe to re-run: finished cells are skipped and judged runs are not re-judged,
# so an interrupted night resumes by running this again.
#
#   SETTING=s1 MODELS="glm-5.3" bash odyssey/run_all.sh
#   SETTING=s1 MODELS=terra JOBS=4 bash odyssey/run_all.sh     # four cells at once
#   SETTING=s2 MODELS="glm-5.3 minimax-m3" bash odyssey/run_all.sh
#   SETTING=s1 MODELS=terra REPLICATES="r1" bash odyssey/run_all.sh
#   DRY_RUN=1 SETTING=s2 MODELS=terra bash odyssey/run_all.sh   # plan only, no spend
#
# MODELS takes keys from odyssey/models.json (`python odyssey/models.py` lists
# them); a key deployed on Azure runs there for free, everything else bills
# OpenRouter. Logs land in logs/<setting>-<model>-<phase>.log.
set -u
cd "$(dirname "$0")/.."

SETTING="${SETTING:-s1}"
SUITE="${SUITE:-main-original}"
MODELS="${MODELS:-terra}"
REPLICATES="${REPLICATES:-r1 r2 r3}"
# Setting 1's personas: one per group of people. Setting 2's are generated from
# the protocol and selected by run_matched_pairs.py, so PERSONAS is unused there.
PERSONAS="${PERSONAS:-none travel-expert elderly-novice budget-student non-native-speaker}"
PY="${PY:-python}"
# Setting 1 fans out: one Chrome per worker, ~1.5 GB of RAM each. Setting 2 stays
# serial -- a matched pair's two arms must not race for the same profile.
JOBS="${JOBS:-1}"
DRY_RUN="${DRY_RUN:-}"
RESULTS="odyssey/results/$SETTING"
mkdir -p logs

case "$SETTING" in
  s1|s2) ;;
  *) echo "SETTING must be s1 or s2 (got '$SETTING')" >&2; exit 2 ;;
esac

say() { printf '\n=== %s  %s\n' "$(date '+%F %T')" "$*"; }
run() { if [[ -n "$DRY_RUN" ]]; then echo "DRY: $*"; else "$@"; fi; }
failed=""

for model in $MODELS; do
  tag="$SETTING-${model//\//-}"
  say "$SETTING  model=$model"
  if [[ "$SETTING" == s1 ]]; then
    # Every persona x every task, one process per cell, once per replicate.
    for r in $REPLICATES; do
      say "$SETTING  model=$model  replicate=$r"
      if ! PERSONAS="$PERSONAS" TASK_SUITE="$SUITE" PYTHON_BIN="$PY" JOBS="$JOBS" \
           run bash odyssey/run_grid.sh --setting "$SETTING" --model "$model" \
             --replicate-id "$r" --headless >> "logs/$tag-$r.log" 2>&1; then
        failed="$failed $SETTING/$model/$r"
        say "$model $r reported failed cells (see logs/$tag-$r.log)"
      fi
    done
  else
    for r in $REPLICATES; do
      say "$SETTING  model=$model  replicate=$r"
      # Without --execute this only prints the plan, which is what DRY_RUN wants.
      execute=(--execute)
      [[ -n "$DRY_RUN" ]] && execute=()
      if ! run $PY odyssey/run_matched_pairs.py --suite "$SUITE" \
             --replicate-id "$r" --headless "${execute[@]+"${execute[@]}"}" \
             -- --setting "$SETTING" --model "$model" \
             >> "logs/$tag-$r.log" 2>&1; then
        failed="$failed $SETTING/$model/$r"
        say "$model $r reported failed cells (see logs/$tag-$r.log)"
      fi
    done
  fi
done

# Judges read finished runs, so they come after every cell. The fidelity judge
# needs the inline R1-Rn verdicts: its coverage guardrail is computed from
# judgement.communicated.
say "experience judge"
run $PY odyssey/experience_judge.py --results "$RESULTS" \
  > "logs/$SETTING-experience_judge.log" 2>&1 \
  || say "experience judge reported errors (see logs/$SETTING-experience_judge.log)"

if [[ "$SETTING" == s2 ]]; then
  say "persona fidelity judge"
  run $PY odyssey/persona_fidelity_judge.py --results "$RESULTS" \
    > "logs/$SETTING-fidelity_judge.log" 2>&1 \
    || say "fidelity judge reported errors (see logs/$SETTING-fidelity_judge.log)"

  say "pair separation"
  run $PY odyssey/pair_separation.py "$RESULTS" --evidence 2>&1 \
    | tee "logs/$SETTING-pair_separation.log"
fi

say "scores"
# report.py otherwise falls back to the catalog default suite (shopping).
run $PY odyssey/report.py "$RESULTS" --suite "$SUITE" 2>&1 \
  | tee "logs/$SETTING-report.log"

say "cost and time"
run $PY odyssey/cost_report.py "$RESULTS" --csv "logs/$SETTING-cells.csv" 2>&1 \
  | tee "logs/$SETTING-cost.log"

say "done${failed:+; failed:$failed}"
