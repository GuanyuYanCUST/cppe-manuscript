import json

d = "real_glm53"
n_atk_rows = 0
per_k = {}
oop_k10 = []
for line in open(f"results/{d}/replay/main.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if r.get("method") != "PG":
        continue
    if r.get("attacker"):
        n_atk_rows += 1
        per_k[r["k_req"]] = per_k.get(r["k_req"], 0) + 1
        if r["k_req"] == 10 and r.get("n_covered_out_of_D"):
            oop_k10.append((r["domain"], r["seed"], r["channel"],
                            r["n_covered_out_of_D"]))
print("GLM PG attacker rows by k:", dict(sorted(per_k.items())))
print("GLM PG k=10 oop count:", len(oop_k10))
print("first 5:", oop_k10[:5])
