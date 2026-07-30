---
name: "earnings-report-orchestrator"
description: "财报编排调度技能。1句话触发初始化：先收集调度间隔/配置/公司库（前置用户交互），再由 LLM 检测并自动安装 Python 前提项，调用子技能脚本生成 env-check-result 缓存，自动创建定时任务。符合触发条件才真正调用子技能生成报告。"
---

# 财报编排调度器（v3.2.2）

## 概述

父技能（orchestrator），作为**编排层**，不重写报告生成逻辑：

1. **★ 信息收集前置**：1 句话触发初始化后，先收集「工作根目录 + 调度间隔 + API Key + Webhook + 公司库 + 部署方案」6 项用户交互，全部收集完毕再执行环境检测
2. **★ Python 前提项 + LLM 自动安装**：Python 3.8+ 是所有脚本运行前提。LLM 检测到 Python 不存在时**直接调用系统包管理器安装**（winget/brew/apt），无需用户确认
3. **★ 父技能代理子技能环境检测**：调用子技能 `check-and-install.py`，子技能目录生成 `.env-check-result.{platform}.json` 缓存（永久有效）
4. **★ 自动创建定时任务**：通过 TRAE `Schedule` 工具创建（默认每 12 小时），符合触发条件才调用子技能
5. **★ 就绪检查三验证**：财报发布 + 电话会议结束 + 媒体更新全 PASS → 调用子技能 `earnings-report` 生成报告
6. **★ v3.1 静默调度规则**：定时任务触发后，直接读取初始化标记和公司库。当天无财报→**静默不输出**；有财报未发布→**仅输出提示**，等待下一次调度
7. **★ v3.2 路径动态化 + 部署可选**：所有路径基于技能实际安装目录推断，不硬编码开发仓库路径；Cloudflare 部署必选（默认）+ GitHub 部署可选
8. **★ v3.2.1 路径分类规则**：区分"配置文件目录"（技能安装目录）和"输出/仓库目录"（用户工作空间）；输出目录初始化时由 LLM 询问工作根目录后填写为 `<工作根目录>/Output/earnings-reports`，不从技能安装路径推断
9. **★ v3.2.2 Python 探测优先级 + stub 跳过**：agent 内置 Python 优先于系统 PATH，跳过 Windows Store 0 字节 stub；探测到的绝对路径写入 `config.local.json` 的 `python_executable` 字段，子技能缓存 `.env-check-result.{platform}.json` 也写入 `py_executable`，所有后续脚本调用使用绝对路径不依赖 PATH

**与子技能的关系**：父技能**不改动子技能文件**，只读取/调用子技能脚本。子技能 v5.5.0+ 已统一 Python 单文件，父技能统一用 `python_executable` 绝对路径调用，无平台分支。

## 关键地址

★ v3.2.1 路径分类规则（核心改造）：

- **配置文件目录**（config.local.json / company-library.json / .parent-init-done.json / .env-check-result.\*.json）：基于"当前技能实际安装目录"推断（`Path(__file__).resolve().parent.parent`）
- **输出/仓库目录**（paths.output\_dir / paths.repo\_dir）：在**用户工作空间**，与技能安装目录无关，必须由用户在初始化时显式填写

| 项                | 值                                                                                                    | 目录类型     |
| ---------------- | ---------------------------------------------------------------------------------------------------- | -------- |
| 父技能目录            | **当前 SKILL.md 所在目录**（脚本通过 `Path(__file__).resolve().parent.parent` 动态获取）                             | 配置文件目录   |
| 子技能目录            | 同级 `earnings-report` 目录（即 `<父技能安装目录>/../earnings-report`），初始化时自动推断并写入 config.local.json              | 配置文件目录   |
| 公司库文件            | `{parent_skill_dir}/company-library.json`                                                            | 配置文件目录   |
| 父技能初始化标记         | `{parent_skill_dir}/.parent-init-done.json`（运行时生成，.gitignore 排除）                                     | 配置文件目录   |
| 子技能环境检测缓存        | `{child_skill_dir}/.env-check-result.{platform}.json`（运行时生成，.gitignore 排除，永久有效）                      | 配置文件目录   |
| **报告输出目录**       | `<工作根目录>/Output/earnings-reports`（★ 用户工作空间，初始化时由 LLM 询问用户并填写到 config.local.json 的 paths.output\_dir） | **输出目录** |
| **git 仓库目录**     | 同报告输出目录（`<工作根目录>/Output/earnings-reports`，需为 git 仓库根目录）                                              | **输出目录** |
| TRAE Schedule 工具 | 平台原生（cron 5 字段，最小 10 分钟粒度）                                                                           | —        |

**★ v3.2.1 路径推断规则**（区分两类目录）：

- **配置文件目录**：父技能脚本通过 `Path(__file__).resolve().parent.parent` 获取父技能安装目录；子技能目录默认推断为 `<父技能安装目录>/../earnings-report`（兄弟目录关系）
- **输出/仓库目录**：**不从技能安装路径推断**，初始化时 LLM 询问用户工作根目录，填写为 `<工作根目录>/Output/earnings-reports`；留空时脚本抛错提示用户配置
- 用户可在 config.local.json 中显式指定 `child_skill_dir`（配置目录）/ `paths.output_dir` / `paths.repo_dir`（输出目录）

## 触发条件

- **"请执行初始化"** / "初始化父技能" / "init parent"（★ 1 句话触发完整初始化流程）
- "添加公司 XXX 到财报库" / "入库 NVDA"
- "列出财报公司库" / "查看公司库"
- "检查今天有哪些公司要发财报" / "今日财报日历"
- "启动定时任务" / "暂停定时任务" / "修改调度间隔"
- "为 NVDA 生成财报报告"（手动触发，跳过就绪检查）
- "检查 NVDA 财报就绪状态"

## 自动化硬性约束

> 全程静默执行，仅在需要用户决策或异常时弹窗。所有弹窗用 `AskUserQuestion`，超时 ≥ 24 小时，不主动关闭。

1. 所有脚本仅 Python 跨平台版本，依赖 Python 3.8+ 标准库 + requests
2. 文件操作用 Python pathlib，禁止 os.system 调用 Copy-Item / cp 等高风险命令
3. **不改动子技能文件**，只读取/调用子技能脚本
4. 弹窗边界：初始化信息收集（4 项）、首次初始化异常、就绪检查异常
5. `config.local.json` 必须被 `.gitignore` 排除（脱敏）
6. 执行完毕清理资源（删除临时脚本、关闭 HTTP 服务器）
7. Trae 专有能力（Schedule、AskUserQuestion、Task 子代理、WebFetch）以 ★ 标注，其他 agent 可降级为系统 cron / 命令行 stdin / 串行执行 / Python requests
8. **★ v3.2.2 Python 调用全局规则**：本文档中所有 `python "{...}"` 命令模板中的 `python` 占位符，LLM 实际执行时**必须替换为** `config.local.json` 的 `python_executable` 字段绝对路径（初始化阶段 3 探测并缓存，优先 agent 内置 Python）。原因：Windows Store「应用执行别名」0 字节 stub 会拦截 `python` 命令导致退出码 9009。示例：`python "{parent_skill_dir}\scripts\library-manager.py" --action today` 实际执行为 `"<python_executable>" "{parent_skill_dir}\scripts\library-manager.py" --action today`

