"""Export ALL paper data into results/DATA_SUMMARY_20261010/ (tables 10-25).

Covers: Fig7 dose grid, Fig8 model×domain×channel, full master grid
(model×method×k×arm), coercion sensitivity, EAV, overload bench,
offline experiments E1/E2/E6/E7/E8/E9/ER, glm pilot, Gate-B causal chain,
run scale & cost. Sources are frozen JSONs only, zero API.

Run: .venv/bin/python scripts/export_data_summary_full.py
"""
import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "DATA_SUMMARY_20261010"
MT = json.load(open(ROOT / "results/TABLES/master_table.json"))


def w(name, header, rows):
    with open(OUT / name, "w", newline="", encoding="utf-8-sig") as f:
        cw = csv.writer(f)
        cw.writerow(header)
        cw.writerows(rows)
    print("wrote", name, len(rows), "rows")


def knr(m):  # {k,n,rate,...} -> "k/n/rate%" triplet, N/A-aware
    if m is None or m.get("na") or m.get("n") == 0:
        return ["N/A", "N/A", "N/A"]
    r = m["rate"]
    if r is None:
        return ["N/A", "N/A", "N/A"]
    return [m["k"], m["n"], f"{100*r:.2f}"]


# ---- 10  Fig.7 dose: propose / UPR / B1-UER vs k --------------------------
rows = []
for model, ks in MT["fig7_dose"].items():
    for k, t in sorted(ks.items(), key=lambda x: int(x[0].split("=")[1])):
        rows.append([model, k.split("=")[1], t["n"], t["prop"], t["oop"],
                     t["propose_pct"],
                     t["upr_over_n"],
                     "N/A" if t["upr_over_proposed"] is None
                     else round(t["upr_over_proposed"], 2),
                     t["b1_uer_pct"]])
w("10_剂量曲线_Fig7_按模型xk.csv",
  ["模型", "k(历史条数)", "n轨迹", "提案", "越界提案oop", "提案%",
   "UPR%(of全部轨迹)", "UPR%(of提案)", "B1 UER%"], rows)

# ---- 11  Fig.8: model × domain × channel ----------------------------------
rows = []
for model, cells in MT["fig8_upr"].items():
    for dc, t in sorted(cells.items()):
        d, c = dc.split("|")
        rows.append([model, d, c, t["n"], t["prop"], t["oop"], t["b1_uer"]])
w("11_UPR矩阵_Fig8_按模型x领域x通道.csv",
  ["模型", "领域", "通道", "n(=50/格)", "提案prop", "越界oop", "B1_UER计数"], rows)

# ---- 12  full master grid: model × method × k × arm -----------------------
rows = []
for model, cells in MT["master"].items():
    for key, t in cells.items():
        p = key.split("|")          # B0|k=0|atk  or  B0|k=0
        arm = p[2] if len(p) == 3 else "legit"
        rows.append([model, p[0], p[1].split("=")[1], arm,
                     t["n"], t["proposed"], t["malformed"], t["installed"],
                     t["cppe_issuer"], t["unauth_effect"], t["valid_accepted"],
                     t["atc_done"], t["atc_via_case"],
                     t["n_tasks"], t["turn_successes"]])
rows.sort(key=lambda r: (r[0], r[1], int(r[2]), r[3]))
w("12_全网格_按模型x方法xkx臂.csv",
  ["模型", "方法", "k", "臂(legit/atk)", "n轨迹", "提案", "malformed",
   "安装", "无凭据安装cppe_issuer", "未授权效果unauth_effect",
   "VPA valid_accepted", "ATC完成", "ATC经case", "n_tasks", "turn_successes"],
  rows)
print("note: cppe_scope dead field omitted from 12 (use 00/03/fig_data_v2)")

# ---- 13  coercion sensitivity ---------------------------------------------
co = json.load(open(ROOT / "results/TABLES/coerce_compare.json"))
rows = []
for e in co:
    for side in ("strict", "coerced"):
        s = e[side]
        rows.append([e["model"], e["method"],
                     "严格(原样)" if side == "strict" else "无损数值转换", side,
                     s["n"], s["propose_rate"], s["install_rate"],
                     s["cppe_issuer"], s["UER"], s["VPA"], s["ATC"],
                     s["ATC_via_case"], s["malformed"]])
w("13_胁迫敏感性_严格vs无损转换.csv",
  ["模型", "方法", "口径", "side", "n", "提案率", "安装率", "无凭据安装率",
   "UER", "VPA", "ATC", "ATC经case", "malformed率"], rows)

# ---- 14  EAV excess-action volume (attacker arm) --------------------------
eav = json.load(open(ROOT / "results/TABLES/eav.json"))
rows = []
for model, arms in eav["per_arm"].items():
    for key, t in sorted(arms.items()):
        rows.append([model, *key.split("|"), t["n"], t["installed"],
                     round(t["mean"], 4), t["median"], t["p90"],
                     round(t["p95"], 3), t["max"], t["frac_gt0"],
                     round(t["mean_norm"], 6)])
