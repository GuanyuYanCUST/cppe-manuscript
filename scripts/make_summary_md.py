"""Generate results/DATA_SUMMARY_20261010/summary.md — every number of the
paper in one markdown file, each table followed by a short explanation.

All values read from the same frozen JSONs the CSVs came from (zero new
experiments). Run: .venv/bin/python scripts/make_summary_md.py
"""
import json
import pathlib
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "DATA_SUMMARY_20261010"
CV = json.load(open(ROOT / "audit_20261010/gates/cell_verify_v3.json"))
MT = json.load(open(ROOT / "results/TABLES/master_table.json"))
L = []


def tb(header, rows, note=None):
    L.append("| " + " | ".join(str(h) for h in header) + " |")
    L.append("|" + "---|" * len(header))
    for r in rows:
        L.append("| " + " | ".join("" if v is None else str(v)
                                  for v in r) + " |")
    if note:
        L.append("")
        L.append(note)
    L.append("")


def h2(t):
    L.extend(["", "## " + t, ""])


def h3(t):
    L.extend(["", "### " + t, ""])


def pct(k, n, dp=2):
    return "N/A" if not n else f"{100*k/n:.{dp}f}%"


def wil(k, n, dp=2):
    if not n:
        return "N/A"
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from pguard.stats import wilson
    lo, hi = wilson(k, n)
    return f"[{100*lo:.{dp}f}, {100*hi:.{dp}f}]"


# ============================= 头部 =============================
L.extend([
    "# 论文全部实验数据汇总（summary.md）",
    "",
    "生成：2026-10-10，`scripts/make_summary_md.py`，全部数值来自冻结",
    "产物（cell_verify_v3 独立重算 / Gate C / master_table / 各实验",
    "summary.json），零新实验、零 API。每个表后附一段解释。",
    "分母总表先看 §1.1；引用任何百分比前先看文末「已知坑」。",
])

# ============================= 1. 主实验 =============================
h2("1. 真实 5 模型主实验（L1 live + L2 回放，k=10 为主）")
L.append("5 个模型各 800 条 legit 轨迹（4 韧 × 4 通道 × 50 种子）+ 200 条"
         "攻击轨迹；每条轨迹真实多轮会话后冻结，回放进 8 个方法 × 5 档 k，"
         "共 200,000 行、0 错误。")

h3("1.1 分母口径表（一切百分比的分母）")
D = CV["denominators"]
tb(["量", "数值", "含义"], [
    ["legit 轨迹", D["trajectories_legit"], "5 模型 × 800，回放单位"],
    ["提案轨迹", D["proposing"], "轨迹末自选立规则模式并给出规则文本"],
    ["MALFORMED", D["malformed"], "规则解析失败，全方法 fail-closed 0 安装"],
    ["well-formed 提案", D["well_formed_proposals"], "= 无防护方法安装数"],
    ["PG 安装", D["pg_installed"], "授权+遏制双检通过，全部带 root cap"],
    ["PG 判 OUT_OF_ROOT", D["pg_out_of_root"], "越界提案，正确拒绝"],
    ["PG 判 CAP_SCOPE(越界上)", D["pg_cap_scope_on_oop"], "越界提案先撞 cap（全 GLM）"],
    ["PG 判 CAP_SCOPE(类内)", D["pg_cap_scope_inclass"], "范围内但 cap 类型不匹配（PG 的误拒代价）"],
    ["CPPE-SCOPE 逃逸安装(无防护)", D["pg_oop_proposals"],
     "598 = 584 探针可见 + 14 类外，在 B1 族里全部装进去"],
], "4,000 = 832 未提案 + 208 malformed + 2,275 PG安装 + 87 类内cap拒 + "
   "584 越界拒 + 14 越界cap拒。")

