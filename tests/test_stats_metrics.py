"""Exact statistics sanity (hand-checked values)."""
from pguard.metrics import summarize_arm
from pguard.stats import clopper_pearson_upper_zero, percentiles, wilson


def test_wilson_zero_over_ten():
    lo, hi = wilson(0, 10)
    assert lo == 0.0
    assert abs(hi - 0.2775) < 5e-4      # hand-computed 0.27748


def test_wilson_known_proportion():
    lo, hi = wilson(500, 1000)
    assert abs(lo - 0.4691) < 5e-4 and abs(hi - 0.5309) < 5e-4


def test_cp_upper_zero_matches_published_pilot_bound():
    # prior draft reported 0/500 -> upper 0.735%
    assert abs(clopper_pearson_upper_zero(500) - 0.007351) < 2e-6


def test_percentiles_interpolates():
    p = percentiles([1, 2, 3, 4], ps=(50,))
    assert abs(p[50] - 2.5) < 1e-9


def test_summarize_arm_counts(tmp_path):
    ev = [
        {"arm": "A", "event": "RULE_PROPOSED", "candidate_unsafe": True},
        {"arm": "A", "event": "INSTALL_ATTEMPT",
         "guard_decision": "REJECT:NO_AUTHORITY"},
        {"arm": "A", "event": "TOOL_EFFECT",
         "tool_effect": {"unauthorized": False}},
        {"arm": "B", "event": "TOOL_EFFECT",
         "tool_effect": {"unauthorized": False}},
    ]
    s = summarize_arm(ev, "A")
    assert s["UPR"]["k"] == 1 and s["UPR"]["n"] == 1
    assert s["UIR"]["k"] == 0 and s["UIR"]["n"] == 1
    assert s["UER"]["k"] == 0 and s["UER"]["n"] == 1
    assert summarize_arm(ev, "B")["UPR"]["n"] == 0
    assert summarize_arm(ev, "Z")["events"] == 0
