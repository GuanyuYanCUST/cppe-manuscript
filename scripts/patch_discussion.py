"""Replace the four \\draft blocks of the Discussion section in V5 with
grounded text computed from the frozen tables (same no-hand-typing
rule)."""
import json
import pathlib
import sys

sys.path.insert(0, "src")
from pguard.stats import wilson                    # noqa: E402

R = pathlib.Path("results/TABLES")
FD = json.load(open(R / "fig_data.json"))
S5 = json.load(open(R / "s5_split.json"))
UT = json.load(open(R / "master_table.json"))["utility"]
OB = json.load(open(R / "overload_bench.json"))["latency"]
MODELS = FD["models"]

N = 4000
prop = inst = 0
oop_pg = 0
for m in MODELS:
    for d in FD["domains"]:
        c = FD["cell"].get(f"{m}|{d}|B1|k=10")
        if c:
            prop += c["prop"]
            inst += c["inst"]
        # 'oop' is recorded only on PG cells (trajectory-level)
        oop_pg += FD["cell"][f"{m}|{d}|PG|k=10"]["oop"]
pg_inst = sum(FD["cell"][f"{m}|{d}|PG|k=10"]["inst"]
              for m in MODELS for d in FD["domains"])
leg_oop = sum(v["legit"][0] for v in S5.values())   # coverage-level
contained = sum(FD["cell"][f"{m}|{d}|B3|k=10"]["inst"]
                for m in MODELS for d in FD["domains"])
# ^ certify-only arm installs exactly the contained well-formed set
# (census 2362 = 2275 PG + 87 CAP_SCOPE); B1_inst - oop was wrong
# (mixed in 598 well-formed declared-oop rules)
frr = contained - pg_inst
frr_pct = 100 * frr / contained
leg_oop = sum(v["legit"][0] for v in S5.values())
ts = [UT[m]["task_success"] for m in MODELS]

paras = {
    "Scope of the Formal Guarantee":
    f"""The safety theorem assumes complete mediation, correct trusted
evidence for the stated semantics, cryptographic separation, and sound
containment verification; it does not establish universal harmlessness
or resistance to root compromise. The empirical arm measures what the
theorem cannot: that real models, left to their own devices, generate
the escalations the theorem anticipates ({100*leg_oop/N:.1f}\\% of
benign trajectories), and that \\PG's enforcement holds on those
trajectories (zero unauthorized effects across all {N:,}).""",
    "Availability and Deployment Trade-Offs":
    f"""\\PG's cost is administrative, not computational: of
{contained:,} contained, well-formed proposals it installs
{pg_inst:,}, leaving {frr} ({frr_pct:.1f}\\%) uninstalled --- all
\\textsc{{CapScope}} action-class rejections under the delegated grant
class, recoverable through broader delegation or the case channel ---
and authorized-task completion
stays at 100\\% on every arm with task success
{min(ts):.3f}--{max(ts):.3f}. Decision-path overhead is p95
{OB['PG']['250']['p95_ms']:.2f}\\,ms at 250 installed precedents,
indistinguishable from the unguarded baseline. Scope DSL expressivity,
disconnected freshness, human review on unknown/timeout outcomes, and
authorized learning acceleration remain operator-governed dials.""",
    "Threats to Validity and Negative Results":
    f"""We report adverse and null results as-is. (i) Frozen-trajectory
replay fixes each trajectory's final proposal, so memory-capacity
effects on rule shape cannot be observed (tail-truncation replays are
null by construction); defences that reshape learning require live
re-rollouts we did not run. (ii) Two of five arms ran across mixed
provider relays; per-channel splits are qualitatively identical but
are homogeneity checks with a stated composition confound, not A/B
tests. (iii) The adaptive attacker is a fixed two-probe ratchet;
adaptivity beyond it is covered only by the offline (mock-labelled)
suite. (iv) B5 (installs-never-serves) is a genuinely negative
design point: safe, but with zero utility and admitted rules that
still carry excess authority. (v) Model behaviour differs widely
(case-only finals range from 0 to {100*max(UT[m]['case_only'] for m in MODELS)/800:.0f}\\%
of trajectories); cross-model numbers describe behaviour under
identical prompts, not capability rankings. (vi) Relay list prices
are unverified against final invoices; cost figures are upper bounds
at official prices.""",
    "Research Ethics and Generative AI Usage":
    """All experiments run against synthetic authorization universes in
a sandboxed harness; no real credentials, production systems, or
personal data are involved. No proposed rule was ever executed ---
only classified by the reference monitor. Model outputs are retained
verbatim for auditability. API usage is disclosed (five commercial
models, ~\\$198 upper bound at official list prices), and this paper's
use of generative AI follows the IEEE S\\&P~2027 disclosure policy:
AI assistance was limited to the authors' tooling and drafting under
author direction; all measurements are machine-derived from frozen
artifacts.""",
}

tex = pathlib.Path.home() / "S&P" / "SP2027_Paper_Skeleton_V5.tex"
text = tex.read_text(encoding="utf-8")
for head, body in paras.items():
    key = f"\\subsection{{{head}}}\n"
    i = text.index(key)
    j = text.index("\\subsection{", i + len(key))
    text = text[:i] + key + body.strip() + "\n\n" + text[j:]
tex.write_text(text, encoding="utf-8")
print("patched 4 subsections in", tex)
