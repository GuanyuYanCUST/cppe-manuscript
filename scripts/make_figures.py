"""Generate the real-data paper figures (PDF) into results/FIGS/.
Style per 图表设计大纲 §11: English text, white background, no dual
Y axes, no win/lose preset colors, shared legends, thin bar edges,
panel labels (a)..(h).  Fig 6/7/8/9 + A3 (EAV) + A4 (overhead).
"""
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
FD = json.load(open("results/TABLES/fig_data.json"))
MODELS, DOMS, CHANS = FD["models"], FD["domains"], FD["channels"]
CELL, UPR = FD["cell"], FD["upr"]

M7 = [("B0", "Static"), ("B1", "History"), ("B2", "RAG"),
      ("B3", "LLM-Judge"), ("B4", "Prov."), ("B5", "EventSrc"),
      ("PG", "PG")]
# muted, colorblind-safe-ish categorical palette; PG last, same width
C7 = ["#8c8c8c", "#5778a4", "#b8a1c7", "#d95f02", "#6a9f58",
      "#c9b458", "#2b6a6a"]
plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "figure.dpi": 200, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False})


def ci_err(k, d, v):
    """Wilson error arms, clipped >=0 (center can exceed k/d at tiny
    rates, which would give negative yerr)."""
    if not d:
        return 0.0, 0.0
    lo, hi = wilson(k, d)
    return max(v - 100 * lo, 0.0), max(100 * hi - v, 0.0)


def cells(dom, method, k=10):
    """All-model pooled counts for one (domain, method, k)."""
    n = uer = vpa = prop = inst = 0
    for m in MODELS:
        c = CELL.get(f"{m}|{dom}|{method}|k={k}")
        if c:
            n += c["n"]; uer += c["uer"]; vpa += c["vpa"]
            prop += c["prop"]; inst += c["inst"]
    return n, uer, vpa, prop, inst


# ---------------------------------------------------------------- Fig 6
fig, axes = plt.subplots(2, 4, figsize=(10.5, 4.6), sharey="row")
x = np.arange(len(M7))
for j, dom in enumerate(DOMS):
    for i, (metric, row) in enumerate((("UER", 0), ("VPA", 1))):
        ax = axes[row][j]
        vals, los, his = [], [], []
        for me, _ in M7:
            n, uer, vpa, prop, _ = cells(dom, me)
            k = uer if metric == "UER" else vpa
            d = n if metric == "UER" else prop
            v = 100 * k / d if d else 0.0
            lo, hi = ci_err(k, d, v)
            vals.append(v); los.append(lo)
            his.append(hi)
        ax.bar(x, vals, 0.72, color=C7, edgecolor="#333",
               linewidth=0.4, yerr=[los, his], capsize=1.2,
               error_kw={"elinewidth": 0.6})
        if row == 0:
            ax.set_title(dom, fontsize=9)
        ax.set_xticks(x)
        ax.set_xticklabels([lbl for _, lbl in M7], rotation=45,
                           ha="right")
        ax.set_ylim(0, 100)
        ax.yaxis.grid(True, linestyle="--", linewidth=0.4,
                      alpha=0.5)
        ax.set_axisbelow(True)
        if j == 0:
            ax.set_ylabel("Unsafe Admission / UER (%)" if row == 0
                          else "Valid Precedent Acceptance (%)")
        ax.text(-0.14, 1.06, f"({'abcd'[j] if row == 0 else 'efgh'[j]})",
                transform=ax.transAxes, fontsize=9)
fig.tight_layout()
fig.savefig(FIGS / "fig6_tradeoff.pdf")
plt.close(fig)

# ---------------------------------------------------------------- Fig 7
fig, axes = plt.subplots(2, 4, figsize=(10.5, 4.4), sharex=True)
KS = (0, 1, 3, 5, 10)
LINE = [("B1", "#5778a4", "History reuse"),
        ("B4", "#d95f02", "Perfect provenance"),
        ("B5", "#c9b458", "Event sourcing"),
        ("PG", "#2b6a6a", "PRECEDENTGUARD")]