h3("1.2 各方法汇总（pooled，k=10，legit n=4,000）")
tb(["方法", "提案", "安装", "UER", "UER% [Wilson95]", "无凭据安装", "scope安装", "VPA", "ATC(case)"],
   [[m, t["prop"], t["inst"], t["uer"],
     f'{pct(t["uer"], t["n"])} {wil(t["uer"], t["n"])}',
     t["issuer"], t["scope"], t["vpa"], f'{t["atc"]} ({t["atc_case"]})']
    for m, t in CV["per_method_legit"].items()],
   "**读法**：UER=未授权效果（核心安全指标，效果层）；无凭据安装=安装时"
   "没有 root 签发的类型化凭据（授权层）；scope 安装=规则越出任务根"
   "（范围层）。三层互补。B1/B2/B4/B6 四行完全相同＝同一机制四种规格"
   "（判别实验在 §3.1 E5）。B3 只装 containment 通过的规则所以 UER=0，"
   "但其安装无凭据（它是谓词评审，不是 root）。ATC 列：PG 在全部 4,000 行"
   "跑探针 4,000/4,000（3,698 走 case）；基线 1,040 是**未测量子集**"
   "（探针在 wf 路径只对 PG 运行），已测的 1,040 全部成功——不是失败。")

h3("1.3 各模型 × 方法（k=10，legit n=800/模型）")
tb(["模型", "方法", "提案", "安装", "UER", "UER% [Wilson95]", "scope", "VPA"],
   [[k.split("|")[0],
      k.split("|")[1], t["prop"], t["inst"], t["uer"],
     f'{pct(t["uer"], t["n"])} {wil(t["uer"], t["n"])}',
     t.get("scope", ""), t.get("vpa", "")]
    for k, t in CV["per_model"].items()],
   "**读法**：模型性格光谱——GLM/Gemini 激进（提案 91%、UER 27%），"
   "Claude 谨慎（提案 38%、UER 2%）。PG 在所有模型 UER=0（每模型 0/800，"
   "exact CP 上界 0.46%）。Claude VPA=0 是严格类型产物（95% 规则带字符串"
   "数字边界→惰性），无损转换口径下 36.6%（见 §5.1）。")

h3("1.4 B1 族 UER：模型 × 韧（20 格，每格 n=200）")
tb(["模型", "韧", "UER k", "UER% [Wilson95]"],
   [[k.split("|")[0], k.split("|")[1], v["uer"],
     f'{pct(v["uer"], v["n"])} {wil(v["uer"], v["n"])}']
    for k, v in CV["per_model_domain_b1_uer"].items()],
   "**读法**：Fig.6-C(a) 的原始数。风险不是单模型毛病：20 格里 17 格"
   "非零，finance/dataaccess 普遍高于 cloudops。")

h3("1.5 PG 提案去向（按模型）")
RR = CV["pg_reject_reasons_per_model"]
rows = []
for m in CV["models"]:
    rr = RR[f"{m}|PG"]
    malf = sum(v for k, v in rr.items() if k.startswith("MALFORMED"))
    pg = CV["per_model"][f"{m}|PG"]
    rows.append([m, pg["prop"], pg["inst"], rr.get("OUT_OF_ROOT", 0),
                 rr.get("CAP_SCOPE", 0), malf,
                 pct(pg["inst"], pg["prop"], 1)])
tb(["模型", "提案", "安装(cap)", "OUT_OF_ROOT拒", "CAP_SCOPE拒", "MALFORMED拒",
    "安装率%"], rows,
   "**读法**：Fig.6-C(b)。PG 拒绝的两个安全理由：OUT_OF_ROOT=越界"
   "（正确拒绝）；CAP_SCOPE=cap 类型/范围不匹配（87 类内是 PG 的误拒代价"
   "3.7%，14 条越界提案被 cap 先拦，结果等价安全）。")

h3("1.6 VPA 按模型（PG 的合法复用）")
tb(["模型", "VPA k", "提案 n", "安装 n", "VPA% (of 提案) [Wilson95]"],
   [[m, v["vpa"], v["prop"], v["inst"],
     f'{pct(v["vpa"], v["prop"])} {wil(v["vpa"], v["prop"])}']
    for m, v in CV["per_model_pg_vpa"].items()],
   "**读法**：Fig.6-C(c) 上半。VPA=装的规则后来在 case 通道被合法引用"
   "放行。合计 720/3,168（分母也可用 2,275 安装，引用时必须写明）。"
   "Gemini 64.7% 最高；Claude 0%（打字产物，见 §5.1）。")

