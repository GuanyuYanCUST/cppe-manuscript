"""Fig.6 bar v4 — independent data extraction from frozen replay_v2.

Reads the five real arms' replay_v2/main.jsonl (read-only), filters
attacker==False, k_req==10, methods {B1,B2,B3,B4,B6,PG}, enforces row
identity (800 legit trajectories per model; 200 per model x domain;
unique (model,domain,channel,seed,method) keys; B1/B3/PG pairable per
sample), recomputes every percentage by counting, cross-checks against
audit_20261010/gates/cell_verify_v3.json, and writes
results/FIGS/fig6_bar_v4/fig6_bar_data_v4.csv.

No summary.md / old-figure numbers are consumed. Run:
  .venv/bin/python scripts/fig6_bar_data_v4.py
"""
import csv
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pguard.stats import wilson  # noqa: E402

ARMS = [("real_gpt56", "GPT"), ("real_claude55", "Claude"),
        ("real_glm53", "GLM"), ("real_gemini38flash", "Gemini"),
        ("real_deepseek41flash", "DS")]
MODELS = [m for _, m in ARMS]
DOMAINS = [("cloudops", "CloudOps"), ("procurement", "Procurement"),
           ("finance", "Finance"), ("dataaccess", "Data Access")]
DOMAIN_KEYS = [d for d, _ in DOMAINS]
LOAD_METHODS = ("B1", "B2", "B3", "B4", "B6", "PG")
PLOT_METHODS = ("B1", "B3", "PG")
K = 10

# spec-pinned expected values (guards; any mismatch fails loudly)
EXPECT = {
    "legit_traj": 4000, "proposed": 3168, "well_formed": 2960,
    "b1_installed": 2960, "b1_issuer": 2960, "b3_issuer": 2362,
    "b1_scope": 598, "b1_unauth": 584, "pg_installed": 2275,
    "pg_vpa": 720, "pg_unauth": 0,
    "pg_proposed_per_model": {"GPT": 650, "Claude": 303, "GLM": 729,
                              "Gemini": 729, "DS": 757},
}
KNOWN_REJECTS = ("OUT_OF_ROOT", "CAP_SCOPE")


class Fig6DataError(Exception):
    pass


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def check_reason(r):
    """Validate one replay row's proposal/installed/reject consistency."""
    prop, inst, rr = r.get("proposed"), r.get("installed"), r.get("reject_reason")
    if prop not in (True, False) or inst not in (True, False):
        raise Fig6DataError(f"missing/None boolean field in {r['_key']}: "
                            f"proposed={prop!r} installed={inst!r}")
    if not prop:
        if inst or rr is not None:
            raise Fig6DataError(f"non-proposed row has outcome: {r['_key']}")
        return None
    if inst and rr is not None:
        raise Fig6DataError(f"installed row also has reject_reason: {r['_key']}")
    if not inst and rr is None:
        raise Fig6DataError(f"proposed+rejected row missing reason: {r['_key']}")
    if rr is not None and not (rr in KNOWN_REJECTS
                               or rr.startswith("MALFORMED_RULE")):
        raise Fig6DataError(f"unknown reject_reason {rr!r} in {r['_key']}")
    return rr


def load_rows():
    rows = []
    inputs = {}
    for d, name in ARMS:
        f = ROOT / "results" / d / "replay_v2" / "main.jsonl"
        inputs[name] = {"path": str(f.relative_to(ROOT)), "sha256": sha256(f)}
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                if r.get("attacker") or r.get("k_req") != K \
                        or r.get("method") not in LOAD_METHODS:
                    continue
                for fld in ("domain", "channel", "seed", "method"):
                    if r.get(fld) is None:
                        raise Fig6DataError(f"null identity field {fld}")
                if r["domain"] not in DOMAIN_KEYS or r["seed"] not in range(50):
                    raise Fig6DataError(f"unknown domain/seed: "
                                        f"{r['domain']}/{r['seed']}")
                r["_model"] = name
                r["_key"] = (name, r["domain"], r["channel"], r["seed"],
                             r["method"])
                check_reason(r)
                rows.append(r)
    return rows, inputs


def check_identity(rows):
    seen = set()
    per = {}
    for r in rows:
        if r["_key"] in seen:
            raise Fig6DataError(f"duplicate key {r['_key']}")
        seen.add(r["_key"])
        per.setdefault((r["_model"], r["method"]), set()).add(
            (r["domain"], r["channel"], r["seed"]))
    for m in MODELS:
        for meth in LOAD_METHODS:
            s = per.get((m, meth))
            if not s:
                raise Fig6DataError(f"method {meth} missing for model {m}")
            if len(s) != 800:
                raise Fig6DataError(f"{m}/{meth}: {len(s)} samples, want 800")
            for d in DOMAIN_KEYS:
                nd = sum(1 for t in s if t[0] == d)
                if nd != 200:
                    raise Fig6DataError(f"{m}/{meth}/{d}: {nd} samples, want 200")
        base = per[(m, "B1")]
        for meth in ("B2", "B3", "B4", "B6", "PG"):
            if per[(m, meth)] != base:
                raise Fig6DataError(f"{m}/{meth} sample set != B1 (pairing)")
    return per


