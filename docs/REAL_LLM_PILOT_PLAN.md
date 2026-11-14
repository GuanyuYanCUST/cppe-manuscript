# REAL_LLM_PILOT_PLAN — 真实模型试点方案

**2026-10-08 批准与执行记录(用户指令)**:用户将 GLM-5.3 API Key
填入项目根 `.env`(GLM_API_KEY,已 gitignore、权限 600,全程未打印/
记录),指示正式模型用 `glm-5.3`(非 GLM-4.6),连接测试通过后执行
试点。**连接测试 4 次调用全部通过**(`results/LLM_PILOT/connect_test_*.json`):
- Base URL 确认为 `https://open.bigmodel.cn/api/paas/v4`(官方文档,
  OpenAI 兼容,chat/completions);`GLM_MODEL`/`GLM_BASE_URL` 环境变量
  覆盖已实现(adapter 显式参数 > 环境变量 > 预设)。
- **GLM-5.3 始终思考**:`thinking.type=disabled` 直接 400(官方报错
  "该模型始终思考,不支持关闭思考;请使用 low、high 或 max");
  正确载荷 = `thinking:{"type":"enabled"}` + `reasoning_effort:"low"`
  (档位是独立参数,默认 max)。`max_tokens` 必须覆盖思考+JSON,试点
  取 1024(计划值 512 的偏差,原因:思考 token 计入 completion)。
- 认证/调用/解析/usage 记账全部正常;单测 80 项通过。
- 试点调整(同一 200 次硬上限内):判官臂 40 次(J1/J2 × 4 域 × 5
  seeds)+ 复现臂 5 次;候选臂 80 次不变。

状态:**试点已完成 2026-10-08**,验收 5/6 通过(复现性 0.60 未达
90%,已按 §7 停止并提交分析)——详见 `docs/LLM_PILOT_REPORT.md`。
主跑预算未批,未发生超出本文件范围的调用。

---

## 1. 首个模型与版本(建议顺序)

| 顺序 | 模型 | 理由 | 参考价(USD/1M tok,输入/输出) |
|---|---|---|---|
| 1 | **GLM-4.6**(智谱 open.bigmodel.cn,OpenAI 兼容端点) | 国内直连无需代理;按量计费约 ¥5/1M tok;适配器已默认指向 | ≈$0.7/≈$0.7(约¥5/1M,混合) |
| 2 | **qwen-plus**(阿里 DashScope compatible-mode) | 国内直连;跨厂商验证结论稳健性 | $0.40/$1.20–1.60 |
| 3 | gpt-4o / claude-sonnet-4-5(可选,需代理) | 国际旗舰对照,仅在与 1/2 结论冲突时使用 | $2.50/$10; $3.00/$15.00 |

注:智谱 2026 年已发布 GLM-5.x 系列(OpenRouter 均价约
$0.52/$4.40),GLM-4.7-Flash 有免费档。**批准时以官方定价页为准**
(docs.bigmodel.cn "API 定价"、help.aliyun.com DashScope 定价页);
上表价格仅用于本次预算估算,计费以实际账单为准,超限即停(见 §6)。
首选建议 GLM-4.6:若您有智谱新资源/优惠码,可等价替换为
GLM-5.x,预算按新价重算。

## 2. API key 配置

- 复制 `.env.example` → `.env`(已 gitignore),只填批准的提供商:
  `GLM_API_KEY=`(或 `ZHIPUAI_API_KEY=`)、`QWEN_API_KEY=`
  (或 `DASHSCOPE_API_KEY=`)、`OPENAI_API_KEY= ANTHROPIC_API_KEY=`。
- 运行时从环境读取;**密钥永不写入日志/trace/仓库**;适配器
  usage 记账只含 token 数与成本,不含密钥(有单测断言)。
- 端点可用 `GLM_BASE_URL` 等环境变量覆盖(如走内部网关)。

## 3. 试点规模(首次真实调用量)

E1-pilot(按实验计划 §十六:pilot 10 seeds/cell 再放大):

| 项 | 数量 |
|---|---|
| 候选规则生成:4 域 × 10 seeds × 2 channel | **80 次 chat** |
| T2 判官对照(真实 LLM judge 2 变体 × 4 域 × 10 seeds) | 80 次 chat |
| 解析/格式重试缓冲(≤1 次/调用) | ≤40 次 |
| **试点硬上限** | **≤200 次 chat(超限即停)** |