w("14_EAV_过量动作体积_攻击臂.csv",
  ["模型", "方法", "臂", "n", "安装数", "人均过量动作mean", "median", "p90",
   "p95", "max", "有过量动作占比", "mean/领域全集"], rows)

# ---- 15  overload microbenchmark ------------------------------------------
ob = json.load(open(ROOT / "results/TABLES/overload_bench.json"))
rows = []
for meth, loads in ob["latency"].items():
    for nr, t in sorted(loads.items(), key=lambda x: int(x[0])):
        rows.append([meth, t["n_rules"],
                     round(t["p50_ms"], 4), round(t["p95_ms"], 4),
                     round(t["p99_ms"], 4), round(t["mean_ms"], 4)])
w("15_过载微基准_延迟.csv",
  ["方法", "规则数n_rules", "p50_ms", "p95_ms", "p99_ms", "mean_ms"], rows)

# ---- 16  E2 offline baseline matrix ---------------------------------------
e2 = json.load(open(ROOT / "results/E2/E2-baselines-20261008-155014"
                    "/summary.json"))["by_method"]
rows = []
for m, t in e2.items():
    r = [m, t.get("desc", "")]
    for met in ("UIR", "UER", "VPA", "FRR", "ATC"):
        r.extend(knr(t.get(met)))
    rows.append(r)
w("16_E2_离线基线矩阵_mock800格.csv",
  ["方法", "描述", "UIR k", "UIR n", "UIR%", "UER k", "UER n", "UER%",
   "VPA k", "VPA n", "VPA%", "FRR k", "FRR n", "FRR%", "ATC k", "ATC n",
   "ATC%"], rows)

# ---- 17  E6 adaptive attacks ----------------------------------------------
e6 = json.load(open(ROOT / "results/E6/E6-adaptive-20261008-160427"
                    "/summary.json"))
rows = []
for atk, budgets in e6["pg_unsafe_by_budget"].items():
    for b, t in sorted(budgets.items(), key=lambda x: int(x[0])):
        rows.append([atk, int(b), *knr(t)])
w("17_E6_自适应攻击_PG不安全放行.csv",
  ["攻击类型", "预算budget", "不安全放行k", "n", "不安全放行率%"], rows)

# ---- 18  E7 ablations ------------------------------------------------------
e7 = json.load(open(ROOT / "results/E7/E7-ablation-20261008-155832"
                    "/summary.json"))
def e7_row(dom, atk, sub, fo, ao):
    return [dom, f"{atk}:{sub}" if sub else atk,
            fo.get("install", ""), fo.get("reason", ""), fo.get("effect", ""),
            ao.get("install", ""), ao.get("effect", ""),
            "PASS" if fo.get("install") is False and ao.get("install") else "?"]


rows = []
for dom, atks in e7["results"].items():
    for atk, t in atks.items():
        o = t["outcomes"]
        if "full" in o:
            rows.append(e7_row(dom, atk, "", o["full"], o["ablated"]))
        else:  # A4 has two sub-attacks, each with full/ablated
            for sub, st in o.items():
                rows.append(e7_row(dom, atk, sub, st["full"], st["ablated"]))
w("18_E7_消融穿透_每攻击只在对应消融下得手.csv",
  ["领域", "攻击", "完整版安装", "完整版拒绝原因", "完整版效果",
   "消融后安装", "消融后效果", "完整版拒+消融后装"], rows)

# ---- 19  E9 robustness: corruption + overload -----------------------------
e9 = json.load(open(ROOT / "results/E9/E9-robustness-20261008-160608"
                    "/summary.json"))
rows = []
for p, t in e9["corruption"].items():
    rows.append(["历史污染", p, *knr(t["FRR"]), *knr(t["admitted"]),
                 *knr(t["unsafe_admissions"])])
for x, t in e9["overload"].items():
    rows.append([f"过载{x}(load={t['load']},budget={t['budget']})", "",
                 *knr(t["denial_rate"]), *knr(t["admit_rate"]), "", "", ""])
w("19_E9_鲁棒性_污染与过载.csv",
  ["条件", "污染率p", "FRR k", "FRR n", "FRR%", "放行 k", "放行 n", "放行%",
   "不安全放行 k", "不安全放行 n", "不安全放行%"], rows)

# ---- 20  ER revocation -----------------------------------------------------
er = json.load(open(ROOT / "results/ER/ER-revocation-20261008-155859"
                    "/summary.json"))
rows = []
for dom, t in er["results"].items():
    o = t["outcomes"]
    rows.append([dom,
                 o["R1_precedent"]["served_before"],
                 o["R1_precedent"]["served_after"],
                 o["R1_precedent"]["reason_after"],
                 o["R2_cap"]["install_ok"], o["R2_cap"]["reason"],
                 o["R3_case"]["decision"], o["R3_case"]["reason"],
                 "PASS" if t["passed"] else "FAIL"])
