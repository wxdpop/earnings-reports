# earnings-report Skill

> **自动生成上市公司最新财报深度分析 HTML 报告**：用户提供公司名 + 财报季度，技能完成数据搜集、整理、HTML 生成、校验、单文件构建、部署（Cloudflare 必选 + GitHub 可选）、飞书推送全流程。**子技能可独立使用，不依赖父技能**。

---

## ★ 技能定位

| 项 | 说明 |
|---|---|
| **技能类型** | 子技能（执行层）— 也可独立使用 |
| **核心能力** | 1 句话「分析 XX 财报」→ 自动生成自包含 HTML 财报深度分析报告 |
| **依赖关系** | **不依赖父技能**。可单独安装使用，也可被父技能 `earnings-report-orchestrator` 调度 |
| **跨平台** | Windows / Mac / Linux 三平台（统一 Python 3 单文件入口） |
| **跨 Agent** | Trae / Trae CN / Claude Code / Cursor / Codex 等 70+ Agent（通过 skills.sh 安装） |

### 子技能 vs 父技能

| 维度 | 子技能（本技能） | 父技能（orchestrator） |
|------|---------------|----------------------|
| 定位 | 执行层：生成单份财报报告 | 编排层：定时调度 + 公司库管理 + 就绪检查 |
| 触发方式 | **手动执行**：用户提供公司名 + 季度 | 自动调度：定时检查财报发布状态 |
| 依赖 | 无（独立可用） | 依赖本子技能 |
| 适用场景 | 按需生成指定公司财报 | 财报季自动跟踪多家公司 |

> **★ 关键**：子技能可单独安装使用，**不需要安装父技能**。如需自动化定时调度多家公司，再安装父技能。

---

## ★ 工作流程（10 阶段）

```
用户输入公司名 + 财报季度
    ↓
阶段 -1：环境检查（首次/变更时）→ check-and-install.py
    ↓
阶段 -1.5：★ 用户信息收集 → collect-user-info.py
    ↓
阶段 0：解析输入（公司名/季度/本位币）
    ↓
阶段 1：数据拉取（★ 并行）
    ├─ 1.1 API 结构化数据（fetch-data.py：Finnhub + Alpha Vantage）
    └─ 1.2 WebFetch 白名单辅助（公司 IR + 格隆汇/富途/汇通/华盛通）
    ↓
阶段 2：数据整理 + 汇率换算
    ↓
阶段 3：生成 sections JSON（LLM 整段 HTML）+ charts.js
    ↓
阶段 4：模板填充（fill-template.py，含结构完整性校验）
    ↓
阶段 5：单文件构建（build-standalone.py，Python 字符串 .replace() 精确匹配）
    ↓
阶段 6：无头浏览器验证（verify-headless.py，Chrome headless）
    ↓
阶段 7-9：并行执行
    ├─ 阶段 7：资源清理
    ├─ 阶段 8：部署（Cloudflare 必选 + GitHub 可选）
    └─ 阶段 9：飞书群推送（全中文交互卡片）
```

---

## ★ 一键安装 Skill

### 通用安装（推荐，安装到所有支持的 Agent，全局）

```powershell
npx skills add https://github.com/wxdpop/earnings-reports/tree/main/earnings-report-skill -g -a "*" -y --skill earnings-report
```

### 仅安装到 Trae CN（中国版）

```powershell
npx skills add https://github.com/wxdpop/earnings-reports/tree/main/earnings-report-skill -g -a trae-cn -y --skill earnings-report
```

### 仅安装到指定 Agent（如 Claude Code + Cursor）

```powershell
npx skills add https://github.com/wxdpop/earnings-reports/tree/main/earnings-report-skill -g -a claude-code cursor -y --skill earnings-report
```

### 参数说明

| 参数 | 含义 | 必填 |
|------|------|------|
| `https://github.com/wxdpop/earnings-reports/tree/main/earnings-report-skill` | Skill 所在的 GitHub 子目录 URL | 是 |
| `-g` | 全局安装（用户级，所有项目可用） | 是 |
| `-a "*"` | 安装到所有支持的 Agent（Trae/Trae CN/Claude Code/Cursor/Codex 等） | 是 |
| `-a trae-cn` | 仅安装到指定 Agent（可多选，空格分隔） | 二选一 |
| `-y` | 跳过交互确认 | 是 |
| `--skill earnings-report` | 指定要安装的 Skill 名称 | 是 |

### 前提条件

