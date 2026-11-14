"""One diagnostic call against the claude preset: status + body dump."""
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pguard.llm_adapter import _http_transport, load_dotenv  # noqa: E402

load_dotenv(str(ROOT / ".env"))
url = (os.environ.get("CLAUDE_BASE_URL",
                      "https://api.anthropic.com/v1")
       + "/chat/completions")
payload = {"model": os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5"),
           "messages": [{"role": "user", "content": "Reply with the "
                                                  "single word: pong"}],
           "temperature": 0.0, "max_tokens": 256}
headers = {"Content-Type": "application/json",
           "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
           "Authorization": "Bearer " + os.environ["ANTHROPIC_API_KEY"]}
status, body = _http_transport("POST", url, headers, payload, 60.0)
print("status:", status)
print("body:", body[:800])