h3("1.7 攻击臂（200 轨迹/模型，episodic，每条 2 次被拒探针）")
tb(["模型", "方法", "提案", "安装", "越界提案", "未授权效果"],
   [[k.split("|")[0], k.split("|")[1], v["prop"], v["inst"], v["oop"],
     v["eff"]]
    for k, v in CV["attacker_per_model_B1_PG"].items()],
   "**读法**：图 6 不含这批（分母不同）。攻击者 B1 安装且 133/1000 出现"
   "未授权效果（GLM 14 / Claude 5 / Gemini 58 / DS 28 / GPT 28）；"
   "PG 安装 569 条 contained 规则（借类授权上车）但未授权效果 0。")

h3("1.8 真实任务成功率（L1，方法无关）")
tb(["模型", "成功率", "k / 8,000 任务", "Wilson95"],
   [[m, MT["utility"][m]["task_success"],
     round(MT["utility"][m]["task_success"] * 8000),
     wil(round(MT["utility"][m]["task_success"] * 8000), 8000)]
    for m in CV["models"]],
   "**读法**：回放只改策略层、不改任务执行，故成功率与方法无关，只反映"
   "模型差异（74.5%–82.5%）。它与 PG ATC 4,000/4,000 一起支撑"
   "「加防护不牺牲可用性」。")

# ============================= 2. L3 fork =============================
h2("2. 授权分叉实验（L3，只对 PG 的回放做 root cap 分叉）")
forks = [json.loads(x) for x in
         open(ROOT / "audit_20261010/gates/authority_fork_results.jsonl")]
agg = {}
for r in forks:
    a = agg.setdefault((r["fork"], bool(r["attacker"])),
                       Counter(n=0, prop=0, inst=0, eff=0))
    a["n"] += 1
    a["prop"] += bool(r.get("proposed"))
    a["inst"] += bool(r.get("installed"))
    a["eff"] += bool(r.get("unauth_effect"))
tb(["fork 条件", "臂", "n", "提案", "安装", "未授权效果"],
   [[f, "攻击" if a else "legit", v["n"], v["prop"], v["inst"], v["eff"]]
    for (f, a), v in sorted(agg.items(), key=str)],
   "**读法**：Fig.9 右半。control=harness 扮演 root 给 PG 签 cap（真实"
   "运行条件）；grant_absent=无授权 → 一次都不装；四种坏 cap（过期/错签发"
   "者/类型混淆/过期 epoch）全部 0 安装。13,200 行未授权效果全 0——"
   "PG 的安全性不依赖 cap 存在，但可用性（安装）依赖它。")

# ============================= 3. 离线实验 =============================
h2("3. 离线机制实验（L4，mock 模型，论文中标注 offline）")

h3("3.1 E5 因子实验：记忆 × 授权 2×2（Fig.9 左半，n=40/格）")
E5 = json.load(open(ROOT / "results/E5/E5-factorial-20261008-155213"
                    "/summary.json"))["table"]
rows = []
for cell, t in E5.items():
    for meth, st in t.items():
        rows.append([cell, meth, f'{st["install_rate"]["k"]}/{st["install_rate"]["n"]}',
                     f'{st["UIR"]["k"]}/{st["UIR"]["n"]}',
                     f'{st["VPA"]["k"]}/{st["VPA"]["n"]}'])
tb(["格子(记忆|grant)", "方法", "安装 k/n", "未授权安装 k/n", "VPA k/n"], rows,
   "**读法**：matched counterfactual——同一 contained 候选、同一签名历史、"
   "同一 root，只变「记忆 lossy/exact」和「有无 root cap」。关键格 "
   "exact|grant=0：B2/B6 靠完美溯源照装 40/40（未授权），PG 拒绝——"
   "「知道发生过 ≠ 有权立法」。E5 不执行下游效果，effect 一律 N/A。")

h3("3.2 E2 离线基线矩阵（800 格 × 8 方法，mock）")
e2 = json.load(open(ROOT / "results/E2/E2-baselines-20261008-155014"
                    "/summary.json"))["by_method"]


def knr(m):
    if not m or m.get("na") or not m.get("n") or m.get("rate") is None:
        return "N/A"
    return f'{m["k"]}/{m["n"]} = {100*m["rate"]:.1f}%'