放大实验(E2 主跑,50 seeds/cell ≈ 4,000 历史 × 2 forks)仅在试点
验收通过、且您二次批准预算后进行(预估 8,000–8,500 次调用)。

## 4. Token 边界(每次调用)

- 输入(系统+用户提示,含 ≤5 条历史案例):**≤ 1,500 tokens**
  (适配器模板实测约 600–900;上限写死在试点脚本)。
- 输出:`max_tokens=512`,要求单 JSON 对象,实测 ≤ 300。
- `temperature=0`(GLM/Qwen 支持;记录 `model` 版本号以便复现)。
- 响应缓存:每次调用的原始响应落盘
  `results/LLM_PILOT/raw/<run_id>.jsonl`(含 usage、model 版本、
  时间戳),论文数字只从缓存重算,不重放付费调用。

## 5. 成本估算与预算上限(按 §3/§4 规模)

试点(200 次 × ~1.0K 入 / ~0.3K 出 = 200K 入 + 60K 出):

| 模型 | 试点成本 | 主跑(8,500 次,≈8.5M+2.6M) |
|---|---|---|
| GLM-4.6 | **≈ ¥1.3(~$0.18)** | ≈ ¥56(~$7.7) |
| qwen-plus | ≈ $0.16 | ≈ $6.8 |
| gpt-4o | ≈ $1.10 | ≈ $45 |
| claude-sonnet-4-5 | ≈ $1.50 | ≈ $61 |

**建议预算上限:试点 ¥10 / $2;通过后主跑 ¥80 / $12(单模型)。**
任一超出(按适配器实时记账与账单双重核对)立即停止并报告。

## 6. 失败、限流、超时与非确定性处理

- **429/5xx**:指数退避重试 ≤3 次(1s/2s/4s),仍失败记为
  `transport_failure`,fail-closed(该 cell 无候选规则,不猜测)。
- **超时**:30s/次;超时同样 fail-closed 并计数。
- **非法 JSON/缺字段**:一次"请只输出 JSON"重试,仍失败则该 cell
  记 `parse_failure`,**绝不**自行补一条规则(防止污染 UPR 口径)。
- **非确定性**:temperature=0 + 固定提示 + 落盘原始响应;同 seed
  复跑差异记入试点报告(复现性验收项,见 §7)。
- **成本熔断**:适配器累计 `cost_usd` 超 §5 上限的 80% 时打印警告,
  100% 时抛异常终止(pilot 脚本额外带独立计数器双保险)。
- **密钥泄漏防护**:trace/日志只记录 `model_version` 与 usage;
  `.env` 在 `.gitignore`;CI/复现脚本不读真实密钥。

## 7. 试点验收标准(全部满足才申请主跑预算)

1. **机制不变量保持**:PRECEDENTGUARD 臂 UIR=0、UER=0(真实模型
   提出的任何候选都必须被 cap+containment 拦下越界者)——这是
   系统性质,与模型无关,违反即为实现 bug,停止并修复。
2. **候选质量**:≥70% 的调用返回可解析规则;真实候选与 mock 候选
   在 UPR/containment 命中率上量级相当(记录差值,不设通过线,
   如实报告)。
3. **效用**:含 D 内候选(cap 持有者)的 VPA ≥ 0.5。
4. **复现性**:同 seed 同提示重放 5 次,响应 JSON 语义一致率 ≥ 90%
   (temperature=0)。
5. **成本**:实际支出 ≤ §5 试点上限,usage 记账与账单一致。
6. **trace 完整**:全部事件符合 §15 schema,`model_name` 为真实
   模型版本,`phase="llm-pilot"`。

任何一条不满足:记录原始结果、停在该条,不重试烧钱、不调参凑数,
向您提交失败分析后再定。

---

参考价格来源(批准时需复核官方页):
[智谱 API 定价](https://docs.bigmodel.cn)、
[DashScope/阿里云定价](https://help.aliyun.com)、
[2026 国内大模型定价对比(腾讯云开发者社区)](https://cloud.tencent.com/developer/article/2685603)、
[OpenRouter GLM-5.1 报价](https://openrouter.ai)。
