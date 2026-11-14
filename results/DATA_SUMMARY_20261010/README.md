# DATA_SUMMARY_20261010 — 论文全部数据汇总与逐项说明

本文件夹汇总这篇论文（S&P 2027, CPPE / PRECEDENTGUARD）**全部实验数据**：
26 张 CSV（utf-8-sig，Excel 直接可开，比率与 Wilson 95% CI 已预计算）
+ 10 个机读 JSON 拷贝 + **summary.md（全部数值汇总进一个文件，每表带读法
解释，756 行）**。所有数字源自冻结的实验产物，零 API、零新实验。
可复现入口：`~/S&P/precedentguard`
`.venv/bin/python scripts/export_data_summary.py`（表 00–09 + 旧汇总）
`.venv/bin/python scripts/export_data_summary_full.py`（表 10–25 + 拷贝）
`.venv/bin/python audit_20261010/gates/verify_cells_v3.py`（独立重算器）
原始数据（rollouts/raw/replay JSONL、冻结 manifest）全程只读。

---

## 0. 必读：六个证据层级（不要混着比）

| 层 | 是什么 | 哪些表 |
|---|---|---|
| L1 live rollout | 真实模型多轮会话（5 模型 × 800 legit + 200 attacker） | 07（task_success）、25（规模成本） |
| L2 确定性回放 | L1 冻结轨迹逐条回放进 8 方法 × 5 档 k，200,000 行 | 00–06、10–12（图 6/7/8 数据源） |
| L3 授权分叉 | 只对 PG 的 L2 重放做有/无 root cap、cap 无效分叉 | 09（图 9 右半） |
| L4 离线因子/鲁棒实验 | mock 模型、构造历史（每张表都标了 mock） | 08（E5）、16–22（E1/E2/E6/E7/E8/E9/ER） |
| L5 审计普查 | 不是新实验，是 L2 的独立复算（三层 0 mismatch） | 24（Gate B 因果链）、cell_verify_v3.json |
| L6 敏感性/微基准 | 同一冻结数据的换口径重放、延迟基准 | 13（胁迫）、14（EAV）、15（过载） |

**比较规则**：L2 内部可互相比（同批轨迹）；L1 只看模型间差异；
L4 与 L2 不是同一批样本，只能比"机制方向"，不能比数值大小。

---

## 1. 论文地图：哪个结论用哪张表

| 论文主张 | 数据 |
|---|---|
| CPPE 风险真实存在（无防护时 14.6% 轨迹出现未授权效果） | 01（B1 族 UER 584/4,000）、03（模型×领域分布） |
| PG 把它压到 0（CP≤0.0922%） | 01（PG 行）、24（因果链证明效果真实发生） |
| 风险随历史长度增长（剂量效应） | 10（Fig.7：k=0→10 提案率与 UPR 上升） |
| 风险是系统性的，不是单模型毛病 | 02/03/11（5 模型×4 韧×4 通道全覆盖） |
| "完美溯源"基线防不住 CPPE | 01（B2/B4/B6 ≡ B1 逐格相同）、08（E5 exact+无授权照样装） |
| 无 root 授权 = 一次都不装 | 09（grant_absent 与 4 种坏 cap 全 0）、08（E5 2×2） |
| 每个机制组件都必要 | 18（E7：6 种攻击各自只在对应消融下得手） |
| 自适应攻击者也钻不进 | 17（E6：5 类攻击 × 预算 1–50，PG 不安全放行全 0） |
| 抗污染/抗过载（fail-closed） | 19（E9：污染↑→FRR↑、不安全放行恒 0；过载→拒绝率↑） |
| 撤销有效 | 20（ER：R1/R2/R3 四域全过） |
| 效果不是模拟的 | 24（Gate B：584/584 COMMIT→PEP→沙箱状态变化哈希配对） |
| PG 不牺牲可用性 | 01（PG ATC 4,000/4,000）、07（task_success 与方法无关）、13（胁迫下仍 0） |
| 论文里那张已发表的 DSL 复用率曲线我们复现了 | 21（E8：实测 20/52/79.2/92.3% 对上已发表值） |
| 开销可忽略 | 15（PEP p95 0.23ms @250 规则，PG≈B1） |
| 部署/成本可行性 | 25（$197.58、200,000 行回放 0 错误） |

