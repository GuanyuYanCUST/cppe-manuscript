#!/bin/bash
# Keep running an arm's sweeps until all 1000 checkpoints exist
# (800 legit incl policy_distillation + 200 atk), then replay once.
# Usage: fill_until_done.sh <provider>
cd "$(dirname "$0")/.." || exit 1
P="${1:?usage: fill_until_done.sh <provider>}"
PY=.venv/bin/python
case "$P" in
  gpt)      DIR=results/real_gpt56 ;;
  claude)   DIR=results/real_claude55 ;;
  gemini)   DIR=results/real_gemini38flash ;;
  deepseek) DIR=results/real_deepseek41flash ;;
  glm)      DIR=results/real_glm53 ;;
  *) echo "unknown provider $P"; exit 1 ;;
esac

for i in $(seq 1 12); do
  n=$(ls "$DIR"/rollouts/main/*.json 2>/dev/null | wc -l)
  echo "=== [fill $P #$i] $n/1000 $(date +%H:%M:%S) ==="
  [ "$n" -ge 1000 ] && break
  # main pass covers 3 channels + attacker; ch4 pass covers
  # policy_distillation — both needed to converge
  bash scripts/run_main_par.sh "$P" 2>&1 | tail -1 || true
  n=$(ls "$DIR"/rollouts/main/*.json 2>/dev/null | wc -l)
  [ "$n" -ge 1000 ] && break
  bash scripts/run_channel4.sh "$P" 2>&1 | tail -1 || true
done
n=$(ls "$DIR"/rollouts/main/*.json 2>/dev/null | wc -l)
echo "=== [fill $P] final $n/1000, replay ==="
$PY experiments/real_rollout.py --tag main --provider "$P" --replay-only 2>&1 | tail -3
echo "=== [fill $P] DONE at $n $(date +%H:%M:%S) ==="
