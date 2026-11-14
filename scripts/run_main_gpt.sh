#!/bin/bash
# Stage-4 GPT arm (gpt-5.6-sol via Codex relay).  Same 16-batch design
# as run_main.sh, provider-isolated checkpoints/raw/replay under
# results/real_gpt56/.  Relay 409 locks are retried with long backoff
# inside the adapter; 1113-style fatal codes still stop instantly.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
G="--provider gpt --tag main --seeds 50 --n-tasks 10 --calls-cap 600"
for domain in cloudops procurement finance dataaccess; do
  for channel in episodic vector_rag skill_consolidation; do
    echo "=== cell $domain $channel $(date +%H:%M:%S) ==="
    $PY experiments/real_rollout.py --domains "$domain" \
      --channels "$channel" $G 2>&1 | tail -2
  done
done
for domain in cloudops procurement finance dataaccess; do
  echo "=== attacker $domain $(date +%H:%M:%S) ==="
  $PY experiments/real_rollout.py --domains "$domain" \
    --channels episodic $G --attacker 2>&1 | tail -2
done
echo "=== replay $(date +%H:%M:%S) ==="
$PY experiments/real_rollout.py --tag main --provider gpt \
  --replay-only 2>&1 | tail -60
echo "=== DONE $(date +%H:%M:%S) ==="
