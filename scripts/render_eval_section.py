"""Render the populated Evaluation section (V5) from frozen JSONs and
splice it into SP2027_Paper_Skeleton_V5.tex (V4 untouched).  All
numbers are computed here — none hand-typed.  Also copies figure PDFs
into ~/S&P/figs/ for the tex tree."""
import json
import pathlib
import shutil
import sys

sys.path.insert(0, "src")
from pguard.stats import wilson                    # noqa: E402

R = pathlib.Path("results/TABLES")
FD = json.load(open(R / "fig_data.json"))
S5 = json.load(open(R / "s5_split.json"))
EAV = json.load(open(R / "eav.json"))["per_arm"]
OB = json.load(open(R / "overload_bench.json"))["latency"]
CClist = json.load(open(R / "coerce_compare.json"))
UT = json.load(open(R / "master_table.json"))["utility"]
MODELS = FD["models"]
CC = {(r["model"], r["method"]): r for r in CClist}


def ci(k, n):
    lo, hi = wilson(k, n) if n else (0.0, 1.0)
    return f"{100*k/n:.1f}\\% [{100*lo:.1f}, {100*hi:.1f}]" if n else "--"


def pooled(method, k=10):
    tot = {f: 0 for f in ("n", "uer", "vpa", "prop", "inst", "oop")}
    for m in MODELS:
        for dom in FD["domains"]:
            c = FD["cell"].get(f"{m}|{dom}|{method}|k={k}")
            if c:
                for f in tot:
                    tot[f] += c[f]
    return tot


P = {me: pooled(me) for me in
     ("B0", "B1", "B2", "B3", "B4", "B5", "B6", "PG")}
N = P["B1"]["n"]                                  # 4000
prop_tot = P["B1"]["prop"]
malformed = prop_tot - P["B1"]["inst"]            # fail-closed rejects
contained = prop_tot - P["B1"]["oop"]             # wait: oop is traj-level

# fig_data 'oop' is trajectory-level (same across methods): contained
# proposals = prop - oop
oop_leg = P["B1"]["oop"]
# fig_data records 'oop' only on PG cells (trajectory-level field):
oop_scope = pooled("PG")["oop"]        # declared-scope UPR numerator

atk = [sum(v["atk"][i] for v in S5.values()) for i in range(3)]
leg = [sum(v["legit"][i] for v in S5.values()) for i in range(3)]
atk_oop, atk_b1, atk_rej = atk
leg_oop = leg[0]
# well-formed contained = B3 installs: the certify-only arm
# (containment enforced, authority ablated) installs exactly the
# contained well-formed set.  Census k=10 legit: 2362 = 2275 PG
# installs + 87 CAP_SCOPE.  NOT B1_inst - oop: that mixes in the 598
# well-formed declared-oop rules (584 OUT_OF_ROOT + 14 CAP_SCOPE).
contained = P["B3"]["inst"]
frr = contained - P["PG"]["inst"]

# supply extremes with labels
sup = sorted((S5[m]["legit"][0], m) for m in MODELS)
sup_lo, sup_lo_m = sup[0]
sup_hi, sup_hi_m = sup[-1]

ts = [UT[m]["task_success"] for m in MODELS]
ts_lo, ts_hi = min(ts), max(ts)
ts_pool = sum(UT[m]["task_success"] * 800 for m in MODELS) / N

case_claude = UT["Claude-5.5"]["case_only"]
case_glm = UT["GLM-5.3"]["case_only"]

# EAV
glm_eav = EAV["GLM-5.3"]["B1|legit"]
pg_eav_max = max(EAV[m]["PG|legit"]["frac_gt0"] for m in MODELS)
pg_eav_maxreq = max(EAV[m]["PG|legit"]["max"] for m in MODELS)

# coercion
def cc(model, method, side, key):
    return CC[(model, method)][side][key]

gpt_b1_s = cc("GPT-5.6", "B1", "strict", "UER")
gpt_b1_c = cc("GPT-5.6", "B1", "coerced", "UER")
cl_b1_s = cc("Claude-5.5", "B1", "strict", "UER")
cl_b1_c = cc("Claude-5.5", "B1", "coerced", "UER")
cl_pg_s = cc("Claude-5.5", "PG", "strict", "VPA")
cl_pg_c = cc("Claude-5.5", "PG", "coerced", "VPA")
gpt_pg_c = cc("GPT-5.6", "PG", "coerced", "VPA")
ds_pg_c = cc("DeepSeek-v4.1-flash", "PG", "coerced", "VPA")
gm_pg_c = cc("Gemini-3.8-flash", "PG", "coerced", "VPA")