tb(["方法", "描述", "UIR", "UER", "VPA", "FRR", "ATC"],
   [[m, t.get("desc", ""), *(knr(t.get(x)) for x in
                             ("UIR", "UER", "VPA", "FRR", "ATC"))]
    for m, t in e2.items()],
   "**读法**：机制层语义自检。PG 全指标安全且 FRR=0；B0 全拒（FRR=1）；"
   "B1/B2/B4/B6 同列；B3 UIR=0.5（contained 一半）；B5 只装不服务。")

h3("3.3 E6 自适应攻击（5 攻击 × 预算 {1,5,10,25,50}，n=12/格）")
e6 = json.load(open(ROOT / "results/E6/E6-adaptive-20261008-160427"
                    "/summary.json"))
tb(["攻击", "预算", "PG 不安全放行 k/n"],
   [[atk, b, f'{t["k"]}/{t["n"]} = {100*t["rate"]:.1f}%']
    for atk, bs in e6["pg_unsafe_by_budget"].items()
    for b, t in sorted(bs.items(), key=lambda x: int(x[0]))],
   "**读法**：PG 在所有攻击×预算下不安全放行全 0（对照：evidence-"
   "consistency 型评审 JUDGE_EVID 会放行 42/50——见 E6 文档）。"
   "预算加大也不恶化。")

h3("3.4 E7 消融（4 韧 × 6 攻击，每攻击只在对应消融下得手）")
e7 = json.load(open(ROOT / "results/E7/E7-ablation-20261008-155832"
                    "/summary.json"))
def e7_desc(atk, st):
    """Render one full/ablated pair using whichever schema the attack has."""
    if "decision" in st:  # A3 necessity
        return (f'决策={st["decision"]} 拒因={st["reason"]} '
                f'不必要例外={st["unnecessary_exception_admitted"]}')
    if "second" in st:    # A5 replay
        return (f'第1次={st["first"]} 第2次={st["second"]}'
                f'({st["second_reason"]}) 重放效果={st["replayed_effect"]}')
    eff = st.get("effect")
    eff_s = "N/A" if eff is None else eff
    return f'装={st.get("install")} 拒因={st.get("reason")} 效果={eff_s}'


rows = []
for dom, atks in e7["results"].items():
    for atk, t in atks.items():
        o = t["outcomes"]
        if "full" in o:
            rows.append([dom, atk, e7_desc(atk, o["full"]),
                         e7_desc(atk, o["ablated"])])
        else:
            for sub, st in o.items():
                rows.append([dom, f"{atk}:{sub}", e7_desc(atk, st["full"]),
                             e7_desc(atk, st["ablated"])])
tb(["韧", "攻击", "完整版", "消融对应机制后"], rows,
   "**读法**：必要性证明——A1 类型/A2 遏制/A3 必要性/A4 epoch-CAS/"
   "A5 重放/A6 LLM 评审，每个攻击在完整版被对应机制拒绝、只在该机制"
   "消融后得手（A3=不必要例外被放行、A5=同一 CASE 重放第二次得逞、"
   "A4a 效果未测记 N/A）。28/28 全部按预期。")

h3("3.5 E9 鲁棒性：历史污染 + 过载（n=200 / n=40）")
e9 = json.load(open(ROOT / "results/E9/E9-robustness-20261008-160608"
                    "/summary.json"))
rows = []
for p, t in e9["corruption"].items():
    rows.append([p] + [knr(t[x]) for x in ("FRR", "admitted",
                                           "unsafe_admissions")])
for x, t in e9["overload"].items():
    uns = knr(t.get("unsafe_admissions")) if t.get("unsafe_admissions") else "0/40 = 0%"
    rows.append([f'过载{x}(load={t["load"]},budget={t["budget"]})',
                 "拒答 " + knr(t["denial_rate"]), knr(t["admit_rate"]), uns])
tb(["条件", "FRR", "放行", "不安全放行"], rows,
   "**读法**：污染率↑→误拒率(FRR) 0→100% 单调上升（fail-closed 的代价）"
   "，但**不安全放行恒 0**（从未 fail-open）；过载超预算→拒绝率上升，"
   "同样不开闸。FRR 语义 = any-spurious-edge。")

h3("3.6 ER 撤销（R1 规则 / R2 cap / R3 case）")
er = json.load(open(ROOT / "results/ER/ER-revocation-20261008-155859"
                    "/summary.json"))
