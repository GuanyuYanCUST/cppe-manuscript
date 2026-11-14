#!/usr/bin/env python3
"""E7 special-case review: the 28-record expansion behind Table 4's footnote.

Materializes, from the frozen E7 component-ablation summary
(results/E7/E7-ablation-20261008-155832/summary.json -- the canonical 24-cell
run; the two earlier partial run dirs are not used), one row per outcome
record with its pass predicate:

  20 install-block records : A1 issuer typing, A2 containment, A6 LLM-only
                             judge (4 domains each) plus A4 epoch/CAS with its
                             two sub-checks (stale_epoch, post_amend_cas;
                             4 domains x 2 = 8)
   4 necessity records      : A3 full-system DENY (NECESSITY_BETTER_PLAN_EXISTS)
                             vs ablated ADMIT_CASE
   4 replay records         : A5 first use ADMIT, second use DENY (REPLAY);
                             ablated second use admits with effect

Pass rule per record (matches the frozen summary's `passed` flag at the
24-cell level): the full system blocks/denies (no install, no effect) while
the same attack under the corresponding component ablation succeeds
(installs / admits / replays with a flagged effect). Offline oracle flags,
not executed sandbox probes.

Usage:  python3 scripts/e7_special_case_review.py [--out CSV]
Fails (exit 1) unless all 24 cells pass and exactly 28 records are emitted.
"""
import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CANONICAL_RUN = "E7-ablation-20261008-155832"
SUMMARY = os.path.join(ROOT, "results", "E7", CANONICAL_RUN, "summary.json")

INSTALL_ARMS = ("A1_issuer_typing", "A2_containment", "A6_llm_only_judge")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(
        ROOT, "audit_20261010", "gates", "E7_SPECIAL_CASE_REVIEW.csv"))
    args = ap.parse_args()

    with open(SUMMARY, encoding="utf-8") as fh:
        s = json.load(fh)

    failures = []
    rows = []
    cells_passed = 0
    cells_total = 0
    for dom in sorted(s["results"]):
        for arm, v in sorted(s["results"][dom].items()):
            cells_total += 1
            if not v.get("passed"):
                failures.append(f"{dom}/{arm}: passed=False")
            else:
                cells_passed += 1
            out = v["outcomes"]
            if arm in INSTALL_ARMS:
                rows.append([dom, arm, "install_block",
                             out["full"].get("reason", ""),
                             "install" if out["ablated"].get("install") else "",
                             bool(out["ablated"].get("effect"))])
            elif arm == "A3_necessity":
                rows.append([dom, arm, "necessity",
                             f'{out["full"]["decision"]}:{out["full"]["reason"]}',
                             out["ablated"]["decision"],
                             bool(out["ablated"].get("unnecessary_exception_admitted"))])
            elif arm == "A4_epoch_cas":
                for sub in ("stale_epoch", "post_amend_cas"):
                    o = out[sub]
                    rows.append([dom, arm, f"install_block:{sub}",
                                 o["full"].get("reason", ""),
                                 "install" if o["ablated"].get("install") else "",
                                 bool(o["ablated"].get("effect"))])
            elif arm == "A5_replay":
                rows.append([dom, arm, "replay",
                             f'1st:{out["full"]["first"]};2nd:{out["full"]["second"]}:{out["full"]["second_reason"]}',
                             f'2nd:{out["ablated"]["second"]}',
                             bool(out["ablated"].get("replayed_effect"))])
            else:
                failures.append(f"{dom}/{arm}: unknown arm shape")

    # every emitted record must show full-system block + ablated success
    # (install-block records flag success by the install itself -- the
    # stale_epoch sub-check probes no effect; post_amend_cas/A1/A2/A6 do)
    for r in rows:
        if not r[4] or (not r[5] and r[4] != "install"):
            failures.append(f"record {r[0]}/{r[1]}: ablated outcome not a success: {r}")
        if not r[3]:
            failures.append(f"record {r[0]}/{r[1]}: empty full-system reason")

    if cells_passed != 24 or cells_total != 24:
        failures.append(f"cells: {cells_passed}/{cells_total} != 24/24")
    if len(rows) != 28:
        failures.append(f"record count {len(rows)} != 28 "
                        "(20 install-block + 4 necessity + 4 replay)")

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["domain", "attack", "record_kind",
                    "full_system_outcome", "ablated_outcome", "ablated_effect_flagged"])
        w.writerows(rows)

    if failures:
        print("E7 REVIEW MISMATCH:")
        for f in failures:
            print(" ", f)
        sys.exit(1)
    print(f"OK: 24/24 cells pass; {len(rows)} records -> {args.out}")
    print("expansion = 20 install-block (A4 carries stale_epoch + post_amend_cas) "
          "+ 4 necessity + 4 replay")


if __name__ == "__main__":
    main()
