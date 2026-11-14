# Fig.6 v4 (bar-chart version) — scientific review and provenance

Generated 2026-10-10 by `scripts/fig6_bar_data_v4.py` +
`scripts/make_fig6_bar_v4.py` (this session, matplotlib 3.10.9).
A parallel delivery produced earlier the same day by a concurrent session
(Origin 2026) is preserved as `fig6_bar_review_origin_session.md` and
`*.opju` / `*_origin_report.json`; the numbers in both deliveries agree
on every guard checkpoint. Same-name PDF/SVG/PNG/CSV in this directory
are this session's matplotlib render (they overwrote the concurrent
session's same-name exports — see INCIDENT at the bottom).

## Data provenance and guards

- Source: the five `results/real_*/replay_v2/main.jsonl` (frozen), read-only.
  Filter: `attacker==False, k_req==10, method in {B1,B2,B3,B4,B6,PG}` →
  4,000 legitimate trajectories per method, 800 per model, 200 per
  model×domain. Percentages are recomputed by counting rows; no summary.md
  or prior-figure number is consumed anywhere in the pipeline.
- Identity guards: unique (model,domain,channel,seed,method) keys; every
  method arm pairs sample-for-sample with B1; B1/B2/B4/B6 verdict fields
  (installed, issuer, scope, unauth) identical per sample — one shared
  unguarded-install mechanism, four specs, never drawn as four baselines.
- Cross-check: every panel figure is matched cell-for-cell against
  `audit_20261010/gates/cell_verify_v3.json` (via explicit model-name
  aliasing, not positional zip). Headline guards re-derive all 11 pinned
  counts (4000 / 3168 / 2960 / 2960 / 2362 / 598 / 584 / 2275 / 720 / 0
  / per-model proposed 650-303-729-729-757) and reject any mismatch.
- B3 issuer-unsafe rate is 2362/4000 = **59.05%** (the metrics contract's
  "58.05%" is a typo; the guard asserts 59.05 to 3 decimals).
- Tests: `tests/test_fig6_bar_v4.py` — 17 passed (unit + integration,
  including zero/full Wilson bounds, zero-denominator, unknown
  reject_reason, duplicate keys, missing method, family divergence,
  synthetic aggregation, CSV round-trip on frozen data).
- Checksums: `SHA256SUMS.txt` (this session's outputs + inputs).

## Panel (a) — Unauthorized effects across models and domains

Claims supported: B1-family unauthorized-effect rate per model×domain
(n=200 per cell, counts labelled, Wilson 95% CI); PRECEDENTGUARD is
0/200 in all 20 cells (open teal circles on the zero line; a true zero,
not a 0.1% bar). Y-axes are domain-specific (CloudOps 0–10%,
Procurement 0–60%, Finance 0–100%, Data Access 0–20%) — disclosed in the
figure itself, in the caption, and a uniform 0–100% review variant
(`fig6_bar_v4_uniform_y.pdf`) is shipped so no range choice is hidden;
the uniform variant carries its own "range identical" note.
Not claimable: attacker-trajectory outcomes (excluded by filter), any
causal claim that a model is "less safe" (rates measure harness-probed
effects under one harness), cross-domain magnitude comparisons read off
the default axes (use the uniform variant for that).

## Panel (b) — PG proposal outcomes

Claims supported: of each model's proposals (GPT 650, Claude 303, GLM
729, Gemini 729, DS 757; total 3168), the mutually exclusive split into
installed (2275 total) / rejected out-of-root (584) / rejected
CAP_SCOPE (101, of which 14 hit the cap only after drifting out of the
requested root) / malformed (208). Buckets sum to proposed per model
(guarded). Not claimable: rejection "errors" as model failures — the
out-of-root rejections are the guard working as designed.

## Panel (c) — Authorized installation and precedent reuse

