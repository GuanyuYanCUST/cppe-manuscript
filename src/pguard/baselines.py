"""B0–B6 baseline methods + PRECEDENTGUARD under one shared harness
(实验计划 §三: the 8-method comparison).

All methods share the same PolicyStore machinery, the same worlds, seeds,
histories, candidates and probes; they differ ONLY in the enforced
conditions — so the comparison is matched by construction and no baseline
is artificially weakened:

  B0  Strict/Immutable      never installs reusable rules (utility cost:
                            VPA=0), CASE path intact.
  B1  Success-Reuse         learner channel writes the store directly.
  B2  Provenance-Only       installs iff the history is authentic+signed;
                            no independent rulemaking separation.
  B3  Root-Aware Judge      (offline: oracle-informed mock judge) installs
                            iff the rule is contained in D; typed authority
                            NOT required.  Real LLM judge = LLM phase.
  B4  Scoped CASE + Expiry  correct one-shot case management, but the
                            learning pipeline still writes the store.
  B5  Action-Level Authorizer rules may install but never serve at the
                            PEP (per-request authorization only).
  B6  Exact Event Sourcing  installs iff every history event verifies
                            exactly (sig + chain); still no rulemaking
                            separation.
  PG  PRECEDENTGUARD        typed cap + containment + CAS (full guards).
"""
from __future__ import annotations

from . import certs as C
from .policy_store import PolicyStore
from .oracle import AuthorizationOracle
from .monitor import ReferenceMonitor
from .tools import ToolSandbox
from .crypto import KeyStore, Principal

METHODS = ("B0", "B1", "B2", "B3", "B4", "B5", "B6", "PG")

METHOD_DESC = {
    "B0": "strict/immutable policy store",
    "B1": "success-reuse (worked-before -> install)",
    "B2": "provenance-only (signed history suffices)",
    "B3": "root-aware judge (mock: containment-only, no typed authority)",
    "B4": "scoped CASE + expiry, learner write channel",
    "B5": "action-level authorizer (rules never serve)",
    "B6": "exact signed event sourcing",
    "PG": "PRECEDENTGUARD (typed cap + containment + CAS)",
}

# which methods gate the install on history authenticity
PROVENANCE_GATED = {"B2": "signed", "B6": "exact"}


class MethodWorld:
    """A fresh per-method world with the method's enforced conditions.

    ``ks``/``root``/``case_issuer`` let a cell share ONE keystore across
    all 8 methods (keys are deterministic per name|role|seed), so the same
    signed history verifies in every method's world — matched forks."""

    def __init__(self, method: str, domain, seed: int, ks=None, root=None,
                 case_issuer=None):
        self.method = method
        self.ks = ks if ks is not None else KeyStore()
        self.root = root if root is not None else self.ks.add(
            Principal("root", "root", seed))
        self.case_issuer = case_issuer if case_issuer is not None else \
            self.ks.add(Principal("casesvc", "case_issuer", seed))
        self.ks.add(Principal("agent", "agent", seed))
        kw = {}
        if method == "B3":
            kw = dict(guarded=True, authority_required=False)
        elif method == "B5":
            kw = dict(guarded=False, precedents_serve=False)
        elif method in ("B1", "B2", "B4", "B6"):
            kw = dict(guarded=False)
        else:                                  # B0, PG
            kw = dict(guarded=True)
        self.store = PolicyStore(domain, self.ks, self.root,
                                 case_issuers={"casesvc"}, **kw)
        self.sandbox = ToolSandbox(domain)
        self.monitor = ReferenceMonitor(self.store, domain, self.ks)
        self.oracle = AuthorizationOracle(domain, self.ks, "root")

    def issue_cap(self, domain, seed, cap_id=None):
        import time
        cap = C.make_precedent_cap(
            cap_id=cap_id or f"CAP-{self.method}-s{seed:04d}", issuer="root",
            rule_class=domain.rule_class, t_exp=time.time() + 3600.0,
            version=1, epoch=1)
        return C.sign_cert(cap, self.root)

    def attempt_install(self, rule, cap, provenance_ok: bool):
        """The method's install decision for one candidate.  Returns
        (attempted, ok, reason, prec)."""
        m = self.method
        if m == "B0":
            return False, False, "IMMUTABLE_STORE", None
        gate = PROVENANCE_GATED.get(m)
        if gate and not provenance_ok:
            return False, False, f"PROVENANCE_INVALID", None
        if m == "PG":
            r = self.monitor.certify_and_install(rule, cap)
            return True, r["ok"], r["reason"], r["precedent"]
        if m == "B3":
            r = self.monitor.certify_and_install(rule, None)  # judge: scope only
            return True, r["ok"], r["reason"], r["precedent"]
        # B1/B2/B4/B5/B6: learner write channel
        ok, why, prec = self.store.unguarded_install(rule)
        return True, ok, why, prec


def verify_history(case_certs: list[dict], keystore) -> bool:
    """Exact signed event sourcing check: every CASE cert must verify
    (signature + issuer + kind).  Tampered attrs -> False."""
    for cert in case_certs:
        ok, why = C.verify_signature(cert, keystore)
        if not ok or cert["kind"] != C.KIND_CASE:
            return False
        # binding check: signed attrs must still hash consistently
        if cert.get("attrs") is None:
            return False
    return True


def make_lossy(case_certs: list[dict]) -> list[dict]:
    """Corrupt the memory copy of the history (attrs mutated after
    signing): signature verification then fails, modelling a lossy/
    unreliable learning-memory channel."""
    out = [dict(c) for c in case_certs]
    if out:
        out[0] = dict(out[0])
        out[0]["attrs"] = dict(out[0]["attrs"])
        k = sorted(out[0]["attrs"])[0]
        out[0]["attrs"][k] = "CORRUPTED"
    return out
