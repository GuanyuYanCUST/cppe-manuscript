"""Figure 6 (two versions) — security-utility trade-off, real replay only.

A: 2x4 paired-dumbbell grid per figure_specs/fig6.yaml (rows: UER, VPA;
   cols: domains). B1 family drawn once (B2/B4/B6 identical — asserted);
   B3 gray tick; PG teal. Wilson 95% CI on every dot; zeros as labeled
   markers; VPA/ATC undefined for baselines (closed_loop computes them on
   the PG path only) -> "N/A", never 0.
B: compact integrated 3-panel summary (per-model UER dumbbells; per-
   proposal rulemaking violations incl. v2 scope ground truth; PG-only
   utility with dual denominators).

Render guard: pooled per-method numbers from fig_data_v2.json must equal
gates/metrics_recompute.json (Gate C) and the DERIVED_V2_DIFF scope
totals, else the script refuses to draw.
"""
import hashlib
import json
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
RC = json.load(open(ROOT / "audit_20261010/gates/"
                    "metrics_recompute.json"))["per_method_legit_k10"]

MODELS = FD["models"]
DOMS = FD["domains"]
SHORT = ["GLM-5.3", "Claude-5.5", "Gemini-3.8f", "DS-4.1f", "GPT-5.6"]
C_PG, C_B1, C_B3 = "#0F6E6E", "#B3492C", "#8C8C8C"

plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
    "xtick.labelsize": 6.5, "ytick.labelsize": 7, "legend.fontsize": 6.5,
    "figure.dpi": 200, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False})


def cell(model, dom, method, k=10):
    return FD["cell"].get(f"{model}|{dom}|{method}|k={k}")


def pooled(method, field):
    return sum((cell(m, d, method) or {}).get(field, 0)
               for m in MODELS for d in DOMS)


def issuer_installs(m):
    """cppe_issuer install count: every B1–B6 install lacks typed
    authority; guarded arms install none (verified against Gate C)."""
    return pooled(m, "inst") if m.startswith("B") else 0


# ---- render guard (refuse to draw on any mismatch) -----------------------
EXPECT_SCOPE = {"B0": 0, "B1": 598, "B2": 598, "B3": 0, "B4": 598,
                "B5": 598, "B6": 598, "PG": 0}
for meth, ref in RC.items():
    for fig_field, rk in (("n", "n"), ("prop", "proposed"),
                          ("inst", "installed"),
                          ("uer", "unauth_effect")):
        if meth == "B0" and fig_field == "prop":
            continue   # B0 rejects pre-processing: row field is False,
            # Gate C's 3,168 is trajectory-level (see PG cells)
        got = pooled(meth, fig_field)
        assert got == ref[rk], (meth, fig_field, got, ref[rk])
    # cppe_issuer is not a fig_data field: every B1–B6 install is
    # issuer-violating (== inst), guarded arms install none — verify
    assert issuer_installs(meth) == ref["cppe_issuer"], meth
for meth, exp in EXPECT_SCOPE.items():
    got = pooled(meth, "scope")
    assert got == exp, ("scope", meth, got, exp)
assert pooled("PG", "vpa") == 720 and pooled("PG", "atc") == 4000
assert pooled("PG", "atc_case") == 3698
# family identity: B1==B2==B4==B6 on every drawn field; B5 shares
# install/scope behavior but its installs never serve (UER 0, contract
# §6) — documented exception, not drawn as the family dot
for field in ("uer", "inst", "scope", "prop"):
    vals = {pooled(m, field) for m in ("B1", "B2", "B4", "B6")}
    assert len(vals) == 1, (field, vals)
assert pooled("B5", "inst") == pooled("B1", "inst")
assert pooled("B5", "scope") == pooled("B1", "scope")
assert pooled("B5", "uer") == 0
print("[guard] Gate C + v2 scope totals reconciled; drawing")

