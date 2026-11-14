#!/bin/bash
cd "$(dirname "$0")/.." || exit 1
for d in real_glm53 real_gpt56; do
  n=$(ls results/$d/rollouts/main/*.json 2>/dev/null | grep -c '\.json$')
  a=$(ls results/$d/rollouts/main/*-atk.json 2>/dev/null | grep -c '\.json$')
  echo "$d: $((n - a)) legit + $a atk = $n/800"
done