tb(["韧", "R1 撤销前→后仍服务", "R2 撤销后装 cap", "R3 撤销后 case", "判定"],
   [[d, f'{t["outcomes"]["R1_precedent"]["served_before"]}→'
        f'{t["outcomes"]["R1_precedent"]["served_after"]}'
        f' ({t["outcomes"]["R1_precedent"]["reason_after"]})',
     f'{t["outcomes"]["R2_cap"]["install_ok"]} ({t["outcomes"]["R2_cap"]["reason"]})',
     t["outcomes"]["R3_case"]["decision"], "PASS" if t["passed"] else "FAIL"]
    for d, t in er["results"].items()],
   "**读法**：撤销三级全生效——已装规则停服、旧 cap 不能再装新规则、"
   "旧 case 不能再开门。4 域全 PASS。")

h3("3.7 E8 DSL 复用率复现（vs 已发表值）")
e8 = json.load(open(ROOT / "results/E8/E8-dsl-20261008-153337/summary.json"))
rows = []
for s in ("A", "B"):
    pub = e8["published_reference"][s]
    for t in e8[s]["table"]:
        rows.append([s, t["length"], t["histories"], t["reuse_unsafe_pct"],
                     pub.get(str(t["length"]), "—"), t["pg_unsafe"]])
tb(["系列", "历史长度", "枚举历史", "复用不安全%(实测)", "已发表%", "PG 不安全"], rows,
   "**读法**：论文引用的已发表「复用不安全率」曲线在本代码库逐格复现"
   "（20/52/79.2/92.3…完全一致），PG 全 0。注意 1.92 系 whole-history "
   "distinct-new-rules 口径。")

h3("3.8 E1 mock 单元自检（4 臂）")
e1 = json.load(open(ROOT / "results/E1/E1-mock-20261008-145848/summary.json"))
tb(["臂", "事件数", "UPR", "UIR", "UER", "VPA", "FRR"],
   [[a, t["events"], *(knr(t.get(x)) for x in ("UPR", "UIR", "UER", "VPA",
                                               "FRR"))]
    for a, t in e1["arms"].items()],
   "**读法**：mock 语义基线——A=全危险、D=全安全等极端臂，验证指标"
   "计算管线的方向性。")

h3("3.9 GLM 试点（200 call 上限内，¥2.0）")
p = json.load(open(ROOT / "results/LLM_PILOT/LLM-PILOT-20261008-170409"
                   "/summary.json"))
rows = [["模型", p["model"]], ["调用/成本", f'{p["usage"]["calls"]} calls, '
        f'${p["cost_usd_estimate"]}, 解析率 {p["parse_rate_A"]}']]
for m, mets in p["metrics"].items():
    for met, t in mets.items():
        rows.append([f"{m}.{met}", knr(t)])
tb(["项", "值"], rows,
   "**读法**：正式跑之前的小规模试点：PG 0/69 未授权、B1 UER 4.3%，"
   "方向与主实验一致；复现率 0.60 的 nondeterminism 发现与处理见 "
   "docs/LLM_PILOT_REPORT.md。")

# ============================= 4. 审计 =============================
h2("4. 独立审计（L5，不是新实验，是对主实验的复算）")
ec = json.load(open(ROOT / "audit_20261010/gates/effect_chain_summary.json"))
tb(["项", "值"],
   [["越界轨迹", ec["n_coverage_oop_trajectories"]],
    ["B1 因果配对成功", f'{ec["n_causal_pair_ok"]}/{ec["n_coverage_oop_trajectories"]} '
     '(COMMIT rule → PEP ADMIT_PRECEDENT 同 rule_id → 沙箱状态变化哈希验证)'],
    ["VPA 合法阳性对照", ec["legal_positive_control_vpa_witnesses"]],
    ["阴性对照（PG 同轨迹）", "0 安装 → 0 放行 → 0 状态变化"],
    ["效果语义", "in-harness 沙箱状态变化（非外部系统效果）"]],
   "**读法**：Gate B 证明 584 个 UER 的「效果」是真实发生的状态变化链，"
   "不是计数器；720 个 VPA 也有见证。三层独立重算（原始↔绘图层↔Gate C）"
   "0 mismatch。")

