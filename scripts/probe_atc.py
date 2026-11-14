"""Diagnose ATC under a resource='*' LLM precedent: what does pep_decide
return for the fresh-CASE request once a broad standing rule is in?"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pguard.closed_loop import replay_method          # noqa: E402

roll = ROOT / "results/real_glm53/rollouts/acceptance"
t = json.loads((roll / "cloudops-episodic-s000.json").read_text())

# replay into PG and instrument the ATC block by re-doing it manually
row = replay_method(t, "PG", atc_resource="prod-api")
print("row:", json.dumps({k: row[k] for k in
      ("installed", "valid_accepted", "atc_done", "probe_admitted",
       "candidate_contained", "n_covered_out_of_D")}, indent=1))

from e2_baselines import ATC_RESOURCE              # noqa: E402
from pguard import certs as C                       # noqa: E402
from pguard.baselines import MethodWorld, verify_history   # noqa: E402
from pguard.domains import get_domain               # noqa: E402
import time                                         # noqa: E402

d = get_domain(t["domain"])
mw = MethodWorld("PG", d, t["seed"])
for m in t["memory"]:
    if "case_cert" in m:
        ok, why = mw.store.issue_case(m["case_cert"])
        assert ok, why
from pguard.closed_loop import normalize_candidate  # noqa: E402
cand, _ = normalize_candidate(t["final"]["rule"])
cap = mw.issue_cap(d, t["seed"], cap_id="CAP-probe")
certs = [m["case_cert"] for m in t["memory"] if "case_cert" in m]
attempted, ok, reason, prec = mw.attempt_install(
    cand, cap, verify_history(certs, mw.ks))
print("install:", attempted, ok, reason, prec is not None)
ar = {"action": d.case_request["action"],
      "resource": ATC_RESOURCE[d.name],
      "attrs": dict(d.case_request["attrs"])}
print("ATC req:", ar["resource"])
dec, reason, rid = mw.store.pep_decide(ar)
print("pep_decide(no cert):", dec, reason, rid)
