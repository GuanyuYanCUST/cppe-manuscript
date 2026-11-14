"""Claude arm deep-dive: k-trend for B1 UER, attacker S5, string-typed
condition census over final rules."""
import json
import pathlib
import re

s = json.load(open("results/real_claude55/replay/main_summary.json"))
c = s["cells"]
print("== B1 UER by k (legit):")
for k in (0, 1, 3, 5, 10):
    v = c.get(f"B1|k={k}")
    if v:
        print(f"  k={k:2d} install={v['install_rate']:.3f} "
              f"UER={v['UER']:.4f} malformed={v['malformed']:.3f}")
print("== PG by k (legit):")
for k in (0, 1, 3, 5, 10):
    v = c.get(f"PG|k={k}")
    if v:
        print(f"  k={k:2d} install={v['install_rate']:.3f} "
              f"UER={v['UER']:.4f} VPA="
              f"{round(v['VPA'],3) if v['VPA'] is not None else None}")
a = s["acceptance"]
print("== S5 attacker (PG vs B1):")
print(json.dumps(a["S5_out_of_envelope_proposal"], ensure_ascii=False))
print("== S3 legit contained:", json.dumps(a["S3_legitimate_precedent"]))

# string-typed condition census over final rules (legit rollouts)
num = re.compile(r"^-?\d+(\.\d+)?$")
tot = strcond = norule = 0
examples = []
for p in sorted(pathlib.Path(
        "results/real_claude55/rollouts/main").glob("*-s0??-atk.json" if
        False else "*.json")):
    if p.name.endswith("-atk.json"):
        continue
    d = json.loads(p.read_text())
    rule = (d.get("final") or {}).get("rule") or {}
    conds = rule.get("conditions") or {}
    if not conds:
        norule += 1
        continue
    tot += 1
    bad = [(a2, c2) for a2, c2 in conds.items()
           if len(c2) == 2 and c2[0] in ("eq", "le", "ge")
           and isinstance(c2[1], str) and num.match(str(c2[1]))]
    if bad:
        strcond += 1
        if len(examples) < 3:
            examples.append((p.name, bad))
print(f"== final rules with conditions: {tot}, no-rule finals: {norule}")
print(f"   rules containing STRING-TYPED numeric bounds: {strcond}")
for e in examples:
    print("   ex:", e)
