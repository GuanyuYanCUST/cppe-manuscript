"""Figure 6 (S2), versions A+B — security-utility trade-off.
Written to this SEPARATE filename because scripts/make_fig6.py is being
edited concurrently by another session (2026-10-10 10:46); outputs are
fig6_tradeoff_A/B.* (also mine), theirs are fig6a/fig6b.*.

Contract: audit_20261010/figure_specs/fig6.yaml.
A  2x4 paired-dumbbell grid (rows UER/VPA, cols domains); B1-family
   drawn once (B2/B4/B6 asserted identical; B5 identical installs but
   UER 0 — caption), B3 lone gray tick, Wilson 95% CI on every dot,
   PG zeros as on-axis markers + pooled 0/N with CP upper.
   VPA row is PG-ONLY: baselines have no authorized precedent path ->
   "N/A" text, never a fabricated 0 dot.
B  compact integrated 4-panel: per-model UER dumbbells; install
   composition with v2 scope ground truth; VPA dual denominators;
   ATC channel split (data-driven from fig_data_v2 atc fields).
Render guard: pooled per-method numbers MUST equal Gate C
(metrics_recompute.json) + DERIVED_V2_DIFF scope totals, else refuse.
"""
import hashlib
import json
import math
import pathlib
import sys

sys.path.insert(0, "src")
from pguard.stats import wilson                       # noqa: E402

import matplotlib                                     # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib.lines import Line2D                   # noqa: E402
import numpy as np                                    # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIGS = ROOT / "results" / "FIGS"
FD = json.load(open(ROOT / "results/TABLES/fig_data_v2.json"))
REC = json.load(open(ROOT / "audit_20261010/gates/"
                     "metrics_recompute.json"))["per_method_legit_k10"]

MODELS = FD["models"]
DOMS = FD["domains"]
SHORT = ["GLM-5.3", "Claude-5.5", "Gem-3.8f", "DS-4.1f", "GPT-5.6"]
C_PG, C_FAM, C_B3 = "#0F6E6E", "#B3492C", "#8C8C8C"

plt.rcParams.update({
    "font.size": 7.5, "axes.titlesize": 8, "axes.labelsize": 7.5,
    "xtick.labelsize": 6, "ytick.labelsize": 6, "legend.fontsize": 6.5,
    "figure.dpi": 200, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False})


def cell(m, dm, me):
    return FD["cell"].get(f"{m}|{dm}|{me}|k=10")


def pooled(me):
    keys = ("n", "uer", "vpa", "prop", "inst", "scope", "atc", "atc_case")
    t = dict.fromkeys(keys, 0)
    for m in MODELS:
        for dm in DOMS:
            c = cell(m, dm, me)
            if c:
                for k in keys:
                    t[k] += c.get(k, 0)
    return t


# ---- render guard ----------------------------------------------------------
METHODS = ("B0", "B1", "B2", "B3", "B4", "B5", "B6", "PG")
for me in METHODS:
    t, r = pooled(me), REC[me]
    assert (t["n"], t["prop"], t["inst"], t["uer"]) == \
        (r["n"], r["proposed"], r["installed"], r["unauth_effect"]), me
EXP_SCOPE = {"B1": 598, "B2": 598, "B4": 598, "B5": 598, "B6": 598,
             "B0": 0, "B3": 0, "PG": 0}
for me in METHODS:
    assert pooled(me)["scope"] == EXP_SCOPE[me], me
pg = pooled("PG")
assert (pg["vpa"], pg["atc"], pg["atc_case"]) == (720, 4000, 3698)
for m in MODELS:                       # family identity where claimed
    for dm in DOMS:
        ref = cell(m, dm, "B1")
        assert all(cell(m, dm, o)["uer"] == ref["uer"]
                   and cell(m, dm, o)["inst"] == ref["inst"]
                   for o in ("B2", "B4", "B6")), (m, dm)
print("[guard] Gate C + v2 scope totals reconciled; drawing")

CP = lambda k, n: 100 * (1 - 0.025 ** (1 / n))       # two-sided 95% upper


def dumbbell(ax, models, getrate, ymax, zero_note=None):
    """B1-family <-> PG dumbbell, Wilson CI per dot, B3 lone tick.
    fam=None -> PG-only (N/A family, NO fabricated zero dot)."""
    for i, m in enumerate(models):
        fam, pg_, b3 = getrate(m)
        if fam is not None:
            lo, hi = wilson(*fam)
            ax.plot([i, i], [100 * fam[0], 100 * hi], color=C_FAM,
                    linewidth=0.8, alpha=0.45, zorder=3)
            ax.plot(i, 100 * fam[0], "o", ms=3.2, color=C_FAM, mec="#333",
                    mew=0.3, zorder=5, clip_on=False)
            ax.plot([i, i], [100 * fam[0], 100 * pg_[0]], color="#bbb",
                    linewidth=0.6, zorder=1)
        lo, hi = wilson(*pg_)
        ax.plot([i, i], [100 * lo, 100 * hi], color=C_PG, linewidth=0.8,
                alpha=0.5, zorder=4)
        ax.plot(i, 100 * pg_[0], "D", ms=3.0, color=C_PG, mec="#333",
                mew=0.3, zorder=6, clip_on=False)
        if b3 is not None:
            ax.plot([i + 0.22], [100 * b3[0]], marker="_", ms=4.5,
                    color=C_B3, mew=1.2, zorder=4, clip_on=False)
    ax.set_ylim(-0.02 * ymax, ymax)
    ax.set_xlim(-0.6, len(models) - 0.2)
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels(SHORT, rotation=35, ha="right")
    ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
    ax.set_axisbelow(True)
    if zero_note:
        ax.text(0.98, 0.95, zero_note, transform=ax.transAxes,
                ha="right", va="top", fontsize=5.6, color="#333")


