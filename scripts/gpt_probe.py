"""One tiny live call through the gpt adapter to see the raw error."""
import os
import sys

sys.path.insert(0, "src")
from pguard.llm_adapter import LLMRuleAdapter, load_dotenv  # noqa: E402

load_dotenv(".env")
a = LLMRuleAdapter(provider="gpt", enabled=True, max_retries=1,
                   max_output_tokens=64)
print("model:", os.environ.get("GPT_MODEL"))
try:
    r = a._chat([{"role": "user", "content": "Reply: pong"}])
    print("OK:", r[:80])
    print("usage:", a.usage)
except Exception as e:  # noqa: BLE001
    print("FAIL:", type(e).__name__, str(e)[:400])
