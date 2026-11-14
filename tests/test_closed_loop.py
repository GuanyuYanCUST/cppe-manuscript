"""Closed-loop harness tests — all through MockTransport, zero network."""
import json
import sys
import time

sys.path.insert(0, str(__file__).rsplit("/tests/", 1)[0] + "/src")

from pguard.closed_loop import (Rollout, normalize_candidate,   # noqa: E402
                                replay_method, rule_matches)
from pguard.domains import get_domain                     # noqa: E402
from pguard.llm_adapter import LLMRuleAdapter, MockTransport  # noqa: E402
from pguard.oracle import AuthorizationOracle             # noqa: E402


def _body(content, ptok=600, ctok=80):
    return json.dumps({
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": ptok, "completion_tokens": ctok},
        "model": "glm-5.3"})


def _adapter(script):
    return LLMRuleAdapter(
        provider="glm",
        transport=MockTransport([(200, s) for s in script]),
        max_output_tokens=512)


def _tasks(domain, n=2):
    return [dict(domain.case_request) for _ in range(n)]


def test_closed_loop_case_mode_all_admitted():
    d = get_domain("cloudops")
    calls = json.dumps({"tool_call": dict(
        action=d.case_request["action"],
        resource=d.case_request["resource"],
        attrs=dict(d.case_request["attrs"]))})
    a = _adapter([_body(calls), _body(calls),
                  _body(json.dumps({"mode": "case",
                                    "tool_call": {}}))])
    ro = Rollout(a, d, 0, "episodic", _tasks(d))
    traj = ro.run()
    assert len(traj["turns"]) == 2
    assert all(t["admitted"] and t["state_changed"]
               for t in traj["turns"])
    assert len(traj["memory"]) == 2
    assert all(m["outcome"] == "success" for m in traj["memory"])
    assert traj["final"]["mode"] == "case"
    assert traj["final"]["rule"] is None
    # conversation really is multi-turn: assistant turns + feedback
    kinds = [m["role"] for m in ro.messages]
    assert kinds.count("user") == 5      # 2 tasks + 2 feedbacks + final
    assert kinds.count("assistant") == 3
    assert "Result:" in ro.messages[3]["content"]


def test_closed_loop_bad_attrs_get_failure_feedback():
    d = get_domain("finance")
    bad = json.dumps({"tool_call": {"action": "wire_transfer",
                                    "resource": "acct-vendor",
                                    "attrs": {"urgency": 1}}})
    a = _adapter([_body(bad), _body(json.dumps({"mode": "case"}))])
    ro = Rollout(a, d, 3, "episodic", _tasks(d, 1))
    traj = ro.run()
    t = traj["turns"][0]
    assert not t["admitted"]
    assert t["memory_outcome"] == "failure"
    assert "Result:" in ro.messages[3]["content"]


def test_replay_pg_rejects_out_of_root_b1_installs():
    d = get_domain("cloudops")
    calls = json.dumps({"tool_call": dict(
        action=d.case_request["action"],
        resource=d.case_request["resource"],
        attrs=dict(d.case_request["attrs"]))})
    rule = dict(d.ratchet_rule)          # the canonical out-of-root shape
    a = _adapter([_body(calls), _body(calls),
                  _body(json.dumps({"mode": "precedent",
                                    "rule": rule}))])
    traj = Rollout(a, d, 1, "episodic", _tasks(d)).run()
    assert traj["final"]["rule"] == rule
    pg = replay_method(traj, "PG", atc_resource="prod-api")
    assert pg["proposed"] and pg["attempted"]
    assert not pg["installed"] and pg["reject_reason"] == "OUT_OF_ROOT"
    assert not pg["cppe_issuer"] and not pg["cppe_scope"]
    assert not pg["unauth_effect"]
    b1 = replay_method(traj, "B1", atc_resource="prod-api")
    assert b1["installed"] and b1["cppe_issuer"]
    assert b1["cppe_scope"]               # F-C2 fix: ratchet escapes D
    assert b1["unauth_effect"]            # ratchet admits the probe
    assert b1["n_covered_out_of_D"] > 0


def test_replay_pg_installs_contained_and_serves():
    d = get_domain("cloudops")
    calls = json.dumps({"tool_call": dict(
        action=d.case_request["action"],
        resource=d.case_request["resource"],
        attrs=dict(d.case_request["attrs"]))})
    rule = dict(d.positive_rule)
    a = _adapter([_body(calls), _body(calls),
                  _body(json.dumps({"mode": "precedent",
                                    "rule": rule}))])
    traj = Rollout(a, d, 2, "episodic", _tasks(d)).run()
    pg = replay_method(traj, "PG", atc_resource="prod-api")
    assert pg["installed"] and not pg["cppe_issuer"]
    assert not pg["cppe_scope"] and not pg["unauth_effect"]
    assert pg["valid_accepted"]           # serves the case request
    assert pg["atc_done"]
    b0 = replay_method(traj, "B0", atc_resource="prod-api")
    assert not b0["attempted"] and b0["reject_reason"] == "IMMUTABLE_STORE"