- **Node.js 22+**（npx 运行所需）：
  - Windows：`winget install OpenJS.NodeJS.LTS`
  - Mac：`brew install node`
  - Linux（Ubuntu/Debian）：`sudo apt-get install nodejs npm`
  - Linux（CentOS/RHEL）：`sudo yum install nodejs`

### Skill 安装目录

| Agent | 全局安装路径 |
|-------|-------------|
| Trae CN | `~/.trae-cn/skills/earnings-report/` |
| Trae | `~/.trae/skills/earnings-report/` |
| Claude Code | `~/.claude/skills/earnings-report/` |
| Cursor | `~/.cursor/skills/earnings-report/` |

### 其他常用命令

```powershell
# 查看已安装的 Skill
npx skills list

# 检查 Skill 更新
npx skills check

# 更新所有 Skill 到最新版本
npx skills update

# 卸载 Skill
npx skills remove earnings-report

# 搜索 skills.sh 上的其他 Skill
npx skills find "财报"
```

> **★ 提示**：一键安装命令仅安装 Skill 本身（SKILL.md + scripts/ + references/ + templates/），不会自动安装依赖和创建配置文件。安装完成后，在 Trae 对话中说「检查环境」，AI 会自动调用 `check-and-install.py` 引导完成剩余配置。

---

## ★ 使用方式

### 方式一：在 Trae IDE 中调用（推荐）

将本技能安装到 Trae skills 目录后，在 Trae 对话中直接说：

```
分析特斯拉最新财报
分析英伟达 2026 Q2 财报
分析阿里巴巴 earnings
分析阿斯利康 2026 Q1 业绩
```

AI 会自动按 10 阶段工作流执行，无需手动指定参数。

### 方式二：手动按阶段执行（调试/集成场景）

如需在命令行或脚本中手动调用，按以下阶段顺序执行：

```bash
# 阶段 -1：环境检查 + 自动安装（首次必执行）
python "{skill_dir}/scripts/check-and-install.py"
python "{skill_dir}/scripts/check-and-install.py" --fix-config  # 创建配置模板
python "{skill_dir}/scripts/check-and-install.py" --china       # 强制国内镜像

# 阶段 1.1：API 数据拉取（Finnhub + Alpha Vantage，自动调用 parse-financial-data.py）
python "{skill_dir}/scripts/fetch-data.py" --symbol "TSLA" --out-dir "{output_dir}/data/tsla-q2-2026"

# 阶段 4：模板填充（含结构完整性校验）
python "{skill_dir}/scripts/fill-template.py" \
    --template-file "{skill_dir}/references/report-template.md" \
    --sections-file "{output_dir}/data/tsla-q2-2026-sections.json" \
    --output-file "{output_dir}/tsla-q2-2026-earnings/index.html"

# 阶段 5：单文件构建（Python 字符串 .replace() 精确匹配）
python "{skill_dir}/references/build-standalone.py" --source-dir "{output_dir}/tsla-q2-2026-earnings"

# 阶段 6：无头浏览器验证（Chrome headless，跨平台路径检测）
python "{skill_dir}/references/verify-headless.py" "{repo_dir}/reports/TSLA/tsla-q2-2026-earnings.html"

# 阶段 9：飞书推送（17 个参数，详见 send-feishu.py --help）
python "{skill_dir}/references/send-feishu.py" \
    --company-name "特斯拉" --quarter "2026 Q2" \
    --report-url "https://wxdpop.github.io/earnings-reports/reports/TSLA/tsla-q2-2026-earnings.html" \
    --cf-pages-url "https://earnings-reports.pages.dev/reports/TSLA/tsla-q2-2026-earnings.html" \
    --repo-url "https://github.com/wxdpop/earnings-reports" \
    --revenue "..." --revenue-yoy "+9.6%" \
    --net-income "..." --net-income-yoy "-45.3%" \
    --gross-margin "14.6%" --margin-delta "-8.0 pts" \
    --key-metric "0.39 美元" --key-metric-label "每股收益(EPS)" --key-metric-delta "-45.8%" \
    --highlights "关键亮点1\n关键亮点2" \
    --file-size "1180 KB" --card-color "red"
```

### 方式三：被父技能自动调度

如已安装父技能 `earnings-report-orchestrator`，则无需手动调用本子技能：

- 父技能初始化时自动调用 `check-and-install.py` 完成环境检测
- 父技能定时任务命中财报发布日 → 就绪检查全 PASS → 自动调用本子技能 10 阶段工作流
- 详见父技能 README：[earnings-report-orchestrator-skill/SKILL.md](../earnings-report-orchestrator-skill/SKILL.md)

---

## ★ 配置文件

### 配置文件加载策略

