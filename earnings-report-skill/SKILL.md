---
name: "earnings-report"
description: "自动生成上市公司最新财报深度分析HTML报告（含数据图表、移动端适配、单文件输出）。当用户要求分析某公司财报/earnings/业绩时调用。"
---

# 财报深度分析报告生成器

> **★ 版本管理约定**：本技能不记录历史版本信息，始终更新到最新版本。Git 操作固定使用 git CLI。

## 概述

自动生成上市公司财报深度分析报告。用户提供公司名称（可选指定年份/季度），技能完成数据搜集、整理、HTML生成、校验、单文件构建、部署和推送，输出自包含 HTML。

- **★ 跨平台**：所有脚本统一为 Python 3 单文件入口（Windows/Mac/Linux 通用），消除双平台 .ps1/.sh 维护负担；Chrome headless 验证
- **统一存放**：最终 HTML 存放在 git 仓库 `reports/{TICKER}/{company-slug}-{quarter}-earnings.html`，TICKER 为股票代码大写
- **路径可配置**：通过 `config.local.json` 的 `paths.output_root` 自定义（仓库目录由代码推导，不存入 config）；路径分类规则：配置文件目录基于技能安装目录推断，输出根目录在用户工作空间需显式配置

## 关键地址与配置

**仓库与部署节点**：

| 项 | 值 | 目录类型 |
|---|---|---|
| GitHub 仓库 | `deployment.github.repo`（动态读取，可选，deployment.targets 含 github 时启用） | — |
| GitHub Pages URL | `https://{github-user}.github.io/{repo-name}/reports/{TICKER}/{filename}.html`（从 `deployment.github.repo` 推导，可选备用） | — |
| Cloudflare Pages 项目名 | 运行时从 `deployment.github.repo` 提取仓库名（取 `/` 后的部分），不在配置文件中定义（必选） | — |
| Cloudflare Pages URL | `https://earnings-reports.pages.dev/reports/{TICKER}/{filename}.html`（★ 主链接，必选） | — |
| 本地 git 仓库路径 | 仓库目录 = `paths.output_root`/Output/项目名（代码推导，不存入 config；项目名从 `deployment.github.repo` 提取仓库名） | **输出目录** |
| 输出根目录 | `paths.output_root`（用户输入盘符+文件夹，如 `d:\TraeAutomaticTools`） | **输出目录** |
| 配置文件目录 | 技能安装目录：`config.local.json` / `.env-check-result.*.json` 均在技能安装目录（基于 `Path(__file__).resolve().parent.parent` 推断）| **配置文件目录** |

**API Key 获取地址**：

| API | 注册地址 | 用途 | 配置字段 |
|-----|---------|------|---------|
| Finnhub | https://finnhub.io/register | 公司 profile、分析师评级 | `finnhub.api_key` |
| Alpha Vantage | https://www.alphavantage.support/free-api-key | 三大报表（收入/资产负债/现金流） | `alphavantage.api_key` |

**config.local.json 配置示例**（由 `--fix-config` 自动创建模板，填入真实值后使用；被 .gitignore 排除；修正为与 config.example.json 一致的嵌套结构）：

```json
{
  "feishu": {
    "webhook_url": "<your-feishu-webhook-url>"
  },
  "finnhub": {
    "api_key": "<your-finnhub-api-key>"
  },
  "alphavantage": {
    "api_key": "<your-alphavantage-api-key>"
  },
  "paths": {
    "output_root": ""
  }
}
```

路径分类规则（区分两类目录）：
- **配置文件目录**（config.local.json / .env-check-result.*.json）：基于技能安装目录推断（`Path(__file__).resolve().parent.parent`），无需用户配置
- **输出根目录**（paths.output_root）：在用户工作空间，**不从技能安装路径推断**；留空时脚本抛错提示用户配置
- `paths.output_root`：用户输入的输出根目录（盘符+文件夹，如 `d:\TraeAutomaticTools`）；仓库目录 = `output_root`/Output/项目名（代码运行时推导，项目名从 `deployment.github.repo` 提取仓库名）

**★ 配置统一入口**：所有配置项（API Key、Webhook URL、路径）统一从 `config.local.json` 加载，不再支持环境变量，降低复杂性。

**飞书 Webhook 配置**：
- 写入 `config.local.json` 的 `feishu.webhook_url` 字段（嵌套结构），一次配置永久生效

## 触发条件

- "分析XX财报"、"XX最新业绩"、"XX earnings"、"XX财报会议分析"
- "分析XX 2025 Q3 财报"（指定季度）

## 自动化硬性约束

> 全程静默执行，仅在检测失败或异常时弹窗。

1. **所有 RunCommand 设置 `requires_approval: false`** — 禁止命令审批弹窗
2. **弹窗边界** — 仅以下 3 种情况调用 `AskUserQuestion`：
   - 环境检测不通过（阶段 -1）
   - 配置文件未正确配置（阶段 -1）
   - 环节执行失败
   - 部署（阶段8）、飞书推送（阶段9）等均自动执行，不弹窗确认
