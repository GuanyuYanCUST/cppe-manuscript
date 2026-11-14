"""DSL-A / DSL-B formal containment verifiers and independent oracles (E8).

Semantics follow the prior draft's Appendix A exactly:

DSL-A (monotone threshold, "energy reserve"):
    D_A(u,a,r) = min(4, (u+a+2r)//4),  u,a in [0,7], r in {0,1}.
    Rule = (U, A, r_req, Dmax): admits a deviation iff u>=U and a>=A and
    (r=1 if r_req) and d<=Dmax.  The rule is contained iff EVERY evidence
    point it admits has D_A >= Dmax — i.e. the allowed deviation never
    exceeds the level the envelope justifies.  Monotone in u,a,r, so the
    *verifier* checks only the least-favorable point (U, A, r_min); the
    *oracle* re-decides by full enumeration.

DSL-B (non-monotone disjunctive, "containment/evacuation"):
    D_B = (smoke & pressureStable & tox<=6) | (evac & backupVent & tox<=8)
    over booleans smoke/ps/evac/backup and integer tox in [0,10]
    (16 x 11 = 176 points).  A rule is a finite disjunction of conjunctive
    clauses {var: 0/1/None, tox_bound}; contained iff every point matching
    any clause satisfies D_B.  Both verifier and oracle enumerate the
    bounded domain, with structurally independent matchers/envelopes.

Ratcheting moves (adversarial generalizer, Appendix A):
    DSL-A seed (U=6, A=6, r_req=True, Dmax=3); moves: lower urgency,
    lower scarcity, drop reversibility, increase deviation, unchanged.
    DSL-B seed single clause (smoke=1, ps=1, tox<=3); moves: raise tox
    bound, drop smoke, drop ps, add evac clause (evac=1, backup=1,
    tox<=8; idempotent), unchanged.
"""
from __future__ import annotations

import itertools

# ----------------------------------------------------------------- DSL-A
A_U_MAX = 7          # u,a in [0,7]
A_LEVEL_CAP = 4


