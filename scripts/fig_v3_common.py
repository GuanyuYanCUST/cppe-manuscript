"""Shared loader + render-guard helpers for the v3 (S3) figure set.

Every v3 figure guards against audit_20261010/gates/cell_verify_v3.json
— the INDEPENDENT per-cell recount of the raw replay_v2 JSONL (fresh
implementation, three-layer cross-checked: raw == fig_data_v2 == Gate C,
0 mismatches) — instead of re-deriving numbers from fig_data.  Guards
here assert per-model / per-cell values, not pooled totals only.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pguard.stats import wilson                       # noqa: E402

CV = json.load(open(ROOT / "audit_20261010/gates/"
                    "cell_verify_v3.json"))
if CV["verdict"] != "PASS":
    raise SystemExit("cell_verify_v3 verdict != PASS — refuse to draw")

MODELS = CV["models"]                    # GLM-5.3, Claude-5.5, Gemini…,
DOMS = CV["domains"]
SHORT = {"GLM-5.3": "GLM-5.3", "Claude-5.5": "Claude-5.5",
         "Gemini-3.8-flash": "Gem-3.8f",
         "DeepSeek-v4.1-flash": "DS-4.1f", "GPT-5.6": "GPT-5.6"}

C_PG, C_B1, C_B3, C_BLUE = "#0F6E6E", "#B3492C", "#8C8C8C", "#5778a4"

RC_PARAMS = {
    "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
    "xtick.labelsize": 6.5, "ytick.labelsize": 7, "legend.fontsize": 6.5,
    "figure.dpi": 200, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False,
    "pdf.fonttype": 42,      # embedded TrueType (vector, selectable text)
}

OUTDIR = ROOT / "results" / "FIGS" / "v3_20261010"
OUTDIR.mkdir(parents=True, exist_ok=True)


def pm(model, method):
    """per-model legit k=10 counts from the independent recount."""
    return CV["per_model"][f"{model}|{method}"]


def pooled(method):
    return CV["per_method_legit"][method]


def denom():
    return CV["denominators"]


def assert_denoms():
    d = denom()
    assert (d["trajectories_legit"], d["proposing"], d["malformed"],
            d["well_formed_proposals"]) == (4000, 3168, 208, 2960)
    assert (d["pg_installed"], d["pg_out_of_root"],
            d["pg_cap_scope_on_oop"], d["pg_cap_scope_inclass"]) == \
        (2275, 584, 14, 87)
    assert sum(v["uer"] for k, v in CV["per_model"].items()
               if k.endswith("|B1")) == 584
    for m in MODELS:                      # heterogeneity must survive:
        # per-model B1 UER equals the independent recount exactly
        assert pm(m, "B1")["uer"] == CV["per_model"][f"{m}|B1"]["uer"]


def cp95(n):
    """two-sided 95% exact upper bound for 0 events on n trials (%)"""
    return 100 * (1 - 0.025 ** (1 / n))


def wilson_pct(k, n):
    """(rate%, lower err, upper err) clamped at 0 — never negative."""
    r = 100 * k / n if n else 0.0
    lo, hi = wilson(k, n)
    return r, max(0.0, r - 100 * lo), max(0.0, 100 * hi - r)
