import json

tot = {"B1": 0, "PG": 0}
oop = {"B1": 0, "PG": 0}
ks = {}
for d in ("real_glm53", "real_claude55", "real_gemini38flash",
          "real_deepseek41flash", "real_gpt56"):
    for line in open(f"results/{d}/replay/main.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r.get("attacker") and r.get("method") in tot \
                and "proposed" in r:
            tot[r["method"]] += 1
            ks[r["k_req"]] = ks.get(r["k_req"], 0) + 1
            if r.get("n_covered_out_of_D"):
                oop[r["method"]] += 1
print("atk B1/PG rows (all k):", tot, " oop:", oop)
print("k distribution:", dict(sorted(ks.items())))
