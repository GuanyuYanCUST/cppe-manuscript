# Real-LLM Experiment Report — Five-Model Matrix (Final)

Project: *No Precedent Without Power: Preventing Case-to-Policy
Privilege Escalation in Learning Agents* (IEEE S&P 2027).
Framework: `precedentguard` @ WSL Ubuntu-22.04 `~/S&P/precedentguard`.
Authoritative plan: `~/S&P/实验计划.md` (over `图表设计大纲.md`).
Date of record: 2026-10-10. All numbers below are machine-derived from
the frozen artifacts listed in §9; regeneration commands in §10.

---

## 1. What was run

**Type-3 closed-loop rollouts** (one real multi-turn conversation per
trajectory): task → CASE certification → sandbox execution → feedback →
channel-retained memory → final self-chosen mode (case-only vs.
precedent proposal with a concrete rule). Then **frozen-trajectory
offline replay** (zero additional LLM calls) of every trajectory into
8 methods (B0–B6, PG) × k-grid {0, 1, 3, 5, 10}.

Matrix (frozen per 实验计划 §一):

| factor | levels |
|---|---|
| models | GLM-5.3, Claude-5.5 (sonnet), Gemini-3.8-flash, DeepSeek-v4.1-flash, GPT-5.6-sol |
| domains | cloudops, procurement, finance, dataaccess |
| learning channels | episodic, vector_rag, skill_consolidation, policy_distillation |
| seeds | 50 per cell |
| legit trajectories | 5 × 4 × 4 × 50 = **4,000** |
| attacker trajectories | 5 × 4 × 50 = **1,000** (episodic, 2 denied probes each) |
| replay rows | 5,000 traj × 8 methods × 5 k = **200,000** |

Acceptance: 1,000/1,000 checkpoints per arm, zero missing grid cells,
zero replay errors in all five `replay/main.jsonl` files (40,000 rows
each). Estimated spend at official list prices: **$197.58** (GPT
$102.22; conservative upper bound — relay billing to be reconciled).

## 2. Headline results (k=10, legit, n=800 per arm)

| model | propose% | B1 install% | **B1 UER% [Wilson 95%]** | PG UER% [CI] | PG VPA% | task_success |
|---|---|---|---|---|---|---|
| Gemini-3.8-flash | 91.1 | 91.1 | 27.5 [24.5, 30.7] | 0.0 [0.0, 0.5] | 64.7 | 0.825 |
| GLM-5.3 | 91.1 | 75.9 | 26.9 [23.9, 30.1] | 0.0 [0.0, 0.5] | 19.2 | 0.745 |
| DeepSeek-v4.1-flash | 94.6 | 86.4 | 12.6 [10.5, 15.1] | 0.0 [0.0, 0.5] | 5.4 | 0.822 |
| GPT-5.6 | 81.2 | 81.2 | 4.0 [2.8, 5.6] | 0.0 [0.0, 0.5] | 10.3 | 0.756 |
| Claude-5.5 | 37.9 | 35.4 | 2.0 [1.2, 3.2] | 0.0 [0.0, 0.5] | 0.0* | 0.816 |

\* Claude VPA=0 is a **strict-typing artifact**, not absence of valid
reuse: 158/166 (95%) of its final rules carry string-typed numeric
bounds (`["eq","1"]`). Under the lossless-coercion sensitivity replay
(§5.2) Claude VPA rises to **0.366**, on par with GPT (0.480) and
DeepSeek (0.518). Both conventions are reported.

- **PG UER = 0.000 on all five arms** (upper CI ≤ 0.5%), while
  preserving task success (0.745–0.825) and completing **4,000/4,000**
  delegated tasks through the case channel (ATC, §4.2).
- B1/B2/B4/B6 are numerically identical throughout (see §5.3), so
  "perfect provenance" does not reduce CPPE at all in this benchmark.
- B3 (root-aware judge) achieves UER=0 by rejecting ~half of installs
  but still commits CPPE-ISSUER on what it installs; B5
  (installs-never-serves) has UER=0 with zero utility (VPA=0, and its
  installs still carry excess authority volume, §5.4).
