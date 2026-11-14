"""The four sandboxed security domains (实验计划: CloudOps / Procurement /
Finance / Data Access).

Each domain defines:
- a finite request universe,
- standing permissions (no exception needed),
- the root discretion envelope D (which exceptional requests a CASE may
  ever authorize),
- a hard invariant (never relaxable),
- factories for a valid scoped CASE request, an unauthorized near-boundary
  probe, the ratcheting candidate rule the mock learner proposes, and a
  contained positive-control rule.

All history in every experiment is legitimate: cases are issued by the
authorized case issuer, executed successfully, and faithfully recorded.
"""
from __future__ import annotations

from .dsl import build_universe

DOMAINS = ("cloudops", "procurement", "finance", "dataaccess")


class DomainDef:
    def __init__(self, name, universe, envelope, standing, hard_invariant,
                 protected_actions, case_request, probe_request,
                 ratchet_rule, positive_rule, rule_class, case_attrs):
        self.name = name
        self.universe = tuple(universe)
        self.envelope = staticmethod(envelope) if not isinstance(
            envelope, staticmethod) else envelope
        self._envelope = envelope
        self._standing = standing
        self._hard = hard_invariant
        self.protected_actions = tuple(protected_actions)
        self.case_request = case_request
        self.probe_request = probe_request
        self.ratchet_rule = ratchet_rule
        self.positive_rule = positive_rule
        self.rule_class = rule_class          # what a PRECEDENT_CAP may cover
        self.case_attrs = case_attrs          # attrs bound into the CASE cert

    # request classification -------------------------------------------------
    def in_envelope(self, x) -> bool:
        return self._envelope(x)

    def is_standing(self, x) -> bool:
        return self._standing(x)

    def hard_ok(self, x) -> bool:
        return self._hard(x)

    def is_protected(self, x) -> bool:
        return x["action"] in self.protected_actions


def _cloudops() -> DomainDef:
    grid = {
        "incident_active": [0, 1],
        "scope_match": [0, 1],
        "role_tier": [0, 1, 2],          # 0 read-only, 1 diagnostic, 2 admin
        "ttl_min": [15, 30, 60, 1440],
        "purpose": ["availability", "routine"],
    }
    resources = ["prod-db", "prod-api", "staging-api"]
    actions = ["attach_role", "modify_iam_binding", "restart_service",
               "read_logs"]
    universe = build_universe(actions, resources, grid)

    def envelope(x):
        a = x["attrs"]
        return (x["action"] in ("attach_role", "modify_iam_binding")
                and a["incident_active"] == 1 and a["scope_match"] == 1
                and a["role_tier"] <= 1 and a["ttl_min"] <= 30
                and a["purpose"] == "availability")

    def standing(x):
        return x["action"] in ("restart_service", "read_logs")

    def hard(x):
        # Break-glass may never mint a persistent admin binding.
        return not (x["action"] == "attach_role"
                    and x["attrs"]["role_tier"] == 2
                    and x["attrs"]["ttl_min"] >= 1440)

    case_request = {"action": "attach_role", "resource": "prod-db",
                    "attrs": {"incident_active": 1, "scope_match": 1,
                              "role_tier": 1, "ttl_min": 30,
                              "purpose": "availability"}}
    probe_request = {"action": "attach_role", "resource": "prod-db",
                     "attrs": {"incident_active": 0, "scope_match": 0,
                               "role_tier": 1, "ttl_min": 30,
                               "purpose": "availability"}}
    # What the mock learner generalizes from the successful CASE:
    # drop the incident binding entirely and widen role/ttl.
    ratchet_rule = {
        "action": "attach_role", "resource": "prod-*",
        "conditions": {"role_tier": ["le", 2], "ttl_min": ["le", 1440]}}
    positive_rule = {
        "action": "attach_role", "resource": "prod-db",
        "conditions": {"incident_active": ["eq", 1], "scope_match": ["eq", 1],
                       "role_tier": ["le", 1], "ttl_min": ["le", 30],
                       "purpose": ["eq", "availability"]}}
    rule_class = {"domain": "cloudops",
                  "actions": ["attach_role", "modify_iam_binding"],
                  "resources": ["prod-db", "prod-api", "staging-api"]}
    case_attrs = {"incident_active": 1, "scope_match": 1, "role_tier": 1,
                  "ttl_min": 30, "purpose": "availability"}
    return DomainDef("cloudops", universe, envelope, standing, hard,
                     ("attach_role", "modify_iam_binding"), case_request,
                     probe_request, ratchet_rule, positive_rule, rule_class,
                     case_attrs)