3. **命令阻塞** — `blocking: true`（除 HTTP 服务器用 `blocking: false`）
4. **文件操作用 Python pathlib / shutil** — `pathlib.Path` / `shutil.copy2` / `shutil.rmtree` 等，禁止 `os.system` 调用 `Copy-Item` / `cp` 等高风险命令
5. **无头验证用 Chrome headless** — 跨平台路径自动检测，Chrome 不可用时退化为纯 HTML 结构验证
6. **阶段7/8/9 并行执行** — 阶段6验证 PASS 后，单条消息并行启动 3 个子代理（Task 工具），等待全部返回
7. **★ 阶段1 数据拉取并行执行** — API 脚本（RunCommand）+ 多站点 WebFetch（N 个 Task 子代理）在单条消息中并行启动，等待全部返回后汇总
8. **脱敏检查** — 提交前自查（详见"脱敏检查"规范）
9. **执行完毕清理资源** — 关闭 HTTP 服务器、删除临时文件

## 工作流程

### 阶段 -1：环境检查与自动安装

**触发时机**：首次调用、环境变更、用户主动要求"检查环境"。

**执行脚本**（统一为 Python 单文件入口，Windows/Mac/Linux 通用）：

```bash
# 跨平台统一调用（自动选择 python3/python）
python "{skill_dir}/scripts/check-and-install.py"              # 检查 + 自动安装
python "{skill_dir}/scripts/check-and-install.py" --china      # 强制国内镜像
python "{skill_dir}/scripts/check-and-install.py" --fix-config # 创建 config.local.json
python "{skill_dir}/scripts/check-and-install.py" --skip-check # 跳过检查，直接安装全部
python "{skill_dir}/scripts/check-and-install.py" --force-check # 强制重检（忽略缓存）
```

**检查项目（9 项并行）**：

| # | 检查项 | Windows 安装命令 | Mac/Linux 安装命令 |
|---|--------|-----------------|-------------------|
| 1 | Python 3.8+ | `winget install Python.Python.3.12` | `brew install python@3.12` / `sudo apt-get install python3` |
| 2 | Node.js 18+ | `winget install OpenJS.NodeJS.LTS` | `brew install node@18` / NodeSource |
| 3 | Google Chrome | `winget install Google.Chrome` | `brew install --cask google-chrome` / apt 添加 Google 源 |
| 4 | Git | `winget install Git.Git` | `brew install git` / `sudo apt-get install git` |
| 5 | GitHub CLI | `winget install GitHub.cli` | `brew install gh` / apt 添加 GitHub 源 |
| 6 | wrangler | `npm i -g wrangler`（国内用 npmmirror） | `npm i -g wrangler`（国内用 npmmirror） |
| 7 | PowerShell 7+ | `winget install Microsoft.PowerShell` | Mac/Linux 可选（使用 .sh 脚本无需） |
| 8 | config.local.json | `--fix-config` 自动创建 | `--fix-config` 自动创建 |
| 9 | git 仓库初始化 | 检查 `.git` + remote origin | 检查 `.git` + remote origin |

国内 IP 自动启用镜像源（npm 淘宝 `registry.npmmirror.com` / pip 清华 `pypi.tuna.tsinghua.edu.cn` / Homebrew 清华 / apt 清华），或 `--china` 强制启用。

**缓存机制**：全部 PASS 后结果保存到 `.env-check-result.{platform}.json`（按平台分文件，永久有效）。下次运行直接读取缓存秒级通过。`--force-check` 强制重检。缓存文件被 `.gitignore` 排除。

**弹窗规则**：
- 全部 PASS → 静默进入阶段 0
- config.local.json 不存在 → 自动 `--fix-config` 创建，弹窗提示用户编辑填入真实值
- 依赖缺失 → 自动安装（无需确认），安装后重新检查
- 仅 config 类（API Key 未填）需弹窗提示用户手动编辑

### 阶段 -1.5：用户信息收集

**触发时机**：阶段 -1 环境检查通过后，检测到 config.local.json 含未替换占位符或关键字段为空时触发。子技能本身也需要信息收集前置（standalone 模式独立完成）；父技能初始化时通过 proxy 模式代理此流程，并额外增加调度间隔收集（父技能专有字段）。

**执行脚本**：

```bash
# standalone 模式（子技能独立使用，不收集调度间隔）
python "{skill_dir}/scripts/collect-user-info.py" --mode standalone
python "{skill_dir}/scripts/collect-user-info.py" --mode standalone --answers /path/to/answers.json

# proxy 模式（被父技能调用代理收集，含调度间隔）
python "{skill_dir}/scripts/collect-user-info.py" --mode proxy --parent-config <父技能 config.local.json 路径>
python "{skill_dir}/scripts/collect-user-info.py" --mode proxy --parent-config <父技能 config.local.json 路径> --answers /path/to/answers.json

# 仅检测占位符和登录状态
python "{skill_dir}/scripts/collect-user-info.py" --mode standalone --check-only
```

