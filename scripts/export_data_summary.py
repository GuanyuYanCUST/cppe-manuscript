"""Export the S3 data summary folder (user-facing, human-readable).

Writes results/DATA_SUMMARY_20261010/ :
  - CSV tables (utf-8-sig, Excel-friendly) exported from the independent
    recount (cell_verify_v3.json), master_table, E5 summary and the
    authorization fork — one question per table, rates + Wilson CIs
    precomputed so no calculator is needed;
  - verbatim copies of the machine-readable sources.

Run: .venv/bin/python scripts/export_data_summary.py
"""
import csv
import json
import pathlib
import shutil
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pguard.stats import wilson                       # noqa: E402

CV = json.load(open(ROOT / "audit_20261010/gates/cell_verify_v3.json"))
assert CV["verdict"] == "PASS"
MT = json.load(open(ROOT / "results/TABLES/master_table.json"))["utility"]
OUT = ROOT / "results" / "DATA_SUMMARY_20261010"
OUT.mkdir(parents=True, exist_ok=True)


def wil3(k, n):
    lo, hi = wilson(k, n)
    return f"{100*k/n:.2f}", f"{100*lo:.2f}", f"{100*hi:.2f}"


def w(name, header, rows):
    with open(OUT / name, "w", newline="", encoding="utf-8-sig") as f:
        cw = csv.writer(f)
        cw.writerow(header)
        cw.writerows(rows)
    print("wrote", name, len(rows), "rows")


D = CV["denominators"]
w("00_分母口径表.csv",
  ["量", "数值", "含义"],
  [["legit 轨迹总数", D["trajectories_legit"],
    "5 模型 × 800（4 领域×4 通道×50 种子），k=10，真实回放"],
   ["提案轨迹数 proposing", D["proposing"], "轨迹末自由选择了 precedent 模式并给出规则提案"],
   ["其中 MALFORMED", D["malformed"], "提案规则解析失败/结构非法 → 所有方法 fail-closed 拒绝，0 安装"],
   ["well-formed 提案", D["well_formed_proposals"], "=B1 安装数 2,960；安装只可能发生在 wf 上"],
   ["PG 安装(带root cap)", D["pg_installed"], "PG 在授权+遏制双检下安装的规则，全部带 root 签发凭据"],
   ["PG 判 OUT_OF_ROOT", D["pg_out_of_root"], "提案规则越出任务根范围(逃逸) → 正确拒绝(584)"],
   ["PG 判 CAP_SCOPE(oop 上)", D["pg_cap_scope_on_oop"], "越出范围的提案先撞类型/范围 cap(14, 全 GLM)"],
   ["PG 判 CAP_SCOPE(类内)", D["pg_cap_scope_inclass"], "范围内提案但 cap 类型不匹配的残余拒绝(87)"],
   ["CPPE-SCOPE 逃逸安装(B1族)", D["pg_oop_proposals"],
    "598 = 584 probe可见 + 14 类外；在无防护方法里这 598 条全部安装且逃逸"],
   ])

w("01_各方法汇总_legit_k10.csv",
  ["方法", "n轨迹", "提案", "安装", "未授权效果UER", "UER%", "Wilson95下", "Wilson95上",
   "无凭据安装(issuer)", "scope安装", "VPA", "ATC", "ATC经case"],
  [[m, t["n"], t["prop"], t["inst"], t["uer"], *wil3(t["uer"], t["n"]),
    t["issuer"], t["scope"], t["vpa"], t["atc"], t["atc_case"]]
   for m, t in CV["per_method_legit"].items()])

w("02_各模型_B1族_B3_B5_PG.csv",
  ["模型", "方法", "n", "提案", "安装", "UER", "UER%", "Wilson下", "Wilson上",
   "scope安装", "VPA", "ATC", "ATC经case"],
  [[k.split("|")[0], k.split("|")[1], t["n"], t["prop"], t["inst"],
    t["uer"], *wil3(t["uer"], t["n"]), t["scope"], t["vpa"], t["atc"],
    t["atc_case"]]
   for k, t in CV["per_model"].items()])