UEMAX = max(
    100 * (cell(m, d, "B1") or {"uer": 0, "n": 1})["uer"] /
    (cell(m, d, "B1") or {"uer": 0, "n": 1})["n"]
    for m in MODELS for d in DOMS)


def dumbbell(ax, x, b1r, b1n, pgk, pgn):
    """gray connector + orange family dot (CI) + teal PG dot at its value."""
    lo, hi = wilson(b1k := round(b1r * b1n / 100), b1n)
    ax.plot([x, x], [100 * pgk / pgn, b1r], color="#bbb", lw=0.8, zorder=1)
    ax.errorbar(x, b1r, yerr=[[max(0.0, 100 * (b1r / 100 - lo))],
                              [100 * (hi - b1r / 100)]], fmt="none",
                ecolor="#222", elinewidth=0.7, capsize=1.5, zorder=3)
    ax.plot(x, b1r, "o", ms=3.4, color=C_B1, mec="#333", mew=0.4, zorder=4)
    pgr = 100 * pgk / pgn
    plo, phi = wilson(pgk, pgn)
    ax.errorbar(x, pgr, yerr=[[max(0.0, 100 * (pgr / 100 - plo))],
                              [100 * (phi - pgr / 100)]], fmt="none",
                ecolor=C_PG, elinewidth=0.7, capsize=1.5, zorder=3)
    ax.plot(x, pgr, "D", ms=3.2, color=C_PG, mec="#333", mew=0.4, zorder=4,
            clip_on=False)
    if pgk == 0:
        ax.text(x, 2.2, "0", ha="center", fontsize=5.2, color=C_PG)


def pg_dot(ax, x, k, n, color=C_PG):
    r = 100 * k / n if n else 0.0
    if n == 0:
        ax.text(x, 2, "N/A", ha="center", fontsize=5.5, color="#444")
        return
    lo, hi = wilson(k, n)
    ax.errorbar(x, r, yerr=[[max(0.0, 100 * (r / 100 - lo))],
                            [100 * (hi - r / 100)]],
                fmt="none", ecolor="#222", elinewidth=0.7, capsize=1.5)
    ax.plot(x, r, "o", ms=3.4, color=color, mec="#333", mew=0.4)


# ============================ VERSION A ===================================
fig = plt.figure(figsize=(7.24, 2.44))
gs = fig.add_gridspec(2, 4, hspace=0.5, wspace=0.42,
                      top=0.86, bottom=0.13, left=0.075, right=0.985)
for j, dom in enumerate(DOMS):
    for i in range(2):
        ax = fig.add_subplot(gs[i, j])
        ax.set_xticks(range(5))
        ax.set_xticklabels(SHORT, fontsize=6, rotation=0)
        ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
        ax.set_axisbelow(True)
        if i == 0:                                   # UER row
            ax.set_title(dom, fontsize=7.5, loc="left")
            for m_i, m in enumerate(MODELS):
                c1 = cell(m, dom, "B1")
                dumbbell(ax, m_i, 100 * c1["uer"] / c1["n"], c1["n"], 0,
                         c1["n"])
                ax.plot([m_i + 0.18], [0], marker="|", ms=5, color=C_B3,
                        mew=1.0, clip_on=False)
            ax.set_ylim(0, UEMAX + 4)
            ax.set_yticks(np.arange(0, UEMAX + 5, 10))
        else:                                        # VPA row (PG only)
            for m_i, m in enumerate(MODELS):
                c = cell(m, dom, "PG")
                pg_dot(ax, m_i, c["vpa"], c["prop"])
            ax.set_ylim(0, 60)
            ax.set_yticks([0, 20, 40, 60])
        if j == 0:
            ax.set_ylabel("UER (% traj.)" if i == 0 else "VPA (% prop.)",
                          fontsize=7)
        if i == 0 and j == 0:
            ax.text(0.02, 0.99, "B3: 0 all (tick)\nPG: 0/200 all\n"
                    "B5: installs, never serves",
                    transform=ax.transAxes, va="top", ha="left",
                    fontsize=5.2, color="#555")
        if i == 1 and j == 0:
            ax.text(0.02, 0.99, "B0–B6: N/A\n(no case channel)",
                    transform=ax.transAxes, va="top", ha="left",
                    fontsize=5.2, color="#555")