**核心说明**：
- 采用两阶段调用协议（阶段 A 输出弹窗规范 → LLM 执行 AskUserQuestion → 阶段 B 写入 config）
- standalone 模式收集 6 项（输出根目录、API Key、飞书 Webhook、公司库导入方案、部署方案、GitHub 仓库名称→`deployment.github.repo`），**不收集调度间隔**（子技能无定时调度任务环节）；GitHub 仓库名称仅当部署方案选择 cloudflare_github 时收集
- proxy 模式收集 7 项（增加调度间隔，写入父技能 config 的 `schedule` 字段；GitHub 仓库名称仅当部署方案选择 cloudflare_github 时收集）
- 脚本不直接调用 AskUserQuestion，通过两阶段调用协议实现跨 Agent 兼容
- `gh auth login` / `wrangler login` 是系统级交互操作，脚本仅检测状态，实际登录由 LLM 执行
- **详细规范（弹窗选项、字段映射、占位符检测、字段归属规则、输出 JSON 消费映射）见 [info-collect-spec.md](references/info-collect-spec.md)**

### 阶段 0：解析用户输入

1. 识别公司名称（中英文均可，如"英伟达"="NVDA"）
2. 识别年份/季度（如"2025 Q3"、"去年三季度"）；未指定则取最新
3. 识别公司本位币（美元/欧元/日元/新台币等），决定是否需要汇率换算

### 阶段 1：数据拉取

**★ 并行执行策略**：本阶段 1.1（API 脚本）和 1.2（WebFetch 多站点）**无依赖关系，必须并行执行**。主代理在单条消息中同时发起：
- 1 个 RunCommand 调用 fetch-data 脚本（API 结构化数据）
- N 个 Task 子代理并行 WebFetch 不同白名单站点（每个子代理负责 1-2 个站点）

并行可将数据拉取耗时从串行 ~60s 降至 ~20s。子代理返回结构化摘要（关键数据 + 同比 + 管理层评论 + 业绩指引），主代理汇总后进入阶段 2。

**1.1 API 结构化数据**（脚本化，统一为 Python 入口）：

```bash
# 跨平台统一调用
python "{skill_dir}/scripts/fetch-data.py" --symbol "NOK" --out-dir "{repo_root}/data/nok-data"
# OutDir 省略时自动从 config.local.json 的 paths.output_root 推导仓库目录（output_root/Output/项目名）
python "{skill_dir}/scripts/fetch-data.py" --symbol "NOK"
```

拉取 5 类数据：Finnhub profile + 分析师评级；Alpha Vantage 收入报表 + 资产负债表 + 现金流（各近 8 季度）。输出文件：`{symbol-lower}-{profile|recommendations|income-statement|balance-sheet|cashflow}.json`。

**★ 数据解析自动输出**：fetch-data 完成后自动调用 `scripts/parse-financial-data.py`，输出完整 6 季度财务摘要（Profile/评级/收入/资产负债/现金流/关键指标汇总），LLM 无需写临时解析脚本。

**1.2 WebFetch 白名单辅助**（LLM 补充非结构化信息，★ 多站点并行）：

- **P0**：公司官方 IR 页面（原始财报、管理层评论、业绩指引）
- **P1**：格隆汇（gelonghui.com）、富途资讯（futunn.com）、汇通财经（fx678.com）、华盛通（hstong.com）
- **P2**：投行研报（Goldman Sachs/JPMorgan/BNP Paribas 等）

**禁止的数据源**：搜狐、今日头条、东方财富、百度百家号、微信公众号等非专业财经媒体一律不得引用。

LLM 通过 WebFetch 补充：财报会议要点、分部/地区营收、行业上下文与市场反应。

**★ 并行 WebFetch 示例**（主代理单条消息同时启动多个 Task 子代理）：

```
# 子代理 1：公司 IR 页面（P0，必选）— 原始财报数据、管理层评论、业绩指引
# 子代理 2：格隆汇 + 富途（P1）— 财报分析、市场反应、分部数据
# 子代理 3：汇通财经 + 华盛通（P1）— 行业上下文、投行观点
```

每个子代理返回结构化摘要，主代理汇总后交叉验证。

### 阶段 2：数据整理与汇率换算

1. 筛选专业来源，剔除非专业来源
2. 交叉验证关键数据（API vs WebFetch，≥2 个来源）
3. **汇率规则**：
   - **美元本位币公司**（TSLA/NVDA/AAPL/MSFT 等）：直接用美元，meta 注明"不涉及汇率换算"
   - **非美元本位币公司**（ASML/EUR、NOK/EUR、TSMC/TWD、Toyota/JPY 等）：保留当地货币，括号备注美元，格式 `营收 53.28 亿欧元（约 57.62 亿美元）`
   - 换算汇率：财报发布日官方汇率，保留 4 位小数
4. meta 信息和表格注脚注明汇率基准日期与汇率值
5. 图表和正文货币单位一致

