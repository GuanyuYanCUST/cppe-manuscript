"""Repeated-sampling experiment: 20 fresh replays of the frozen pilot's
fixed repro cell, metrics pre-registered in
results/real_glm53/audit/PRE_REGISTERED_RESAMPLE_METRICS.md."""
import hashlib
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from e2_baselines import build_history                    # noqa: E402
from llm_pilot import CachingTransport, Guard             # noqa: E402
from pguard.domains import get_domain                     # noqa: E402
from pguard.llm_adapter import LLMRuleAdapter, load_dotenv  # noqa: E402
from pguard.oracle import AuthorizationOracle             # noqa: E402

N = 20
RAWDIR = ROOT / "results" / "real_glm53" / "raw"
OUTDIR = ROOT / "results" / "real_glm53" / "audit"


def parse_rule(content):
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`").replace("json", "", 1).strip()
    return json.loads(text) if text.startswith("{") else None


def matches(rule, x):
    if rule.get("action", "*") != "*" and rule["action"] != x["action"]:
        return False
    pat = rule.get("resource", "*")
    if pat != "*" and pat != x["resource"] and not (
            pat.endswith("*") and x["resource"].startswith(pat[:-1])):
        return False
    for attr, cond in rule.get("conditions", {}).items():
        v = x["attrs"].get(attr)
        op, bound = cond
        if op == "any":
            continue
        if v is None:
            return False
        if op == "eq" and v != bound:
            return False
        if op == "le" and not v <= bound:
            return False
        if op == "ge" and not v >= bound:
            return False
    return True


def main():
    load_dotenv(".env")
    RAWDIR.mkdir(parents=True, exist_ok=True)
    OUTDIR.mkdir(parents=True, exist_ok=True)
    pre = OUTDIR / "PRE_REGISTERED_RESAMPLE_METRICS.md"
    pre_hash = hashlib.sha256(pre.read_bytes()).hexdigest()
    run_id = f"resample-{time.strftime('%Y%m%d-%H%M%S')}"
    raw_path = RAWDIR / f"{run_id}.jsonl"
    raw_file = open(raw_path, "a", encoding="utf-8")
    ct = CachingTransport(30.0, raw_file, calls_cap=25)
    adapter = LLMRuleAdapter(provider="glm", enabled=True, max_retries=2,
                             max_output_tokens=1024, transport=ct)
    assert adapter.enabled, "GLM_API_KEY absent"
    ct.adapter = adapter

    domain = get_domain("cloudops")
    oracle = AuthorizationOracle(domain, None, "root")
    ks, root, casesvc, entries = build_history(domain, 0, "episodic", 5)
    memory = [{"case_id": c["case_id"], "request": r,
               "outcome": "success", "cert_kind": "CASE"}
              for c, r in entries]
    rules, parse_fails = [], 0
    try:
        for i in range(N):
            rule = adapter.propose_rule(domain, memory,
                                        domain.probe_request)
            if rule is None:
                parse_fails += 1
            rules.append(rule)
            print(f"  [{i+1}/{N}] {'ok' if rule else 'parse_failure'}",
                  flush=True)
    except Guard as g:
        print(f"[guard] {g}", flush=True)
    finally:
        raw_file.close()

    parsed = [r for r in rules if r]
    out = {"run_id": run_id, "n_calls": len(rules),
           "M0_parse_rate": round(len(parsed) / len(rules), 4),
           "pre_registered_sha256": pre_hash,
           "model": adapter.model, "prompt_cell": "cloudops|s0|episodic|k5",
           "usage": dict(adapter.usage), "http": ct.http_requests}
    if parsed:
        canon = [json.dumps(r, sort_keys=True) for r in parsed]
        counts: dict[str, int] = {}
        for c in canon:
            counts[c] = counts.get(c, 0) + 1
        modal_c, modal_n = max(counts.items(), key=lambda kv: kv[1])
        modal = json.loads(modal_c)
        mss = [sum(1 for x in domain.universe if matches(r, x))
               for r in parsed]
        modal_ms = sum(1 for x in domain.universe if matches(modal, x))
        verdicts = [oracle.rule_contained(r)[0] for r in parsed]
        modal_verdict = max(set(verdicts), key=verdicts.count)
        mc = modal.get("conditions", {})
        oms, rels = [], []
        for i, r in enumerate(parsed):
            rc = r.get("conditions", {})
            for k in mc:
                if k not in rc:
                    oms.append((i, k))
                elif json.dumps(rc[k]) != json.dumps(mc[k]):
                    rels.append((i, k))
        out.update({
            "M1_structural_modal": round(modal_n / len(parsed), 4),
            "n_distinct": len(counts),
            "M2_action_resource": round(
                sum(1 for r in parsed
                    if r["action"] == modal["action"]
                    and r["resource"] == modal["resource"]) / len(parsed),
                4),
            "M3_security_modal": round(
                sum(1 for v in verdicts if v == modal_verdict)
                / len(parsed), 4),
            "M3_boundary_crossing_rate": round(
                sum(1 for v in verdicts if v != modal_verdict)
                / len(parsed), 4),
            "M4_widening_freq": round(
                sum(1 for s in mss if s > modal_ms) / len(parsed), 4),
            "M4_narrower_freq": round(
                sum(1 for s in mss if s < modal_ms) / len(parsed), 4),
            "M5_omission_freq": round(
                len({i for i, _ in oms}) / len(parsed), 4),
            "M5_relaxation_freq": round(
                len({i for i, _ in rels}) / len(parsed), 4),
            "verdict_counts": {str(v): verdicts.count(v)
                               for v in set(verdicts)},
            "variant_counts": {k[:120]: v for k, v in counts.items()},
            "modal_rule": modal})
    (OUTDIR / "resample20.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items()
                      if k.startswith(("M", "usage", "http", "verdict"))},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
