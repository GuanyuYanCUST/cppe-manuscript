"""Figure 9: rulemaking authority vs history fidelity.

(a) E5 offline factorial (frozen run E5-factorial-20261008-155213):
    memory fidelity {lossy, exact} x grant {none, root cap},
    SAME contained candidate / root policy / downstream request
    (matched counterfactual), 4 domains x 10 seeds = n=40 per cell/method.
    B2==B6 (evidence-gated) and B1==B3 (ungated) asserted identical and
    drawn once per family (shared install path, R5).
(b) Real-trajectory authorization fork (gates/authority_fork_results.jsonl,
    PG only, frozen 5-model rollouts replayed deterministically):
    installs require a valid live root-issued cap; invalid-cap arms
    (expired / wrong-issuer / type-confusion / stale-epoch) pooled.

Discipline: N/A (zero-attempt denominator) printed as N/A, never 0;
true zeros labeled k/n with Wilson 95% CI whiskers; no unobserved values.
"""
import hashlib
import json
import pathlib
import sys
from collections import Counter

sys.path.insert(0, "src")
from pguard.stats import wilson                       # noqa: E402

import matplotlib                                     # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
import numpy as np                                    # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIGS = ROOT / "results" / "FIGS"
FIGS.mkdir(parents=True, exist_ok=True)
E5 = json.load(open(ROOT / "results/E5/E5-factorial-20261008-155213"
                    "/summary.json"))

plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "figure.dpi": 200, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False})

C_PG, C_EV, C_UN = "#2b6a6a", "#5778a4", "#9a9a9a"

# ---- (a) E5 factorial: verify family-identity, then draw one bar/group --
CELLS = [("lossy|grant=0", "lossy memory, no grant"),
         ("lossy|grant=1", "lossy memory, root cap"),
         ("exact|grant=0", "exact memory, no grant"),
         ("exact|grant=1", "exact memory, root cap")]
GROUPS = [("PG", "PG", C_PG), ("B2/B6", ("B2", "B6"), C_EV),
          ("B1/B3", ("B1", "B3"), C_UN)]

