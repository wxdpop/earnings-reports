# 信息收集规范（info-collect-spec.md）

> 本文档是 `collect-user-info.py` 的静态参考镜像，供 LLM 在执行信息收集前预读理解。运行时由 `collect-user-info.py` 输出 JSON 规范，本文档不参与运行时执行。

---

## 一、收集流程概述

`collect-user-info.py` 采用**两阶段调用协议**：

```
阶段 A（无 --answers 参数）：
    脚本输出弹窗规范 JSON（standalone 5 项 / proxy 6 项）→ LLM 按规范执行 AskUserQuestion → 组装 answers.json

阶段 B（带 --answers 参数）：
    脚本读取 answers.json → 写入 config.local.json → 输出最终状态 JSON
```

**两种调用模式**：

| 模式 | 调用方 | 写入目标 | 弹窗数量 | 适用场景 |
|---|---|---|---|---|
| `standalone` | 子技能自身 | 子技能 config.local.json | 5 项（不含调度间隔） | 子技能独立使用 |
| `proxy` | 父技能调用 | 父技能 config.local.json | 6 项（含调度间隔） | 父技能初始化时代理收集 |

> **约束**：子技能无定时调度任务环节，`standalone` 模式不收集调度间隔（弹窗 1）；`proxy` 模式由父技能代理时才收集调度间隔并写入父技能 config 的 `schedule` 字段。

---

## 二、弹窗规范（standalone 5 项 / proxy 6 项）

### 弹窗 0：工作根目录（输出目录定位）

| 选项 | 值 | 说明 |
|---|---|---|
| **使用当前工作目录（推荐）** | `__cwd__` | 自动获取当前工作目录作为工作根目录 |
| 手动输入工作根目录 | `__user_input__` | 用户打字输入绝对路径，如 `d:\TraeAutomaticTools` 或 `~/projects` |

**字段映射**：
- `paths.output_dir` = `<工作根目录>/Output/stock-financial-reports`
- `paths.repo_dir` = 同 `paths.output_dir`

**约束**：与技能安装目录无关，必须由用户显式选择。

---

### 弹窗 1：调度间隔选择

| 选项 | cron 表达式 | 说明 |
|---|---|---|
| **每 12 小时（推荐）** | `0 0,12 * * *` | 默认，平衡及时性和资源占用 |
| 每 6 小时 | `0 0,6,12,18 * * *` | 高频检查，适合财报季 |
| 每 24 小时 | `0 0 * * *` | 每天凌晨检查一次 |
| 每 10 分钟（最小粒度） | `*/10 * * * *` | 最高频检查（Trae Schedule 最小粒度） |

**字段映射**：
- `schedule.cron` ← 用户选择
- `schedule.timezone` = `Asia/Shanghai`（固定）
- `schedule.enabled` = `true`（固定）

**约束**：仅 `proxy` 模式写入父技能 config（`schedule` 是父技能专有字段，子技能不需要）。

---

### 弹窗 2：API Key 状态

| 选项 | 值 | 说明 |
|---|---|---|
| 已有 Finnhub + Alpha Vantage API Key | `have_both` | 用户已有，引导编辑 config.local.json 填入 |
| 需注册 Finnhub API Key | `need_finnhub` | 输出注册地址 https://finnhub.io/register |
| 需注册 Alpha Vantage API Key | `need_alphavantage` | 输出注册地址 https://www.alphavantage.support/free-api-key |
| 需注册两个 API Key | `need_both` | 输出两个注册地址 |

**字段映射**：
- `finnhub.api_key` ← 用户后续手动编辑填入真实值
- `alphavantage.api_key` ← 用户后续手动编辑填入真实值

**占位符检测**：
- `<your-finnhub-api-key>`
- `<your-alphavantage-api-key>`

**约束**：脚本不在此阶段填入真实 API Key（用户需手动编辑），仅确保占位符存在。

---

### 弹窗 3：飞书 Webhook 状态

