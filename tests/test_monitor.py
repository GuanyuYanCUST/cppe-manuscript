"""Necessity checker fail-closed semantics + monitor wiring."""
from pguard.monitor import NecessityChecker, ReferenceMonitor

from test_store import make_case, world


def test_necessity_fail_closed():
    nc = NecessityChecker()
    assert nc.check("verified_unsat") == (True, "")
    assert nc.check("sat_witness") == (False, "BETTER_PLAN_EXISTS")
    assert nc.check("unknown") == (False, "UNKNOWN")
    assert nc.check("timeout") == (False, "TIMEOUT")
    assert nc.check("garbage-status") == (False, "UNKNOWN")


def test_necessity_budget_overflow_is_timeout():
    nc = NecessityChecker(budget=2)
    nc.in_flight = 2
    assert nc.check("verified_unsat") == (False, "TIMEOUT")


def test_monitor_gates_admit_case_on_necessity():
    d, st, root, iss = world()
    mon = ReferenceMonitor(st, d, st.keystore, necessity_required=True)
    case = make_case(iss, d)
    st.issue_case(case)
    for status, expected in (("timeout", "NECESSITY_TIMEOUT"),
                             ("sat_witness", "NECESSITY_BETTER_PLAN_EXISTS"),
                             ("unknown", "NECESSITY_UNKNOWN")):
        r = mon.handle_request(d.case_request, case_cert=case,
                               necessity_status=status)
        assert r["decision"] == "DENY" and r["reason"] == expected, r
    # nonce only consumed on success: the verified path still admits
    r = mon.handle_request(d.case_request, case_cert=case,
                           necessity_status="verified_unsat")
    assert r["decision"] == "ADMIT_CASE", r


def test_monitor_latency_fields_present():
    d, st, root, iss = world()
    mon = ReferenceMonitor(st, d, st.keystore)
    r = mon.handle_request(d.case_request)
    assert r["decision"] == "DENY" and r["latency_auth_ms"] >= 0
    r2 = mon.certify_and_install(d.ratchet_rule, None)
    assert r2["guard_decision"] == "REJECT:NO_AUTHORITY"
    assert r2["latency_verify_ms"] >= 0
