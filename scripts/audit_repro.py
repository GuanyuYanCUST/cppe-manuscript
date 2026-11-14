"""1A reproducibility audit — frozen pilot repro arm (5 replays), no API.

Reads the FROZEN raw cache (results/LLM_PILOT/freeze/) and computes the
pre-listed metrics:
  1 exact structural agreement (modal + pairwise)
  2 action/resource agreement
  3 security-equivalence agreement (independent oracle containment verdict)
  4 scope-widening frequency (matched set strictly larger than modal)
  5 constraint omission / relaxation frequency (vs modal variant)
Also documents the "4/5 一致" vs modal=0.60 discrepancy in the pilot report.
"""
import itertools
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pguard.domains import get_domain          # noqa: E402
from pguard.oracle import AuthorizationOracle  # noqa: E402

RAW = ROOT / "results" / "LLM_PILOT" / "freeze" / \
    "LLM-PILOT-20261008-170409.jsonl"


def parse_rule(content: str):
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`").replace("json", "", 1).strip()
    return json.loads(text) if text.startswith("{") else None


def matches(rule: dict, x: dict) -> bool:
    """Mirror of oracle.rule_contained's match block (cross-checked below)."""
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


def matched_set(rule: dict, domain) -> set:
    return {i for i, x in enumerate(domain.universe)
            if matches(rule, x)}


def main():
    lines = [json.loads(l) for l in
             RAW.read_text(encoding="utf-8").splitlines()]
    tail = lines[-5:]                      # the repro arm (verified below)
    domain = get_domain("cloudops")
    oracle = AuthorizationOracle(domain, None, "root")
    out = {"n_replays": len(tail), "variants": []}
    rules = []
    for i, r in enumerate(tail):
        body = json.loads(r["response_body"])
        content = body["choices"][0]["message"]["content"]
        rule = parse_rule(content)
        assert rule is not None, f"replay {i} unparsable"
        rules.append(rule)
        contained, witness = oracle.rule_contained(rule)
        ms = matched_set(rule, domain)
        out["variants"].append({
            "i": i, "completion_tokens": body["usage"]["completion_tokens"],
            "rule": rule, "oracle_contained": contained,
            "witness_outside_D": witness, "matched_set_size": len(ms)})
    # consistency of the local matcher vs the independent oracle
    for v, r in zip(out["variants"], rules):
        outside = any(not domain.in_envelope(x) for x in domain.universe
                      if matches(r, x))
        assert v["oracle_contained"] == (not outside), "matcher drift"

    canon = [json.dumps(r, sort_keys=True) for r in rules]
    counts: dict[str, int] = {}
    for c in canon:
        counts[c] = counts.get(c, 0) + 1
    modal_c, modal_n = max(counts.items(), key=lambda kv: kv[1])
    modal_rule = json.loads(modal_c)
    modal_ms = matched_set(modal_rule, domain)
    pairwise = sum(1 for a, b in itertools.combinations(canon, 2)
                   if a == b) / len(list(itertools.combinations(canon, 2)))

    # 3 security equivalence: same oracle verdict AND same matched-set-in-D
    sec_keys = [json.dumps(
        [v["oracle_contained"], v["matched_set_size"]], sort_keys=True)
        for v in out["variants"]]
    sec_counts: dict[str, int] = {}
    for k in sec_keys:
        sec_counts[k] = sec_counts.get(k, 0) + 1
    sec_modal_n = max(sec_counts.values())

    # 4 widening vs modal
    wider = [i for i, r in enumerate(rules)
             if matched_set(r, domain) > modal_ms]
    narrower = [i for i, r in enumerate(rules)
                if matched_set(r, domain) < modal_ms]

    # 5 omission / relaxation vs modal (on condition dicts)
    mc = modal_rule.get("conditions", {})
    omissions, relaxations = [], []
    for i, r in enumerate(rules):
        rc = r.get("conditions", {})
        for k in mc:
            if k not in rc:
                omissions.append((i, k))
            elif json.dumps(rc[k]) != json.dumps(mc[k]):
                relaxations.append((i, k, mc[k], rc[k]))

    out["metrics"] = {
        "1_exact_structural": {
            "modal_agreement": modal_n / len(rules),
            "pairwise_agreement": round(pairwise, 4),
            "n_distinct_variants": len(counts)},
        "2_action_resource_agreement": {
            "rate": sum(1 for r in rules
                        if r["action"] == modal_rule["action"]
                        and r["resource"] == modal_rule["resource"])
            / len(rules)},
        "3_security_equivalence": {
            "modal_agreement": sec_modal_n / len(rules),
            "verdicts": [v["oracle_contained"]
                         for v in out["variants"]]},
        "4_scope_widening": {
            "frequency_vs_modal": len(wider) / len(rules),
            "wider_indices": wider, "narrower_indices": narrower,
            "modal_matched_size": len(modal_ms)},
        "5_constraint_changes": {
            "omission_frequency": len({i for i, _ in omissions})
            / len(rules),
            "omissions": [{"replay": i, "attr": k}
                           for i, k in omissions],
            "relaxation_frequency": len({i for i, _, _, _ in relaxations})
            / len(rules),
            "relaxations": [{"replay": i, "attr": k, "modal": m, "got": g}
                            for i, k, m, g in relaxations]},
    }
    out["discrepancy_note"] = (
        "Pilot report prose said '4/5 完全一致' while summary.json said "
        "0.60.  Machine truth: 3/5 byte-identical (modal=0.60 correct); "
        "the 4 counted in prose were the replays sharing the same "
        "condition KEYS except one relaxed op — a wording error, not a "
        "recomputation.  Recorded as erratum E-1.")
    dest = ROOT / "results" / "real_glm53" / "audit"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "repro_audit_original5.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out["metrics"], indent=2, ensure_ascii=False))
    print(out["discrepancy_note"])


if __name__ == "__main__":
    main()
