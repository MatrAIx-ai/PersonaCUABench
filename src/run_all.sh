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
#   SETTING=s1 MODELS="minimax-m3" bash src/run_all.sh
#   SETTING=s1 MODELS=terra JOBS=4 bash src/run_all.sh     # four cells at once
#   SETTING=s2 MODELS="minimax-m3 kimi-k3" bash src/run_all.sh
#   SETTING=s1 MODELS=terra REPLICATES="r1 r2 r3" bash src/run_all.sh
#   PROMPT_CACHE=off SETTING=s1 MODELS=terra bash src/run_all.sh  # uncached cost
#   JUDGE_B=off SETTING=s1 MODELS="<key>" bash src/run_all.sh    # skip the paid judge
#   NUDGE=both SETTING=s1 MODELS="<key>" bash src/run_all.sh    # proactivity ablation
#   AGENT_PERSONA=on SETTING=s1 MODELS="<key>" bash src/run_all.sh  # agent sees the profile
#   FORCE_CLARIFY=on SETTING=s1 MODELS="<key>" bash src/run_all.sh  # agent must clarify
#   RESULTS_ROOT=/data/x/results LOG_DIR=/data/x/logs PROFILE_ROOT=/data/x/chrome \
#     SETTING=s1 MODELS="<key>" bash src/run_all.sh                 # keep a run off this disk
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
# The second experience judge, on a second vendor, is what the P1-P5 agreement
# number rests on -- and it is the only part of a run that bills OpenRouter even
# when the backbone is free. JUDGE_B=off runs judge A alone; whoever collects
# the results can add the second judge later over the saved records.
JUDGE_B="${JUDGE_B:-anthropic/claude-opus-4.8}"
[[ "$JUDGE_B" == off || "$JUDGE_B" == none ]] && JUDGE_B=""
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
# The persona-profile ablation. AGENT_PERSONA=on also gives the agent the
# persona's profile in its system prompt; the main experiment gives it only
# what the persona said. Like NUDGE it is part of every cell's identity. The
# `none` control has no profile, so on turns it off unless CONTROL is set.
AGENT_PERSONA="${AGENT_PERSONA:-off}"
PERSONA_ARGS=(__sentinel__)
case "$AGENT_PERSONA" in
  off) ;;
  on) PERSONA_ARGS+=(--agent-sees-persona); export CONTROL="${CONTROL:-0}" ;;
  *) echo "AGENT_PERSONA must be off or on (got '$AGENT_PERSONA')" >&2; exit 2 ;;
esac
# The forced-clarification ablation. FORCE_CLARIFY=on requires the agent to
# clarify with the user -- as fully as it can, at any point, at least once --
# before finishing. Unlike AGENT_PERSONA it keeps the `none` control: that user
# can answer questions too.
FORCE_CLARIFY="${FORCE_CLARIFY:-off}"
case "$FORCE_CLARIFY" in
  off) ;;
  on) PERSONA_ARGS+=(--force-clarify) ;;
  *) echo "FORCE_CLARIFY must be off or on (got '$FORCE_CLARIFY')" >&2; exit 2 ;;
esac
DRY_RUN="${DRY_RUN:-}"
# Where results, logs and Chrome profiles go. The defaults are the repo's own;
# an arm that must live on another disk points all three elsewhere.
RESULTS_ROOT="${RESULTS_ROOT:-src/results}"
RESULTS="$RESULTS_ROOT/$SETTING"
OUT_ARGS=(__sentinel__)
[[ "$RESULTS_ROOT" != src/results ]] && OUT_ARGS+=(--out "$RESULTS_ROOT")
if [[ "$RESULTS_ROOT" != src/results && "$SETTING" == s2 ]]; then
  # run_matched_pairs.py writes under src/results itself; the judges would
  # then read an empty directory and report nothing.
  echo "RESULTS_ROOT is Setting 1 only for now" >&2; exit 2
fi
LOG_DIR="${LOG_DIR:-logs}"
export LOG_DIR PROFILE_ROOT="${PROFILE_ROOT:-artifacts/chrome-profiles}"
mkdir -p "$LOG_DIR"

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
                 "${NUDGE_ARGS[@]:1}" "${PERSONA_ARGS[@]:1}" "${OUT_ARGS[@]:1}" \
                 >> "$LOG_DIR/$tag-$r-$suite-$arm.log" 2>&1; then
            failed="$failed $SETTING/$model/$r/$suite/$arm"
            say "$model $r $suite $arm reported failed cells (see $LOG_DIR/$tag-$r-$suite-$arm.log)"
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
             >> "$LOG_DIR/$tag-$r.log" 2>&1; then
        failed="$failed $SETTING/$model/$r"
        say "$model $r reported failed cells (see $LOG_DIR/$tag-$r.log)"
      fi
    done
  fi
done

# Judges read finished runs, so they come after every cell. The fidelity judge
# needs the inline R1-Rn verdicts: its coverage guardrail is computed from
# judgement.communicated.
say "experience judge"
run $PY src/experience_judge.py --results "$RESULTS" --judge-b "$JUDGE_B" \
  > "$LOG_DIR/$SETTING-experience_judge.log" 2>&1 \
  || say "experience judge reported errors (see $LOG_DIR/$SETTING-experience_judge.log)"

if [[ "$SETTING" == s2 ]]; then
  say "persona fidelity judge"
  run $PY src/persona_fidelity_judge.py --results "$RESULTS" \
    > "$LOG_DIR/$SETTING-fidelity_judge.log" 2>&1 \
    || say "fidelity judge reported errors (see $LOG_DIR/$SETTING-fidelity_judge.log)"

  say "pair separation"
  run $PY src/pair_separation.py "$RESULTS" --evidence 2>&1 \
    | tee "$LOG_DIR/$SETTING-pair_separation.log"
fi

say "scores"
# report.py otherwise falls back to the catalog default suite.
for suite in $SUITES; do
  run $PY src/report.py "$RESULTS" --suite "$suite" 2>&1 \
    | tee "$LOG_DIR/$SETTING-report-$suite.log"
done

say "cost and time"
run $PY src/cost_report.py "$RESULTS" --csv "$LOG_DIR/$SETTING-cells.csv" 2>&1 \
  | tee "$LOG_DIR/$SETTING-cost.log"

if [[ "$NUDGE" == both ]]; then
  say "proactivity ablation: asking versus guessing"
  run $PY src/cost_report.py "$RESULTS" --by proactive_nudge 2>&1 \
    | tee "$LOG_DIR/$SETTING-nudge.log"
fi

if [[ "$AGENT_PERSONA" == on ]]; then
  say "persona-profile ablation"
  run $PY src/cost_report.py "$RESULTS" --by agent_sees_persona 2>&1 \
    | tee "$LOG_DIR/$SETTING-agent-persona.log"
fi

if [[ "$FORCE_CLARIFY" == on ]]; then
  say "forced-clarification ablation"
  run $PY src/cost_report.py "$RESULTS" --by force_clarify 2>&1 \
    | tee "$LOG_DIR/$SETTING-force-clarify.log"
fi

say "done${failed:+; failed:$failed}"
