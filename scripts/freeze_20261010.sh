#!/bin/bash
# Artifact freeze 2026-10-10: in-place SHA256SUMS over all paper-relevant
# trees + MANIFEST.  Nothing is moved or modified; the sums file is the
# verification anchor for the submission artifact.
cd "$(dirname "$0")/.." || exit 1
F=results/FREEZE-20261010
mkdir -p "$F"
{
  echo "freeze: five-model matrix final + follow-up tables/figures"
  echo "date: $(date -Is)"
  echo "tests: $(.venv/bin/python -m pytest tests/ -q 2>&1 | tail -1)"
  echo "trees: results src tests experiments scripts docs"
  echo "rows: $(cat results/real_*/replay/main.jsonl | wc -l) replay rows"
} > "$F/MANIFEST.txt"
find results src tests experiments scripts docs -type f \
  ! -path "results/FREEZE-*" ! -name "*.pyc" \
  ! -path "*__pycache__*" ! -path "*.venv*" -print0 \
  | xargs -0 sha256sum > "$F/SHA256SUMS"
wc -l "$F/SHA256SUMS"
sha256sum "$F/SHA256SUMS" "$F/MANIFEST.txt"
echo "FREEZE DONE $(date -Is)"