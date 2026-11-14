"""List models visible to the ccmax (claude) zhongkey key; probe qwen ones."""
import json
import os
import sys

sys.path.insert(0, "src")
from pguard.llm_adapter import _http_transport, load_dotenv  # noqa: E402

load_dotenv(".env")
base = os.environ["CLAUDE_BASE_URL"].rstrip("/")
key = os.environ["ANTHROPIC_API_KEY"]
h = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0",
     "Authorization": "Bearer " + key}

s, b = _http_transport("GET", base + "/models", h, None, 30.0)
print("status:", s)
if s != 200:
    print(b[:200]); sys.exit(0)
ids = sorted(m["id"] for m in json.loads(b).get("data", []))
print(len(ids), "models")
print([i for i in ids if "qwen" in i.lower() or "kimi" in i.lower()]
      or "no qwen/kimi in pool")

for m in [i for i in ids if "qwen" in i.lower()]:
    p = {"model": m, "messages": [{"role": "user",
         "content": "Reply with the single word: pong"}], "max_tokens": 256}
    s, b = _http_transport("POST", base + "/chat/completions", h, p, 90.0)
    print(f"{m:26s}", "OK " + json.loads(b)["choices"][0]["message"]["content"][:30]
          if s == 200 else f"{s} {b[:80]}")
