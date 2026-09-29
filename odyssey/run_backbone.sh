#!/usr/bin/env bash
# Run the full grid (every task x its 3 assigned personas) for one or more
# execution backbones. The persona simulator and judge stay fixed; only the
# CUA doing the work changes.
#
# Each backbone has its own API. odyssey/backbones.json maps a backbone name to
# its model id and to the .env variables holding its endpoint and key.
#
#   PERSONA_MODEL=gpt-5.6-terra bash odyssey/run_backbone.sh claude-opus-5.5
#   PERSONA_MODEL=gpt-5.6-terra bash odyssey/run_backbone.sh kimi-k3 glm-5.3 grok-4.7
#   PERSONA_MODEL=gpt-5.6-terra bash odyssey/run_backbone.sh all      # every backbone
#   SHARDS=3 PERSONA_MODEL=... bash odyssey/run_backbone.sh qwen3.8-27b   # 3 parallel workers
#   nohup env PERSONA_MODEL=... bash odyssey/run_backbone.sh all > backbone.log 2>&1 &
#
# Env:
#   PERSONA_MODEL     required: the persona simulator, identical for every backbone
#   PERSONA_PROVIDER  default: inferred from the model id (gpt-* -> azure, else qwen)
#   SHARDS            parallel workers per backbone, each with its own Chrome profile (default 1)
#   LOG_DIR           default: <repo>/logs
#   BACKBONES_FILE    default: odyssey/backbones.json
# Extra arguments after the backbone names, following "--", go to run.py.
# Resumable: rerun the same command and finished cells are skipped.
set -u
cd "$(dirname "$0")/.."

: "${PERSONA_MODEL:?set PERSONA_MODEL (the persona simulator, same for every backbone)}"
PERSONA_PROVIDER="${PERSONA_PROVIDER:-}"
SHARDS="${SHARDS:-1}"
LOG_DIR="${LOG_DIR:-$PWD/logs}"
PYTHON="${PYTHON:-.venv/bin/python}"
export BACKBONES_FILE="${BACKBONES_FILE:-$PWD/odyssey/backbones.json}"

names=()
while [ $# -gt 0 ] && [ "$1" != "--" ]; do names+=("$1"); shift; done
[ "${1:-}" = "--" ] && shift
known=$("$PYTHON" -c "import json,os; print(' '.join(k for k in json.load(open(os.environ['BACKBONES_FILE'])) if k != '_note'))")
if [ ${#names[@]} -eq 0 ]; then
  echo "usage: PERSONA_MODEL=... bash odyssey/run_backbone.sh <backbone> [...] | all  [-- run.py args]" >&2
  echo "backbones: $known" >&2
  exit 2
fi
[ "${names[*]}" = "all" ] && read -r -a names <<< "$known"
for name in "${names[@]}"; do
  if ! [[ " $known " == *" $name "* ]]; then
    echo "unknown backbone '$name'; known: $known" >&2
    exit 2
  fi
done
if ! [[ "$SHARDS" =~ ^[1-9][0-9]*$ ]]; then echo "invalid SHARDS=$SHARDS" >&2; exit 2; fi
mkdir -p "$LOG_DIR"

for name in "${names[@]}"; do
  model=$("$PYTHON" -c "import json,os,sys; print(json.load(open(os.environ['BACKBONES_FILE']))[sys.argv[1]]['model'])" "$name")
  echo "=== backbone $name ($model)  persona $PERSONA_MODEL, $SHARDS worker(s) ==="
  pids=()
  for ((i = 0; i < SHARDS; i++)); do
    PROFILE="$PWD/odyssey/.chrome-profile-w$i" SHARD_COUNT="$SHARDS" SHARD_INDEX="$i" \
      PYTHON="$PYTHON" bash odyssey/run_grid.sh \
        --model "$model" --provider "$name" \
        --persona-model "$PERSONA_MODEL" --persona-provider "$PERSONA_PROVIDER" "$@" \
        > "$LOG_DIR/grid_${name}_w$i.log" 2>&1 &
    pids+=($!)
  done
  status=0
  for pid in "${pids[@]}"; do wait "$pid" || status=1; done
  echo "=== backbone $name done (exit $status); logs: $LOG_DIR/grid_${name}_w*.log ==="
done

"$PYTHON" odyssey/report.py
