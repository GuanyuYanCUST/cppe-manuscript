"""One diagnostic call: print HTTP status + response body (no headers)."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pguard.llm_adapter import _http_transport, load_dotenv  # noqa: E402

load_dotenv(str(ROOT / ".env"))
import os  # noqa: E402

url = (os.environ.get("GPT_BASE_URL",
                      "https://api.openai.com/v1")
       + "/chat/completions")
payload = {"model": os.environ.get("GPT_MODEL", "gpt-5.6-terra"),
           "messages": [{"role": "user", "content": "Reply with the "
                                                  "single word: pong"}],
           "temperature": 0.0, "max_tokens": 256}
headers = {"Content-Type": "application/json",
           "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
           "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]}
status, body = _http_transport("POST", url, headers, payload, 60.0)
print("status:", status)
print("body:", body[:600])
if status != 200:  # try the HK line as fallback
    url2 = "https://ca.memofun.net/v1/chat/completions"
    s2, b2 = _http_transport("POST", url2, headers, payload, 60.0)
    print("hk status:", s2)
    print("hk body:", b2[:600])