## 工作流程

### 阶段 -1：1 句话初始化（★ v3.0 核心改造：信息收集前置 + Python 自动安装）

**触发**：用户说"请执行初始化"、"初始化父技能"、"init parent"，或首次调用父技能、环境变更、用户主动要求初始化。

**★ v3.0 流程顺序（不可调整）**：

```
步骤 1：加载/创建父技能 config.local.json
    ↓
步骤 2：★ 信息收集前置（6 项用户交互一次性收集）
    │   2.0 ★ v3.2.1 收集工作根目录（输出目录定位，与技能安装目录无关）
    │   2.1 收集调度间隔（默认每12小时）
    │   2.2 收集 API Key 状态（已有/需注册）
    │   2.3 收集飞书 Webhook 状态（已有/需配置/跳过）
    │   2.4 收集公司库导入方案（默认美股7巨头）
    │   2.5 ★ v3.2 收集部署方案（默认仅 Cloudflare；可选追加 GitHub）
    ↓
步骤 3：★ Python 前提项检测 + LLM 自动安装
    │   3.1 检测 python --version
    │   3.2 不存在 → LLM 直接调用系统包管理器安装（无需用户确认）
    │       Windows: winget install Python.Python.3.12 --silent
    │       macOS:   brew install python@3.12
    │       Linux:   sudo apt-get install -y python3 python3-pip
    │   3.3 安装完成后再次检测，确认 Python 3.8+ 可用
    ↓
步骤 4：调用子技能环境检测脚本 check-and-install.py
    │   4.1 子脚本检测 9 项依赖（Node/Chrome/Git/gh/wrangler/PowerShell 7+/config/仓库）
    │   4.2 缺失依赖自动安装（国内 IP 启用镜像源）
    │   4.3 全部 PASS 后生成 .env-check-result.{platform}.json 缓存
    ↓
步骤 5：校验子技能缓存生成成功
    ↓
步骤 6：引导用户编辑 config.local.json（如步骤2标记需注册/配置）
    ↓
步骤 6.5：★ v3.2 Cloudflare API Token + GitHub 可选登录
    │   6.1 引导获取 Cloudflare API Token（必选，用于 Cloudflare Pages 部署）
    │   6.2 GitHub 登录（可选，步骤 2.5 判断）
    │       - 部署方案含 github → 执行 gh auth login
    │       - 仅 cloudflare → 跳过 GitHub 登录
    ↓
步骤 7：同步配置到子技能目录（去除父技能专有字段后复制）
    ↓
步骤 8：导入公司库（按步骤2.4选择执行）
    ↓
步骤 9：写入父技能初始化标记 .parent-init-done.json
    ↓
步骤 10：★ 自动创建定时任务（Schedule 工具）
    ↓
步骤 11：输出初始化完成摘要
```

#### 步骤 1：加载/创建父技能配置（★ v3.2.1 路径分类推断）

- **获取当前技能安装路径**：LLM 通过脚本所在目录推断 `parent_skill_dir`（即 SKILL.md 所在目录）
- 读取 `{parent_skill_dir}/config.local.json`
- 不存在则从 `config.example.json` 复制模板
- **★ v3.2.1 配置文件目录自动填充**（config.local.json 中配置字段为空时）：
  - `parent_skill_dir` = 当前 SKILL.md 所在目录（绝对路径）
  - `child_skill_dir` = `<parent_skill_dir>/../earnings-report`（兄弟目录，自动推断）
- **★ v3.2.1 输出目录需用户填写**（不从技能安装路径推断）：
  - `paths.output_dir` = `<工作根目录>/Output/earnings-reports`（LLM 询问用户工作根目录后填写）
  - `paths.repo_dir` = 同 `paths.output_dir`（git 仓库根目录）
  - ★ 输出目录与配置文件目录是不同概念：配置文件在技能安装目录，输出目录在用户工作空间
- 校验 `child_skill_dir` 目录存在；不存在则弹窗提示用户手动指定

#### 步骤 2：★ 信息收集前置（AskUserQuestion 弹窗，一次性收集 6 项）

**弹窗 0：★ v3.2.1 工作根目录收集（输出目录定位）**

| 选项               | 说明                                                        |
| ---------------- | --------------------------------------------------------- |
| **使用当前工作目录（推荐）** | 自动获取当前工作目录作为工作根目录，输出目录为 `<工作根目录>/Output/earnings-reports` |
| 手动输入工作根目录        | 用户打字输入绝对路径，如 `d:\TraeAutomaticTools` 或 `~/projects`       |

★ 此目录用于填写 config.local.json 的 `paths.output_dir` 和 `paths.repo_dir`，与技能安装目录无关。

**弹窗 1：调度间隔选择**

| 选项              | cron 表达式            | 说明                        |
| --------------- | ------------------- | ------------------------- |
| **每 12 小时（推荐）** | `0 0,12 * * *`      | 默认，平衡及时性和资源占用             |
| 每 6 小时          | `0 0,6,12,18 * * *` | 高频检查，适合财报季                |
| 每 24 小时         | `0 0 * * *`         | 每天凌晨检查一次                  |
| 每 10 分钟（最小粒度）   | `*/10 * * * *`      | 最高频检查（Trae Schedule 最小粒度） |

**弹窗 2：API Key 状态**

| 选项                                 | 说明                                                     |
| ---------------------------------- | ------------------------------------------------------ |
| 已有 Finnhub + Alpha Vantage API Key | 用户已有，引导编辑 config.local.json 填入                         |
| 需注册 Finnhub API Key                | 输出注册地址 <https://finnhub.io/register>                   |
| 需注册 Alpha Vantage API Key          | 输出注册地址 <https://www.alphavantage.support/free-api-key> |
| 需注册两个 API Key                      | 输出两个注册地址                                               |

**弹窗 3：飞书 Webhook 状态**

| 选项               | 说明                                 |
| ---------------- | ---------------------------------- |
| 已有飞书 Webhook URL | 用户已有，引导编辑 config.local.json 填入     |
| 需配置飞书群机器人        | 输出配置指引（飞书群 → 设置 → 群机器人 → 添加自定义机器人） |
| 跳过飞书推送           | 不配置 Webhook，子技能阶段 9 飞书推送将被跳过       |

**弹窗 4：公司库导入方案**