# ---- Version A: 2x4 paired dumbbells ---------------------------------------
fig = plt.figure(figsize=(7.24, 2.62))
gs = fig.add_gridspec(2, 4, hspace=0.68, wspace=0.44,
                      left=0.075, right=0.99, top=0.88, bottom=0.21)
for ci, dm in enumerate(DOMS):
    ax = fig.add_subplot(gs[0, ci])                       # UER row
    n_pool = sum(cell(m, dm, "PG")["n"] for m in MODELS)
    uer_pg = sum(cell(m, dm, "PG")["uer"] for m in MODELS)

    def get_uer(m, dm=dm):
        fam, p, b3 = cell(m, dm, "B1"), cell(m, dm, "PG"), cell(m, dm, "B3")
        return ((fam["uer"] / fam["n"], fam["n"]),
                (p["uer"] / p["n"], p["n"]),
                (b3["uer"] / b3["n"],))

    ymax = max(5.0, 5 * math.ceil(100 * max(
        cell(m, dm, "B1")["uer"] / cell(m, dm, "B1")["n"]
        for m in MODELS) / 5))
    dumbbell(ax, MODELS, get_uer, ymax,
             zero_note=f"PG 0/{n_pool} (CP<{CP(uer_pg, n_pool):.2f}%)")
    if ci == 0:
        ax.set_ylabel("UER (% trajectories)")
    ax.set_title(dm, fontsize=7.5, loc="left", style="italic")

    ax = fig.add_subplot(gs[1, ci])                       # VPA row (PG only)
    vmax = max(100 * cell(m, dm, "PG")["vpa"] / cell(m, dm, "PG")["prop"]
               for m in MODELS)
    ymax = max(10.0, 10 * math.ceil(vmax / 10))

    def get_vpa(m, dm=dm):
        p = cell(m, dm, "PG")
        return (None, (p["vpa"] / p["prop"], p["prop"]), None)

    dumbbell(ax, MODELS, get_vpa, ymax)
    if ci == 0:
        ax.set_ylabel("VPA (% proposed, PG)")
        ax.text(0.02, 0.05, "baselines: N/A\n(no authorized\nprecedent path)",
                transform=ax.transAxes, fontsize=5.4, color="#555",
                va="bottom")
fig.legend(handles=[
    Line2D([], [], marker="o", ls="", ms=3.6, color=C_FAM, mec="#333",
           label="naive reuse B1 (B2/B4/B6 identical; B5 installs same)"),
    Line2D([], [], marker="_", ls="", ms=5, mew=1.2, color=C_B3,
           label="B3 per-rule admin (UER 0)"),
    Line2D([], [], marker="D", ls="", ms=3.4, color=C_PG, mec="#333",
           label="PRECEDENTGUARD")],
    loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.005),
    fontsize=6.3)
for ext in ("pdf", "png"):
    fig.savefig(FIGS / f"fig6_tradeoff_A.{ext}", dpi=300)
plt.close(fig)

# ---- Version B: compact integrated 1x4 -------------------------------------
fig, axes = plt.subplots(1, 4, figsize=(7.24, 2.15),
                         gridspec_kw={"wspace": 0.58, "left": 0.065,
                                      "right": 0.99, "top": 0.85,
                                      "bottom": 0.22})
ax = axes[0]                                              # (a) per-model UER

def get_uer_all(m):
    fam, p, b3 = pooled("B1"), pooled("PG"), pooled("B3")
    return ((fam["uer"] / fam["n"], fam["n"]),
            (p["uer"] / p["n"], p["n"]), (b3["uer"] / b3["n"],))

dumbbell(ax, MODELS, get_uer_all, 20.0,
         zero_note=f"PG 0/4000 (CP<{CP(0, 4000):.2f}%)")
ax.set_ylabel("UER (% trajectories)")
ax.set_title("(a) per-model UER", fontsize=7.5, loc="left")

ax = axes[1]                                              # (b) installs
me_b = [("naive reuse\n(B1; B2/B4/B5/B6\nidentical)", pooled("B1"), C_FAM,
         "////"),
        ("B3 root\nsignoff", pooled("B3"), C_B3, ""),
        ("PRECE-\nDENTGUARD", pooled("PG"), C_PG, "")]