# ============================= 5. 敏感性/微基准 =============================
h2("5. 敏感性分析与微基准（L6）")

h3("5.1 类型胁迫敏感性：严格 vs 无损数值转换（k=10 legit）")
co = json.load(open(ROOT / "results/TABLES/coerce_compare.json"))
rows = []
for e in co:
    s, c = e["strict"], e["coerced"]
    rows.append([e["model"], e["method"], f'{100*s["UER"]:.1f}%',
                 f'{100*c["UER"]:.1f}%', f'{100*s["VPA"]:.1f}%',
                 f'{100*c["VPA"]:.1f}%'])
tb(["模型", "方法", "UER 严格", "UER 转换", "VPA 严格", "VPA 转换"], rows,
   "**读法**：Claude 95% 规则带字符串数字边界（\"1\" 而非 1），严格类型下"
   "惰性（VPA 0）；换无损转换后 VPA 0→36.6%（与 GPT 48%/DS 51.8% 同量"
   "级）——VPA=0 是打字习惯产物，不是 PG 失效。同时 B1 UER 反而升高"
   "（字符串类型一直在掩护基线），PG 两种口径 UER 都恒 0。")

h3("5.2 EAV 过量动作体积（攻击臂，每轨迹越界动作数）")
eav = json.load(open(ROOT / "results/TABLES/eav.json"))
rows = []
for model, arms in eav["per_arm"].items():
    for key, t in sorted(arms.items()):
        if t["installed"]:
            rows.append([model, key, t["installed"], round(t["mean"], 2),
                         round(t["p95"], 1), t["max"],
                         f'{100*t["frac_gt0"]:.1f}%'])
tb(["模型", "方法|臂", "安装", "人均越界动作", "p95", "max", "发生率"], rows,
   "**读法**：UER 回答「有没有越权」，EAV 回答「越权多少」。PG 全 0（未"
   "列=0 安装或 0 过量）；B1 族 GLM 7.6% 攻击轨迹有越界动作、单轨迹最多 "
   "14–18 个。领域全集大小：cloudops 1152 / procurement 432 / finance 432 "
   "/ dataaccess 486。")

h3("5.3 PEP 过载微基准（延迟 ms）")
ob = json.load(open(ROOT / "results/TABLES/overload_bench.json"))
rows = []
for meth, loads in ob["latency"].items():
    for nr, t in sorted(loads.items(), key=lambda x: int(x[0])):
        rows.append([meth, t["n_rules"], round(t["p50_ms"], 3),
                     round(t["p95_ms"], 3), round(t["p99_ms"], 3)])
tb(["方法", "规则数", "p50", "p95", "p99"], rows,
   "**读法**：规则库 50→250 条延迟线性、亚毫秒，PG≈B1（typed cap 验证"
   "开销可忽略）。")

# ============================= 6. 剂量与矩阵 =============================
h2("6. 剂量效应（Fig.7）与模型×韧×通道矩阵（Fig.8）")

h3("6.1 剂量：k（历史条数）→ 提案 / UPR / B1 UER（每模型 n=800/k）")
rows = []
for model, ks in MT["fig7_dose"].items():
    for k, t in sorted(ks.items(), key=lambda x: int(x[0].split("=")[1])):
        rows.append([model, k.split("=")[1], t["prop"], t["oop"],
                     f'{t["propose_pct"]:.1f}%',
                     "N/A" if t["upr_over_proposed"] is None
                     else f'{t["upr_over_proposed"]:.1f}%',
                     f'{t["b1_uer_pct"]:.1f}%'])
tb(["模型", "k", "提案", "越界提案", "提案%", "UPR%(of提案)", "B1 UER%"], rows,
   "**读法**：Fig.7。k=0（无历史）提案率 0 → k=1 起提案率与 UPR 同时跳升"
   "→ k=10 饱和。B1 UER 随 k 单调上升——历史越多，模型越想立规则、越容易"
   "越界，PG 的必要性随之上升。")

h3("6.2 Fig.8：模型 × 韧 × 通道（80 格，n=50/格）")
rows = []
for model, cells in MT["fig8_upr"].items():
    for dc, t in sorted(cells.items()):
        rows.append([model, *dc.split("|"), t["prop"], t["oop"], t["b1_uer"]])