| 选项                | 说明                                     |
| ----------------- | -------------------------------------- |
| **导入美股 7 巨头（推荐）** | 预设 AAPL/MSFT/GOOGL/AMZN/NVDA/META/TSLA |
| 美股 7 巨头 + 阿里巴巴    | 预设 7 巨头 + BABA                         |
| 中概股龙头             | 预设 BABA/PDD/JD/BIDU/NIO/LI/XPEV        |
| 手动输入 ticker 列表    | 用户打字输入，如 "NVDA, TSLA, AMD"             |
| 跳过，稍后手动添加         | 不导入任何公司                                |

**弹窗 5：★ v3.2 部署方案选择**

| 选项                              | deployment.targets         | 说明                                          |
| ------------------------------- | -------------------------- | ------------------------------------------- |
| **仅 Cloudflare Pages（推荐默认）**    | `["cloudflare"]`           | 默认，Cloudflare 必选 + 飞书推送，无需 GitHub 登录 |
| Cloudflare + GitHub 双节点        | `["cloudflare", "github"]` | 追加 GitHub Pages 备用节点，需要 GitHub 登录 |

★ 部署方案约束：Cloudflare 始终必选（不可关闭）；GitHub 为可选项，默认不启用。

**收集完毕后**：将用户选择写入 `config.local.json`：

- `paths.output_dir` / `paths.repo_dir` ← 弹窗 0 工作根目录 + `/Output/earnings-reports`
- `schedule.cron` 字段 ← 弹窗 1 选择
- `deployment.targets` 字段 ← 弹窗 5 选择
- `deployment.github.enabled` ← 弹窗 5 含 github 时 true，否则 false
- 标记 API Key/Webhook/公司库/Cloudflare Token 的处理状态到内存变量，待步骤 6/6.5/8 执行

#### 步骤 3：★ Python 前提项检测 + LLM 自动安装（★ v3.2.2 agent 优先检测）

**★ v3.2.2 检测原则**：先检测当前 agent 是否内置 Python（沙箱环境，requests 等常用库已预装），有就标记后续直接使用 agent 内置路径；agent 没有再检测系统级别；系统没有就直接安装并校验 PATH。

**3.1 检测 agent 内置 Python（优先）**

LLM 执行以下命令探测 TRAE agent 内置 Python（覆盖 Windows / macOS / Linux）：

```bash
# Windows：TRAE 沙箱内置 Python
$agentPy = "$env:APPDATA\TRAE SOLO CN\ModularData\ai-agent\vm\tools\python\python.exe"
if (Test-Path $agentPy) { & $agentPy --version }

# macOS：TRAE 应用包内置 Python
ls "$HOME/Library/Application Support/TRAE SOLO CN/ModularData/ai-agent/vm/tools/python/bin/python3"

# Linux：TRAE 配置目录内置 Python
ls "$HOME/.config/TRAE SOLO CN/ModularData/ai-agent/vm/tools/python/bin/python3"
```

**3.2 agent 内置 Python 存在 → 标记并写入 config.local.json**

- 将绝对路径写入 `config.local.json` 的 `python_executable` 字段
- 后续所有脚本调用使用此绝对路径，不依赖 PATH
- 跳过步骤 3.3-3.7，直接进入步骤 4

**3.3 agent 无内置 Python → 检测系统 Python（跳过 Windows Store stub）**

LLM 执行命令检测系统 Python（★ 必须跳过 WindowsApps 目录下的 0 字节 stub）：

```bash
# Windows：先排除 WindowsApps stub，再尝试 py launcher / python3 / python
$pyCmds = @("py", "python3", "python")
foreach ($cmd in $pyCmds) {
    $found = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($found -and $found.Source -notlike "*WindowsApps*" -and (Get-Item $found.Source).Length -gt 0) {
        & $found.Source --version
        break
    }
}

# macOS / Linux：直接检测 python3
python3 --version 2>&1
```

**3.4 系统 Python 不存在 → LLM 直接安装（无需用户确认）**

按平台执行安装命令：

```bash
# Windows（winget，Windows 10 1709+ 自带）
winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements

# macOS（Homebrew）
brew install python@3.12

# Linux（Debian/Ubuntu）
sudo apt-get update && sudo apt-get install -y python3 python3-pip

# Linux（CentOS/RHEL）
sudo yum install -y python3 python3-pip
```

**3.5 ★ v3.2.2 安装后 PATH 校验（关键）**

安装完成后，winget/brew/apt 可能未立即刷新当前进程 PATH，必须主动校验：

```bash
# Windows：从注册表重新读取 Machine + User PATH 并刷新当前进程
$machinePath = [Environment]::GetEnvironmentVariable("PATH", "Machine")
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
$env:PATH = "$userPath;$machinePath;$env:PATH"

# 校验 Python 可用
python --version  # 或 py --version / python3 --version

# macOS / Linux：通过登录 shell 重新加载 PATH
exec bash -l  # 或重新打开终端
```

**3.6 标记系统 Python 路径**

- 探测到的系统 Python 绝对路径写入 `config.local.json` 的 `python_executable` 字段
- 后续所有脚本调用使用此绝对路径，避免 PATH 顺序问题

**3.7 安装 requests 库（Python 已存在或安装后）**

```bash
# 使用探测到的 python_executable 绝对路径
"<python_executable>" -m pip install requests --quiet
# 国内加速
"<python_executable>" -m pip install requests -i https://pypi.tuna.tsinghua.edu.cn/simple --quiet
```

**3.8 安装失败处理**

- winget/brew/apt 不存在或安装失败 → 弹窗提示用户手动安装 Python 3.8+，终止流程
- 安装成功但 PATH 校验失败 → LLM 从已知安装路径 fallback 查找（如 `C:\Program Files\Python\Python312\python.exe` / `/usr/local/bin/python3`）
- 找到 fallback 路径 → 写入 `python_executable` 字段，继续流程
- 仍找不到 → 弹窗提示用户重启终端后再次执行初始化

#### 步骤 4：调用子技能环境检测脚本（★ 不改动子技能文件，实际执行子技能脚本）

```bash
# ★ v3.2.2：使用步骤 3 探测到的 python_executable 绝对路径，不依赖 PATH
"<python_executable>" "{child_skill_dir}\scripts\check-and-install.py"
```

**可选参数**：

- `--china` 强制国内镜像
- `--fix-config` 创建 config.local.json 模板
- `--force-check` 强制重检（忽略缓存）

**子脚本执行内容**（父技能不关心细节，只看结果）：

- 并行检查 9 项依赖（Node.js 18+ / Chrome / Git / GitHub CLI / wrangler / PowerShell 7+ / config.local.json / git 仓库）
- ★ v5.5.1：`check_python()` 内部使用 `resolve_python_executable()` 优先探测 agent 内置 Python，跳过 Windows Store 0 字节 stub
- ★ v5.5.1：`save_cache()` 将探测到的 `py_executable` 绝对路径写入 `.env-check-result.{platform}.json` 缓存
- 缺失依赖自动安装（国内 IP 自动启用镜像源：npm 淘宝 / pip 清华 / Homebrew 清华 / apt 清华）
- 全部 PASS 后在子技能目录生成 `.env-check-result.{platform}.json` 缓存（下次秒级通过）

