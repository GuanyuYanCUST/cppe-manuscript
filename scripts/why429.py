"""Show the actual 429 response bodies (they carry the reason)."""
import json
import pathlib

raw = pathlib.Path(__file__).resolve().parents[1] / \
    "results/real_glm53/raw"
seen = set()
for p in sorted(raw.glob("rollout-main-*.jsonl")):
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if o.get("status") != 429:
            continue
        b = o.get("response_body", "")
        if isinstance(b, str):
            try:
                b = json.loads(b)
            except ValueError:
                pass
        key = json.dumps(b, sort_keys=True, ensure_ascii=False)[:400]
        if key not in seen:
            seen.add(key)
            print(p.name, "->", key[:380])
