import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from pathlib import Path

def wilson_ci(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * np.sqrt((p * (1 - p) / n) + (z**2 / (4 * n**2))) / denom
    lo = max(0.0, center - half)
    hi = min(1.0, center + half)
    return lo, hi

def short_model(name):
    return {
        "GPT": "GPT",
        "Claude": "Cla.",
        "GLM": "GLM",
        "Gemini": "Gem.",
        "DeepSeek": "DS",
    }[name]

def make_figure(csv_path, pdf_path, png_path, svg_path):
    df = pd.read_csv(csv_path)

    models = ["GPT", "Claude", "GLM", "Gemini", "DeepSeek"]
    domains = ["CloudOps", "Procurement", "Finance", "Data Access"]
    ylims_a = {"CloudOps": 10, "Procurement": 60, "Finance": 100, "Data Access": 20}
    stack_cols = ["Installed", "Out-of-root", "CAP_SCOPE", "Malformed"]

    sub_pg = df[df["method"] == "PG"].groupby("model", as_index=False).sum(numeric_only=True)
    sub_pg["install_rate"] = sub_pg["installed"] / sub_pg["proposed"] * 100.0
    sub_pg["valid_rate"] = sub_pg["valid_accepted"] / sub_pg["proposed"] * 100.0
    sub_pg = sub_pg.set_index("model").loc[models].reset_index()

    n_hist = 4000
    tot_b1 = df[df["method"] == "B1"][["cppe_issuer", "cppe_scope", "unauth_effect"]].sum()
    tot_b3 = df[df["method"] == "B3"][["cppe_issuer", "cppe_scope", "unauth_effect"]].sum()

    cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    c0 = cycle[0]
    c1 = cycle[1]
    c2 = cycle[2]
    c3 = cycle[3] if len(cycle) > 3 else cycle[0]
    stack_color_map = dict(zip(stack_cols, cycle[:4]))

    plt.rcParams.update({
        "font.size": 11,
        "axes.titlesize": 14,
        "axes.labelsize": 13,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
    })

    fig = plt.figure(figsize=(12.3, 11.35), constrained_layout=False)
    gs = fig.add_gridspec(3, 4, height_ratios=[1.0, 1.0, 1.16], hspace=0.63, wspace=0.32)

    # (a)
    axes_a = [fig.add_subplot(gs[0, i]) for i in range(4)]
    for i, domain in enumerate(domains):
        ax = axes_a[i]
        sub = df[(df["method"] == "B1") & (df["domain"] == domain)].set_index("model").loc[models]
        x = np.arange(len(models))
        rates = sub["unauth_effect"] / sub["N"] * 100.0

        lower, upper = [], []
        for _, r in sub.iterrows():
            lo, hi = wilson_ci(int(r["unauth_effect"]), int(r["N"]))
            p = r["unauth_effect"] / r["N"]
            lower.append((p - lo) * 100)
            upper.append((hi - p) * 100)

        ax.bar(x, rates.values, yerr=np.array([lower, upper]), capsize=4, width=0.62, zorder=3)

        for xi, y in zip(x, rates.values):
            if y > 0:
                offset = 0.55 if domain != "Finance" else 1.0
                label = f"{y:.0f}" if abs(y - round(y)) < 0.05 else f"{y:.1f}"
                ax.text(
                    xi, y + offset, label,
                    ha="center", va="bottom", fontsize=10.5,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=0.4)
                )

        ax.plot(
            x, np.zeros_like(x), linestyle="None", marker="o", markersize=7,
            markerfacecolor="white", markeredgecolor=c1, markeredgewidth=1.8,
            clip_on=False, zorder=4
        )

        ax.set_title(f"{domain} (0-{ylims_a[domain]}%)", fontsize=13.8, weight="bold", pad=8)
        ax.set_ylim(-0.4, ylims_a[domain])
        ax.set_xticks(x)
        ax.set_xticklabels([short_model(m) for m in models], fontsize=10.5)
        if i == 0:
            ax.set_ylabel("B1 effect (%)", fontsize=13)
        if domain in ["CloudOps", "Data Access"]:
            ax.set_yticks([0, ylims_a[domain] / 2, ylims_a[domain]])
        elif domain == "Procurement":
            ax.set_yticks([0, 30, 60])
        else:
            ax.set_yticks([0, 50, 100])
        ax.grid(axis="y", alpha=0.30, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    row_a_pos = axes_a[0].get_position()
    fig.text(row_a_pos.x0, row_a_pos.y1 + 0.045, "(a) Unauthorized sandbox-probe effects",
             fontsize=17.5, weight="bold", ha="left", va="bottom")
    fig.text(row_a_pos.x0, row_a_pos.y1 + 0.019,
             "Bars show B1 rates with nominal 95% Wilson intervals | n = 200 histories per model-domain cell | PG markers are 0/200",
             fontsize=10.4, ha="left", va="bottom")

    legend_a = [
        Patch(facecolor=c0, label="B1 effect"),
        Line2D([0], [0], marker="o", linestyle="None", markersize=8,
               markerfacecolor="white", markeredgecolor=c1, markeredgewidth=1.8,
               label="PG: 0/200 in each cell")
    ]
    fig.legend(handles=legend_a, loc="upper right", bbox_to_anchor=(0.98, 0.975),
               ncol=2, frameon=False, fontsize=10.4, handlelength=1.0, handletextpad=0.4)

    # (b)
    axes_b = [fig.add_subplot(gs[1, i]) for i in range(4)]
    for i, domain in enumerate(domains):
        ax = axes_b[i]
        sub = df[(df["method"] == "PG") & (df["domain"] == domain)].set_index("model").loc[models]
        x = np.arange(len(models))
        proposed = sub["proposed"].values.astype(float)

        bottom = np.zeros(len(models))
        for idx, col in enumerate(stack_cols):
            share = sub[col].values / proposed * 100.0
            ax.bar(x, share, bottom=bottom, width=0.62, zorder=3)
            for xi, s, b in zip(x, share, bottom):
                if s >= 8:
                    txt_color = "white" if idx == 0 else "black"
                    ax.text(
                        xi, b + s / 2, f"{int(round(s))}",
                        ha="center", va="center", fontsize=10.5, weight="bold", color=txt_color
                    )
            bottom += share

        ax.set_ylim(0, 112)
        ax.set_yticks([0, 50, 100])
        ax.set_title(domain, fontsize=13.8, weight="bold", pad=8)
        ax.set_xticks(x)
        ax.set_xticklabels([short_model(m) for m in models], fontsize=10.5)
        if i == 0:
            ax.set_ylabel("Proposals (%)", fontsize=13)
        ax.grid(axis="y", alpha=0.30, linewidth=0.8)
        ax.set_axisbelow(True)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        ax2 = ax.twinx()
        ymax = int(np.ceil(max(proposed) / 25.0) * 25)
        ymax = max(ymax, 100)
        ytop = ymax * 1.04
        ax2.plot(x, proposed, marker="o", linewidth=1.6, markersize=5.5, clip_on=False, zorder=4)
        ax2.set_ylim(0, ytop)
        ticks = [0, ymax * 0.25, ymax * 0.5, ymax * 0.75, ymax]
        ax2.set_yticks(ticks)
        ax2.set_yticklabels([f"{int(t)}" for t in ticks], fontsize=9.2)
        ax2.tick_params(axis="y", length=3)
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_alpha(0.25)
        if i == 3:
            ax2.set_ylabel("PG proposals", fontsize=10.5)

    row_b_pos = axes_b[0].get_position()
    fig.text(row_b_pos.x0, row_b_pos.y1 + 0.045, "(b) PG proposal dispositions by domain",
             fontsize=17.5, weight="bold", ha="left", va="bottom")
    fig.text(row_b_pos.x0, row_b_pos.y1 + 0.019,
             "100% stacked bars for disposition shares | overlaid line shows the number of PG proposals in each model-domain cell",
             fontsize=10.4, ha="left", va="bottom")

    legend_b = [
        Patch(facecolor=stack_color_map["Installed"], label="Installed"),
        Patch(facecolor=stack_color_map["Out-of-root"], label="Out-of-root"),
        Patch(facecolor=stack_color_map["CAP_SCOPE"], label="CAP_SCOPE"),
        Patch(facecolor=stack_color_map["Malformed"], label="Malformed"),
        Line2D([0], [0], marker="o", linewidth=1.6, markersize=5.5, label="Proposal count"),
    ]
    fig.legend(handles=legend_b, loc="upper center", bbox_to_anchor=(0.58, 0.648),
               ncol=5, frameon=False, fontsize=10.15, handlelength=1.0, handletextpad=0.35)

    # (c)
    ax_c = fig.add_subplot(gs[2, 0:2])
    x = np.arange(len(models))
    w = 0.34

    vals_install = sub_pg["install_rate"].values
    vals_valid = sub_pg["valid_rate"].values

    err_install = [[], []]
    err_valid = [[], []]
    for _, r in sub_pg.iterrows():
        lo, hi = wilson_ci(int(r["installed"]), int(r["proposed"]))
        p = r["installed"] / r["proposed"]
        err_install[0].append((p - lo) * 100)
        err_install[1].append((hi - p) * 100)

        lo2, hi2 = wilson_ci(int(r["valid_accepted"]), int(r["proposed"]))
        p2 = r["valid_accepted"] / r["proposed"]
        err_valid[0].append((p2 - lo2) * 100)
        err_valid[1].append((hi2 - p2) * 100)

    ax_c.bar(x - w/2, vals_install, width=w, yerr=np.array(err_install), capsize=4, label="Installed / proposed", zorder=3)
    ax_c.bar(x + w/2, vals_valid, width=w, yerr=np.array(err_valid), capsize=4, label="Canonical hit / proposed", zorder=3)

    for xi, yi in zip(x - w/2, vals_install):
        ax_c.text(
            xi, yi + 1.8, f"{int(round(yi))}",
            ha="center", va="bottom", fontsize=10.7,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=0.3)
        )
    for xi, yi in zip(x + w/2, vals_valid):
        ax_c.text(
            xi, yi + 1.8, f"{int(round(yi))}",
            ha="center", va="bottom", fontsize=10.7,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=0.3)
        )

    ax_c.set_xticks(x)
    ax_c.set_xticklabels([m if m != "DeepSeek" else "DS" for m in models], fontsize=11.8)
    ax_c.set_ylim(0, 110)
    ax_c.set_yticks([0, 25, 50, 75, 100])
    ax_c.set_ylabel("Proposals (%)", fontsize=13)
    ax_c.grid(axis="y", alpha=0.30, linewidth=0.8)
    ax_c.set_axisbelow(True)
    ax_c.spines["top"].set_visible(False)
    ax_c.spines["right"].set_visible(False)
    ax_c.set_title("(c) Conditional PG installation / reuse", fontsize=16.5, weight="bold", loc="left", pad=12)
    ax_c.legend(loc="upper left", bbox_to_anchor=(0.0, 1.10), ncol=2, frameon=False,
                fontsize=10.25, handlelength=1.0, handletextpad=0.4)

    # (d)
    ax_d = fig.add_subplot(gs[2, 2:4])
    cats = ["Issuer-unsafe\ninstallation", "Scope escape\ninstallation", "Unauthorized\nsandbox effect"]
    x = np.arange(len(cats))
    w = 0.24

    series = [
        ("B1", [tot_b1["cppe_issuer"], tot_b1["cppe_scope"], tot_b1["unauth_effect"]]),
        ("B3 (no grant)", [tot_b3["cppe_issuer"], tot_b3["cppe_scope"], tot_b3["unauth_effect"]]),
    ]

    for j, (name, counts) in enumerate(series):
        rates = np.array(counts) / n_hist * 100.0
        lower, upper = [], []
        for k in counts:
            lo, hi = wilson_ci(int(k), n_hist)
            p = k / n_hist
            lower.append((p - lo) * 100)
            upper.append((hi - p) * 100)
        xpos = x + (j - 0.5) * w
        ax_d.bar(xpos, rates, width=w, yerr=np.array([lower, upper]), capsize=4, label=name, zorder=3)
        for xi, yv, kv in zip(xpos, rates, counts):
            if kv > 0:
                ax_d.text(
                    xi, yv + 1.6, f"{int(kv)}",
                    ha="center", va="bottom", fontsize=10.7, weight="bold",
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.75, pad=0.3)
                )
            else:
                ax_d.plot([xi], [0], linestyle="None", marker="o", markersize=6,
                          markerfacecolor="white", markeredgecolor=c2, markeredgewidth=1.5,
                          clip_on=False, zorder=4)

    pg_x = x + 1.5 * w
    ax_d.plot(pg_x, np.zeros_like(pg_x), linestyle="None", marker="o", markersize=7,
              markerfacecolor="white", markeredgecolor=c1, markeredgewidth=1.8,
              label="PG = 0", clip_on=False, zorder=4)
    for xi in pg_x:
        ax_d.text(
            xi, 1.2, "0",
            ha="center", va="bottom", fontsize=10.2,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.65, pad=0.2)
        )

    ax_d.set_xticks(x)
    ax_d.set_xticklabels(cats, fontsize=11.6)
    ax_d.set_ylim(-0.6, 85)
    ax_d.set_yticks([0, 20, 40, 60, 80])
    ax_d.set_ylabel("Histories (%)", fontsize=13)
    ax_d.grid(axis="y", alpha=0.30, linewidth=0.8)
    ax_d.set_axisbelow(True)
    ax_d.spines["top"].set_visible(False)
    ax_d.spines["right"].set_visible(False)
    ax_d.set_title("(d) Failures across enforcement layers", fontsize=16.5, weight="bold", loc="left", pad=12)

    legend_d = [
        Line2D([0], [0], marker="o", linestyle="None", markersize=7,
               markerfacecolor="white", markeredgecolor=c1, markeredgewidth=1.8, label="PG = 0"),
        Patch(facecolor=c0, label="B1"),
        Patch(facecolor=c1, label="B3 (no grant)"),
    ]
    ax_d.legend(handles=legend_d, loc="upper left", bbox_to_anchor=(0.0, 1.10), ncol=3, frameon=False,
                fontsize=10.25, handlelength=1.0, handletextpad=0.4)

    fig.text(
        0.5, 0.018,
        "Frozen k=10 legitimate-arm replay | In (c), grants are simulated class-scoped grants | "
        "Unauthorized effects are measured by in-harness sandbox probes | Canonical hit = valid PEP hit / proposed",
        ha="center", va="bottom", fontsize=10.5
    )

    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=300, bbox_inches="tight")
    fig.savefig(svg_path, bbox_inches="tight")
    plt.close(fig)

if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    make_figure(
        csv_path=base / "Fig6_442_frozen_data.csv",
        pdf_path=base / "Fig6_442_layout_refined.pdf",
        png_path=base / "Fig6_442_layout_refined.png",
        svg_path=base / "Fig6_442_layout_refined.svg",
    )
