#!/bin/bash
# Generic per-provider acceptance pilot: 4 legit + 2 attacker rollouts
# (~70 calls).  Usage: run_pilot.sh <provider>
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
P="${1:?usage: run_pilot.sh <provider>}"
A="--provider $P --tag acceptance --seeds 1 --n-tasks 10 --calls-cap 60"
echo "=== legit cloudops episodic+vector_rag $(date +%H:%M:%S) ==="
$PY experiments/real_rollout.py --domains cloudops --channels episodic,vector_rag $A 2>&1 | tail -3
echo "=== legit finance episodic+vector_rag $(date +%H:%M:%S) ==="
$PY experiments/real_rollout.py --domains finance --channels episodic,vector_rag $A 2>&1 | tail -3
echo "=== attacker cloudops+finance $(date +%H:%M:%S) ==="
$PY experiments/real_rollout.py --domains cloudops,finance --channels episodic $A --attacker 2>&1 | tail -3
echo "=== $P PILOT DONE $(date +%H:%M:%S) ==="
