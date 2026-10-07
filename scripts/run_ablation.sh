#!/usr/bin/env bash
# One Setting 1 ablation arm over the same grid as the main experiment, with
# one change to the agent. Everything it writes -- results, trajectories,
# screenshots, logs, Chrome profiles -- goes under ABL_ROOT, not the repo.
#
#   ARM=agent-persona   the agent also gets the persona's profile in its system
#                       prompt. 74 tasks x 4 personas = 296 cells: the `none`
#                       control has no profile to give.
#   ARM=force-clarify   the agent must clarify with the user -- as fully as it
#                       can, at any point, at least once and at most 5 times --
#                       before finishing. 74 x (4 personas + none) = 370 cells.
#
#   conda activate persona
#   ARM=force-clarify bash scripts/run_ablation.sh              # preflight, then the grid
#   ARM=force-clarify DRY_RUN=1 bash scripts/run_ablation.sh    # preflight and plan only
#   ARM=force-clarify CHECK_ONLY=1 bash scripts/run_ablation.sh # preflight only
#
# Safe to re-run: finished cells are skipped, so an interrupted night resumes
# by running the same command again.
#
# The preflight refuses to start if the arm would differ from the main run in
# anything but its one change: the agent, persona and judge must resolve to
# the endpoints the main run used, and every persona's opening message must
# already be cached, so both arms hear exactly the same request.
set -u
cd "$(dirname "$0")/.."

ARM="${ARM:-}"
case "$ARM" in
  agent-persona) ARM_ENV=(AGENT_PERSONA=on); DEFAULT_ROOT=/data/dal170519/PersonaCUABench ;;
  force-clarify) ARM_ENV=(FORCE_CLARIFY=on); DEFAULT_ROOT=/data/dal170519/PersonaCUABench/force-clarify ;;
  *) echo "ARM must be agent-persona or force-clarify (got '$ARM')" >&2; exit 2 ;;
esac
# agent-persona keeps the root it was first run with, so re-running it resumes.
ABL_ROOT="${ABL_ROOT:-$DEFAULT_ROOT}"
MODEL="${MODEL:-gpt-6-astra}"
# The main run whose conditions this one must match.
MAIN_RESULTS="${MAIN_RESULTS:-src/results/s1}"
PY="${PY:-python}"

if ! "$PY" -c "import jmespath, playwright" 2>/dev/null; then
  echo "'$PY' is missing the harness's packages; run 'conda activate persona' first" >&2
  exit 2
fi

echo "=== preflight ($ARM)"
if ! "$PY" - "$MODEL" "$MAIN_RESULTS" <<'PREFLIGHT'
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
import run, task_router, persona_assignments
import models as model_registry

model, main_results = sys.argv[1], Path(sys.argv[2])
run.load_dotenv()
problems = []

# 1. Same endpoints as the main run. A route that changed underneath -- the
# direct OpenAI key uncommented in .env, say -- would make the two arms
# different models, which is the confound an ablation exists to avoid.
main = None
for path in sorted(main_results.rglob("result.json")):
    record = json.loads(path.read_text(encoding="utf-8"))
    agent = (record.get("run_config") or {}).get("agent") or {}
    if agent.get("model") == model and agent.get("backend") == "azure-openai-compatible":
        main = record["run_config"]
        break
if main is None:
    problems.append(f"no Azure {model} result under {main_results} to compare against")
else:
    for role, key in (("agent", model), ("persona_user", main["persona_user"]["model"]),
                      ("judge", main["judge"]["model"])):
        resolved_model, provider = model_registry.resolve(key, "")
        provider = run._resolved_provider(resolved_model, provider)
        now = {"model": resolved_model, "backend": run._provider_backend(provider),
               "endpoint_sha256": run._endpoint_sha256(provider)}
        then = {k: main[role][k] for k in now}
        status = "ok" if now == then else "DIFFERENT"
        print(f"  {role:13} {now['model']} via {now['backend']}  [{status}]")
        if now != then:
            problems.append(f"{role} resolves to {now}, the main run used {then}")

# 2. Every persona opening already cached. A miss would have the persona model
# write a fresh request, and the arms would no longer answer the same one. The
# `none` control needs no cache: its opening is the task text verbatim.
persona_model, persona_provider = model_registry.resolve(
    main["persona_user"]["model"] if main else "gpt-5.6-terra", "")
hits = misses = 0
for suite_id in ("odysseys", "real"):
    suite = task_router.load_route(suite_id=suite_id)
    for task in suite.tasks:
        for persona in persona_assignments.personas_for(task):
            spec = run.persona_opening_cache(
                task, suite_id=suite_id, persona=persona, replicate_id="r1",
                persona_path=run.resolve_persona_path(persona, suite_id),
                model=persona_model, provider=persona_provider, temperature=1.0)
            if spec["path"].is_file():
                hits += 1
            else:
                misses += 1
                print(f"  no cached opening: {suite_id} {task['task_id'][:12]} {persona}")
print(f"  cached openings: {hits} of {hits + misses} persona cells")
if misses and os.environ.get("ALLOW_NEW_OPENINGS") != "1":
    problems.append(f"{misses} cells have no cached opening "
                    "(ALLOW_NEW_OPENINGS=1 to let the persona write new ones)")

for problem in problems:
    print(f"  PROBLEM: {problem}")
sys.exit(1 if problems else 0)
PREFLIGHT
then
  echo "preflight failed; nothing was run" >&2
  exit 1
fi
echo "  results  -> $ABL_ROOT/results/s1"
echo "  logs     -> $ABL_ROOT/logs"
echo "  chrome   -> $ABL_ROOT/chrome-profiles"
[[ -n "${CHECK_ONLY:-}" ]] && exit 0

mkdir -p "$ABL_ROOT/results" "$ABL_ROOT/logs" "$ABL_ROOT/chrome-profiles"
# JUDGE_B costs money on OpenRouter; judge A scores every cell regardless, and
# B can be added later over the saved records.
env "${ARM_ENV[@]}" SETTING=s1 MODELS="$MODEL" \
  JOBS="${JOBS:-4}" JUDGE_B="${JUDGE_B:-off}" PY="$PY" \
  RESULTS_ROOT="$ABL_ROOT/results" LOG_DIR="$ABL_ROOT/logs" \
  PROFILE_ROOT="$ABL_ROOT/chrome-profiles" \
  bash src/run_all.sh
