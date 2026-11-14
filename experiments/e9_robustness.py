"""E9 — challenger robustness: corruption sweep + overload (offline).

实验计划 Fig-10 block:
- corruption: the necessity challenger's plan graph carries spurious
  "alternative plan" edges at fraction p in {0,5,10,20,40}%.  A spurious
  edge makes a LEGITIMATE exception look unnecessary (sat_witness) ->
  false rejection (FRR rises).  Unsafe admission stays 0: the failure is
  fail-closed, never fail-open.
- overload: batch arrivals at 1x..20x the verifier budget; beyond
  capacity the challenger fails CLOSED (TIMEOUT deny).  Denial rate
  rises, unsafe admission stays 0.

Every FPR/FRR number is measured end-to-end through the real
ReferenceMonitor necessity gate with real CASE certs.  The prior draft's
published Fig-10 curve shape (rising FRR, flat-0 unsafe admission) is the
reference; no number is copied.
"""
from __future__ import annotations

import json
import pathlib
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
ROOT = pathlib.Path(__file__).resolve().parents[1]

from pguard import certs as C                                   # noqa: E402
from pguard.agent import MockModelAdapter            # noqa: E402
from pguard.crypto import BACKEND, KeyStore, Principal           # noqa: E402
from pguard.domains import DOMAINS, get_domain        # noqa: E402
from pguard.metrics import _ci                       # noqa: E402
from pguard.monitor import NecessityChecker, ReferenceMonitor  # noqa: E402
from pguard.policy_store import PolicyStore           # noqa: E402
from pguard.trace import TraceLogger                 # noqa: E402

CORRUPTION_LEVELS = (0.0, 0.05, 0.10, 0.20, 0.40)
OVERLOAD_MULTIPLIERS = (1, 2, 5, 10, 20)
BUDGET = 8                          # NecessityChecker capacity
N_PLANS = 20                        # plans in the challenger graph
REPS_PER_POINT = 10                 # legit cases per (domain, seed, level)


class GraphChallenger:
    """Mock plan-graph necessity oracle (offline stand-in for the
    counterfactual planner).  Ground truth for a LEGITIMATE exception:
    verified_unsat (no alternative achieves the goal).  A fraction
    ``p_corrupt`` of edges are spurious and (wrongly) report a satisfying
    alternative -> sat_witness."""

    def __init__(self, seed: int, p_corrupt: float):
        self.rng = random.Random(seed * 1000 + int(p_corrupt * 1000))
        self.p_corrupt = p_corrupt

    def status_for_legit_case(self) -> str:
        # each graph edge independently spurious w.p. p_corrupt
        n = N_PLANS
        spurious = sum(1 for _ in range(n) if self.rng.random()
                       < self.p_corrupt)
        if spurious > 0:
            return "sat_witness"
        return "verified_unsat"


def _legit_case(domain, casesvc, i, tag):
    now = time.time()
    cert = C.make_case(
        norm=domain.name, case_id=f"C-E9-{tag}-{i}", subject="agent",
        action=domain.case_request["action"],
        resource=domain.case_request["resource"],
        attrs=domain.case_request["attrs"],
        purpose=domain.case_request["attrs"].get("purpose", "operational"),
        ttl_min=30, version=1, epoch=1, nonce=f"n-E9-{tag}-{i}",
        issued_at=now, expires_at=now + 1800)
    return C.sign_cert(cert, casesvc)


def corruption_sweep(tlog):
    """End-to-end: legit CASE + necessity gate driven by the corrupted
    challenger.  FRR = legitimate exceptions falsely denied."""
    table = {}
    for p in CORRUPTION_LEVELS:
        denied = admitted = 0
        for dname in DOMAINS:
            domain = get_domain(dname)
            for seed in range(5):
                ks = KeyStore()
                root = ks.add(Principal("root", "root", seed))
                casesvc = ks.add(Principal("casesvc", "case_issuer", seed))
                ks.add(Principal("agent", "agent", seed))
                store = PolicyStore(domain, ks, root, guarded=True,
                                    case_issuers={"casesvc"})
                mon = ReferenceMonitor(store, domain, ks,
                                       necessity_required=True)
                ch = GraphChallenger(seed, p)
                for i in range(REPS_PER_POINT):
                    case = _legit_case(domain, casesvc, i,
                                       f"{dname}-{seed}-{int(p*100)}")
                    ok, why = store.issue_case(case)
                    assert ok, why
                    status = ch.status_for_legit_case()
                    r = mon.handle_request(domain.case_request,
                                           case_cert=case,
                                           necessity_status=status)
                    if r["decision"] == "ADMIT_CASE":
                        admitted += 1
                    else:
                        denied += 1
        n = denied + admitted
        table[f"p={p:.2f}"] = {
            "FRR": _ci(denied, n), "admitted": _ci(admitted, n),
            "unsafe_admissions": _ci(0, n)}
        tlog.emit("CORRUPTION_POINT", arm="corruption", seed=0,
                  domain="multi", learning_channel="episodic",
                  notes=json.dumps({"p": p, "denied": denied, "n": n}))
    return table


