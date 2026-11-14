"""DSL semantics + differential test: monitor's containment vs the
independent oracle's containment must agree on every domain/rule pair."""
from pguard.crypto import KeyStore, Principal
from pguard.domains import DOMAINS, get_domain
from pguard.dsl import build_universe, containment, denotation, rule_matches
from pguard.oracle import AuthorizationOracle


def _rule_variants(d):
    return [
        d.ratchet_rule,
        d.positive_rule,
        {"action": "*", "resource": "*", "conditions": {}},      # everything
        {"action": d.case_request["action"],
         "resource": d.case_request["resource"],
         "conditions": {}},                                       # whole object
        {"action": d.case_request["action"],
         "resource": "nonexistent-*", "conditions": {}},          # empty rule
    ]


def test_ratchet_escapes_and_positive_is_contained_every_domain():
    for name in DOMAINS:
        d = get_domain(name)
        assert not containment(d.ratchet_rule, d.in_envelope,
                               d.universe)[0], name
        assert containment(d.positive_rule, d.in_envelope,
                           d.universe)[0], name


def test_oracle_vs_dsl_containment_differential():
    ks = KeyStore()
    ks.add(Principal("root", "root", 0))
    for name in DOMAINS:
        d = get_domain(name)
        orc = AuthorizationOracle(d, ks, "root")
        for rule in _rule_variants(d):
            assert containment(rule, d.in_envelope, d.universe)[0] == \
                orc.rule_contained(rule)[0], (name, rule)


def test_rule_matches_ops():
    d = get_domain("cloudops")
    r = d.ratchet_rule
    assert rule_matches(r, {"action": "attach_role", "resource": "prod-db",
                            "attrs": {"role_tier": 2, "ttl_min": 1440}})
    assert not rule_matches(r, {"action": "attach_role",
                                "resource": "staging-api", "attrs": {}})
    fin = get_domain("finance")
    assert rule_matches(fin.ratchet_rule, {
        "action": "wire_transfer", "resource": "acct-payroll",
        "attrs": {"amount_usd": 1000000, "account_type": "external"}})


def test_universe_sizes_exact():
    d = get_domain("cloudops")
    # 4 actions x 3 resources x (2*2*3*4*2 attr combos) = 1152
    assert len(d.universe) == 1152
    assert len(build_universe(["a"], ["r"], {"x": [1], "y": [1, 2]})) == 2


def test_denotation_subset_relation():
    d = get_domain("cloudops")
    den = denotation(d.positive_rule, d.universe)
    assert den and all(d.in_envelope(x) for x in den)