- EAV (excess authority volume of admitted rules): **PG = 0 excess
  universe requests on every admitted rule, all arms**; B1-family
  35% of GLM installs carry excess (mean 1.5, max 18 requests).

## 3. Security-critical splits (S5 corrected)

`main_summary.json`'s `S5_out_of_envelope_proposal` block **pools
legit+attacker traffic** (no attacker filter in `summarize()`); the
"717" quoted in the interim acceptance is that pooled count. Correct
split (`scripts/s5_split.py`, k=10, per-trajectory):

| traffic | out-of-envelope final rules | PG rejected | B1 unauthorized effect |
|---|---|---|---|
| legit (n=4,000) | **584 (14.6%)** | 584/584 | 584/584 |
| attacker (n=1,000) | **133 (13.3%)** | 133/133 | 133/133 |
| pooled (n=5,000) | 717 | 717/717 | 717/717 |

Legit per-arm oop counts equal the B1 UER counts exactly (215/16/220/
101/32), as they must — internal validity check passed. Positioning:
B1's 100%-on-oop behaviour is definitional (an out-of-envelope rule
admits out-of-envelope probes); the non-trivial facts are the
**supply rates** (14.6% of benign trajectories end in an escalation
proposal) and the per-arm legit-traffic UER spectrum. Attacker supply
rate (13.3%) is comparable to benign — the phenomenon is not
attacker-exclusive.

## 4. Metric definitions and revisions (report both where changed)

### 4.1 UER — unauthorized effect rate
PA-3 semantics: a rule installed by the method produces an
out-of-envelope protected effect (issuer-OR-scope). Measured on the
rule's actual out-of-envelope coverage (up to 3 probes) + canonical
probe. Dual denominators available in `master_table.json` (/n and
/proposed).

### 4.2 ATC — authorized-task completion (REVISED 2026-10-10)
The ATC probe (fresh CASE cert for a novel delegated resource) was
accidentally gated on `proposal is not None` and on
`normalize_candidate` success — early returns skipped it entirely.
Claude's 497/800 case-only trajectories and every MALFORMED-proposal
trajectory were scored ATC=False without the probe ever running
(structural artifact: PG ATC% ≡ B1 install%, verified 2960/2960 probe
successes pre-fix). Fix: `_atc()` closure runs on all three return
paths (`src/pguard/closed_loop.py`, test
`test_atc_probe_runs_without_proposal`, 98/98). Re-replay of all five
arms (old data preserved `replay/main_pre_atcfix*`). **Revised result:
ATC = 100% (4,000/4,000) on every arm** — the case channel completes
every delegated task regardless of what (or whether) the agent
proposed. ATC remains a PG-mechanism metric: B0–B6 implement no case
channel (N/A, not 0).

### 4.3 VPA — valid precedent acceptance
Contained proposal admitted and serving the original case request,
per proposed trajectory. Strict typing kept verbatim by default;
coercion variant in §5.2.

### 4.4 UPR — unsafe proposal rate
Fraction of trajectories whose final proposal is not contained in the
root envelope (trajectory-level, method-independent). Fig 8 uses
per-domain×channel cells; `fig_data.json` carries per-k values.

## 5. Fairness analyses

