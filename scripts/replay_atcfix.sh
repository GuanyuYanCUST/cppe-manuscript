#!/bin/bash
# Re-replay all five arms with the ATC-coverage fix (offline, zero API).
# Old jsonl+summary preserved as *_pre_atcfix (never delete).
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
for P in glm claude gemini deepseek gpt; do
  case "$P" in
    gpt)      DIR=results/real_gpt56 ;;
    claude)   DIR=results/real_claude55 ;;
    gemini)   DIR=results/real_gemini38flash ;;
    deepseek) DIR=results/real_deepseek41flash ;;
    glm)      DIR=results/real_glm53 ;;
  esac
  (
    [ -f "$DIR/replay/main_pre_atcfix.jsonl" ] || \
      cp "$DIR/replay/main.jsonl" "$DIR/replay/main_pre_atcfix.jsonl"
    [ -f "$DIR/replay/main_pre_atcfix_summary.json" ] || \
      cp "$DIR/replay/main_summary.json" \
         "$DIR/replay/main_pre_atcfix_summary.json"
    echo "=== [atcfix $P] replay start $(date +%H:%M:%S) ==="
    $PY experiments/real_rollout.py --tag main --provider "$P" \
      --replay-only 2>&1 | tail -2
    echo "=== [atcfix $P] DONE $(date +%H:%M:%S) ==="
  ) >> "logs/atcfix_$P.log" 2>&1 &
done
wait
echo "=== ATC-FIX REPLAY ALL DONE $(date +%H:%M:%S) ==="