- **唯一入口**：`config.local.json`（不再支持环境变量，降低复杂性）
- **模板文件**：`config.example.json`（已脱敏，提交到 git）
- **真实配置**：`config.local.json`（被 `.gitignore` 排除，不提交）

### 创建配置文件

```bash
# 复制模板（如尚未创建）
# Windows
Copy-Item "<skill_dir>\config.example.json" "<skill_dir>\config.local.json"
# Mac/Linux
cp "<skill_dir>/config.example.json" "<skill_dir>/config.local.json"

# 或通过环境检查脚本自动创建
python "<skill_dir>/scripts/check-and-install.py" --fix-config
```

### ★ 信息收集流程

除了手动编辑 config.local.json，还可通过 `collect-user-info.py` 引导收集配置：

```bash
# standalone 模式（子技能独立使用，两阶段调用协议）
# 阶段 A：输出弹窗规范 JSON
python "<skill_dir>/scripts/collect-user-info.py" --mode standalone

# 阶段 B：LLM 执行弹窗后回传答案，写入 config.local.json
python "<skill_dir>/scripts/collect-user-info.py" --mode standalone --answers /path/to/answers.json

# 仅检测占位符和登录状态
python "<skill_dir>/scripts/collect-user-info.py" --mode standalone --check-only
```

**两种调用模式**：
- `standalone`：子技能独立使用，写入子技能自身 config.local.json
- `proxy`：被父技能初始化时代理调用，写入父技能 config.local.json

**6 项收集项**：工作根目录 / 调度间隔 / API Key 状态 / 飞书 Webhook / 公司库导入方案 / 部署方案

详细规范见 [info-collect-spec.md](references/info-collect-spec.md)

### config.local.json 配置示例（子技能）

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
    "output_dir": "",
    "repo_dir": ""
  }
}
```

### 路径配置说明

★ 路径分类规则（区分两类目录）：

| 字段 | 含义 | 目录类型 | 默认值 |
|------|------|---------|--------|
| `paths.output_dir` | 报告输出根目录 | **输出目录**（用户工作空间） | `<工作根目录>/Output/stock-financial-reports`（需用户填写） |
| `paths.repo_dir` | git 仓库根目录 | **输出目录**（用户工作空间） | 同 `paths.output_dir`（需为 git 仓库根目录） |

> **★ 关键规则**：输出/仓库目录**不从技能安装路径推断**，必须由用户显式填写。
>
> - **独立使用本子技能时**：手动编辑 `config.local.json` 填写 `paths.output_dir` 和 `paths.repo_dir`
> - **被父技能调度时**：父技能初始化时通过弹窗询问工作根目录后自动填写

### 验证配置生效

```bash
# 运行环境检查脚本（自动检查 9 项依赖与配置）
python "<skill_dir>/scripts/check-and-install.py"