#### 步骤 5：校验子技能缓存生成成功

- 父技能读取 `{child_skill_dir}\.env-check-result.windows.json`（Windows）/ `.env-check-result.macos.json`（Mac）/ `.env-check-result.linux.json`（Linux）
- 确认 `all_pass=true`，提取 `check_time`
- ★ v3.2.2：提取缓存中的 `py_executable` 字段，若 `config.local.json` 的 `python_executable` 为空则回填
- 缓存不存在或 `all_pass=false` → 弹窗提示子技能脚本执行失败的具体原因

#### 步骤 6：引导用户编辑 config.local.json（如步骤 2 标记需注册/配置）

**判断逻辑**：

- 步骤 2.2 标记"需注册 API Key" → 输出注册地址，提示用户注册后编辑 `config.local.json`
- 步骤 2.3 标记"需配置 Webhook" → 输出飞书配置指引
- 步骤 2.2/2.3 标记"已有" → 跳过引导

**输出提示语**（仅在需要时）：

```
请编辑 {parent_skill_dir}\config.local.json 填入真实值：
- Finnhub API Key: https://finnhub.io/register
- Alpha Vantage API Key: https://www.alphavantage.support/free-api-key
- 飞书 Webhook URL: 飞书群 → 设置 → 群机器人 → 添加自定义机器人

填入后再次说"请执行初始化"完成配置同步。
```

**占位符检测**：

- 检测到 `config.local.json` 仍含 `<your-xxx>` 占位符 → 提示用户编辑，终止流程
- 占位符全部替换 → 进入步骤 6.5

#### 步骤 6.5：★ v3.2 Cloudflare API Token + GitHub 可选登录

**6.5.1 引导获取 Cloudflare API Token**（必选，deployment.targets 含 cloudflare 时执行）

**输出提示语**：

```
请前往 Cloudflare 获取 API Token：
1. 访问 https://dash.cloudflare.com/profile/api-tokens
2. 点击 "Create Token"
3. 选择 "Edit Cloudflare Workers" 模板（或自定义，需包含 Cloudflare Pages 编辑权限）
4. 复制生成的 Token 填入 config.local.json 的 deployment.cloudflare.api_token 字段
5. 同时填入 deployment.cloudflare.account_id（在 Cloudflare 仪表盘右侧可以看到）

填入后继续执行初始化。
```

**6.5.2 GitHub 登录**（可选，根据步骤 2.5 弹窗 5 的部署方案判断）

**判断逻辑**：

- `deployment.targets` 含 `"github"` → 执行 GitHub 登录
- `deployment.targets` 仅含 `"cloudflare"`（默认）→ **跳过 GitHub 登录**

**GitHub 登录命令**（含 github 时执行）：

```bash
# 检测 gh CLI 是否已登录
gh auth status 2>&1

# 未登录则执行登录（非交互式，使用 token）
# 方式1：通过环境变量 GH_TOKEN 登录（推荐）
# 方式2：通过 gh auth login --with-token < token.txt
gh auth login --with-token
```

**登录失败处理**：

- gh CLI 未安装 → 子技能环境检测脚本（步骤 4）应已安装
- 登录失败 → 弹窗提示用户手动执行 `gh auth login`，终止流程
- 登录成功 → 继续步骤 7

**★ 默认部署流程（仅 Cloudflare）**（deployment.targets = \["cloudflare"]）：

- Cloudflare 始终必选，无条件部署
- 跳过 GitHub 登录（默认）
- 子技能阶段 8 部署时仅执行 `wrangler pages deploy`，跳过 `git push`
- 飞书推送使用 Cloudflare Pages URL 作为报告主链接
- `.parent-init-done.json` 标记 `github_logged_in: false`

**★ 追加 GitHub 部署流程**（deployment.targets = \["cloudflare", "github"]）：

- Cloudflare 仍为必选主链接
- 追加执行 GitHub 登录（gh auth login）
- 子技能阶段 8 部署时先 `wrangler pages deploy`（必选），再 `git push`（可选追加）
- 飞书推送同时推送 Cloudflare 主链接 + GitHub 备用链接
- `.parent-init-done.json` 标记 `github_logged_in: true`

★ 部署方案约束：Cloudflare 始终必选（不可关闭）；GitHub 为可选项，默认不启用。

#### 步骤 7：同步配置到子技能目录（★ 仅初始化时复制一次，后续以子技能目录为准）

- 读取父技能 `config.local.json`
- **去除** `child_skill_dir` / `parent_skill_dir` / `schedule` 字段
- **保留** `deployment` 字段（子技能阶段 8 部署需要读取 deployment.targets 判断部署策略）
- 写入子技能目录 `config.local.json`（覆盖）
- 这样子技能脚本读取自身目录配置即可工作

#### 步骤 8：导入公司库（按步骤 2.4 选择执行）

**导入命令**：

```bash
# 导入美股 7 巨头
python "{parent_skill_dir}\scripts\library-manager.py" --action import-presets --preset "mag7"

# 导入美股 7 巨头 + 阿里巴巴
python "{parent_skill_dir}\scripts\library-manager.py" --action import-presets --tickers "AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA,BABA"

# 导入中概股龙头
python "{parent_skill_dir}\scripts\library-manager.py" --action import-presets --tickers "BABA,PDD,JD,BIDU,NIO,LI,XPEV"

# 导入自定义 ticker 列表
python "{parent_skill_dir}\scripts\library-manager.py" --action import-presets --tickers "NVDA,TSLA,AMD"
```

**美股 7 巨头预设**（Magnificent 7，内置常量）：

```python
# scripts/library-manager.py 内置常量
MAGNIFICENT_7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]
```

**批量入库逻辑**：解析 ticker → **并行调用** Finnhub `/stock/profile2` 拉 profile（★ Trae 用 Task 子代理并行）→ **并行查询**下次财报日期（Finnhub `/calendar/earnings`）→ 写入 `company-library.json`，所有公司 `last_report_status.status="waiting"` → 弹窗确认导入结果。

**已存在公司处理**：ticker 已存在 → 跳过不覆盖，输出 `skipped` 列表。

#### 步骤 9：写入父技能初始化标记

```json
// {parent_skill_dir}\.parent-init-done.json
{
  "initialized_at": "2026-07-28T10:00:00+08:00",
  "child_skill_dir": "<初始化时根据技能安装路径自动填充>",
  "child_skill_version": "v5.5.0",
  "env_check_passed": true,
  "env_check_cache": ".env-check-result.windows.json",
  "config_synced": true,
  "schedule_cron": "0 0,12 * * *",
  "schedule_created": true,
  "library_imported": true,
  "deployment": {
    "targets": ["cloudflare"],
    "cloudflare_configured": true,
    "github_logged_in": false
  }
}
```

