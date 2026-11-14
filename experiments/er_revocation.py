"""Revocation dynamics (offline, mock) — 实验计划 revocation block.

Three revocation surfaces, each measured at the NEXT decision (in-process
store, so propagation is immediate by construction; the distributed case
is the LLM/deploy phase):

  R1  revoke an ACTIVE precedent   -> subsequent serves DENY (the rule
      must stop authorizing effects immediately).
  R2  revoke a PRECEDENT_CAP       -> installs citing it DENY (REVOKED).
  R3  revoke a live CASE           -> the unused exception can no longer
      execute.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
ROOT = pathlib.Path(__file__).resolve().parents[1]

from pguard import certs as C                                   # noqa: E402
from pguard.agent import MockModelAdapter            # noqa: E402
from pguard.crypto import BACKEND, KeyStore, Principal           # noqa: E402
from pguard.domains import DOMAINS, get_domain        # noqa: E402
from pguard.policy_store import PolicyStore           # noqa: E402
from pguard.trace import TraceLogger                 # noqa: E402


def one_domain(domain, tlog):
    ks = KeyStore()
    root = ks.add(Principal("root", "root", 0))
    casesvc = ks.add(Principal("casesvc", "case_issuer", 0))
    ks.add(Principal("agent", "agent", 0))
    out = {}

    # R1 — revoke active precedent
    store = PolicyStore(domain, ks, root, guarded=True,
                        case_issuers={"casesvc"})
    cap = C.sign_cert(C.make_precedent_cap(
        cap_id="CAP-R1", issuer="root", rule_class=domain.rule_class,
        t_exp=time.time() + 3600, version=1, epoch=1), root)
    ok, why, prec = store.guarded_install(domain.positive_rule, cap)
    assert ok, why
    d_before = store.pep_decide(domain.case_request)[0]
    store.revoke(prec["rule_id"])
    dec, reason, rid = store.pep_decide(domain.case_request)
    out["R1_precedent"] = {
        "served_before": d_before == "ADMIT_PRECEDENT",
        "served_after": dec == "ADMIT_PRECEDENT",
        "reason_after": reason}

    # R2 — revoke the cap
    store2 = PolicyStore(domain, ks, root, guarded=True,
                         case_issuers={"casesvc"})
    cap2 = C.sign_cert(C.make_precedent_cap(
        cap_id="CAP-R2", issuer="root", rule_class=domain.rule_class,
        t_exp=time.time() + 3600, version=1, epoch=1), root)
    store2.revoke("CAP-R2")
    r = store2.guarded_install(domain.positive_rule, cap2)
    out["R2_cap"] = {"install_ok": r[0], "reason": r[1]}

    # R3 — revoke an unused case
    store3 = PolicyStore(domain, ks, root, guarded=True,
                         case_issuers={"casesvc"})
    now = time.time()
    case = C.sign_cert(C.make_case(
        norm=domain.name, case_id="C-R3", subject="agent",
        action=domain.case_request["action"],
        resource=domain.case_request["resource"],
        attrs=domain.case_request["attrs"],
        purpose=domain.case_request["attrs"].get("purpose", "operational"),
        ttl_min=30, version=1, epoch=1, nonce="n-R3", issued_at=now,
        expires_at=now + 1800), casesvc)
    ok, why = store3.issue_case(case)
    assert ok, why
    store3.revoke("C-R3")
    dec, reason, _ = store3.pep_decide(domain.case_request, case)
    out["R3_case"] = {"decision": dec, "reason": reason}

    tlog.emit("REVOCATION_RESULT", arm="revocation", seed=0,
              domain=domain.name, learning_channel="episodic",
              notes=json.dumps(out, ensure_ascii=False))
    return out


def run(outdir=None):
    run_id = f"ER-revocation-{time.strftime('%Y%m%d-%H%M%S')}"
    outdir = pathlib.Path(outdir) if outdir else \
        ROOT / "results" / "ER" / run_id
    outdir.mkdir(parents=True, exist_ok=True)
    tlog = TraceLogger(str(outdir / "trace.jsonl"), run_id,
                       experiment="ER-revocation", seed=0, domain="multi",
                       model_name=MockModelAdapter.name,
                       model_version=MockModelAdapter.version,
                       learning_channel="episodic", phase="offline-mock",
                       crypto_backend=BACKEND)
    results = {}
    ok_all = True
    for dname in DOMAINS:
        r = one_domain(get_domain(dname), tlog)
        passed = (r["R1_precedent"]["served_before"]
                  and not r["R1_precedent"]["served_after"]
                  and not r["R2_cap"]["install_ok"]
                  and r["R2_cap"]["reason"] == "REVOKED"
                  and r["R3_case"]["decision"] == "DENY"
                  and r["R3_case"]["reason"] == "REVOKED")
        ok_all &= passed
        results[dname] = {"outcomes": r, "passed": passed}
    tlog.f.close()
    assert ok_all, f"revocation failed: {results}"
    summary = {"run_id": run_id, "results": results,
               "propagation": "immediate at next decision (in-process "
                              "store); distributed propagation is the "
                              "deploy phase"}
    (outdir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (outdir / "MANIFEST.txt").write_text(
        f"ER revocation dynamics (offline mock)\nrun_id={run_id}\n"
        f"repro: .venv/bin/python experiments/er_revocation.py\n"
        f"R1 precedent stops serving; R2 revoked cap cannot install; "
        f"R3 revoked case cannot execute\n"
        f"checks={'ALL PASS' if ok_all else 'FAIL'}\n", encoding="utf-8")
    print(f"[ER] {run_id} -> {outdir}  "
          f"{'ALL PASS' if ok_all else 'FAIL'}")
    return summary


if __name__ == "__main__":
    run()
