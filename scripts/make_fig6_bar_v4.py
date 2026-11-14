"""Fig.6 v4 — four-panel bar-chart figure (IEEE double-column, 180mm).

Row 1 (a) B1 UER per model x domain, per-domain y ranges + PG zero markers.
Row 2 (b) PG proposal outcomes (100% stacked)  |  (c) install & reuse rates.
Row 3 (d) violations across enforcement layers (B1/B3/PG, n=4,000).

All numbers come from fig6_bar_data_v4.build_payload() (guarded, counted
from frozen replay_v2). Uniform-y variant: fig6_bar_v4_uniform_y.pdf.
Run: .venv/bin/python scripts/make_fig6_bar_v4.py
"""
import json
import pathlib
import shutil
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import fig6_bar_data_v4 as fd  # noqa: E402

OUT = ROOT / "results/FIGS/fig6_bar_v4"

C_B1, C_PG, C_B3 = "#B3492C", "#0F6E6E", "#8C8C8C"
C_OOR, C_CAP, C_MALF = "#D28A43", "#7C6B99", "#BFC7CC"
C_PG_LIGHT, C_INK, C_GRID = "#73ACA7", "#28333B", "#DCE1E4"
A_YLIM = {"cloudops": 10, "procurement": 60, "finance": 100, "dataaccess": 20}
A_YTICKS = {"cloudops": (0, 5, 10), "procurement": (0, 20, 40, 60),
            "finance": (0, 25, 50, 75, 100), "dataaccess": (0, 10, 20)}

mpl.rcParams.update({
    "font.family": "DejaVu Sans", "pdf.fonttype": 42, "svg.fonttype": "none",
    "text.color": C_INK, "axes.labelcolor": C_INK,
    "xtick.color": C_INK, "ytick.color": C_INK,
    "axes.edgecolor": C_INK, "axes.linewidth": 0.7,
    "grid.color": C_GRID, "grid.linewidth": 0.4,
    "xtick.major.width": 0.7, "ytick.major.width": 0.7,
    "xtick.major.size": 2.2, "ytick.major.size": 2.2,
})


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=8)


def zero_marker(ax, x, color):
    ax.plot([x], [0], marker="o", markersize=3.4, markerfacecolor="white",
            markeredgecolor=color, markeredgewidth=0.9, linestyle="none",
            zorder=5, clip_on=False)


def panel_a(fig, gs, P, uniform=False):
    models = fd.MODELS
    x = {m: i for i, m in enumerate(models)}
    sub = gs.subgridspec(1, 4, wspace=0.42)
    axs = []
    for j, (dkey, dname) in enumerate(fd.DOMAINS):
        ax = fig.add_subplot(sub[0, j])
        axs.append(ax)
        style(ax)
        ax.set_title(dname, fontsize=8.75, fontweight="bold", pad=3.0)
        top = 100.0 if uniform else A_YLIM[dkey]
        ax.set_ylim(0, top)
        ax.set_yticks(A_YTICKS[dkey] if not uniform else
                      [t for t in (0, 25, 50, 75, 100) if t <= top])
        ax.set_xlim(-0.55, len(models) - 0.45)
        ax.set_xticks(range(len(models)))
        ax.set_xticklabels(models)
        for m in models:
            cell = P["A"][m][dkey]
            k = cell["b1_unauth"]
            p = fd.pct(k, 200)
            lo, hi = fd.wil(k, 200)
            if k > 0:
                ax.bar([x[m] - 0.17], [p], width=0.30, color=C_B1,
                       linewidth=0.4, edgecolor=C_B1, zorder=3)
                ax.errorbar([x[m] - 0.17], [p],
                            yerr=[[p - lo], [hi - p]], color=C_INK,
                            linewidth=0.8, capsize=2.2, capthick=0.8,
                            zorder=4)
                lab_y = hi + 0.012 * top
                if lab_y + 0.055 * top > top:        # label would clip
                    ax.annotate(f"{k}", (x[m] - 0.17, hi), xytext=(6, -2),
                                textcoords="offset points", fontsize=7.5,
                                ha="left", va="top", color=C_INK)
                else:
                    ax.annotate(f"{k}", (x[m] - 0.17, hi), xytext=(0, 1.5),
                                textcoords="offset points", fontsize=7.5,
                                ha="center", va="bottom", color=C_INK)
            else:
                zero_marker(ax, x[m] - 0.17, C_B1)
                ax.annotate("0", (x[m] - 0.17, 0), xytext=(0, 3),
                            textcoords="offset points", fontsize=7.5,
                            ha="center", va="bottom", color=C_INK)
            zero_marker(ax, x[m] + 0.17, C_PG)
        if j == 0:
            ax.set_ylabel("B1 UER (%)", fontsize=8)
        ax.tick_params(axis="x", pad=1.5)
        axs.append(ax)
    return axs


