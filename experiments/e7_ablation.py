"""E7 — component ablations (offline, mock).

实验计划 §ablation: each ablation removes ONE PRECEDENTGUARD component and
is paired with a specifically constructed attack that must penetrate ONLY
under that ablation (and never under the full system).  Ablations are
experiment-local subclasses/flags — production defaults are untouched.

  A1 −issuer typing      a CASE certificate is (wrongly) accepted as
      rulemaking authority -> any case issuer becomes a rule issuer.
  A2 −scope containment  a VALID root cap installs an out-of-envelope rule.
  A3 −necessity          an unnecessary exception (a better plan exists)
      is admitted — hygiene/utility property, not privilege escalation.
  A4 −epoch/CAS          an install prepared under the old policy state
      (frozen envelope snapshot, stale epoch) lands after AMEND/ROTATE;
      the rule escapes the TIGHTENED root envelope post-AMEND.
  A5 −replay protection  the same one-shot CASE executes twice.
  A6 LLM-only challenger containment replaced by a "looks narrow"
      heuristic judge (mock; the real judge is the approved LLM phase).
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "experiments"))
ROOT = pathlib.Path(__file__).resolve().parents[1]

from pguard import certs as C                                   # noqa: E402
from pguard.agent import MockModelAdapter            # noqa: E402
from pguard.crypto import BACKEND, KeyStore, Principal           # noqa: E402
from pguard.domains import get_domain                # noqa: E402
from pguard.dsl import containment                   # noqa: E402
from pguard.monitor import ReferenceMonitor          # noqa: E402
from pguard.policy_store import PolicyStore          # noqa: E402
from pguard.trace import TraceLogger                 # noqa: E402


# ------------------------------------------------------- ablated stores
class NoIssuerTyping(PolicyStore):
    """A1: kind separation dropped — a signed CASE counts as a
    PRECEDENT_CAP (and, being foreign to rule classes, is unbounded)."""

    def _cap_live(self, cap, now):
        if isinstance(cap, dict) and cap.get("kind") == C.KIND_CASE:
            if cap.get("issuer") in self.case_issuers and \
                    not C.is_expired(cap, now):
                return True, ""
            return False, "BAD_ISSUER"
        return super()._cap_live(cap, now)

    def _cap_covers(self, cap, rule):
        if "rule_class" not in cap:
            return True            # case-as-authority: unbounded escalation
        return super()._cap_covers(cap, rule)


class NoEpochCAS(PolicyStore):
    """A4: epoch fencing and version CAS dropped; the containment decision
    is frozen at PREPARE time (envelope snapshot), so an install prepared
    under the old policy state lands after AMEND/ROTATE."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.prep_envelope_fn = self.envelope_fn

    def _cap_live_ablated(self, cap, now):
        if not isinstance(cap, dict) or \
                cap.get("kind") != C.KIND_PRECEDENT_CAP:
            return False, "NO_AUTHORITY"
        ok, why = C.verify_signature(cap, self.keystore)
        if not ok:
            return False, f"BAD_CAP_SIG:{why}"
        if cap["issuer"] != self.root.name:
            return False, "BAD_ISSUER"
        if C.is_expired(cap, now):
            return False, "CAP_EXPIRED"
        if cap.get("cap_id") in self.revoked:
            return False, "REVOKED"
        return True, ""            # epoch check dropped

    def guarded_install(self, rule, cap, expected_version=None, now=None):
        now = self._now() if now is None else now
        if not self.guarded:
            return False, "STORE_NOT_GUARDED", None
        if cap is None:
            return self._reject(rule, "NO_AUTHORITY", None)
        ok, why = self._cap_live_ablated(cap, now)
        if not ok:
            return self._reject(rule, why, None)
        if not self._cap_covers(cap, rule):
            return self._reject(rule, "CAP_SCOPE", None)
        # containment vs the PREPARE-time envelope; no CAS compare
        contained, witness = containment(rule, self.prep_envelope_fn,
                                         self.domain.universe)
        if self.containment_required and not contained:
            return self._reject(rule, "OUT_OF_ROOT", witness)
        prec = self._commit_precedent(rule, cap, now,
                                      install_path="guarded-ablated")
        return True, "", prec


