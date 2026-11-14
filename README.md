# PRECEDENTGUARD experiment framework (S&P 2027 artifact)

Reproducible framework for the CPPE (Case-to-Policy Privilege Escalation)
study.  Everything offline/mock runs with **zero API cost**; the LLM phase
is wired but refuses to run without explicit cost approval.

## Layout
```
src/pguard/        crypto, certs, dsl, dsl_formal, domains, policy_store,
                   oracle, monitor, tools, agent, baselines, llm_adapter,
                   trace, stats, metrics
experiments/       e1_endtoend.py    E1 end-to-end CPPE (4 arms)
                   e2_baselines.py   E2/E3 B0–B6+PG matched forks + k-sweep
                                     (also carries the E4 offline note:
                                     single mock model, aggregation degenerate)
                   e5_factorial.py   E5 Perfect Provenance 2×2
                   e6_adaptive.py    E6 five adaptive attacks × budgets
                   e7_ablation.py    E7 six component ablations
                   e8_dsl_stress.py  E8 DSL-A/B exhaustive stress
                   e9_robustness.py  E9 challenger corruption + overload
                   er_revocation.py  revocation dynamics (R1/R2/R3)
                   audit_e1.py       E1 independent audit report generator
tests/             pytest suite (76 tests)
results/           per-run JSONL traces + summary.json + MANIFEST.txt
                   (E1, E2, E5, E6, E7, E8, E9, ER subdirs)
scripts/           run_all_tests.sh
docs/              E1_INDEPENDENT_AUDIT.md, REAL_LLM_PILOT_PLAN.md,
                   prior paper text (reference)
```

## Quickstart
```
python3 -m virtualenv .venv && .venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest tests/ -q
.venv/bin/python experiments/e1_endtoend.py 25
.venv/bin/python experiments/e2_baselines.py     # ~10 s, 12,800 forks
.venv/bin/python experiments/e5_factorial.py
.venv/bin/python experiments/e6_adaptive.py
.venv/bin/python experiments/e7_ablation.py
.venv/bin/python experiments/e8_dsl_stress.py
.venv/bin/python experiments/e9_robustness.py
.venv/bin/python experiments/er_revocation.py
```

## Rules baked into the code
- No statistic is ever computed from anything but emitted JSONL traces.
- Mock model is tagged `mock-deterministic-v1`, `is_llm=false` in every
  event; LLM adapters raise unless explicitly enabled (`llm_adapter.py`
  supports a MockTransport for zero-network tests; paid pilot plan in
  `docs/REAL_LLM_PILOT_PLAN.md`).
- Baselines share every mechanism except their one defining enforced
  condition (`baselines.py`); no baseline is artificially weakened
  (B0/B5 CASE paths stay functional — ATC=1 in E2).
- Ablations are experiment-local subclasses/flags; production
  PolicyStore defaults are full PRECEDENTGUARD semantics.
- Crypto backend (`ed25519-pynacl` / `hmac-sha256`) recorded in every run
  manifest and trace.
- Rejected installs never mutate `policy_hash` (asserted in tests + E1).
- Zero-denominator metrics are N/A, never 0% (`na: true`).

## Real-model rollouts (frozen, included)
- results/real_{glm53,claude55,gemini38flash,deepseek41flash,gpt56}/
  - raw/rollout-*.jsonl — frozen request/response cache per call
    (ts, url, status, latency, payload; no credentials are stored)
  - rollouts/main/*.json — 4,000 legit + 1,000 attacker trajectories
    (5 arms x 4 domains x 4 memory channels x 50 seeds)
  - replay_v2/main.jsonl — 200,000 offline replay records per arm
    (8 methods x 5 k_req x 1,000 trajectories)
- results/real_qwen37plus/ is an empty placeholder (zero successful
  calls; excluded from all reported statistics).
- All paper statistics are recomputed offline from these frozen files;
  no network access is needed to re-run the replay or the analyses.
