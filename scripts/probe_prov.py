"""One tiny live call via a provider adapter (argv: provider)."""
import os
import sys

sys.path.insert(0, "src")
from pguard.llm_adapter import LLMRuleAdapter, load_dotenv  # noqa: E402

load_dotenv(".env")
p = sys.argv[1]
a = LLMRuleAdapter(provider=p, enabled=True, max_retries=1,
                   max_output_tokens=64)
print(p, "model:", a.model)
try:
    r = a._chat([{"role": "user", "content": "Reply: pong"}])
    print(p, "OK:", (r or "")[:60], "| usage:", a.usage)
except Exception as e:  # noqa: BLE001
    print(p, "FAIL:", type(e).__name__, str(e)[:300])
