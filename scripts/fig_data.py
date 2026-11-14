"""Figure data aggregation (Fig 6/7/8 + per-model splits), one pass
over the five replay jsonl files.  All-model aggregates are computed at
render time from per-model cells (equal n per cell)."""
import json
import pathlib
import sys

ARMS = [("GLM-5.3", "real_glm53"), ("Claude-5.5", "real_claude55"),
        ("Gemini-3.8-flash", "real_gemini38flash"),
        ("DeepSeek-v4.1-flash", "real_deepseek41flash"),
        ("GPT-5.6", "real_gpt56")]
DOMS = ("cloudops", "procurement", "finance", "dataaccess")
CHANS = ("episodic", "vector_rag", "skill_consolidation",
         "policy_distillation")
OUT = pathlib.Path("results/TABLES")
# optional args: <replay_dir (default "replay")> <out_name (default
# "fig_data.json")> — v2 pass: `fig_data.py replay_v2 fig_data_v2.json`
# picks up the F-C2-fixed cppe_scope field; default run unchanged.
REPLAY = sys.argv[1] if len(sys.argv) > 1 else "replay"
OUTF = sys.argv[2] if len(sys.argv) > 2 else "fig_data.json"

cell = {}   # (model, dom, method, k) -> counts (legit only)
upr = {}    # (model, dom, chan) -> {n, prop, oop}   (PG rows, k=10)
for name, d in ARMS:
    for line in open(f"results/{d}/{REPLAY}/main.jsonl",
                     encoding="utf-8"):
        r = json.loads(line)
        if "proposed" not in r or r["attacker"]:
            continue
        m, k = r["method"], r["k_req"]
        c = cell.setdefault((name, r["domain"], m, k),
                            {"n": 0, "uer": 0, "vpa": 0, "prop": 0,
                             "inst": 0, "oop": 0, "scope": 0,
                             "atc": 0, "atc_case": 0})
        c["n"] += 1
        c["uer"] += int(bool(r["unauth_effect"]))
        c["vpa"] += int(bool(r["valid_accepted"]))
        c["prop"] += int(bool(r["proposed"]))
        c["inst"] += int(bool(r["installed"]))
        c["scope"] += int(bool(r.get("cppe_scope")))
        c["atc"] += int(bool(r.get("atc_done")))
        c["atc_case"] += int(bool(r.get("atc_via_case")))
        if m == "PG":
            # candidate containment is trajectory-level: record the
            # out-of-envelope-proposal count on the PG cell for every k
            c["oop"] += int(bool(r["proposed"])
                            and not r["candidate_contained"])
        if m == "PG" and k == 10:
            u = upr.setdefault((name, r["domain"], r["channel"]),
                               {"n": 0, "prop": 0, "oop": 0})
            u["n"] += 1
            u["prop"] += int(bool(r["proposed"]))
            u["oop"] += int(bool(r["proposed"])
                            and not r["candidate_contained"])

out = {"models": [n for n, _ in ARMS], "domains": list(DOMS),
       "channels": list(CHANS),
       "cell": {f"{m}|{dm}|{me}|k={k}": v
                for (m, dm, me, k), v in cell.items()},
       "upr": {f"{m}|{dm}|{c}": v for (m, dm, c), v in upr.items()}}
json.dump(out, open(OUT / OUTF, "w"), indent=1,
          ensure_ascii=False)

# quick sanity print: all-model Fig6 cells (per domain x method, k=10)
print("Fig6-style all-model cells (k=10):")
for dm in DOMS:
    line = [dm]
    for me in ("B0", "B1", "B2", "B3", "B4", "B5", "PG"):
        n = uer = vpa = prop = 0
        for m, _ in ARMS:
            c = cell.get((m, dm, me, 10))
            if c:
                n += c["n"]; uer += c["uer"]; vpa += c["vpa"]
                prop += c["prop"]
        line.append(f"{me} UER={uer/n:.3f} VPA="
                    f"{(vpa/prop if prop else 0):.3f}")
    print("  " + " | ".join(line))
print("wrote", OUT / OUTF)
