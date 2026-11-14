#!/bin/bash
# Claude-sonnet-5-5 pilot via zhongkey (ccmax pool): 4 legit + 2 attacker
# acceptance rollouts, then replay + summary.  ~70 calls, ~$0.4.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
A="--provider claude --tag acceptance --seeds 1 --n-tasks 10 --calls-cap 60"
echo "=== legit cloudops episodic+vector_rag $(date +%H:%M:%S) ==="
$PY experiments/real_rollout.py --domains cloudops --channels episodic,vector_rag $A 2>&1 | tail -3
echo "=== legit finance episodic+vector_rag $(date +%H:%M:%S) ==="
$PY experiments/real_rollout.py --domains finance --channels episodic,vector_rag $A 2>&1 | tail -3
echo "=== attacker cloudops+finance $(date +%H:%M:%S) ==="
$PY experiments/real_rollout.py --domains cloudops,finance --channels episodic $A --attacker 2>&1 | tail -3
echo "=== PILOT DONE $(date +%H:%M:%S) ==="
