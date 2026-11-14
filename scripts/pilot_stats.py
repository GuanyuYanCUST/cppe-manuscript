"""Claude pilot digest: per-file call count, tokens, cost, parse outcomes."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
res = ROOT / "results" / sys.argv[1] if len(sys.argv) > 1 \
    else ROOT / "results" / "real_claude55"

tot_pt = tot_ct = calls = 0
for f in sorted((res / "raw").glob("*.jsonl")):
    pt = ct = n = 0
    for line in f.open(encoding="utf-8"):
        r = json.loads(line)
        u = r.get("usage") or {}
        pt += u.get("prompt_tokens", 0)
        ct += u.get("completion_tokens", 0)
        n += 1
    calls += n
    tot_pt += pt
    tot_ct += ct
    print(f"{f.name}: {n} calls, {pt} in / {ct} out tok")

# trajectories: modes + parse health
for p in sorted((res / "rollouts" / "acceptance").glob("*.json")):
    t = json.loads(p.read_text(encoding="utf-8"))
    fin = t.get("final") or {}
    n_turns = len(t.get("turns", []))
    drops = sum(1 for x in t.get("turns", []) if not x.get("admitted", False)
                and x.get("memory_outcome") == "failure")
    rule = fin.get("rule")
    print(f"{p.name}: mode={fin.get('mode')} rule={'yes' if rule else 'no'} "
          f"turns={n_turns} mem={len(t.get('memory', []))}")

# cost at zhongkey effective rate $4.5/$4.5 per 1M (base $3 x1.5 ccmax)
c_base = (tot_pt * 3 + tot_ct * 3) / 1e6
c_x15 = c_base * 1.5
print(f"\nTOTAL {calls} calls: {tot_pt} in / {tot_ct} out tok")
print(f"cost @ $3/$3:  ${c_base:.3f}")
print(f"cost @ x1.5:   ${c_x15:.3f}")
if calls:
    print(f"per call avg: {tot_pt // calls} in / {tot_ct // calls} out, "
          f"${c_x15 / calls:.4f}/call @x1.5")
