# 定时任务调度规范（v3.1 静默调度）

## 概述

父技能通过 TRAE `Schedule` 工具创建定时任务，每 N 小时执行一次财报调度。任务触发时，TRAE 会启动新会话执行 `message` 中描述的工作流。

**★ v3.1 静默调度原则**：定时任务在后台静默运行，避免频繁打扰用户。仅在需要用户关注时才输出。

## cron 表达式

| 调度间隔 | cron 表达式 | 说明 |
|----------|-------------|------|
| 每 6 小时 | `0 0,6,12,18 * * *` | 高频检查，适合财报季 |
| **每 12 小时（默认）** | `0 0,12 * * *` | 平衡及时性和资源占用 |
| 每 24 小时 | `0 0 * * *` | 每天凌晨检查一次 |

**时区**：默认 `Asia/Shanghai`，可在 config.local.json 的 `schedule.timezone` 修改。

**约束**：
- TRAE Schedule 工具最小粒度为 10 分钟，不支持秒级
- cron 5 字段格式：`minute hour day-of-month month day-of-week`
- 不支持 `*/N` 跨日复杂调度（如"每 8 小时"需展开为 `0 0,8,16 * * *`）

## ★ v3.1 静默调度规则

| 场景 | 输出行为 |
|------|---------|
| 初始化标记不存在/未通过 | 弹窗提示初始化 |
| 公司库为空 | **完全静默**，不输出任何内容 |
| 当天无财报更新（library-manager today 返回空） | **完全静默**，不输出任何内容 |
| 当天有财报但未正式发布（就绪检查未通过） | 仅输出"XX公司当日有财报更新计划，正式财报还没有发布，等待下一次调度执行" |
| 当天有财报且已正式发布（就绪检查全 PASS） | 调用子技能生成报告，完成后输出生成摘要 |
| 异常错误 | 输出错误信息 |

## 调度任务 message 模板（★ v3.1 静默版）

创建定时任务时，`message` 字段必须包含完整执行指令（新会话无上下文）：

```
执行财报调度任务（父技能 earnings-report-orchestrator v3.1 静默调度）：

★ v3.1 静默规则：默认不输出任何内容，仅在特定情况输出（见下方规则）

【前置检查 - 静默】
1. 读取 {parent_skill_dir}\.parent-init-done.json
   - 不存在或 env_check_passed=false → 弹窗提示"父技能未初始化，请说'请执行初始化'"，终止
   - 存在且通过 → 继续（不输出日志）
2. 读取 {parent_skill_dir}\company-library.json
   - companies 为空 → ★ 静默终止，不输出任何内容
   - 有公司 → 继续（不输出日志）

【今日待发财报公司筛选 - 静默】
3. 执行：python "{parent_skill_dir}\scripts\library-manager.py" --action today
   - 获取 next_earnings_date == today 的公司列表
   - ★ 列表为空（当天无财报更新）→ ★ 静默终止，不输出任何内容，等待下一次调度
   - 列表非空 → 继续

【并行就绪检查】（★ Trae 用 Task 子代理并行）
4. 对每个命中公司，并行执行：
   python "{parent_skill_dir}\scripts\readiness-check.py" --ticker "{ticker}" --quarter "{next_quarter}"
   - 脚本输出待检查 URL 列表 + 判定规则
   - LLM 用 WebFetch 完成实际抓取，回填结果
   - 三项全 PASS → ready=true

【就绪检查结果分流 - ★ v3.1 静默规则】
5. 根据就绪检查结果分流：
   - ★ 任一未通过（财报还未正式发布完成）
     → 仅输出："XX公司当日有财报更新计划，正式财报还没有发布，等待下一次调度执行"
     → 保持 status="waiting"，不调用子技能，等下一次调度
     → 不弹窗、不输出详细检查日志
   - 三项全部 PASS（财报已正式发布完成）
     → 调用 dispatch-child-skill.py 触发子技能生成报告

【触发子技能生成报告】
6. 对 ready=true 的公司，执行：
   python "{parent_skill_dir}\scripts\dispatch-child-skill.py" --ticker "{ticker}" --quarter "{next_quarter}"
   - 脚本输出子技能脚本调用序列
   - LLM 按序列执行子技能 9 阶段工作流（fetch-data → fill-template → build-standalone → verify-headless → 部署 → 飞书推送）

【更新公司库状态】
7. 生成完成后执行：
   python "{parent_skill_dir}\scripts\library-manager.py" --action update-status \
     --ticker "{ticker}" --status "completed" \
     --quarter "{next_quarter}" --path "reports/{TICKER}/{company-slug}-{quarter}-earnings.html"

8. 输出生成摘要（仅在报告生成成功时输出）

★ 静默规则总结：
- 公司库为空 → 完全静默
- 当天无财报更新 → 完全静默
- 有财报未发布 → 仅输出提示语
- 报告生成完成 → 输出生成摘要
- 异常错误 → 输出错误信息

【异常处理】
- 子技能脚本执行失败 → 弹窗提示具体失败阶段和原因，status 改为 "failed"
- WebFetch 抓取失败 → 标记该项检查未通过，等下一次调度
- 配置文件缺失 → 弹窗提示，终止本次调度
```

## 创建定时任务（★ Trae 增强）

通过 `Schedule` 工具创建：

```
action: create
name: "财报调度-{interval}h"
cron_expression: "0 0,12 * * *"  # 按用户弹窗选择
timezone: "Asia/Shanghai"
message: <上述模板，替换 {parent_skill_dir} 为实际路径>
```

## 管理定时任务

| 操作 | Schedule action | 说明 |
|------|----------------|------|
| 创建 | `create` | 首次启动定时任务 |
| 暂停 | `pause` | 暂时停止调度（保留配置） |
| 恢复 | `resume` | 恢复已暂停的任务 |
| 删除 | `delete` | 彻底删除任务 |
| 查看列表 | `list` | 列出所有定时任务 |
| 查看详情 | `get` | 查看任务执行历史 |
| 立即触发 | `trigger` | 手动触发一次执行（测试用） |

## 修改调度间隔

1. 弹窗询问用户新的调度间隔（6/12/24 小时）
2. 调用 `Schedule action: list` 找到现有任务 ID
3. 调用 `Schedule action: update` 更新 `cron_expression`
4. 更新 `config.local.json` 的 `schedule.cron` 字段

## 其他 agent 降级方案

| Trae 能力 | 降级方案 |
|-----------|---------|
| Schedule 工具 | Linux/Mac: `crontab -e` 添加 cron 任务<br>Windows: 任务计划程序（schtasks） |
| Task 子代理 | 串行执行 readiness-check.py |
| WebFetch | Python requests + BeautifulSoup |
| AskUserQuestion | 命令行 stdin 交互 |

**降级示例（Linux crontab）**：

```bash
# 每 12 小时执行（0 点和 12 点）
0 0,12 * * * cd /path/to/parent_skill && python3 scripts/run-scheduler.py >> logs/scheduler.log 2>&1
```

**降级示例（Windows 任务计划程序）**：

```powershell
# 创建任务（每 12 小时触发）
schtasks /create /tn "EarningsScheduler" /tr "python D:\path\to\scripts\run-scheduler.py" /sc daily /st 00:00 /ri 720 /du 24:00
```
