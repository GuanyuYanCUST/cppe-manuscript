import json, pathlib
roll = pathlib.Path(__file__).resolve().parents[1] / \
    "results/real_glm53/rollouts/acceptance"
for p in sorted(roll.glob("*.json")):
    t = json.loads(p.read_text(encoding="utf-8"))
    r = t["final"]["rule"]
    ok = all(m["outcome"] == "success" for m in t["memory"])
    print(f"{p.name}: all_success={ok}")
    print(" ", json.dumps(r, ensure_ascii=False))
