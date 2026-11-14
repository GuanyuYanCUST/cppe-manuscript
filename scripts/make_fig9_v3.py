"""Fig.9 redesigned (v3) — authority vs history fidelity.

Left  — E5 offline 2x2 factorial as a compact MATRIX (replaces the four
        repeated 0%/100% bar groups): rows = memory fidelity {lossy,
        exact}, cols = root cap {absent, present}; three family rows per
        cell (PG / B2-B6 / B1-B3, family identity asserted from the
        frozen summary). Every entry prints installs n/N + whether the
        installs carry root authority (filled marker = cap-backed,
        open = no credential). B2/B6 evidence gate and PG authority gate
        are the two live axes; grant factor binds PG only (by design —
        baselines have no authority check), stated on-figure.
        Downstream effects were NOT executed in E5 -> N/A (measured:
        installs + PEP admit VPA only).
Right — real-trajectory authorization fork (PG), recounted fresh from
        gates/authority_fork_results.jsonl: legit {valid, none, pooled
        invalid} vs attacker {valid, none}; labels placed above/below
        the zero line in disjoint positions (no overlap).

Render guard: E5 family identity + checks all true; fork recount must
equal the Gate-A audit totals (2,275 / 569 / 0 / 0; 0 unauth effects).
"""
import json
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                   # noqa: E402
from matplotlib.lines import Line2D               # noqa: E402

from fig_v3_common import (C_B1, C_B3, C_BLUE, C_PG, OUTDIR, RC_PARAMS,
                           ROOT, wilson_pct)

plt.rcParams.update(RC_PARAMS)

E5 = json.load(open(ROOT / "results/E5/E5-factorial-20261008-155213"
                    "/summary.json"))
assert all(E5["checks"].values()), "E5 frozen checks not all true"
FAM = [("PG", ("PG",), C_PG), ("B2/B6", ("B2", "B6"), C_BLUE),
       ("B1/B3", ("B1", "B3"), C_B3)]
CELLS = [("lossy", 0), ("lossy", 1), ("exact", 0), ("exact", 1)]
for f, g in CELLS:                       # family identity inside a cell
    t = E5["table"][f"{f}|grant={g}"]
    for a, b in (("B2", "B6"), ("B1", "B3")):
        assert t[a]["install_rate"]["k"] == t[b]["install_rate"]["k"]
        assert t[a]["UIR"]["k"] == t[b]["UIR"]["k"]

fig = plt.figure(figsize=(7.12, 2.75))
gs = fig.add_gridspec(1, 2, width_ratios=[1.62, 1.0], wspace=0.30,
                      left=0.055, right=0.99, top=0.80, bottom=0.30)
left = gs[0].subgridspec(2, 2, hspace=0.10, wspace=0.55)

