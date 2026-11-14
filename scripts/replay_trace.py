"""Replay every GPT main trajectory, print full traceback of first error."""
import json
import pathlib
import sys
import traceback

sys.path.insert(0, "experiments")
sys.path.insert(0, "src")
from e2_baselines import ATC_RESOURCE, case_variant  # noqa: E402
from real_rollout import METHODS, ks_for  # noqa: E402
from pguard.closed_loop import replay_method  # noqa: E402

roll = pathlib.Path("results/real_gpt56/rollouts/main")
shown = 0
for p in sorted(roll.glob("*.json")):
    traj = json.loads(p.read_text())
    atc = ATC_RESOURCE[traj["domain"]]
    for method in METHODS:
        for k in ks_for(traj):
            try:
                replay_method(traj, method, k=k, atc_resource=atc)
            except Exception:  # noqa: BLE001
                print(f"=== {p.name} {method} k={k}")
                traceback.print_exc()
                shown += 1
                if shown >= 2:
                    sys.exit(0)
print("no errors")