### 阶段 3：生成 sections JSON

LLM 生成完整 sections JSON，遵循 `templates/sections-reference.md` 规范。

**结构**（必须嵌套，sections 为对象含 sec01-sec12）：

```json
{
  "meta": {
    "company_name": "...", "quarter": "Q2 2026", "report_type": "quarterly-earnings",
    "report_date": "...", "earnings_date": "...", "data_source": "...",
    "currency_unit": "USD", "generated_at": "...", "report_version": "latest",
    "disclaimer_text": "本报告基于公开财务数据自动生成，仅供参考，不构成任何投资建议。"
  },
  "header": "<header class=\"report-head\">...</header>",
  "sections": { "sec01": "<section id=\"sec01\">...</section>", ..., "sec12": "..." },
  "footer": "<footer>...</footer>"
}
```

**header 必须用模板结构**（`references/report-template.md` 对齐）：

```html
<header class="report-head">
  <div class="wrap">
    <div class="kicker">财报深度分析 · Q2 2026</div>
    <h1>公司名称 2026 年第二季度财报分析</h1>
    <p class="sub">公司简介与核心数据摘要...</p>
    <div class="meta">报告日期：... | 财报日期：... | 货币：... | 数据源：...</div>
    <div class="stat-grid">
      <div class="stat-card"><div class="stat-label">营收</div><div class="stat-value">XX 亿</div><div class="stat-delta up">+XX% YoY</div></div>
      <!-- 4 个 stat-card：营收/净利润/毛利率/关键指标 -->
    </div>
  </div>
</header>
```

- **必须包含**：`.wrap` 容器、`.stat-grid` + 4 个 `.stat-card`
- **禁止使用**：`.title-block`、`.subtitle`、`.meta-row` 等非模板类名
- **类名兼容**：stat-card 内长类名（`.stat-value`/`.stat-label`/`.stat-delta`）与短类名（`.v`/`.l`/`.d`）等效；变体：`.stat-delta.up/.pos/.positive`（绿）、`.down/.neg/.negative`（红）、`.flat/.warn`（橙）

**sec01 禁止 stat-grid**（避免与 header 重复），用 `highlights-box` + `callout` 结构。

**charts.js 生成**（基于 `references/charts-template.js`）：
- SVG 渲染器，`animation: false`，注册 `resize` 监听，颜色从 CSS 变量读取
- 移动端适配：`isMobile = window.innerWidth <= 700`
- 双 Y 轴：每个数据系列显式绑定 `yAxisIndex`
- **7 个固定图表**：chart-revenue-trend / chart-revenue-mix / chart-margin-trend / chart-cashflow / chart-kpi-trend / chart-geo / chart-radar
- **★ 标签全中文**：`name`、`legend.data`、坐标轴标签必须简体中文；业务板块/地区名与正文表格译名一致（如"移动网络"而非"Mobile Networks"）；仅股票代码和百分比/数字单位可保留英文/符号

**生成原则**：LLM 生成整段 HTML，脚本做块替换，避免细粒度字段填充。引用标记用 `<sup><a href="#cite-N">[N]</a></sup>`，与 footer 一一对应。

### 阶段 4：模板填充

```bash
# 跨平台统一调用（统一为 Python 入口）
python "{skill_dir}/scripts/fill-template.py" \
    --template-file "{skill_dir}/references/report-template.md" \
    --sections-file "{repo_root}/data/nok-q2-2026-sections.json" \
    --output-file "{repo_root}/nok-q2-2026-earnings/index.html"
```

脚本自动：读取模板和 JSON → 替换 meta 占位符（10 个）→ 替换 header/12 section/footer 块（正则匹配）→ **结构完整性校验** → 清理剩余占位符 → 输出 index.html。

**结构校验规范**（详见 `templates/sections-reference.md`）：

| Section | 必需子元素 | 禁止元素 |
|---------|-----------|---------|
| sec01 核心摘要 | highlights-box, callout | stat-grid |
| sec02 财务概览 | chart-revenue-trend, table | - |
| sec03 营收分析 | chart-revenue-mix, table, callout | - |
| sec04 盈利能力 | stat-grid, chart-margin-trend, table, callout | - |
| sec05 资产负债现金流 | chart-cashflow, table, insight-grid | - |
| sec06 运营指标 | stat-grid, chart-kpi-trend | - |
| sec07 分部与地区 | chart-geo, table, insight-grid | - |
| sec08 业绩指引 | table, timeline, callout | - |
| sec09 管理层评论 | callout, highlights-box | - |
| sec10 风险因素 | risk-list, callout | - |
| sec11 投资观点 | stat-grid, insight-grid, callout | - |
| sec12 附录 | glossary, chart-radar | - |

### 阶段 5：单文件构建