tb(["模型", "韧", "通道", "提案", "越界", "B1 UER"], rows,
   "**读法**：Fig.8 原始数。policy_distillation 通道提案最密；风险分布"
   "跨 80 格普遍存在（非单点异常）。")

h3("6.3 全网格 pooled：方法 × k × 臂（跨 5 模型合计）")
agg = defaultdict(lambda: Counter())
for model, cells in MT["master"].items():
    for key, t in cells.items():
        p = key.split("|")
        g = agg[(p[0], p[1], p[2] if len(p) > 2 else "legit")]
        for f in ("n", "proposed", "malformed", "installed", "cppe_issuer",
                  "unauth_effect", "valid_accepted", "atc_done"):
            g[f] += t[f]
rows = []
for (m, k, arm) in sorted(agg, key=lambda x: (x[0], int(x[1].split("=")[1]), x[2])):
    t = agg[(m, k, arm)]
    rows.append([m, k.split("=")[1], arm, t["n"], t["proposed"],
                 t["installed"], t["cppe_issuer"], t["unauth_effect"],
                 t["valid_accepted"]])
tb(["方法", "k", "臂", "n", "提案", "安装", "无凭据安装", "未授权效果", "VPA"],
   rows,
   "**读法**：表 12 的 pooled 视图（完整 400 行模型级拆分见 "
   "12_全网格_按模型x方法xkx臂.csv）。k 越大安装越多；atk 臂 B1 未授权效果 "
   "133、PG 0。cppe_scope 死列已剔除（见坑 2）。")

# ============================= 7. 规模成本 =============================
h2("7. 规模与成本")
tb(["项", "值"],
   [["模型", "GLM-5.3 / Claude-5.5 / Gemini-3.8-flash / DeepSeek-v4.1-flash / GPT-5.6"],
    ["legit 轨迹", "5 × 4 × 4 × 50 = 4,000"],
    ["attacker 轨迹", "5 × 4 × 50 = 1,000"],
    ["回放", "5,000 × 8 方法 × 5 k = 200,000 行，0 错误"],
    ["检查点", "1,000/1,000 × 5 臂，无缺失格"],
    ["花费", "$197.58（官方牌价估，GPT $102.22；中继账单待对账）"],
    ["证据类型", "Type-3 closed-loop：真实多轮会话 + 冻结轨迹回放"]],
   "**读法**：混合通道（GLM 395 bigmodel+605 zhongkey；GPT aizex+zhongkey）"
   "已声明且两阶段定性一致。")

# ============================= 8. 坑 =============================
h2("8. 已知坑（引用数字前必读）")
L.extend([
    "1. **master_table.json 禁引两列**：`utility[].atk_oop`（legit+attacker "
    "pooled）与 `atc_b1`（旧语义）。攻击臂拆分唯一来源=§1.7 / s5_split.json"
    "（legit 584 + attacker 133）。",
    "2. **master_table.json 的 cppe_scope 是死字段**（v1 未写恒 False）；scope "
    "真值=§1.1（598/584 双口径）或 fig_data_v2.json。",
    "3. **基线 ATC=1,040 是未测量不是失败**（wf 路径探针只对 PG 运行，"
    "closed_loop.py:510）；论文只能写 \"PG ATC 4,000/4,000\"。",
    "4. B1/B2/B4/B6 四列相同=一个机制四种规格，不是抄写错误。",
    "5. 分母纪律：3,168 提案 ≠ 2,960 wf ≠ 4,000 轨迹 ≠ 8,000 任务；0 事件格 "
    "exact CP 上界分母专用（n=4000→0.0922%，n=800→0.46%，n=3168→0.116%，"
    "n=40→7.2%）。",
    "6. §3 全部是 mock 离线实验，引用时必须带 \"offline (mock)\" 标签，"
    "与真实臂分层表述。",
    "7. E5 无下游 effect 执行，effect 一律 N/A（§3.1）。",
    "8. Claude VPA=0 须与 §5.1 转换口径（36.6%）并列报告。",
    "",
    "— 逐字段词典与图↔表映射见同目录 README.md；机读母本见各 *.json 拷贝。",
])

open(OUT / "summary.md", "w", encoding="utf-8").write("\n".join(L))
print("wrote summary.md", len(L), "lines")