#### 步骤 10：★ 自动创建定时任务（Schedule 工具）

通过 TRAE `Schedule` 工具创建定时任务：

```
action: create
name: "财报调度-12h"
cron_expression: "0 0,12 * * *"  # 按步骤 2.1 用户选择
timezone: "Asia/Shanghai"
message: |
  执行财报调度任务（父技能 earnings-report-orchestrator v3.2.1 静默调度）：
  
  ★ v3.1 静默规则：默认不输出任何内容，仅在特定情况输出（见下方规则）
  
  1. 读取 {parent_skill_dir}\.parent-init-done.json
     - 不存在或 env_check_passed=false → 弹窗提示"父技能未初始化，请说'请执行初始化'"，终止
     - 存在且通过 → 继续（不输出日志）
  
  2. 读取 {parent_skill_dir}\company-library.json
     - companies 为空 → ★ 静默终止，不输出任何内容
     - 有公司 → 继续（不输出日志）
  
  3. 执行：python "{parent_skill_dir}\scripts\library-manager.py" --action today
     ★★ 方案A：脚本内部获取真实系统北京时间，判断每个命中公司是否已过发布时间 ★★
     - 获取 next_earnings_date == today 的公司列表
     - 返回 current_time（真实系统北京时间）、companies[].released、all_released、dispatch_advice
     - ★ 列表为空（当天无财报更新）→ ★ 静默终止，不输出任何内容，等待下一次调度
     - ★ 列表非空但 all_released=false（存在未到发布时间的公司）→ ★ 静默终止，等待下一次调度
     - 列表非空且 all_released=true → 继续（仅对 released=true 的公司执行就绪检查）
  
  4. 对每个命中公司，并行执行 readiness-check.py（★ Trae 用 Task 子代理并行）
     - 就绪检查三项：财报已发布 + 电话会议已结束 + 媒体已更新
     - has_earnings_call=False 的公司跳过电话会议检查
  
  5. 根据就绪检查结果分流：
     - ★ 任一未通过（财报还未正式发布完成）
       → 仅输出："XX公司当日有财报更新计划，正式财报还没有发布，等待下一次调度执行"
       → 保持 status="waiting"，不调用子技能，等下一次调度
     - 三项全部 PASS（财报已正式发布完成）
       → 调用 dispatch-child-skill.py 触发子技能生成报告
  
  6. 生成完成后调用 library-manager.py update-status 改为 "completed"
   ★ status=completed 时自动拉取 Finnhub API 更新下一次财报日期：
   - 成功 → next_earnings_date 更新为下一次，next_earnings_status="waiting"
   - 失败 → next_earnings_date 保持空，next_earnings_status="waiting"（等待兜底补全）
   - 手动指定 → 加 --next-date/--next-time/--next-quarter 参数跳过 API 拉取
7. ★ 兜底任务：每次调度执行完毕后，调用 backfill-next 检查所有 next_earnings_date 为空的公司，重新拉取 Finnhub 补全

  8. 输出生成摘要（仅在报告生成成功时输出）
  
  ★ 静默规则总结：
  - 公司库为空 → 完全静默
  - 当天无财报更新 → 完全静默
  - 有财报未发布 → 仅输出提示语
  - 报告生成完成 → 输出生成摘要
  - 异常错误 → 输出错误信息
```

#### 步骤 11：输出初始化完成摘要

```
✅ 父技能初始化完成（v3.0）
- Python 版本：3.12.x
- 子技能环境检测：全部 PASS（缓存已生成）
- 配置同步：已复制到子技能目录
- 公司库导入：8 家公司（AAPL/MSFT/GOOGL/AMZN/NVDA/META/TSLA/BABA）
- 定时任务：每 12 小时执行（cron: 0 0,12 * * *）
- 下次调度时间：2026-07-29 00:00 北京时间

后续操作：
- "添加公司 XXX" 添加新公司
- "检查 NVDA 就绪状态" 手动触发就绪检查
- "为 NVDA 生成财报报告" 手动跳过就绪检查直接生成
```

#### 步骤 12：后续调用（★ v3.1 跳过初始化，直接读标记和公司库）

**初始化标记检测逻辑**：

```
触发调度任务
    ↓
读取 {parent_skill_dir}\.parent-init-done.json
    ↓
标记存在且 env_check_passed=true？
    ├─ 是 → ★ v3.1 直接读取公司库，进入调度执行流程（阶段 1.3）
    │       不重新执行环境检测、不弹窗、不输出初始化信息
    │       子技能被调用时读取自身缓存秒级通过
    │
    └─ 否 → 标记不存在或 env_check_passed=false
            → 弹窗提示"父技能未初始化，请说'请执行初始化'"
            → 终止本次调度，不执行任何后续操作
```

**`--force-init`** **参数**：用户主动说"重新初始化"时，强制重新执行阶段 -1 完整 11 步流程。

**★ v3.1 静默规则**：后续调用不输出任何"正在检查初始化标记"之类的日志，直接读标记 → 读公司库 → 进入调度逻辑。只有以下 3 种情况才输出：

1. 标记不存在/未通过 → 弹窗提示初始化
2. 有公司财报未发布 → 输出"XX公司当日有财报更新计划，正式财报还没有发布，等待下一次调度执行"
3. 报告生成完成 → 输出生成摘要

### 阶段 0：公司库管理

**触发词**："添加公司 XXX 到财报库"、"列出公司库"、"更新 NVDA 下次财报日期"、"移除 NVDA"

#### 0.1 公司库数据结构

`company-library.json`：

```json
{
  "version": "1.0",
  "last_updated": "2026-07-28T10:00:00+08:00",
  "companies": [
    {
      "ticker": "NVDA",
      "company_name_cn": "英伟达",
      "company_name_en": "NVIDIA Corporation",
      "currency": "USD",
      "exchange": "NASDAQ",
      "ir_url": "https://investor.nvidia.com/financial-info/quarterly-results/",
      "gelonghui_keyword": "英伟达",
      "futunn_keyword": "NVDA",
      "next_earnings_date": "2026-08-26",
      "next_earnings_time": "05:00",
      "next_quarter": "Q2 FY2026",
      "next_earnings_status": "waiting",
      "has_earnings_call": true,
      "last_report_status": {
        "quarter": "Q1 FY2026",
        "generated_at": "2026-05-30T14:00:00+08:00",
        "report_path": "reports/NVDA/nvidia-q1-fy2026-earnings.html",
        "status": "completed"
      },
      "enabled": true,
      "created_at": "2026-07-28T10:00:00+08:00"
    }
  ]
}
```

**状态流转**：

`last_report_status.status`（报告生成状态）：

- 新公司入库 → `"waiting"`（等待财报发布）
- 报告生成完成 → `"completed"`
- 就绪检查未通过 → 保持 `"waiting"`，等下一次调度
- 生成失败 → `"failed"`，弹窗提示