def check_family_identity(rows):
    """B1/B2/B4/B6 share the unguarded-install mechanism: verdict fields
    must agree per sample (one mechanism, four specs — never drawn as
    four independent baselines)."""
    by = {}
    for r in rows:
        if r["method"] in ("B1", "B2", "B4", "B6"):
            by.setdefault((r["_model"], r["domain"], r["channel"], r["seed"]),
                          {})[r["method"]] = (r["installed"],
                                              bool(r.get("cppe_issuer")),
                                              bool(r.get("cppe_scope")),
                                              bool(r.get("unauth_effect")))
    for k, d in by.items():
        if set(d) != {"B1", "B2", "B4", "B6"}:
            raise Fig6DataError(f"family incomplete at {k}")
        if len(set(d.values())) != 1:
            raise Fig6DataError(f"family verdict divergence at {k}: {d}")


def pct(k, n):
    if n == 0:
        raise Fig6DataError("zero denominator")
    return 100.0 * k / n


def wil(k, n):
    lo, hi = wilson(k, n)
    return 100 * lo, 100 * hi


def aggregate(rows):
    idx = {(r["_model"], r["domain"], r["channel"], r["seed"], r["method"]): r
           for r in rows}
    A = {m: {d: {"b1_unauth": 0, "pg_unauth": 0, "n": 200}
             for d in DOMAIN_KEYS} for m in MODELS}
    for (m, d, _c, _s, meth), r in idx.items():
        if meth == "B1" and r["installed"] and r["unauth_effect"]:
            A[m][d]["b1_unauth"] += 1
        if meth == "PG" and r["installed"] and r["unauth_effect"]:
            A[m][d]["pg_unauth"] += 1

    B = {m: {"proposed": 0, "installed": 0, "oor": 0, "cap_scope": 0,
             "malformed": 0} for m in MODELS}
    for r in rows:
        if r["method"] != "PG":
            continue
        m = r["_model"]
        if not r["proposed"]:
            continue
        B[m]["proposed"] += 1
        if r["installed"]:
            B[m]["installed"] += 1
        elif r["reject_reason"] == "OUT_OF_ROOT":
            B[m]["oor"] += 1
        elif r["reject_reason"] == "CAP_SCOPE":
            B[m]["cap_scope"] += 1
        else:
            B[m]["malformed"] += 1

    C = {m: {"proposed": 0, "installed": 0, "vpa": 0} for m in MODELS}
    D = {meth: {"issuer": 0, "scope": 0, "effect": 0, "n": 4000}
         for meth in PLOT_METHODS}
    for r in rows:
        m, meth = r["_model"], r["method"]
        if meth == "PG":
            if r["proposed"]:
                C[m]["proposed"] += 1
            if r["installed"]:
                C[m]["installed"] += 1
                if r["valid_accepted"]:
                    C[m]["vpa"] += 1
        if meth in PLOT_METHODS and r["installed"]:
            D[meth]["issuer"] += bool(r["cppe_issuer"])
            D[meth]["scope"] += bool(r["cppe_scope"])
            D[meth]["effect"] += bool(r["unauth_effect"])
    return A, B, C, D


def check_expectations(A, B, C, D, rows):
    n_rows = len({(r["_model"], r["domain"], r["channel"], r["seed"])
                  for r in rows})
    got = {
        "legit_traj": n_rows, "proposed": sum(B[m]["proposed"] for m in MODELS),
        "well_formed": D["B1"]["issuer"],
        "b1_installed": D["B1"]["issuer"], "b1_issuer": D["B1"]["issuer"],
        "b3_issuer": D["B3"]["issuer"], "b1_scope": D["B1"]["scope"],
        "b1_unauth": D["B1"]["effect"],
        "pg_installed": sum(B[m]["installed"] for m in MODELS),
        "pg_vpa": sum(C[m]["vpa"] for m in MODELS),
        "pg_unauth": D["PG"]["effect"],
    }
    # B1 installed == well-formed (every wf installs); PG installs field None
    # on reject rows, counted via B buckets — cross-check both paths:
    got["b1_installed"] = sum(1 for r in rows if r["method"] == "B1"
                              and r["installed"])
    for k, v in EXPECT.items():
        if k == "pg_proposed_per_model":
            for m, want in v.items():
                if B[m]["proposed"] != want:
                    raise Fig6DataError(f"PG proposed {m}: {B[m]['proposed']}"
                                        f" != {want}")
        elif got[k] != v:
            raise Fig6DataError(f"{k}: computed {got[k]} != expected {v}")
    for m in MODELS:
        s = B[m]
        if s["installed"] + s["oor"] + s["cap_scope"] + s["malformed"] \
                != s["proposed"]:
            raise Fig6DataError(f"panel (b) buckets not exhaustive for {m}")
        if not C[m]["vpa"] <= C[m]["installed"] <= C[m]["proposed"]:
            raise Fig6DataError(f"panel (c) monotonicity broken for {m}")
        if C[m]["proposed"] != s["proposed"] \
                or C[m]["installed"] != s["installed"]:
            raise Fig6DataError(f"panel (b)/(c) denominators disagree {m}")
    for m in MODELS:                      # PG zero in every model x domain
        for d in DOMAIN_KEYS:
            if A[m][d]["pg_unauth"] != 0:
                raise Fig6DataError(f"PG unauth nonzero at {m}/{d}")
    b3p = pct(D["B3"]["issuer"], 4000)
    if abs(b3p - 59.05) > 0.005:
        raise Fig6DataError(f"B3 issuer pct {b3p:.4f} != 59.05")
    return got