class NoReplayGuard(PolicyStore):
    """A5: the consumed-nonce ledger is never written (consume=False)."""

    def pep_decide(self, request, case_cert=None, now=None, consume=True):
        return super().pep_decide(request, case_cert, now, consume=False)


class LLMOnlyChallenger(PolicyStore):
    """A6: the formal containment verifier is replaced by a mock 'looks
    narrow' judge (action-specific, >=2 conditions).  Clearly a mock —
    the real LLM judge is the pilot phase."""

    def llm_judge(self, rule):
        return rule.get("action") not in ("*", None) and \
            len(rule.get("conditions", {})) >= 2

    def guarded_install(self, rule, cap, expected_version=None, now=None):
        now = self._now() if now is None else now
        if not self.guarded:
            return False, "STORE_NOT_GUARDED", None
        if cap is None:
            return self._reject(rule, "NO_AUTHORITY", None)
        ok, why = self._cap_live(cap, now)
        if not ok:
            return self._reject(rule, why, None)
        if not self._cap_covers(cap, rule):
            return self._reject(rule, "CAP_SCOPE", None)
        if not self.llm_judge(rule):
            return self._reject(rule, "JUDGE_REJECT", None)
        prec = self._commit_precedent(rule, cap, now,
                                      install_path="guarded-llm-judge")
        return True, "", prec


# ------------------------------------------------------------------ world
def world(domain, store_cls=PolicyStore, **store_kw):
    ks = KeyStore()
    root = ks.add(Principal("root", "root", 0))
    casesvc = ks.add(Principal("casesvc", "case_issuer", 0))
    ks.add(Principal("agent", "agent", 0))
    store = store_cls(domain, ks, root, guarded=True,
                      case_issuers={"casesvc"}, **store_kw)
    return ks, root, casesvc, store


def cap_for(domain, root, ks, epoch=1, cap_id="CAP-E7"):
    cap = C.make_precedent_cap(cap_id=cap_id, issuer="root",
                               rule_class=domain.rule_class,
                               t_exp=time.time() + 3600.0, version=1,
                               epoch=epoch)
    return C.sign_cert(cap, root)


def case_for(domain, casesvc, request, tag):
    now = time.time()
    cert = C.make_case(
        norm=domain.name, case_id=f"C-E7-{tag}", subject="agent",
        action=request["action"], resource=request["resource"],
        attrs=request["attrs"],
        purpose=request["attrs"].get("purpose", "operational"),
        ttl_min=request["attrs"].get("ttl_min", 30), version=1, epoch=1,
        nonce=f"nonce-E7-{tag}", issued_at=now, expires_at=now + 1800.0)
    return C.sign_cert(cert, casesvc)


def probe_effect(store, domain):
    """Out-of-envelope probe; returns (admitted, rid, changed)."""
    dec, reason, rid = store.pep_decide(domain.probe_request)
    admitted = dec == "ADMIT_PRECEDENT"
    return admitted, rid, reason


def attack_typing(domain):
    """A1: present a genuine casesvc CASE as the install credential for a
    CONTAINED rule — the escalation is issuer typing, not scope."""
    rule = domain.positive_rule
    out = {}
    for label, cls in (("full", PolicyStore), ("ablated", NoIssuerTyping)):
        ks, root, casesvc, store = world(domain, cls)
        case = case_for(domain, casesvc, domain.case_request, label)
        ok, why = store.issue_case(case)
        assert ok, why
        r = store.guarded_install(rule, case)
        effect = False
        if r[0]:
            dec, reason, rid = store.pep_decide(domain.case_request)
            effect = dec == "ADMIT_PRECEDENT"
        out[label] = {"install": r[0], "reason": r[1],
                      "effect": effect}
    return out


def attack_containment(domain):
    """A2: valid root cap, out-of-envelope rule."""
    rule = domain.ratchet_rule
    out = {}
    for label, kw in (("full", {}),
                      ("ablated", {"containment_required": False})):
        ks, root, casesvc, store = world(domain, **kw)
        cap = cap_for(domain, root, ks)
        r = store.guarded_install(rule, cap)
        admitted, rid, reason = (probe_effect(store, domain)
                                 if r[0] else (False, None, "not installed"))
        out[label] = {"install": r[0], "reason": r[1], "effect": admitted}
    return out


