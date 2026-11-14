"""LLM adapter unit tests — all through MockTransport, zero network."""
import json
import os
import sys

sys.path.insert(0, str(__file__).rsplit("/tests/", 1)[0] + "/src")

from pguard.llm_adapter import (LLMRuleAdapter, MockTransport,  # noqa: E402
                                load_dotenv)
from pguard.domains import get_domain                     # noqa: E402


def _ok_body(rule_json, ptok=800, ctok=120):
    return json.dumps({
        "choices": [{"message": {"content": rule_json}}],
        "usage": {"prompt_tokens": ptok, "completion_tokens": ctok}})


def _memory(domain):
    return [{"case_id": "C1", "request": domain.case_request,
             "outcome": "success", "cert_kind": "CASE"}]


def test_disabled_adapter_never_reaches_network():
    a = LLMRuleAdapter(provider="glm", enabled=False)
    assert not a.enabled
    try:
        a.propose_rule(get_domain("cloudops"), _memory(
            get_domain("cloudops")), {})
        raised = False
    except RuntimeError:
        raised = True
    assert raised


def test_mock_transport_parses_rule_and_accounts_usage():
    rule = {"action": "attach_role", "resource": "prod-db",
            "conditions": {"incident_active": ["eq", 1]}}
    mt = MockTransport([(200, _ok_body(json.dumps(rule)))])
    a = LLMRuleAdapter(provider="glm", transport=mt)
    d = get_domain("cloudops")
    got = a.propose_rule(d, _memory(d), d.probe_request)
    assert got == rule
    assert a.usage["calls"] == 1
    assert a.usage["prompt_tokens"] == 800
    assert a.usage["completion_tokens"] == 120
    assert a.cost_usd() > 0
    # API key never appears in usage or cost records (skip the vacuous
    # empty-key case)
    assert not a._api_key or a._api_key not in json.dumps(a.usage)
    # request went to the provider's chat endpoint with the model set
    assert mt.requests[0]["url"].endswith("/chat/completions")
    assert mt.requests[0]["payload"]["model"] == a.model
    assert mt.requests[0]["payload"]["temperature"] == 0.0


def test_markdown_fences_tolerated():
    rule = {"action": "attach_role", "resource": "prod-db",
            "conditions": {}}
    mt = MockTransport([(200, _ok_body("```json\n" + json.dumps(rule)
                                       + "\n```"))])
    a = LLMRuleAdapter(provider="qwen", transport=mt)
    d = get_domain("cloudops")
    assert a.propose_rule(d, _memory(d), d.probe_request) == rule


def test_retry_on_429_then_success(monkeypatch):
    monkeypatch.setattr("pguard.llm_adapter.time.sleep",
                        lambda s: None)
    rule = {"action": "attach_role", "resource": "prod-db",
            "conditions": {}}
    mt = MockTransport([(429, "rate limited"),
                        (200, _ok_body(json.dumps(rule)))])
    a = LLMRuleAdapter(provider="glm", transport=mt, max_retries=2)
    d = get_domain("cloudops")
    assert a.propose_rule(d, _memory(d), d.probe_request) == rule
    assert a.usage["retries"] == 1


def test_socket_timeout_retried_then_fail_closed(monkeypatch):
    monkeypatch.setattr("pguard.llm_adapter.time.sleep",
                        lambda s: None)
    import socket

    state = {"n": 0}

    def flaky(method, url, headers, payload):
        state["n"] += 1
        if state["n"] <= 2:
            raise socket.timeout("read timed out")
        return 200, _ok_body(json.dumps(
            {"action": "a", "resource": "r", "conditions": {}}))

    a = LLMRuleAdapter(provider="glm", transport=flaky, max_retries=3)
    d = get_domain("cloudops")
    assert a.propose_rule(d, _memory(d), d.probe_request) is not None
    assert a.usage["retries"] == 2
    # always-timeout transport exhausts retries and fails closed
    def dead(method, url, headers, payload):
        raise socket.timeout("read timed out")
    b = LLMRuleAdapter(provider="glm", transport=dead, max_retries=1)
    assert b.propose_rule(d, _memory(d), d.probe_request) is None
    assert b.usage["failures"] == 1


def test_permanent_4xx_not_retried():
    mt = MockTransport([(400, "bad request")])
    a = LLMRuleAdapter(provider="glm", transport=mt, max_retries=3)
    d = get_domain("cloudops")
    assert a.propose_rule(d, _memory(d), d.probe_request) is None
    assert len(mt.requests) == 1          # one shot, no backoff burns
    assert a.usage["failures"] == 1 and a.usage["retries"] == 0


def test_retry_exhaustion_fails_closed(monkeypatch):
    monkeypatch.setattr("pguard.llm_adapter.time.sleep",
                        lambda s: None)
    mt = MockTransport([(429, "rate limited")])
    a = LLMRuleAdapter(provider="glm", transport=mt, max_retries=1)
    d = get_domain("cloudops")
    assert a.propose_rule(d, _memory(d), d.probe_request) is None
    assert a.usage["failures"] == 1


def test_1113_balance_error_is_fatal_not_rate_limit():
    # the 2026-10-08 incident: 429 + error 1113 (账户已欠费) was retried
    # and waited on as if transient — it must raise immediately instead
    import pytest
    from pguard.llm_adapter import FatalAPIError
    body = json.dumps({"error": {"code": "1113",
                                 "message": "您的账户已欠费，请充值后重试"}})
    mt = MockTransport([(429, body)] * 5)
    a = LLMRuleAdapter(provider="glm", transport=mt, max_retries=3)
    with pytest.raises(FatalAPIError) as ei:
        a._chat([{"role": "user", "content": "x"}])
    assert ei.value.code == "1113" and ei.value.status == 429
    assert len(mt.requests) == 1       # raised on the first response
    assert a.usage["retries"] == 0     # no backoff burned on a fatal code


