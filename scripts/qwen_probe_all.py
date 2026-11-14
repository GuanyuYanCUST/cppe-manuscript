"""Probe every model the qwen-group key can see; print usable ones."""
import json
import os
import sys

sys.path.insert(0, "src")
from pguard.llm_adapter import _http_transport, load_dotenv  # noqa: E402

load_dotenv(".env")
base = os.environ["QWEN_BASE_URL"].rstrip("/")
key = os.environ["QWEN_API_KEY"]
h = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0",
     "Authorization": "Bearer " + key}

s, b = _http_transport("GET", base + "/models", h, None, 30.0)
ids = sorted(m["id"] for m in json.loads(b).get("data", [])) if s == 200 else []
print("models:", ids)

for m in ids:
    p = {"model": m, "messages": [{"role": "user",
         "content": "Reply with the single word: pong"}], "max_tokens": 256}
    try:
        s, b = _http_transport("POST", base + "/chat/completions", h, p, 90.0)
    except Exception as e:  # noqa: BLE001
        print(f"{m:24s} EXC {type(e).__name__}")
        continue
    if s == 200:
        try:
            txt = json.loads(b)["choices"][0]["message"]["content"][:40]
        except Exception:  # noqa: BLE001
            txt = b[:60]
        print(f"{m:24s} OK  {txt!r}")
    else:
        print(f"{m:24s} {s}  {b[:90]}")
