# GLM 调用通道审计（2026-10-08）

用户指令：暂停实验、不充值、不自动恢复；审计真实调用链。本文记录审计
结论，密钥一律不明文出现。

## 1. 真实请求 URL（rollout 链路）

`experiments/real_rollout.py` → `src/pguard/llm_adapter.py`
`PROVIDERS["glm"]` → `https://open.bigmodel.cn/api/paas/v4/chat/completions`
（标准按量付费 PAAS 端点，Bearer 鉴权）。

**这不是 Coding Plan 端点。** 官方 FAQ（docs.bigmodel.cn/cn/coding-plan/faq）：
- Claude Code 必须用 `https://open.bigmodel.cn/api/anthropic`
- 其他指定编码工具用 `https://open.bigmodel.cn/api/coding/paas/v4`
- 官网体验中心不支持套餐

## 2. Key 来源

项目 `.env`（mode 600）`GLM_API_KEY`，49 字符，前缀 a923bf。与 Claude Code
环境（`ANTHROPIC_AUTH_TOKEN`，同前缀同长度）是**同一把 Coding Plan Key**。
即：两条通道独立（rollout→PAAS v4；Claude Code→anthropic 兼容层），
但凭据同源——Coding Plan Key 被同时当作了按量付费 Key 用。

## 3. 计费通道与 ¥2.74

1,822 次成功调用（16:32→19:21）全部落在标准 PAAS 按量付费通道，按
tokens_used.py 估算 ≈¥2.74（参考价 ¥1.1/¥3.90 每百万 tok）。实际扣的是
账号赠金/余额（非 Coding Plan 套餐额度），耗尽后开始返回 1113。
确切扣费以 bigmodel 财务中心-费用明细（抵扣资源包列）为准。

## 4. 1113 误判为可重试限流的根因

官方错误码表：1113 = HTTP 429 + "您的账户已欠费"——**不可重试的业务错误**。
`_chat` 旧逻辑只看 HTTP 429 就退避重试 + RateLimited 熔断 + waiter 每 10
分钟探测，等于对欠费无限等待。烧掉了 7 个 cell × 600 请求上限、产生
90 个纯 infra 垃圾 checkpoint（已 purge，见 PURGE_REPORT.json）。

## 5. 800 个自动化 rollout 是否属于 Coding Plan 允许场景

**不属于。** 官方使用须知 + FAQ：
- 套餐"仅限在官方支持的指定工具与产品环境中使用"（ZCode、Claude Code、
  Claude for IDE、Codex、OpenCode、Pi 等 Coding Agent 工具）
- "自建应用、网站、机器人、SaaS 产品等场景……请使用智谱提供的标准
  API 服务，并根据对应协议计费"
- 违规后果：限流、冻结，3 次以上违规可能封号

本项目 rollout 是自建实验脚本，非指定工具。**结论：不得把 rollout 改指
到 `/api/coding/paas/v4` 来蹭套餐额度**（用户指令第 4 条，亦为合规要求）。
合规路径 = 标准按量付费 API + 有余额的账号（当前 URL 即正确端点）。

## 6. 已落地的修复（代码，未产生任何新调用）

- `src/pguard/llm_adapter.py`：新增 `FatalAPIError` + `RETRYABLE_CODES`
  （1302/1305/1308/1310）；`_chat` 解析响应体 `error.code`，非重试码且
  非 5xx/传输错 → 立即抛出，零退避。1113/1309/1313/1001/1210… 全部
  stop-and-report。
- `experiments/real_rollout.py`：单独捕获 FatalAPIError → 打印
  `[fatal]`、保留 checkpoint、exit 2（不静默、不等待）。
- `scripts/wait_and_run.sh`：探测到 FatalAPIError 立即 exit 2，不再循环。
  顶部注明未经用户批准不得重启。
- `tests/test_llm_adapter.py`：+3 回归测试（1113 首响应即抛、其他致命
  码、真限流码仍退避）。92/92 通过。

## 7. 现状与等待决定

- 进程：0（waiter/probe/driver 全部已杀，cron 已删）
- 资产：77 条干净轨迹保留于 results/real_glm53/rollouts/main/；
  raw 缓存与 LLM_PILOT/freeze 未动
- 等用户决定：充按量余额续跑（合规）／停止真实 LLM 实验／其他方案
