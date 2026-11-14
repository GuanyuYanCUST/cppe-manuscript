"""Sensitivity replay: numeric-string condition bounds losslessly
coerced before enforcement (coerce=True), all five arms, frozen
trajectories — zero API cost.  Answers the fairness question "is the
Claude VPA=0 result a strict-typing artifact?"  Writes
replay/main_coerced.jsonl + main_coerced_summary.json per arm.
"""
import json
import pathlib
import sys

sys.path.insert(0, "src")
sys.path.insert(0, "experiments")
from real_rollout import (ATC_RESOURCE, METHODS, PROVIDER_DIRS, ROOT,  # noqa: E402
                          ks_for, summarize)
from pguard.closed_loop import replay_method          # noqa: E402

REV = {v: k for k, v in PROVIDER_DIRS.items()}

for d in ("real_glm53", "real_claude55", "real_gemini38flash",
          "real_deepseek41flash", "real_gpt56"):
    roll = ROOT / "results" / d / "rollouts" / "main"
    rep = ROOT / "results" / d / "replay"
    rep.mkdir(parents=True, exist_ok=True)
    rows = []
    with open(rep / "main_coerced.jsonl", "w", encoding="utf-8") as f:
        for p in sorted(roll.glob("*.json")):
            traj = json.loads(p.read_text(encoding="utf-8"))
            atc = ATC_RESOURCE[traj["domain"]]
            for method in METHODS:
                for k in ks_for(traj):
                    try:
                        row = replay_method(traj, method, k=k,
                                            atc_resource=atc, coerce=True)
                    except Exception as e:  # noqa: BLE001
                        row = {"method": method, "domain": traj["domain"],
                               "channel": traj["channel"],
                               "seed": traj["seed"], "k_req": k,
                               "attacker": traj["attacker"],
                               "reject_reason":
                                   f"REPLAY_ERROR:{type(e).__name__}:{e}"}
                    row["run_id"] = traj.get("run_id")
                    rows.append(row)
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[coerced {d}] {len(rows)} rows", flush=True)
    summarize(rows, "main_coerced", REV[d])