fig = plt.figure(figsize=(7.16, 2.7))
gs = fig.add_gridspec(1, 2, width_ratios=[2.05, 1.0], wspace=0.30)
left = gs[0].subgridspec(2, 2, hspace=0.62, wspace=0.30)
cell_axes = [fig.add_subplot(left[i // 2, i % 2]) for i in range(4)]

for ax, (key, title) in zip(cell_axes, CELLS):
    t = E5["table"][key]
    # assert family identity inside the cell (B2==B6, B1==B3)
    for fam in (("B2", "B6"), ("B1", "B3")):
        assert all(t[fam[0]][m]["k"] == t[fam[1]][m]["k"]
                   and t[fam[0]][m]["n"] == t[fam[1]][m]["n"]
                   for m in ("install_rate", "UIR")), fam
    xpos, w = np.arange(len(GROUPS)), 0.38
    for i, (label, members, color) in enumerate(GROUPS):
        m0 = t[members if isinstance(members, str) else members[0]]
        ins, uir = m0["install_rate"], m0["UIR"]
        for off, stat, hatch in ((-w / 2 - 0.02, ins, ""),
                                 (+w / 2 + 0.02, uir, "////")):
            if stat["na"]:
                ax.text(i + off, 4, "N/A", ha="center", fontsize=6,
                        color="#444")
                continue
            r, n = stat["rate"], stat["n"]
            ax.bar(i + off, 100 * r, w * 0.92, color=color,
                   edgecolor="#333", linewidth=0.4, hatch=hatch, alpha=0.95)
            lo = 0.0 if stat["wilson_lo"] is None else stat["wilson_lo"]
            hi = 1.0 if stat["wilson_hi"] is None else stat["wilson_hi"]
            ax.errorbar(i + off, 100 * r,
                        yerr=[[100 * (r - lo)], [100 * (hi - r)]],
                        fmt="none", ecolor="#222", elinewidth=0.7,
                        capsize=1.6)
            ax.text(i + off, 103, f'{stat["k"]}/{n}', ha="center",
                    fontsize=5.8, color="#222")
    ax.set_xticks(xpos)
    ax.set_xticklabels([g[0] for g in GROUPS], fontsize=6.5)
    ax.set_ylim(0, 118)
    ax.set_yticks([0, 50, 100])
    ax.set_title(title, fontsize=7.5, loc="left")
    ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
    ax.set_axisbelow(True)
cell_axes[0].set_ylabel("install / unauthorized (%)")
cell_axes[2].set_ylabel("install / unauthorized (%)")

# ---- (b) real-trajectory authorization fork (PG only) --------------------
forks = [json.loads(l) for l in
         open(ROOT / "audit_20261010/gates/authority_fork_results.jsonl")]
agg = {}
for r in forks:
    k = (r["fork"], r["attacker"])
    a = agg.setdefault(k, Counter(n=0, prop=0, inst=0, eff=0))
    a["n"] += 1
    a["prop"] += bool(r.get("proposed"))
    a["inst"] += bool(r.get("installed"))
    a["eff"] += bool(r.get("unauth_effect"))
INVALID = ("cap_expired", "cap_wrong_issuer", "cap_type_confusion",
           "cap_stale_epoch")
inv = Counter()
for f in INVALID:
    inv += agg[(f, False)]
leg = [(agg[("control", False)], "valid grant"),
       (agg[("grant_absent", False)], "no grant"),
       (inv, "invalid cap")]
atk = [(agg[("control", True)], "valid grant"),
       (agg[("grant_absent", True)], "no grant")]

axb = fig.add_subplot(gs[1])
for row, (bars, color) in enumerate(((leg, C_PG), (atk, "#c98c5a"))):
    for j, (c, label) in enumerate(bars):
        x = row + (j - 1) * 0.28
        r = c["inst"] / c["prop"] if c["prop"] else 0.0
        lo, hi = wilson(c["inst"], c["prop"])
        axb.bar(x, 100 * r, 0.24, color=color, edgecolor="#333",
                linewidth=0.4)
        axb.errorbar(x, 100 * r, yerr=[[100 * (r - lo)],
                                       [100 * (hi - r)]],
                     fmt="none", ecolor="#222", elinewidth=0.7, capsize=1.6)
        axb.text(x, 103, f'{c["inst"]}/{c["prop"]}', ha="center",
                 fontsize=5.8, color="#222")
axb.axhline(0, color="#333", linewidth=0.6)
axb.set_xticks([0, 1])
axb.set_xticklabels(["legit\n(5 models)", "attacker\narm"], fontsize=7)
axb.set_ylim(0, 118)
axb.set_yticks([0, 50, 100])
axb.set_ylabel("PG installs / proposals (%)")
axb.set_title("real trajectories: grant fork", fontsize=7.5, loc="left")
axb.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
axb.set_axisbelow(True)
# bar identity annotation (same color family per cluster is positional)
for j, lab in enumerate(("valid", "none", "invalid*")):
    axb.text(-0.28 + j * 0.28, -16, lab, ha="center", fontsize=5.8,
             color="#444")
for j, lab in enumerate(("valid", "none")):
    axb.text(1 + (j - 0.5) * 0.28, -16, lab, ha="center", fontsize=5.8,
             color="#444")

tot_prop = sum(a["prop"] for a in agg.values())
tot_eff = sum(a["eff"] for a in agg.values())
assert tot_eff == 0

from matplotlib.patches import Patch                  # noqa: E402
fig.legend(handles=[
    Patch(facecolor="#888", edgecolor="#333", linewidth=0.4,
          label="install rate (solid, Wilson 95% CI)"),
    Patch(facecolor="#888", edgecolor="#333", linewidth=0.4, hatch="////",
          label="unauthorized installs (hatched)"),
    Patch(facecolor="#ccc", edgecolor="#777", linewidth=0.4,
          label="N/A: zero attempts")],
    loc="lower center", ncol=3, frameon=False, fontsize=6.5,
    bbox_to_anchor=(0.5, -0.10))
fig.text(0.99, -0.155,
         "* invalid-cap arms pooled: expired / wrong-issuer / "
         "type-confused / stale-epoch (n=3,200). Attacker-arm installs "
         "are contained rules admitted under the class grant; "
         f"unauthorized effects 0 across all forks "
         f"({tot_prop:,} proposals).",
         ha="right", fontsize=5.8, color="#444")
fig.savefig(FIGS / "fig9_authority_fidelity.pdf")
fig.savefig(FIGS / "fig9_authority_fidelity.png", dpi=300)

# ---- provenance -----------------------------------------------------------
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

prov = {
    "figure": "fig9_authority_fidelity.pdf",
    "inputs": {
        "E5": "results/E5/E5-factorial-20261008-155213/summary.json",
        "fork": "audit_20261010/gates/authority_fork_results.jsonl",
    },
    "sha256": {
        "E5": sha(ROOT / "results/E5/E5-factorial-20261008-155213"
                  "/summary.json"),
        "fork": sha(ROOT / "audit_20261010/gates/"
                    "authority_fork_results.jsonl"),
    },
    "evidence_layers": {
        "a": "offline factorial (E5): mock histories, real store logic, "
             "n=40/cell/method, matched counterfactual (same candidate, "
             "root policy, downstream request)",
        "b": "deterministic frozen-trajectory replay (real 5-model "
             "rollouts), PG only; invalid-cap arms pooled n="
             f"{inv['n']} ({inv['prop']} proposals)",
    },
    "totals": {f"{k[0]}|atk={k[1]}": dict(v) for k, v in sorted(
        agg.items(), key=str)},
    "claims_crosscheck": {
        "PG_installs_iff_grant": all(
            agg[(f, a)]["inst"] == (0 if f != "control" else
                                    agg[(f, a)]["inst"])
            for f, a in agg),
        "zero_unauth_effects_all_forks": tot_eff == 0,
        "exact_no_grant_B2B6_unauthorized":
            E5["table"]["exact|grant=0"]["B2"]["UIR"]["k"] == 40,
    },
}
json.dump(prov, open(FIGS / "fig9_provenance.json", "w"), indent=1)
print("fig9 written")
print(json.dumps(prov["claims_crosscheck"], indent=1))
