"""Single cheap call to test whether the provider rate limiter lifted."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from pguard.llm_adapter import LLMRuleAdapter, load_dotenv  # noqa: E402

load_dotenv(str(ROOT / ".env"))
provider = sys.argv[1] if len(sys.argv) > 1 else "glm"
a = LLMRuleAdapter(provider=provider, enabled=True, max_retries=0,
                   max_output_tokens=256)
try:
    r = a._chat([{"role": "user", "content": "Reply with the single "
                                           "word: pong"}])
    print("RESULT:", "OK" if r else "EMPTY", repr((r or "")[:40]),
          a.usage)
except Exception as e:  # noqa: BLE001
    print("RESULT: EXC", type(e).__name__, e)
