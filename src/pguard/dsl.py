"""Candidate-rule DSL and containment checking for the four security
domains.

A rule is a conjunction over request attributes::

    {"action": str, "resource": pattern, "conditions": {attr: [op, value]}}

with ``op`` in {"eq","le","ge","any"} and ``resource`` an exact name, a
``"prefix*"`` glob, or ``"*"``.  Requests are tuples
``{"action", "resource", "attrs": {...}}`` drawn from each domain's finite
universe ``U``.  Containment ``[[r]] ⊆ D`` is decided exactly by
enumeration over ``U`` (sound and complete for these finite domains — the
same decision procedure the prior draft used for DSL-B).  The Independent
Authorization Oracle (oracle.py) re-implements this check independently so
the monitor's verdict and the ground truth are cross-validated in tests.
"""
from __future__ import annotations

import hashlib
import itertools
import json


def resource_match(pattern: str, resource: str) -> bool:
    if pattern == "*" or pattern == resource:
        return True
    if pattern.endswith("*"):
        return resource.startswith(pattern[:-1])
    return False


def cond_holds(cond, value) -> bool:
    op, bound = cond[0], cond[1]
    if op == "any":
        return True
    if value is None:
        return False
    if op == "eq":
        return value == bound
    if op == "le":
        try:
            return value <= bound
        except TypeError:  # incomparable (int value vs str bound from an
            return False   # LLM rule ["le","30"]) — never holds, fail-closed
    if op == "ge":
        try:
            return value >= bound
        except TypeError:
            return False
    raise ValueError(f"unknown op {op!r}")


def rule_matches(rule: dict, request: dict) -> bool:
    if rule.get("action", "*") != "*" and rule["action"] != request["action"]:
        return False
    if not resource_match(rule.get("resource", "*"), request["resource"]):
        return False
    for attr, cond in rule.get("conditions", {}).items():
        if not cond_holds(cond, request["attrs"].get(attr)):
            return False
    return True


def rule_hash(rule: dict) -> str:
    return hashlib.sha256(
        json.dumps(rule, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]


def containment(rule: dict, envelope, universe) -> tuple[bool, dict | None]:
    """Exact containment over the finite universe.

    Returns (contained, witness_request_outside_D).
    """
    for x in universe:
        if rule_matches(rule, x) and not envelope(x):
            return False, x
    return True, None


def denotation(rule: dict, universe) -> list[dict]:
    return [x for x in universe if rule_matches(rule, x)]


def excess_volume(rule: dict, envelope, universe) -> float:
    """EAV: fraction of the universe covered by the rule but outside D."""
    n = len(universe)
    if n == 0:
        return 0.0
    bad = sum(1 for x in universe
              if rule_matches(rule, x) and not envelope(x))
    return bad / n


def build_universe(actions, resources, attr_grid: dict) -> list[dict]:
    """Cross product of actions x resources x attribute grid."""
    keys = sorted(attr_grid)
    uni = []
    for action in actions:
        for resource in resources:
            for values in itertools.product(*(attr_grid[k] for k in keys)):
                uni.append({"action": action, "resource": resource,
                            "attrs": dict(zip(keys, values))})
    return uni
