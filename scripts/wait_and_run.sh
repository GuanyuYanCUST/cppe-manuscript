#!/bin/bash
# Wait out the provider rate limiter, then run the main sweep twice
# (pass 2 fills any gap left by mid-run guards), then replay+tables.
# DO NOT relaunch without explicit user approval (2026-10-08 order:
# experiments paused pending the Coding-Plan compliance decision).
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
while true; do
  out=$($PY scripts/probe_limit.py 2>/dev/null)
  case "$out" in
    *"RESULT: OK"*)
      echo "$(date +%H:%M:%S) limiter lifted — starting sweep"
      break;;
    *"FatalAPIError"*)
      # 1113 balance-exhausted etc.: a business error no amount of
      # waiting fixes — stop and report instead of looping forever
      echo "$(date +%H:%M:%S) FATAL: $out"
      exit 2;;
  esac
  echo "$(date +%H:%M:%S) still rate-limited ($out), sleeping 10 min"
  sleep 600
done
for pass in 1 2; do
  echo "=== sweep pass $pass $(date +%H:%M:%S) ==="
  bash scripts/run_main.sh
done
$PY scripts/make_main_tables.py
echo "=== ALL DONE $(date +%H:%M:%S) ==="