nprop = pooled("B1")["prop"]
for i, (lab, t, color, hatch) in enumerate(me_b):
    lo, hi = wilson(t["inst"], nprop)
    ax.bar(i, t["inst"], 0.62, color=color, edgecolor="#333",
           linewidth=0.4, hatch=hatch, zorder=3)
    ax.errorbar(i, t["inst"], yerr=[[t["inst"] - lo * nprop],
                                    [hi * nprop - t["inst"]]],
                fmt="none", ecolor="#222", elinewidth=0.7, capsize=1.6,
                zorder=4)
    ax.text(i, t["inst"] + 70, f'{t["inst"]:,}', ha="center", fontsize=6)
ax.set_xticks(range(3))
ax.set_xticklabels([m[0] for m in me_b], fontsize=5.6)
ax.set_ylim(0, 3560)
ax.set_ylabel("installs (of 3,168 wf proposals)")
ax.set_title("(b) install composition", fontsize=7.5, loc="left")
fam = pooled("B1")
ax.text(0, 300, f"{fam['scope']} scope-escaping\n(v2 commit stamp)",
        ha="center", fontsize=5.4, color="#7a2d18")
ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
ax.set_axisbelow(True)

ax = axes[2]                                              # (c) VPA dual denoms
for i, (num, den) in enumerate(((pg["vpa"], pg["inst"]),
                                (pg["vpa"], pg["prop"]))):
    r = 100 * num / den
    lo, hi = wilson(num, den)
    ax.plot([i, i], [100 * lo, 100 * hi], color=C_PG, linewidth=0.9,
            alpha=0.5)
    ax.plot(i, r, "o", ms=3.6, color=C_PG, mec="#333", mew=0.3)
    ax.text(i + 0.07, r, f"{num}/{den:,}", fontsize=6, va="center")
ax.set_xticks([0, 1])
ax.set_xticklabels(["of installs", "of proposals"], fontsize=6.2)
ax.set_xlim(-0.5, 1.75)
ax.set_ylim(0, 42)
ax.set_ylabel("VPA (%)")
ax.set_title("(c) reuse utility (PG)", fontsize=7.5, loc="left")
ax.text(0.98, 0.05, "baselines: N/A", transform=ax.transAxes, ha="right",
        fontsize=5.6, color="#555")
ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
ax.set_axisbelow(True)

ax = axes[3]                                              # (d) ATC split
total, case = pg["atc"], pg["atc_case"]
prec = total - case
ax.bar(0, case, 0.5, color="#2f8f8f", edgecolor="#333", linewidth=0.4)
ax.bar(0, prec, 0.5, bottom=case, color="#0F6E6E", edgecolor="#333",
       linewidth=0.4)
ax.plot([0], [total], marker="_", ms=14, color="#222")
ax.text(0.33, total - 170, f"{total:,}/{total:,}", fontsize=6, va="center")
ax.text(0.33, case / 2, f"{case:,} case", fontsize=6, va="center")
ax.text(0.33, case + prec / 2 + 70, f"{prec} precedent", fontsize=6,
        va="center")
ax.set_xticks([])
ax.set_xlim(-0.55, 1.3)
ax.set_ylim(0, 4380)
ax.set_ylabel("tasks completed")
ax.set_title("(d) case availability (PG)", fontsize=7.5, loc="left")
ax.text(0.02, 0.05, "availability probe;\nnot task success", fontsize=5.4,
        color="#555", va="bottom")
for ext in ("pdf", "png"):
    fig.savefig(FIGS / f"fig6_tradeoff_B.{ext}", dpi=300)
plt.close(fig)


# ---- provenance ------------------------------------------------------------
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


prov = {
    "figures": ["fig6_tradeoff_A.pdf", "fig6_tradeoff_B.pdf"],
    "script": "scripts/make_fig6_tradeoff.py (separate from make_fig6.py: "
              "concurrent-edit collision 2026-10-10 10:46)",
    "inputs": {"fig_data": "results/TABLES/fig_data_v2.json",
               "gate_c": "audit_20261010/gates/metrics_recompute.json"},
    "sha256": {"fig_data": sha(ROOT / "results/TABLES/fig_data_v2.json"),
               "gate_c": sha(ROOT / "audit_20261010/gates/"
                             "metrics_recompute.json")},
    "render_guard": "per-method n/proposed/installed/unauth_effect equal "
                    "Gate C for all 8 methods; scope totals equal "
                    f"{EXP_SCOPE}; VPA=720, ATC=4000 (3,698 case)",
    "evidence_level": "deterministic frozen-trajectory replay (5 real "
                      "models), derived v2 (F-C2), k=10 legit, attacker "
                      "excluded",
}
json.dump(prov, open(FIGS / "fig6_provenance.json", "w"), indent=1)
print("[fig6] A + B written (fig6_tradeoff_A/B)")
