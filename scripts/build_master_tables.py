"""Five-arm master tables from replay jsonl (zero API cost).

Outputs under results/TABLES/:
- master_table.json / .md   — model × method × k aggregates + Wilson CIs,
                              attacker S5 table, PG-vs-B1 utility table
- fig8_upr.json             — UPR matrix (model × domain × channel)
- fig7_dose.json            — UPR & B1-UER vs k (prefix dose-response)
- b1b6_diff.json            — per-trajectory B1 vs B6 verdict mismatches
"""
import json
import pathlib
import sys

sys.path.insert(0, "src")
from pguard.stats import wilson  # noqa: E402

ARMS = [("GLM-5.3", "real_glm53"), ("Claude-5.5", "real_claude55"),
        ("Gemini-3.8-flash", "real_gemini38flash"),
        ("DeepSeek-v4.1-flash", "real_deepseek41flash"),
        ("GPT-5.6", "real_gpt56")]
OUT = pathlib.Path("results/TABLES")
OUT.mkdir(exist_ok=True)

FIELDS = ("proposed", "installed", "cppe_issuer", "cppe_scope",
          "unauth_effect", "valid_accepted", "atc_done", "atc_via_case")
RATES = ("propose_rate", "install_rate", "cppe_issuer", "cppe_scope_any",
         "UER", "ATC", "ATC_via_case", "malformed")


def pct(k, n):
    return None if not n else 100.0 * k / n


master, fig8, fig7, b1b6, util = {}, {}, {}, {}, {}
b1b6 = {"compared": 0, "mismatch": 0, "examples": []}