`next_earnings_status`（下一次财报处理状态）：

- 新公司入库 → `"waiting"`（待处理）
- 报告生成完成（update-status status=completed）→ 自动拉取 Finnhub API 更新下一次财报日期：
  - 成功 → `"waiting"`（next\_earnings\_date 已更新为下一次，等待发布）
  - 失败 → `"waiting"`（next\_earnings\_date 保持空，等待兜底任务补全）
- 兜底任务（backfill-next）→ 检查 `next_earnings_date` 为空且 `next_earnings_status == "waiting"` 的公司，重新拉取 Finnhub 补全
- `action_today` 过滤条件：`next_earnings_date == today` 且 `next_earnings_status == "waiting"`（空日期不会命中，不会重复触发）

#### 0.2 入库流程（library-manager.py）

1. 解析公司名/代码 → 调用 Finnhub `/stock/profile2` 拉 profile（名称/交易所/本位币/IR 网站）
2. **查询下一次财报公布日期**（三选一，按优先级）：
   - P0：Finnhub `/calendar/earnings` API（精确到日 + 时间，★ ADR 兼容：去掉 `.` 后缀匹配）
   - P1：公司 IR 页面 WebFetch（解析 earnings calendar 区块）
   - P2：格隆汇/富途搜索"NVDA 财报日期"补充
3. 写入 `company-library.json`，`last_report_status.status="waiting"`
4. **弹窗确认入库信息**（公司名/下次财报日期/IR 地址/本位币）

#### 0.3 命令示例（全部 Python 跨平台）

```bash
# 添加公司（自动拉取 profile + 下次财报日期）
python "{parent_skill_dir}\scripts\library-manager.py" --action add --ticker "NVDA"

# 列出所有公司
python "{parent_skill_dir}\scripts\library-manager.py" --action list

# 查看单个公司详情
python "{parent_skill_dir}\scripts\library-manager.py" --action show --ticker "NVDA"

# 更新下次财报日期
python "{parent_skill_dir}\scripts\library-manager.py" --action update-next --ticker "NVDA" --date "2026-08-26" --time "05:00"

# 更新报告状态（★ status=completed 时自动拉取 Finnhub 更新下一次财报日期，无需手动指定）
python "{parent_skill_dir}\scripts\library-manager.py" --action update-status --ticker "NVDA" --status "completed" --quarter "Q2 FY2026" --path "reports/NVDA/nvidia-q2-fy2026-earnings.html"

# 更新报告状态（手动指定下一次财报日期，跳过 Finnhub API 拉取）
python "{parent_skill_dir}\scripts\library-manager.py" --action update-status --ticker "NVDA" --status "completed" --quarter "Q2 FY2026" --path "reports/NVDA/nvidia-q2-fy2026-earnings.html" --next-date "2026-11-20" --next-time "05:00" --next-quarter "Q3 FY2026"

# ★ 兜底任务：检查所有 next_earnings_date 为空的公司，重新拉取 Finnhub 补全（每次调度完毕后执行）
python "{parent_skill_dir}\scripts\library-manager.py" --action backfill-next

# 移除公司
python "{parent_skill_dir}\scripts\library-manager.py" --action remove --ticker "NVDA"

# 导出今日待发布财报公司
python "{parent_skill_dir}\scripts\library-manager.py" --action today
```

### 阶段 1：定时任务调度

#### 1.1 调度间隔（步骤 2.1 已收集，写入 config.schedule.cron）

| 选项                | cron 表达式            | 说明                        |
| ----------------- | ------------------- | ------------------------- |
| 每 6 小时            | `0 0,6,12,18 * * *` | 高频检查，适合财报季                |
| **每 12 小时（推荐默认）** | `0 0,12 * * *`      | 默认，平衡及时性和资源占用             |
| 每 24 小时           | `0 0 * * *`         | 每天凌晨检查一次                  |
| 每 10 分钟（最小粒度）     | `*/10 * * * *`      | 最高频检查（Trae Schedule 最小粒度） |

**时区**：默认 `Asia/Shanghai`，可在 config 的 `schedule.timezone` 修改。

#### 1.2 创建定时任务（★ Trae 增强，步骤 10 已自动创建）

通过 `Schedule` 工具创建（详见步骤 10）。

#### 1.3 调度任务执行内容（★ v3.1 静默调度规则）

**★ v3.1 核心改造**：调度任务触发后，先读初始化标记，再读公司库，根据公司库状态决定输出行为。**默认静默**，仅在特定情况输出。

```
[定时任务触发]
  ↓
1. 读取 {parent_skill_dir}\.parent-init-done.json
   ├─ 不存在或 env_check_passed=false → 弹窗"父技能未初始化"，终止
   └─ 存在且通过 → 继续（不输出任何日志）
  ↓
2. 读取 {parent_skill_dir}\company-library.json
   ├─ companies 为空 → ★ 静默终止，不输出任何内容
   └─ 有公司 → 继续（不输出任何日志）
  ↓
3. 执行：python "{parent_skill_dir}\scripts\library-manager.py" --action today
   ★★ 方案A 核心改造：脚本内部获取真实系统北京时间，判断每个命中公司是否已过发布时间 ★★
   获取 next_earnings_date == today 的公司列表，并返回以下关键字段：
   - current_time：真实系统北京时间（UTC+8），LLM 必须以此时间为准
   - companies[].released：true=已过发布时间，false=未到发布时间
   - companies[].hours_until_release：距发布还有多少小时（负数表示已过）
   - companies[].release_status：发布状态描述
   - all_released：所有命中公司是否都已过发布时间
   - dispatch_advice：调度决策建议

   ├─ ★ 列表为空（当天无财报更新）
   │   → ★ 静默终止，不输出任何内容，等待下一次调度
   │   → 不弹窗、不打印"今日无公司发布财报"
   │
   ├─ ★ 列表非空但 all_released=false（存在未到发布时间的公司）
   │   → ★ 静默终止，不输出任何内容，等待下一次调度
   │   → LLM 不得依赖 topics.md 或用户输入的调度说明中的时间，必须以 current_time 为准
   │   → 示例：current_time=2026-07-29T09:47:00+08:00，next_earnings_time=20:00
   │            → hours_until_release=10.2 → released=false → 静默等待
   │
   └─ 列表非空且 all_released=true（所有命中公司都已过发布时间）
       ↓
4. 对每个命中公司（仅 released=true 的公司），并行执行 readiness-check.py（★ Trae 用 Task 子代理并行）
   就绪检查三项：
   ① 财报是否已发布（公司 IR 页面有最新季度财报链接）
   ② 电话会议是否已结束（IR 页面有 replay/audio 链接，或媒体报道"电话会议结束"）
   ③ 格隆汇/富途是否已发布财报分析文章（WebFetch 搜索关键词）
   ★ has_earnings_call=False 的公司跳过检查项 2，只查 1+3
  ↓
5. 根据就绪检查结果分流：
   ├─ ★ 任一未通过（财报还未正式发布完成）
   │   → 仅输出："XX公司当日有财报更新计划，正式财报还没有发布，等待下一次调度执行"
   │   → 保持 status="waiting"，不调用子技能，等下一次调度
   │   → 不弹窗、不输出详细检查日志
   │
   └─ 三项全部 PASS（财报已正式发布完成）
       → 调用 dispatch-child-skill.py 触发子技能生成报告
  ↓
6. 生成完成后调用 library-manager.py update-status 改为 "completed"
   ★ status=completed 时自动拉取 Finnhub API 更新下一次财报日期：
   - 成功 → next_earnings_date 更新为下一次，next_earnings_status="waiting"
   - 失败 → next_earnings_date 保持空，next_earnings_status="waiting"（等待兜底补全）
   - 手动指定 → 加 --next-date/--next-time/--next-quarter 参数跳过 API 拉取
7. ★ 兜底任务：每次调度执行完毕后，调用 backfill-next 检查所有 next_earnings_date 为空的公司，重新拉取 Finnhub 补全
  ↓
8. 输出生成摘要（仅在报告生成成功时输出）
```

