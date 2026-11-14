"""Per-API-channel metrics for the two mixed-channel arms.
Boundaries: GLM ts<20261009-163820 = bigmodel, else zhongkey (verified
by the 397-min gap at exactly index 395); GPT ts<20261009-190000 =
aizex, else zhongkey (documented switch time, no clean gap)."""
import json
import pathlib

CUT = {"real_glm53": "20261009-163820", "real_gpt56": "20261009-190000"}
PHASE1 = {"real_glm53": "bigmodel", "real_gpt56": "aizex"}

for d in ("real_glm53", "real_gpt56"):
    cut = CUT[d]
    phase = {}
    n1 = 0
    for p in pathlib.Path(f"results/{d}/rollouts/main").glob("*.json"):
        t = json.loads(p.read_text(encoding="utf-8")).get("ts", "")
        ch1 = t < cut
        n1 += ch1
        phase[p.stem] = PHASE1[d] if ch1 else "zhongkey"
    print(f"== {d}: {PHASE1[d]}={n1} zhongkey={len(phase)-n1} ==")
    agg = {}
    for line in open(f"results/{d}/replay/main.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r.get("k_req") != 10 or r.get("attacker") or "proposed" not in r:
            continue
        name = f"{r['domain']}-{r['channel']}-s{r['seed']:03d}"
        c = agg.setdefault(phase[name],
                           {"n": 0, "prop": 0, "b1_uer": 0,
                            "pg_vpa": 0, "mal": 0})
        if r["method"] == "B1":
            c["n"] += 1
            c["prop"] += r["proposed"]
            c["b1_uer"] += r["unauth_effect"]
            c["mal"] += int(str(r.get("reject_reason") or "")
                            .startswith("MALFORMED"))
        if r["method"] == "PG" and r["proposed"]:
            c["pg_vpa"] += r["valid_accepted"]
    for ch, c in agg.items():
        vpa = c["pg_vpa"] / c["prop"] if c["prop"] else None
        print(f"  {ch:9s} n={c['n']:4d} propose={c['prop']/c['n']:.3f}"
              f" B1_UER={c['b1_uer']/c['n']:.3f}"
              f" PG_VPA={vpa if vpa is None else round(vpa,3)}"
              f" malform={c['mal']/c['n']:.3f}")