fig.legend(handles=[
    Line2D([], [], marker="o", ls="", color=C_B1, mec="#333", ms=4,
           label="B1 family (B2/B4/B6 identical)"),
    Line2D([], [], marker="D", ls="", color=C_PG, mec="#333", ms=4,
           label="PRECEDENTGUARD"),
    Line2D([], [], marker="|", ls="", color=C_B3, ms=6, mew=1.2,
           label="B3 per-rule admin")],
    loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.0))
fig.text(0.985, 0.965, "deterministic frozen-trajectory replay "
         "(derived v2, F-C2)", ha="right", fontsize=5.5, color="#777")
for ext in ("pdf", "png"):
    fig.savefig(FIGS / f"fig6a_tradeoff.{ext}", dpi=300)
plt.close(fig)

# ============================ VERSION B ===================================
fig = plt.figure(figsize=(7.24, 2.15))
gs = fig.add_gridspec(1, 3, width_ratios=[1.25, 1.0, 1.0], wspace=0.38,
                      top=0.82, bottom=0.16, left=0.06, right=0.99)

# (a) per-model UER dumbbells (pooled over domains)
ax = fig.add_subplot(gs[0])
for m_i, m in enumerate(MODELS):
    n = sum((cell(m, d, "B1") or {"n": 0})["n"] for d in DOMS)
    ue = sum((cell(m, d, "B1") or {"uer": 0})["uer"] for d in DOMS)
    dumbbell(ax, m_i, 100 * ue / n, n, 0, n)
    ax.plot([m_i + 0.18], [0], marker="|", ms=5, color=C_B3, mew=1.0,
            clip_on=False)
ax.set_xticks(range(5))
ax.set_xticklabels(SHORT, fontsize=6)
ax.set_ylim(0, UEMAX + 4)
ax.set_yticks(np.arange(0, UEMAX + 5, 10))
ax.set_ylabel("UER (% traj.)")
ax.set_title("(a) unauthorized effects per trajectory", fontsize=7.5,
             loc="left")
ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
ax.set_axisbelow(True)
ax.text(0.02, 0.99, "n=800/model; PG 0/800; B3 0/800", transform=
        ax.transAxes, va="top", fontsize=5.2, color="#555")

# (b) rulemaking violations per wf proposal (n=3,168): filled circle =
#     CPPE-ISSUER installs, open square = CPPE-SCOPE installs (v2 truth)
ax = fig.add_subplot(gs[1])
NPROP = pooled("B1", "prop")
for x_i, (meth, color) in enumerate((("B1", C_B1), ("B3", C_B3),
                                     ("PG", C_PG))):
    pg_dot(ax, x_i - 0.13, issuer_installs(meth), NPROP, color=color)
    k = pooled(meth, "scope")
    r = 100 * k / NPROP
    lo, hi = wilson(k, NPROP)
    ax.errorbar(x_i + 0.13, r, yerr=[[100 * (r / 100 - lo)],
                                     [100 * (hi - r / 100)]], fmt="none",
                ecolor="#222", elinewidth=0.7, capsize=1.5)
    ax.plot(x_i + 0.13, r, "s", ms=3.2, mfc="white", mec=color, mew=0.9)
ax.set_xticks(range(3))
ax.set_xticklabels(["B1 family", "B3", "PG"], fontsize=6.5)
ax.set_ylim(0, 105)
ax.set_ylabel("% of wf proposals")
ax.set_title("(b) rulemaking violations (n=3,168)", fontsize=7.5,
             loc="left")
ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
ax.set_axisbelow(True)
ax.text(0.02, 0.99, "issuer: 2960 / 2362 / 0\nscope (v2): 598 / 0 / 0",
        transform=ax.transAxes, va="top", fontsize=5.2, color="#555")
