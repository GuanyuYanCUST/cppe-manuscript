#!/bin/bash
# Generic parallel arm launcher: 4 domain workers, then one replay pass.
# Usage: run_main_par.sh <provider>
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
P="${1:?usage: run_main_par.sh <provider>}"
G="--provider $P --tag main --seeds 50 --n-tasks 10 --calls-cap 600"

worker() {  # $1 = domain
  local d=$1
  for channel in episodic vector_rag skill_consolidation; do
    echo "=== [worker $d] cell $d $channel $(date +%H:%M:%S) ==="
    $PY experiments/real_rollout.py --domains "$d" --channels "$channel" \
      $G 2>&1 | tail -2
  done
  echo "=== [worker $d] attacker $(date +%H:%M:%S) ==="
  $PY experiments/real_rollout.py --domains "$d" --channels episodic \
    $G --attacker 2>&1 | tail -2
  echo "=== [worker $d] DONE $(date +%H:%M:%S) ==="
}

for d in cloudops procurement finance dataaccess; do
  worker "$d" >> "logs/${P}_worker_$d.log" 2>&1 &
done
wait
echo "=== replay $(date +%H:%M:%S) ==="
$PY experiments/real_rollout.py --tag main --provider "$P" \
  --replay-only 2>&1 | tail -60
echo "=== $P ALL DONE $(date +%H:%M:%S) ==="
