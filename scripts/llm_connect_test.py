"""ONE real GLM-5.3 connection test (user-approved 2026-10-08).

Single HTTP call: verifies auth, model invocation, response parsing, and
token usage accounting.  The API key is loaded from .env, used for the
Authorization header, and NEVER printed, echoed, or written anywhere.
Exit codes: 0 pass, 1 API/parse failure, 2 key not configured.
"""
import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pguard.llm_adapter import LLMRuleAdapter, load_dotenv  # noqa: E402


def _save(rec):
    d = os.path.join(os.path.dirname(__file__), "..", "results",
                     "LLM_PILOT")
    os.makedirs(d, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    p = os.path.join(d, "connect_test_%s.json" % ts)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print("saved: %s" % os.path.relpath(p))


def main():
    load_dotenv(".env")
    a = LLMRuleAdapter(provider="glm", model="glm-5.3", enabled=True,
                       max_retries=0, max_output_tokens=512)
    if not a.enabled:
        print("FAIL(config): GLM_API_KEY absent from env and .env")
        return 2
    print("config: model=%s base_url=%s key=***set" % (a.model, a.base_url))
    payload = {"model": a.model,
               "messages": [{"role": "user",
                             "content": "Reply with exactly: OK"}],
               "temperature": 0.0, "max_tokens": 512}
    payload.update(a._extra_payload)
    headers = {"Content-Type": "application/json",
               "Authorization": "Bearer " + a._api_key}
    t0 = time.time()
    status, body = a.transport("POST", a.base_url + "/chat/completions",
                               headers, payload)
    dt = time.time() - t0
    print("http: status=%d latency_s=%.2f bytes=%d" % (status, dt, len(body)))
    out = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
           "model": a.model, "base_url": a.base_url,
           "http_status": status, "latency_s": round(dt, 2)}
    if status != 200:
        try:      # sanitized provider error (body carries no key material)
            msg = json.loads(body).get("error", {}).get("message",
                                                        body[:200])
        except ValueError:
            msg = body[:200]
        print("FAIL(auth/transport): %s" % msg)
        out["error"] = msg
        _save(out)
        return 1
    try:
        data = json.loads(body)
        content = data["choices"][0]["message"]["content"]
        u = data.get("usage", {})
        assert int(u.get("prompt_tokens", 0)) > 0
    except (ValueError, KeyError, IndexError, TypeError, AssertionError) as e:
        print("FAIL(parse): %r" % e)
        out["parse_error"] = repr(e)
        _save(out)
        return 1
    a.usage["calls"] = 1
    a.usage["prompt_tokens"] = u.get("prompt_tokens", 0)
    a.usage["completion_tokens"] = u.get("completion_tokens", 0)
    print("model_echo: %s" % data.get("model", ""))
    print("reply: %r" % content)
    print("usage: %s" % json.dumps(a.usage))
    print("cost_usd(estimate): %.6f" % a.cost_usd())
    out.update({"server_model": data.get("model", ""), "reply": content,
                "usage": dict(a.usage),
                "cost_usd_estimate": a.cost_usd(),
                "auth_ok": True, "parse_ok": True})
    _save(out)
    print("PASS: auth + invoke + parse + usage all OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
