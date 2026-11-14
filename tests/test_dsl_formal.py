"""E8 formal-DSL tests: exact semantics, absorbing property, differential
zero-mismatch, and mutation catching."""
import pytest

from pguard.dsl_formal import (
    A_SEED, B_SEED, MUTANTS, a_move, a_oracle_contains, a_rule_contains,
    b_move, b_oracle_contains, b_rule_contains)

from experiments.e8_dsl_stress import (
    differential, grid_corpus, reachable_states)


def test_dsl_a_seed_contained_and_hand_checked_levels():
    assert a_rule_contains(A_SEED) == (True, None)
    assert a_rule_contains((6, 6, True, 4))[0] is False   # d↑ unsafe
    assert a_rule_contains((5, 6, True, 3))[0] is True    # 13/4 -> 3
    assert a_rule_contains((6, 6, False, 3))[0] is True   # 12/4 -> 3
    assert a_rule_contains((6, 6, False, 3)) == a_oracle_contains((6, 6, False, 3))


def test_dsl_b_seed_and_l1_moves():
    assert b_rule_contains(B_SEED) == (True, None)
    assert b_rule_contains(b_move(B_SEED, 0))[0] is True    # tox 3->4
    assert b_rule_contains(b_move(B_SEED, 1))[0] is False   # drop smoke
    assert b_rule_contains(b_move(B_SEED, 2))[0] is False   # drop ps
    assert b_rule_contains(b_move(B_SEED, 3))[0] is True    # evac clause


@pytest.mark.parametrize("dsl", ["A", "B"])
def test_unsafe_states_absorbing(dsl):
    """Moves only loosen rules, so once unsafe always unsafe — the
    premise that makes end-state counting equal ever-installed counting."""
    for rule in reachable_states(dsl):
        if not (a_rule_contains(rule)[0] if dsl == "A"
                else b_rule_contains(rule)[0]):
            for m in range(5):
                r2 = (a_move(rule, m) if dsl == "A" else b_move(rule, m))
                assert not (a_rule_contains(r2)[0] if dsl == "A"
                            else b_rule_contains(r2)[0]), (rule, m)


@pytest.mark.parametrize("dsl", ["A", "B"])
def test_verifier_vs_oracle_zero_mismatch(dsl):
    diff = differential(dsl)
    assert diff["mismatch_count"] == 0
    assert diff["corpus_size"] > diff["reachable_states"]  # grid superset


def test_published_l1_l2_l3_exact_fractions():
    from experiments.e8_dsl_stress import enumerate_histories
    for dsl, expect in (("A", {1: 1, 2: 13, 3: 99}),
                        ("B", {1: 2, 2: 16, 3: 98})):
        rows, _, _ = enumerate_histories(dsl)
        for row in rows:
            if row["length"] in expect:
                assert row["reuse_unsafe"] == expect[row["length"]], \
                    (dsl, row)


def test_every_mutant_is_caught():
    for name, (fn, dsl) in MUTANTS.items():
        corpus = reachable_states(dsl) + grid_corpus(dsl)
        mismatches = sum(
            1 for rule in corpus if fn(rule)[0] !=
            (a_oracle_contains(rule)[0] if dsl == "A"
             else b_oracle_contains(rule)[0]))
        assert mismatches > 0, f"mutation {name} not caught"


def test_certificate_mutants_via_store():
    from experiments.e8_dsl_stress import mutation_testing
    res = mutation_testing()
    assert res["stale_root_version"]["caught"]
    assert res["bad_issuer"]["caught"]