**★ v3.1 静默规则总结**（★ v3.2.2 方案A 增加发布时间判断）：

| 场景                                   | 输出行为                                   |
| ------------------------------------ | -------------------------------------- |
| 初始化标记不存在/未通过                         | 弹窗提示初始化                                |
| 公司库为空                                | **完全静默**，不输出任何内容                       |
| 当天无财报更新（library-manager today 返回空）   | **完全静默**，不输出任何内容                       |
| ★ 当天有财报但未到发布时间（released=false，方案A新增） | **完全静默**，不输出任何内容，等待下一次调度               |
| 当天有财报且已过发布时间，但就绪检查未通过                | 仅输出"XX公司当日有财报更新计划，正式财报还没有发布，等待下一次调度执行" |
| 当天有财报且已过发布时间，就绪检查全 PASS              | 调用子技能生成报告，完成后输出生成摘要                    |

**★ 方案A 时间判断原则**：LLM 必须以 `library-manager.py --action today` 返回的 `current_time`（真实系统北京时间）为准，**不得依赖 topics.md 记忆或用户输入的调度说明中的时间**。若 `all_released=false`，静默终止，不执行就绪检查。

**设计原则**：定时任务在后台静默运行，避免频繁打扰用户。仅在需要用户关注时才输出（财报未发布提示、报告生成完成摘要、异常错误）。

### 阶段 2：就绪检查（readiness-check.py）

**触发**：定时任务命中今日财报公司、用户主动要求"检查 NVDA 就绪状态"。

```bash
python "{parent_skill_dir}\scripts\readiness-check.py" --ticker "NVDA" --quarter "Q2 FY2026"
```

**输出 JSON**：

```json
{
  "ticker": "NVDA",
  "quarter": "Q2 FY2026",
  "check_time": "2026-08-27T12:00:00+08:00",
  "earnings_released": {
    "passed": true,
    "evidence": "IR 页面存在 Q2 FY2026 财报 PDF 链接，发布时间 2026-08-26 21:00 UTC"
  },
  "earnings_call_ended": {
    "passed": true,
    "evidence": "IR 页面存在 audio replay 链接，标题包含 'Q2 FY2026 Earnings Call'"
  },
  "media_updated": {
    "gelonghui": {"passed": true, "url": "..."},
    "futunn": {"passed": true, "url": "..."}
  },
  "ready": true,
  "summary": "三项全部 PASS，可调用子技能生成报告"
}
```

**判定标准**（保守原则，避免误触发）：

| 检查项       | 判定标准                                                       | 数据源              |
| --------- | ---------------------------------------------------------- | ---------------- |
| ① 财报已发布   | IR 页面存在当前季度的 PDF/news 链接，且发布时间 ≥ 财报预定时间                    | WebFetch 公司 IR   |
| ② 电话会议已结束 | IR 页面有 audio replay / webcast replay 链接；或媒体报道"电话会议结束/会议要点" | WebFetch IR + 媒体 |
| ③ 媒体已更新   | 格隆汇**或**富途**至少一家**有标题包含 ticker+财报/业绩/Q{N} 的文章，且发布日期 = 当天   | WebFetch 格隆汇/富途  |

**保守策略**：三项全部 PASS 才触发子技能。任一未通过 → 等下一次调度。

**注意**：readiness-check.py 的 WebFetch 检查部分由 LLM 执行（脚本输出待检查 URL 列表 + 判定规则，LLM 用 WebFetch 完成实际抓取并回填结果），避免脚本直接抓取被反爬，LLM 可智能解析页面结构变化。

### 阶段 3：调用子技能生成报告（dispatch-child-skill.py）

**前置条件**：阶段 2 三项全 PASS，或用户手动触发跳过就绪检查。

```bash
# ★ v3.2.2：python 须替换为 config.local.json 的 python_executable 绝对路径（见自动化硬性约束第 8 条）
python "{parent_skill_dir}\scripts\dispatch-child-skill.py" --ticker "NVDA" --quarter "Q2 FY2026"
```

**脚本执行内容**（仅做参数封装和路径校验，实际执行由 LLM 编排）：

1. 从 `config.local.json` 读取 `child_skill_dir`、`output_dir`、`repo_dir`
2. 校验子技能目录存在、`.parent-init-done.json` 标记存在
3. ★ v3.2.2：调用 `resolve_python_executable()` 解析 Python 绝对路径（7 级优先级），输出 JSON 的 `script_invocation` 字段为绝对路径
4. 输出子技能脚本调用序列（JSON），LLM 按此序列执行子技能 9 阶段工作流（`command` 字段已用绝对路径，LLM 直接执行即可）

**★ v3.0 统一 Python 调用**（子技能 v5.5.0+ 已统一 Python 单文件，无平台分支）：

```
# 以下命令模板中的 python 须替换为 dispatch-child-skill.py 输出 JSON 的 script_invocation 字段值
阶段 1：python "{child_skill_dir}\scripts\fetch-data.py" --symbol "NVDA" --out-dir "{output_dir}\data\nvda-q2-fy2026"
        （fetch-data 完成后自动调用 parse-financial-data.py 输出 6 季度财务摘要）
阶段 1.5：并行 WebFetch 多站点（★ Trae 用 Task 子代理，公司 IR + 格隆汇 + 富途 + 汇通财经 + 华盛通）
阶段 2：数据整理与汇率换算（LLM 完成）
阶段 3：生成 sections JSON（LLM 按 templates/sections-reference.md 规范生成）
阶段 4：python "{child_skill_dir}\scripts\fill-template.py" --template-file "{child_skill_dir}\references\report-template.md" --sections-file "..." --output-file "..."
阶段 5：python "{child_skill_dir}\references\build-standalone.py" --source-dir "..."（构建后移动到 {repo_dir}\reports\{TICKER}\）
阶段 6：python "{child_skill_dir}\references\verify-headless.py" "{repo_dir}\reports\{TICKER}\{filename}.html"
阶段 7-9：并行执行清理 + 部署 + 飞书推送（★ Trae 用 Task 子代理）
         飞书推送：python "{child_skill_dir}\references\send-feishu.py" --report-file "..."
```

