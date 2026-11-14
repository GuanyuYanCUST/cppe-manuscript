"""Print acceptance-pilot summary for a provider dir (argv: results/real_<p>/rollouts/acceptance)."""
import json
import pathlib
import sys

d = pathlib.Path(sys.argv[1])
tot_in = tot_out = tot_calls = 0
for f in sorted(d.glob("*.json")):
    r = json.loads(f.read_text())
    ro = r.get("rollout", r)
    tasks = ro.get("tasks") or ro.get("turns") or []
    admitted = sum(1 for t in tasks if t.get("admitted"))
    modes = [t.get("mode") for t in tasks]
    final = ro.get("final_mode")
    # cost: walk raw records if present
    raw = r.get("raw") or {}
    calls = raw.get("calls") or ro.get("calls") or []
    for c in calls:
        u = c.get("usage") or {}
        if isinstance(u, str):
            try:
                u = json.loads(u)
            except Exception:
                u = {}
        tot_in += u.get("prompt_tokens", 0) or 0
        tot_out += u.get("completion_tokens", 0) or 0
    tot_calls += len(calls)
    print(f"{f.name:40s} tasks={len(tasks):2d} admitted={admitted:2d} "
          f"final={final!s:8s} task_modes={modes}")
print(f"calls={tot_calls} in={tot_in} out={tot_out}")