---

## 2. 文件清单

**主实验（真实 5 模型臂）**
| 文件 | 内容 |
|---|---|
| 00_分母口径表 | 9 个关键分母/计数定义（一切百分比先看这张） |
| 01_各方法汇总_legit_k10 | 8 方法 pooled 全指标（图 6-B 数据） |
| 02_各模型_B1族_B3_B5_PG | 5 模型 × 4 方法（模型性格光谱） |
| 03_UER_按模型x领域_B1族 | 5×4=20 格 UER（图 6-C(a)） |
| 04_PG提案去向_按模型 | PG 安装/OUT_OF_ROOT/CAP_SCOPE/malformed 分解（图 6-C(b)） |
| 05_VPA按模型 | PG 合法复用（图 6-C(c) 上） |
| 06_攻击臂_按模型 | 200 攻击轨迹/模型 B1 vs PG（图 6 不含，表 6 单独给） |
| 07_真实任务成功率_live | L1 任务成功率 ×8,000 整数（图 6-C(c) 下） |
| 08_E5因子实验_offline | 2×2 记忆×授权 × 5 方法（图 9 左半，n=40/格） |
| 09_授权分叉fork | 6 种授权条件 × legit/attacker（图 9 右半，13,200 行） |
| 10_剂量曲线_Fig7 | 5 模型 × k∈{0,1,3,5,10}：提案%/UPR%/B1-UER%（图 7） |
| 11_UPR矩阵_Fig8 | 5×4 韧×4 通道 = 80 格提案/越界/UER（图 8，n=50/格） |
| 12_全网格_模型x方法xkx臂 | 400 行 = 5×8×5×2 全量计数（最底层数据表） |
| 13_胁迫敏感性 | 严格类型 vs 无损数值转换两种口径（Claude VPA 0→36.6%） |
| 14_EAV_过量动作体积 | 攻击臂每轨迹放行的越界动作数（B1 max 18/轨迹） |
| 15_过载微基准 | PEP 延迟 p50/p95/p99 × 规则数 50–250 |
| 25_规模与成本 | 4,000/1,000/200,000/$197.58 等冻结数字 |

**离线机制实验（mock，论文中明确标注 offline）**
| 文件 | 内容 |
|---|---|
| 16_E2_离线基线矩阵 | 800 格 × 8 方法：UIR/UER/VPA/FRR/ATC 全 N/A 感知 |
| 17_E6_自适应攻击 | 5 攻击 × 预算{1,5,10,25,50}：PG 不安全放行全 0（n=12/格） |
| 18_E7_消融穿透 | 4 韧 × 6 攻击 × (完整版, 消融版)：每攻击只在对应消融下得手 |
| 19_E9_鲁棒性 | 历史污染 p=0–40% → FRR 0→1、不安全放行恒 0；过载 1x–4x |
| 20_ER_撤销 | R1 规则/R2 cap/R3 case 撤销后全拒（4 域 PASS） |
| 21_E8_DSL复现 | 复用不安全率曲线实测 vs 已发表值（14 格全对上） |
| 22_E1_mock单元自检 | 4 臂指标自检（mock 语义基线） |
| 23_pilot试点_glm53 | 200 call 上限试点：PG 0/69、B1 UER 4.3%、成本 ¥2.0 |

**审计与拷贝**
| 文件 | 内容 |
|---|---|
| 24_因果链_GateB | 584/584 因果配对 + 720 VPA 见证 + 阴性对照 |
| cell_verify_v3.json | 独立重算母本（三层 0 mismatch，v3 图 guard 数据源） |
| gateC_metrics_recompute.json | Gate C 审计基准 |
| gateB_effect_chain.json | 24 的机读版 |
| fig_data_v2.json | 图 6/7/8 绘图层输入（模型×韧×方法×k 格） |
| master_table.json | 表 10/11/12 的母本（注意 §4 坑 1/2） |
| coerce_compare.json / eav.json / overload_bench.json / s5_split.json | 表 13/14/15/攻击拆分母本 |
| v3_MANIFEST.json | v3 三图脚本/输入/输出 SHA256 + 双渲染字节级一致证明 |