**完成后更新状态**（★ 自动拉取 Finnhub 更新下一次财报日期）：

```bash
python "{parent_skill_dir}\scripts\library-manager.py" --action update-status \
  --ticker "NVDA" --status "completed" \
  --quarter "Q2 FY2026" --path "reports/NVDA/nvidia-q2-fy2026-earnings.html"
# ★ 不传 --next-date 时自动拉取 Finnhub API，更新 next_earnings_date/next_quarter/next_earnings_status
```

**失败时回滚**：

```bash
python "{parent_skill_dir}\scripts\library-manager.py" --action update-status \
  --ticker "NVDA" --status "failed" --quarter "Q2 FY2026"
```

### 阶段 4：手动触发（跳过就绪检查）

**触发词**："为 NVDA 生成财报报告"

直接调用阶段 3 的 dispatch-child-skill.py，跳过阶段 2 就绪检查。适用于：

- 用户明确要求立即生成
- 财报已发布多日，定时任务未触发
- 测试子技能链路

## 配置继承关系

### config.local.json（父技能，被 .gitignore 排除）

```json
{
  "child_skill_dir": "",
  "parent_skill_dir": "",
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
  },
  "deployment": {
    "targets": ["cloudflare"],
    "cloudflare": {
      "api_token": "<your-cloudflare-api-token>",
      "account_id": "<your-cloudflare-account-id>",
      "project_name": "earnings-reports"
    },
    "github": {
      "enabled": false,
      "repo": ""
    }
  },
  "schedule": {
    "enabled": true,
    "cron": "0 0,12 * * *",
    "timezone": "Asia/Shanghai"
  }
}
```

★ v3.2.1 路径字段说明（区分两类目录）：

- `child_skill_dir` / `parent_skill_dir`：**配置文件目录**，留空时初始化自动推断（推荐留空）
- `paths.output_dir`：**输出目录**，在用户工作空间，留空时由初始化弹窗 0 询问工作根目录后填写为 `<工作根目录>/Output/earnings-reports`
- `paths.repo_dir`：**仓库目录**，同 `paths.output_dir`（git 仓库根目录）
- `deployment.targets`：Cloudflare 始终必选（不可关闭），GitHub 为可选项
  - `["cloudflare"]`：默认，仅 Cloudflare Pages（推荐）
  - `["cloudflare", "github"]`：Cloudflare + GitHub 双节点（可选追加 GitHub）
- `deployment.github.enabled`：targets 含 `github` 时为 true，否则 false（默认 false）

### 子技能配置同步

- 父技能初始化时（阶段 -1 步骤 7），将父技能配置**去除** `child_skill_dir` / `parent_skill_dir` / `schedule` 字段后，复制到子技能目录 `config.local.json`
- 后续以子技能目录下的 `config.local.json` 为准（子技能脚本读取自身目录）
- 父技能不主动同步配置变更，避免覆盖用户在子技能侧的修改

## 跨平台脚本规范

父技能所有脚本**仅 Python 版本**（不再写 .ps1 + .sh 双版本），依赖 Python 3.8+ 标准库（pathlib / json / argparse / urllib / datetime）+ `requests` 库。

| 脚本                                | 功能                                      |
| --------------------------------- | --------------------------------------- |
| `scripts/library-manager.py`      | 公司库 CRUD                                |
| `scripts/earnings-calendar.py`    | 财报日历拉取（Finnhub / IR）                    |
| `scripts/readiness-check.py`      | 就绪检查三项（HTTP 检查部分由 LLM 用 WebFetch 执行）    |
| `scripts/dispatch-child-skill.py` | 子技能调度器（参数封装 + 路径校验，★ v3.0 统一 Python 调用） |

**子技能脚本调用对应**（★ v3.0 统一 Python，无平台分支）：

| 功能       | 子技能脚本路径                           | 调用方式                                                               |
| -------- | --------------------------------- | ------------------------------------------------------------------ |
| 环境检查+安装  | `scripts/check-and-install.py`    | `python`                                                           |
| API 数据拉取 | `scripts/fetch-data.py`           | `python --symbol XXX --out-dir YYY`                                |
| 财务数据解析   | `scripts/parse-financial-data.py` | `python {data_dir}`                                                |
| 模板填充     | `scripts/fill-template.py`        | `python --template-file ... --sections-file ... --output-file ...` |
| 单文件构建    | `references/build-standalone.py`  | `python --source-dir ...`                                          |
| 无头验证     | `references/verify-headless.py`   | `python {report_path}`                                             |
| 飞书推送     | `references/send-feishu.py`       | `python --report-file ...`                                         |

## 目录结构

```
earnings-report-orchestrator-skill/
├── SKILL.md                          # 本文档
├── config.example.json               # 配置模板（提交到仓库）
├── config.local.json                 # 真实配置（.gitignore 排除）
├── company-library.json              # ★ 公司库（核心数据，可提交）
├── .parent-init-done.json            # 初始化标记（.gitignore 排除，运行时生成）
├── .gitignore                        # 排除敏感文件
├── scripts/                          # ★ 全部 Python 跨平台
│   ├── library-manager.py            # 公司库 CRUD
│   ├── earnings-calendar.py          # 财报日历拉取
│   ├── readiness-check.py            # 就绪检查三项
│   └── dispatch-child-skill.py       # 子技能调度器（★ v3.0 统一 Python 调用）
└── scheduler/
    └── cron-task-definition.md       # 定时任务调度规范
```

## 参考文件清单

| 文件                                  | 用途                                   |
| ----------------------------------- | ------------------------------------ |
| `SKILL.md`                          | 父技能主文档（本文档）                          |
| `config.example.json`               | 配置模板                                 |
| `company-library.json`              | 公司库数据                                |
| `scripts/library-manager.py`        | 公司库 CRUD（跨平台）                        |
| `scripts/earnings-calendar.py`      | 财报日历拉取（Finnhub / IR）                 |
| `scripts/readiness-check.py`        | 就绪检查三项（财报+电话会+媒体）                    |
| `scripts/dispatch-child-skill.py`   | 子技能调度器（★ v3.0 统一 Python 调用）          |
| `scheduler/cron-task-definition.md` | 定时任务调度规范（含 cron 表达式、message 模板、降级方案） |
| `.parent-init-done.json`            | 父技能初始化标记（运行时生成）                      |

<br />

