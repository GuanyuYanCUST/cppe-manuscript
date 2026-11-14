#!/bin/bash
# 4th channel (policy_distillation) fill for one provider: 4 domain
# workers in parallel, then one replay pass.  Integrates into the same
# main checkpoints (legit 600 -> 800 per arm).
# Usage: run_channel4.sh <provider>
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
P="${1:?usage: run_channel4.sh <provider>}"
G="--provider $P --tag main --seeds 50 --n-tasks 10 --calls-cap 600"

for d in cloudops procurement finance dataaccess; do
  (
    echo "=== [ch4 $d] start $(date +%H:%M:%S) ==="
    $PY experiments/real_rollout.py --domains "$d" \
      --channels policy_distillation $G 2>&1 | tail -2
    echo "=== [ch4 $d] DONE $(date +%H:%M:%S) ==="
  ) >> "logs/${P}_ch4_$d.log" 2>&1 &
done
wait
echo "=== $P ch4 rollouts done $(date +%H:%M:%S), replay ==="
$PY experiments/real_rollout.py --tag main --provider "$P" \
  --replay-only 2>&1 | tail -3
echo "=== $P CH4 ALL DONE $(date +%H:%M:%S) ==="