```bash
# 跨平台统一调用（统一为 Python 入口）
# ★ --ticker 必传：股票代码大写（如 NOK），用于创建 reports/{TICKER}/ 子目录，每个公司用子文件夹隔离
python "{skill_dir}/references/build-standalone.py" \
    --source-dir "{repo_root}/nok-q2-2026-earnings" \
    --ticker "NOK" \
    --output-dir "{repo_root}"
```

脚本自动（使用 Python 字符串 .replace() 精确匹配，避免正则不稳定）：
1. echarts.min.js 自动复制（从 `skill/assets/js/echarts.min.js` 复制到 `$SOURCE_DIR/_shared/js/`，无需网络下载）
2. 内联 echarts.min.js 和 charts.js（转义 `</script>` 为 `<\/script>`）
3. 输出单文件到 `仓库目录/reports/{TICKER}/{company-slug}-{quarter}-earnings.html`（仓库目录 = `output_root`/Output/项目名，由代码推导，不存入 config）

**★ reports 目录规范**：
- 路径：`仓库目录/reports/{TICKER}/{company-slug}-{quarter}-earnings.html`（仓库目录 = `output_root`/Output/项目名）
- **只保留最终单文件 HTML**，不复制 index.html 副本，不保留 _shared/js/、assets/charts.js 等中间产物
- 每个公司用子文件夹隔离（按 TICKER 大写命名，如 `reports/NOK/`、`reports/NVDA/`）
- 源目录 `{repo_root}/{company-slug}-{quarter}-earnings/`（含 index.html、assets/charts.js 等中间产物）由阶段 7 资源清理删除

### 阶段 6：无头浏览器验证

```bash
# 跨平台统一调用（仅保留 .py 主入口，删除 .ps1/.sh 包装器）
python "{skill_dir}/references/verify-headless.py" "{repo_root}/reports/{TICKER}/{company-slug}-{quarter}-earnings.html"
```

`verify-headless.py` 跨平台（Python 3 通用，内置 Chrome 三平台路径检测）。

**Chrome 路径检测**（按优先级，三平台完整候选）：