for j, dom in enumerate(DOMS):
    # top: UPR vs k (trajectory-level, method-independent; PG cells
    # carry the out-of-envelope proposal counts per k)
    ax = axes[0][j]
    ys, los, his = [], [], []
    for k in KS:
        n = oop = 0
        for m in MODELS:
            c = CELL.get(f"{m}|{dom}|PG|k={k}")
            if c:
                n += c["n"]; oop += c["oop"]
        v = 100 * oop / n if n else 0.0
        lo, hi = ci_err(oop, n, v)
        ys.append(v); los.append(lo); his.append(hi)
    ax.errorbar(range(len(KS)), ys, yerr=[los, his], color="#8c5b3f",
                marker="o", markersize=2.5, linewidth=1.0, capsize=1.2,
                elinewidth=0.6)
    ax.set_title(dom, fontsize=9)
    ax.set_xticks(range(len(KS)))
    ax.set_xticklabels([str(k) for k in KS])
    ax.set_ylim(-3, 100)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
    ax.set_axisbelow(True)
    if j == 0:
        ax.set_ylabel("Unsafe Proposal Rate (%)")
    ax.text(-0.14, 1.06, f"({'abcd'[j]})", transform=ax.transAxes,
            fontsize=9)
    # bottom: UER vs k per method
    ax2 = axes[1][j]
    for me, col, lbl in LINE:
        ys, los, his = [], [], []
        for k in KS:
            n, uer, _, _, _ = cells(dom, me, k)
            v = 100 * uer / n if n else 0.0
            lo, hi = ci_err(uer, n, v)
            ys.append(v); los.append(lo)
            his.append(100 * hi - v)
        ax2.errorbar(range(len(KS)), ys, yerr=[los, his], color=col,
                     marker="o", markersize=2.5, linewidth=1.0,
                     capsize=1.2, elinewidth=0.6, label=lbl)
    ax2.set_xticks(range(len(KS)))
    ax2.set_xticklabels([str(k) for k in KS])
    ax2.set_xlabel("retained successful CASEs (k)")
    ax2.set_ylim(-3, 100)
    ax2.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
    ax2.set_axisbelow(True)
    if j == 0:
        ax2.set_ylabel("Unauthorized Effect Rate (%)")
    ax2.text(-0.14, 1.06, f"({'efgh'[j]})", transform=ax.transAxes,
             fontsize=9)
axes[1][0].legend(loc="upper left", frameon=False)
fig.tight_layout()
fig.savefig(FIGS / "fig7_ratchet.pdf")
plt.close(fig)
print("fig6, fig7 written")

# ---------------------------------------------------------------- Fig 8
fig, axes = plt.subplots(1, 4, figsize=(10.5, 2.6))
for j, dom in enumerate(DOMS):
    M = np.zeros((len(MODELS), len(CHANS)))
    for i, m in enumerate(MODELS):
        for c, ch in enumerate(CHANS):
            u = UPR.get(f"{m}|{dom}|{ch}")
            M[i][c] = 100 * u["oop"] / u["n"] if u and u["n"] else 0.0
    ax = axes[j]
    im = ax.imshow(M, cmap="Blues", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(CHANS)))
    ax.set_xticklabels(["epis", "rag", "skill", "distill"], rotation=45,
                       ha="right")
    if j == 0:
        ax.set_yticks(range(len(MODELS)))
        ax.set_yticklabels([m.replace("-flash", "").replace("-5.5", "")
                            for m in MODELS])
    else:
        ax.set_yticks([])
    ax.set_title(dom, fontsize=9)
    for i in range(len(MODELS)):
        for c in range(len(CHANS)):
            ax.text(c, i, f"{M[i][c]:.1f}", ha="center", va="center",
                    fontsize=6,
                    color="white" if M[i][c] > 55 else "#222")
    ax.text(-0.1, 1.08, f"({'abcd'[j]})", transform=ax.transAxes,
            fontsize=9)