def test_other_fatal_business_codes_raise(monkeypatch):
    import pytest
    from pguard.llm_adapter import FatalAPIError
    monkeypatch.setattr("pguard.llm_adapter.time.sleep",
                        lambda s: None)
    for code, status in [("1309", 429), ("1313", 429), ("1001", 401),
                         ("1210", 400)]:
        mt = MockTransport([(status, json.dumps(
            {"error": {"code": code, "message": "x"}}))])
        a = LLMRuleAdapter(provider="glm", transport=mt, max_retries=2)
        with pytest.raises(FatalAPIError):
            a._chat([{"role": "user", "content": "x"}])


def test_true_rate_limit_codes_still_back_off(monkeypatch):
    # 1302 (rate limit) / 1305 (overload) / 1308+1310 (windowed quota)
    # are the real transient 429s — keep the backoff-and-fail-closed path
    monkeypatch.setattr("pguard.llm_adapter.time.sleep",
                        lambda s: None)
    for code in ("1302", "1305", "1308", "1310"):
        mt = MockTransport([(429, json.dumps(
            {"error": {"code": code, "message": "x"}}))])
        a = LLMRuleAdapter(provider="glm", transport=mt, max_retries=1)
        assert a._chat([{"role": "user", "content": "x"}]) is None
        assert a.usage["retries"] == 2   # both attempts hit the code


def test_relay_409_operation_in_progress_retries_then_succeeds(monkeypatch):
    # aizex Codex relay: 409 "同一 Codex operation 正在处理中，请稍后…
    # 重试" is transient by its own error text — must back off and
    # recover, not fatal-stop (observed killing the GPT pilot 2026-10-09)
    monkeypatch.setattr("pguard.llm_adapter.time.sleep",
                        lambda s: None)
    mt = MockTransport([
        (409, json.dumps({"error": {"code": "operation_in_progress",
                                    "message": "retry later"}})),
        (200, _ok_body(json.dumps({"action": "a", "resource": "r",
                                   "conditions": {}})))])
    a = LLMRuleAdapter(provider="gpt", transport=mt, max_retries=2)
    assert a._chat([{"role": "user", "content": "x"}]) is not None
    assert a.usage["retries"] == 1 and a.usage["calls"] == 1


def test_invalid_json_fails_closed():
    mt = MockTransport([(200, _ok_body("not json at all"))])
    a = LLMRuleAdapter(provider="gpt", transport=mt)
    d = get_domain("cloudops")
    assert a.propose_rule(d, _memory(d), d.probe_request) is None
    assert a.usage["failures"] == 1


def test_missing_action_resource_rejected():
    mt = MockTransport([(200, _ok_body(json.dumps(
        {"conditions": {}})))])
    a = LLMRuleAdapter(provider="claude", transport=mt)
    d = get_domain("cloudops")
    assert a.propose_rule(d, _memory(d), d.probe_request) is None


def test_price_table_fallback():
    a = LLMRuleAdapter(provider="glm", model="glm-9-future",
                       transport=MockTransport([]))
    assert a._price() == (3.00, 15.00)     # conservative fallback


def test_env_overrides_model_and_base_url(monkeypatch):
    monkeypatch.setenv("GLM_MODEL", "glm-5.3-test")
    monkeypatch.setenv("GLM_BASE_URL", "https://gw.example/v4")
    a = LLMRuleAdapter(provider="glm", transport=MockTransport([]))
    assert a.model == "glm-5.3-test"
    assert a.base_url == "https://gw.example/v4"
    b = LLMRuleAdapter(provider="glm", model="explicit-wins",
                       transport=MockTransport([]))
    assert b.model == "explicit-wins"


def test_reasoning_toggle_only_for_reasoning_providers():
    # glm/qwen payloads disable thinking; gpt/claude get no extra keys
    mt = MockTransport([(200, _ok_body("{}"))])
    LLMRuleAdapter(provider="glm", transport=mt)._chat(
        [{"role": "user", "content": "x"}])
    assert mt.requests[0]["payload"]["thinking"] == {"type": "enabled"}
    assert mt.requests[0]["payload"]["reasoning_effort"] == "low"
    mt2 = MockTransport([(200, _ok_body("{}"))])
    LLMRuleAdapter(provider="qwen", transport=mt2)._chat(
        [{"role": "user", "content": "x"}])
    assert mt2.requests[0]["payload"]["enable_thinking"] is False
    mt3 = MockTransport([(200, _ok_body("{}"))])
    LLMRuleAdapter(provider="gpt", transport=mt3)._chat(
        [{"role": "user", "content": "x"}])
    assert "thinking" not in mt3.requests[0]["payload"]
    assert "enable_thinking" not in mt3.requests[0]["payload"]


def test_load_dotenv_quiet_no_override(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text('# comment\nGLM_API_KEY="sk-abc"\nQWEN_API_KEY=xyz\n'
                 'BADLINE\nGLM_MODEL=glm-5.3\n', encoding="utf-8")
    monkeypatch.setattr(os, "environ", dict(os.environ))
    os.environ.pop("GLM_API_KEY", None)
    os.environ["QWEN_API_KEY"] = "preset-wins"
    n = load_dotenv(str(p))
    assert n == 2
    assert os.environ["GLM_API_KEY"] == "sk-abc"
    assert os.environ["QWEN_API_KEY"] == "preset-wins"   # no override
    assert os.environ["GLM_MODEL"] == "glm-5.3"
