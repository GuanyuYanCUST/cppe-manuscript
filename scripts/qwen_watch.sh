#!/bin/bash
# Poll zhongkey qwen models until one becomes usable; log every attempt.
cd "$(dirname "$0")/.." || exit 1
PY=.venv/bin/python
for i in $(seq 1 48); do   # up to 8 hours
  echo "=== probe $i $(date +%H:%M:%S) ==="
  for m in qwen3.7-max qwen3.8-max; do
    .venv/bin/python - "$m" <<'EOF'
import os, sys, json, pathlib
sys.path.insert(0, "src")
from pguard.llm_adapter import _http_transport, load_dotenv
load_dotenv(".env")
m = sys.argv[1]
base = os.environ["QWEN_BASE_URL"].rstrip("/")
h = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0",
     "Authorization": "Bearer " + os.environ["QWEN_API_KEY"]}
p = {"model": m, "messages": [{"role": "user",
     "content": "Reply with the single word: pong"}], "max_tokens": 256}
s, b = _http_transport("POST", base + "/chat/completions", h, p, 60.0)
ok = s == 200
print(m, "OK" if ok else f"status {s}", flush=True)
sys.exit(0 if ok else 1)
EOF
    if [ $? -eq 0 ]; then
      echo "$m AVAILABLE at $(date)" >> logs/qwen_watch.log
      echo "QWEN_UP:$m"
      exit 0
    fi
  done
  sleep 600
done
echo "QWEN_STILL_DOWN after 8h"
