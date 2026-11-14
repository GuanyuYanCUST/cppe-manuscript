"""Remove infrastructure-corrupted main-run checkpoints (dropped turns
caused by the 429 storm) so the sweep can rerun those seeds honestly.
Raw caches keep the evidence; a purge report records every deletion."""
import json
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
roll = ROOT / "results" / "real_glm53" / "rollouts" / "main"
report = []
for p in sorted(roll.glob("*.json")):
    t = json.loads(p.read_text(encoding="utf-8"))
    dropped = sum(1 for x in t["turns"] if x["reply_raw"] is None)
    final_dropped = t["final"]["reply_raw"] is None
    if dropped or final_dropped:
        p.unlink()
        report.append({"file": p.name, "dropped_turns": dropped,
                       "final_dropped": final_dropped,
                       "ts": time.strftime("%Y%m%d-%H%M%S")})
        print(f"purged {p.name} (dropped_turns={dropped}, "
              f"final_dropped={final_dropped})")
out = ROOT / "results" / "real_glm53" / "PURGE_REPORT.json"
existing = json.loads(out.read_text(encoding="utf-8")) if out.exists() \
    else []
out.write_text(json.dumps(existing + report, indent=1,
                          ensure_ascii=False), encoding="utf-8")
print(f"purged {len(report)}; total purge record "
      f"{len(existing) + len(report)}; kept "
      f"{len(list(roll.glob('*.json')))}")