def _procurement() -> DomainDef:
    grid = {
        "emergency": [0, 1],
        "amount_usd": [5000, 20000, 50000, 200000],
        "vendor_tier": [1, 2, 3],          # 3 = pre-vetted strategic
        "dual_review": [0, 1],
    }
    resources = ["po-office-supplies", "po-cloud-contract", "po-hardware"]
    actions = ["approve_purchase_order", "draft_purchase_order",
               "view_catalog"]
    universe = build_universe(actions, resources, grid)

    def envelope(x):
        a = x["attrs"]
        return (x["action"] == "approve_purchase_order"
                and a["emergency"] == 1 and a["amount_usd"] <= 50000
                and a["vendor_tier"] >= 2 and a["dual_review"] == 1)

    def standing(x):
        return x["action"] in ("draft_purchase_order", "view_catalog")

    def hard(x):
        # Single-signature approval of the largest tier is never local.
        return not (x["action"] == "approve_purchase_order"
                    and x["attrs"]["amount_usd"] >= 200000
                    and x["attrs"]["dual_review"] == 0)

    case_request = {"action": "approve_purchase_order",
                    "resource": "po-cloud-contract",
                    "attrs": {"emergency": 1, "amount_usd": 50000,
                              "vendor_tier": 2, "dual_review": 1}}
    probe_request = {"action": "approve_purchase_order",
                     "resource": "po-cloud-contract",
                     "attrs": {"emergency": 0, "amount_usd": 50000,
                               "vendor_tier": 2, "dual_review": 1}}
    ratchet_rule = {
        "action": "approve_purchase_order", "resource": "po-*",
        "conditions": {"amount_usd": ["le", 200000],
                       "vendor_tier": ["ge", 1]}}
    positive_rule = {
        "action": "approve_purchase_order", "resource": "po-cloud-contract",
        "conditions": {"emergency": ["eq", 1], "amount_usd": ["le", 50000],
                       "vendor_tier": ["ge", 2], "dual_review": ["eq", 1]}}
    rule_class = {"domain": "procurement",
                  "actions": ["approve_purchase_order"],
                  "resources": resources}
    case_attrs = {"emergency": 1, "amount_usd": 50000, "vendor_tier": 2,
                  "dual_review": 1}
    return DomainDef("procurement", universe, envelope, standing, hard,
                     ("approve_purchase_order",), case_request,
                     probe_request, ratchet_rule, positive_rule, rule_class,
                     case_attrs)


