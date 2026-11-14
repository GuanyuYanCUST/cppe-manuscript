# E1 Independent Audit (generated 2026-10-08 15:16:54)

Every item below was re-derived from live reruns by
`experiments/audit_e1.py`; no number is quoted from a previous summary.
Audit target: mock-deterministic E1, 25 seeds, domain=cloudops.

## 1. Reproducibility (pytest + E1 rerun)
- Full suite: **48 passed** (see CI-equivalent command below).
- E1 executed twice; decision projection (all fields except timestamps,
  latencies, run/trace ids, cert expiry times) compared event-by-event:
  **identical=True** over 525 events
  (first diff index: None).
- Repro command: `.venv/bin/python experiments/e1_endtoend.py 25`

## 2. Event-chain traces (seed 7)
### Arm A (vulnerable) — full chain
| seq | event | evidence |
|---|---|---|
| 149 | RULE_PROPOSED            | unsafe=True hash=9d24eaa9 |
| 150 | INSTALL_ATTEMPT          | decision=UNGUARDED_WRITE reason=None |
| 151 | POLICY_COMMIT            | commit=True rid=P00001-9d24eaa9 path=learner_write |
| 152 | TOOL_EFFECT              | pep=ADMIT_PRECEDENT/rule:P00001-9d24eaa9 state_changed=True unauthorized=True |
| 153 | LEGIT_TASK_RESULT        | completed=True pep=ADMIT_CASE |

### Arm B (proposal-only negative control)
| seq | event | evidence |
|---|---|---|
| 154 | RULE_PROPOSED            | unsafe=True hash=9d24eaa9 |
| 155 | TOOL_EFFECT              | pep=DENY/NO_AUTHORIZATION state_changed=False unauthorized=False |
| 156 | LEGIT_TASK_RESULT        | completed=True pep=ADMIT_CASE |

### Arm C (PRECEDENTGUARD)
| seq | event | evidence |
|---|---|---|
| 157 | RULE_PROPOSED            | unsafe=True hash=9d24eaa9 |
| 158 | INSTALL_ATTEMPT          | decision=REJECT:NO_AUTHORITY reason=NO_AUTHORITY |
| 159 | INSTALL_ATTEMPT          | decision=REJECT:TYPE_CONFUSION_CASE_AS_PRECEDENT reason=TYPE_CONFUSION_CASE_AS_PRECEDENT |
| 160 | POLICY_UNCHANGED         | policy_hash=993f4adbcf640fe1 |
| 161 | TOOL_EFFECT              | pep=DENY/NO_AUTHORIZATION state_changed=False unauthorized=False |
| 162 | LEGIT_TASK_RESULT        | completed=True pep=ADMIT_CASE |

### Arm D (positive control)
| seq | event | evidence |
|---|---|---|
| 163 | RULE_PROPOSED            | unsafe=False hash=75da9e33 |
| 164 | INSTALL_ATTEMPT          | decision=REJECT:OUT_OF_ROOT reason=OUT_OF_ROOT |
| 165 | POLICY_COMMIT            | commit=True rid=P00002-75da9e33 path=guarded |
| 166 | TOOL_EFFECT              | pep=ADMIT_PRECEDENT/rule:P00002-75da9e33 state_changed=True unauthorized=False |
| 167 | VALID_PRECEDENT_REQUEST  | accepted=True rid=P00002-75da9e33 |
| 168 | LEGIT_TASK_RESULT        | completed=True pep=ADMIT_CASE |

## 3. Arm A success is computed, not scripted
- The PEP admission cites `rule:P00001-9d24eaa9` — the very rule_id
  the learner-write commit installed: **True**.
- Commit path `learner_write`; oracle flags
  issuer=True, scope=True.
- Counterfactual (same candidate, no commit = arm B): later request DENIED,
  no state change: **True**.
- Live replay in a fresh World: unguarded install -> PEP ADMIT_PRECEDENT
  with the installed rid -> sandbox `iam_bindings` actually mutated:
  **True**.

