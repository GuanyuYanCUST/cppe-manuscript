"""Freeze the S3 v3 figure set.

1. render all three figures with SOURCE_DATE_EPOCH fixed (deterministic
   PDF metadata), twice;
2. byte-compare the two renders (determinism proof);
3. write results/FIGS/v3_20261010/MANIFEST.json: generation time,
   commands, sha256 of scripts + inputs + outputs.

Run: .venv/bin/python scripts/freeze_v3.py
"""
import hashlib
import json
import os
import pathlib
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "results/FIGS/v3_20261010"
SCRIPTS = ["scripts/fig_v3_common.py", "scripts/make_fig6b_v3.py",
           "scripts/make_fig6c_v3.py", "scripts/make_fig9_v3.py"]
INPUTS = ["audit_20261010/gates/cell_verify_v3.json",
          "results/TABLES/master_table.json",
          "results/E5/E5-factorial-20261008-155213/summary.json",
          "audit_20261010/gates/authority_fork_results.jsonl"]
FIGS = ["fig6b_tradeoff_v3.pdf", "fig6c_tradeoff_v3.pdf",
        "fig9_factorial_v3.pdf", "fig6b_tradeoff_v3.png",
        "fig6c_tradeoff_v3.png", "fig9_factorial_v3.png"]
EPOCH = 1728500000


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


env = dict(os.environ, SOURCE_DATE_EPOCH=str(EPOCH))
for rnd in (1, 2):
    for s in ("make_fig6b_v3", "make_fig6c_v3", "make_fig9_v3"):
        subprocess.run([str(ROOT / ".venv/bin/python"),
                        str(ROOT / "scripts" / f"{s}.py")],
                       check=True, env=env, cwd=str(ROOT / "scripts"),
                       capture_output=True)
    if rnd == 1:
        first = {f: sha(OUT / f) for f in FIGS}
identical = first == {f: sha(OUT / f) for f in FIGS}

manifest = {
    "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "source_date_epoch": EPOCH,
    "commands": [f"SOURCE_DATE_EPOCH={EPOCH} .venv/bin/python scripts/"
                 f"{s}.py" for s in ("make_fig6b_v3", "make_fig6c_v3",
                                     "make_fig9_v3")],
    "deterministic_rerender_identical": identical,
    "guard": "all numbers asserted against "
             "audit_20261010/gates/cell_verify_v3.json (independent "
             "per-cell recount of raw replay_v2; raw == fig_data_v2 == "
             "Gate C, 0 mismatches) at render time",
    "sha256": {
        "scripts": {s: sha(ROOT / s) for s in SCRIPTS},
        "inputs": {i: sha(ROOT / i) for i in INPUTS},
        "outputs": {f: sha(OUT / f) for f in FIGS},
    },
}
(OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
print("deterministic_rerender_identical:", identical)
for f in FIGS:
    print(" ", f, manifest["sha256"]["outputs"][f][:16])
if not identical:
    raise SystemExit(2)