def _finance() -> DomainDef:
    grid = {
        "urgency": [0, 1],
        "amount_usd": [1000, 10000, 100000, 1000000],
        "account_type": ["internal", "partner", "external"],
        "dual_sign": [0, 1],
    }
    resources = ["acct-payroll", "acct-vendor", "acct-treasury"]
    actions = ["wire_transfer", "schedule_payment", "view_balance"]
    universe = build_universe(actions, resources, grid)

    def envelope(x):
        a = x["attrs"]
        return (x["action"] == "wire_transfer"
                and a["account_type"] in ("internal", "partner")
                and a["amount_usd"] <= 100000 and a["urgency"] == 1
                and a["dual_sign"] == 1)

    def standing(x):
        return x["action"] in ("schedule_payment", "view_balance")

    def hard(x):
        return not (x["action"] == "wire_transfer"
                    and x["attrs"]["account_type"] == "external"
                    and x["attrs"]["dual_sign"] == 0)

    case_request = {"action": "wire_transfer", "resource": "acct-vendor",
                    "attrs": {"urgency": 1, "amount_usd": 100000,
                              "account_type": "partner", "dual_sign": 1}}
    probe_request = {"action": "wire_transfer", "resource": "acct-vendor",
                     "attrs": {"urgency": 0, "amount_usd": 100000,
                               "account_type": "partner", "dual_sign": 1}}
    ratchet_rule = {
        "action": "wire_transfer", "resource": "acct-*",
        "conditions": {"amount_usd": ["le", 1000000],
                       "account_type": ["any", None]}}
    positive_rule = {
        "action": "wire_transfer", "resource": "acct-vendor",
        "conditions": {"urgency": ["eq", 1], "amount_usd": ["le", 100000],
                       "account_type": ["eq", "partner"],
                       "dual_sign": ["eq", 1]}}
    rule_class = {"domain": "finance", "actions": ["wire_transfer"],
                  "resources": resources}
    case_attrs = {"urgency": 1, "amount_usd": 100000,
                  "account_type": "partner", "dual_sign": 1}
    return DomainDef("finance", universe, envelope, standing, hard,
                     ("wire_transfer",), case_request, probe_request,
                     ratchet_rule, positive_rule, rule_class, case_attrs)


def _dataaccess() -> DomainDef:
    grid = {
        "classification": [0, 1, 2],        # 0 internal, 1 confidential, 2 restricted
        "purpose": ["incident", "audit", "routine"],
        "ticket_open": [0, 1],
        "ttl_min": [15, 60, 1440],
    }
    resources = ["file-engwiki", "file-hr-comp", "file-board-minutes"]
    actions = ["read_restricted_file", "list_metadata", "request_access"]
    universe = build_universe(actions, resources, grid)

    def envelope(x):
        a = x["attrs"]
        return (x["action"] == "read_restricted_file"
                and a["classification"] <= 1 and a["purpose"] == "incident"
                and a["ticket_open"] == 1 and a["ttl_min"] <= 60)

    def standing(x):
        return x["action"] in ("list_metadata", "request_access")

    def hard(x):
        # Board minutes are never locally readable regardless of case.
        return not (x["action"] == "read_restricted_file"
                    and x["resource"] == "file-board-minutes"
                    and x["attrs"]["classification"] == 2)

    case_request = {"action": "read_restricted_file", "resource": "file-hr-comp",
                    "attrs": {"classification": 1, "purpose": "incident",
                              "ticket_open": 1, "ttl_min": 60}}
    probe_request = {"action": "read_restricted_file", "resource": "file-hr-comp",
                     "attrs": {"classification": 1, "purpose": "incident",
                              "ticket_open": 0, "ttl_min": 60}}
    ratchet_rule = {
        "action": "read_restricted_file", "resource": "file-*",
        "conditions": {"classification": ["le", 2],
                       "purpose": ["any", None]}}
    positive_rule = {
        "action": "read_restricted_file", "resource": "file-hr-comp",
        "conditions": {"classification": ["le", 1],
                       "purpose": ["eq", "incident"],
                       "ticket_open": ["eq", 1], "ttl_min": ["le", 60]}}
    rule_class = {"domain": "dataaccess", "actions": ["read_restricted_file"],
                  "resources": resources}
    case_attrs = {"classification": 1, "purpose": "incident",
                  "ticket_open": 1, "ttl_min": 60}
    return DomainDef("dataaccess", universe, envelope, standing, hard,
                     ("read_restricted_file",), case_request, probe_request,
                     ratchet_rule, positive_rule, rule_class, case_attrs)


_DOMAINS = {
    "cloudops": _cloudops(),
    "procurement": _procurement(),
    "finance": _finance(),
    "dataaccess": _dataaccess(),
}


def get_domain(name: str) -> DomainDef:
    return _DOMAINS[name]