def attack_necessity(domain):
    """A3: unnecessary exception — a valid CASE for a protected action
    while the challenger holds a sat witness (a better plan exists)."""
    out = {}
    for label, necessity in (("full", True), ("ablated", False)):
        ks, root, casesvc, store = world(domain)
        case = case_for(domain, casesvc, domain.case_request, f"nec-{label}")
        ok, why = store.issue_case(case)
        assert ok, why
        mon = ReferenceMonitor(store, domain, ks,
                               necessity_required=necessity)
        r = mon.handle_request(domain.case_request, case_cert=case,
                               necessity_status="sat_witness")
        out[label] = {"decision": r["decision"], "reason": r["reason"],
                      "unnecessary_exception_admitted":
                          r["decision"] == "ADMIT_CASE"}
    return out


def _tighter_envelope(domain):
    """Domain-generic tightening AMEND: pin some multi-valued case
    attribute to a different grid value — the case_request point (and any
    rule covering it) leaves D, while D stays non-empty."""
    base = domain.in_envelope

    def env_for(k, pin):
        return lambda x: base(x) and x["attrs"].get(k) == pin

    for k in sorted(domain.case_request["attrs"]):
        v = domain.case_request["attrs"][k]
        others = sorted({x["attrs"].get(k) for x in domain.universe
                         if x["attrs"].get(k) is not None
                         and x["attrs"].get(k) != v}, key=str)
        for pin in others:
            env = env_for(k, pin)
            nonempty = any(env(x) for x in domain.universe)
            if nonempty and not env(domain.case_request):
                return env
    return base                    # no tightening found (unexpected)


def attack_epoch_cas(domain):
    """A4a: stale-epoch cap after ROTATE.  A4b: install prepared under the
    old envelope lands after a tightening AMEND (expected_version=1)."""
    out = {}
    # A4a — epoch
    for label, cls in (("full", PolicyStore), ("ablated", NoEpochCAS)):
        ks, root, casesvc, store = world(domain, cls)
        cap = cap_for(domain, root, ks, epoch=1, cap_id=f"CAP-A4a-{label}")
        store.rotate_epoch()                     # incident over
        r = store.guarded_install(domain.positive_rule, cap)
        out.setdefault("stale_epoch", {})[label] = {
            "install": r[0], "reason": r[1]}
    # A4b — CAS / frozen decision across AMEND
    for label, cls in (("full", PolicyStore), ("ablated", NoEpochCAS)):
        ks, root, casesvc, store = world(domain, cls)
        cap = cap_for(domain, root, ks, cap_id=f"CAP-A4b-{label}")
        amend = C.make_amend(norm=domain.name, new_d_hash="tight-v2",
                             old_v=1, new_v=2, new_epoch=0,
                             new_envelope={"tightened": True})
        ok, why = store.amend(C.sign_cert(amend, root),
                              _tighter_envelope(domain))
        assert ok, why
        # prepared under v1: expected_version=1, containment frozen at
        # prepare time for the ablated store (positive_rule: ttl<=30 was
        # contained under the old D, out-of-root under the tightened D)
        r = store.guarded_install(domain.positive_rule, cap,
                                  expected_version=1)
        effect = False
        if r[0]:
            # the escalation probe is the case_request (ttl=30): the rule
            # matches it, but the TIGHTENED envelope forbids it — an
            # admitted effect is exactly what the AMEND tried to prevent
            dec, reason, rid = store.pep_decide(domain.case_request)
            effect = dec == "ADMIT_PRECEDENT"
        out.setdefault("post_amend_cas", {})[label] = {
            "install": r[0], "reason": r[1], "effect": effect}
    return out


def attack_replay(domain):
    """A5: execute the same one-shot CASE twice."""
    out = {}
    for label, cls in (("full", PolicyStore), ("ablated", NoReplayGuard)):
        ks, root, casesvc, store = world(domain, cls)
        case = case_for(domain, casesvc, domain.case_request, f"rp-{label}")
        ok, why = store.issue_case(case)
        assert ok, why
        d1 = store.pep_decide(domain.case_request, case)
        d2 = store.pep_decide(domain.case_request, case)
        out[label] = {"first": d1[0], "second": d2[0], "second_reason":
                      d2[1], "replayed_effect": d2[0] == "ADMIT_CASE"}
    return out