def panel_b(ax, P):
    style(ax)
    models = fd.MODELS
    segs = [("installed", "Installed", C_PG, "white"),
            ("oor", "Out of root", C_OOR, "white"),
            ("cap_scope", "CAP_SCOPE", C_CAP, "white"),
            ("malformed", "Malformed", C_MALF, C_INK)]
    xs = range(len(models))
    for i, m in enumerate(models):
        B = P["B"][m]
        n = B["proposed"]
        bottom = 0.0
        for field, _lab, col, _tc in segs:
            frac = B[field] / n
            ax.bar([i], [100 * frac], bottom=[bottom], width=0.62,
                   color=col, linewidth=0.5, edgecolor="white", zorder=3)
            if 100 * frac >= 6.0:
                ax.annotate(f"{B[field]}", (i, bottom + 50 * frac),
                            fontsize=7.5, ha="center", va="center",
                            color="white" if col != C_MALF else C_INK,
                            zorder=4)
            bottom += 100 * frac
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_xticks(list(xs))
    ax.set_xticklabels(models)
    ax.set_ylabel("Share of proposals (%)", fontsize=8)
    ax.tick_params(axis="x", pad=1.5)
    return [Patch(facecolor=c, edgecolor="white", linewidth=0.5, label=l)
            for _f, l, c, _t in segs]


def panel_c(ax, P):
    style(ax)
    models = fd.MODELS
    for i, m in enumerate(models):
        C = P["C"][m]
        n = C["proposed"]
        for off, field, col in ((-0.19, "installed", C_PG_LIGHT),
                                (0.19, "vpa", C_PG)):
            k = C[field]
            p = fd.pct(k, n)
            lo, hi = fd.wil(k, n)
            if k > 0:
                ax.bar([i + off], [p], width=0.34, color=col, linewidth=0.4,
                       edgecolor=col, zorder=3)
                ax.errorbar([i + off], [p], yerr=[[p - lo], [hi - p]],
                            color=C_INK, linewidth=0.8, capsize=2.2,
                            capthick=0.8, zorder=4)
            else:
                zero_marker(ax, i + off, C_PG)
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_xlim(-0.55, len(models) - 0.45)
    ax.set_xticks(range(len(models)))
    ax.set_xticklabels(models)
    ax.set_ylabel("Rate (% of proposals)", fontsize=8)
    ax.tick_params(axis="x", pad=1.5)
    return [Patch(facecolor=C_PG_LIGHT, label="Installed / proposed"),
            Patch(facecolor=C_PG, label="Valid PEP hit / proposed")]


def panel_d(ax, P):
    style(ax)
    groups = [("issuer", "Issuer-unsafe\ninstallation"),
              ("scope", "Scope-escaping\ninstallation"),
              ("effect", "Unauthorized\nsandbox effect")]
    meths = [("B1", C_B1, "B1 (unguarded install)"),
             ("B3", C_B3, "B3 containment judge (no root credential)"),
             ("PG", C_PG, "PG (ours)")]
    offs = {"B1": -0.26, "B3": 0.0, "PG": 0.26}
    for gi, (field, _lab) in enumerate(groups):
        for meth, col, _ml in meths:
            k = P["D"][meth][field]
            x = gi + offs[meth]
            if k > 0:
                p = fd.pct(k, 4000)
                lo, hi = fd.wil(k, 4000)
                ax.bar([x], [p], width=0.23, color=col, linewidth=0.4,
                       edgecolor=col, zorder=3)
                ax.errorbar([x], [p], yerr=[[p - lo], [hi - p]],
                            color=C_INK, linewidth=0.8, capsize=2.2,
                            capthick=0.8, zorder=4)
                ax.annotate(f"{k}", (x, hi), xytext=(0, 1.5),
                            textcoords="offset points", fontsize=7.5,
                            ha="center", va="bottom", color=C_INK)
            else:
                zero_marker(ax, x, col)
    ax.set_ylim(0, 80)
    ax.set_yticks([0, 20, 40, 60, 80])
    ax.set_xlim(-0.55, 2.55)
    ax.set_xticks([g for g in range(3)])
    ax.set_xticklabels([lab for _f, lab in groups], fontsize=8)
    ax.set_ylabel("Violations per 4,000 histories (%)", fontsize=8)
    ax.tick_params(axis="x", pad=1.5)
    ax.annotate("denominator: 4,000 legitimate histories per method",
                (0.995, 0.03), xycoords="axes fraction", fontsize=7.5,
                ha="right", va="bottom", color="#5A646B")
    return [Patch(facecolor=c, label=l) for _m, c, l in meths]