# 预期输出：所有检查项为 [PASS]
```

### API Key / Webhook 注册

**所有 API Key、Webhook、Token、部署站点账号的注册和获取流程**，请参阅：

> 📖 [注册和 Token 获取方式（完整文档）](../注册和Token获取方式.md)

简要对照表：

| 配置项 | 用途 | 是否必选 | 获取方式 |
|--------|------|---------|---------|
| `finnhub.api_key` | API 数据拉取（公司 profile、分析师评级） | 必选 | [Finnhub 注册](https://finnhub.io/register) |
| `alphavantage.api_key` | API 数据拉取（三大报表） | 必选 | [Alpha Vantage 注册](https://www.alphavantage.support/free-api-key) |
| `feishu.webhook_url` | 飞书群推送 | 必选（可跳过） | 飞书群 → 群机器人 → 添加自定义机器人 |
| `paths.output_dir` | 报告输出目录 | 必选 | 用户工作空间路径 |
| `paths.repo_dir` | git 仓库目录 | 必选 | 同 `paths.output_dir` |
| `deployment.targets` | 部署方案（`["cloudflare"]` 或 `["cloudflare","github"]`） | 必选 | collect-user-info.py 弹窗 5 收集 |
| `deployment.cloudflare.api_token` | Cloudflare Pages 部署 | 必选 | [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens) |
| `deployment.cloudflare.account_id` | Cloudflare 账户标识 | 必选 | Cloudflare Dashboard 右侧栏 |
| `deployment.cloudflare.project_name` | Cloudflare Pages 项目名 | 必选 | 运行时从 `deployment.github.repo` 仓库名推导，不在配置文件中定义 |
| `deployment.github.enabled` | GitHub 部署开关 | 可选 | targets 含 github 时 true |
| `deployment.github.repo` | GitHub 仓库地址 | 可选 | `用户名/仓库名` |

---

## ★ 技能目录结构

```
earnings-report-skill/
├── SKILL.md                          # 技能主配置文件（工作流程定义）
├── README.md                         # 本文档
├── config.example.json               # 配置模板（已脱敏，提交到 git）
├── config.local.json                 # 真实配置（★ 被 .gitignore 排除，不提交）
├── assets/
│   └── js/
│       └── echarts.min.js            # ★ echarts@5.5.0 内置库（1MB，build 脚本自动复制）
├── references/                       # 参考资源与构建/验证/推送脚本（★ 统一 Python）
│   ├── report-template.md            # HTML 报告模板（含 CSS/布局/TOC/12 section 结构）
│   ├── charts-template.js            # ECharts 图表模板（7 个固定图表）
│   ├── build-standalone.py           # 单文件构建脚本（Python 字符串 .replace() 精确匹配）
│   ├── verify-headless.py            # 无头浏览器验证脚本（跨平台 Python 3，Chrome 三平台路径检测）
│   └── send-feishu.py                # 飞书群推送脚本（跨平台 Python 3）
├── scripts/                          # 核心脚本（★ 统一 Python 单文件入口）
│   ├── check-and-install.py          # 环境检查 + 自动安装（跨平台，9 项依赖并行检查）
│   ├── fetch-data.py                 # API 数据拉取（Finnhub + Alpha Vantage，自动调用 parse-financial-data.py）
│   ├── fill-template.py              # 模板填充脚本（含结构完整性校验）
│   └── parse-financial-data.py       # 财务数据解析工具（fetch-data 自动调用，输出 6 季度财务摘要）
└── templates/
    └── sections-reference.md         # 各 section 必需子元素规范（结构校验依据）
```

### 生成的报告目录结构（在用户工作空间的 git 仓库下，非 skill 目录）

```
<工作根目录>/Output/stock-financial-reports/    # 用户工作空间
├── reports/{TICKER}/                  # 最终 HTML 统一存放点（按公司股票代码大写分文件夹）
│   └── {company-slug}-{quarter}-earnings.html
└── data/{symbol}-{quarter}/           # API 数据（供调试，阶段 7 自动清理）
    └── {symbol}-{profile|recommendations|income-statement|balance-sheet|cashflow}.json
