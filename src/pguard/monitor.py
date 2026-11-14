"""PRECEDENTGUARD reference monitor.

Wraps a guarded PolicyStore and adds the fail-closed necessity checker
(Algorithm 3 semantics: UNKNOWN / TIMEOUT / SAT all deny — only a verified
UNSAT "no better alternative" certificate satisfies the obligation).
"""
from __future__ import annotations

from .policy_store import DEC_ADMIT_CASE, DEC_ADMIT_PREC, DEC_DENY


class NecessityChecker:
    """Bounded counterfactual challenger (fail-closed).

    ``status`` comes from the (untrusted) proposal pipeline; the monitor
    only accepts ``verified_unsat``.  ``timeout_s``/``budget`` model the
    bounded resource: exceeding them yields ``timeout`` -> DENY.
    """

    def __init__(self, budget: int = 8, timeout_s: float = 0.002):
        self.budget = budget
        self.timeout_s = timeout_s
        self.in_flight = 0

    def check(self, status: str) -> tuple[bool, str]:
        if self.in_flight >= self.budget:
            return False, "TIMEOUT"
        if status == "verified_unsat":
            return True, ""
        if status == "sat_witness":
            return False, "BETTER_PLAN_EXISTS"
        if status == "unknown":
            return False, "UNKNOWN"
        if status == "timeout":
            return False, "TIMEOUT"
        return False, "UNKNOWN"


class ReferenceMonitor:
    def __init__(self, store, domain, keystore,
                 necessity_required: bool = False,
                 checker: NecessityChecker | None = None):
        self.store = store
        self.domain = domain
        self.keystore = keystore
        self.necessity_required = necessity_required
        self.checker = checker or NecessityChecker()

    def certify_and_install(self, rule: dict, cap: dict | None,
                            necessity_status: str = "verified_unsat",
                            expected_version: int | None = None):
        """Algorithm 2 with latency capture for the trace logger."""
        import time
        t0 = time.perf_counter()
        ok, reason, prec = self.store.guarded_install(
            rule, cap, expected_version=expected_version)
        t1 = time.perf_counter()
        guard_decision = "INSTALL" if ok else f"REJECT:{reason}"
        return {"ok": ok, "reason": reason, "precedent": prec,
                "guard_decision": guard_decision,
                "latency_verify_ms": (t1 - t0) * 1000.0}

    def handle_request(self, request: dict, case_cert: dict | None = None,
                       necessity_status: str = "verified_unsat"):
        """Algorithm 1 with fail-closed necessity and latency capture.

        The PEP is evaluated nonce-free first; only an ADMIT_CASE that also
        passes the necessity obligation burns the nonce (so a
        necessity-denied exception can be retried once the challenger
        returns a verified certificate).
        """
        import time
        t0 = time.perf_counter()
        decision, reason, rid = self.store.pep_decide(
            request, case_cert, consume=not self.necessity_required)
        # necessity obligations bind only the EXCEPTION path — a standing
        # permission is not an exception and needs no counterfactual
        if (decision == DEC_ADMIT_CASE and self.necessity_required
                and str(reason).startswith("case:")):
            ok, why = self.checker.check(necessity_status)
            if not ok:
                decision, reason, rid = DEC_DENY, f"NECESSITY_{why}", None
            else:
                decision, reason, rid = self.store.pep_decide(request,
                                                              case_cert)
        t1 = time.perf_counter()
        return {"decision": decision, "reason": reason, "rule_id": rid,
                "latency_auth_ms": (t1 - t0) * 1000.0}