Claims supported: installed/proposed and valid-PEP-hit/proposed per
model with Wilson CI; monotonicity vpa ≤ installed ≤ proposed is
guarded. Claude's VPA=0 is drawn as a zero-line open marker (not a fake
small bar). Not claimable: task success, end-to-end utility, or any
comparison against ATC (4,000/4,000 offers no discriminating signal and
is deliberately absent), per the analysis plan.

## Panel (d) — Violations across enforcement layers

Claims supported: per 4,000 legitimate histories, B1 = 2960/598/584
(74.00% / 14.95% / 14.60%), B3 = 2362/0/0 (59.05%), PG = 0/0/0, with
absolute counts labelled on non-zero bars and open markers at zero.
B3's label is "B3 containment judge (no root credential)" — B3 rejects
out-of-root proposals without any root-grant simulation, which is why
its scope and effect counts are zero by construction, not by merit.
Not claimable: B3 as a deployable policy (no legitimate installation
path for root-reaching proposals).

## Evidence disclosures (must survive into the paper caption)

1. Candidates were produced by real LLM agents; measurements come from
   deterministic frozen-trajectory replay (replay_v2).
2. PG's legitimate installs depend on the harness simulating the
   issuance of root capability (canonical PEP probe), not on an actual
   privileged issuer.
3. Unauthorized effects are measured by harness sandbox probes, not by
   agents attempting attacks on their own.
4. B1/B2/B4/B6 share one unguarded-install mechanism (four specs,
   verdict-identical per sample); panel (a)/(d) therefore draw B1 only.
5. PG closed-loop task success is not measured in this figure.
6. Panel (a) y-axes are domain-adaptive; the uniform-y review variant is
   shipped alongside.
7. All percentages are recomputed from frozen rows; every panel is
   cross-checked against cell_verify_v3.json.

## Differences from the previous Fig.6 (v3, dot/dumbbell style)

- v3 fig6b/fig6c were dot plots / dumbbells on pooled or two-panel
  layouts; v4 is a four-panel bar layout with per-cell counts, Wilson
  CI on every rate, and explicit zero markers.
- v4 adds the per-model×domain B1 UER breakdown (panel a) that v3 only
  summarized; adds PG proposal-outcome decomposition (panel b); keeps
  install/reuse (c) and the three-layer violation comparison (d).
- No number changed: v4 re-derives every value from replay_v2 and
  matches cell_verify_v3 and the S1.5/S2 sealed counts; B3 rate is now
  labelled 59.05% (58.05% in the contract was a typo, fixed at the
  funnel stage).

## Rendering QA

- Inserted at `\textwidth` in IEEEtran conference (figure*): 0 Overfull
  warnings, 2-page probe compile (MiKTeX); screenshots in
  `acceptance/` (page, zoom, panel-a close-up, grayscale).
- Grayscale check: method encoding survives (B1 dark, B3 mid-gray, PG
  open/teal, distinct sampled gray levels 38/98/195); the only
  grayscale-adjacent pair is CAP_SCOPE purple vs Installed teal in
  panel (b) — separated by white rules and position; camera-ready is
  color.
- Fonts: DejaVu Sans (Arial/Helvetica unavailable in WSL), Type 42
  embedded (`pdf.fonttype=42`); smallest text 7.5 pt, per spec.
- Figure size 180×135 mm (7.087×5.315 in) exactly.

## INCIDENT — concurrent same-task session (full disclosure)

A second session built the same figure in Origin 2026 (17:53–18:01,
before this session's 20:19+ render). Its delivery shared this
directory. This session's render overwrote the same-name files
(fig6_bar_v4.pdf/svg/png, fig6_bar_v4_uniform_y.pdf/svg,
fig6_bar_data_v4.csv) — irreversible; its unique artifacts (.opju,
origin reports, validation.json, ieee_preview, SHA256SUMS,
uniform-y png, its review.md → now preserved as
fig6_bar_review_origin_session.md) are untouched. Both deliveries'
numbers agree on all guard checkpoints. Which set becomes official is
the user's call.
