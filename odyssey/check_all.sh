#!/usr/bin/env bash
# Every offline check, with the exit code that actually decides.
#
# Run this before pushing. No network, no API keys, no browser: it is the gate
# that catches a broken call before it costs a night of runs.
#
#   bash odyssey/check_all.sh
set -u
cd "$(dirname "$0")/.."
PY="${PY:-python3}"

# A piped command hides the failure behind the pipe's exit code, which is how a
# red test once got committed as green. Nothing here is piped.
failed=""
for check in \
  "odyssey/test_pipeline.py" \
  "odyssey/test_accounting.py" \
  "odyssey/test_pair_separation.py" \
  "odyssey/responses_shim.py" \
  ; do
  printf '%-40s' "$check"
  if out=$("$PY" "$check" 2>&1); then
    printf 'ok\n'
  else
    printf 'FAILED\n%s\n' "$out"
    failed="$failed $check"
  fi
done

for check in "odyssey/prepare_v1.py --check" "odyssey/models.py"; do
  printf '%-40s' "$check"
  if out=$("$PY" $check 2>&1); then
    printf 'ok\n'
  else
    printf 'FAILED\n%s\n' "$out"
    failed="$failed $check"
  fi
done

if [[ -n "$failed" ]]; then
  echo
  echo "FAILED:$failed"
  exit 1
fi
echo
echo "all offline checks passed"
