# 注册和 Token 获取方式

> 本文档详细说明使用本技能所需的**全部 API Key、Webhook、Token、部署站点账号**的注册和获取流程，按站点分章节说明。
>
> - **必选**：Finnhub、Alpha Vantage、飞书 Webhook、Cloudflare（至少一项部署）
> - **可选**：GitHub（如选择「仅 Cloudflare 部署」可跳过）
> - **总览表**：见文末 [配置项总览](#配置项总览)

---

## 1. Finnhub（必选）

**用途**：公司 profile、分析师评级、财报日历等结构化数据。

| 项 | 值 |
|---|---|
| 官网 | https://finnhub.io/ |
| 注册地址 | https://finnhub.io/register |
| 控制台 | https://finnhub.io/dashboard |
| 免费套餐限制 | 60 次/分钟 |
| 配置字段 | `finnhub.api_key` |

### 1.1 注册账号

1. 访问 https://finnhub.io/register
2. 填写邮箱、密码、姓名，点击 **Sign up**
3. 邮箱验证（收到验证邮件后点击激活链接）

### 1.2 获取 API Key

1. 登录后访问 https://finnhub.io/dashboard
2. 在 Dashboard 顶部可见 **API Key**（32 位字符串，格式：`xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`）
3. 点击 API Key 旁的复制按钮，或手动选中复制

### 1.3 填入配置

将 API Key 填入 `config.local.json` 的 `finnhub.api_key` 字段：

```json
{
  "finnhub": {
    "api_key": "你的32位Finnhub API Key"
  }
}
```

> **提示**：免费套餐足够生成财报报告使用。如需更高频次调用，可在 Dashboard 升级付费套餐。

---

## 2. Alpha Vantage（必选）

**用途**：季度收入报表、资产负债表、现金流量表等三大报表数据。

| 项 | 值 |
|---|---|
| 官网 | https://www.alphavantage.co/ |
| 注册地址 | https://www.alphavantage.support/free-api-key |
| 文档 | https://www.alphavantage.co/documentation/ |
| 免费套餐限制 | 25 次/天 |
| 配置字段 | `alphavantage.api_key` |

### 2.1 注册账号

1. 访问 https://www.alphavantage.support/free-api-key
2. 填写表单：邮箱、姓名、用途说明
3. 提交后页面会直接显示你的 **API Key**（同时发送到邮箱）

### 2.2 获取 API Key

- 注册成功后，API Key 直接显示在确认页面
- 也可在邮箱中查收 Alpha Vantage 发送的欢迎邮件，邮件中包含 API Key
- 格式：16 位大写字符串（如 `XXXXXXXXXXXXXXXX`）

### 2.3 填入配置

将 API Key 填入 `config.local.json` 的 `alphavantage.api_key` 字段：

```json
{
  "alphavantage": {
    "api_key": "你的16位Alpha Vantage API Key"
  }
}
```

> **提示**：免费套餐 25 次/天，单次财报生成约消耗 3-5 次调用，足够每日生成 5+ 份报告。

---

## 3. 飞书群机器人 Webhook（必选）

**用途**：财报生成完成后向飞书群推送交互卡片消息。

| 项 | 值 |
|---|---|
| 飞书官网 | https://www.feishu.cn/ |
| 飞书 Web 端 | https://www.feishu.cn/messenger/ |
| 配置字段 | `feishu.webhook_url` |
| 操作平台 | **PC 端或 Web 端**（移动端不支持添加自定义机器人） |

### 3.1 创建飞书群聊

1. 登录飞书 PC 端或 Web 端 https://www.feishu.cn/messenger/
2. 点击左侧「消息」面板右上角的 **+** → **创建群组**
3. 填写群名称（如「财报报告助手」），添加群成员（可仅添加自己），点击 **创建**

### 3.2 添加自定义机器人

1. 进入群聊 → 点击右上角 **齿轮图标**（群设置）
2. 在群设置中找到 **群机器人** → 点击 **添加机器人**
3. 在机器人列表中选择 **自定义机器人**（Custom Bot）
4. 填写机器人名称（如「财报报告助手」）、描述（可选）、头像（可选）
5. 点击 **添加**

### 3.3 获取 Webhook URL

1. 添加成功后，弹窗会显示 **Webhook URL**，格式：
   ```
   https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   ```
2. **立即复制** Webhook URL（关闭弹窗后可在机器人详情中再次查看）
3. 可选：在「安全设置」中开启 **自定义关键词** 校验（如设置为「财报」），机器人仅响应包含该关键词的消息

### 3.4 填入配置

将 Webhook URL 填入 `config.local.json` 的 `feishu.webhook_url` 字段：

```json
{
  "feishu": {
    "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/你的-webhook-id"
  }
}
```

> **★ 安全提示**：Webhook URL 等同于密钥，**严禁提交到 git**。本仓库已通过 `.gitignore` 排除 `config.local.json`。
>
> **★ 跳过飞书推送**：如不需要飞书推送，可在父技能初始化时选择「跳过飞书推送」，或将 `feishu.webhook_url` 留空。

---

## 4. Cloudflare（必选，至少一项部署）

**用途**：Cloudflare Pages 部署财报 HTML 报告，境内访问稳定，作为主链接。

| 项 | 值 |
|---|---|
| 官网 | https://www.cloudflare.com/ |
| 注册地址 | https://dash.cloudflare.com/sign-up |
| 控制台 | https://dash.cloudflare.com/ |
| API Token 管理 | https://dash.cloudflare.com/profile/api-tokens |
| Pages 文档 | https://developers.cloudflare.com/pages/ |
| 配置字段 | `deployment.cloudflare.api_token`、`deployment.cloudflare.account_id`（project_name 运行时从 github.repo 仓库名推导） |

### 4.1 注册账号

1. 访问 https://dash.cloudflare.com/sign-up
2. 填写邮箱、密码，点击 **Sign Up**
3. 邮箱验证（收到验证邮件后点击激活链接）
4. 登录后进入 Cloudflare Dashboard

### 4.2 创建 Cloudflare Pages 项目

**方式一：通过 wrangler CLI 创建（推荐）**

```bash
# 安装 wrangler
npm i -g wrangler

# 登录 Cloudflare（浏览器授权）
npx wrangler login

# 创建 Pages 项目
npx wrangler pages project create earnings-reports --production-branch=main

# 验证认证状态
npx wrangler whoami
```

**方式二：通过 Web 界面创建**

1. 进入 Cloudflare Dashboard → 左侧 **Workers & Pages**
2. 点击 **Create application** → **Pages** → **Upload assets**
3. 项目名填 `earnings-reports`，Production branch 填 `main`
4. 点击 **Deploy**（首次部署可上传任意占位文件）

### 4.3 获取 Account ID

1. 进入 Cloudflare Dashboard 任意页面
2. 在右侧边栏的 **Account ID** 区域直接复制
   - 或访问 https://dash.cloudflare.com/ → 选中你的账户 → 右侧栏可见 **Account ID**
3. 格式：32 位十六进制字符串

### 4.4 获取 API Token

1. 访问 https://dash.cloudflare.com/profile/api-tokens
2. 点击 **Create Token**
3. 选择模板 **Edit Cloudflare Workers**（或自定义，需包含以下权限）：
   - **Account** → **Cloudflare Pages** → **Edit**
   - **Account** → **Account Settings** → **Read**
4. 点击 **Continue to summary** → **Create Token**
5. **立即复制** Token（仅显示一次，关闭页面后无法再查看）
   - 格式：40 位字母数字字符串（如 `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`）

### 4.5 填入配置

将 API Token 和 Account ID 填入 `config.local.json` 的 `deployment.cloudflare` 字段：

```json
{
  "deployment": {
    "targets": ["cloudflare"],
    "cloudflare": {
      "api_token": "你的40位Cloudflare API Token",
      "account_id": "你的32位Account ID"
    }
  }
}
```

> **★ 安全提示**：API Token 等同于密钥，**严禁提交到 git**。本仓库已通过 `.gitignore` 排除 `config.local.json`。
>
> **★ 默认仅 Cloudflare 部署**：Cloudflare 始终必选（默认）。如需 GitHub Pages 备份，可在初始化时选择「Cloudflare + GitHub 双节点」。

---

## 5. GitHub（可选）

**用途**：GitHub 仓库托管报告源文件 + GitHub Pages 部署备份链接。默认仅 Cloudflare 部署时可跳过本节。

| 项 | 值 |
|---|---|
| 官网 | https://github.com/ |
| 注册地址 | https://github.com/signup |
| GitHub CLI 文档 | https://cli.github.com/ |
| Personal Access Token | https://github.com/settings/tokens |
| 配置字段 | `deployment.github.enabled`、`deployment.github.repo` |

### 5.1 注册账号

1. 访问 https://github.com/signup
2. 填写用户名、邮箱、密码，点击 **Create account**
3. 邮箱验证（收到验证邮件后点击验证链接）
4. 完成个性化引导（可跳过）

### 5.2 创建 GitHub 仓库

1. 登录 GitHub，点击右上角 **+** → **New repository**
2. 仓库名称填 `earnings-reports`
3. 选择 **Public**（必须公开，GitHub Pages 免费版仅支持公开仓库）
4. 勾选 **Add a README file**（自动初始化仓库）
5. 点击 **Create repository**

### 5.3 启用 GitHub Pages

1. 进入仓库 **Settings** → 左侧 **Pages**
2. **Source** 选择 **Deploy from a branch**
3. 分支选 `main` / `(root)` → 点击 **Save**
4. 等待 1-2 分钟，访问 `https://{你的用户名}.github.io/earnings-reports/` 验证

### 5.4 安装 GitHub CLI

```bash
# Windows（winget）
winget install GitHub.cli

# macOS（Homebrew）
brew install gh

# Linux（Debian/Ubuntu）
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update && sudo apt install gh
```

安装后重开终端，验证：

```bash
gh --version
```

### 5.5 登录 GitHub CLI

**方式一：浏览器交互登录（推荐）**

```bash
gh auth login
```

按提示选择：
- **GitHub.com**
- **HTTPS**
- **Login with a web browser** → 复制一次性代码 → 浏览器粘贴授权

**方式二：Personal Access Token 登录（CI/自动化场景）**

1. 访问 https://github.com/settings/tokens → 点击 **Generate new token** → **Generate new token (classic)**
2. 设置 Note（如 `earnings-reports`）、Expiration（建议 90 天）
3. 勾选权限：`repo`（完整）、`workflow`、`read:org`
4. 点击 **Generate token** → **立即复制** Token（仅显示一次）
5. 通过命令行登录：

```bash
# 方式 1：环境变量（推荐）
# Windows PowerShell
$env:GH_TOKEN = "你的GitHub Token"
gh auth status

# Mac/Linux
export GH_TOKEN="你的GitHub Token"
gh auth status

# 方式 2：通过 stdin
echo "你的GitHub Token" | gh auth login --with-token
```

### 5.6 验证登录

```bash
gh auth status
# 应输出：Logged in to github.com as {用户名}
```

### 5.7 填入配置

将仓库信息填入 `config.local.json` 的 `deployment.github` 字段：

```json
{
  "deployment": {
    "targets": ["cloudflare", "github"],
    "github": {
      "enabled": true,
      "repo": "你的用户名/earnings-reports"
    }
  }
}
```

> **★ 安全提示**：Personal Access Token 等同于密码，**严禁提交到 git**。建议通过 `GH_TOKEN` 环境变量传入，不写入 config.local.json。

---

## 6. 克隆仓库到本地（部署前置）

完成上述注册后，将仓库克隆到本地（用于存放报告源文件并部署到 Cloudflare/GitHub Pages）：

```bash
# 替换 {your-username} 为你的 GitHub 用户名
git clone https://github.com/{your-username}/earnings-reports.git D:\TraeAutomaticTools\Output\earnings-reports-git
```

> **★ 提示**：克隆路径即父技能初始化弹窗 0 中询问的「工作根目录」下的 `Output/stock-financial-reports` 子目录。

---

## 配置项总览

### 完整 config.local.json 示例（父技能）

> ★ 默认仅启用 Cloudflare 部署。如需追加 GitHub Pages 备份，将 `targets` 改为 `["cloudflare", "github"]` 并设 `github.enabled=true`。

```json
{
  "child_skill_dir": "",
  "parent_skill_dir": "",
  "feishu": {
    "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  },
  "finnhub": {
    "api_key": "你的32位Finnhub API Key"
  },
  "alphavantage": {
    "api_key": "你的16位Alpha Vantage API Key"
  },
  "paths": {
    "output_dir": "D:/你的工作根目录/Output/stock-financial-reports",
    "repo_dir": "D:/你的工作根目录/Output/stock-financial-reports"
  },
  "deployment": {
    "targets": ["cloudflare"],
    "cloudflare": {
      "api_token": "你的40位Cloudflare API Token",
      "account_id": "你的32位Account ID"
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

### 配置项对照表

| 配置项 | 用途 | 是否必选 | 获取方式 | 是否提交 git |
|--------|------|---------|---------|-------------|
| `finnhub.api_key` | API 数据拉取 | 必选 | [Finnhub 注册](https://finnhub.io/register) | 否（.gitignore 排除） |
| `alphavantage.api_key` | API 数据拉取 | 必选 | [Alpha Vantage 注册](https://www.alphavantage.support/free-api-key) | 否（.gitignore 排除） |
| `feishu.webhook_url` | 飞书群推送 | 必选（可跳过） | 飞书群 → 群机器人 → 添加自定义机器人 | 否（.gitignore 排除） |
| `deployment.cloudflare.api_token` | Cloudflare Pages 部署 | 必选（与 GitHub 二选一） | [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens) | 否（.gitignore 排除） |
| `deployment.cloudflare.account_id` | Cloudflare 账户标识 | 必选（与 GitHub 二选一） | Cloudflare Dashboard 右侧栏 | 否（.gitignore 排除） |
| `deployment.github.enabled` | GitHub 部署开关 | 可选 | targets 含 github 时 true | 否（.gitignore 排除） |
| `deployment.github.repo` | GitHub 仓库地址 | 可选 | `用户名/仓库名` | 否（.gitignore 排除） |
| `paths.output_dir` | 报告输出目录 | 必选 | 父技能初始化时由 LLM 询问工作根目录后填写 | 否（.gitignore 排除） |
| `paths.repo_dir` | git 仓库目录 | 必选 | 同 `paths.output_dir` | 否（.gitignore 排除） |
| `config.example.json` | 配置模板 | — | 仓库已提供 | 是（已脱敏） |

### 配置加载优先级

1. **config.local.json**（唯一入口，不再支持环境变量）
2. 留空时脚本抛错提示用户配置（不再回退到环境变量）

### 部署方案组合

| 部署方案 | `deployment.targets` | 飞书推送链接来源 | 是否需要 GitHub 登录 |
|---------|---------------------|----------------|---------------------|
| 仅 Cloudflare Pages（推荐默认） | `["cloudflare"]` | Cloudflare 主链接 | 否 |
| Cloudflare + GitHub 双节点 | `["cloudflare", "github"]` | Cloudflare 主链接 + GitHub 备用 | 是 |

> **★ 约束**：Cloudflare 始终必选（不可关闭）；GitHub 为可选项，默认不启用。

---

## 常见问题

### Q1：Finnhub API Key 调用频率超限怎么办？

免费套餐 60 次/分钟。如生成多份报告时遇到 429 错误，可：
- 等待 1 分钟后重试
- 升级到付费套餐（$0.001/请求）
- 在父技能初始化时减小调度频率

### Q2：Alpha Vantage API Key 25 次/天不够用怎么办？

免费套餐 25 次/天，单次财报生成约消耗 3-5 次。如需更多：
- 升级到 Premium 套餐（$49.99/月起，75 次/分钟）
- 申请免费学术用途额度（[申请地址](https://www.alphavantage.co/support/)）

### Q3：飞书 Webhook 推送失败（StatusCode 非 0）？

- 检查 Webhook URL 是否正确（不要漏掉 `https://` 前缀）
- 检查是否开启了「自定义关键词」安全校验，机器人消息内容必须包含该关键词
- 检查机器人是否被群主移除（重新添加即可）

### Q4：Cloudflare Pages 部署失败？

- 检查 API Token 是否包含 `Cloudflare Pages: Edit` 权限
- 检查 Account ID 是否正确（不是 Zone ID）
- 检查 `wrangler` 是否已授权：`npx wrangler whoami`

### Q5：GitHub Pages 部署后访问 404？

- 检查仓库是否为 Public（GitHub Pages 免费版仅支持公开仓库）
- 检查 Settings → Pages → Source 是否已配置为 `main / (root)`
- 等待 1-2 分钟让 GitHub Actions 完成部署
- 检查报告路径是否为 `reports/{TICKER}/{filename}.html`

### Q6：可以同时使用多个飞书群推送吗？

当前仅支持单个 Webhook URL。如需多群推送，可在 `references/send-feishu.py` 中扩展循环调用逻辑。

---

## 参考链接

- **Finnhub 文档**：https://finnhub.io/docs/api
- **Alpha Vantage 文档**：https://www.alphavantage.co/documentation/
- **飞书开放平台**：https://open.feishu.cn/document/
- **Cloudflare Pages 文档**：https://developers.cloudflare.com/pages/
- **Cloudflare API Tokens**：https://dash.cloudflare.com/profile/api-tokens
- **GitHub CLI 文档**：https://cli.github.com/manual/
- **GitHub Personal Access Tokens**：https://github.com/settings/tokens
- **GitHub Pages 文档**：https://docs.github.com/en/pages