for idx, (f, g) in enumerate(CELLS):
    ax = fig.add_subplot(left[idx // 2, idx % 2])
    t = E5["table"][f"{f}|grant={g}"]
    for yi, (lab, members, col) in enumerate(FAM):
        st = t[members[0]]["install_rate"]
        uir = t[members[0]]["UIR"]
        y = 2 - yi
        if st["na"]:
            ax.text(2, y, "N/A", fontsize=5.5, color="#444", va="center")
            continue
        r, elo, ehi = wilson_pct(st["k"], st["n"])
        ax.plot([r - elo, r + ehi], [y, y], color=col, lw=1.0, alpha=0.55)
        if st["k"] == 0:
            ax.plot([0], [y], marker="|", ms=5, color=col, mew=1.2)
            why = ("refused: no rulemaking authority"
                   if (lab == "PG" and g == 0)
                   else "rejected: evidence gate")
            ax.text(2, y, f'0/{st["n"]} {why}', fontsize=5.0, color="#444",
                    va="center")
        else:
            capbacked = (lab == "PG" and g == 1)
            if capbacked:
                ax.plot(r, y, "o", ms=3.8, color=col, mec="#333", mew=0.4)
            else:
                ax.plot(r, y, "o", ms=3.8, mfc="white", mec=col, mew=1.1)
            tag = "root cap" if capbacked else (
                "no credential" if uir["k"] else "authorized")
            ax.text(2, y, f'{st["k"]}/{st["n"]} · {tag}', fontsize=5.0,
                    color="#333", va="center")
    ax.set_yticks([2, 1, 0])
    ax.set_yticklabels([f[0] for f in FAM], fontsize=6)
    ax.set_xlim(-4, 100)
    ax.set_xticks((0, 50, 100))
    ax.set_ylim(-0.6, 2.6)
    ax.xaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
    ax.set_axisbelow(True)
    if idx // 2 == 0:
        ax.set_title({0: "no root cap", 1: "root cap"}[g] +
                     (" (offline factorial)" if idx == 0 else ""),
                     fontsize=7.5, loc="left")
    if idx % 2 == 0:
        ax.set_ylabel(f + " memory", fontsize=7)
fig.text(0.055, 0.315, "x = install rate (n=40 per cell·method; matched "
         "candidates: same signed history, root and contained rule in all\n"
         "four cells; root cap binds PG only). downstream effects NOT "
         "executed in E5 → N/A; measured: installs + PEP admit (VPA\n"
         "40/40 wherever installed). B2/B6 lossy+cap = false rejection "
         "cost of evidence-only gating.", fontsize=5.4, color="#444")

# ---- right: real-trajectory authorization fork ------------------------------
forks = [json.loads(l) for l in
         open(ROOT / "audit_20261010/gates/authority_fork_results.jsonl")]
agg = {}
for r in forks:
    a = agg.setdefault((r["fork"], bool(r["attacker"])),
                       Counter(n=0, prop=0, inst=0, eff=0))
    a["n"] += 1
    a["prop"] += bool(r.get("proposed"))
    a["inst"] += bool(r.get("installed"))
    a["eff"] += bool(r.get("unauth_effect"))
INVALID = ("cap_expired", "cap_wrong_issuer", "cap_type_confusion",
           "cap_stale_epoch")
inv = Counter()
for f in INVALID:
    inv += agg[(f, False)]
leg = [(agg[("control", False)], "valid"),
       (agg[("grant_absent", False)], "none"),
       (inv, "invalid*")]
atk = [(agg[("control", True)], "valid"),
       (agg[("grant_absent", True)], "none")]
assert (leg[0][0]["inst"], leg[0][0]["prop"]) == (2275, 3168)
assert atk[0][0]["inst"] == 569 and atk[0][0]["prop"] == 767
assert leg[1][0]["inst"] == 0 and leg[2][0]["inst"] == 0
assert all(a["eff"] == 0 for a in agg.values())

axb = fig.add_subplot(gs[1])
MARK = {"valid": ("o", C_PG, False), "none": ("o", "#8C8C8C", True),
        "invalid*": ("s", "#8C8C8C", True)}
for row, (bars, base) in enumerate(((leg, 0.0), (atk, 1.35))):
    for j, (c, lab) in enumerate(bars):
        x = base + j * 0.34
        mk, col, openf = MARK[lab]
        r, elo, ehi = wilson_pct(c["inst"], c["prop"])
        axb.errorbar(x, r, yerr=[[elo], [ehi]], fmt="none", ecolor="#222",
                     elinewidth=0.7, capsize=1.5)
        if openf:
            axb.plot(x, r, mk, ms=3.8, mfc="white", mec=col, mew=1.1)
        else:
            axb.plot(x, r, mk, ms=3.8, color=col, mec="#333", mew=0.4)
        above = (j % 2 == 0) or r > 5
        axb.text(x, (r + ehi + 4) if above else (-4.5),
                 f'{c["inst"]:,}/{c["prop"]:,}',
                 ha="center", fontsize=5.4,
                 va="bottom" if above else "top",
                 color="#222" if above else "#555")
        axb.text(x, -13, lab, ha="center", fontsize=5.4, color="#444")
axb.axhline(0, color="#333", linewidth=0.6)
axb.set_xticks((0.34, 1.52))
axb.set_xticklabels(["legit\n(5 models)", "attacker\narm"], fontsize=6.5)
axb.set_ylim(-16, 100)
axb.set_yticks((0, 25, 50, 75, 100))
axb.set_ylabel("PG installs / proposals (%)")
axb.set_title("real trajectories: grant fork", fontsize=7.5, loc="left")
axb.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
axb.set_axisbelow(True)
fig.text(0.99, 0.135, "* pooled: expired / wrong-issuer / type-confused /"
         " stale-epoch (n=3,200 rows, 729 proposals). grant_absent legit:"
         f' 0/{leg[1][0]["prop"]:,} installs. attacker installs = contained'
         " rules under the class grant;\nunauthorized effects 0 across all "
         f'{sum(a["n"] for a in agg.values()):,} rows (13,200).',
         ha="right", fontsize=5.4, color="#444")

for ext in ("pdf", "png"):
    fig.savefig(OUTDIR / f"fig9_factorial_v3.{ext}", dpi=300)
plt.close(fig)
print("fig9_factorial_v3 written")