for name, d in ARMS:
    agg, pgk, pgdc, per_traj = {}, {}, {}, {}
    for line in open(f"results/{d}/replay/main.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if "proposed" not in r:      # REPLAY_ERROR row — honest skip
            continue
        key = (r["method"], r["k_req"], bool(r["attacker"]))
        a = agg.setdefault(key, {f: 0 for f in FIELDS} |
                           {"n": 0, "malformed": 0, "n_tasks": 0,
                            "turn_successes": 0})
        a["n"] += 1
        for f in FIELDS:
            a[f] += int(bool(r.get(f)))
        a["malformed"] += int(str(r.get("reject_reason") or "")
                              .startswith("MALFORMED"))
        a["n_tasks"] += r.get("n_tasks", 0)
        a["turn_successes"] += r.get("turn_successes", 0)
        if r["method"] == "PG":
            oop = int(r["proposed"] and not r["candidate_contained"])
            if not r["attacker"]:
                k = pgk.setdefault(r["k_req"], {"n": 0, "prop": 0, "oop": 0})
                k["n"] += 1
                k["prop"] += int(r["proposed"])
                k["oop"] += oop
                if r["k_req"] == 10:   # fig8 cell + per-domain B1 UER
                    c = pgdc.setdefault((r["domain"], r["channel"]),
                                        {"n": 0, "prop": 0, "oop": 0,
                                         "b1_uer": 0})
                    c["n"] += 1
                    c["prop"] += int(r["proposed"])
                    c["oop"] += oop
        if r["method"] in ("B1", "B6") and not r["attacker"]:
            t = per_traj.setdefault((r["domain"], r["channel"], r["seed"],
                                     r["k_req"]), {})
            t[r["method"]] = (int(bool(r.get("installed"))),
                              int(bool(r.get("unauth_effect"))),
                              int(bool(r.get("valid_accepted"))))
    master[name] = {f"{m}|k={k}|{'atk' if atk else 'legit'}": v
                    for (m, k, atk), v in agg.items()}
    # B1 UER per dom×chan (fig6 split): second cheap pass
    for line in open(f"results/{d}/replay/main.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r.get("method") == "B1" and r.get("k_req") == 10 \
                and not r["attacker"] and "proposed" in r:
            c = pgdc.setdefault((r["domain"], r["channel"]),
                                {"n": 0, "prop": 0, "oop": 0, "b1_uer": 0})
            c["b1_uer"] += int(bool(r["unauth_effect"]))
    fig8[name] = {f"{dm}|{ch}": v for (dm, ch), v in pgdc.items()}
    fig7[name] = {f"k={k}": {**v,
                             "propose_pct": pct(v["prop"], v["n"]),
                             "upr_over_n": pct(v["oop"], v["n"]),
                             "upr_over_proposed":
                                 pct(v["oop"], v["prop"]),
                             "b1_uer_pct": pct(
                                 agg[("B1", k, False)]["unauth_effect"],
                                 agg[("B1", k, False)]["n"])}
                  for k, v in pgk.items()}
    for t in per_traj.values():
        if "B1" in t and "B6" in t:
            b1b6["compared"] += 1
            if t["B1"] != t["B6"]:
                b1b6["mismatch"] += 1
                if len(b1b6["examples"]) < 5:
                    b1b6["examples"].append(t)
    # utility row from PG/B1 k=10 legit + summary acceptance
    a10 = agg[("PG", 10, False)]
    b10 = agg[("B1", 10, False)]
    s = json.load(open(f"results/{d}/replay/main_summary.json"))["acceptance"]
    s5 = s["S5_out_of_envelope_proposal"]
    util[name] = {
        "task_success": a10["turn_successes"] / a10["n_tasks"],
        "atc_pg": pct(a10["atc_done"], a10["n"]),
        "atc_b1": pct(b10["atc_done"], b10["n"]),
        "case_only": s["S2_case_only"]["case_mode_count"],
        "atk_oop": s5["n_out_of_envelope_proposals"],
        "atk_pg_rejected_all": s5["pg_rejected_all"],
        "atk_b1_unauth": s5["b1_unauth_effect"]}

json.dump({"master": master, "fig8_upr": fig8, "fig7_dose": fig7,
           "b1b6": b1b6, "utility": util},
          open(OUT / "master_table.json", "w"), indent=1, ensure_ascii=False)

md = ["# Five-arm master tables (generated from replay/main.jsonl)\n"]
md.append("## Table 4 core: k=10 legit, UER Wilson 95% CI\n")
for name, _ in ARMS:
    md.append(f"\n### {name}\n")
    md.append("| method | n | propose% | install% | UER% [CI] | VPA% |"
              " ATC% | malformed% |")
    md.append("|---|---|---|---|---|---|---|---|")
    for mk, a in sorted(master[name].items()):
        if not mk.endswith("|k=10|legit"):
            continue
        n = a["n"]
        lo, hi = wilson(a["unauth_effect"], n)
        vpa = pct(a["valid_accepted"], a["proposed"]) \
            if a["proposed"] else 0.0
        md.append(
            f"| {mk.split('|')[0]} | {n} | {pct(a['proposed'], n):.1f} |"
            f" {pct(a['installed'], n):.1f} |"
            f" {pct(a['unauth_effect'], n):.1f}"
            f" [{100*lo:.1f},{100*hi:.1f}] | {vpa:.1f} |"
            f" {pct(a['atc_done'], n):.1f} | {pct(a['malformed'], n):.1f} |")
md.append("\n## Utility & attacker (PG vs B1, k=10)\n")
md.append("ATC (authorized-task completion via the case channel) is a"
          " PG-mechanism metric: B0-B6 implement no case channel, so their"
          " ATC is N/A by construction, not zero.\n")
md.append("| model | task_success | ATC PG% | ATC B1 | case-only |"
          " atk OOP | PG reject | B1 unauth |")
md.append("|---|---|---|---|---|---|---|---|")
for name, u in util.items():
    md.append(f"| {name} | {u['task_success']:.3f} | {u['atc_pg']:.1f} |"
              f" N/A | {u['case_only']} | {u['atk_oop']} |"
              f" {'ALL' if u['atk_pg_rejected_all'] else 'NO'} |"
              f" {u['atk_b1_unauth']} |")
md.append(f"\n## B1 vs B6 verdict identity: compared {b1b6['compared']},"
          f" mismatch {b1b6['mismatch']}\n")
(OUT / "master_table.md").write_text("\n".join(md), encoding="utf-8")
print("wrote", OUT / "master_table.md")
print("B1 vs B6 (legit, all arms): compared", b1b6["compared"],
      "mismatch", b1b6["mismatch"])
