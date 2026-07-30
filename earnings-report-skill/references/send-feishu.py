#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨平台飞书群机器人推送脚本（v5.5.0，全中文交互卡片）

合并自原 send-feishu.ps1 + send-feishu.sh，单文件覆盖 Windows/Mac/Linux。

将财报报告摘要和外网链接以全中文交互卡片形式推送到飞书群机器人。
卡片包含：标题、摘要、核心数据字段、关键亮点、外网链接按钮。

Webhook URL 加载：config.local.json（统一入口）

用法：
  python send-feishu.py \
    --company-name "特斯拉" --quarter "2026 Q2" \
    --report-url "https://wxdpop.github.io/earnings-reports/TSLA/..." \
    --cf-pages-url "https://earnings-reports.pages.dev/TSLA/" \
    --repo-url "https://github.com/wxdpop/earnings-reports" \
    --revenue "255.06 亿美元" --revenue-yoy "+9.6%" \
    --net-income "14.78 亿美元" --net-income-yoy "-45.3%" \
    --gross-margin "14.6%" --margin-delta "-8.0 pts" \
    --key-metric "0.39 美元" --key-metric-label "每股收益(EPS)" --key-metric-delta "-45.8%" \
    --highlights "营收创历史同期新高\n交付量同比增长 14%" \
    --file-size "1180 KB" --card-color "red"