| 平台 | 候选路径（按优先级） |
|------|---------------------|
| Windows | `C:\Program Files\Google\Chrome\Application\chrome.exe` → `%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe` → `%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe` |
| Mac | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` → `~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` |
| Linux | `/usr/bin/google-chrome` → `/usr/bin/google-chrome-stable` → `/usr/bin/chromium-browser` → `/usr/bin/chromium` |

Chrome 不可用时自动退化为纯 HTML 结构验证（不执行 JS，无法验证图表渲染）。

**验证项**（全部 PASS 才通过）：
- 图表渲染：SVG 数量 ≥ 2（或 echarts.init≥2 + 容器≥2 + 零外部依赖）
- StatCard 数量 ≥ 4
- 参考资料数量 ≥ 5
- 外部 `<script src>` = 0
- 外部 `<link href>` = 0
- `@font-face` 声明 = 0

脚本自动：启动临时 HTTP 服务器 → Chrome headless 截图 → HTML 结构验证 → 输出 PASS/FAIL → 关闭服务器。

### 阶段 7-9：并行执行

**阶段6验证 PASS 后，主代理在单条消息中并行启动 3 个子代理（Task 工具，`subagent_type: general_purpose_task`），等待全部返回。**

**并行可行性**：
- 阶段7（清理）：清理 `data/{ticker}-{quarter}-earnings/` 临时目录，不影响 `reports/`
- 阶段8（部署）：只依赖 `reports/{TICKER}/` 最终文件
- 阶段9（飞书推送）：只依赖 `reports/{TICKER}/` 最终文件
- 三者互不依赖，可完全并行

**子代理 A — 阶段7 资源清理**：
1. 关闭 HTTP 服务器（StopCommand 关闭对应 command_id）
2. 删除临时工作目录 `data/{ticker}-{quarter}-earnings/`（保留 `data/{ticker}-{quarter}/` API 数据供调试）
3. 删除生成器临时脚本（parse-*.py、_gen_*.py、_verify*.py）
4. 保留 `reports/{TICKER}/` 最终产出物

**子代理 B — 阶段8 部署（Cloudflare 必选 + GitHub 可选）**：

**★ 部署策略**：读取 `config.local.json` 的 `deployment.targets` 判断：
- Cloudflare 始终必选（无条件执行 `wrangler pages deploy`）
- `deployment.targets` 含 `"github"` → 追加执行 GitHub 部署（依据 `github_repo_action` 选择 init/clone 流程，仓库名称动态读取 `deployment.github.repo`）；不含 → 跳过

**前置条件**：
- Cloudflare（必选）：wrangler 已授权、Cloudflare Pages 项目（运行时从 `deployment.github.repo` 提取仓库名作为 `--project-name`）已创建
- GitHub（可选，仅当 deployment.targets 含 github 时需要）：`gh` 已鉴权（`gh auth status` 检查）、仓库 `deployment.github.repo`（动态读取）已启用 Pages

**GitHub Pages**（仅当 deployment.targets 含 github 时执行）：`git push origin main` 后自动触发（1-2 分钟生效）。

**Cloudflare Pages 部署命令**（★ 必选，必须从 `cf-pages-deploy/` 父目录部署，保持 `/reports/` 路径前缀）：

```powershell
# Windows
# repo_root 从 config.local.json 的 paths.output_root + deployment.github.repo 推导（仓库目录 = output_root/Output/项目名）
$OutputRoot = "<从 config.local.json paths.output_root 读取，如 d:\TraeAutomaticTools>"
# CF_PROJECT 从 deployment.github.repo 提取仓库名（取 / 后的部分，无 / 则整体），同时作为仓库子目录名
$ghRepo = "<从 config.local.json deployment.github.repo 读取，如 wxdpop/stock-financial-reports>"
$CF_PROJECT = if ($ghRepo.Contains("/")) { $ghRepo.Split("/")[-1] } else { $ghRepo }
# 仓库目录 = output_root/Output/项目名（代码推导）
$repoRoot = Join-Path $OutputRoot "Output\$CF_PROJECT"
$src = "$repoRoot\reports"
$dst = "$repoRoot\cf-pages-deploy\reports"
# 1. 复制 reports/ 到 cf-pages-deploy/reports/（.NET API）
[System.IO.Directory]::CreateDirectory($dst) | Out-Null
Get-ChildItem -LiteralPath $src -Recurse | ForEach-Object {
    $dest = $_.FullName.Replace($src, $dst)
    if ($_.PSIsContainer) { [System.IO.Directory]::CreateDirectory($dest) | Out-Null }
    else { [System.IO.File]::Copy($_.FullName, $dest, $true) }
}
# 2. 从 cf-pages-deploy 目录部署（切勿直接部署 reports 目录）
Set-Location "$repoRoot\cf-pages-deploy"
npx --yes wrangler pages deploy . --project-name "$CF_PROJECT" --branch main --commit-dirty=true
# 3. 清理临时目录
[System.IO.Directory]::Delete("$repoRoot\cf-pages-deploy", $true)
```

```bash
# Mac/Linux
# repo_root 从 config.local.json 的 paths.output_root + deployment.github.repo 推导（仓库目录 = output_root/Output/项目名）
output_root="<从 config.local.json paths.output_root 读取，如 ~/TraeAutomaticTools>"
# CF_PROJECT 从 deployment.github.repo 提取仓库名（取 / 后的部分，无 / 则整体），同时作为仓库子目录名
gh_repo="<从 config.local.json deployment.github.repo 读取，如 wxdpop/stock-financial-reports>"
CF_PROJECT="${gh_repo##*/}"
# 仓库目录 = output_root/Output/项目名（代码推导）
repo_root="$output_root/Output/$CF_PROJECT"
mkdir -p "$repo_root/cf-pages-deploy/reports"
cp -r "$repo_root/reports/." "$repo_root/cf-pages-deploy/reports/"
cd "$repo_root/cf-pages-deploy"
npx --yes wrangler pages deploy . --project-name "$CF_PROJECT" --branch main --commit-dirty=true
rm -rf "$repo_root/cf-pages-deploy"
```

**★ 关键教训**：`wrangler pages deploy <dir>` 会将 `<dir>` 内容上传到 Pages 根目录。直接部署 `reports` 目录会变成 `/NFLX/xxx.html`（错误）；必须从包含 `reports/` 子目录的父目录部署，路径才是 `/reports/NFLX/xxx.html`（正确）。

**GitHub 部署命令**（仅当 deployment.targets 含 github 时执行；分支统一 `main`，仓库可见性 `public`，仓库名称动态读取 `deployment.github.repo`）：

```bash
# 仓库名称从 config.local.json 的 deployment.github.repo 读取（如 wxdpop/earnings-reports）
GH_REPO="<从 config.local.json deployment.github.repo 读取>"

# 首次部署（github_repo_action=init）：先创建远程仓库，再首次推送
gh repo create "$GH_REPO" --public
git add .
git commit -m "feat: add earnings report"
git push -u origin main

# 后续部署（github_repo_action=clone/pull 或已初始化）：直接提交并推送
git add .
git commit -m "feat: add earnings report"
git push
```

**返回 URL**：
- Cloudflare（必选主链接）：`https://earnings-reports.pages.dev/reports/{TICKER}/{filename}.html`
- GitHub（可选备用，仅当 deployment.targets 含 github 时返回）：`https://{github-user}.github.io/{repo-name}/reports/{TICKER}/{filename}.html`（从 `deployment.github.repo` 推导）

**子代理 C — 阶段9 飞书推送**（统一为 Python 入口）：

