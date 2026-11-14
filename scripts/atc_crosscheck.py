"""Why does PG ATC% == B1 install% exactly, in every arm? Cross-tab
PG k=10 legit rows: proposed / atc_done / reject_reason pattern."""
import glob
import json

for d in ("real_glm53", "real_claude55", "real_gemini38flash",
          "real_deepseek41flash", "real_gpt56"):
    c = {"n": 0, "prop": 0, "prop_atc": 0, "noprop": 0,
         "noprop_atc": 0, "reasons": {}}
    for line in open(f"results/{d}/replay/main.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r.get("method") != "PG" or r.get("k_req") != 10 \
                or r.get("attacker") or "proposed" not in r:
            continue
        c["n"] += 1
        key = "prop" if r["proposed"] else "noprop"
        c[key] += 1
        c[f"{key}_atc"] += int(bool(r["atc_done"]))
        if r["proposed"] and not r["atc_done"]:
            rr = r.get("reject_reason") or "none"
            c["reasons"][rr.split(":")[0] + ("|inst" if r["installed"]
                                             else "|noinst")] = \
                c["reasons"].get(rr.split(":")[0]
                                 + ("|inst" if r["installed"]
                                    else "|noinst"), 0) + 1
    print(d, c)