def a_level(u: int, a: int, r: int) -> int:
    return min(A_LEVEL_CAP, (u + a + 2 * r) // 4)


def a_rule_contains(rule) -> tuple[bool, tuple | None]:
    """Verifier: extremal-point check (monotone shortcut)."""
    U, A, r_req, Dmax = rule
    r_lf = 1 if r_req else 0
    if a_level(U, A, r_lf) >= Dmax:
        return True, None
    return False, (U, A, r_lf)


def a_oracle_contains(rule) -> tuple[bool, tuple | None]:
    """Independent oracle: full enumeration, no monotonicity shortcut."""
    U, A, r_req, Dmax = rule
    for u in range(0, A_U_MAX + 1):
        if u < U:
            continue
        for a in range(0, A_U_MAX + 1):
            if a < A:
                continue
            for r in ({1} if r_req else (0, 1)):
                if a_level(u, a, r) < Dmax:
                    return False, (u, a, r)
    return True, None


A_SEED = (6, 6, True, 3)
A_MOVES = ("lower_urgency", "lower_scarcity", "drop_reversibility",
           "increase_deviation", "unchanged")


def a_move(rule: tuple, i: int) -> tuple:
    U, A, r_req, Dmax = rule
    if i == 0:
        return (max(0, U - 1), A, r_req, Dmax)
    if i == 1:
        return (U, max(0, A - 1), r_req, Dmax)
    if i == 2:
        return (U, A, False, Dmax)
    if i == 3:
        return (U, A, r_req, Dmax + 1)
    return rule


# ----------------------------------------------------------------- DSL-B
B_BOOLS = ("smoke", "pressureStable", "evac", "backupVent")
B_TOX_MAX = 10
B_POINTS = tuple(itertools.product((0, 1), repeat=4))   # 16


def b_envelope(point_bits: tuple, tox: int) -> bool:
    smoke, ps, evac, backup = point_bits
    return (smoke == 1 and ps == 1 and tox <= 6) or \
           (evac == 1 and backup == 1 and tox <= 8)


def _clause_matches(clause, point_bits: tuple, tox: int) -> bool:
    for var, val in zip(B_BOOLS, point_bits):
        want = clause.get(var)
        if want is not None and want != val:
            return False
    return tox <= clause["tox_bound"]


def b_rule_contains(rule) -> tuple[bool, tuple | None]:
    """Verifier: exhaustive enumeration over the 176-point domain."""
    for point_bits in B_POINTS:
        for tox in range(0, B_TOX_MAX + 1):
            if any(_clause_matches(cl, point_bits, tox) for cl in rule):
                if not b_envelope(point_bits, tox):
                    return False, (point_bits, tox)
    return True, None


def b_oracle_contains(rule) -> tuple[bool, tuple | None]:
    """Independent oracle: integer-encoded truth table, structurally
    different matcher (explicit loop-and-flag instead of any())."""
    for idx in range(176):
        tox = idx % 11
        bits_idx = idx // 11
        smoke = (bits_idx >> 3) & 1
        ps = (bits_idx >> 2) & 1
        evac = (bits_idx >> 1) & 1
        backup = bits_idx & 1
        matched = False
        for cl in rule:
            ok = True
            if cl.get("smoke") is not None and cl["smoke"] != smoke:
                ok = False
            if ok and cl.get("pressureStable") is not None \
                    and cl["pressureStable"] != ps:
                ok = False
            if ok and cl.get("evac") is not None and cl["evac"] != evac:
                ok = False
            if ok and cl.get("backupVent") is not None \
                    and cl["backupVent"] != backup:
                ok = False
            if ok and tox > cl["tox_bound"]:
                ok = False
            if ok:
                matched = True
                break
        if not matched:
            continue
        branch1 = smoke == 1 and ps == 1 and tox <= 6
        branch2 = evac == 1 and backup == 1 and tox <= 8
        if not (branch1 or branch2):
            return False, ((smoke, ps, evac, backup), tox)
    return True, None


B_SEED = ({"smoke": 1, "pressureStable": 1, "tox_bound": 3},)
B_EVAC_CLAUSE = {"evac": 1, "backupVent": 1, "tox_bound": 8}
B_MOVES = ("raise_tox_bound", "drop_smoke", "drop_pressure_stable",
           "add_evac_clause", "unchanged")


def b_move(rule: tuple, i: int) -> tuple:
    clauses = [dict(c) for c in rule]
    if i == 0:
        clauses[0]["tox_bound"] += 1
    elif i == 1:
        clauses[0].pop("smoke", None)
    elif i == 2:
        clauses[0].pop("pressureStable", None)
    elif i == 3:
        if B_EVAC_CLAUSE not in clauses:
            clauses.append(dict(B_EVAC_CLAUSE))
    return tuple(clauses)


# ------------------------------------------------------- mutated verifiers
# Each mutant breaks exactly one assumption; the differential test must
# catch every one of them (实验计划 E8 mutation-testing requirement).
def mutant_a_strict_inequality(rule):
    """`<`/`<=` confusion: requires level > Dmax instead of >=."""
    U, A, r_req, Dmax = rule
    return (a_level(U, A, 1 if r_req else 0) > Dmax, None)


def mutant_a_scope_widening(rule):
    """Envelope quietly widened one notch (every level +1).  Note: simply
    raising the cap 4->5 is a semantic no-op on this universe (u,a<=7
    bounds every level at 4), so the mutant widens the level itself."""
    U, A, r_req, Dmax = rule
    level = min(A_LEVEL_CAP, (U + A + 2 * (1 if r_req else 0)) // 4) + 1
    return (level >= Dmax, None)


def mutant_b_missing_conjunct(rule):
    """D_B' drops pressureStable from branch 1 (accepts unsafe rules)."""
    for point_bits in B_POINTS:
        for tox in range(0, B_TOX_MAX + 1):
            if any(_clause_matches(cl, point_bits, tox) for cl in rule):
                smoke, ps, evac, backup = point_bits
                ok = (smoke == 1 and tox <= 6) or \
                     (evac == 1 and backup == 1 and tox <= 8)
                if not ok:
                    return False, (point_bits, tox)
    return True, None


def mutant_b_wrong_disjunction(rule):
    """D_B' = branch1 AND branch2 (conjunction): over-strict, false rejects."""
    for point_bits in B_POINTS:
        for tox in range(0, B_TOX_MAX + 1):
            if any(_clause_matches(cl, point_bits, tox) for cl in rule):
                smoke, ps, evac, backup = point_bits
                ok = (smoke == 1 and ps == 1 and tox <= 6) and \
                     (evac == 1 and backup == 1 and tox <= 8)
                if not ok:
                    return False, (point_bits, tox)
    return True, None


def mutant_b_tox_strict(rule):
    """`<=`/`<` confusion inside the clause matcher."""
    for point_bits in B_POINTS:
        for tox in range(0, B_TOX_MAX + 1):
            for cl in rule:
                m = True
                for var, val in zip(B_BOOLS, point_bits):
                    want = cl.get(var)
                    if want is not None and want != val:
                        m = False
                if m and tox < cl["tox_bound"]:
                    if not b_envelope(point_bits, tox):
                        return False, (point_bits, tox)
                    break
    return True, None


MUTANTS = {
    "a_strict_inequality": (mutant_a_strict_inequality, "A"),
    "a_scope_widening": (mutant_a_scope_widening, "A"),
    "b_missing_conjunct": (mutant_b_missing_conjunct, "B"),
    "b_wrong_disjunction": (mutant_b_wrong_disjunction, "B"),
    "b_tox_strict": (mutant_b_tox_strict, "B"),
}
