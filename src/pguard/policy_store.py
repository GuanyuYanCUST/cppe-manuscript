"""Normative state and the policy store.

Implements the labeled transition system of the paper:
CASE / EXEC_CASE / OUTCOME / LEARN / PROPOSE_PREC / INSTALL_PREC / AMEND /
REVOKE / ROTATE.

Two integration modes (Experiment E1's core contrast):

- ``guarded``   — INSTALL_PREC executes Algorithm 2 (CertifyAndInstall
  Precedent): an independent PRECEDENT capability, containment, epoch and
  version checks, atomic CAS commit.
- ``unguarded`` — the *vulnerable* integration: the policy-learning
  pipeline holds a direct write channel to the store, so a learned
  candidate commits without any independent rulemaking authority.  This is
  the CPPE-issuer failure the paper studies; it is a property of the
  integration, not of any component being "broken".

Every commit appends a hash-chained audit event; the policy hash changes
only through INSTALL_PREC / AMEND / REVOKE, never through learning.
"""
from __future__ import annotations

import hashlib
import time

from . import certs as C
from .crypto import canonical
from .dsl import containment, rule_matches, rule_hash

DEC_ADMIT_PREC = "ADMIT_PRECEDENT"
DEC_ADMIT_CASE = "ADMIT_CASE"
DEC_DENY = "DENY"


class AuditEntry(dict):
    pass