```

---

## ★ 环境依赖（跨平台，跨 Agent）

### 运行时依赖（9 项，check-and-install.py 自动检测+安装）

| # | 依赖项 | 版本要求 | 用途 | Windows 安装 | Mac/Linux 安装 |
|---|--------|---------|------|-------------|---------------|
| 1 | Python | 3.8+ | 所有脚本运行前提（★ 必选） | `winget install Python.Python.3.12` | `brew install python@3.12` / `sudo apt-get install python3` |
| 2 | Node.js | 18+（推荐 22+） | wrangler 运行环境 | `winget install OpenJS.NodeJS.LTS` | `brew install node@18` / NodeSource |
| 3 | Google Chrome | 稳定版 | 无头浏览器验证 | `winget install Google.Chrome` | `brew install --cask google-chrome` / apt 添加 Google 源 |
| 4 | Git | 2.x | 仓库管理 | `winget install Git.Git` | `brew install git` / `sudo apt-get install git` |
| 5 | GitHub CLI (gh) | 最新 | GitHub Pages 部署 | `winget install GitHub.cli` | `brew install gh` / apt 添加 GitHub 源 |
| 6 | wrangler | 4.x | Cloudflare Pages 部署 | `npm i -g wrangler`（国内用 npmmirror） | `npm i -g wrangler`（国内用 npmmirror） |
| 7 | PowerShell | 7+ | 可选（部分场景使用） | `winget install Microsoft.PowerShell` | Mac/Linux 可选 |
| 8 | config.local.json | — | 配置文件 | `--fix-config` 自动创建 | `--fix-config` 自动创建 |
| 9 | git 仓库 | — | 报告存放与部署 | 检查 `.git` + remote origin | 检查 `.git` + remote origin |

> **国内 IP 自动启用镜像源**：npm 淘宝 `registry.npmmirror.com` / pip 清华 `pypi.tuna.tsinghua.edu.cn` / Homebrew 清华 / apt 清华。或通过 `--china` 强制启用。

### 跨平台支持

| 平台 | 状态 | 备注 |
|------|------|------|
| Windows 10 1709+ | ✅ 完整支持 | 推荐 winget 安装依赖 |
| macOS 11+ | ✅ 完整支持 | 推荐 Homebrew 安装依赖 |
| Linux（Ubuntu/Debian/CentOS/RHEL） | ✅ 完整支持 | apt / yum 包管理器 |

### 跨 Agent 支持（通过 skills.sh 安装）

| Agent | 安装路径 | 状态 |
|-------|---------|------|
| Trae CN | `~/.trae-cn/skills/earnings-report/` | ✅ 完整支持 |
| Trae | `~/.trae/skills/earnings-report/` | ✅ 完整支持 |
| Claude Code | `~/.claude/skills/earnings-report/` | ✅ 完整支持 |
| Cursor | `~/.cursor/skills/earnings-report/` | ✅ 完整支持 |
| Codex | `~/.codex/skills/earnings-report/` | ✅ 完整支持 |
| 其他 70+ Agent | 各 Agent skills 目录 | ✅ 通过 skills.sh 通用安装 |

> **★ Trae 专有能力**（其他 Agent 可降级）：
> - `Schedule` 工具 → 系统级 cron 替代
> - `AskUserQuestion` → 命令行 stdin 替代
> - `Task` 子代理 → 串行执行 / Python multiprocessing 替代
> - `WebFetch` → Python `requests` 替代

### 环境检查缓存机制

- 全部 PASS 后结果保存到 `.env-check-result.{platform}.json`（按平台分文件，永久有效）
- 下次运行直接读取缓存秒级通过
- `--force-check` 强制重检（忽略缓存）
- 缓存文件被 `.gitignore` 排除

---

## ★ 报告特性

### 输出格式

- **单文件输出**：所有 JS/CSS 内联，无外部依赖，体积约 1-1.2 MB
- **7 个 ECharts 图表**：SVG 渲染、响应式、移动端适配、★ 标签强制简体中文
- **左侧侧边栏目录**：桌面端固定侧边栏（160px）+ 移动端抽屉式菜单 + 滚动高亮
- **12 章节结构化报告**：核心摘要 → 财务概览 → 营收分析 → ... → 投资观点 → 附录
- **移动端兼容**：两档断点（700px / 480px），全元素适配

### 12 章节结构

| Section | 标题 | 必需子元素 |
|---------|------|-----------|
| Header | 报告头部 | `.stat-grid` + 4 个 `.stat-card` |
| sec01 | 核心摘要 | highlights-box, callout（禁止 stat-grid） |
| sec02 | 财务概览 | chart-revenue-trend, table |
| sec03 | 营收分析 | chart-revenue-mix, table, callout |
| sec04 | 盈利能力 | stat-grid, chart-margin-trend, table, callout |
| sec05 | 资产负债与现金流 | chart-cashflow, table, insight-grid |
| sec06 | 运营指标 | stat-grid, chart-kpi-trend |
| sec07 | 分部与地区 | chart-geo, table, insight-grid |
| sec08 | 业绩指引 | table, timeline, callout |
| sec09 | 管理层评论 | callout, highlights-box |
| sec10 | 风险因素 | risk-list, callout |
| sec11 | 投资观点 | stat-grid, insight-grid, callout |
| sec12 | 附录 | glossary, chart-radar |

### 部署架构（Cloudflare 必选 + GitHub 可选）

| 节点 | URL 格式 | 适用场景 | 优先级 |
|------|---------|---------|--------|
| **Cloudflare Pages** | `https://earnings-reports.pages.dev/reports/{TICKER}/{filename}.html` | 境内境外均可（必选主链接） | ★ 必选 |
| GitHub Pages（可选） | `https://wxdpop.github.io/earnings-reports/reports/{TICKER}/{filename}.html` | 境外备份（deployment.targets 含 github 时启用） | 可选备份 |

**为什么 Cloudflare Pages 为必选主链接？**
- GitHub Pages 在境内访问不稳定，偶发抽风
- Cloudflare Pages 在境内有 CDN 节点，访问稳定、速度快，不会被墙
- GitHub 为可选备节点，默认不启用，需要时在 deployment.targets 追加 "github"

### 飞书交互卡片推送效果

推送内容包含：
- 卡片标题：`{公司中文名} {季度} 财报分析报告`
- 卡片颜色：`green`（业绩好）/ `red`（业绩差）/ `blue`（中性）
- 4 个数据字段：营收、净利润、毛利率、关键指标
- 按钮：查看报告（Cloudflare 主链接，必选）/ 查看报告（GitHub 备用，可选）/ GitHub 仓库（可选）
- 关键亮点列表（3-5 条）
- 链接信息（根据部署方案动态生成）

---

## ★ 文件命名规则

