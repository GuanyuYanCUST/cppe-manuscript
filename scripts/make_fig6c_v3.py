"""Fig.6-C (v3, NEW) — full heterogeneity + PG outcomes + real utility.

Three separated blocks (user S3 directive):
  (a) UER dot matrix, 5 models x 4 domains, ONE shared scale, per-cell
      Wilson CI + counts — cross-model heterogeneity preserved (GLM
      procurement 52% vs Claude 0%); PG/B3 zeros stated per-cell-verified;
  (b) PG rulemaking outcomes per model (authorization availability +
      correct rejections): every proposal resolved into installed-with-
      credential / OUT_OF_ROOT / CAP_SCOPE / malformed, % of that
      model's own proposal count (bar-end n= label — denominators
      differ per model and are printed, never silently mixed);
  (c) legitimate PRECEDENT acceptance (VPA, % of proposals) vs ACTUAL
      task success (% of 8,000 live tasks, method-independent) —
      different denominators, separate markers, both Wilson.

Render guard: matrix values == cell_verify_v3 per_model_domain recount;
composition == PG reject-reason census; VPA == per-model recount; task
success == master_table.json x8000 exact integers.
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                   # noqa: E402
from matplotlib.lines import Line2D               # noqa: E402
from matplotlib.patches import Patch              # noqa: E402

from fig_v3_common import (C_B1, C_B3, C_BLUE, C_PG, CV, DOMS, MODELS,
                           OUTDIR, RC_PARAMS, ROOT, SHORT, assert_denoms,
                           pm, wilson_pct, cp95)

assert_denoms()
MT = json.load(open(ROOT / "results/TABLES/master_table.json"))["utility"]
plt.rcParams.update(RC_PARAMS)

fig = plt.figure(figsize=(7.12, 2.8))
gs = fig.add_gridspec(1, 3, width_ratios=[1.35, 1.05, 1.15], wspace=0.40,
                      left=0.075, right=0.99, top=0.84, bottom=0.15)

# ---- (a) UER dot matrix (B1 family; unified scale) --------------------------
ax = fig.add_subplot(gs[0])
MD = CV["per_model_domain_b1_uer"]
DMARK = {"cloudops": "o", "procurement": "s", "finance": "^",
         "dataaccess": "v"}
for i, m in enumerate(MODELS):
    for j, dm in enumerate(DOMS):
        c = MD[f"{m}|{dm}"]
        assert c["n"] == 200
        r, elo, ehi = wilson_pct(c["uer"], c["n"])
        y = i + (1.5 - j) * 0.115
        ax.plot([r - elo, r + ehi], [y, y], color=C_B1, lw=0.9, alpha=0.45,
                solid_capstyle="butt", zorder=2)
        ax.plot(r, y, DMARK[dm], ms=2.9, color=C_B1, mec="#333", mew=0.3,
                zorder=4)
        ax.text(r, y + 0.135, f'{c["uer"]}', ha="center", fontsize=4.8,
                color="#555", zorder=5)
    ax.text(-2.5, i, SHORT[m], ha="right", va="center", fontsize=6)
ax.set_ylim(-0.6, 4.65)
ax.set_yticks([])
ax.set_xlim(-2, 58)
ax.set_xticks((0, 10, 20, 30, 40, 50))
ax.set_xlabel("UER (% of 200 trajectories per cell)")
ax.set_title("(a) unauthorized effects · B1 family", fontsize=7.5,
             loc="left")
ax.xaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
ax.set_axisbelow(True)
ax.axvline(0, color="#333", linewidth=0.6)
ax.text(0.30, 0.985, "PG: 0 in all 20 cells\n(0/4,000, CP≤"
        f"{cp95(4000):.3f}%)\nB3: 0 in all 20 cells\n(per-cell verified)",
        transform=ax.transAxes, fontsize=5.4, color="#444", va="top")
ax.legend(handles=[Line2D([], [], marker=v, ls="", color=C_B1, ms=3.4,
                          mec="#333", label=k)
                   for k, v in DMARK.items()],
          frameon=False, fontsize=5.4, loc="lower right",
          bbox_to_anchor=(1.0, 0.10), handletextpad=0.2, labelspacing=0.25)

# ---- (b) PG rulemaking outcomes per model -----------------------------------
ax = fig.add_subplot(gs[1])
RR = CV["pg_reject_reasons_per_model"]
SEGS = [("installed (root cap)", C_PG, "inst"),
        ("OUT_OF_ROOT", C_B1, "OUT_OF_ROOT"),
        ("CAP_SCOPE", C_B3, "CAP_SCOPE")]
for i, m in enumerate(MODELS):
    rr = RR[f"{m}|PG"]
    malf = sum(v for k, v in rr.items() if k.startswith("MALFORMED"))
    prop = pm(m, "PG")["prop"]
    counts = [pm(m, "PG")["inst"], rr.get("OUT_OF_ROOT", 0),
              rr.get("CAP_SCOPE", 0), malf]
    assert sum(counts) == prop, (m, counts, prop)
    left = 0.0
    for (lab, col, _k), k in zip(SEGS, counts[:3]):
        ax.barh(i, 100 * k / prop, left=left, height=0.62, color=col,
                edgecolor="white", linewidth=0.3)
        if k / prop > 0.10:
            ax.text(left + 50 * k / prop, i, f"{k}", ha="center",
                    va="center", fontsize=5.2,
                    color="white" if col == C_PG else "#fff")
        left += 100 * k / prop
    ax.barh(i, 100 * malf / prop, left=left, height=0.62, color="#e4e4e4",
            edgecolor="white", linewidth=0.3, hatch="//")
    if malf / prop > 0.10:
        ax.text(left + 50 * malf / prop, i, f"{malf}", ha="center",
                va="center", fontsize=5.2, color="#555")
    ax.text(101.5, i, f'n={prop}', ha="left", va="center", fontsize=5.4,
            color="#444")
ax.set_yticks(range(len(MODELS)))
ax.set_yticklabels([SHORT[m] for m in MODELS], fontsize=6)
ax.invert_yaxis()
ax.set_xlim(0, 118)
ax.set_xticks((0, 25, 50, 75, 100))
ax.set_xlabel("% of the model's proposals")
ax.set_title("(b) PG resolves every proposal", fontsize=7.5, loc="left")
ax.xaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
ax.set_axisbelow(True)
ax.legend(handles=[Patch(facecolor=C_PG, label="installed (2,275)"),
                   Patch(facecolor=C_B1,
                         label="OUT_OF_ROOT stop (584)"),
                   Patch(facecolor=C_B3, label="CAP_SCOPE (101)"),
                   Patch(facecolor="#e4e4e4", hatch="//",
                         label="malformed (208)")],
          frameon=False, fontsize=5.2, loc="lower left",
          bbox_to_anchor=(-0.02, -0.02))
ax.text(0.99, 0.02, "scope-escaping = 598\n= 584 OOR + 14 CAP-on-oop",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=5.0,
        color="#444")

# ---- (c) VPA vs live task success -------------------------------------------
ax = fig.add_subplot(gs[2])
NT = 8000
for i, m in enumerate(MODELS):
    p = CV["per_model_pg_vpa"][m]
    assert p["vpa"] == pm(m, "PG")["vpa"] and p["prop"] == pm(m, "PG")["prop"]
    r, elo, ehi = wilson_pct(p["vpa"], p["prop"])
    ax.errorbar(i - 0.16, r, yerr=[[elo], [ehi]], fmt="none", ecolor=C_PG,
                elinewidth=0.7, capsize=1.4)
    ax.plot(i - 0.16, r, "o", ms=3.3, color=C_PG, mec="#333", mew=0.4)
    ax.text(i - 0.16, r + ehi + 3.2, f'{p["vpa"]}/{p["prop"]}', ha="center",
            fontsize=4.9, color=C_PG)
    k = round(MT[m]["task_success"] * NT)
    assert abs(k / NT - MT[m]["task_success"]) < 1e-9, m
    r2, elo2, ehi2 = wilson_pct(k, NT)
    ax.errorbar(i + 0.16, r2, yerr=[[elo2], [ehi2]], fmt="none",
                ecolor=C_BLUE, elinewidth=0.7, capsize=1.4)
    ax.plot(i + 0.16, r2, "s", ms=3.1, color=C_BLUE, mec="#333", mew=0.4)
    ax.text(i + 0.16, r2 - ehi2 - 6.2, f"{100*k/NT:.0f}", ha="center",
            fontsize=4.9, color=C_BLUE)
ax.set_xticks(range(len(MODELS)))
ax.set_xticklabels([SHORT[m] for m in MODELS], fontsize=6)
ax.set_ylim(-8, 105)
ax.set_yticks((0, 25, 50, 75, 100))
ax.set_ylabel("%")
ax.set_title("(c) acceptance vs task success", fontsize=7.5, loc="left")
ax.yaxis.grid(True, linestyle="--", linewidth=0.4, alpha=0.5)
ax.set_axisbelow(True)
ax.axhline(0, color="#333", linewidth=0.6)
ax.legend(handles=[
    Line2D([], [], marker="o", ls="", color=C_PG, ms=3.5,
           label="VPA (PG, % proposals)"),
    Line2D([], [], marker="s", ls="", color=C_BLUE, ms=3.5,
           label="task success (% 8,000 live tasks)")],
    frameon=False, fontsize=5.6, loc="upper center")
ax.text(0.02, 0.02, "task success: live rollout,\nmethod-independent · VPA 0"
        " (Claude):\ninert string-typed rules", transform=ax.transAxes,
        fontsize=5.2, color="#444", va="bottom")

fig.text(0.99, 1.0, "deterministic frozen-trajectory replay · real 5-model"
         " rollouts · legit k=10 · attacker excluded",
         ha="right", va="top", fontsize=5.5, color="#777")
for ext in ("pdf", "png"):
    fig.savefig(OUTDIR / f"fig6c_tradeoff_v3.{ext}", dpi=300)
plt.close(fig)
print("fig6c_tradeoff_v3 written")