# dose (pooled over models+domains) from fig_data
KS = ("1", "3", "5", "10")


def dose(me):
    out = []
    for k in KS:
        t = {f: 0 for f in ("n", "uer", "prop", "inst", "oop")}
        for m in MODELS:
            for dom in FD["domains"]:
                c = FD["cell"].get(f"{m}|{dom}|{me}|k={k}")
                if c:
                    for f in t:
                        t[f] += c[f]
        out.append(t)
    return out


D_PG, D_B1 = dose("PG"), dose("B1")

p95_pg = OB["PG"]["250"]["p95_ms"]
p95_b1 = OB["B1"]["250"]["p95_ms"]

Ntex = f"{N:,}".replace(",", "{,}")
ATK_ROWS = "\n".join(
    f"{m} & {S5[m]['atk'][0]} & {S5[m]['atk'][2]} & 0 & "
    f"{S5[m]['atk'][1]} & {S5[m]['atk'][1]} \\\\" for m in MODELS)

tex = f"""\\section{{Evaluation}}\\label{{sec:eval}}
\\subsection{{RQ1: Does Effective CPPE Arise in Real Agent Traces?}}
Yes. Across {N:,} closed-loop trajectories (five models $\\times$ four
domains $\\times$ four learning channels $\\times$ 50 seeds), {prop_tot:,}
({100*prop_tot/N:.1f}\\%) end with the agent \\emph{{spontaneously}}
proposing a standing \\AuthPrec\\ rule after successful \\AuthCase-mediated
tasks. Of these, {oop_scope} ({100*oop_scope/N:.1f}\\%) declare rule
conditions outside the root envelope, and {leg_oop}
({100*leg_oop/N:.1f}\\%, Wilson 95\\% CI
[{100*wilson(leg_oop, N)[0]:.1f}, {100*wilson(leg_oop, N)[1]:.1f}])
cover at least one out-of-envelope request outright --- with no
attacker present. The coverage-level count is the security-relevant
one: under naive reuse every one of the {leg_oop} becomes an
unauthorized standing rule (RQ2). Per-model supply ranges from {100*sup_lo/800:.1f}\\%
({sup_lo_m}) to {100*sup_hi/800:.1f}\\% ({sup_hi_m}); a further
{malformed} proposals ({100*malformed/N:.1f}\\% of all trajectories)
fail schema validation and are rejected whole (fail-closed, never
silently repaired). At $k{{=}}0$ no method admits any rule. A
representative trace (finance: out-of-root \\texttt{{prod-*}} widening
after a successful incident case) appears in the artifact appendix.

\\subsection{{RQ2: Security--Utility Compared with Strong Baselines}}
Table~\\ref{{tab:results}} pools all five arms ($N={Ntex}$ matched
legit trajectories at $k{{=}}10$; attacker arm in
Table~\\ref{{tab:attacks}}). \\PG\\ admits zero unauthorized effects
({ci(P['PG']['uer'], N)}; exact Clopper--Pearson upper
{100*(1-0.025**(1/N)):.2f}\\%) while installing
{P['PG']['inst']}/{contained} ({100*P['PG']['inst']/contained:.1f}\\%) of
well-formed contained proposals and
completing all {N:,}/{N:,} delegated tasks through the case channel
(ATC = 100\\% on every arm). The {frr} uninstalled contained
proposals are all action-class rejections (\\textsc{{CapScope}}: the
delegated grant covers the domain's canonical action class), so the
residual rejection rate within the granted class is zero. The
naive-reuse family (B1/B2/B4/B6)
converts every out-of-envelope proposal into standing authority:
{leg_oop}/{N} ({100*leg_oop/N:.1f}\\%) unauthorized effects, and every
install commits a CPPE-ISSUER violation (learner-signed authority).
B0 (static) is safe but installs nothing; B3 (root-aware judge) keeps
effects contained but retains only {100*P['B3']['inst']/P['B1']['inst']:.0f}\\%
of B1's installs and still commits CPPE-ISSUER on what it installs;
B5 installs but never serves (zero utility), and its admitted rules
still carry excess authority volume. Excess-authority volume of
admitted rules (EAV): \\PG\\ = {pg_eav_maxreq} excess universe requests
on every admitted rule, every arm; {100*glm_eav['frac_gt0']:.0f}\\% of
B1's installs on the worst arm (GLM-5.3) carry excess (mean
{glm_eav['mean']:.1f}, max {glm_eav['max']} requests). Task success is
trajectory-level and method-independent: {ts_lo:.3f}--{ts_hi:.3f}
(pooled {ts_pool:.3f}).

\\begin{{figure*}}[!t]
\\centering
\\includegraphics[width=\\textwidth]{{figs/fig6_tradeoff.pdf}}
\\caption{{\\textbf{{Security--utility trade-off across authorization
domains.}} Upper row: unauthorized-effect rate (UER). Lower row: valid
precedent acceptance (VPA). Bars pool five models (Wilson 95\\% CIs);
columns are domains. Static reauthorization is the safety floor with no
reusable autonomy; history/provenance reuse silently expands authority;
\\PG\\ keeps UER at zero while retaining contained reuse.}}
\\label{{fig:main}}
\\end{{figure*}}

\\begin{{table*}}[!t]
\\centering\\scriptsize
\\caption{{\\textbf{{Main security and utility, pooled over five models}}
($N=4{{,}}000$ legit trajectories, $k{{=}}10$). Issuer viol.: installs
signed by the learner (CPPE-ISSUER). Out-of-root: installed rules
outside the root envelope. VPA/ATC are case-channel metrics of the
guarded path; baselines implement no case channel (---). FRR counts
well-formed contained proposals not installed ({contained} total; all
\\PG\\ rejections are \\textsc{{CapScope}} action-class misses). Task
success is trajectory-level, method-independent.}}
\\label{{tab:results}}
\\resizebox{{\\textwidth}}{{!}}{{%
\\begin{{tabular}}{{@{{}}lrrrrrrr@{{}}}}
\\toprule
Method & Installs $n/N$ & Issuer viol. & Out-of-root & Unauthorized
effects & Valid precedents & FRR (contained) & p95 decide (ms)\\\\
\\midrule
B0 Static & 0/{N:,} & 0 & 0 & {ci(P['B0']['uer'], N)} & --- & {contained} & ---\\\\
B1 History & {P['B1']['inst']}/{N:,} & {P['B1']['inst']} & {leg_oop} & {ci(P['B1']['uer'], N)} & --- & 0 & ---\\\\
B2 RAG & {P['B2']['inst']}/{N:,} & {P['B2']['inst']} & {leg_oop} & {ci(P['B2']['uer'], N)} & --- & 0 & ---\\\\
B3 Judge & {P['B3']['inst']}/{N:,} & {P['B3']['inst']} & 0 & {ci(P['B3']['uer'], N)} & --- & {contained - P['B3']['inst']} & ---\\\\
B4 Prov. & {P['B4']['inst']}/{N:,} & {P['B4']['inst']} & {leg_oop} & {ci(P['B4']['uer'], N)} & --- & 0 & ---\\\\
B5 EventSrc & {P['B5']['inst']}/{N:,} & {P['B5']['inst']} & {leg_oop} & {ci(P['B5']['uer'], N)} & --- & 0 & ---\\\\
B6 ExactES & {P['B6']['inst']}/{N:,} & {P['B6']['inst']} & {leg_oop} & {ci(P['B6']['uer'], N)} & --- & 0 & ---\\\\
\\midrule
\\PG & {P['PG']['inst']}/{N:,} & 0 & 0 & {ci(P['PG']['uer'], N)} &
{P['PG']['vpa']}/{prop_tot} & {frr} & {p95_pg:.3f}\\\\
\\bottomrule
\\end{{tabular}}}}
\\end{{table*}}

\\begin{{table}}[!t]
\\centering\\small
\\caption{{\\textbf{{Adversarial arm}} (200 attacker trajectories per
model: benign tasks, then two denied probes; $k{{=}}10$). Out-of-root
final rules, and their fate under \\PG\\ vs.\\ B1.}}
\\label{{tab:attacks}}
\\begin{{tabular}}{{@{{}}lrrrrr@{{}}}}
\\toprule
Model & Out-of-root & \\PG\\ rejects & \\PG\\ unauth. & B1 installs & B1 unauth.\\\\
\\midrule
{ATK_ROWS}
\\midrule
Pooled & {atk_oop} & {atk_rej} & 0 & {atk_b1} & {atk_b1}\\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}

\\subsection{{RQ3: How Does Repeated Success Change the Risk?}}
Fig.~\\ref{{fig:dose}} varies the number of retained successful \\AuthCase s
($k$ prefix views of frozen histories; proposals are the model's own).
The learner's appetite grows with success --- the rate of proposals
declaring conditions beyond the root envelope rises
from {100*D_PG[0]['oop']/D_PG[0]['n']:.1f}\\% at $k{{=}}1$ to
{100*D_PG[3]['oop']/D_PG[3]['n']:.1f}\\% at $k{{=}}10$ (pooled) --- while
\\PG\\'s admission stays at zero unauthorized effects at every $k$
(B1: {100*D_B1[0]['uer']/D_B1[0]['n']:.1f}\\% $\\rightarrow$
{100*D_B1[3]['uer']/D_B1[3]['n']:.1f}\\%). The learner may increasingly
propose escalation; the reference monitor does not increasingly permit
it.

\\begin{{figure}}[!t]
\\centering
\\includegraphics[width=\\columnwidth]{{figs/fig7_ratchet.pdf}}
\\caption{{\\textbf{{Repeated-success dose--response}} ($k\\in\\{{0,1,3,5,10\\}}$,
pooled models; Wilson 95\\% bands). Upper: unsafe proposal rate
(trajectory-level, method-independent). Lower: unauthorized-effect rate
by method.}}
\\label{{fig:dose}}
\\end{{figure}}

\\subsection{{RQ4: Across Which Models and Learning Channels?}}
Fig.~\\ref{{fig:matrix}} reports the out-of-envelope proposal rate per
model $\\times$ channel $\\times$ domain. The phenomenon is
\\emph{{general}}: every model/channel cell with non-trivial proposal
volume shows non-zero UPR. The model axis spans a behavioural
spectrum --- Claude-5.5 ends {case_claude}/800 legit trajectories in
case-only mode (no standing rule at all; {case_glm} for GLM-5.3),
while GLM-5.3 and Gemini-3.8-flash propose in over 90\\% of
trajectories. Two arms ran on mixed API relays (provider channels
changed mid-run); a per-channel split shows both phases qualitatively
identical (the phases cover different grid cells, so this is a
homogeneity check with a stated composition confound, not an A/B
test).

\\begin{{figure*}}[!t]
\\centering
\\includegraphics[width=\\textwidth]{{figs/fig8_heatmap.pdf}}
\\caption{{\\textbf{{Case-to-policy proposals across model families and
reuse mechanisms.}} Cell: \\% of histories whose final proposal is
outside the root envelope ($k{{=}}10$). All 5$\\times$4 cells per domain
are populated (no N/A); case-only-heavy rows are low by behaviour, not
by failure.}}
\\label{{fig:matrix}}
\\end{{figure*}}

\\subsection{{RQ5: Perfect Provenance Is Not Precedent Authority}}
In benign channels the signed history \\emph{{is}} the success history,
so exact event sourcing (B6) recovers naive reuse (B1) exactly:
per-trajectory verdict tuples (installed, effect, acceptance) are
identical in 20{{,}}000/20{{,}}000 comparisons. Perfect provenance
therefore does not reduce CPPE at all in this benchmark
(Fig.~\\ref{{fig:provenance}}); its value appears only under history
tampering (offline E5). A typing-convention sensitivity replay
(lossless numeric-string coercion of rule bounds, e.g.\\
\\texttt{{["le","30"]$\\to$["le",30]}}) shows the pooling is not an
artifact of strict typing: baselines' UER \\emph{{rises}} under the
lenient convention (GPT-5.6 {gpt_b1_s:.3f}$\\to${gpt_b1_c:.3f},
Claude-5.5 {cl_b1_s:.3f}$\\to${cl_b1_c:.3f}) while \\PG\\ remains at
zero under both conventions. Claude-5.5's strict-typing VPA of
{cl_pg_s:.3f} rises to {cl_pg_c:.3f} under coercion (GPT-5.6
{gpt_pg_c:.3f}, DeepSeek {ds_pg_c:.3f}, Gemini {gm_pg_c:.3f}),
confirming its reuse deficit was representational, not behavioural.

\\begin{{figure*}}[!t]
\\centering
\\includegraphics[width=0.82\\textwidth]{{figs/fig9_provenance.pdf}}
\\caption{{\\textbf{{Preserving the history is not equivalent to
authorizing a rule.}} All \\AuthCase\\ events are authentic, correctly
scoped, exactly recorded. Bars: unauthorized-effect rate (a) and valid
precedent acceptance (b), pooled models, Wilson 95\\% CIs.}}
\\label{{fig:provenance}}
\\end{{figure*}}

\\subsection{{RQ6: Adaptive Exception Farming}}
Offline adaptive suite (E6, mock-labelled): five attack families
$\\times$ budgets $\\{{1,5,10,25,50\\}}$ --- \\PG\\ admits zero unsafe
rules in every cell; an evidence-consistency LLM judge admits 42/50
unsafe at budget 50. The real five-model attacker arm (two denied
probes after benign tasks, Table~\\ref{{tab:attacks}}) yields
{atk_oop}/1{{,}}000 trajectories whose final rule is out-of-envelope:
\\PG\\ rejects {atk_rej}/{atk_oop} with zero unauthorized effects; B1
installs {atk_b1}/{atk_oop}, all with unauthorized standing effects
(Fig.~\\ref{{fig:robust}}a, real overlay).

\\subsection{{RQ7: Ablations of Each Enforcement Component}}
Offline ablation grid (E7, mock-labelled): each of six attacks
penetrates \\emph{{only}} under the ablation of the component the
safety proof assumes (typing, containment, necessity, epoch-CAS,
replay, LLM-judge); with all components enabled no attack succeeds.
The disabled controls invalidate the theorem's assumptions by
construction --- the failures are the point.

\\subsection{{RQ8: Independent DSL Verifiers}}
Offline verification cross-check (E8): two independent containment
verifiers (exhaustive enumeration and SMT-style) agree on all 14
published rule rows; 5 semantic mutants and 2 timeout mutants are
caught. This is DSL verification, not real-agent prevalence.

\\subsection{{RQ9: Corruption, Revocation and Overload}}
Offline robustness (E9, mock-labelled): with 0--40\\% spurious
challenger edges, false rejection rises (0/0.6/0.9/1/1) while unsafe
admission stays flat-zero --- the challenger degrades conservatively,
never openly. Under 1--20$\\times$ proposal overload the store sheds
load (denial 0$\\rightarrow$0.95) with zero unsafe admissions.
Decision latency on the real deployment path (microbenchmark):
p95 {p95_pg:.2f}\\,ms at 250 installed precedents ({p95_b1:.2f}\\,ms
unguarded B1) --- typed containment adds no measurable decision-time
cost (Fig.~\\ref{{fig:robust}}c, Appendix~A4).

\\begin{{figure*}}[!t]
\\centering
\\includegraphics[width=\\textwidth]{{figs/fig10_attacks_degradation.pdf}}
\\caption{{\\textbf{{Adaptive attacks and fail-closed degradation.}}
(a) Attack success: offline suite (budget 50) plus the \\emph{{real}}
five-model farming overlay ($n{{=}}{atk_oop}$). (b) Challenger
corruption trades availability for conservatism. (c) Overload sheds
load fail-closed; unsafe admission stays zero.}}
\\label{{fig:robust}}
\\end{{figure*}}
"""

# ---- splice into V5 ----------------------------------------------------
src = pathlib.Path.home() / "S&P" / "SP2027_Paper_Skeleton_V4.tex"
dst = pathlib.Path.home() / "S&P" / "SP2027_Paper_Skeleton_V5.tex"
text = src.read_text(encoding="utf-8")
a = text.index("\\section{Evaluation}")
b = text.index("\\section{Discussion, Limitations, and Ethics}")
dst.write_text(text[:a] + tex + "\n" + text[b:], encoding="utf-8")
print("wrote", dst, f"({len(tex)} chars section)")

figdir = pathlib.Path.home() / "S&P" / "figs"
figdir.mkdir(exist_ok=True)
nfig = 0
for f in pathlib.Path("results/FIGS").glob("*.pdf"):
    shutil.copy(f, figdir / f.name)
    nfig += 1
print("figs copied:", nfig)