```bash
# 跨平台统一调用（17 个参数，详见 send-feishu.py --help）
# ★ --cf-pages-url 必选（Cloudflare 始终部署）；--report-url / --repo-url 可选（仅 deployment.targets 含 github 时传入）
python "{skill_dir}/references/send-feishu.py" \
    --company-name "公司中文名" --quarter "2026 Q2" \
    --cf-pages-url "https://earnings-reports.pages.dev/reports/{TICKER}/{filename}.html" \
    --report-url "https://wxdpop.github.io/earnings-reports/reports/{TICKER}/{filename}.html" \
    --repo-url "https://github.com/wxdpop/earnings-reports" \
    --revenue "..." --revenue-yoy "+9.6%" \
    --net-income "..." --net-income-yoy "-45.3%" \
    --gross-margin "14.6%" --margin-delta "-8.0 pts" \
    --key-metric "0.39 美元" --key-metric-label "每股收益(EPS)" --key-metric-delta "-45.8%" \
    --highlights "关键亮点1\n关键亮点2" \
    --file-size "1180 KB" --card-color "red"
```

★ 参数说明：
- `--cf-pages-url`（必选）：Cloudflare Pages URL，始终传入
- `--report-url`（可选）：GitHub Pages URL，仅当 `deployment.targets` 含 `github` 时传入；不含时留空，飞书卡片不显示 GitHub 备用按钮
- `--repo-url`（可选）：GitHub 仓库 URL，仅当 `deployment.targets` 含 `github` 时传入；不含时留空，飞书卡片不显示 GitHub 仓库按钮

Webhook URL 从 config.local.json 的 `feishu.webhook_url`（嵌套结构）加载（统一入口，不再支持环境变量，严禁硬编码）。推送全中文交互卡片，返回推送结果（StatusCode: 0 success）。

**任一子代理失败时，主代理弹窗提示具体失败阶段和原因。**

## 关键规范

### 文件路径与命名

- **最终存放路径**：`{repo_root}/reports/{TICKER}/{company-slug}-{quarter}-earnings.html`
- **TICKER**：股票代码大写（如 JPM/TSLA/ASML）
- **company-slug**：小写英文无空格（如 nok、tsmc、alphabet）
- **quarter 格式**：`q{N}-{YYYY}`（如 q2-2026）
- **占位符**：`{repo_root}` = 仓库目录（= `output_root`/Output/项目名，由代码推导），`{skill_dir}` = 技能根目录
- **脚本命名**：统一为 Python 单文件入口（`.py`），不再提供 `.ps1` / `.sh` 双版本；环境检测与 Chrome 路径检测在脚本内部按 `platform.system()` 分支处理

### 跨平台脚本统一入口

**平台检测**：脚本内部使用 Python `platform.system()` 判定（`Windows` / `Darwin` / `Linux`），自动选择路径候选与命令，无需用户介入。

**脚本对应关系**（统一 Python 入口，Windows/Mac/Linux 通用）：

| 功能 | 脚本路径 | 关键参数 | 备注 |
|------|---------|---------|------|
| 环境检查+安装 | `scripts/check-and-install.py` | `--china` / `--fix-config` / `--force-check` / `--skip-check` | 内部按平台选择安装命令（winget/brew/apt） |
| ★ 用户信息收集 | `scripts/collect-user-info.py` | `--mode standalone\|proxy` / `--answers` / `--check-only` | 承载 standalone 6 项 / proxy 7 项弹窗收集逻辑（规范见 info-collect-spec.md） |
| API 数据拉取 | `scripts/fetch-data.py` | `--symbol` / `--out-dir` | 完成后自动调用 parse-financial-data.py |
| 模板填充 | `scripts/fill-template.py` | `--template-file` / `--sections-file` / `--output-file` | 含结构完整性校验 |
| 单文件构建 | `references/build-standalone.py` | `--source-dir` / `--output-dir` | 使用 Python 字符串 .replace() 精确匹配 |
| 无头验证 | `references/verify-headless.py` | `<report.html>` | 内置 Chrome 三平台路径检测 |
| 飞书推送 | `references/send-feishu.py` | `--company-name` / `--quarter` 等 17 个参数 | Webhook URL 从 config 加载 |
| 数据解析 | `scripts/parse-financial-data.py` | 自动调用，无需手动执行 | ★ 跨平台，fetch-data 完成后自动调用 |

**参数风格**：统一 GNU 长参数（`--param-name "value"`），退出码一致（0=成功，1=失败）。

**文件编码**：所有 `.py` 文件 UTF-8 无 BOM LF。仓库根 `.gitattributes` 强制 LF 换行（除 .bat/.cmd 保持 CRLF）。

### 脱敏检查

- **严禁硬编码**：飞书 Webhook URL、API 密钥、令牌等敏感信息
- **传入方式**：config.local.json（唯一入口，被 .gitignore 排除）
- **配置字段**：`feishu.webhook_url`、`finnhub.api_key`、`alphavantage.api_key`、`paths.output_root`（均为嵌套结构）
- **config.local.json 必须被 .gitignore 排除**，仅提交 config.example.json 模板
- **提交前自查**：
  - Windows：`git diff --cached | findstr /i "hook webhook api_key token password secret"`
  - Mac/Linux：`git diff --cached | grep -iE "hook|webhook|api_key|token|password|secret"`
- 详见仓库根 `SECURITY.md`