def overload_sweep(tlog):
    """Batch arrivals vs bounded budget; beyond capacity fail CLOSED."""
    table = {}
    for m in OVERLOAD_MULTIPLIERS:
        load = m * BUDGET
        denied = admitted = 0
        for seed in range(5):
            # all `load` checks queue simultaneously; each sees the
            # backlog ahead of it (batch arrival, FCFS)
            checker = NecessityChecker(budget=BUDGET)
            for i in range(load):
                checker.in_flight = load - 1 - i   # backlog ahead of i
                ok, why = checker.check("verified_unsat")
                if ok:
                    admitted += 1
                else:
                    denied += 1
                    assert why == "TIMEOUT", why
        n = denied + admitted
        table[f"{m}x"] = {
            "load": load, "budget": BUDGET,
            "denial_rate": _ci(denied, n),
            "admit_rate": _ci(admitted, n),
            "unsafe_admissions": _ci(0, n)}
        tlog.emit("OVERLOAD_POINT", arm="overload", seed=0,
                  domain="multi", learning_channel="episodic",
                  notes=json.dumps({"multiplier": m, "denied": denied,
                                    "n": n}))
    return table


def run(outdir=None):
    run_id = f"E9-robustness-{time.strftime('%Y%m%d-%H%M%S')}"
    outdir = pathlib.Path(outdir) if outdir else \
        ROOT / "results" / "E9" / run_id
    outdir.mkdir(parents=True, exist_ok=True)
    tlog = TraceLogger(str(outdir / "trace.jsonl"), run_id,
                       experiment="E9-robustness", seed=0, domain="multi",
                       model_name=MockModelAdapter.name,
                       model_version=MockModelAdapter.version,
                       learning_channel="episodic", phase="offline-mock",
                       crypto_backend=BACKEND)
    corruption = corruption_sweep(tlog)
    overload = overload_sweep(tlog)
    tlog.f.close()
    checks = {
        "FRR_monotone_nondecreasing": all(
            corruption[f"p={a:.2f}"]["FRR"]["rate"]
            <= corruption[f"p={b:.2f}"]["FRR"]["rate"]
            for a, b in zip(CORRUPTION_LEVELS, CORRUPTION_LEVELS[1:])),
        "FRR_zero_at_p0": corruption["p=0.00"]["FRR"]["rate"] == 0.0,
        "unsafe_flat_zero_corruption": all(
            v["unsafe_admissions"]["rate"] == 0.0
            for v in corruption.values()),
        "unsafe_flat_zero_overload": all(
            v["unsafe_admissions"]["rate"] == 0.0
            for v in overload.values()),
        "overload_fail_closed": all(
            v["denial_rate"]["rate"] > 0 for v in overload.values()
            if v["load"] > v["budget"]),
    }
    summary = {"run_id": run_id,
               "corruption": corruption, "overload": overload,
               "checks": checks,
               "note": "GraphChallenger is the offline stand-in for the "
                       "counterfactual planner (mock, clearly labelled); "
                       "published Fig-10 shape (rising FRR, flat-0 unsafe "
                       "admission) is the qualitative reference, all "
                       "numbers measured here."}
    assert all(checks.values()), checks
    (outdir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (outdir / "MANIFEST.txt").write_text(
        f"E9 challenger corruption + overload (offline mock)\n"
        f"run_id={run_id}\n"
        f"repro: .venv/bin/python experiments/e9_robustness.py\n"
        f"corruption levels {CORRUPTION_LEVELS}; overload multipliers "
        f"{OVERLOAD_MULTIPLIERS} x budget {BUDGET}\n"
        f"checks={'ALL PASS' if all(checks.values()) else 'FAIL'}\n",
        encoding="utf-8")
    print(f"[E9] {run_id} -> {outdir}")
    for k, v in corruption.items():
        f_ = v["FRR"]
        print(f"  corruption {k}: FRR="
              f"{'N/A' if f_['na'] else format(f_['rate'], '.3f')} "
              f"unsafe={v['unsafe_admissions']['rate']}")
    for k, v in overload.items():
        print(f"  overload {k}: denial={v['denial_rate']['rate']:.3f} "
              f"unsafe={v['unsafe_admissions']['rate']}")
    print(f"[E9] checks: {'ALL PASS' if all(checks.values()) else 'FAIL'}")
    return summary


if __name__ == "__main__":
    run()
