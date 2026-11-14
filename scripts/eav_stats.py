"""EAV (Excess Authority Volume) of admitted rules, from replay rows
(zero API cost).  n_covered_out_of_D on a row = number of universe
requests the candidate rule admits outside the root envelope — for
installed rows that is exactly the admitted excess authority.

Outputs results/TABLES/eav.{json,md}.  Fig A3 = distribution plot of
per-installed-rule EAV by method.
"""
import json
import pathlib
import sys

sys.path.insert(0, "src")
from pguard.domains import get_domain            # noqa: E402
from pguard.stats import percentiles             # noqa: E402

ARMS = [("GLM-5.3", "real_glm53"), ("Claude-5.5", "real_claude55"),
        ("Gemini-3.8-flash", "real_gemini38flash"),
        ("DeepSeek-v4.1-flash", "real_deepseek41flash"),
        ("GPT-5.6", "real_gpt56")]
UNI = {d: len(get_domain(d).universe)
       for d in ("cloudops", "procurement", "finance", "dataaccess")}
OUT = pathlib.Path("results/TABLES")
OUT.mkdir(exist_ok=True)

out = {"universe_sizes": UNI, "per_arm": {}}
for name, d in ARMS:
    per = {}
    for line in open(f"results/{d}/replay/main.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r.get("k_req") != 10 or "proposed" not in r:
            continue
        key = (r["method"], bool(r["attacker"]))
        c = per.setdefault(key, {"n": 0, "installed": 0, "eav": []})
        c["n"] += 1
        if r["installed"]:
            c["installed"] += 1
            eav = r["n_covered_out_of_D"] or 0
            c["eav"].append(eav)
            c.setdefault("eav_norm", []).append(
                eav / UNI[r["domain"]])
    out["per_arm"][name] = {}
    for (m, atk), c in per.items():
        e = c["eav"]
        if e:
            p = percentiles(e, (50, 90, 95))
            stats = {"n": c["n"], "installed": c["installed"],
                     "mean": sum(e) / len(e), "median": p[50],
                     "p90": p[90], "p95": p[95], "max": max(e),
                     "frac_gt0": sum(1 for x in e if x > 0) / len(e),
                     "mean_norm": sum(c.get("eav_norm", [0]))
                     / max(len(c.get("eav_norm", [1])), 1)}
        else:
            stats = {"n": c["n"], "installed": c["installed"],
                     "mean": 0.0, "median": 0, "p90": 0, "p95": 0,
                     "max": 0, "frac_gt0": 0.0, "mean_norm": 0.0}
        out["per_arm"][name][f"{m}|{'atk' if atk else 'legit'}"] = stats

json.dump(out, open(OUT / "eav.json", "w"), indent=1, ensure_ascii=False)
md = ["# EAV of admitted rules (k=10; absolute universe-request count;"
      f" universe sizes {UNI})\n",
      "| model | method | arm | installed | mean | median | p90 | max |"
      " >0 | mean/|U| |", "|---|---|---|---|---|---|---|---|---|---|"]
for name in dict(ARMS):
    for mk, s in sorted(out["per_arm"][name].items()):
        m, arm = mk.split("|")
        md.append(f"| {name} | {m} | {arm} | {s['installed']} |"
                  f" {s['mean']:.1f} | {s['median']} | {s['p90']} |"
                  f" {s['max']} | {s['frac_gt0']:.2f} |"
                  f" {s['mean_norm']:.3f} |")
(OUT / "eav.md").write_text("\n".join(md), encoding="utf-8")
print("wrote", OUT / "eav.md")