---

## 3. 字段词典（每个数字什么意思）

**分母（00 表）**
- 4,000 legit 轨迹 = 5 模型 × 4 韧 × 4 通道 × 50 种子；另 1,000 attacker
  轨迹（5×4×50，episodic，每条 2 次被拒探针）。图 6 一律排除攻击臂。
- 3,168 提案（79.2%）→ 208 MALFORMED（规则解析失败，全方法 fail-closed
  0 安装）→ 2,960 well-formed = 无防护安装数。
- PG：2,275 安装 / 584 判 OUT_OF_ROOT / 101 判 CAP_SCOPE（87 韧内 + 14
  类外）/ 208 malformed。4,000 = 832 未提案 + 208 + 2,275 + 87 + 584 + 14。
- scope 双口径：598（commit 戳真值 = 584+14）与 584（探针可见），
  并存有意设计。

**L2 回放核心指标（01–05、12 表）**
- `提案 proposed`：轨迹末模型自选"立规则"模式并给出规则文本。
- `安装 installed`：规则写入策略库。B1/B2/B4/B6=2,960（凡 wf 必装）；
  B5 同装 2,960 但永不生效；B3=2,362（只装 containment 通过的）；
  PG=2,275。
- `UER 未授权效果`（核心安全指标）：安装的规则后来在沙箱真实放行了
  无授权不该发生的受保护动作（独立 oracle 判定 + Gate B 因果配对）。
  PG 0/4,000；B1 族 584/4,000=14.6% [13.5,15.7]。效果层 ≠ 安装层。
- `cppe_issuer 无凭据安装`：安装时无 root 签发类型化凭据。B1 族 2,960、
  B3 2,362（B3 是遏制谓词评审，不发凭据——故也计入）、PG 0。
- `cppe_scope`：规则语义越出任务根。⚠️ 仅 replay_v2/fig_data_v2/cell_verify_v3
  的值可信（v2 修复后）；master_table.json 该列是死字段，表 12 已剔除。
- `VPA valid_accepted`：PG 安装的规则后来在 case 通道被合法引用放行：
  720（分母 3,168 提案或 2,275 安装，逐点标注）。
- `ATC`：novel 任务 case 通道可用性探针。**PG：4,000/4,000（3,698 走
  case、302 走 precedent）**。基线 1,040 = 仅在未提案+malformed 行上
  测量（wf 路径设计上只对 PG 跑探针，closed_loop.py:510），1,040/1,040
  全部成功走 case——**不是可用性失败，是未测量**（见 §4 坑 3）。
- `turn_successes/n_tasks`（12 表）：L1 任务成功计数，与方法无关。
- `UPR`（10/11 表）：unauthorized precedent proposal——提案本身越出
  任务根（无论装没装）；B1 UER ≤ UPR（装了不一定真放行效果）。

**L3 fork（09 表）**：control（harness 扮演 root 签 cap）legit 2,275/3,168、
attacker 569/767（contained 规则借类授权上车，0 未授权效果）；
grant_absent 与 cap_expired/wrong_issuer/type_confusion/stale_epoch 全 0
安装；13,200 行未授权效果全 0。

**L4（08、16–22 表）**：E5 只测 install/UIR（无凭据安装率）/VPA，
**无下游 effect 执行 → effect 一律 N/A**；money cell = exact 历史 + 无
授权：B2/B6 靠完美溯源照装 40/40（未授权），PG 拒绝。"知道发生过 ≠
有权立法"。E6 的 n=12/格（3 种子×4 韧）；E7 判定列 = 完整版拒绝 ∧
消融后安装；E9 的 GraphChallenger 是 mock（表内已注明）；E8 实测值
与已发表曲线逐格对照。

