"""List final-mode + rule sketch for every rollout json in a dir (argv: dir)."""
import json
import pathlib
import sys

for f in sorted(pathlib.Path(sys.argv[1]).glob("*.json")):
    d = json.loads(f.read_text())
    fin = d.get("final") or {}
    rule = fin.get("rule") or {}
    cond = rule.get("conditions") or {}
    admits = sum(1 for t in d.get("turns", []) if t.get("admitted"))
    print(f"{f.name:42s} turns_admit={admits:2d}/{d.get('n_tasks')} "
          f"final_mode={str(fin.get('mode')):10s} "
          f"rule={rule.get('action')!s}:{rule.get('resource')!s}({len(cond)}conds)")
    raw = fin.get("reply_raw") or ""
    if fin.get("mode") is None and raw:
        print("   raw[:200]:", raw[:200].replace("\n", " "))
