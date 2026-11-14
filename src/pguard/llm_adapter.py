"""Unified GPT / Claude / GLM / Qwen adapter (OpenAI-compatible transport).

Zero third-party dependencies (stdlib urllib).  Network is used ONLY
when ``enabled=True`` AND an API key is configured — the offline phase
constructs it with a MockTransport, never a socket.

Cost accounting: every call's usage is recorded; ``cost_usd`` uses the
per-model price table (USD per 1M tokens), conservative (unknown model
prices fall back to the most expensive configured tier).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request


class RateLimited(Exception):
    """Provider rate limit that survived full backoff on 3 consecutive
    turns.  Runners catch this and stop the cell instead of writing
    infrastructure-failure trajectories as if they were model behavior."""


class FatalAPIError(Exception):
    """Business error retrying can never fix (official error-code table,
    docs.bigmodel.cn/cn/faq/api-code): 1113 account balance exhausted,
    1309 plan expired, 1313 fair-use throttle, 1311/1314/1315 wrong
    entitlement/key type, 1316-1321 quota+no-overage-balance, 401 auth,
    400 bad request.  Runners must STOP the whole run and report —
    never wait, never retry, never checkpoint."""

    def __init__(self, code: str, message: str, status: int):
        super().__init__(f"HTTP {status} error {code}: {message}")
        self.code, self.status = code, status


# business codes that ARE worth retrying (everything else on a 4xx/429
# body is fatal by the official table); 5xx/transport stay retryable.
# operation_in_progress: relay-side 409 concurrency lock whose own error
# text says "请稍后查询或重试" (observed on aizex Codex relay 2026-10-09)
RETRYABLE_CODES = {"1302", "1305", "1308", "1310",
                   "operation_in_progress"}


def _error_code(body: str) -> tuple[str | None, str]:
    """Extract (error.code, error.message) from a response body, if any."""
    try:
        e = json.loads(body).get("error", {})
        c = e.get("code")
        return (str(c) if c is not None else None), e.get("message", "")
    except (ValueError, AttributeError):
        return None, ""

# provider presets: OpenAI-compatible endpoints (Claude via Anthropic's
# OpenAI-compatibility endpoint).  extra_payload carries provider-specific
# switches: GLM-5.x / Qwen are reasoning models — thinking MUST be disabled
# or max_tokens is consumed by reasoning and content comes back empty
# (observed live 2026-10-08: 32-token budget -> reply '').
PROVIDERS = {
    "gpt": {"base_url": "https://api.openai.com/v1",
            "key_env": "OPENAI_API_KEY", "default_model": "gpt-4o"},
    "claude": {"base_url": "https://api.anthropic.com/v1",
               "key_env": "ANTHROPIC_API_KEY",
               "default_model": "claude-sonnet-5-5",
               # zhongkey/ccmax Claude serves thinking-enabled upstream:
               # temperature 0 -> HTTP 400 invalid_request (2026-10-09
               # probe); extra_payload merges last, overriding the
               # constructor default of 0.0
               "extra_payload": {"temperature": 1.0}},
    "glm": {"base_url": "https://open.bigmodel.cn/api/paas/v4",
            "key_env": "GLM_API_KEY", "default_model": "glm-5.3",
            # glm-5.3 always thinks: thinking.type only takes
            # enabled/disabled (disabled -> HTTP 400 for GLM-5.x); effort
            # is the separate reasoning_effort param (low/high/max,
            # default max) — use low + max_tokens sized for reasoning+JSON
            "extra_payload": {"thinking": {"type": "enabled"},
                              "reasoning_effort": "low"}},
    "qwen": {"base_url":
             "https://dashscope.aliyuncs.com/compatible-mode/v1",
             "key_env": "QWEN_API_KEY", "default_model": "qwen-plus",
            "extra_payload": {"enable_thinking": False}},
    # gemini via OpenAI-compat (Google's v1beta OpenAI endpoint or a
    # relay via GEMINI_BASE_URL); thinking toggles are not needed on
    # the compat layer
    "gemini": {"base_url":
               "https://generativelanguage.googleapis.com/v1beta/"
               "openai",
               "key_env": "GEMINI_API_KEY",
               "default_model": "gemini-3.8-flash"},
    # deepseek official OpenAI-compatible endpoint; override
    # DEEPSEEK_BASE_URL if routed via a relay
    "deepseek": {"base_url": "https://api.deepseek.com/v1",
                 "key_env": "DEEPSEEK_API_KEY",
                 "default_model": "deepseek-v4.1-flash"},
}

# USD per 1M tokens (input, output) — REFERENCE PRICES for planning; the
# pilot plan doc re-verifies them at approval time and the adapter only
# uses them for accounting, never for billing decisions.
PRICE_TABLE_USD_PER_MTOK = {
    "gpt-4o": (2.50, 10.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    # claude-sonnet-5-5 via zhongkey relay 2026-10-09: $3/$3 per 1M
    # (official output tier is $15 — relay pass-through pricing used for
    # accounting only; billing is whatever the relay actually charges)
    "claude-sonnet-5-5": (3.00, 3.00),
    "glm-4-plus": (0.50, 0.50),
    # glm-5.3 2026-10 quotes diverge (¥1.8/¥2.7 vs ¥8/¥28 per 1M) — use the
    # conservative high quote (≈$1.10/$3.90); billing is per provider bill
    "glm-5.3": (1.10, 3.90),
    "qwen-plus": (0.40, 1.20),
    # deepseek-v4.1-flash: flash tier, priced conservatively high until
    # the first real bill pins it (accounting only, never billing)
    "deepseek-v4.1-flash": (0.50, 2.00),
}
_FALLBACK_PRICE = (3.00, 15.00)


class MockTransport:
    """Deterministic stand-in for the HTTP layer (offline tests only).

    ``script`` is a list of (status, body) replies served in order; the
    last reply repeats.  Records every request for assertions."""

    def __init__(self, script: list[tuple[int, str]]):
        self.script = list(script)
        self._last = (500, "{}")
        self.requests: list[dict] = []

    def __call__(self, method: str, url: str, headers: dict,
                 payload: dict) -> tuple[int, str]:
        self.requests.append({"method": method, "url": url,
                              "headers": dict(headers),
                              "payload": payload})
        if self.script:
            self._last = self.script.pop(0)
        return self._last


def load_dotenv(path: str = ".env") -> int:
    """Load KEY=VALUE lines from ``path`` into os.environ.

    No override of already-set vars, values unquoted, comments/blank lines
    skipped, nothing is ever printed or logged.  Missing file -> 0."""
    if not os.path.isfile(path):
        return 0
    n = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip().strip("'\"")
            if k and v and k not in os.environ:
                os.environ[k] = v
                n += 1
    return n


def _http_transport(method, url, headers, payload, timeout_s):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method=method,
        headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        # socket timeout / DNS / connection reset: status 0 = transient
        # transport failure — caller retries with backoff, never crashes
        return 0, f"transport-error: {e!r}"


class LLMRuleAdapter:
    """Chat-completions client that proposes policy rules as JSON.

    Fail-closed: any transport error, retry exhaustion, or unparsable
    response yields ``None`` (NO rule proposed) — never a guessed rule.
    """

    name = "llm-openai-compat"
    is_llm = True

    def __init__(self, provider: str = "glm", model: str | None = None,
                 enabled: bool = False, transport=None,
                 max_retries: int = 3, timeout_s: float = 30.0,
                 temperature: float = 0.0, max_output_tokens: int = 512,
                 base_url_env: str = "", api_key_env: str = ""):
        preset = PROVIDERS[provider]
        self.provider = provider
        # explicit arg > {PROVIDER}_MODEL env (e.g. GLM_MODEL) > preset
        self.model = (model
                      or os.environ.get(f"{provider.upper()}_MODEL", "")
                      or preset["default_model"])
        # explicit env-name arg > {PROVIDER}_BASE_URL env > preset
        self.base_url = ((os.environ.get(base_url_env, "")
                          if base_url_env else "")
                         or os.environ.get(f"{provider.upper()}_BASE_URL",
                                           "")
                         or preset["base_url"])
        self._api_key = os.environ.get(
            api_key_env or preset["key_env"], "")
        self.enabled = enabled and bool(self._api_key)
        self._explicit_transport = transport is not None
        self.transport = transport or (
            lambda m, u, h, p: _http_transport(m, u, h, p, timeout_s))
        self.max_retries = max_retries
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self._extra_payload = dict(preset.get("extra_payload", {}))
        self.usage = {"calls": 0, "prompt_tokens": 0,
                      "completion_tokens": 0, "retries": 0,
                      "failures": 0}
        self._consec_rate_limited = 0
        self.version = f"{provider}:{self.model}"

    # ------------------------------------------------------------- cost
    def _price(self) -> tuple[float, float]:
        for k, v in PRICE_TABLE_USD_PER_MTOK.items():
            if self.model.startswith(k):
                return v
        return _FALLBACK_PRICE

    def cost_usd(self) -> float:
        pin, pout = self._price()
        return round(self.usage["prompt_tokens"] * pin / 1e6
                     + self.usage["completion_tokens"] * pout / 1e6, 6)

    # ---------------------------------------------------------- transport
    def _chat(self, messages: list[dict]) -> str | None:
        if not self.enabled and not self._explicit_transport:
            # disabled with the DEFAULT (real HTTP) transport: refuse —
            # offline phase must not touch the network.  Explicit test/
            # dry-run transports (MockTransport, stubs) are allowed.
            raise RuntimeError("LLM adapter not enabled (offline phase); "
                               "construct with a MockTransport for tests "
                               "or enabled=True after cost approval")
        payload = {"model": self.model, "messages": messages,
                   "temperature": self.temperature,
                   "max_tokens": self.max_output_tokens}
        payload.update(self._extra_payload)
        headers = {"Content-Type": "application/json",
                   # browser-ish UA: some relays sit behind Cloudflare
                   # rules that 403-ban the default python-urllib
                   # signature (observed: CF error 1010, 2026-10-09)
                   "User-Agent": "Mozilla/5.0 (Windows NT 10.0; "
                                 "Win64; x64)",
                   "Authorization": f"Bearer {self._api_key}"}
        url = f"{self.base_url}/chat/completions"
        delay = 1.0
        for attempt in range(self.max_retries + 1):
            try:
                status, body = self.transport("POST", url, headers,
                                              payload)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                # any transport-level exception (socket timeout, reset,
                # DNS): transient status 0 — retry with backoff below
                status, body = 0, f"transport-error: {e!r}"
            retryable = False
            if status != 200:
                # classify by the business error code in the body (a 429
                # is NOT automatically a rate limit: 1113 "余额不足" also
                # arrives as 429 and waiting/retrying on it is pure waste)
                code, msg = _error_code(body)
                retryable = code in RETRYABLE_CODES
                if (code is not None and not retryable
                        and not (status >= 500 or status <= 0)):
                    raise FatalAPIError(code, msg, status)
            if status == 200:
                try:
                    data = json.loads(body)
                    content = data["choices"][0]["message"]["content"]
                    u = data.get("usage", {})
                except (ValueError, KeyError, IndexError, TypeError):
                    self.usage["failures"] += 1
                    return None          # malformed 200: fail closed
                self.usage["calls"] += 1
                self.usage["prompt_tokens"] += u.get("prompt_tokens", 0)
                self.usage["completion_tokens"] += \
                    u.get("completion_tokens", 0)
                self._consec_rate_limited = 0
                return content
            if not (status == 429 or status >= 500 or status <= 0
                    or retryable):
                # permanent client error (400/401/403/404...): retrying
                # cannot help — fail closed immediately
                self.usage["failures"] += 1
                return None
            # 429 rate limit / 5xx / transport timeout (status<=0):
            # backoff and retry.  429 gets LONG patient delays — a
            # provider-side limiter punishes hammering, and a burned
            # request budget buys nothing.
            self.usage["retries"] += 1
            if status == 429 or retryable:
                # rate limits AND relay locks (409 operation_in_progress)
                # need patient waits — short 1-2 s jabs just burn budget
                delay = min(30.0 * (2 ** attempt), 180.0)
            if attempt == self.max_retries:
                self.usage["failures"] += 1
                if status == 429:
                    # circuit breaker: 3 consecutive turns fully
                    # rate-limited means the limiter is account-wide —
                    # writing more "model behavior" would be fiction.
                    # Raise so the runner stops this cell cleanly.
                    self._consec_rate_limited += 1
                    if self._consec_rate_limited >= 3:
                        raise RateLimited(
                            "provider rate limit persists across "
                            f"{self._consec_rate_limited} turns "
                            "with full backoff")
                return None
            time.sleep(delay)
            delay *= 2
        return None

    # ------------------------------------------------------------ prompt
    PROMPT_TEMPLATE = (
        "You are the policy-learning component of an authorization "
        "system.\nDomain '{domain}': root envelope D admits {env_desc}.\n"
        "Successful exception history (each was individually adjudicated "
        "and executed):\n{history}\nLater request needing authorization: "
        "{probe}\nPropose ONE reusable policy rule as strict JSON with "
        "keys action (string), resource (string, '*' prefix allowed), "
        "conditions (object mapping attribute -> [op, value] with op in "
        "eq/le/ge/any). Reply with the JSON object ONLY.")

    def propose_rule(self, domain, memory, probe) -> dict | None:
        hist = json.dumps([{"request": m["request"], "outcome":
                            m["outcome"]} for m in memory[-5:]],
                          ensure_ascii=False)
        env_desc = json.dumps(
            {"action": domain.case_request["action"],
             "attrs": domain.case_request["attrs"]},
            ensure_ascii=False)
        messages = [
            {"role": "system", "content": "Output a single JSON object."},
            {"role": "user", "content": self.PROMPT_TEMPLATE.format(
                domain=domain.name, env_desc=env_desc, history=hist,
                probe=json.dumps(probe, ensure_ascii=False))}]
        content = self._chat(messages)
        if content is None:
            return None
        try:
            # tolerate markdown fences
            text = content.strip()
            if text.startswith("```"):
                text = text.strip("`").lstrip("json").strip()
            rule = json.loads(text)
        except (ValueError, AttributeError):
            self.usage["failures"] += 1
            return None
        if not (isinstance(rule, dict) and "action" in rule
                and "resource" in rule):
            self.usage["failures"] += 1
            return None
        rule.setdefault("conditions", {})
        return rule