w("20_ER_撤销_三级.csv",
  ["领域", "R1撤销前规则仍服务", "R1撤销后仍服务", "R1撤销后原因",
   "R2撤销后能否再装cap", "R2原因", "R3撤销后CASE决策", "R3原因", "判定"], rows)

# ---- 21  E8 DSL reproduction ----------------------------------------------
e8 = json.load(open(ROOT / "results/E8/E8-dsl-20261008-153337/summary.json"))
rows = []
for series in ("A", "B"):
    pub = e8["published_reference"][series]
    for t in e8[series]["table"]:
        rows.append([series, t["length"], t["histories"], t["reuse_unsafe"],
                     t["reuse_unsafe_pct"], pub.get(str(t["length"]), ""),
                     t["pg_unsafe"]])
w("21_E8_DSL复现_复用不安全率.csv",
  ["系列", "历史长度", "枚举历史数", "复用不安全k", "复用不安全%(实测)",
   "已发表值%(对照)", "PG不安全k"], rows)

# ---- 22  E1 mock unit sanity ----------------------------------------------
e1 = json.load(open(ROOT / "results/E1/E1-mock-20261008-145848"
                    "/summary.json"))
rows = []
for arm, t in e1["arms"].items():
    r = [arm, t["events"]]
    for met in ("UPR", "UIR", "UER", "ATC", "VPA", "FRR"):
        r.extend(knr(t.get(met)))
    rows.append(r)
w("22_E1_mock单元自检.csv",
  ["臂", "事件数", "UPR k/n/%", "", "", "UIR k/n/%", "", "", "UER k/n/%", "",
   "", "ATC k/n/%", "", "", "VPA k/n/%", "", "", "FRR k/n/%", "", ""], rows)

# ---- 23  glm pilot ---------------------------------------------------------
p = json.load(open(ROOT / "results/LLM_PILOT/LLM-PILOT-20261008-170409"
                   "/summary.json"))
rows = [["模型", p["model"]],
        ["调用数", p["usage"]["calls"]],
        ["prompt/completion tokens",
         f"{p['usage']['prompt_tokens']}/{p['usage']['completion_tokens']}"],
        ["成本USD(估)", p["cost_usd_estimate"]],
        ["解析率armA", p["parse_rate_A"]]]
for m, mets in p["metrics"].items():
    for met, t in mets.items():
        rows.append([f"{m}.{met}", *knr(t)])
w("23_pilot试点_glm53_69格.csv", ["项", "值/k", "n", "rate%"], rows)

# ---- 24  Gate-B causal chain ----------------------------------------------
ec = json.load(open(ROOT / "audit_20261010/gates/effect_chain_summary.json"))
w("24_因果链_GateB.csv", ["项", "值"],
  [["越界轨迹数", ec["n_coverage_oop_trajectories"]],
   ["B1 因果链配对成功(COMMIT->PEP放行->沙箱状态变化)", ec["n_causal_pair_ok"]],
   ["全部通过", ec["PASS_causal_chain_all"]],
   ["VPA 合法阳性对照见证", ec["legal_positive_control_vpa_witnesses"]],
   ["阴性对照", ec["negative_control"]],
   ["效果语义", ec["label"]]])

# ---- 25  run scale & cost (from frozen report) ----------------------------
w("25_规模与成本.csv", ["项", "数值", "说明"],
  [["模型数", 5, "GLM/Claude/Gemini/DeepSeek/GPT"],
   ["legit轨迹", "5×4×4×50=4,000", "模型×领域×通道×种子"],
   ["attacker轨迹", "5×4×50=1,000", "episodic,每条2次被拒探针"],
   ["replay行数", "5,000×8×5=200,000", "轨迹×方法×k,0错误"],
   ["检查点", "1,000/1,000×5臂", "无缺失格"],
   ["花费USD(官方牌价估)", "$197.58", "GPT $102.22;中继账单待对账"],
   ["证据类型", "Type-3 closed-loop", "真实多轮会话+冻结轨迹回放"]])

# ---- machine-readable copies ----------------------------------------------
import shutil
for src, dst in [
        ("results/TABLES/master_table.json", "master_table.json"),
        ("results/TABLES/coerce_compare.json", "coerce_compare.json"),
        ("results/TABLES/eav.json", "eav.json"),
        ("results/TABLES/overload_bench.json", "overload_bench.json"),
        ("results/TABLES/s5_split.json", "s5_split.json"),
        ("audit_20261010/gates/effect_chain_summary.json",
         "gateB_effect_chain.json")]:
    shutil.copy2(ROOT / src, OUT / dst)
    print("copied", dst)
print("DONE ->", OUT)