| 类型 | 格式 | 示例 |
|------|------|------|
| 仓库文件夹 | `{TICKER}/`（大写） | `TSLA/`, `ASML/`, `NVDA/` |
| HTML 文件 | `{company-slug}-{quarter}-earnings.html` | `tsla-q2-2026-earnings.html` |
| company-slug | 小写英文无空格 | `tsla`, `asml`, `tsmc`, `alphabet` |
| quarter | `q{N}-{YYYY}` | `q2-2026`, `q1-fy2026` |

---

## ★ 数据源白名单

### 允许（P0/P1/P2）

- **P0**：公司官方 IR 页面（原始财报数据，必选）
- **P1**：格隆汇（gelonghui.com）、富途资讯（futunn.com）、汇通财经（fx678.com）、华盛通（hstong.com）
- **P2**：投行研报（Goldman Sachs / JPMorgan / BNP Paribas 等）

### 禁止

搜狐、今日头条、东方财富、百度百家号、微信公众号等非专业财经媒体一律不得引用。

### 汇率换算规则

- **美元本位币公司**（TSLA/NVDA/AAPL/MSFT 等）：直接用美元，meta 注明「不涉及汇率换算」
- **非美元本位币公司**（ASML/EUR、NOK/EUR、TSMC/TWD、Toyota/JPY 等）：保留当地货币，括号备注美元，格式 `营收 53.28 亿欧元（约 57.62 亿美元）`
- **换算汇率**：财报发布日官方汇率，保留 4 位小数

---

## ★ 跨平台脚本统一入口

**所有脚本统一为 Python 3 单文件入口**（Windows/Mac/Linux 通用），不再提供 .ps1/.sh 双版本。

| 功能 | 脚本路径 | 关键参数 | 备注 |
|------|---------|---------|------|
| 环境检查+安装 | `scripts/check-and-install.py` | `--china` / `--fix-config` / `--force-check` / `--skip-check` | 内部按平台选择安装命令（winget/brew/apt） |
| API 数据拉取 | `scripts/fetch-data.py` | `--symbol` / `--out-dir` | 完成后自动调用 parse-financial-data.py |
| 财务数据解析 | `scripts/parse-financial-data.py` | 自动调用，无需手动执行 | 输出 6 季度财务摘要 |
| 模板填充 | `scripts/fill-template.py` | `--template-file` / `--sections-file` / `--output-file` | 含结构完整性校验 |
| 单文件构建 | `references/build-standalone.py` | `--source-dir` / `--output-dir` | 使用 Python 字符串 .replace() 精确匹配 |
| 无头验证 | `references/verify-headless.py` | `<report.html>` | 内置 Chrome 三平台路径检测 |
| 飞书推送 | `references/send-feishu.py` | `--company-name` / `--quarter` 等 17 个参数 | Webhook URL 从 config 加载 |

**参数风格**：统一 GNU 长参数（`--param-name "value"`），退出码一致（0=成功，1=失败）。

**文件编码**：所有 `.py` 文件 UTF-8 无 BOM LF。仓库根 `.gitattributes` 强制 LF 换行（除 .bat/.cmd 保持 CRLF）。

### Chrome 路径检测（按优先级，三平台完整候选）

