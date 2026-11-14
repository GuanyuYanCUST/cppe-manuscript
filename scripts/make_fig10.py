"""Figure 10: adaptive attacks (mock E6 + REAL 5-model exception
farming overlay), challenger corruption (E9), overload (E9)."""
import json
import pathlib
import sys

sys.path.insert(0, "src")
from pguard.stats import wilson                    # noqa: E402

import matplotlib                                 # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                    # noqa: E402
import numpy as np                                 # noqa: E402

FIGS = pathlib.Path("results/FIGS")
FIGS.mkdir(parents=True, exist_ok=True)
E6 = json.load(open("results/E6/E6-adaptive-20261008-160427/summary.json"))
E9 = json.load(open("results/E9/E9-robustness-20261008-160608/summary.json"))
plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "figure.dpi": 200, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False})

fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.0))

# ---- (a) adaptive attacks: E6 mock (budget=50) + real farming overlay
names = {"T1_exception_farming": "Farming\n(mock)",
         "T2_similarity_nudging": "Nudging",
         "T3_cross_resource": "Cross-res",
         "T4_exact_log_laundering": "Log-launder",
         "T5_verification_pressure": "Verif-pressure"}
groups, b1_v, pg_v, b1_n = [], [], [], []
for atk, label in names.items():
    rows = E6["raw"][atk]["50"]
    b1 = sum(1 for x in rows if x["out"].get("B1", {}).get("effect"))
    nb1 = sum(1 for x in rows if "B1" in x["out"])
    pg = sum(1 for x in rows if x["out"].get("PG", {}).get("effect"))
    npg = sum(1 for x in rows if "PG" in x["out"])
    if not nb1:                     # fallback: strongest available baseline
        for alt in ("B6", "B4", "B2"):
            nb1 = sum(1 for x in rows if alt in x["out"])
            if nb1:
                b1 = sum(1 for x in rows
                         if x["out"].get(alt, {}).get("effect"))
                break
    groups.append(label)
    b1_v.append(100 * b1 / nb1 if nb1 else 0.0)
    pg_v.append(100 * pg / npg if npg else 0.0)
    b1_n.append(nb1)
# real farming overlay: 5-model attacker arm, out-of-envelope final
# rules at k=10 (PG rows define the trajectory count; B1 row of the
# same trajectory gives the baseline effect)
tot = b1e = pge = 0
for d in ("real_glm53", "real_claude55", "real_gemini38flash",
          "real_deepseek41flash", "real_gpt56"):
    for line in open(f"results/{d}/replay/main.jsonl",
                     encoding="utf-8"):
        r = json.loads(line)
        if (r.get("method") in ("B1", "PG") and r.get("k_req") == 10
                and r.get("attacker") and r.get("n_covered_out_of_D")
                and "proposed" in r):
            tot += 1
            b1e += int(r["method"] == "B1" and r["unauth_effect"])
            pge += int(r["method"] == "PG" and r["unauth_effect"])
ntraj = tot // 2                     # B1 + PG rows per trajectory
groups.append(f"Farming\n(real, n={ntraj})")
b1_v.append(100 * b1e / ntraj); pg_v.append(100 * pge / ntraj)
ax = axes[0]
x = np.arange(len(groups))
ax.bar(x - 0.19, b1_v, 0.36, color="#5778a4", edgecolor="#333",
       linewidth=0.4, label="History reuse (B1)")
ax.bar(x + 0.19, pg_v, 0.36, color="#2b6a6a", edgecolor="#333",
       linewidth=0.4, label="PRECEDENTGUARD")
ax.set_xticks(x)
ax.set_xticklabels(groups, fontsize=6.5)
ax.set_ylabel("Attack success / unsafe effect (%)")
ax.set_ylim(0, 105)
ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
ax.set_axisbelow(True)
ax.legend(frameon=False)
ax.set_title("(a) Adaptive attacks", fontsize=9, loc="left")

# ---- (b) challenger corruption
ax = axes[1]
ps = sorted(E9["corruption"], key=lambda s: float(s.split("=")[1]))
pct = [100 * float(p.split("=")[1]) for p in ps]
frr = [100 * E9["corruption"][p]["FRR"]["rate"] for p in ps]
uns = [100 * E9["corruption"][p]["unsafe_admissions"]["rate"]
       for p in ps]
ax.plot(pct, frr, marker="o", markersize=2.8, color="#8c5b3f",
        label="False rejection (FRR)")
ax.plot(pct, uns, marker="s", markersize=2.8, color="#2b6a6a",
        label="Unsafe admission")
ax.set_xlabel("spurious challenger edges (%)")
ax.set_ylabel("rate (%)")
ax.set_ylim(-3, 103)
ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
ax.set_axisbelow(True)
ax.legend(frameon=False)
ax.set_title("(b) Challenger corruption", fontsize=9, loc="left")

# ---- (c) overload
ax = axes[2]
loads = sorted(E9["overload"], key=lambda s: int(s.rstrip("x")))
lx = [int(l.rstrip("x")) for l in loads]
admit = [100 * E9["overload"][l]["admit_rate"]["rate"] for l in loads]
denial = [100 * E9["overload"][l]["denial_rate"]["rate"] for l in loads]
unsafe = [100 * E9["overload"][l]["unsafe_admissions"]["rate"]
          for l in loads]
ax.plot(lx, admit, marker="o", markersize=2.8, color="#5778a4",
        label="Legitimate admissions")
ax.plot(lx, denial, marker="^", markersize=2.8, color="#c98c5a",
        label="Denials (load shedding)")
ax.plot(lx, unsafe, marker="s", markersize=2.8, color="#2b6a6a",
        label="Unsafe admissions")
ax.set_xscale("log")
ax.set_xticks(lx)
ax.set_xticklabels([f"{l}x" for l in lx])
ax.set_xlabel("proposal load multiplier")
ax.set_ylabel("rate (%)")
ax.set_ylim(-3, 103)
ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
ax.set_axisbelow(True)
ax.legend(frameon=False)
ax.set_title("(c) Overload (fail-closed)", fontsize=9, loc="left")

fig.tight_layout()
fig.savefig(FIGS / "fig10_attacks_degradation.pdf")
plt.close(fig)
print("fig10 written; real farming overlay n =", ntraj,
      "B1", b1e, "PG", pge)