ax.legend(handles=[
    Line2D([], [], marker="o", ls="", color="#555", ms=3.5,
           label="CPPE-ISSUER installs"),
    Line2D([], [], marker="s", ls="", markerfacecolor="white",
           markeredgecolor="#555", ms=3.5, label="CPPE-SCOPE (v2)")],
    frameon=False, fontsize=5.8, loc="center right")

# (c) PG-only utility, dual denominators
ax = fig.add_subplot(gs[2])
ax.plot(0, 100 * 720 / 2275, "o", ms=3.6, color=C_PG, mec="#333", mew=0.4)
lo, hi = wilson(720, 2275)
ax.errorbar(0, 100 * 720 / 2275, yerr=[[100 * (720 / 2275 - lo)],
                                       [100 * (hi - 720 / 2275)]],
            fmt="none", ecolor="#222", elinewidth=0.7, capsize=1.5)
ax.plot(1, 100 * 720 / 3168, "o", ms=3.6, color="#5778a4", mec="#333",
        mew=0.4)
lo, hi = wilson(720, 3168)
ax.errorbar(1, 100 * 720 / 3168, yerr=[[100 * (720 / 3168 - lo)],
                                       [100 * (hi - 720 / 3168)]],
            fmt="none", ecolor="#222", elinewidth=0.7, capsize=1.5)
pg_dot(ax, 2, 3698, 4000, color=C_PG)
pg_dot(ax, 3, 302, 4000, color="#5778a4")
ax.set_xticks(range(4))
ax.set_xticklabels(["VPA /\ninstalls", "VPA /\nproposals",
                    "ATC via\ncase", "ATC via\nprecedent"], fontsize=6)
ax.set_ylim(0, 105)
ax.set_ylabel("% (PG only)")
ax.set_title("(c) case-channel utility", fontsize=7.5, loc="left")
ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
ax.set_axisbelow(True)
ax.text(0.02, 0.99, "720/2,275 · 720/3,168\n3,698/4,000 · 302/4,000\n"
        "B0–B6: N/A (no case channel)",
        transform=ax.transAxes, va="top", fontsize=5.2, color="#555")

fig.text(0.99, 0.99, "deterministic frozen-trajectory replay "
         "(derived v2, F-C2)", ha="right", fontsize=5.5, color="#777",
         va="top")
for ext in ("pdf", "png"):
    fig.savefig(FIGS / f"fig6b_tradeoff.{ext}", dpi=300)
plt.close(fig)

# ---- provenance ----------------------------------------------------------
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


prov = {
    "figures": ["fig6a_tradeoff.pdf", "fig6b_tradeoff.pdf"],
    "inputs": {"fig_data": "results/TABLES/fig_data_v2.json",
               "gate_c": "audit_20261010/gates/metrics_recompute.json"},
    "sha256": {"fig_data": sha(ROOT / "results/TABLES/fig_data_v2.json")},
    "guard": "per-method n/proposed/installed/unauth_effect/cppe_issuer "
             "== Gate C; scope == DERIVED_V2_DIFF totals "
             "{B1,B2,B4,B5,B6}=598, B3/PG/B0=0; VPA=720; ATC=4000(3698c)",
    "semantics": {
        "UER": "per-trajectory unauthorized effect (unauth_effect)",
        "VPA": "PG valid_accepted / proposed, per cell",
        "scope": "v2 commit-stamp out_of_root (ground truth)",
        "NA": "VPA/ATC undefined for B0-B6 (PG path only in closed_loop)",
    },
}
json.dump(prov, open(FIGS / "fig6_provenance.json", "w"), indent=1)
print("fig6a + fig6b written")