"""
import sys
import os
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

# ============================================================
# Windows stdout UTF-8 处理
# ============================================================
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass

# ============================================================
# 颜色
# ============================================================
COLOR_GREEN = '\033[32m'
COLOR_YELLOW = '\033[33m'
COLOR_RED = '\033[31m'
COLOR_GRAY = '\033[90m'
COLOR_RESET = '\033[0m'

if sys.platform == 'win32':
    os.system('')


def log(msg, level='INFO'):
    color = {
        'INFO': '',
        'OK': COLOR_GREEN,
        'WARN': COLOR_YELLOW,
        'ERROR': COLOR_RED,
        'GRAY': COLOR_GRAY,
    }.get(level, '')
    print(f"{color}{msg}{COLOR_RESET}")


# ============================================================
# 路径与配置加载
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent  # references/
SKILL_ROOT = SCRIPT_DIR.parent                # skill 根
CONFIG_FILE = SKILL_ROOT / 'config.local.json'


def load_webhook_url():
    """加载 Webhook URL：config.local.json（统一入口）"""
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
            feishu = cfg.get('feishu', {})
            if isinstance(feishu, dict):
                url = feishu.get('webhook_url', '')
                if url:
                    log('[config] 已加载 config.local.json', 'GRAY')
                    return url
        except Exception as e:
            log(f"config.local.json 解析失败: {e}", 'WARN')

    log('[错误] 未找到飞书 Webhook URL。请：', 'ERROR')
    log('  创建 config.local.json（参考 config.example.json，嵌套结构：feishu.webhook_url）', 'ERROR')
    return ''


# ============================================================
# 主流程
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='跨平台飞书群机器人推送脚本（全中文交互卡片）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--company-name', required=True, help='公司中文名（如"特斯拉"）')
    parser.add_argument('--quarter', required=True, help='季度标识（如"2026 Q2"）')
    parser.add_argument('--report-url', default='', help='报告 GitHub Pages URL（可选，仅 deployment.targets 含 github 时传入；不含时留空）')
    parser.add_argument('--cf-pages-url', required=True, help='Cloudflare Pages URL（必选，Cloudflare 始终部署）')
    parser.add_argument('--repo-url', default='', help='GitHub 仓库 URL（可选，仅 deployment.targets 含 github 时传入）')
    parser.add_argument('--revenue', required=True, help='营收数据')
    parser.add_argument('--revenue-yoy', required=True, help='营收同比（如"+9.6%"）')
    parser.add_argument('--net-income', required=True, help='净利润')
    parser.add_argument('--net-income-yoy', required=True, help='净利润同比')
    parser.add_argument('--gross-margin', required=True, help='毛利率')
    parser.add_argument('--margin-delta', required=True, help='毛利率变化')
    parser.add_argument('--key-metric', required=True, help='关键指标值')
    parser.add_argument('--key-metric-label', required=True, help='关键指标标签（如"每股收益(EPS)"）')
    parser.add_argument('--key-metric-delta', required=True, help='关键指标同比变化')
    parser.add_argument('--highlights', required=True, help='关键亮点（多行用 \\n 分隔）')
    parser.add_argument('--file-size', required=True, help='文件大小')
    parser.add_argument('--card-color', default='blue', help='卡片颜色: green/red/blue (默认 blue)')
    args = parser.parse_args()

    # 加载 Webhook URL
    webhook_url = load_webhook_url()
    if not webhook_url:
        sys.exit(1)

    company_name = args.company_name
    quarter = args.quarter
    report_url = args.report_url
    cf_pages_url = args.cf_pages_url
    repo_url = args.repo_url
    revenue = args.revenue
    revenue_yoy = args.revenue_yoy
    net_income = args.net_income
    net_income_yoy = args.net_income_yoy
    gross_margin = args.gross_margin
    margin_delta = args.margin_delta
    key_metric = args.key_metric
    key_metric_label = args.key_metric_label
    key_metric_delta = args.key_metric_delta
    highlights = args.highlights
    file_size = args.file_size
    card_color = args.card_color

    # 构建关键亮点（多行转 lark_md）
    highlights_lines = [f"- {line}" for line in highlights.split('\n')]
    highlights_md = '\n'.join(highlights_lines)

    # 动态构建 action 按钮（Cloudflare 始终为必选主按钮，GitHub 按 report_url 是否传入决定）
    action_buttons = []
    # Cloudflare 始终为主按钮（必选）
    action_buttons.append({
        'tag': 'button',
        'text': {'tag': 'plain_text', 'content': '查看报告（Cloudflare 镜像）'},
        'url': cf_pages_url,
        'type': 'primary',
    })
    # GitHub 备按钮（可选，仅当 report_url 传入时添加）
    if report_url:
        action_buttons.append({
            'tag': 'button',
            'text': {'tag': 'plain_text', 'content': '查看报告（GitHub 备用）'},
            'url': report_url,
            'type': 'default',
        })
    # 仓库按钮（可选，仅当 repo_url 传入时添加）
    if repo_url:
        action_buttons.append({
            'tag': 'button',
            'text': {'tag': 'plain_text', 'content': 'GitHub 仓库'},
            'url': repo_url,
            'type': 'default',
        })

    # 动态构建链接信息文本
    link_info = "**链接信息**\n"
    link_info += f"- 主链接（Cloudflare）：{cf_pages_url}\n"
    if report_url:
        link_info += f"- 备用链接（GitHub Pages）：{report_url}\n"
    if repo_url:
        link_info += f"- 仓库地址：{repo_url}\n"
    link_info += f"- 文件大小：{file_size}\n"
    if report_url:
        link_info += "- 托管方式：Cloudflare Pages（主）+ GitHub Pages（备）双节点（免费、永久、境内境外均可访问）"
    else:
        link_info += "- 托管方式：Cloudflare Pages（免费、永久、境内境外均可访问）"

    # 正文描述
    if report_url:
        deploy_desc = "报告已部署至 Cloudflare Pages（主，境内可访问）+ GitHub Pages（备）双节点，境内境外均可访问，点击下方按钮直接查看。"
        note_content = '主链接为 Cloudflare Pages，境内境外均可访问；GitHub 为备用链接。'
    else:
        deploy_desc = "报告已部署至 Cloudflare Pages，境内境外均可访问，点击下方按钮直接查看。"
        note_content = '主链接为 Cloudflare Pages，境内境外均可访问。'

    # 构建全中文交互卡片
    card = {
        'msg_type': 'interactive',
        'card': {
            'config': {'wide_screen_mode': True, 'enable_forward': True},
            'header': {
                'title': {'tag': 'plain_text', 'content': f"{company_name} {quarter} 财报分析报告"},
                'template': card_color,
            },
            'elements': [
                {
                    'tag': 'div',
                    'text': {
                        'tag': 'lark_md',
                        'content': f"**{company_name} {quarter} 财报深度分析报告已生成**\n\n{deploy_desc}",
                    },
                },
                {'tag': 'hr'},
                {'tag': 'action', 'actions': action_buttons},
                {'tag': 'hr'},
                {
                    'tag': 'div',
                    'fields': [
                        {'is_short': True, 'text': {'tag': 'lark_md', 'content': f"**营收**\n{revenue}（{revenue_yoy} YoY）"}},
                        {'is_short': True, 'text': {'tag': 'lark_md', 'content': f"**净利润**\n{net_income}（{net_income_yoy} YoY）"}},
                        {'is_short': True, 'text': {'tag': 'lark_md', 'content': f"**毛利率**\n{gross_margin}（{margin_delta}）"}},
                        {'is_short': True, 'text': {'tag': 'lark_md', 'content': f"**{key_metric_label}**\n{key_metric}（{key_metric_delta} YoY）"}},
                    ],
                },
                {'tag': 'hr'},
                {
                    'tag': 'div',
                    'text': {'tag': 'lark_md', 'content': f"**关键亮点**\n{highlights_md}"},
                },
                {'tag': 'hr'},
                {
                    'tag': 'div',
                    'text': {'tag': 'lark_md', 'content': link_info},
                },
                {
                    'tag': 'note',
                    'elements': [
                        {'tag': 'plain_text', 'content': note_content},
                    ],
                },
            ],
        },
    }

    # 序列化为 JSON（UTF-8，确保中文不乱码）
    json_str = json.dumps(card, ensure_ascii=False)
    json_bytes = json_str.encode('utf-8')

    # 发送请求（带重试）
    print("正在推送飞书消息...")
    max_retries = 2
    for i in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                webhook_url,
                data=json_bytes,
                headers={'Content-Type': 'application/json; charset=utf-8'},
                method='POST',
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode('utf-8')
                response = json.loads(body)
            if response.get('code') == 0:
                log(f"推送成功：{response.get('msg', '')}", 'OK')
                print(json.dumps(response, ensure_ascii=False, indent=2))
                sys.exit(0)
            else:
                log(f"推送失败（code={response.get('code')}）：{response.get('msg', '')}", 'ERROR')
                sys.exit(1)
        except urllib.error.URLError as e:
            log(f"第 {i} 次推送异常：{e}", 'WARN')
            if i < max_retries:
                import time
                time.sleep(3)
        except Exception as e:
            log(f"第 {i} 次推送异常：{e}", 'WARN')
            if i < max_retries:
                import time
                time.sleep(3)

    log(f"推送失败，已重试 {max_retries} 次", 'ERROR')
    sys.exit(1)


if __name__ == '__main__':
    main()
