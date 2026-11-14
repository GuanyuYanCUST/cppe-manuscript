"""One-off: compare the 5 repro-arm raw replies (no API calls)."""
import json

lines = [json.loads(l) for l in open(
    "results/LLM_PILOT/raw/LLM-PILOT-20261008-170409.jsonl",
    encoding="utf-8")]
tail = lines[-5:]
for i, r in enumerate(tail):
    try:
        body = json.loads(r["response_body"])
        c = body["choices"][0]["message"]["content"]
        comp = body["usage"]["completion_tokens"]
        text = c.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text.replace("json", "", 1).strip()
        rule = json.loads(text) if text.startswith("{") else None
        print(i, "status", r["status"], "completion_tokens", comp,
              "rule:", json.dumps(rule, sort_keys=True)[:200])
    except Exception as e:                     # noqa: BLE001
        print(i, "parse err", repr(e)[:90])