def test_replay_k_truncation_and_no_success_no_proposal():
    d = get_domain("cloudops")
    bad = json.dumps({"tool_call": {"action": "attach_role",
                                    "resource": "prod-db",
                                    "attrs": {}}})
    a = _adapter([_body(bad), _body(json.dumps({"mode": "precedent",
                                                "rule": d.ratchet_rule}))])
    traj = Rollout(a, d, 5, "episodic", _tasks(d, 1)).run()
    row = replay_method(traj, "B1")
    assert not row["proposed"]            # zero successes -> no learning
    # k truncation on a successful history
    calls = json.dumps({"tool_call": dict(
        action=d.case_request["action"],
        resource=d.case_request["resource"],
        attrs=dict(d.case_request["attrs"]))})
    a = _adapter([_body(calls)] * 3 +
                 [_body(json.dumps({"mode": "precedent",
                                    "rule": d.positive_rule}))])
    traj = Rollout(a, d, 6, "episodic", _tasks(d, 3)).run()
    for k in (0, 1, 3):
        row = replay_method(traj, "B1", k=k)
        assert row["k"] == k
        assert row["proposed"] == (k >= 1)


def test_replay_survives_expired_wall_clock():
    """Frozen trajectories older than the 30-min CASE TTL must replay:
    the world clock is anchored to the trajectory's own issuance time."""
    d = get_domain("cloudops")
    calls = json.dumps({"tool_call": dict(
        action=d.case_request["action"],
        resource=d.case_request["resource"],
        attrs=dict(d.case_request["attrs"]))})
    a = _adapter([_body(calls), _body(calls),
                  _body(json.dumps({"mode": "precedent",
                                    "rule": d.positive_rule}))])
    traj = Rollout(a, d, 7, "episodic", _tasks(d)).run()
    old = time.time() - 4000.0
    for m in traj["memory"]:
        if "case_cert" in m:
            c = m["case_cert"]
            c["expires_at"] -= 4000.0   # now long past its live TTL
            c["sig"] = None             # would fail any re-sign scheme
    # sig=None breaks verification on purpose: the anchored path must
    # not need fresh signing — restore real sigs, keep stale times
    for m in traj["memory"]:
        if "case_cert" in m:
            m["case_cert"]["sig"] = None
    # rebuild properly signed certs with stale issued/expires times
    from pguard import certs as C
    from pguard.baselines import MethodWorld
    holder = MethodWorld("PG", d, 7)
    for m in traj["memory"]:
        if "case_cert" in m:
            c = m["case_cert"]
            body = {k: v for k, v in c.items()
                    if k not in ("sig", "issuer")}
            body["issued_at"] = old
            body["expires_at"] = old + 1800.0
            m["case_cert"] = C.sign_cert(body, holder.case_issuer)
    row = replay_method(traj, "PG", atc_resource="prod-api")
    assert row["installed"] and not row["unauth_effect"]


def test_rule_matches_agrees_with_oracle():
    d = get_domain("finance")
    o = AuthorizationOracle(d, None, "root")
    for rule in (d.ratchet_rule, d.positive_rule,
                 {"action": "*", "resource": "*", "conditions": {}}):
        covered_out = [x for x in d.universe
                       if rule_matches(rule, x)
                       and not d.in_envelope(x)]
        assert o.rule_contained(rule)[0] == (not covered_out)


def test_normalize_coerce_sensitivity_variant():
    """coerce=True losslessly converts numeric-string bounds only; the
    default path keeps them verbatim-strict (fail-closed)."""
    from pguard.closed_loop import normalize_candidate
    r = {"action": "attach_role", "resource": "prod-db",
         "conditions": {"ttl_min": ["le", "30"], "role_tier": ["eq", "1"],
                        "purpose": ["eq", "availability"]}}
    strict, why = normalize_candidate(r)
    assert why is None
    assert strict["conditions"]["ttl_min"] == ["le", "30"]   # verbatim
    coerced, why = normalize_candidate(r, coerce=True)
    assert why is None
    assert coerced["conditions"]["ttl_min"] == ["le", 30]
    assert coerced["conditions"]["role_tier"] == ["eq", 1]
    assert coerced["conditions"]["purpose"] == ["eq", "availability"]
    # non-numeric strings and invented syntax untouched / still rejected
    r2 = {"action": "attach_role", "resource": "prod-db",
          "conditions": {"any": ["any", "a", "b"]}}
    assert normalize_candidate(r2, coerce=True)[0] is None


