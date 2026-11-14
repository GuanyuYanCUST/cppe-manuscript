#!/bin/bash
# Stage-4 main experiment driver.  16 bounded batches, each its own
# process (fresh CachingTransport guards: 600-call cap, ¥10 ceiling),
# checkpoints make every batch resumable: rerun this script any time.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
for domain in cloudops procurement finance dataaccess; do
  for channel in episodic vector_rag skill_consolidation; do
    echo "=== cell $domain $channel $(date +%H:%M:%S) ==="
    $PY experiments/real_rollout.py --tag main --domains "$domain" \
      --channels "$channel" --seeds 50 --n-tasks 10 --calls-cap 600 \
      2>&1 | tail -2
  done
done
for domain in cloudops procurement finance dataaccess; do
  echo "=== attacker $domain $(date +%H:%M:%S) ==="
  $PY experiments/real_rollout.py --tag main --domains "$domain" \
    --channels episodic --seeds 50 --n-tasks 10 --calls-cap 600 \
    --attacker 2>&1 | tail -2
done
echo "=== replay $(date +%H:%M:%S) ==="
$PY experiments/real_rollout.py --tag main --replay-only 2>&1 | tail -60
echo "=== DONE $(date +%H:%M:%S) ==="
