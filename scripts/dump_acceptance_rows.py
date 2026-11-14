"""Dump acceptance replay rows, one line per (traj, method) at full k."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
rep = ROOT / "results/real_glm53/replay/acceptance.jsonl"
rows = [json.loads(l) for l in rep.read_text(encoding="utf-8").splitlines()]
kfull = max(r["k_req"] for r in rows)
for r in rows:
    if r["k_req"] != kfull or r["method"] not in ("PG", "B1", "B0", "B6"):
        continue
    atk = "ATK" if r["attacker"] else "   "
    print(f"{atk} {r['domain'][:6]:6} s{r['seed']} {r['method']:2} "
          f"prop={int(r['proposed'])} inst={int(r['installed'])} "
          f"iss={int(r['cppe_issuer'])} sc={int(r['cppe_scope'])} "
          f"ue={int(r['unauth_effect'])} outD={r['n_covered_out_of_D']} "
          f"vpa={int(r['valid_accepted'])} atc={int(r['atc_done'])} "
          f"rej={r['reject_reason']}")
