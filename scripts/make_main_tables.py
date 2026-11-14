"""Stage-4 summary tables from replay/main.jsonl — PA-1..PA-4 compliant:
UER = issuer OR scope (PA-3), per-rollout AND per-attempt denominators
(PA-4), Wilson CIs everywhere, attacker arm reported separately.
Output: results/real_glm53/main_tables.md (+ main_tables.json)."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pguard.baselines import METHODS            # noqa: E402
from pguard.metrics import _ci                  # noqa: E402

REP = ROOT / "results" / "real_glm53" / "replay"


def wil(k, n):
    c = _ci(k, n)
    if c["na"]:
        return "  n/a"
    return f"{c['rate']:.3f} [{c['wilson_lo']:.2f},{c['wilson_hi']:.2f}]"


def rate(rs, key):
    n = len(rs)
    k = sum(bool(r[key]) for r in rs)
    return f"{k}/{n} {wil(k, n)}"


def main():
    rows = [json.loads(l) for l in
            (REP / "main.jsonl").read_text(encoding="utf-8").splitlines()]
    legit = [r for r in rows if not r["attacker"]]
    atk = [r for r in rows if r["attacker"]]
    ks = sorted({r["k_req"] for r in rows})
    kfull = max(ks)
    out = [f"# Main experiment tables (from replay/main.jsonl, "
           f"{len(rows)} rows; legit {len(legit)} / attacker {len(atk)})",
           "", "## Legit arm — method x k (full memory = "
           f"k={kfull})", "",
           "| method k | rollouts | propose | install | CPPE-issuer "
           "| UER (per-rollout) | UER (per-attempt) | VPA | ATC |"
           " |---|---|---|---|---|---|---|---|---|"]
    js = {"legit": {}, "attacker": {}, "by_domain": {}, "by_channel": {}}
    for method in METHODS:
        for k in ks:
            rs = [r for r in legit if r["method"] == method
                  and r["k_req"] == k]
            if not rs:
                continue
            att = [r for r in rs if r["attempted"]]
            inst = [r for r in rs if r["installed"]]
            prop = [r for r in rs if r["proposed"]]
            pg = [r for r in inst if r["method"] == "PG"]
            vpak = sum(r["valid_accepted"] for r in pg)
            vpa = (f"{vpak}/{len(pg)} "
                   f"{wil(vpak, len(pg))}") if pg else "-"
            k_ue = sum(r["unauth_effect"] for r in att)
            out.append(
                f"| {method} k={k} | {len(rs)} | {rate(rs, 'proposed')} "
                f"| {rate(rs, 'installed')} | {rate(rs, 'cppe_issuer')} "
                f"| {rate(rs, 'unauth_effect')} | "
                f"{k_ue}/{len(att)} {wil(k_ue, len(att))} | {vpa} "
                f"| {rate(rs, 'atc_done')} |")
            js["legit"][f"{method}|k={k}"] = {
                "n": len(rs),
                "propose": _ci(sum(r["proposed"] for r in rs), len(rs)),
                "install": _ci(sum(r["installed"] for r in rs), len(rs)),
                "cppe_issuer": _ci(sum(r["cppe_issuer"] for r in rs),
                                   len(rs)),
                "cppe_any": _ci(sum(r["cppe_issuer"] or r["cppe_scope"]
                                    for r in rs), len(rs)),
                "unauth_effect": _ci(sum(r["unauth_effect"] for r in rs),
                                     len(rs)),
                "unauth_effect_per_attempt": _ci(k_ue, len(att)),
                "vpa": _ci(vpak, len(pg)) if pg else None,
                "atc": _ci(sum(r["atc_done"] for r in rs), len(rs)),
                "malformed": _ci(
                    sum(r["reject_reason"].startswith("MALFORMED")
                        for r in rs if r["reject_reason"]), len(rs))}
    out += ["", "## Attacker arm (separately labeled, episodic only)", "",
            "| method | rollouts | propose | install | out-of-envelope "
            "covered | PG reject reason | UER |", "|---|---|---|---|---|---|---|"]
    for method in METHODS:
        rs = [r for r in atk if r["method"] == method
              and r["k_req"] == kfull]
        if not rs:
            continue
        cov = sum(1 for r in rs if r["n_covered_out_of_D"])
        oor = sum(1 for r in rs
                  if r["reject_reason"] == "OUT_OF_ROOT")
        out.append(f"| {method} | {len(rs)} | {rate(rs, 'proposed')} "
                   f"| {rate(rs, 'installed')} | {cov} | {oor} "
                   f"OUT_OF_ROOT | {rate(rs, 'unauth_effect')} |")
        js["attacker"][method] = {
            "n": len(rs),
            "propose": _ci(sum(r["proposed"] for r in rs), len(rs)),
            "install": _ci(sum(r["installed"] for r in rs), len(rs)),
            "covers_out_of_envelope": _ci(cov, len(rs)),
            "unauth_effect": _ci(sum(r["unauth_effect"] for r in rs),
                                 len(rs))}
    # PG vs B1 by domain and by channel (legit, full k)
    for name, key, vals in (("by_domain", "domain",
                             sorted({r["domain"] for r in legit})),
                            ("by_channel", "channel",
                             sorted({r["channel"] for r in legit}))):
        out += ["", f"## PG vs B1 {name} (legit, k={kfull})", "",
                "| " + key + " | method | n | install | UER | VPA | ATC |",
                "|---|---|---|---|---|---|---|"]
        for v in vals:
            for method in ("PG", "B1"):
                rs = [r for r in legit if r["method"] == method
                      and r["k_req"] == kfull and r[key] == v]
                if not rs:
                    continue
                inst = [r for r in rs if r["installed"]]
                vpak = sum(r["valid_accepted"] for r in inst)
                out.append(
                    f"| {v} | {method} | {len(rs)} "
                    f"| {rate(rs, 'installed')} "
                    f"| {rate(rs, 'unauth_effect')} "
                    f"| {vpak}/{len(inst)} {wil(vpak, len(inst))} "
                    f"| {rate(rs, 'atc_done')} |")
                js[name][f"{v}|{method}"] = {
                    "n": len(rs),
                    "install": _ci(sum(r["installed"] for r in rs), len(rs)),
                    "unauth_effect": _ci(sum(r["unauth_effect"] for r in rs),
                                         len(rs))}
    text = "\n".join(out) + "\n"
    (REP / "main_tables.md").write_text(text, encoding="utf-8")
    (REP / "main_tables.json").write_text(
        json.dumps(js, indent=1, ensure_ascii=False), encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
