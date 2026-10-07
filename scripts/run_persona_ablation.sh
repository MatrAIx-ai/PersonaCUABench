#!/usr/bin/env bash
# The persona-profile ablation; kept so the command it was first run with
# still works. See scripts/run_ablation.sh.
exec env ARM=agent-persona bash "$(dirname "$0")/run_ablation.sh" "$@"