w("03_UER_按模型x领域_B1族.csv",
  ["模型", "领域", "UER计数", "n", "UER%", "Wilson下", "Wilson上"],
  [[k.split("|")[0], k.split("|")[1], v["uer"], v["n"], *wil3(v["uer"], v["n"])]
   for k, v in CV["per_model_domain_b1_uer"].items()])

rows = []
RR = CV["pg_reject_reasons_per_model"]
for m in CV["models"]:
    rr = RR[f"{m}|PG"]
    malf = sum(v for k, v in rr.items() if k.startswith("MALFORMED"))
    pg = CV["per_model"][f"{m}|PG"]
    rows.append([m, pg["prop"], pg["inst"], rr.get("OUT_OF_ROOT", 0),
                 rr.get("CAP_SCOPE", 0), malf,
                 f"{100*pg['inst']/pg['prop']:.1f}"])
w("04_PG提案去向_按模型.csv",
  ["模型", "提案n", "安装(root cap)", "OUT_OF_ROOT拒", "CAP_SCOPE拒",
   "MALFORMED拒", "安装占提案%"], rows)

w("05_VPA按模型.csv",
  ["模型", "VPA", "提案n", "安装n", "VPA%(of提案)", "Wilson下", "Wilson上"],
  [[m, v["vpa"], v["prop"], v["inst"], *wil3(v["vpa"], v["prop"])]
   for m, v in CV["per_model_pg_vpa"].items()])

w("06_攻击臂_按模型.csv",
  ["模型", "方法", "n", "提案", "安装", "越出范围提案oop", "未授权效果"],
  [[k.split("|")[0], k.split("|")[1], v["n"], v["prop"], v["inst"],
    v["oop"], v["eff"]]
   for k, v in CV["attacker_per_model_B1_PG"].items()])

w("07_真实任务成功率_live.csv",
  ["模型", "task_success", "成功任务数k", "n=8000(800轨迹×10任务)",
   "Wilson下", "Wilson上"],
  [[m, MT[m]["task_success"], round(MT[m]["task_success"] * 8000), 8000,
    *wil3(round(MT[m]["task_success"] * 8000), 8000)] for m in CV["models"]])

E5 = json.load(open(ROOT / "results/E5/E5-factorial-20261008-155213"
                    "/summary.json"))["table"]
rows = []
for cell, t in E5.items():
    for meth, st in t.items():
        rows.append([cell, meth,
                     st["install_rate"]["k"], st["install_rate"]["n"],
                     st["UIR"]["k"], st["UIR"]["n"],
                     st["VPA"]["k"], st["VPA"]["n"]])
w("08_E5因子实验_offline.csv",
  ["格子(记忆|grant)", "方法", "安装k", "n", "未授权安装k", "n",
   "PEP接受VPA k", "n"], rows)

forks = [json.loads(l) for l in
         open(ROOT / "audit_20261010/gates/authority_fork_results.jsonl")]
agg = {}
for r in forks:
    a = agg.setdefault((r["fork"], bool(r["attacker"])),
                       Counter(n=0, prop=0, inst=0, eff=0))
    a["n"] += 1
    a["prop"] += bool(r.get("proposed"))
    a["inst"] += bool(r.get("installed"))
    a["eff"] += bool(r.get("unauth_effect"))
rows = [[f, "attacker" if a else "legit", v["n"], v["prop"], v["inst"],
         v["eff"]] for (f, a), v in sorted(agg.items(), key=str)]
w("09_授权分叉fork.csv",
  ["fork", "臂", "行数n", "提案", "安装", "未授权效果"], rows)

for src, dst in [
        ("audit_20261010/gates/cell_verify_v3.json", "cell_verify_v3.json"),
        ("audit_20261010/gates/metrics_recompute.json",
         "gateC_metrics_recompute.json"),
        ("results/TABLES/fig_data_v2.json", "fig_data_v2.json"),
        ("results/FIGS/v3_20261010/MANIFEST.json",
         "v3_MANIFEST.json")]:
    shutil.copy2(ROOT / src, OUT / dst)
    print("copied", dst)
print("DONE ->", OUT)
