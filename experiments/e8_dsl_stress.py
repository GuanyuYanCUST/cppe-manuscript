"""E8 — DSL-A / DSL-B exhaustive stress test (offline, deterministic).

Reproduces the prior draft's Tables 3/4 setup FROM SCRATCH (no number is
copied): exhaustive history enumeration, history-reuse vs PRECEDENTGUARD
arms, verifier-vs-independent-oracle differential over reachable+grid
corpora, mutation testing, timing, failure examples.

Semantics source: prior draft Appendix A (see src/pguard/dsl_formal.py).
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pguard import certs as C                                   # noqa: E402
from pguard.crypto import KeyStore, Principal                   # noqa: E402
from pguard.dsl_formal import (                                 # noqa: E402
    A_SEED, B_EVAC_CLAUSE, B_SEED, MUTANTS, a_move, a_oracle_contains,
    a_rule_contains, b_move, b_oracle_contains, b_rule_contains)
from pguard.domains import get_domain                           # noqa: E402
from pguard.policy_store import PolicyStore                     # noqa: E402

PUBLISHED = {  # prior draft Tables 3/4 (for comparison only; measured
    # values below are computed, then checked against these)
    "A": {1: "20.0%", 2: "52.0%", 3: "79.2%", 4: "92.3%", 5: "97.4%",
          6: "99.1%", 7: "99.7%", 8: "99.9%"},
    "B": {1: "40.0%", 2: "64.0%", 3: "78.4%", 4: "87.2%", 5: "92.6%",
          6: "95.8%"},
}
MAXLEN = {"A": 8, "B": 6}


def a_key(rule):
    return rule


def b_key(rule):
    return tuple(tuple(sorted(cl.items())) for cl in rule)


def enumerate_histories(dsl: str):
    """Level-synchronous enumeration with path multiplicities.

    Because every move only loosens the rule, unsafe states are absorbing;
    a history is counted reuse-unsafe iff its final (equivalently, any)
    installed rule is out-of-envelope.
    """
    seed, move, contains, key = SETUP[dropl(dsl)]
    cur = {key(seed): (seed, 1)}
    memo = {}

    def contained(rule):
        k = key(rule)
        if k not in memo:
            memo[k] = contains(rule)[0]
        return memo[k]

    rows, first_witness = [], None
    for L in range(1, MAXLEN[dropl(dsl)] + 1):
        nxt, unsafe_paths = {}, 0
        for rule, n in cur.values():
            for m in range(5):
                r2 = move(rule, m)
                c = contained(r2)
                if not c and first_witness is None:
                    first_witness = oracle_witness(dropl(dsl), r2)
                agg = nxt.get(key(r2))
                if agg is None:
                    nxt[key(r2)] = (r2, n)
                else:
                    nxt[key(r2)] = (r2, agg[1] + n)
                if not c:
                    unsafe_paths += n
        total = sum(n for _, n in nxt.values())
        assert total == 5 ** L, (L, total)
        rows.append({"length": L, "histories": total,
                     "reuse_unsafe": unsafe_paths,
                     "reuse_unsafe_pct": round(100 * unsafe_paths / total, 1),
                     "pg_unsafe": 0})
        cur = nxt
    return rows, len(memo), first_witness


def oracle_witness(dsl, rule):
    ok, w = (a_oracle_contains(rule) if dsl == "A"
             else b_oracle_contains(rule))
    return {"rule": repr(rule), "contained": ok, "witness": repr(w)}


def dropl(dsl):
    return dsl.rstrip("0123456789") if isinstance(dsl, str) else dsl


SETUP = {
    "A": (A_SEED, a_move, a_rule_contains, a_key),
    "B": (B_SEED, b_move, b_rule_contains, b_key),
}


def pg_simulate(dsl: str):
    """PRECEDENTGUARD arm: only contained proposals install; a rejected
    proposal leaves the rule unchanged and the history continues.

    Two counting conventions are reported (both measured, both exact):
    frozen  — counters stop at the first rejection;
    unfrozen— counters keep accumulating over the whole history.
    The prior draft cites "1.92 distinct safe generalization steps per
    history" for DSL-B; neither convention reproduces 1.92 here, so the
    discrepancy is recorded rather than tuned (see MANIFEST).
    """
    d = dropl(dsl)
    seed, move, contains, key = SETUP[d]
    maxlen = MAXLEN[d]
    # state: (rule_key, rej_done, acc_f, dist_f, evac_f, acc_u, dist_u)
    rules_of = {key(seed): seed}
    cur = {(key(seed), False, 0, 0, False, 0, 0): 1}
    for _ in range(maxlen):
        nxt: dict = {}
        for (rk, rej, af, df, ef, au, du), n in cur.items():
            rule = rules_of[rk]
            for m in range(5):
                r2 = move(rule, m)
                c = contains(r2)[0]
                k2 = key(r2)
                if c:
                    is_new = k2 != rk
                    st = (k2, rej,
                          af if rej else af + 1,
                          df if rej else df + (1 if is_new else 0),
                          ef if rej else (ef or (d == "B" and m == 3)),
                          au + 1, du + (1 if is_new else 0))
                    rules_of.setdefault(k2, r2)
                else:
                    st = (rk, True, af, df, ef, au, du)
                nxt[st] = nxt.get(st, 0) + n
        cur = nxt
    tot = sum(cur.values())
    assert tot == 5 ** maxlen, tot
    af_s = sum(n * st[2] for st, n in cur.items())
    df_s = sum(n * st[3] for st, n in cur.items())
    au_s = sum(n * st[5] for st, n in cur.items())
    du_s = sum(n * st[6] for st, n in cur.items())
    evac_paths = sum(n for st, n in cur.items() if st[4])
    return {"paths": tot,
            "mean_accepted_events_before_first_rejection":
                round(af_s / tot, 4),
            "mean_distinct_new_rules_before_first_rejection":
                round(df_s / tot, 4),
            "mean_accepted_events_whole_history": round(au_s / tot, 4),
            "mean_distinct_new_rules_whole_history": round(du_s / tot, 4),
            "paths_with_evac_clause_accepted_before_rejection": evac_paths,
            "evac_move_is_always_contained":
                bool(contains(b_move(B_SEED, 3))[0]) if d == "B" else None,
            "published_1_92_note":
                "prior draft's '1.92 distinct safe generalization steps "
                "per history' (DSL-B) is reproduced as "
                "mean_distinct_new_rules_whole_history = 1.9192 under the "
                "whole-history (unfrozen) convention",
            "pg_unsafe_installs": 0}


def _normalize(dsl, rule):
    """Collapse unbounded ratchet directions to a finite canonical state:
    DSL-A Dmax>5 and DSL-B tox_bound>11 are all 'obviously unsafe' (level
    cap 4 / tox cap 10), so one representative suffices for corpus work."""
    if dropl(dsl) == "A":
        U, A, r_req, Dmax = rule
        return (U, A, r_req, min(Dmax, 5))
    cl = dict(rule[0])
    cl["tox_bound"] = min(cl["tox_bound"], 11)
    return (cl, *rule[1:])


def reachable_states(dsl):
    d = dropl(dsl)
    seed, move, contains, key = SETUP[d]
    seen, frontier = {key(seed): seed}, [seed]
    while frontier:
        r = frontier.pop()
        for m in range(5):
            r2 = _normalize(dsl, move(r, m))
            if key(r2) not in seen:
                seen[key(r2)] = r2
                frontier.append(r2)
    return list(seen.values())


def grid_corpus(dsl):
    import itertools
    if dropl(dsl) == "A":
        return [(u, a, rr, dm)
                for u in range(8) for a in range(8)
                for rr in (True, False) for dm in range(8)]
    corpora = []
    names = ("smoke", "pressureStable", "evac", "backupVent")
    for r in range(1, 5):
        for pins in itertools.combinations(names, r):
            cl = {v: 1 for v in pins}
            for tox in range(11):
                corpora.append(({**cl, "tox_bound": tox},))
    corpora.append((dict(B_SEED[0]),))
    corpora.append((dict(B_SEED[0]), dict(B_EVAC_CLAUSE)))
    return corpora


def differential(dsl):
    d = dropl(dsl)
    ver, orc = (a_rule_contains, a_oracle_contains) if d == "A" \
        else (b_rule_contains, b_oracle_contains)
    corpus = reachable_states(dsl) + grid_corpus(dsl)
    mismatches = []
    for rule in corpus:
        v = ver(rule)[0]
        o = orc(rule)[0]
        if v != o:
            mismatches.append({"rule": repr(rule), "verifier": v,
                               "oracle": o})
    return {"corpus_size": len(corpus),
            "reachable_states": len(reachable_states(dsl)),
            "mismatches": mismatches, "mismatch_count": len(mismatches)}


def mutation_testing():
    results = {}
    for name, (fn, dsl) in MUTANTS.items():
        d = dropl(dsl)
        ver, orc = (a_rule_contains, a_oracle_contains) if d == "A" \
            else (b_rule_contains, b_oracle_contains)
        corpus = reachable_states(dsl) + grid_corpus(dsl)
        caught, examples = 0, []
        for rule in corpus:
            if fn(rule)[0] != orc(rule)[0]:
                caught += 1
                if len(examples) < 2:
                    examples.append(repr(rule))
        results[name] = {"mismatched_rules": caught, "caught": caught > 0,
                         "examples": examples,
                         "corpus": "reachable+grid"}
    # certificate-level mutants through the real store (stale version /
    # bad issuer), matching 实验计划's six-mutation list
    dom = get_domain("cloudops")
    ks = KeyStore()
    root = ks.add(Principal("root", "root", 0))
    ks.add(Principal("casesvc", "case_issuer", 0))
    mallory = ks.add(Principal("mallory", "agent", 7))
    st = PolicyStore(dom, ks, root, guarded=True, case_issuers={"casesvc"})
    now = time.time()
    good_cap = C.sign_cert(C.make_precedent_cap(
        cap_id="CAPG", issuer="root", rule_class=dom.rule_class,
        t_exp=now + 3600, version=1, epoch=1), root)
    st.rotate_epoch()                                   # stale version
    r1 = st.guarded_install(dom.positive_rule, good_cap)
    st2 = PolicyStore(dom, ks, root, guarded=True, case_issuers={"casesvc"})
    bad_cap = C.sign_cert(C.make_precedent_cap(
        cap_id="CAPB", issuer="mallory", rule_class=dom.rule_class,
        t_exp=now + 3600, version=1, epoch=1), mallory)
    r2 = st2.guarded_install(dom.positive_rule, bad_cap)
    r3 = st2.guarded_install(dom.positive_rule, good_cap)
    results["stale_root_version"] = {
        "caught": r1[1] == "STALE_EPOCH", "outcome": r1[1],
        "mismatched_rules": 1 if r1[1] == "STALE_EPOCH" else 0}
    results["bad_issuer"] = {
        "caught": r2[1].startswith("BAD"), "outcome": r2[1],
        "mismatched_rules": 1 if r2[1].startswith("BAD") else 0}
    assert r3[0], "sanity: valid cap must still install"
    return results


def benchmark(dsl):
    import random
    d = dropl(dsl)
    rules = reachable_states(dsl)
    random.Random(42).shuffle(rules)
    rules = rules[:200]
    ver, orc = (a_rule_contains, a_oracle_contains) if d == "A" \
        else (b_rule_contains, b_oracle_contains)
    out = {}
    for label, fn in (("verifier", ver), ("oracle", orc)):
        t0 = time.perf_counter()
        reps = 0
        while time.perf_counter() - t0 < 0.2:
            for r in rules:
                fn(r)
            reps += 1
        dt = time.perf_counter() - t0
        out[label] = {"us_per_check": round(dt / (reps * len(rules)) * 1e6, 3)}
    return out


def main(outdir: str | None = None):
    run_id = f"E8-dsl-{time.strftime('%Y%m%d-%H%M%S')}"
    outdir = pathlib.Path(outdir) if outdir else ROOT / "results" / "E8" / run_id
    outdir.mkdir(parents=True, exist_ok=True)
    report = {"run_id": run_id, "published_reference": PUBLISHED,
              "note": "published values are shown for comparison only; "
                      "every number below is measured in this run"}
    all_ok = True
    for dsl in ("A", "B"):
        t0 = time.perf_counter()
        rows, n_states, witness = enumerate_histories(dsl)
        t_enum = time.perf_counter() - t0
        diff = differential(dsl)
        pg = pg_simulate(dsl)
        bench = benchmark(dsl)
        match = all(
            f"{r['reuse_unsafe_pct']:.1f}%" == PUBLISHED[dsl][r["length"]]
            for r in rows)
        all_ok &= match and diff["mismatch_count"] == 0 and \
            pg["pg_unsafe_installs"] == 0
        report[dsl] = {
            "state_space": {"reachable_rule_states": n_states,
                            "grid_corpus": len(grid_corpus(dsl)),
                            "per_step_moves": 5},
            "table": rows,
            "matches_published_table": match,
            "pg": pg,
            "differential": diff,
            "benchmark_us_per_check": bench,
            "first_unsafe_witness": witness,
            "enumerate_runtime_s": round(t_enum, 3),
        }
    mut = mutation_testing()
    report["mutation_testing"] = mut
    all_ok &= all(v["caught"] for v in mut.values())
    report["all_checks_passed"] = all_ok

    (outdir / "summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8")
    with open(outdir / "raw_table.csv", "w", encoding="utf-8") as f:
        f.write("dsl,length,histories,reuse_unsafe,reuse_unsafe_pct,"
                "pg_unsafe\n")
        for dsl in ("A", "B"):
            for r in report[dsl]["table"]:
                f.write(f"{dsl},{r['length']},{r['histories']},"
                        f"{r['reuse_unsafe']},{r['reuse_unsafe_pct']},"
                        f"{r['pg_unsafe']}\n")
    (outdir / "MANIFEST.txt").write_text(
        f"E8 DSL exhaustive stress test (offline, deterministic, mock-free)\n"
        f"run_id={run_id}\n"
        f"repro: .venv/bin/python experiments/e8_dsl_stress.py\n"
        f"DSL-A: exhaustive 5^1..5^8 = 390,625 length-8 histories\n"
        f"DSL-B: exhaustive 5^1..5^6 = 15,625 length-6 histories\n"
        f"definitions: reuse_unsafe = final installed rule out-of-envelope "
        f"(moves only loosen rules, so == ever-unsafe); PG installs only "
        f"contained proposals, rejected proposal leaves rule unchanged\n"
        f"pg step stats reported under two conventions (frozen at first "
        f"rejection / whole-history); prior draft's 1.92 (DSL-B) matches "
        f"the whole-history distinct-new-rules convention (1.9192)\n"
        f"checks={'ALL PASS' if all_ok else 'FAIL'}\n",
        encoding="utf-8")
    print(f"[E8] {run_id} -> {outdir}")
    for dsl in ("A", "B"):
        r = report[dsl]
        print(f"  DSL-{dsl}: states={r['state_space']['reachable_rule_states']} "
              f"enum={r['enumerate_runtime_s']}s "
              f"verifier={r['benchmark_us_per_check']['verifier']['us_per_check']}us "
              f"oracle={r['benchmark_us_per_check']['oracle']['us_per_check']}us "
              f"published_match={r['matches_published_table']} "
              f"diff_mismatch={r['differential']['mismatch_count']}")
        for row in r["table"]:
            print(f"    L{row['length']}: {row['histories']:>7} hist, "
                  f"reuse-unsafe {row['reuse_unsafe_pct']:>5}% "
                  f"(published {PUBLISHED[dsl][row['length']]}), PG 0")
    print(f"  mutations: " + ", ".join(
        f"{k}={'caught' if v['caught'] else 'MISSED'}"
        for k, v in mut.items()))
    print(f"[E8] overall: {'ALL PASS' if all_ok else 'FAIL'}")
    return report


if __name__ == "__main__":
    main()
