#!/bin/bash
# Quick sweep status (safe from wsl.exe $-mangling: run as a file).
cd "$(dirname "$0")/.." || exit 1
echo "checkpoints_main: $(ls results/real_glm53/rollouts/main/ 2>/dev/null | grep -c '\.json$')/800"
echo "done_lines_in_resume_log: $(grep -c '\[done\]' logs/main_driver_resume.log)"
echo "rollout_procs: $(pgrep -f real_rollout.py | wc -l)"
echo "driver_procs: $(pgrep -f run_main.sh | wc -l)"
echo "--- log tail ---"
tail -6 logs/main_driver_resume.log
echo "--- newest checkpoints ---"
ls -t results/real_glm53/rollouts/main/ 2>/dev/null | head -5
