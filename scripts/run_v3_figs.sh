#!/bin/bash
# S3 v3 figure runner: render all three, then verify outputs exist.
cd "$(dirname "$0")" || exit 1
for s in make_fig6b_v3 make_fig6c_v3 make_fig9_v3; do
    echo "== $s"
    ../.venv/bin/python "$s.py" || exit 2
done
ls -la ../results/FIGS/v3_20261010/
