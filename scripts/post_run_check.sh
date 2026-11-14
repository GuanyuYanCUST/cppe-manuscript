#!/bin/bash
# Post-run ground truth: checkpoints per cell, anomalies, replay output.
cd "$(dirname "$0")/.." || exit 1
R=results/real_glm53
echo "== checkpoint inventory =="
for d in cloudops procurement finance dataaccess; do
  for c in episodic vector_rag skill_consolidation; do
    n=$(ls $R/rollouts/main/ 2>/dev/null | grep -c "^$d-$c-s[0-9]*\.json$")
    a=$(ls $R/rollouts/main/ 2>/dev/null | grep -c "^$d-$c-s[0-9]*-atk\.json$")
    echo "$d-$c legit=$n atk=$a"
  done
done
echo "total: $(ls $R/rollouts/main/ | grep -c json) (expect 800)"
echo "== anomalies in resume log =="
echo "fatal: $(grep -c '\[fatal\]' logs/main_driver_resume.log)"
echo "guard: $(grep -c '\[guard\]' logs/main_driver_resume.log)"
echo "infra-skip: $(grep -c 'infra-skip' logs/main_driver_resume.log)"
echo "replay-error: $(grep -c 'replay-error' logs/main_driver_resume.log)"
echo "== log tail =="
tail -4 logs/main_driver_resume.log
echo "== replay outputs =="
ls -la $R/replay/ 2>/dev/null | grep main
echo "== cell headers seen =="
grep -c "^=== cell" logs/main_driver_resume.log