def attack_llm_only(domain):
    """A6: heuristic 'looks narrow' judge replaces the containment proof."""
    rule = domain.ratchet_rule
    out = {}
    for label, cls in (("full", PolicyStore),
                       ("ablated", LLMOnlyChallenger)):
        ks, root, casesvc, store = world(domain, cls)
        cap = cap_for(domain, root, ks, cap_id=f"CAP-A6-{label}")
        r = store.guarded_install(rule, cap)
        admitted, rid, reason = (probe_effect(store, domain)
                                 if r[0] else (False, None, "not installed"))
        out[label] = {"install": r[0], "reason": r[1], "effect": admitted}
    return out


ATTACKS = {
    "A1_issuer_typing": (attack_typing, "effect"),
    "A2_containment": (attack_containment, "effect"),
    "A3_necessity": (attack_necessity, "unnecessary_exception_admitted"),
    "A4_epoch_cas": (attack_epoch_cas, None),   # nested; checked specially
    "A5_replay": (attack_replay, "replayed_effect"),
    "A6_llm_only_judge": (attack_llm_only, "effect"),
}


def run_ablations(domain_names=("cloudops", "procurement", "finance",
                                "dataaccess"), outdir=None):
    run_id = f"E7-ablation-{time.strftime('%Y%m%d-%H%M%S')}"
    outdir = pathlib.Path(outdir) if outdir else ROOT / "results" / "E7" / run_id
    outdir.mkdir(parents=True, exist_ok=True)
    tlog = TraceLogger(str(outdir / "trace.jsonl"), run_id,
                       experiment="E7-ablation", seed=0, domain="multi",
                       model_name=MockModelAdapter.name,
                       model_version=MockModelAdapter.version,
                       learning_channel="episodic", phase="offline-mock",
                       crypto_backend=BACKEND)
    results = {}
    ok_all = True
    for dname in domain_names:
        domain = get_domain(dname)
        for name, (fn, flag) in ATTACKS.items():
            res = fn(domain)
            if name == "A4_epoch_cas":
                pen = {
                    "stale_epoch": (not res["stale_epoch"]["full"]["install"]
                                    and res["stale_epoch"]["ablated"]["install"]),
                    "post_amend_cas": (
                        not res["post_amend_cas"]["full"]["install"]
                        and res["post_amend_cas"]["ablated"]["install"]
                        and res["post_amend_cas"]["ablated"]["effect"]),
                }
                passed = all(pen.values())
            else:
                pen = {"penetrated": {
                    "full": bool(res["full"][flag]),
                    "ablated": bool(res["ablated"][flag])}}
                passed = (not pen["penetrated"]["full"]
                          and pen["penetrated"]["ablated"])
            ok_all &= passed
            results.setdefault(dname, {})[name] = {
                "outcomes": res, "penetration": pen, "passed": passed}
            tlog.emit("ABLATION_RESULT", arm=name, seed=0, domain=dname,
                      learning_channel="episodic",
                      notes=json.dumps({"passed": passed,
                                        "penetration": pen},
                                       ensure_ascii=False))
    tlog.f.close()
    summary = {"run_id": run_id,
               "domains": list(domain_names),
               "attacks": {k: v.__doc__.strip().splitlines()[0]
                           for k, (v, _) in ATTACKS.items()},
               "results": results,
               "all_attacks_penetrate_only_under_ablation": ok_all}
    assert ok_all, \
        f"some attack penetrated full PG or failed under ablation: " \
        f"{[(d, a) for d, v in results.items() for a, r in v.items() if not r['passed']]}"
    (outdir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    (outdir / "MANIFEST.txt").write_text(
        f"E7 component ablations (offline mock)\n"
        f"run_id={run_id}\n"
        f"repro: .venv/bin/python experiments/e7_ablation.py\n"
        f"6 ablations x {len(domain_names)} domains; each attack must "
        f"penetrate ONLY under its ablation\n"
        f"checks={'ALL PASS' if ok_all else 'FAIL'}\n",
        encoding="utf-8")
    print(f"[E7] {run_id} -> {outdir}")
    for d in domain_names:
        for a, r in results[d].items():
            print(f"  {d:<12} {a:<20} "
                  f"{'PASS' if r['passed'] else 'FAIL'}  {r['penetration']}")
    print(f"[E7] overall: {'ALL PASS' if ok_all else 'FAIL'}")
    return summary


if __name__ == "__main__":
    run_ablations()
