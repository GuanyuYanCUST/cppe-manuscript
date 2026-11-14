#!/bin/bash
# Parallel GPT-arm launcher: 4 domain workers (max 4 concurrent requests,
# well inside the relay's 10-concurrency tier), each runs its own cells
# sequentially then joins for a single replay pass.  Checkpoints make
# every cell resumable; workers write disjoint (domain, tag) files.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
G="--provider gpt --tag main --seeds 50 --n-tasks 10 --calls-cap 600"

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
  worker "$d" >> "logs/gpt_worker_$d.log" 2>&1 &
done
wait
echo "=== replay $(date +%H:%M:%S) ==="
$PY experiments/real_rollout.py --tag main --provider gpt \
  --replay-only 2>&1 | tail -60
echo "=== ALL DONE $(date +%H:%M:%S) ==="
