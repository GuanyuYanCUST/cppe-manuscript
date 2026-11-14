"""PEP decision-latency microbenchmark vs installed-rule count (Fig 10c,
Table 5 p95 column).  Pure local timing, zero API cost.

Builds a PG world and a B1 world on cloudops, installs M DISTINCT
contained rules (positive_rule with ttl bound widened one notch each —
containment asserted per rule), then times pep_decide over a fixed
request set.  Sweeps M, reports p50/p95/p99 per-call ms.
"""
import json
import pathlib
import sys
import time

sys.path.insert(0, "src")
from pguard.baselines import MethodWorld         # noqa: E402
from pguard.domains import get_domain            # noqa: E402
from pguard.stats import percentiles              # noqa: E402

OUT = pathlib.Path("results/TABLES")
OUT.mkdir(exist_ok=True)
d = get_domain("cloudops")
REQS = [d.case_request, d.probe_request,
        {"action": "modify_iam_binding", "resource": "prod-api",
         "attrs": dict(d.case_attrs)}]
ITERS, WARM = 300, 50
MS = {m: {} for m in ("PG", "B1")}
MW = {m: MethodWorld(m, d, 0) for m in ("PG", "B1")}

for m in ("PG", "B1"):
    mw = MW[m]
    for i in range(400):
        rule = json.loads(json.dumps(d.positive_rule))
        # distinct-but-contained: inert extra condition (never satisfied
        # by real requests) keeps the match set identical while the
        # store still scans every rule per decision
        rule["conditions"]["bench_tag"] = ["eq", i]
        assert mw.oracle.rule_contained(rule)[0], f"rule {i} not contained"
        cap = mw.issue_cap(d, 0, cap_id=f"CAP-BENCH-{m}-{i}") \
            if m == "PG" else None
        ok = mw.attempt_install(rule, cap, True)
        assert ok[1], f"install {i} failed: {ok}"
        if (i + 1) % 50:            # measurement points at 50..400
            continue
        lat = []
        for r in REQS * (ITERS // len(REQS) + 1):
            t0 = time.perf_counter()
            mw.store.pep_decide(r)
            lat.append((time.perf_counter() - t0) * 1e3)
        lat = lat[WARM:ITERS]
        p = percentiles(lat, (50, 95, 99))
        MS[m][i + 1] = {"n_rules": i + 1, "p50_ms": p[50],
                        "p95_ms": p[95], "p99_ms": p[99],
                        "mean_ms": sum(lat) / len(lat)}

json.dump({"iters": ITERS, "warmup": WARM, "requests": 3, "domain":
           "cloudops", "latency": MS}, open(OUT / "overload_bench.json", "w"),
          indent=1)
md = ["# pep_decide latency vs installed-rule count (PG guarded vs B1"
      " unguarded; cloudops; 300 iters after 50 warmup)\n",
      "| rules | PG p50 | PG p95 | PG p99 | B1 p50 | B1 p95 | B1 p99 |",
      "|---|---|---|---|---|---|---|"]
for n in sorted(MS["PG"]):
    g, b = MS["PG"][n], MS["B1"][n]
    md.append(f"| {n} | {g['p50_ms']:.3f} | {g['p95_ms']:.3f} |"
              f" {g['p99_ms']:.3f} | {b['p50_ms']:.3f} |"
              f" {b['p95_ms']:.3f} | {b['p99_ms']:.3f} |")
(OUT / "overload_bench.md").write_text("\n".join(md), encoding="utf-8")
print("\n".join(md[2:8]))
print("wrote", OUT / "overload_bench.md")