| 选项 | 值 | 说明 |
|---|---|---|
| 已有飞书 Webhook URL | `have_webhook` | 用户已有，引导编辑 config.local.json 填入 |
| 需配置飞书群机器人 | `need_config` | 输出配置指引（飞书群 → 设置 → 群机器人 → 添加自定义机器人） |
| 跳过飞书推送 | `skip` | 不配置 Webhook，子技能阶段 9 飞书推送将被跳过 |

**字段映射**：
- `feishu.webhook_url` ← 用户后续手动编辑填入真实值（选择 `skip` 时不写入）

**占位符检测**：
- `<your-feishu-webhook-url>`

---

### 弹窗 4：公司库导入方案

| 选项 | 值 | 预设 tickers |
|---|---|---|
| **导入美股 7 巨头（推荐）** | `mag7` | AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA |
| 美股 7 巨头 + 阿里巴巴 | `mag7_baba` | 7 巨头 + BABA |
| 中概股龙头 | `china` | BABA, PDD, JD, BIDU, NIO, LI, XPEV |
| 手动输入 ticker 列表 | `custom` | 用户打字输入，如 "NVDA, TSLA, AMD" |
| 跳过，稍后手动添加 | `skip` | 空 |

**字段映射**：
- 不写入 config.local.json
- 输出 JSON 的 `company_library_choice` 和 `company_library_tickers` 字段，供父技能步骤 8 消费

---

### 弹窗 5：部署方案选择

| 选项 | 值 | deployment.targets | github.enabled |
|---|---|---|---|
| **仅 Cloudflare Pages（推荐默认）** | `cloudflare_only` | `["cloudflare"]` | `false` |
| Cloudflare + GitHub 双节点 | `cloudflare_github` | `["cloudflare", "github"]` | `true` |

**字段映射**：
- `deployment.targets` ← 用户选择
- `deployment.github.enabled` ← 用户选择
- `deployment.cloudflare.api_token` ← 用户后续手动编辑填入
- `deployment.cloudflare.account_id` ← 用户后续手动编辑填入
- `deployment.cloudflare.project_name` = `earnings-reports`（固定）
- `deployment.github.repo` = 空（用户后续填入）

**占位符检测**：
- `<your-cloudflare-api-token>`
- `<your-cloudflare-account-id>`

**约束**：Cloudflare 始终必选（不可关闭）；GitHub 为可选项，默认不启用。

---

## 三、占位符检测规则（5 项）

| 占位符 | 对应字段 | 检测行为 |
|---|---|---|
| `<your-feishu-webhook-url>` | `feishu.webhook_url` | WARN，不阻断 |
| `<your-finnhub-api-key>` | `finnhub.api_key` | WARN，不阻断 |
| `<your-alphavantage-api-key>` | `alphavantage.api_key` | WARN，不阻断 |
| `<your-cloudflare-api-token>` | `deployment.cloudflare.api_token` | WARN，不阻断 |
| `<your-cloudflare-account-id>` | `deployment.cloudflare.account_id` | WARN，不阻断 |

**检测时机**：
- 阶段 B 写入 config 后立即检测
- `--check-only` 模式独立检测

---

## 四、GitHub 登录状态检测

| 检测项 | 命令 | 输出值 |
|---|---|---|
| gh CLI 登录状态 | `gh auth status` | `logged_in` / `not_logged_in` / `gh_not_installed` / `check_timeout` / `check_failed` |

**约束**：
- 脚本仅检测状态，不执行 `gh auth login`（系统级交互操作，由 LLM 执行）
- 仅当 `deployment.targets` 含 `github` 时检测
- 检测结果通过输出 JSON 的 `github_login_status` 字段返回

---

## 五、config.local.json 字段结构规范

### 5.1 子技能 config.local.json（standalone 模式）

```json
{
  "feishu": { "webhook_url": "<your-feishu-webhook-url>" },
  "finnhub": { "api_key": "<your-finnhub-api-key>" },
  "alphavantage": { "api_key": "<your-alphavantage-api-key>" },
  "paths": {
    "output_dir": "<工作根目录>/Output/stock-financial-reports",
    "repo_dir": "<工作根目录>/Output/stock-financial-reports"
  },
  "deployment": {
    "targets": ["cloudflare"],
    "cloudflare": {
      "api_token": "<your-cloudflare-api-token>",
      "account_id": "<your-cloudflare-account-id>",
      "project_name": "earnings-reports"
    },
    "github": { "enabled": false, "repo": "" }
  }
}
```