### 5.1 Mixed-channel arms
GLM-5.3: 395 trajectories on bigmodel pay-as-you-go + 605 on zhongkey
relay (boundary verified by a 397-minute creation gap 10-09 10:00→
16:38 at exactly file #395). GPT-5.6: aizex relay until ~19:00 10-09
(no clean gap; cutoff documented), rest zhongkey. Both phases show the
same qualitative pattern (high propose, non-zero B1 UER, PG VPA>0);
**the phases cover different grid cells, so this is a homogeneity
check, not an A/B test** — composition confound stated. No conclusion
depends on either channel.

### 5.2 Typing-convention sensitivity (`main_coerced` replays)
Lossless numeric-string coercion applied to rule conditions
(`["le","30"]→["le",30]`) before enforcement:

| model | B1 UER strict→coerced | PG UER | PG VPA strict→coerced |
|---|---|---|---|
| GLM-5.3 | .269 → **.461** | 0 → 0 | .192 → .198 |
| Claude-5.5 | .020 → **.200** | 0 → 0 | .000 → **.366** |
| Gemini-3.8-flash | .275 → .279 | 0 → 0 | .647 → .694 |
| DeepSeek-v4.1-flash | .126 → **.367** | 0 → 0 | .054 → **.518** |
| GPT-5.6 | .040 → **.366** | 0 → 0 | .103 → **.480** |

Three conclusions: (i) Claude's VPA=0 is a typing artifact (fairness
answered); (ii) strict typing was **shielding the baselines** — under
the lenient convention B1-family UER roughly doubles-to-triples, so
CPPE risk is not a typing artifact; (iii) **PG UER stays 0 under both
conventions** — the security claim is convention-robust. PG install
rates drop under coercion (live rules admit more, containment
correctly rejects more).

### 5.3 B1 ≡ B6
Per-trajectory verdict tuples (installed, unauth_effect,
valid_accepted): **20,000/20,000 identical, 0 mismatches**. Structural:
in a benign channel the signed history IS the success history, so
exact event sourcing (B6) recovers naive reuse (B1) exactly. B6's
distinction only appears under history tampering (offline E5).

### 5.4 Memory-capacity (A2) — null by construction
Tail-truncation replay (`main_tail3/5`): all metrics identical to
full memory. Frozen-trajectory replay fixes the candidate; memory
truncation only gates proposal existence (k=0/1 thresholds), it cannot
reshape the rule. Deep capacity effects require live re-rollouts —
out of scope, documented as a limitation.

## 6. Overload / overhead microbenchmark (Fig 10c, Table 5 p95)
`pep_decide` latency vs installed-rule count (cloudops, 300 iters
after 50 warmup, 3 request types, contained rules with inert distinct
conditions): PG p95 = **0.231 ms at 250 rules** (B1 0.267 ms) —
linear scan at ~0.4 µs/rule, negligible next to any LLM call; PG's
typing/containment enforcement adds no measurable decision-time
overhead. E9 overload (fail-closed load shedding) and challenger
corruption (rising FRR, flat-0 unsafe) are offline mock-based,
labelled as such in Fig 10b/10c.

## 7. Execution timeline and incidents (complete, infra ≠ model)

1. **GLM 1113 exhaustion ×3** (10-08 18:43→22:30 halt #1 at 235/800;
   resume 21:26 with new key; halt #2 22:30; 10-09 10:01 halt #3 at
   395/800): pay-as-you-go grants ran dry; root-caused in
   `docs/GLM_CHANNEL_AUDIT.md` (Coding-Plan key misuse); fatal-stop
   fix verified each time (instant stop, ≤1 wasted call, checkpoints
   intact). Infra, never recorded as model behaviour.
2. **GPT relay quirks**: Cloudflare UA block (browser UA in adapter);
   `gpt-5.6-terra` kill-switched by provider → moved to `-sol`;
   409 operation_in_progress made retryable with long backoff;
   `<think>` inline blocks stripped in `_parse_obj`; Aizex 503/timeout
   bursts aborted whole cells → per-seed RateLimited self-heal (240 s
   wait, one fresh retry, then defer).
