#!/bin/bash
# One-line status per arm: checkpoints, last log line, cost-bearing worker liveness.
cd "$(dirname "$0")/.." || exit 1
for d in real_gpt56 real_claude55 real_glm53 real_gemini38flash real_deepseek41flash; do
  n=$(ls results/$d/rollouts/main/*.json 2>/dev/null | wc -l)
  a=$(ls results/$d/rollouts/main/*atk*.json 2>/dev/null | wc -l)
  echo "$d: $((n-a)) legit + $a atk = $n/800"
done
echo "---- workers alive:"
pgrep -fc "real_rollout.py" || echo 0
echo "---- latest log lines:"
for f in logs/gpt_main_par3.log logs/claude_main_par.log logs/gemini_main_par.log logs/main_driver_zhongkey.log; do
  [ -f "$f" ] && echo "[$f] $(tail -1 "$f" | cut -c1-120)"
done