### 5.2 父技能 config.local.json（proxy 模式）

```json
{
  "child_skill_dir": "<由父技能步骤 1 推断>",
  "parent_skill_dir": "<由父技能步骤 1 推断>",
  "feishu": { "webhook_url": "<your-feishu-webhook-url>" },
  "finnhub": { "api_key": "<your-finnhub-api-key>" },
  "alphavantage": { "api_key": "<your-alphavantage-api-key>" },
  "paths": {
    "output_dir": "<工作根目录>/Output/stock-financial-reports",
    "repo_dir": "<工作根目录>/Output/stock-financial-reports"
  },
  "deployment": {
    "targets": ["cloudflare"],
    "cloudflare": {
      "api_token": "<your-cloudflare-api-token>",
      "account_id": "<your-cloudflare-account-id>",
      "project_name": "earnings-reports"
    },
    "github": { "enabled": false, "repo": "" }
  },
  "schedule": {
    "enabled": true,
    "cron": "0 0,12 * * *",
    "timezone": "Asia/Shanghai"
  },
  "python_executable": "<由父技能步骤 3 探测>"
}
```

### 5.3 字段归属规则

| 字段 | standalone 写入 | proxy 写入 | 说明 |
|---|---|---|---|
| `feishu.*` / `finnhub.*` / `alphavantage.*` | ✓ | ✓ | 两边都保留 |
| `paths.*` | ✓ | ✓ | 两边都保留 |
| `deployment.*` | ✓ | ✓ | 两边都保留 |
| `schedule.*` | ✗ | ✓ | 仅父技能（子技能不需要调度） |
| `child_skill_dir` / `parent_skill_dir` | ✗ | ✗ | 由父技能步骤 1 推断，不由收集脚本写入 |
| `python_executable` | ✗ | ✗ | 由父技能步骤 3 探测，不由收集脚本写入 |

---

## 六、输出 JSON 字段消费映射

`collect-user-info.py` 阶段 B 输出的最终状态 JSON，供父技能后续步骤消费：

| 输出字段 | 消费步骤 | 用途 |
|---|---|---|
| `collected_fields` | 步骤 6 | 占位符检测依据 |
| `company_library_choice` | 步骤 8 | 公司库导入方案选择 |
| `company_library_tickers` | 步骤 8 | 公司库导入 ticker 列表 |
| `schedule_cron` | 步骤 10 | 创建定时任务的 cron 表达式 |
| `schedule_timezone` | 步骤 10 | 创建定时任务的时区 |
| `placeholders_remaining` | 步骤 6 | 引导用户编辑 config 的依据 |
| `cloudflare_configured` | 步骤 6.5/9 | 步骤 6.5 判断是否需要引导 Cloudflare 配置；步骤 9 写入 `.parent-init-done.json` 标记 |
| `github_login_required` | 步骤 6.5 | 决定是否执行 GitHub 登录引导 |
| `github_login_status` | 步骤 6.5/9 | 决定是否执行 `gh auth login`，写入 `github_logged_in` 标记 |
| `next_actions` | 步骤 6/6.5 | 引导用户后续操作的动作清单 |

---

## 七、与 collect-user-info.py 的边界

| 维度 | info-collect-spec.md（本文档） | collect-user-info.py |
|---|---|---|
| 性质 | 静态参考文档 | 运行时脚本 |
| 用途 | 供 LLM 预读理解收集规范 | 输出运行时 JSON 规范，执行写入 |
| 参与执行 | 否 | 是 |
| 维护时机 | 收集规范变更时同步更新 | 代码逻辑变更时更新 |

**约束**：两者内容保持一致，但职责不重叠。本文档是 `.py` 的文档化镜像。