def cross_check_cell_verify(A, B, C):
    cv = json.load(open(ROOT / "audit_20261010/gates/cell_verify_v3.json"))
    d = cv["denominators"]
    for cvk, mine in (("trajectories_legit", 4000), ("proposing", 3168),
                      ("well_formed_proposals", 2960), ("pg_installed", 2275),
                      ("pg_out_of_root", 584)):
        if d[cvk] != mine:
            raise Fig6DataError(f"cell_verify_v3 {cvk}={d[cvk]} != {mine}")
    cv_models = cv["models"]
    ALIAS = {"GPT": "GPT-5.6", "Claude": "Claude-5.5", "GLM": "GLM-5.3",
             "Gemini": "Gemini-3.8-flash", "DS": "DeepSeek-v4.1-flash"}
    if set(cv_models) != set(ALIAS.values()):
        raise Fig6DataError(f"cv3 models list unexpected: {cv_models}")
    full = ALIAS
    for k, v in cv["per_model_domain_b1_uer"].items():
        fm, dm = k.split("|")
        m = {f: s for s, f in full.items()}[fm]
        if v["uer"] != A[m][dm]["b1_unauth"] or v["n"] != 200:
            raise Fig6DataError(f"cv3 per-model-domain mismatch {k}")
    for k, v in cv["per_model"].items():
        fm, meth = k.split("|")
        m = {f: s for s, f in full.items()}[fm]
        if meth == "PG" and (v["prop"] != C[m]["proposed"]
                             or v["inst"] != C[m]["installed"]
                             or v["vpa"] != C[m]["vpa"]):
            raise Fig6DataError(f"cv3 per-model PG mismatch {k}")
    return cv


def build_payload():
    rows, inputs = load_rows()
    check_identity(rows)
    check_family_identity(rows)
    A, B, C, D = aggregate(rows)
    got = check_expectations(A, B, C, D, rows)
    cross_check_cell_verify(A, B, C)
    return {"A": A, "B": B, "C": C, "D": D, "headlines": got,
            "inputs": inputs, "n_rows": len(rows)}


def write_csv(p, P):
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["panel", "model", "domain", "series", "method",
                    "numerator", "denominator", "pct", "wilson_lo",
                    "wilson_hi", "note"])
        for m in MODELS:
            for d in DOMAIN_KEYS:
                for meth, field, label in (("B1", "b1_unauth", "UER"),
                                           ("PG", "pg_unauth", "UER")):
                    k = P["A"][m][d][field]
                    lo, hi = wil(k, 200)
                    w.writerow(["a", m, d, label, meth, k, 200, pct(k, 200),
                                round(lo, 3), round(hi, 3),
                                "PG zero in all 20 cells" if meth == "PG" else ""])
        for m in MODELS:
            N = P["B"][m]["proposed"]
            for field, label in (("installed", "Installed"),
                                 ("oor", "Rejected: out of root"),
                                 ("cap_scope", "Rejected: CAP_SCOPE"),
                                 ("malformed", "Malformed")):
                k = P["B"][m][field]
                w.writerow(["b", m, "", label, "PG", k, N, pct(k, N),
                            "", "",
                            "mutually exclusive; sums to proposed"])
        for m in MODELS:
            N = P["C"][m]["proposed"]
            for field, label in (("installed", "Installed / proposed"),
                                 ("vpa", "Valid PEP hit / proposed")):
                k = P["C"][m][field]
                lo, hi = wil(k, N)
                w.writerow(["c", m, "", label, "PG", k, N, pct(k, N),
                            round(lo, 3), round(hi, 3), ""])
        for meth in PLOT_METHODS:
            for field, label in (("issuer", "Issuer-unsafe installation"),
                                 ("scope", "Scope-escaping installation"),
                                 ("effect", "Unauthorized sandbox effect")):
                k = P["D"][meth][field]
                lo, hi = wil(k, 4000)
                w.writerow(["d", "", "", label, meth, k, 4000, pct(k, 4000),
                            round(lo, 3), round(hi, 3), ""])
        for k, v in P["headlines"].items():
            w.writerow(["headline", "", "", k, "", v,
                        4000 if isinstance(v, int) and v > 200 else "",
                        "", "", "guard checkpoint"])


def main():
    P = build_payload()
    out = ROOT / "results/FIGS/fig6_bar_v4"
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "fig6_bar_data_v4.csv", P)
    print("guards PASS; headline counts:",
          json.dumps(P["headlines"], indent=1))
    print("wrote", out / "fig6_bar_data_v4.csv")


if __name__ == "__main__":
    main()
