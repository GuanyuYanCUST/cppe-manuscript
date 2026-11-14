"""Dump structure of one rollout json (argv: path)."""
import json
import pathlib
import sys

d = json.loads(pathlib.Path(sys.argv[1]).read_text())
print("top:", {k: type(v).__name__ for k, v in d.items()})
print("final:", json.dumps(d.get("final"), ensure_ascii=False)[:400])
if d.get("turns"):
    t = d["turns"][0]
    print("turn keys:", sorted(t.keys()))
    for x in d["turns"]:
        prop = x.get("proposal") or x.get("new_rule") or ""
        print(x.get("i"), "admit=", x.get("admitted"),
              "mode=", x.get("proposal_mode") or x.get("mode"),
              "prop_len=", len(json.dumps(prop, ensure_ascii=False)) if prop else 0)