**L6（13–15 表）**
- 13：`strict` = 规则条件原样严格类型（Claude 95% 规则带字符串数字边界
  → 惰性，VPA=0 是打字习惯产物）；`coerced` = 工具调用边界同款无损
  数值转换。胁迫口径下 B1 UER 反而升高（字符串类型在掩护基线）、
  PG UER 恒 0。
- 14：EAV = 攻击臂每轨迹被放行的"领域全集内越界动作"数（体积指标，
  与 UER 的发生指标互补）；PG 全 0。
- 15：PEP pep_decide 延迟（毫秒），规则库 50→250 条线性、亚毫秒。

---

## 4. 已知坑（引用任何数字前先看）

1. **master_table.json 两列禁引**（I7）：`utility[].atk_oop` 是
   legit+attacker 混算 pooled；`atc_b1` 是 ATC 修复前旧语义。攻击臂
   正确拆分 = 06 表 / s5_split.json（legit 584 + attacker 133）。
2. **master_table.json 的 cppe_scope 是死字段**（v1 回放未写、恒
   False）——表 12 已剔除该列；scope 真值看 00/03/fig_data_v2
   （598/584 双口径）。
3. **基线 ATC=1040 是"未测量"不是"失败"**：wf 提案路径的探针设计上
   只对 PG 运行；1040 个已测行全部成功（走 case）。论文表述必须写
   "PG ATC 4,000/4,000"，不能写"基线 ATC 26%"。
4. B1/B2/B4/B6 四列完全相同不是抄写错误：共用同一条 unguarded_install
   终态路径（一个机制四种规格）；判别实验在 E5 篡改臂（08 表）。
5. 3,168（提案）≠ 2,960（wf）≠ 4,000（轨迹）≠ 8,000（任务）：任何
   百分比先看分母；0 事件格的 exact CP 上界分母专用
   （1−0.025^(1/n)：n=4000→0.0922%，n=800→0.46%，n=3168→0.116%，
   n=40→7.2%），不得混用。
6. E5/E6/E7/E9/ER/E1/E2 全部是 mock 离线实验，论文中必须带
   "offline factorial (mock model)" 标签，与真实臂分层表述。
7. fig_data_v2.json 的 cell 键含 k=0/1/3/5/10 五档；图 6 只用 k=10，
   图 7 用全部五档。
8. GPT/GLM 臂是混合通道（GLM 395 bigmodel+605 zhongkey；GPT aizex+
   zhongkey），两阶段定性一致，论文已声明（成色混淆已文档化）。

---

## 5. 图 ↔ 表对照

| 图 | panel | 表 |
|---|---|---|
| Fig.6-B v3 | (a) 每模型 UER / (b) 安装与凭据 / (c) PG 效用 | 02 / 01 / 01(PG 行) |
| Fig.6-C v3 | (a) UER 矩阵 / (b) PG 去向 / (c) VPA vs 任务 | 03 / 04 / 05+07 |
| Fig.7 剂量 | 提案/UPR/B1-UER vs k | 10 |
| Fig.8 矩阵 | 模型×韧×通道 UPR | 11 |
| Fig.9 v3 | 左 2×2 / 右 fork | 08 / 09 |
| Tables 3–5 | 主结果/攻击/剂量 | 01+02 / 06 / 10 |

## 6. 完整数据地图（本文件夹之外）

- 原始轨迹：`results/real_<model>/rollouts/`（冻结，只读）
- 调用缓存：`results/real_<model>/raw/`（每次 LLM 调用原文+回包）
- 回放明细：`results/real_<model>/replay_v2/main.jsonl`（40,000 行/臂）
- 冻结包：`results/FREEZE-20261010/`（5,727 文件）
- 审计：`audit_20261010/`（Gates A–E、契约 v2/v3、S3 问题清单）
- 图：`results/FIGS/`（v3_20261010/ 为 S3 当前版；旧版全保留）
- 报告：`docs/REAL_LLM_EXPERIMENT_REPORT.md`、`docs/GLM53_*`
