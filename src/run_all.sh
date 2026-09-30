#!/usr/bin/env bash
# One unattended pass for one setting over one or more CUA models, then the
# judges, then the reports.
#
# Setting 1 = group personas (tens of dimensions at once, one persona per group).
# Setting 2 = matched pairs (one dimension flipped, everything else held).
# The two never share a results directory: every run is written under
# src/results/<setting>/ and carries the setting in its record.
#
# Safe to re-run: finished cells are skipped and judged runs are not re-judged,
# so an interrupted night resumes by running this again.
#
#   SETTING=s1 MODELS="glm-5.3" bash src/run_all.sh
#   SETTING=s1 MODELS=terra JOBS=4 bash src/run_all.sh     # four cells at once
#   SETTING=s2 MODELS="glm-5.3 minimax-m3" bash src/run_all.sh
#   SETTING=s1 MODELS=terra REPLICATES="r1 r2 r3" bash src/run_all.sh
#   PROMPT_CACHE=off SETTING=s1 MODELS=terra bash src/run_all.sh  # uncached cost
#   NUDGE=both SETTING=s1 MODELS="<key>" bash src/run_all.sh    # proactivity ablation
#   DRY_RUN=1 SETTING=s2 MODELS=terra bash src/run_all.sh   # plan only, no spend
#
# MODELS takes keys from src/models.json (`python src/models.py` lists
# them); a key deployed on Azure runs there for free, everything else bills
# OpenRouter. Logs land in logs/<setting>-<model>-<phase>.log.
set -u
cd "$(dirname "$0")/.."

SETTING="${SETTING:-s1}"
# Both v1 suites by default: the live-web tasks and the REAL sandbox tasks are
# the whole run, and main-original is the retired six-task assignment.
SUITES="${SUITES:-${SUITE:-odysseys real}}"
MODELS="${MODELS:-terra}"
# One pass by default. Repeats cost the same again and are only worth it
# once a difference between models looks real.
REPLICATES="${REPLICATES:-r1}"
# Setting 1's personas come from each task's own domain family
# (src/persona_assignments.py), so this is left empty on purpose: setting it
# would ask a Gmail task in a travel persona's voice. Export PERSONAS only to
# run a deliberate subset. Setting 2's are generated from the protocol and
# selected by run_matched_pairs.py, so it is unused there.
PERSONAS="${PERSONAS:-}"
PY="${PY:-python}"
# Setting 1 fans out: one Chrome per worker, ~1.5 GB of RAM each. Setting 2 stays
# serial -- a matched pair's two arms must not race for the same profile.
JOBS="${JOBS:-1}"
# PROMPT_CACHE=off measures what a run costs without our breakpoints; providers
# that cache by themselves are unaffected either way.
PROMPT_CACHE="${PROMPT_CACHE:-on}"
CACHE_ARGS=(__sentinel__)
[[ "$PROMPT_CACHE" == off ]] && CACHE_ARGS+=(--no-prompt-cache)
# The proactivity ablation. NUDGE=on appends a paragraph to the agent's system
# prompt telling it to ask the user rather than guess when the request leaves
# something out; NUDGE=both runs each cell twice, once each way, which is the
# comparison the arm exists for. The flag is part of every cell's resume
# fingerprint, so the two arms are separate cells and neither overwrites the
# other, and cost_report.py --by proactive_nudge splits the results.
NUDGE="${NUDGE:-off}"
case "$NUDGE" in
  off) NUDGE_ARMS=("plain") ;;
  on) NUDGE_ARMS=("nudge") ;;
  both) NUDGE_ARMS=("plain" "nudge") ;;
  *) echo "NUDGE must be off, on or both (got '$NUDGE')" >&2; exit 2 ;;
esac
DRY_RUN="${DRY_RUN:-}"
RESULTS="src/results/$SETTING"
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
    # Every task with its own four personas plus the control, one process per
    # cell, once per replicate, over each suite.
    for r in $REPLICATES; do
      for suite in $SUITES; do
        for arm in "${NUDGE_ARMS[@]}"; do
          NUDGE_ARGS=(__sentinel__)
          [[ "$arm" == nudge ]] && NUDGE_ARGS+=(--nudge-proactive)
          say "$SETTING  model=$model  replicate=$r  suite=$suite  arm=$arm"
          if ! PERSONAS="$PERSONAS" TASK_SUITE="$suite" PYTHON_BIN="$PY" JOBS="$JOBS" \
               run bash src/run_grid.sh --setting "$SETTING" --model "$model" \
                 --replicate-id "$r" --headless "${CACHE_ARGS[@]:1}" \
                 "${NUDGE_ARGS[@]:1}" \
                 >> "logs/$tag-$r-$suite-$arm.log" 2>&1; then
            failed="$failed $SETTING/$model/$r/$suite/$arm"
            say "$model $r $suite $arm reported failed cells (see logs/$tag-$r-$suite-$arm.log)"
          fi
        done
      done
    done
  else
    for r in $REPLICATES; do
      say "$SETTING  model=$model  replicate=$r"
      # Without --execute this only prints the plan, which is what DRY_RUN wants.
      execute=(--execute)
      [[ -n "$DRY_RUN" ]] && execute=()
      if ! run $PY src/run_matched_pairs.py --suite "${SUITE:-shopping}" \
             --replicate-id "$r" --headless "${execute[@]+"${execute[@]}"}" \
             -- --setting "$SETTING" --model "$model" "${CACHE_ARGS[@]:1}" \
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
run $PY src/experience_judge.py --results "$RESULTS" \
  > "logs/$SETTING-experience_judge.log" 2>&1 \
  || say "experience judge reported errors (see logs/$SETTING-experience_judge.log)"

if [[ "$SETTING" == s2 ]]; then
  say "persona fidelity judge"
  run $PY src/persona_fidelity_judge.py --results "$RESULTS" \
    > "logs/$SETTING-fidelity_judge.log" 2>&1 \
    || say "fidelity judge reported errors (see logs/$SETTING-fidelity_judge.log)"

  say "pair separation"
  run $PY src/pair_separation.py "$RESULTS" --evidence 2>&1 \
    | tee "logs/$SETTING-pair_separation.log"
fi

say "scores"
# report.py otherwise falls back to the catalog default suite.
for suite in $SUITES; do
  run $PY src/report.py "$RESULTS" --suite "$suite" 2>&1 \
    | tee "logs/$SETTING-report-$suite.log"
done

say "cost and time"
run $PY src/cost_report.py "$RESULTS" --csv "logs/$SETTING-cells.csv" 2>&1 \
  | tee "logs/$SETTING-cost.log"

if [[ "$NUDGE" == both ]]; then
  say "proactivity ablation: asking versus guessing"
  run $PY src/cost_report.py "$RESULTS" --by proactive_nudge 2>&1 \
    | tee "logs/$SETTING-nudge.log"
fi

say "done${failed:+; failed:$failed}"
