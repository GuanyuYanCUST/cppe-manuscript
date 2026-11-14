"""List model IDs available to a provider key (argv: glm|qwen|gemini|claude|gpt)."""
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pguard.llm_adapter import PROVIDERS, _http_transport, load_dotenv  # noqa: E402

load_dotenv(str(ROOT / ".env"))
p = sys.argv[1] if len(sys.argv) > 1 else "glm"
preset = PROVIDERS[p]
base = (os.environ.get(f"{p.upper()}_BASE_URL", "")
        or preset["base_url"]).rstrip("/")
key = os.environ.get(preset["key_env"], "")
h = {"User-Agent": "Mozilla/5.0", "Authorization": "Bearer " + key}
s, b = _http_transport("GET", base + "/models", h, None, 30.0)
print(p, "status:", s)
if s == 200:
    ids = sorted(m["id"] for m in json.loads(b).get("data", []))
    for i in ids:
        print(" ", i)
else:
    print(b[:300])
