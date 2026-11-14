"""Fig.6-B revised (v3) — compact integrated security-utility panel.

Fixes vs the S2 candidates (S3_ISSUES_FOUND I1/I2/I3):
  (a) per-model UER drawn from the INDEPENDENT per-model recount
      (heterogeneity preserved; the S2 fig6_tradeoff_B variant repeated
      the pooled 14.6% at every model position — retired);
  (b) ONE trial unit everywhere: installs / violations per 4,000 legit
      trajectories (Wilson(k, 4000)) — no mixed "wf proposals" labels;
      the 208 malformed proposals install nothing on every arm (noted);
      B3 labeled "containment judge (no credential)" — never "root
      signoff" (it enforces containment only, authority_required=False);
  (c) every utility dot prints its own denominator (installs 2,275 /
      proposals 3,168 / trajectories 4,000); ATC marked as availability
      probe, NOT task success.

Render guard: all values == audit gates/cell_verify_v3.json (independent
recount), asserted per model and per metric before drawing.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                   # noqa: E402
from matplotlib.lines import Line2D               # noqa: E402

from fig_v3_common import (C_B1, C_B3, C_BLUE, C_PG, MODELS, OUTDIR,
                           RC_PARAMS, SHORT, assert_denoms, pm, pooled,
                           wilson_pct, cp95)

assert_denoms()
plt.rcParams.update(RC_PARAMS)

fig = plt.figure(figsize=(7.12, 2.2))
gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1.0, 1.25], wspace=0.42,
                      left=0.065, right=0.99, top=0.84, bottom=0.17)

# ---- (a) per-model UER (legit trajectories, k=10) --------------------------
ax = fig.add_subplot(gs[0])
for i, m in enumerate(MODELS):
    b1 = pm(m, "B1")
    r, elo, ehi = wilson_pct(b1["uer"], b1["n"])
    ax.plot([i, i], [r - elo, r + ehi], color=C_B1, lw=1.1, alpha=0.55)
    ax.plot(i, r, "o", ms=3.4, color=C_B1, mec="#333", mew=0.4, zorder=5)
    ax.plot([i + 0.22], [0], marker="_", ms=4.5, color=C_B3, mew=1.2,
            zorder=4, clip_on=False)
    ax.plot(i, 0, "D", ms=3.0, color=C_PG, mec="#333", mew=0.4,
            clip_on=False, zorder=6)
    ax.text(i, r + ehi + 1.2, f'{b1["uer"]}', ha="center", fontsize=5.4,
            color=C_B1)
ax.set_xticks(range(len(MODELS)))
ax.set_xticklabels([SHORT[m] for m in MODELS], fontsize=6)
ax.set_ylim(-1.2, 33)
ax.set_yticks((0, 10, 20, 30))
ax.set_ylabel("UER (% trajectories)")
ax.set_title("(a) unauthorized effects, per model", fontsize=7.5,
             loc="left")
ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
ax.set_axisbelow(True)
ax.axhline(0, color="#333", linewidth=0.6)
ax.text(0.02, 0.97, "PG: 0/800 each (pooled 0/4,000,\nCP≤"
        f"{cp95(4000):.3f}%) · B3: 0/800 each\nn=800 legit/model",
        transform=ax.transAxes, va="top", fontsize=5.4, color="#444")

# ---- (b) rulemaking without authority (per 4,000 legit trajectories) -------
ax = fig.add_subplot(gs[1])
N = 4000
rows = [("B1 family", pooled("B1"), C_B1),
        ("B3 containment\njudge (no\ncredential)", pooled("B3"), C_B3),
        ("PRECE-\nDENTGUARD", pooled("PG"), C_PG)]
for i, (lab, t, col) in enumerate(rows):
    r, elo, ehi = wilson_pct(t["issuer"], N)      # installs w/o credential
    ax.plot([i - 0.13], [r], "o", ms=3.6, color=col, mec="#333", mew=0.4)
    ax.errorbar(i - 0.13, r, yerr=[[elo], [ehi]], fmt="none", ecolor="#222",
                elinewidth=0.7, capsize=1.5)
    ax.text(i - 0.13, r + ehi + 2.5, f'{t["issuer"]:,}', ha="center",
            fontsize=5.8, color=col)
    r2, elo2, ehi2 = wilson_pct(t["scope"], N)    # scope-escaping subset
    ax.plot([i + 0.13], [r2], "s", ms=3.2, mfc="white", mec=col, mew=0.9)
    ax.errorbar(i + 0.13, r2, yerr=[[elo2], [ehi2]], fmt="none",
                ecolor="#666", elinewidth=0.7, capsize=1.5)
    if t["scope"]:
        ax.text(i + 0.13, r2 + ehi2 + 2.5, f'{t["scope"]:,}', ha="center",
                fontsize=5.8, color=col)
assert pooled("B1")["issuer"] == 2960 and pooled("B3")["issuer"] == 2362
assert pooled("PG")["issuer"] == 0 and pooled("B1")["scope"] == 598
ax.set_xticks(range(3))
ax.set_xticklabels([r[0] for r in rows], fontsize=5.8)
ax.set_ylim(-3, 92)
ax.set_yticks((0, 25, 50, 75))
ax.set_ylabel("% of 4,000 legit trajectories")
ax.set_title("(b) installs without root credential", fontsize=7.5,
             loc="left")
ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
ax.set_axisbelow(True)
ax.axhline(0, color="#333", linewidth=0.6)
ax.legend(handles=[
    Line2D([], [], marker="o", ls="", color="#555", ms=3.5,
           label="CPPE-ISSUER installs"),
    Line2D([], [], marker="s", ls="", markerfacecolor="white",
           markeredgecolor="#555", ms=3.5, label="CPPE-SCOPE subset")],
    frameon=False, fontsize=5.8, loc="upper right")
ax.text(0.02, 0.60, "B2/B4/B6 ≡ B1 (verified per cell)\n"
        "B5: same installs, never serves\n208 malformed → 0 installs,"
        "\nall arms · PG: 2,275 installs,\nall credential-backed",
        transform=ax.transAxes, va="top", fontsize=5.2, color="#444")

# ---- (c) PG utility — every dot carries its own denominator ----------------
ax = fig.add_subplot(gs[2])
pg = pooled("PG")
dots = [("VPA /\ninstalls", pg["vpa"], pg["inst"], C_PG),
        ("VPA /\nproposals", pg["vpa"], pg["prop"], C_PG),
        ("ATC via\ncase", pg["atc_case"], pg["atc"], C_BLUE),
        ("ATC via\nprecedent", pg["atc"] - pg["atc_case"], pg["atc"],
         C_BLUE)]
assert (pg["vpa"], pg["inst"], pg["prop"], pg["atc"], pg["atc_case"]) == \
    (720, 2275, 3168, 4000, 3698)
for i, (lab, k, n, col) in enumerate(dots):
    r, elo, ehi = wilson_pct(k, n)
    ax.errorbar(i, r, yerr=[[elo], [ehi]], fmt="none", ecolor="#222",
                elinewidth=0.7, capsize=1.5)
    ax.plot(i, r, "o", ms=3.5, color=col, mec="#333", mew=0.4)
    ax.text(i + 0.05, r, f"{k:,}/{n:,}", fontsize=6, va="center")
ax.set_xticks(range(4))
ax.set_xticklabels([d[0] for d in dots], fontsize=6)
ax.set_xlim(-0.5, 3.9)
ax.set_ylim(0, 105)
ax.set_yticks((0, 25, 50, 75, 100))
ax.set_ylabel("%")
ax.set_title("(c) case-channel utility (PG only)", fontsize=7.5, loc="left")
ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
ax.set_axisbelow(True)
ax.text(0.02, 0.97, "baselines: N/A (no case channel)\nATC = availability"
        " probe,\nNOT task success (Fig.6-C)", transform=ax.transAxes,
        va="top", fontsize=5.4, color="#444")

fig.text(0.99, 1.0, "deterministic frozen-trajectory replay · real 5-model"
         " rollouts · legit k=10 · attacker excluded",
         ha="right", va="top", fontsize=5.5, color="#777")
for ext in ("pdf", "png"):
    fig.savefig(OUTDIR / f"fig6b_tradeoff_v3.{ext}", dpi=300)
plt.close(fig)
print("fig6b_tradeoff_v3 written")
