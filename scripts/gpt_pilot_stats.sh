#!/bin/bash
# GPT pilot digest: modes, proposals, tokens, one None-mode autopsy.
cd "$(dirname "$0")/.." || exit 1
P=.venv/bin/python
$P - <<'EOF'
import json, pathlib, glob
root = pathlib.Path("results/real_gpt56")
cks = sorted((root/"rollouts"/"acceptance").glob("*.json"))
print(f"checkpoints: {len(cks)}")
modes, props, turns_ok, turns_drop = {}, 0, 0, 0
for p in cks:
    t = json.loads(p.read_text())
    f = t["final"]
    modes[f.get("mode")] = modes.get(f.get("mode"), 0) + 1
    props += bool(f.get("rule"))
    for x in t["turns"]:
        if x["reply_raw"] is None: turns_drop += 1
        else: turns_ok += 1
    if f.get("mode") is None:
        print("NONE-MODE file:", p.name)
        print("  final reply_raw[:400]:",
              (f.get("reply_raw") or "")[:400].replace("\n", " "))
print("modes:", modes, "proposals:", props,
      "turns ok/drop:", turns_ok, turns_drop)
# token accounting from raw cache
pt = ct = calls = 0
for p in (root/"raw").glob("*.jsonl"):
    for line in p.read_text().splitlines():
        o = json.loads(line)
        b = o.get("response_body")
        if o.get("status") == 200 and b:
            try:
                u = (json.loads(b) if isinstance(b, str) else b).get("usage", {})
                pt += u.get("prompt_tokens", 0); ct += u.get("completion_tokens", 0); calls += 1
            except ValueError: pass
print(f"raw: calls={calls} prompt={pt} completion={ct}")
EOF