class PolicyStore:
    def __init__(self, domain, keystore, root, guarded: bool = True,
                 version: int = 1, epoch: int = 1, t0: float = 0.0,
                 case_issuers: set[str] | None = None,
                 authority_required: bool = True,
                 containment_required: bool = True,
                 precedents_serve: bool = True):
        self.domain = domain
        self.keystore = keystore
        self.root = root
        self.guarded = guarded
        self.version = version
        self.epoch = epoch
        self.t0 = t0
        # Fail-closed: only these principals may adjudicate CASEs
        # (default: root alone).  A keystore-valid signature from any other
        # principal is NOT case-issuing authority.
        self.case_issuers = case_issuers if case_issuers is not None \
            else {root.name}
        # Enforced-condition switches.  Defaults = full PRECEDENTGUARD
        # semantics.  Baselines B3/B5 and the E7 ablations turn exactly one
        # condition off; every other behaviour is shared machinery.
        self.authority_required = authority_required
        self.containment_required = containment_required
        self.precedents_serve = precedents_serve
        # Per-store envelope (AMEND replaces this; the shared DomainDef is
        # never mutated).
        self.envelope_fn = domain.in_envelope
        self.active_precedents: dict[str, dict] = {}   # rule_id -> cert
        self.live_cases: dict[str, dict] = {}          # case_id -> cert
        self.consumed_nonces: set[str] = set()
        self.revoked: set[str] = set()
        self.audit: list[AuditEntry] = []
        self.chain_hash = hashlib.sha256(b"genesis").hexdigest()
        self._seq = 0

    # ---------------------------------------------------------------- audit
    def _emit(self, label: str, **fields) -> AuditEntry:
        self._seq += 1
        ev = AuditEntry(seq=self._seq, t=time.time(), label=label, **fields)
        blob = (self.chain_hash + canonical(
            {k: v for k, v in ev.items() if k != "t"}).decode()).encode()
        self.chain_hash = hashlib.sha256(blob).hexdigest()
        ev["chain_hash"] = self.chain_hash
        self.audit.append(ev)
        return ev

    def policy_hash(self) -> str:
        return hashlib.sha256(canonical({
            "version": self.version, "epoch": self.epoch,
            "precedents": sorted(self.active_precedents),
            "revoked": sorted(self.revoked),
        })).hexdigest()[:16]

    # ------------------------------------------------------------- CASE path
    def issue_case(self, cert: dict) -> tuple[bool, str]:
        ok, why = C.verify_signature(cert, self.keystore)
        if not ok:
            return False, f"BAD_CASE_SIG:{why}"
        if cert["kind"] != C.KIND_CASE:
            return False, "TYPE_CONFUSION"
        if cert["issuer"] not in self.case_issuers:
            return False, "BAD_ISSUER"
        if C.is_expired(cert, self._now()):
            return False, "EXPIRED"
        if cert["case_id"] in self.live_cases:
            return False, "DUPLICATE_CASE"
        self.live_cases[cert["case_id"]] = cert
        self._emit("ISSUE_CASE", case_id=cert["case_id"],
                   issuer=cert["issuer"], scope=cert["attrs"],
                   expires_at=cert["expires_at"])
        return True, ""

    def _now(self) -> float:
        return time.time()

    # ---------------------------------------------------- INSTALL_PREC path
    def _cap_live(self, cap: dict, now: float) -> tuple[bool, str]:
        """Validate a PRECEDENT_CAP as an install credential."""
        if not isinstance(cap, dict) or cap.get("kind") != C.KIND_PRECEDENT_CAP:
            if isinstance(cap, dict) and cap.get("kind") == C.KIND_CASE:
                return False, "TYPE_CONFUSION_CASE_AS_PRECEDENT"
            return False, "NO_AUTHORITY"
        ok, why = C.verify_signature(cap, self.keystore)
        if not ok:
            return False, f"BAD_CAP_SIG:{why}"
        # Only root (or a root-delegated precedent issuer principal) may
        # hold the capability; the cap itself must be root-signed.
        if cap["issuer"] != self.root.name:
            return False, "BAD_ISSUER"
        if cap["epoch"] != self.epoch:
            return False, "STALE_EPOCH"
        if C.is_expired(cap, now):
            return False, "CAP_EXPIRED"
        if cap["cap_id"] in self.revoked:
            return False, "REVOKED"
        return True, ""

    def _cap_covers(self, cap: dict, rule: dict) -> bool:
        rc = cap["rule_class"]
        # cross-domain delegation is void: the cap must name THIS store's
        # domain (previously keyed off rule.get("domain"), which rules
        # never carry — vacuous check found in the E1 audit)
        if rc.get("domain") != self.domain.name:
            return False
        acts = rc.get("actions", [])
        if acts and rule.get("action") not in acts:
            return False
        return True

    def guarded_install(self, rule: dict, cap: dict | None,
                        expected_version: int | None = None,
                        now: float | None = None
                        ) -> tuple[bool, str, dict | None]:
        """Algorithm 2 — CertifyAndInstallPrecedent (fail-closed)."""
        now = self._now() if now is None else now
        if not self.guarded:
            return False, "STORE_NOT_GUARDED", None
        if self.authority_required:
            if cap is None:
                return self._reject(rule, "NO_AUTHORITY", None)
            ok, why = self._cap_live(cap, now)
            if not ok:
                return self._reject(rule, why, None)
            if not self._cap_covers(cap, rule):
                return self._reject(rule, "CAP_SCOPE", None)
        contained, witness = containment(rule, self.envelope_fn,
                                         self.domain.universe)
        if self.containment_required and not contained:
            return self._reject(rule, "OUT_OF_ROOT", witness)
        exp_v = self.version if expected_version is None else expected_version
        if exp_v != self.version:
            return self._reject(rule, "CAS_RACE", None)
        prec = self._commit_precedent(rule, cap, now,
                                      install_path="guarded")
        return True, "", prec

    def unguarded_install(self, rule: dict,
                          now: float | None = None
                          ) -> tuple[bool, str, dict | None]:
        """Vulnerable learner write channel: no capability, no containment.

        This models real policy-learning integrations where a successful
        trajectory writes a reusable default without an independent
        rulemaking transition (the CPPE-issuer event).
        """
        now = self._now() if now is None else now
        if self.guarded:
            return False, "STORE_GUARDED", None
        prec = self._commit_precedent(rule, None, now,
                                      install_path="learner_write")
        return True, "", prec

    def _reject(self, rule, reason, witness):
        self._emit("INSTALL_REJECTED", rule_hash=rule_hash(rule),
                   reason=reason,
                   witness=canonical(witness).decode() if witness else None)
        return False, reason, None

    def _commit_precedent(self, rule, cap, now, install_path: str) -> dict:
        rid = f"P{self._seq + 1:05d}-{rule_hash(rule)[:8]}"
        prec = C.make_precedent(
            norm=self.domain.name, rule_id=rid, rule=rule,
            rule_hash=rule_hash(rule),
            proof_hash=hashlib.sha256(
                canonical({"contained": True})).hexdigest()[:16],
            cap_id=(cap.get("cap_id") if cap else None),
            scope=(cap.get("rule_class") if cap
                   else {"domain": self.domain.name}),
            t_exp=now + 86400.0, version=self.version, epoch=self.epoch)
        prec["install_path"] = install_path
        # credential: did the commit carry valid rulemaking authority?
        # "none" marks a learner-authority install (CPPE-issuer), including
        # baseline B3's judge-only path and any ablated-authority store.
        prec["credential"] = "cap" if cap else "none"
        prec["issuer"] = self.root.name if cap else "learner"
        # out_of_root: scope ground truth stamped at the single commit
        # funnel (F-C2 fix): the guarded path already evaluated
        # containment for its reject check; recomputing here is
        # O(|universe|) and keeps both install paths and the audit
        # event consistent without signature changes.  A commit whose
        # rule escapes D carries out_of_root=True even when the store
        # let it through (learner_write) — classify_install reads this.
        contained, _ = containment(rule, self.envelope_fn,
                                   self.domain.universe)
        prec["out_of_root"] = not contained
        self.active_precedents[rid] = prec
        self._emit("INSTALL_PREC", rule_id=rid, rule_hash=rule_hash(rule),
                   cap_id=prec["cap_id"], install_path=install_path,
                   credential=prec["credential"],
                   out_of_root=prec["out_of_root"],
                   version=self.version, epoch=self.epoch)
        return prec

    # ------------------------------------------------------- AMEND / REVOKE
    def amend(self, amend_cert: dict, new_envelope_fn) -> tuple[bool, str]:
        ok, why = C.verify_signature(amend_cert, self.keystore)
        if not ok:
            return False, f"BAD_AMEND_SIG:{why}"
        if amend_cert["kind"] != C.KIND_AMEND:
            return False, "TYPE_CONFUSION"
        if amend_cert["issuer"] != self.root.name:
            return False, "BAD_ISSUER"
        if amend_cert["old_v"] != self.version:
            return False, "CAS_RACE"
        self.version = amend_cert["new_v"]
        if amend_cert.get("new_epoch"):
            self.epoch = amend_cert["new_epoch"]
        # Revalidation: drop precedents no longer contained under new D.
        dropped = []
        for rid, prec in list(self.active_precedents.items()):
            contained, _ = containment(prec["rule"], new_envelope_fn,
                                       self.domain.universe)
            if not contained:
                del self.active_precedents[rid]
                dropped.append(rid)
        self.envelope_fn = new_envelope_fn
        self._emit("AMEND", new_v=self.version, dropped=dropped)
        return True, ""

    def revoke(self, cert_id: str) -> None:
        self.revoked.add(cert_id)
        self.active_precedents.pop(cert_id, None)
        self.live_cases.pop(cert_id, None)
        self._emit("REVOKE", cert_id=cert_id)

    def rotate_epoch(self) -> None:
        self.epoch += 1
        self._emit("ROTATE", epoch=self.epoch)

    # ------------------------------------------------------------------ PEP
    def pep_decide(self, request: dict, case_cert: dict | None = None,
                   now: float | None = None,
                   consume: bool = True) -> tuple[str, str, str | None]:
        """Algorithm 1 — HandleNormativeRequest.

        Returns (decision, reason, matched_rule_id).
        Order: hard invariant -> active PRECEDENT -> fresh CASE -> deny.
        ``consume=False`` evaluates without burning the case nonce (used by
        the monitor's necessity gate so a denied-exception retry stays
        possible; single-threaded offline store, no TOCTOU concern).
        """
        now = self._now() if now is None else now
        if not self.domain.hard_ok(request):
            return DEC_DENY, "HARD_INVARIANT", None
        if self.domain.is_standing(request):
            return DEC_ADMIT_CASE, "STANDING_PERMISSION", None
        for rid, prec in self.active_precedents.items():
            if not self.precedents_serve:
                break
            if prec["epoch"] != self.epoch or prec["version"] > self.version:
                continue
            if C.is_expired(prec, now) or rid in self.revoked:
                continue
            if rule_matches(prec["rule"], request):
                return DEC_ADMIT_PREC, f"rule:{rid}", rid
        if case_cert is not None:
            ok, why = C.verify_signature(case_cert, self.keystore)
            if not ok:
                return DEC_DENY, f"BAD_CASE_SIG:{why}", None
            if case_cert["kind"] != C.KIND_CASE:
                return DEC_DENY, "TYPE_CONFUSION", None
            if case_cert["issuer"] not in self.case_issuers:
                return DEC_DENY, "BAD_ISSUER", None
            if case_cert["case_id"] in self.revoked:
                return DEC_DENY, "REVOKED", None
            if C.is_expired(case_cert, now):
                return DEC_DENY, "EXPIRED", None
            if case_cert["nonce"] in self.consumed_nonces:
                return DEC_DENY, "REPLAY", None
            if (case_cert["action"] != request["action"]
                    or case_cert["resource"] != request["resource"]):
                return DEC_DENY, "CASE_SCOPE_MISMATCH", None
            if not self.envelope_fn(request):
                return DEC_DENY, "OUT_OF_ROOT", None
            if consume:
                self.consumed_nonces.add(case_cert["nonce"])
                self._emit("EXEC_CASE", case_id=case_cert["case_id"])
            return DEC_ADMIT_CASE, f"case:{case_cert['case_id']}", None
        return DEC_DENY, "NO_AUTHORIZATION", None
