"""Health stats over raw-calls jsonl files (argv: glob pattern)."""
import glob
import json
import pathlib
import sys

for path in sorted(glob.glob(sys.argv[1])):
    rows = [json.loads(l) for l in
            pathlib.Path(path).read_text().splitlines() if l.strip()]
    n = len(rows)
    ok = [r for r in rows if r.get("status") == 200]
    durs = sorted(r["latency_s"] for r in rows if r.get("latency_s"))
    line = f"{path.split('/')[-1]} calls={n} ok={len(ok)}"
    if durs:
        line += (f" p50={durs[len(durs)//2]:.0f}s"
                 f" p90={durs[int(len(durs)*0.9)]:.0f}s max={durs[-1]:.0f}s")
    bad = {}
    for r in rows:
        if r.get("status") != 200:
            bad[r.get("status")] = bad.get(r.get("status"), 0) + 1
    if bad:
        line += f" non200={bad}"
    print(line)