| 平台 | 候选路径（按优先级） |
|------|---------------------|
| Windows | `C:\Program Files\Google\Chrome\Application\chrome.exe` → `%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe` → `%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe` |
| Mac | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` → `~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` |
| Linux | `/usr/bin/google-chrome` → `/usr/bin/google-chrome-stable` → `/usr/bin/chromium-browser` → `/usr/bin/chromium` |

> Chrome 不可用时自动退化为纯 HTML 结构验证（不执行 JS，无法验证图表渲染）。

---

## ★ 自动化硬性约束

> 本 Skill 设计用于自动化任务调用，执行过程中**全程静默**，仅在检测失败或异常时弹窗。

1. **所有 RunCommand 设置 `requires_approval: false`** — 禁止命令审批弹窗
2. **弹窗边界** — 仅以下 3 种情况调用 `AskUserQuestion`：
   - 环境检测不通过（阶段 -1）
   - 配置文件未正确配置（阶段 -1）
   - 环节执行失败
3. **命令阻塞** — `blocking: true`（除 HTTP 服务器用 `blocking: false`）
4. **文件操作用 Python pathlib / shutil** — `pathlib.Path` / `shutil.copy2` / `shutil.rmtree` 等，禁止 `os.system` 调用 `Copy-Item` / `cp` 等高风险命令
5. **无头验证用 Chrome headless** — 跨平台路径自动检测，Chrome 不可用时退化为纯 HTML 结构验证
6. **阶段7/8/9 并行执行** — 阶段6 验证 PASS 后，单条消息并行启动 3 个子代理（Task 工具），等待全部返回
7. **★ 阶段1 数据拉取并行执行** — API 脚本（RunCommand）+ 多站点 WebFetch（N 个 Task 子代理）在单条消息中并行启动，等待全部返回后汇总
8. **脱敏检查** — 提交前自查，严禁硬编码 API Key / Webhook URL / Token
9. **执行完毕清理资源** — 关闭 HTTP 服务器、删除临时文件

---

## ★ 脱敏检查规范

- **严禁硬编码**：飞书 Webhook URL、API 密钥、Token 等敏感信息
- **传入方式**：`config.local.json`（唯一入口，被 `.gitignore` 排除）
- **配置字段**：`feishu.webhook_url`、`finnhub.api_key`、`alphavantage.api_key`、`paths.output_dir`、`paths.repo_dir`（均为嵌套结构）
- **`config.local.json` 必须被 `.gitignore` 排除**，仅提交 `config.example.json` 模板
- **提交前自查**：
  - Windows：`git diff --cached | findstr /i "hook webhook api_key token password secret"`
  - Mac/Linux：`git diff --cached | grep -iE "hook|webhook|api_key|token|password|secret"`

---

## ★ 已验证公司

> 以下公司财报报告均由本技能自动生成，并已在 Windows / Mac / Linux 三平台验证脚本可正常执行。报告存放在仓库 `reports/{TICKER}/` 目录下。

| 公司 | 代码 | 报告链接 | 在线访问 |
|------|------|---------|---------|
| 摩根大通（JPMorgan Chase & Co.） | JPM | [2026 Q2 报告](../reports/JPM/jpmorgan-q2-2026-earnings.html) | [GitHub Pages](https://wxdpop.github.io/earnings-reports/reports/JPM/jpmorgan-q2-2026-earnings.html) / [国内镜像](https://earnings-reports.pages.dev/reports/JPM/jpmorgan-q2-2026-earnings.html) |
| 特斯拉（Tesla, Inc.） | TSLA | [2026 Q2 报告](../reports/TSLA/tsla-q2-2026-earnings.html) | [GitHub Pages](https://wxdpop.github.io/earnings-reports/reports/TSLA/tsla-q2-2026-earnings.html) / [国内镜像](https://earnings-reports.pages.dev/reports/TSLA/tsla-q2-2026-earnings.html) |
| 谷歌（Alphabet Inc.） | GOOGL | [2026 Q2 报告](../reports/GOOGL/alphabet-q2-2026-earnings.html) | [GitHub Pages](https://wxdpop.github.io/earnings-reports/reports/GOOGL/alphabet-q2-2026-earnings.html) / [国内镜像](https://earnings-reports.pages.dev/reports/GOOGL/alphabet-q2-2026-earnings.html) |
| 英特尔（Intel Corporation） | INTC | [2026 Q2 报告](../reports/INTC/intel-q2-2026-earnings.html) | [GitHub Pages](https://wxdpop.github.io/earnings-reports/reports/INTC/intel-q2-2026-earnings.html) / [国内镜像](https://earnings-reports.pages.dev/reports/INTC/intel-q2-2026-earnings.html) |
| 诺基亚（Nokia Corporation） | NOK | [2026 Q2 报告](../reports/NOK/nok-q2-2026-earnings.html) | [GitHub Pages](https://wxdpop.github.io/earnings-reports/reports/NOK/nok-q2-2026-earnings.html) / [国内镜像](https://earnings-reports.pages.dev/reports/NOK/nok-q2-2026-earnings.html) |
| 强生（Johnson & Johnson） | JNJ | [2026 Q2 报告](../reports/JNJ/jnj-q2-2026-earnings.html) | [GitHub Pages](https://wxdpop.github.io/earnings-reports/reports/JNJ/jnj-q2-2026-earnings.html) / [国内镜像](https://earnings-reports.pages.dev/reports/JNJ/jnj-q2-2026-earnings.html) |
| 高盛（Goldman Sachs Group） | GS | [2026 Q2 报告](../reports/GS/gs-q2-2026-earnings.html) | [GitHub Pages](https://wxdpop.github.io/earnings-reports/reports/GS/gs-q2-2026-earnings.html) / [国内镜像](https://earnings-reports.pages.dev/reports/GS/gs-q2-2026-earnings.html) |
| IBM（International Business Machines） | IBM | [2026 Q2 报告](../reports/IBM/ibm-q2-2026-earnings.html) | [GitHub Pages](https://wxdpop.github.io/earnings-reports/reports/IBM/ibm-q2-2026-earnings.html) / [国内镜像](https://earnings-reports.pages.dev/reports/IBM/ibm-q2-2026-earnings.html) |
| 阿斯利康（AstraZeneca PLC） | AZN | [2026 Q1 报告](../reports/AZN/astrazeneca-q1-2026-earnings.html) | [GitHub Pages](https://wxdpop.github.io/earnings-reports/reports/AZN/astrazeneca-q1-2026-earnings.html) / [国内镜像](https://earnings-reports.pages.dev/reports/AZN/astrazeneca-q1-2026-earnings.html) |
| 阿里巴巴（Alibaba Group） | BABA | [2026 Q1 报告](../reports/BABA/alibabagroupholdingltd-q1-fy2026-earnings.html) | [GitHub Pages](https://wxdpop.github.io/earnings-reports/reports/BABA/alibabagroupholdingltd-q1-fy2026-earnings.html) / [国内镜像](https://earnings-reports.pages.dev/reports/BABA/alibabagroupholdingltd-q1-fy2026-earnings.html) |
| 英伟达（NVIDIA Corporation） | NVDA | [2026 Q1 报告](../reports/NVDA/nvidia-q1-2026-earnings.html) | [GitHub Pages](https://wxdpop.github.io/earnings-reports/reports/NVDA/nvidia-q1-2026-earnings.html) / [国内镜像](https://earnings-reports.pages.dev/reports/NVDA/nvidia-q1-2026-earnings.html) |
| 网飞（Netflix, Inc.） | NFLX | [2026 Q2 报告](../reports/NFLX/netflix-q2-2026-earnings.html) | [GitHub Pages](https://wxdpop.github.io/earnings-reports/reports/NFLX/netflix-q2-2026-earnings.html) / [国内镜像](https://earnings-reports.pages.dev/reports/NFLX/netflix-q2-2026-earnings.html) |
| 联合健康（UnitedHealth Group） | UNH | [2026 Q2 报告](../reports/UNH/unitedhealth-q2-2026-earnings.html) | [GitHub Pages](https://wxdpop.github.io/earnings-reports/reports/UNH/unitedhealth-q2-2026-earnings.html) / [国内镜像](https://earnings-reports.pages.dev/reports/UNH/unitedhealth-q2-2026-earnings.html) |
| Rocket Lab（Rocket Lab USA） | RKLB | [2026 Q1 报告](../reports/RKLB/rocketlab-q1-2026-earnings.html) / [2026 Q2 报告](../reports/RKLB/rocketlab-q2-2026-earnings.html) | [GitHub Pages](https://wxdpop.github.io/earnings-reports/reports/RKLB/rocketlab-q1-2026-earnings.html) / [国内镜像](https://earnings-reports.pages.dev/reports/RKLB/rocketlab-q1-2026-earnings.html) |
| Robinhood（Robinhood Markets） | HOOD | [2026 Q1 报告](../reports/HOOD/hood-q1-2026-earnings.html) | [GitHub Pages](https://wxdpop.github.io/earnings-reports/reports/HOOD/hood-q1-2026-earnings.html) / [国内镜像](https://earnings-reports.pages.dev/reports/HOOD/hood-q1-2026-earnings.html) |
| Nebius Group | NBIS | [2026 Q1 报告](../reports/NBIS/nebis-q1-2026-earnings.html) | [GitHub Pages](https://wxdpop.github.io/earnings-reports/reports/NBIS/nebis-q1-2026-earnings.html) / [国内镜像](https://earnings-reports.pages.dev/reports/NBIS/nebis-q1-2026-earnings.html) |

> 涵盖多元行业：金融（JPM/GS/HOOD）、科技（GOOGL/IBM/INTC/NVDA/NFLX/NBIS）、汽车（TSLA/RKLB）、通信（NOK）、医疗（JNJ/UNH/AZN）、电商（BABA），验证技能对不同行业财报的适配能力。

---

## ★ 相关文档

- 📖 [注册和 Token 获取方式](../注册和Token获取方式.md) — 所有 API Key、Webhook、Token 注册流程
- 📖 [父技能 SKILL.md](../earnings-report-orchestrator-skill/SKILL.md) — 父技能编排调度规范
- 📖 [Section 结构规范](templates/sections-reference.md) — 各 section 必需子元素
- 📖 [仓库主 README](../README.md) — 仓库总览

---

## 许可证

MIT License - 可自由使用、修改、分发。
