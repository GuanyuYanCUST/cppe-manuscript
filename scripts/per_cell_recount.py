#!/usr/bin/env python3
"""Per-cell recount of the 80 model-domain-channel cells (legit arm).

Recomputes, directly from the frozen replay_v2 verdict rows, the per-cell
table reported in the paper (A_T1): proposals, well-formed parses, PG
installations, not-contained proposals, and B1 unauthorized effects.

Recount rule (matches the frozen A_T1 pipeline): for each legitimate
trajectory (attacker=False), take its terminal replay view --- the row
with the largest k (retained-success prefix). Proposals are monotone in
k, so the terminal view equals "ever proposed" (verified: max-k and
any-k union give identical counts on the frozen data).

Well-formed      = proposed and candidate_contained is not None
                  (None means parsing failed; containment never evaluated)
Not contained    = proposed and candidate_contained is not True
                  (out-of-root + out-of-class + malformed)
PG installs      = PG terminal rows with installed=True
B1 effects       = B1 terminal rows with unauth_effect=True

Usage:  python3 scripts/per_cell_recount.py [--out CSV]
Fails (exit 1) if the recomputed per-model sums or the grand totals
deviate from the frozen published values.
"""
import argparse
import collections
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MODELS = [
    ("real_glm53", "GLM-5.3"),
    ("real_claude55", "Claude-5.5"),
    ("real_gemini38flash", "Gemini-3.8-flash"),
    ("real_deepseek41flash", "DeepSeek-v4.1-flash"),
    ("real_gpt56", "GPT-5.6"),
]

# Frozen per-model sums from the published 80-cell table (paper A_T1):
# (proposals, parsed, pg_installs, not_contained, b1_effects)
FROZEN_SUMS = {
    "GLM-5.3": (729, 607, 299, 351, 215),
    "Claude-5.5": (303, 283, 266, 36, 16),
    "Gemini-3.8-flash": (729, 729, 509, 220, 220),
    "DeepSeek-v4.1-flash": (757, 691, 590, 167, 101),
    "GPT-5.6": (650, 650, 611, 32, 32),
}
# Frozen grand totals (paper Table T3 block (a) footnotes).
FROZEN_TOTALS = {"proposals": 3168, "parsed": 2960, "not_contained": 806,
                 "b1_effects": 584, "pg_installs": 2275}


def terminal_rows(path, method):
    """Return {traj_key: row} of the largest-k legit row per trajectory."""
    best = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("method") != method or r.get("attacker"):
                continue
            key = (r["domain"], r["channel"], r["seed"])
            if key not in best or r["k"] > best[key]["k"]:
                best[key] = r
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(
        ROOT, "audit_20261010", "gates", "per_cell_recount.csv"))
    args = ap.parse_args()

    rows_out = []
    failures = []
    for d, name in MODELS:
        path = os.path.join(ROOT, "results", d, "replay_v2", "main.jsonl")
        pg = terminal_rows(path, "PG")
        b1 = terminal_rows(path, "B1")

        cell = collections.defaultdict(
            lambda: dict(n=0, prop=0, parsed=0, pg=0, notc=0, b1=0))
        for (dom, ch, seed), r in pg.items():
            c = cell[(dom, ch)]
            c["n"] += 1
            if r.get("proposed"):
                c["prop"] += 1
                if r.get("candidate_contained") is not None:
                    c["parsed"] += 1
                if r.get("candidate_contained") is not True:
                    c["notc"] += 1
            if r.get("installed"):
                c["pg"] += 1
        for (dom, ch, seed), r in b1.items():
            if r.get("unauth_effect"):
                cell[(dom, ch)]["b1"] += 1

        sums = [0] * 5
        for (dom, ch) in sorted(cell):
            c = cell[(dom, ch)]
            rows_out.append([name, dom, ch, c["n"], c["prop"], c["parsed"],
                             c["pg"], c["notc"], c["b1"]])
            sums = [s + c[k] for s, k in
                    zip(sums, ("prop", "parsed", "pg", "notc", "b1"))]
        got = tuple(sums)
        if got != FROZEN_SUMS[name]:
            failures.append(f"{name}: sums {got} != frozen {FROZEN_SUMS[name]}")

    totals = {
        "proposals": sum(int(r[4]) for r in rows_out),
        "parsed": sum(int(r[5]) for r in rows_out),
        "pg_installs": sum(int(r[6]) for r in rows_out),
        "not_contained": sum(int(r[7]) for r in rows_out),
        "b1_effects": sum(int(r[8]) for r in rows_out),
    }
    for k, v in FROZEN_TOTALS.items():
        if totals[k] != v:
            failures.append(f"total {k}: {totals[k]} != frozen {v}")

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["model", "domain", "channel", "n", "proposals",
                    "well_formed", "pg_installs", "not_contained",
                    "b1_unauth_effects"])
        w.writerows(rows_out)

    if failures:
        print("RECOUNT MISMATCH:")
        for f in failures:
            print(" ", f)
        sys.exit(1)
    print(f"OK: {len(rows_out)} cells -> {args.out}")
    print("per-model sums and grand totals match the frozen published values")


if __name__ == "__main__":
    main()
