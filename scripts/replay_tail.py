"""A2 memory-capacity variant: replay with only the most recent N
memory entries retained (bounded-memory agent), all five arms, frozen
trajectories — zero API cost.  k-prefix truncation keeps the FIRST k
successes; this keeps the LAST N events — the complement direction.
Writes replay/main_tail{N}.jsonl + summaries.
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

for N in (3, 5):
    for d in ("real_glm53", "real_claude55", "real_gemini38flash",
              "real_deepseek41flash", "real_gpt56"):
        roll = ROOT / "results" / d / "rollouts" / "main"
        rep = ROOT / "results" / d / "replay"
        rows = []
        tag = f"main_tail{N}"
        with open(rep / f"{tag}.jsonl", "w", encoding="utf-8") as f:
            for p in sorted(roll.glob("*.json")):
                traj = json.loads(p.read_text(encoding="utf-8"))
                traj["memory"] = traj["memory"][-N:]
                atc = ATC_RESOURCE[traj["domain"]]
                for method in METHODS:
                    # k=N: slicing [:N] of the already-tail-truncated
                    # memory is a no-op, and gives summarize() a real
                    # k_req to key cells on
                    try:
                        row = replay_method(traj, method, k=N,
                                            atc_resource=atc)
                    except Exception as e:  # noqa: BLE001
                        row = {"method": method,
                               "domain": traj["domain"],
                               "channel": traj["channel"],
                               "seed": traj["seed"], "k_req": None,
                               "attacker": traj["attacker"],
                               "reject_reason":
                                   f"REPLAY_ERROR:{type(e).__name__}:"
                                   f"{e}"}
                    row["run_id"] = traj.get("run_id")
                    rows.append(row)
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"[tail{N} {d}] {len(rows)} rows", flush=True)
        summarize(rows, tag, REV[d])