def draw(P, uniform=False):
    fig = plt.figure(figsize=(7.087, 5.315))
    gs = GridSpec(3, 2, figure=fig, height_ratios=[1.0, 1.32, 1.06],
                  left=0.062, right=0.988, top=0.965, bottom=0.072,
                  hspace=0.58, wspace=0.30)
    axs_a = panel_a(fig, gs[0, :], P, uniform)

    ax_b = fig.add_subplot(gs[1, 0])
    ax_b.set_title("(b) PG proposal outcomes", loc="left", fontsize=9.25,
                   fontweight="bold", pad=21)
    h_b = panel_b(ax_b, P)
    ax_b.legend(handles=h_b, loc="lower left", bbox_to_anchor=(0.0, 1.005),
                ncol=4, frameon=False, fontsize=7.5, handlelength=1.15,
                handleheight=0.9, columnspacing=1.0, borderaxespad=0.0)

    ax_c = fig.add_subplot(gs[1, 1])
    ax_c.set_title("(c) Authorized installation and precedent reuse",
                   loc="left", fontsize=9.25, fontweight="bold", pad=21)
    h_c = panel_c(ax_c, P)
    ax_c.legend(handles=h_c, loc="lower left", bbox_to_anchor=(0.0, 1.005),
                ncol=2, frameon=False, fontsize=7.5, handlelength=1.15,
                columnspacing=1.0, borderaxespad=0.0)

    ax_d = fig.add_subplot(gs[2, :])
    ax_d.set_title("(d) Violations across enforcement layers", loc="left",
                   fontsize=9.25, fontweight="bold", pad=21)
    h_d = panel_d(ax_d, P)
    ax_d.legend(handles=h_d, loc="lower left", bbox_to_anchor=(0.0, 1.005),
                ncol=3, frameon=False, fontsize=7.5, handlelength=1.15,
                columnspacing=1.2, borderaxespad=0.0)

    # row (a): title + method legend band above the four domain subplots
    y_title = axs_a[0].get_position().y1 + 0.012
    fig.text(0.062, y_title,
             "(a) Unauthorized effects across models and domains",
             fontsize=9.25, fontweight="bold", va="bottom")
    h_a = [Patch(facecolor=C_B1, label="B1"),
           Line2D([], [], marker="o", markersize=3.4, markerfacecolor="white",
                  markeredgecolor=C_PG, markeredgewidth=0.9, linestyle="none",
                  label="PG (0 in all cells)")]
    fig.legend(handles=h_a, loc="upper right",
               bbox_to_anchor=(0.988, y_title + 0.024), ncol=2,
               frameon=False, fontsize=7.5, handlelength=1.15,
               columnspacing=1.0, borderaxespad=0.0)
    note = ("n = 200 legit histories per model × domain; "
            "y-axis range identical (0-100%) across domain panels "
            "(review variant)" if uniform else
            "n = 200 legit histories per model × domain; "
            "y-axis ranges differ across domain panels")
    fig.text(0.988, y_title + 0.024 - 0.030, note,
             fontsize=7.5, ha="right", va="top", color="#5A646B")
    return fig


def main():
    P = fd.build_payload()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, uniform in (("fig6_bar_v4", False),
                          ("fig6_bar_v4_uniform_y", True)):
        fig = draw(P, uniform)
        fig.savefig(OUT / f"{name}.pdf")
        fig.savefig(OUT / f"{name}.svg")
        if not uniform:
            fig.savefig(OUT / f"{name}.png", dpi=300)
        plt.close(fig)
    # provenance + source copies + checksums
    prov = {
        "inputs": P["inputs"],
        "cell_verify_v3_sha256": fd.sha256(
            ROOT / "audit_20261010/gates/cell_verify_v3.json"),
        "scripts": {p.name: fd.sha256(p) for p in [
            ROOT / "scripts/fig6_bar_data_v4.py",
            ROOT / "scripts/make_fig6_bar_v4.py",
            ROOT / "tests/test_fig6_bar_v4.py"]},
        "headline_counts": P["headlines"],
        "rows_loaded": P["n_rows"],
        "filter": "attacker==False, k_req==10, "
                  "method in {B1,B2,B3,B4,B6,PG}",
        "font": "DejaVu Sans (Arial/Helvetica unavailable in WSL; "
                "Type42-embedded equivalent)",
        "matplotlib": mpl.__version__,
        "figsize_mm": [180, 135],
        "colors": {"B1": C_B1, "PG": C_PG, "B3": C_B3, "PG_light": C_PG_LIGHT,
                   "out_of_root": C_OOR, "cap_scope": C_CAP,
                   "malformed": C_MALF},
    }
    (OUT / "fig6_bar_provenance.json").write_text(
        json.dumps(prov, indent=1), encoding="utf-8")
    src = OUT / "source"
    src.mkdir(exist_ok=True)
    for p in ("scripts/fig6_bar_data_v4.py", "scripts/make_fig6_bar_v4.py",
              "tests/test_fig6_bar_v4.py"):
        shutil.copy2(ROOT / p, src / pathlib.Path(p).name)
    print("rendered:", sorted(q.name for q in OUT.iterdir()))


if __name__ == "__main__":
    main()