### 参考文件清单

| 文件 | 用途 |
|------|------|
| `references/report-template.md` | HTML 报告模板（含 CSS/布局/TOC/12 section 结构） |
| `references/charts-template.js` | ECharts 图表模板（7 个固定图表） |
| `references/build-standalone.py` | 单文件构建脚本（Python 字符串 .replace() 精确匹配） |
| `references/verify-headless.py` | 无头浏览器验证脚本（跨平台 Python 3，内置 Chrome 三平台路径检测） |
| `references/send-feishu.py` | 飞书群推送脚本（跨平台 Python 3） |
| `references/info-collect-spec.md` | 信息收集规范文档（collect-user-info.py 的静态参考镜像） |
| `templates/sections-reference.md` | 各 section 必需子元素规范（结构校验依据） |
| `assets/js/echarts.min.js` | ★ echarts@5.5.0 内置库（1MB，build 脚本自动复制） |
| `scripts/check-and-install.py` | 环境检查+自动安装核心脚本（跨平台） |
| `scripts/collect-user-info.py` | 用户信息收集主入口（standalone/proxy 双模式） |
| `scripts/fetch-data.py` | API 数据拉取脚本（跨平台，自动调用 parse-financial-data.py） |
| `scripts/fill-template.py` | 模板填充脚本（跨平台，含结构完整性校验） |
| `scripts/parse-financial-data.py` | ★ 财务数据解析工具（跨平台，fetch-data 自动调用） |
| `config.example.json` | 配置文件模板（提交到仓库） |
| `config.local.json` | 真实配置（.gitignore 排除，含 API Key/Webhook） |

### 目录结构（精简）

```
earnings-report-skill/
├── SKILL.md                          # 本文档
├── config.local.json                 # 真实配置（.gitignore 排除）
├── config.example.json               # 配置模板
├── assets/js/echarts.min.js          # ★ echarts 内置库
├── references/                       # 参考资源与构建/验证/推送脚本（统一 Python）
│   ├── report-template.md            # HTML 模板
│   ├── charts-template.js            # 图表模板
│   ├── build-standalone.py           # 单文件构建（跨平台 Python 3）
│   ├── verify-headless.py            # 无头验证（跨平台 Python 3）
│   ├── send-feishu.py                # 飞书推送（跨平台 Python 3）
│   └── info-collect-spec.md          # 信息收集规范文档
├── scripts/                          # 核心脚本（统一 Python 单文件入口）
│   ├── check-and-install.py          # 环境检查+安装（跨平台）
│   ├── collect-user-info.py          # 用户信息收集（standalone/proxy 双模式）
│   ├── fetch-data.py                 # API 数据拉取（跨平台）
│   ├── fill-template.py              # 模板填充（跨平台）
│   └── parse-financial-data.py       # 数据解析（跨平台，fetch-data 自动调用）
└── templates/
    └── sections-reference.md         # section 结构规范
```

**生成的报告目录**（在用户工作空间的 git 仓库下，非 skill 目录）：

```
{output_root}/Output/{项目名}/                # 用户工作空间（仓库目录，由代码推导）
├── reports/{TICKER}/                 # 最终 HTML 统一存放点
│   └── {company-slug}-{quarter}-earnings.html
└── data/{symbol}-{quarter}/          # API 数据（供调试）
    └── {symbol}-{profile|recommendations|income-statement|balance-sheet|cashflow}.json
```

仓库目录 = `paths.output_root`/Output/项目名（代码运行时推导，项目名从 `deployment.github.repo` 提取仓库名；`paths.output_root` 为用户输入的输出根目录，盘符+文件夹）。

### 报告结构（12 章节固定顺序）

1. **Header** — 渐变背景 + kicker + 主标题 + 副标题 + meta + 4 个 stat-card
2. **01 核心摘要** — 概述 + highlights-box + callout（不重复 header 的 stat-grid）
3. **02 财务概览** — 7 行财务指标表格 + chart-revenue-trend
4. **03 营收分析** — 营收构成表格 + chart-revenue-mix + 驱动因素 callout
5. **04 盈利能力** — 利润率 stat-grid + chart-margin-trend + 成本结构表格 + callout
6. **05 资产负债与现金流** — 资产负债表 + chart-cashflow + insight-grid
7. **06 运营指标** — KPI stat-grid + chart-kpi-trend（公司特有指标）
8. **07 分部与地区** — chart-geo + 地区表格 + insight-grid
9. **08 业绩指引** — 指引表格 + timeline + callout
10. **09 管理层评论** — CEO/CFO callout + highlights-box
11. **10 风险因素** — risk-list（5 项左右）+ callout
12. **11 投资观点** — 估值 stat-grid + insight-grid + callout
13. **12 附录** — glossary + chart-radar + 数据说明

**布局**：桌面端（>700px）左侧固定侧边栏（160px，12 章节目录）+ 右侧主内容区（maxw 1200px）；移动端（≤700px）汉堡菜单抽屉式目录。
