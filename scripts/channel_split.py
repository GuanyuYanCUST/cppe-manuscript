"""Mixed-channel arms: attribute each rollout to its API channel via
trajectory timestamp gaps, then split propose/B1-UER/PG-VPA by channel.
GLM-5.3 = bigmodel(395) + zhongkey(rest); GPT-5.6 = aizex(~395) +
zhongkey(rest).  Prints the candidate gap so the split can be eyeballed
against the known switch times."""
import json
import pathlib

for d, label in (("real_glm53", "bigmodel/zhongkey"),
                 ("real_gpt56", "aizex/zhongkey")):
    files = sorted(pathlib.Path(f"results/{d}/rollouts/main").glob("*.json"))
    ts = []
    for p in files:
        t = json.loads(p.read_text(encoding="utf-8")).get("ts")
        ts.append((t or "000000-000000", p.name))
    ts.sort()
    # 3 largest time gaps between consecutive rollout creations
    def mins(a, b):
        import datetime as dt
        fa = dt.datetime.strptime(a, "%Y%m%d-%H%M%S")
        fb = dt.datetime.strptime(b, "%Y%m%d-%H%M%S")
        return (fb - fa).total_seconds() / 60
    gaps = []
    for i in range(1, len(ts)):
        m = mins(ts[i - 1][0], ts[i][0])
        if m > 0:
            gaps.append((m, i, ts[i - 1][0], ts[i][0]))
    print(f"== {d} ({label}) n={len(ts)} largest gaps ==")
    for m, i, a, b in sorted(gaps, reverse=True)[:3]:
        print(f"  gap {m:7.1f} min after index {i} ({len(ts)-i} files"
              f" above): {a} -> {b}")