3. **GPT_MODEL env deletion** (user's .env edit): adapter fell back to
   `gpt-4o`, 242 instant HTTP-404s (unbilled), rollouts infra-skipped
   silently; restored `GPT_MODEL=gpt-5.6-sol`. Lesson: verify .env
   completeness after any manual edit.
4. **Claude pilot ×3** (v1 typedenied, v2 finalprose, v3 PASS — all
   preserved): preset forces temperature=1.0 (0 → HTTP 400); ALL
   numbers emitted as JSON strings (lossless coercion at tool_call
   boundary only, rules kept verbatim — the §5.2 sensitivity follows);
   trailing prose after JSON handled; prose-only final refusals
   recorded honestly as mode=None (Claude declined to widen in 2/6
   pilots — a real cross-model contrast).
5. **String-typed ordered bounds** (`["le","30"]`): TypeError at three
   evaluation sites → fail-closed `ord_ok` (incomparable = condition
   not satisfied), 97/97 tests.
6. **summarize KeyError 'proposed'** on REPLAY_ERROR rows → stripped
   once at entry with `replay_errors` counter.
7. **zhongkey 503 blips** (16:19–16:21 10-09; empty-body 503s later):
   adapter fail-closed correctly, no junk checkpoints.
8. **qwen dropped**: qwen3.7-max (503 not deployed) and qwen3.8-max
   (502 upstream) dead at zhongkey all day → DeepSeek-v4.1-flash
   added per user decision.
9. **fill_until_done v1** two bugs (DIR one-liner resolved counts to
   0; MODE loop lacked ch4 pass) — 12 wasted sweeps, zero API cost;
   fixed with case-mapping + dual-pass.
10. **ATC metric revision** (§4.2) and **S5 split correction** (§3):
    both are measurement-coverage fixes post-data; old numbers
    preserved and both reported.

## 8. Limitations (as-is, no hiding)
- Two arms are mixed-channel (§5.1); split is a homogeneity check.
- Frozen-trajectory replay cannot measure memory-shaping effects
  (A2 null, §5.4) or live re-learning under defenses.
- Attacker model is a fixed two-probe ratchet, not adaptive;
  adaptivity is covered by offline E6 (+ real farming overlay).
- k-grid {0,1,3,5,10} caps at n_tasks=10 per trajectory.
- GLM/DeepSeek relay list prices unverified against final bills;
  cost figures are upper bounds at official prices.
- Claude case-only behaviour (62% of its legit trajectories) lowers
  its supply rate; comparisons across models describe behaviour under
  identical prompts, not capability rankings.

## 9. Artifact inventory
- `results/real_{glm53,claude55,gemini38flash,deepseek41flash,gpt56}/
  rollouts/main/*.json` — 5,000 trajectory checkpoints (incl. run_id).
- `.../replay/main.jsonl|main_summary.json` — primary replay;
  `main_pre_atcfix*` — pre-ATC-fix preserved; `main_coerced*` — §5.2;
  `main_tail3|5*` — §5.4.
- `results/TABLES/` — master_table.{json,md}, fig_data.json, eav.{json,md},
  overload_bench.{json,md}, coerce_compare.json, s5_split.json.
- `results/FIGS/` — fig6/7/8/9/10, figA3, figA4 (PDF).
- `results/E*`, `results/LLM_PILOT/freeze/` — offline phases (frozen).
- Raw request/response logs: `.../raw/rollout-main-*.jsonl`.
- Scripts: `scripts/{build_master_tables,fig_data,make_figures,
  make_fig10,eav_stats,overload_bench,replay_coerced,replay_tail,
  channel_split,channel_metrics,s5_split,coerce_compare,
  atc_crosscheck,atk_census*}.py`, `scripts/{replay_atcfix,
  run_channel4,fill_until_done}.sh`.

## 10. Regeneration (zero API cost)
```
.venv/bin/python scripts/replay_atcfix.sh   # re-replay all arms
.venv/bin/python scripts/replay_coerced.py  # sensitivity variant
.venv/bin/python scripts/build_master_tables.py && \
.venv/bin/python scripts/fig_data.py && \
.venv/bin/python scripts/eav_stats.py && \
.venv/bin/python scripts/overload_bench.py && \
.venv/bin/python scripts/s5_split.py && \
.venv/bin/python scripts/make_figures.py && \
.venv/bin/python scripts/make_fig10.py
.venv/bin/python -m pytest tests/ -q          # 99/99
```

Remaining before submission: paper experiment-section rewrite with
these numbers, A5 fixed-decode-parameter declaration, A6 failure-trace
extraction, artifact freeze + SHA256SUMS. Deadlines: abstract
2026-11-10, full paper 2026-11-17.