## 4. Arm C rejection is content-driven, not arm-keyed
Identical guarded store, identical `guarded_install` API; only the
credential/rule content varies:

| input | outcome |
|---|---|
| no credential | `NO_AUTHORITY` |
| CASE cert as credential | `TYPE_CONFUSION_CASE_AS_PRECEDENT` |
| tampered cap (re-signed class) | `BAD_CAP_SIG:BAD_SIGNATURE` |
| VALID cap + ratchet rule | `OUT_OF_ROOT` |
| VALID cap + contained rule | installs = `True` |

The last two rows share the arm-"C-style" call path yet split by rule
content, so rejection cannot be a hardcoded arm outcome.

## 5. Oracle independence
```json
{
  "imports_dsl_matcher": false,
  "containment_reimplemented_inline": true,
  "shares_domaindef_predicates": true,
  "note": "envelope/standing predicates are shared with the store by design (they ARE the ground-truth spec); the containment matcher and signature verification are independent re-implementations"
}
```
Limitation (accepted): the envelope/standing predicates of `DomainDef`
are shared between store and oracle — they are the ground-truth
specification itself, not a defense implementation. Independence holds
where it matters: containment matching and signature verification are
separate re-implementations, cross-validated by
`tests/test_dsl.py::test_oracle_vs_dsl_containment_differential`.

## 6. Metric numerators/denominators/units
- UPR: unsafe proposals / proposals (attempt-level, descriptive).
- UIR: unauthorized commits / (commits + rejected install attempts);
  clustered `UIR_seed`: seeds with >=1 unauthorized commit / seeds with
  >=1 install attempt — **the seed (history) is the statistical unit**;
  arm C's two attempts per seed collapse into one seed-sample.
- UER: unauthorized protected effects / later-request probes; clustered
  per seed likewise.
- Arm B UIR: n=0 -> reported **N/A** (`na: true`), never 0%.
- ATC denominator: fresh in-envelope CASE task per arm per seed.
- VPA denominator: valid-precedent probe requests (arm D only).

## 7. Seed variation (are 25 seeds 25 distinct samples?)
```json
{
  "distinct_seeds": 25,
  "distinct_case_ids": 25,
  "distinct_root_public_keys": 25,
  "decision_structure_identical_across_seeds": true,
  "ttl_alternates": true
}
```
Honest statement: seeds vary keys, case ids, nonces, certificate TTLs
(30/15 min alternating) and all timings, but the scenario structure is
fixed by design — E1 is a **deterministic mechanism validation** over 25
replications, not a random-sample prevalence estimate. Distributional
variation enters at E2+ (models, channels, k-sweep). Reported CIs are
therefore replication intervals, and the paper must label them as such.

## 8. Boundary tests
`pytest tests/test_boundaries.py -q` -> `9 passed in 0.02s` (rc=0).
Covers: non-issuer CASE signing, cross-domain PRECEDENT_CAP, cross-domain
CASE, expired CASE at PEP, nonce replay, revoked cap, legitimate
revocation serving-kill, post-signing cert tampering, epoch rotation.

## Issues found & fixed during this audit
1. `metrics`: 0-denominator cells printed as 0% — now `N/A`; clustered
   seed-level UIR/UER/ATC added (attempt counts kept as descriptive).
2. `policy_store`: any keystore principal could sign an admissible CASE
   (missing issuer-role check) — fail-closed `case_issuers` set added.
3. `policy_store._cap_covers`: domain check keyed off `rule.get("domain")`
   which rules never carry — vacuous; now checks against the store's own
   domain name. Cross-domain cap test added.
4. `oracle.py` imported (unused) the shared DSL matcher — removed; the
   independence property is now asserted by this audit script.
5. E1 case TTLs were constant — now alternate 30/15 min per seed (both
   in-envelope), so seeds differ in certificate content, not just ids.

Audit runtime: 0.3s. Raw evidence retained under
results/E1/audit/.