def test_atc_probe_runs_without_proposal():
    """ATC must not be gated on the agent proposing: case-only agents
    (mode=case, rule=None) and malformed proposals still get the ATC
    probe — the delegated task either completes or it doesn't."""
    d = get_domain("cloudops")
    calls = json.dumps({"tool_call": dict(
        action=d.case_request["action"],
        resource=d.case_request["resource"],
        attrs=dict(d.case_request["attrs"]))})
    # case-only final
    a = _adapter([_body(calls), _body(calls),
                  _body(json.dumps({"mode": "case", "tool_call": {}}))])
    traj = Rollout(a, d, 8, "episodic", _tasks(d)).run()
    pg = replay_method(traj, "PG", atc_resource="prod-api")
    assert not pg["proposed"] and not pg["installed"]
    assert pg["atc_done"] and pg["atc_via_case"]
    # malformed rule final (invented syntax -> normalize fail)
    a = _adapter([_body(calls), _body(calls),
                  _body(json.dumps({"mode": "precedent",
                                    "rule": {"action": "attach_role",
                                             "resource": "prod-db",
                                             "conditions":
                                                 {"any": ["a", "b"]}}}))])
    traj = Rollout(a, d, 9, "episodic", _tasks(d)).run()
    pg = replay_method(traj, "PG", atc_resource="prod-api")
    assert pg["proposed"] and not pg["installed"]
    assert "MALFORMED" in pg["reject_reason"]
    assert pg["atc_done"] and pg["atc_via_case"]


def test_parse_obj_strips_inlined_think_blocks():
    # GPT-5.6 via Codex relay inlines "<think>...</think>" before the
    # JSON (GLM puts reasoning in a separate field); the payload after
    # the block must parse, truncated-think replies must stay None
    from pguard.closed_loop import _parse_obj
    ok = ('<think>**Choosing** stuff</think>\n{"mode":"case",'
          '"tool_call":{"action":"wire_transfer","resource":"acct",'
          '"attrs":{"amount_usd":1000}}}')
    assert _parse_obj(ok)["mode"] == "case"
    fenced = '<think>hmm</think>\n```json\n{"a": 1}\n```'
    assert _parse_obj(fenced) == {"a": 1}
    truncated = "<think>ran out of budget mid-reasoning and never "
    assert _parse_obj(truncated) is None
    assert _parse_obj(None) is None and _parse_obj("") is None


def test_parse_obj_extracts_json_with_trailing_prose():
    # claude-sonnet-5-5 appends prose after the object (2026-10-09 pilot:
    # '{...}\n\nI' — cut mid-sentence); the prefix object must parse and
    # prose-before-json too, while a lone unbalanced object stays None
    from pguard.closed_loop import _parse_obj
    trailing = ('{"mode": "case", "tool_call": {"action": "attach_role"}}'
                "\n\nI'll keep this conservative")
    assert _parse_obj(trailing)["mode"] == "case"
    lead = "Sure, here it is:\n" + trailing
    assert _parse_obj(lead)["mode"] == "case"
    assert _parse_obj("{\"a\": {") is None
    assert _parse_obj('{"a": "has } brace"} tail')["a"] == "has } brace"


def test_tool_call_numeric_strings_coerced():
    # claude-sonnet-5-5 emits numbers as JSON strings ("ttl_min": "30");
    # the sandbox must admit the coerced call, and rule conditions stay
    # verbatim (never coerced)
    from pguard.closed_loop import _coerce_attrs
    a = _coerce_attrs({"incident_active": "1", "ttl_min": "30",
                       "purpose": "availability", "ratio": "1.5",
                       "ver": "v2", "note": "-"})
    assert a == {"incident_active": 1, "ttl_min": 30,
                 "purpose": "availability", "ratio": 1.5,
                 "ver": "v2", "note": "-"}
    d = get_domain("cloudops")
    calls = json.dumps({"tool_call": {
        "action": d.case_request["action"],
        "resource": d.case_request["resource"],
        "attrs": {k: str(v) for k, v in d.case_request["attrs"].items()}}})
    a2 = _adapter([_body(calls), _body(calls),
                   _body(json.dumps({"mode": "case"}))])
    traj = Rollout(a2, d, 8, "episodic", _tasks(d)).run()
    assert all(t["admitted"] and t["state_changed"]
               for t in traj["turns"])


def test_normalize_candidate_fail_closed():
    # invented membership syntax (seen from the real model) -> rejected
    r, why = normalize_candidate(
        {"action": "wire_transfer", "resource": "acct-vendor",
         "conditions": {"account_type": ["any", "internal", "partner"]}})
    assert r is None and "account_type" in why
    # string-typed bound kept verbatim (matches nothing; never coerced)
    r, _ = normalize_candidate(
        {"action": "a", "resource": "*", "conditions":
         {"tier": ["eq", "1"]}})
    assert r["conditions"]["tier"] == ["eq", "1"]
    # canonical rule passes through with defaults filled
    r, why = normalize_candidate({"conditions": {"x": ["le", 3]}})
    assert r == {"action": "*", "resource": "*",
                 "conditions": {"x": ["le", 3]}} and why is None


def test_ord_ok_incomparable_types_fail_closed():
    from pguard.oracle import ord_ok
    assert ord_ok(30, "le", 30) and ord_ok(29, "le", 30)
    assert not ord_ok(31, "le", 30) and not ord_ok(29, "ge", 30)
    # string bound from LLM-typed rule: incomparable => NOT satisfied
    assert ord_ok(30, "le", "30") is False
    assert ord_ok(30, "ge", "30") is False
