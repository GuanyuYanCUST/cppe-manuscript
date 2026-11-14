#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/python -m pytest tests/ -q
.venv/bin/python experiments/e1_endtoend.py 25
