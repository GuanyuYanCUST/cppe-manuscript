"""S5 (out-of-envelope proposals) split by traffic type — corrects the
arm-level S5 in main_summary.json, which has no attacker filter and so
pools legit+attacker traffic.  k=10, PG rows define trajectories."""
import json

ARMS = [("GLM-5.3", "real_glm53"), ("Claude-5.5", "real_claude55"),
        ("Gemini-3.8-flash", "real_gemini38flash"),
        ("DeepSeek-v4.1-flash", "real_deepseek41flash"),
        ("GPT-5.6", "real_gpt56")]
out = {}
tot = {"legit": [0, 0, 0], "atk": [0, 0, 0]}   # oop, b1_unauth, pg_rej
for name, d in ARMS:
    r6 = {"legit": [0, 0, 0], "atk": [0, 0, 0]}
    for line in open(f"results/{d}/replay/main.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if (r.get("k_req") != 10 or not r.get("n_covered_out_of_D")
                or r.get("method") not in ("B1", "PG")
                or "proposed" not in r):
            continue
        arm = "atk" if r.get("attacker") else "legit"
        i = 0 if r["method"] == "PG" else 1
        if r["method"] == "PG":
            r6[arm][0] += 1
            r6[arm][2] += int(not r["installed"])
            tot[arm][0] += 1
            tot[arm][2] += int(not r["installed"])
        else:
            r6[arm][1] += int(bool(r["unauth_effect"]))
            tot[arm][1] += int(bool(r["unauth_effect"]))
    out[name] = r6
    print(f"{name:20s} legit oop={r6['legit'][0]:3d} "
          f"(PG rej {r6['legit'][2]}, B1 unauth {r6['legit'][1]:3d})"
          f" | atk oop={r6['atk'][0]:3d} "
          f"(PG rej {r6['atk'][2]}, B1 unauth {r6['atk'][1]:3d})")
print(f"{'TOTAL':20s} legit oop={tot['legit'][0]} "
      f"(PG rej {tot['legit'][2]}, B1 unauth {tot['legit'][1]}) | "
      f"atk oop={tot['atk'][0]} (PG rej {tot['atk'][2]}, "
      f"B1 unauth {tot['atk'][1]})")
json.dump(out, open("results/TABLES/s5_split.json", "w"), indent=1)
print("wrote results/TABLES/s5_split.json")