cb = fig.colorbar(im, ax=axes, shrink=0.85, pad=0.015)
cb.set_label("UPR (%)", fontsize=8)
fig.savefig(FIGS / "fig8_heatmap.pdf")
plt.close(fig)
print("fig8 written")

# ---------------------------------------------------------------- Fig 9
M5 = [("B1", "History"), ("B3", "LLM-Judge"), ("B4", "Perfect Prov."),
      ("B5", "Event Src."), ("PG", "PG")]
C5 = [C7[1], C7[3], C7[4], C7[5], C7[6]]
fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.0))
for p, (metric, ylab) in enumerate((("UER", "Unsafe Admission / UER (%)"),
                                     ("VPA", "Valid Precedent Acceptance"
                                      " (%)"))):
    ax = axes[p]
    w = 0.16
    for i, (me, _) in enumerate(M5):
        vals, los, his = [], [], []
        for dom in DOMS:
            n, uer, vpa, prop, _ = cells(dom, me)
            k = uer if metric == "UER" else vpa
            d = n if metric == "UER" else prop
            v = 100 * k / d if d else 0.0
            lo, hi = ci_err(k, d, v)
            vals.append(v); los.append(lo)
            his.append(100 * hi - v)
        ax.bar(np.arange(4) + (i - 2) * w, vals, w, color=C5[i],
               edgecolor="#333", linewidth=0.4, yerr=[los, his],
               capsize=1.0, error_kw={"elinewidth": 0.5},
               label=M5[i][1])
    ax.set_xticks(range(4))
    ax.set_xticklabels(DOMS, rotation=20, ha="right")
    ax.set_ylabel(ylab)
    ax.set_ylim(0, 100 if p else 45)
    ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
    ax.set_axisbelow(True)
    ax.text(-0.12, 1.06, f"({'ab'[p]})", transform=ax.transAxes,
            fontsize=9)
axes[0].legend(frameon=False, ncol=2)
fig.tight_layout()
fig.savefig(FIGS / "fig9_provenance.pdf")
plt.close(fig)
print("fig9 written")

# ---------------------------------------------------------------- A3 EAV
EAV = json.load(open("results/TABLES/eav.json"))["per_arm"]
METH = ("B1", "B2", "B3", "B4", "B5", "B6", "PG")
fig, ax = plt.subplots(figsize=(6.4, 2.6))
for i, me in enumerate(METH):
    fr = []
    for m in MODELS:
        s = EAV[m].get(f"{me}|legit")
        fr.append(s["frac_gt0"] if s else 0.0)
    ax.bar(i, 100 * np.mean(fr), 0.72,
           color=C7[1] if me != "PG" else C7[6], edgecolor="#333",
           linewidth=0.4)
    ax.text(i, 100 * np.mean(fr) + 1, f"{100*np.mean(fr):.0f}%",
            ha="center", fontsize=7)
ax.set_xticks(range(len(METH)))
ax.set_xticklabels(METH)
ax.set_ylabel("installs with EAV>0 (%)")
ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(FIGS / "figA3_eav.pdf")
plt.close(fig)

# ---------------------------------------------------------------- A4 bench
OB = json.load(open("results/TABLES/overload_bench.json"))["latency"]
fig, ax = plt.subplots(figsize=(4.6, 2.6))
for me, col in (("PG", C7[6]), ("B1", C7[1])):
    ns = sorted(int(k) for k in OB[me])          # json keys are str
    ax.plot(ns, [OB[me][str(n)]["p95_ms"] for n in ns], marker="o",
            markersize=2.5, color=col, label=me)
ax.set_xlabel("installed precedents")
ax.set_ylabel("pep_decide p95 latency (ms)")
ax.legend(frameon=False)
ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(FIGS / "figA4_overload.pdf")
plt.close(fig)
print("figA3, figA4 written — all figures done")
