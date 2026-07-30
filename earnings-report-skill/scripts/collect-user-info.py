#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collect-user-info.py — 用户信息收集主入口

将信息收集逻辑下沉到子技能侧，由子技能统一承载，
父技能和子技能均可代理调用此收集流程。

## 调用模式

### standalone 模式（子技能独立使用，不收集调度间隔）
    python collect-user-info.py --mode standalone

### proxy 模式（被父技能调用代理收集，含调度间隔）
    python collect-user-info.py --mode proxy --parent-config <父技能 config.local.json 路径>

## 两阶段调用协议

阶段 A（无 --answers 参数）：
    脚本输出弹窗规范 JSON 到 stdout（standalone 6 项 / proxy 7 项），
    LLM 按规范执行 AskUserQuestion，将答案组装为 answers.json 文件。

阶段 B（带 --answers <path> 参数）：
    脚本读取 answers.json，写入 config.local.json（standalone 写子技能；proxy 写父技能），
    输出最终状态 JSON 到 stdout，供父技能后续步骤消费。

## 退出码
    0 = 成功
    1 = 失败（参数错误/文件读写错误/答案格式错误）
"""

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

# ===== 路径常量 =====
SKILL_ROOT = Path(__file__).resolve().parent.parent  # earnings-report-skill/
CHILD_CONFIG = SKILL_ROOT / 'config.local.json'
CHILD_EXAMPLE = SKILL_ROOT / 'config.example.json'

# ===== 占位符检测清单（5 项） =====
PLACEHOLDERS = [
    ('feishu.webhook_url', '<your-feishu-webhook-url>'),
    ('finnhub.api_key', '<your-finnhub-api-key>'),
    ('alphavantage.api_key', '<your-alphavantage-api-key>'),
    ('deployment.cloudflare.api_token', '<your-cloudflare-api-token>'),
    ('deployment.cloudflare.account_id', '<your-cloudflare-account-id>'),
]

# ===== 公司库预设方案 =====
COMPANY_PRESETS = {
    'mag7': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA'],
    'mag7_baba': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BABA'],
    'china': ['BABA', 'PDD', 'JD', 'BIDU', 'NIO', 'LI', 'XPEV'],
}


def log(msg, level='INFO'):
    """日志输出到 stderr（不污染 stdout 的 JSON 契约）"""
    print(f'[{level}] {msg}', file=sys.stderr)


def load_config(config_path):
    """加载 config.local.json，不存在返回空 dict"""
    p = Path(config_path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        log(f'读取配置失败 {config_path}: {e}', 'ERROR')
        return {}


def save_config(config_path, config):
    """保存 config.local.json（UTF-8 无 BOM，2 空格缩进）"""
    p = Path(config_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(config, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    log(f'已写入配置: {config_path}')


def detect_placeholders(config):
    """检测 config 中未替换的占位符（5 项）"""
    remaining = []
    # 检测嵌套字段的占位符
    def get_nested(d, path):
        keys = path.split('.')
        cur = d
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                return None
            cur = cur[k]
        return cur

    for field_path, placeholder in PLACEHOLDERS:
        val = get_nested(config, field_path)
        if isinstance(val, str) and placeholder in val:
            remaining.append(placeholder)
    return remaining


def check_gh_auth_status():
    """检测 gh CLI 登录状态（不执行登录，仅检查）"""
    try:
        result = subprocess.run(
            ['gh', 'auth', 'status'],
            capture_output=True, text=True, timeout=10
        )
        # gh auth status 成功时退出码为 0
        return 'logged_in' if result.returncode == 0 else 'not_logged_in'
    except FileNotFoundError:
        return 'gh_not_installed'
    except subprocess.TimeoutExpired:
        return 'check_timeout'
    except Exception:
        return 'check_failed'


def get_gh_username():
    """获取当前 gh CLI 登录的用户名（不执行登录，仅获取）"""
    try:
        result = subprocess.run(
            ['gh', 'api', 'user', '--jq', '.login'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return ''
    except Exception:
        return ''


def check_github_repo(repo_full):
    """
    检查 GitHub 仓库是否存在
    返回: exists / not_exists / gh_not_installed / not_logged_in / error
    """
    if not repo_full or '/' not in repo_full:
        # 仅仓库名无用户名前缀时无法检查，返回 not_logged_in（需登录后补全再检查）
        return 'not_logged_in'
    try:
        result = subprocess.run(
            ['gh', 'repo', 'view', repo_full, '--json', 'name'],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            return 'exists'
        # 退出码非 0，检查是否是仓库不存在
        if 'Could not resolve' in result.stderr or 'not found' in result.stderr.lower():
            return 'not_exists'
        return 'error'
    except FileNotFoundError:
        return 'gh_not_installed'
    except subprocess.TimeoutExpired:
        return 'error'
    except Exception:
        return 'error'


def build_dialogs_spec(mode):
    """阶段 A：构建弹窗规范 JSON（standalone 6 项 / proxy 7 项）"""
    dialogs = [
        {
            'dialog_id': 'dialog_0_workroot',
            'collect_item': '输出根目录（盘符+文件夹）',
            'field_mapping': ['paths.output_root'],
            'description': '用户输入输出根目录（盘符+文件夹），代码运行时拼接为 仓库目录 = output_root/Output/项目名。与技能安装目录无关',
            'options': [
                {'label': '手动输入输出根目录', 'value': '__user_input__', 'hint': '用户打字输入绝对路径（盘符+文件夹），如 d:\\TraeAutomaticTools 或 ~/projects'}
            ],
            'user_input_required': True,
            'input_hint': '请输入输出根目录（盘符+文件夹，如 D:\\TraeAutomaticTools）',
            'value_transform': '用户输入值直接写入 paths.output_root，不再拼接 Output/项目名（由代码运行时推导）',
            'constraint': '路径必须为绝对路径，不含相对路径符号'
        },
        {
            'dialog_id': 'dialog_1_schedule',
            'collect_item': '调度间隔选择',
            'field_mapping': ['schedule.cron'],
            'options': [
                {'label': '每 12 小时（推荐）', 'value': '0 0,12 * * *'},
                {'label': '每 6 小时', 'value': '0 0,6,12,18 * * *'},
                {'label': '每 24 小时', 'value': '0 0 * * *'},
                {'label': '每 10 分钟（最小粒度）', 'value': '*/10 * * * *'}
            ]
        },
        {
            'dialog_id': 'dialog_2_api_key',
            'collect_item': 'API Key 状态',
            'field_mapping': ['finnhub.api_key', 'alphavantage.api_key'],
            'options': [
                {'label': '需注册 Finnhub API Key', 'value': 'need_finnhub', 'hint': 'https://finnhub.io/register'},
                {'label': '需注册 Alpha Vantage API Key', 'value': 'need_alphavantage', 'hint': 'https://www.alphavantage.support/free-api-key'},
                {'label': '需注册两个 API Key', 'value': 'need_both', 'hint': 'https://finnhub.io/register 和 https://www.alphavantage.support/free-api-key'},
                {'label': '已有 Finnhub + Alpha Vantage API Key', 'value': 'have_both', 'user_input_required': True, 'input_hint': '请输入两个 API Key，逗号分隔，顺序：Finnhub,Alpha Vantage（如 d9hgjd9r01qhv00m6u8g,W94IQXQNUM78UAA1）'}
            ]
        },
        {
            'dialog_id': 'dialog_3_feishu',
            'collect_item': '飞书 Webhook 状态',
            'field_mapping': ['feishu.webhook_url'],
            'options': [
                {'label': '已有飞书 Webhook URL', 'value': 'have_webhook'},
                {'label': '需配置飞书群机器人', 'value': 'need_config', 'hint': '飞书群 → 设置 → 群机器人 → 添加自定义机器人'},
                {'label': '跳过飞书推送', 'value': 'skip', 'hint': '不配置 Webhook，子技能阶段 9 飞书推送将被跳过'}
            ]
        },
        {
            'dialog_id': 'dialog_4_company_library',
            'collect_item': '公司库导入方案',
            'field_mapping': ['__company_library_choice__'],
            'options': [
                {'label': '导入美股 7 巨头（推荐）', 'value': 'mag7', 'tickers': COMPANY_PRESETS['mag7']},
                {'label': '美股 7 巨头 + 阿里巴巴', 'value': 'mag7_baba', 'tickers': COMPANY_PRESETS['mag7_baba']},
                {'label': '中概股龙头', 'value': 'china', 'tickers': COMPANY_PRESETS['china']},
                {'label': '手动输入 ticker 列表', 'value': 'custom', 'hint': '用户打字输入，如 "NVDA, TSLA, AMD"'},
                {'label': '跳过，稍后手动添加', 'value': 'skip', 'tickers': []}
            ]
        },
        {
            'dialog_id': 'dialog_5_deployment',
            'collect_item': '部署方案选择',
            'field_mapping': ['deployment.targets', 'deployment.github.enabled'],
            'options': [
                {'label': '仅 Cloudflare Pages（推荐默认）', 'value': 'cloudflare_only', 'targets': ['cloudflare'], 'github_enabled': False},
                {'label': 'Cloudflare + GitHub 双节点', 'value': 'cloudflare_github', 'targets': ['cloudflare', 'github'], 'github_enabled': True}
            ],
            'constraint': 'Cloudflare 始终必选（不可关闭）；GitHub 为可选项，默认不启用'
        },
        {
            'dialog_id': 'dialog_6_project_name',
            'collect_item': '项目名称',
            'field_mapping': ['deployment.github.repo'],
            'description': '用于 GitHub 仓库名 + Cloudflare Pages 项目名（wrangler --project-name）。无论哪种部署方案都需收集，因为仓库目录推导依赖项目名',
            'options': [
                {'label': '使用默认项目名称 stock-financial-reports（推荐）', 'value': 'stock-financial-reports'},
                {'label': '手动输入项目名称', 'value': '__user_input__', 'hint': '仅允许小写字母、数字、连字符，如 my-earnings-reports'}
            ],
            'validation': {'pattern': '^[a-z0-9][a-z0-9-]*$', 'description': '必须全英文小写字母+数字+连字符，不以连字符开头'},
            'constraint': '同时作为 GitHub 仓库名 和 wrangler --project-name 的值；gh 登录时补全为 用户名/项目名'
        }
    ]
    # standalone 模式不收集调度间隔（子技能无定时调度任务环节）
    if mode == 'standalone':
        dialogs = [d for d in dialogs if d['dialog_id'] != 'dialog_1_schedule']
    return {
        'status': 'collect_required',
        'mode': mode,
        'dialog_count': len(dialogs),
        'dialogs': dialogs
    }


def apply_answers(config, answers, mode):
    """阶段 B：将用户答案应用到 config 字典"""
    import re

    # 弹窗 0：输出根目录（用户输入，直接写入 paths.output_root）
    ans0 = answers.get('dialog_0_workroot', {})
    choice0 = ans0.get('choice', '__user_input__')
    if choice0 == '__user_input__':
        output_root = ans0.get('user_input', '').strip()
    else:
        output_root = choice0 or ''
    config.setdefault('paths', {})
    config['paths']['output_root'] = output_root
    # 删除旧字段（兼容旧 config 迁移）
    config['paths'].pop('output_dir', None)
    config['paths'].pop('repo_dir', None)

    # 弹窗 1：调度间隔（仅 proxy 模式写入 schedule，因为 schedule 是父技能专有字段）
    if mode == 'proxy':
        ans1 = answers.get('dialog_1_schedule', {})
        cron = ans1.get('choice', '0 0,12 * * *')
        config.setdefault('schedule', {})
        config['schedule']['enabled'] = True
        config['schedule']['cron'] = cron
        config['schedule']['timezone'] = 'Asia/Shanghai'

    # 弹窗 2：API Key
    ans2 = answers.get('dialog_2_api_key', {})
    choice2 = ans2.get('choice', '')
    config.setdefault('finnhub', {})
    config.setdefault('alphavantage', {})
    if choice2 == 'have_both':
        # 用户已有 API Key，从输入框解析（格式：Finnhub_key,Alpha_Vantage_key）
        user_input = ans2.get('user_input', '')
        # 支持中英文逗号
        parts = [p.strip() for p in re.split(r'[,，]', user_input) if p.strip()]
        if len(parts) >= 2:
            config['finnhub']['api_key'] = parts[0]
            config['alphavantage']['api_key'] = parts[1]
        else:
            # 解析失败，保留占位符
            if config['finnhub'].get('api_key', '') in ('', '<your-finnhub-api-key>'):
                config['finnhub']['api_key'] = '<your-finnhub-api-key>'
            if config['alphavantage'].get('api_key', '') in ('', '<your-alphavantage-api-key>'):
                config['alphavantage']['api_key'] = '<your-alphavantage-api-key>'
    else:
        # 其他选项：确保占位符存在
        if config['finnhub'].get('api_key', '') in ('', '<your-finnhub-api-key>'):
            config['finnhub']['api_key'] = '<your-finnhub-api-key>'
        if config['alphavantage'].get('api_key', '') in ('', '<your-alphavantage-api-key>'):
            config['alphavantage']['api_key'] = '<your-alphavantage-api-key>'

    # 弹窗 3：飞书 Webhook
    ans3 = answers.get('dialog_3_feishu', {})
    choice3 = ans3.get('choice', '')
    if choice3 != 'skip':
        config.setdefault('feishu', {})
        if config['feishu'].get('webhook_url', '') == '':
            config['feishu']['webhook_url'] = '<your-feishu-webhook-url>'

    # 弹窗 4：公司库导入方案（不写入 config，仅记录选择，供父技能步骤 8 消费）
    ans4 = answers.get('dialog_4_company_library', {})
    choice4 = ans4.get('choice', 'skip')
    # 自定义 ticker 列表
    if choice4 == 'custom':
        custom_tickers = ans4.get('user_input', '')
        # 解析 "NVDA, TSLA, AMD" 为列表
        company_library_tickers = [t.strip().upper() for t in custom_tickers.split(',') if t.strip()]
    else:
        company_library_tickers = COMPANY_PRESETS.get(choice4, [])

    # 弹窗 5：部署方案
    ans5 = answers.get('dialog_5_deployment', {})
    choice5 = ans5.get('choice', 'cloudflare_only')
    if choice5 == 'cloudflare_github':
        targets = ['cloudflare', 'github']
        github_enabled = True
    else:
        targets = ['cloudflare']
        github_enabled = False

    # 弹窗 6：项目名称（始终收集，无论哪种部署方案）
    ans6 = answers.get('dialog_6_project_name', {})
    choice6 = ans6.get('choice', 'stock-financial-reports')
    if choice6 == '__user_input__':
        project_name = ans6.get('user_input', 'stock-financial-reports').strip()
    else:
        project_name = choice6 or 'stock-financial-reports'
    # 项目名正则校验：全英文小写+数字+连字符，不以连字符开头
    if not re.match(r'^[a-z0-9][a-z0-9-]*$', project_name):
        # 校验失败，回退默认值
        project_name = 'stock-financial-reports'
    github_repo_name = project_name

    # 通过 gh api user 获取用户名补全为 用户名/项目名
    gh_user = get_gh_username()
    if gh_user:
        github_repo_full = f"{gh_user}/{project_name}"
    else:
        # gh 未登录或不可用，仅写入项目名，步骤 6.5.2 登录后由父技能补全
        github_repo_full = project_name

    config.setdefault('deployment', {})
    config['deployment']['targets'] = targets
    config['deployment'].setdefault('cloudflare', {})
    if config['deployment']['cloudflare'].get('api_token', '') == '':
        config['deployment']['cloudflare']['api_token'] = '<your-cloudflare-api-token>'
    if config['deployment']['cloudflare'].get('account_id', '') == '':
        config['deployment']['cloudflare']['account_id'] = '<your-cloudflare-account-id>'
    # wrangler --project-name 运行时从 deployment.github.repo 提取项目名（取 / 后的部分）
    config['deployment'].setdefault('github', {})
    config['deployment']['github']['enabled'] = github_enabled
    config['deployment']['github']['repo'] = github_repo_full

    return {
        'company_library_choice': choice4,
        'company_library_tickers': company_library_tickers,
        'schedule_cron': config.get('schedule', {}).get('cron', ''),
        'schedule_timezone': config.get('schedule', {}).get('timezone', 'Asia/Shanghai'),
        'deployment_targets': targets,
        'github_repo_name': github_repo_name,
        'github_repo_full': github_repo_full,
    }


def build_final_status(config, mode, collected_meta):
    """阶段 B：构建最终状态 JSON"""
    placeholders = detect_placeholders(config)
    targets = config.get('deployment', {}).get('targets', [])
    github_required = 'github' in targets
    gh_status = check_gh_auth_status() if github_required else 'not_required'

    # GitHub 仓库检查（仅当 github 部署启用时）
    github_repo_name = collected_meta.get('github_repo_name', '')
    github_repo_full = collected_meta.get('github_repo_full', '')
    if github_required:
        github_repo_status = check_github_repo(github_repo_full)
        # 推导 github_repo_action
        if github_repo_status == 'exists':
            # 仓库存在，需检查本地仓库目录是否已存在且非空（决定 clone 还是 pull）
            # 仓库目录 = output_root/Output/项目名（代码推导，不再从 paths.repo_dir 读取）
            output_root = config.get('paths', {}).get('output_root', '')
            project_name = github_repo_full.split('/')[-1] if github_repo_full else ''
            repo_root = str(Path(output_root) / 'Output' / project_name) if output_root and project_name else ''
            if repo_root and Path(repo_root).exists() and any(Path(repo_root).iterdir()):
                github_repo_action = 'pull'
            else:
                github_repo_action = 'clone'
        elif github_repo_status == 'not_exists':
            github_repo_action = 'init'
        elif github_repo_status == 'not_logged_in':
            github_repo_action = 'pending'  # 需登录后重新检查
        else:
            github_repo_action = 'pending'  # gh_not_installed / error，需处理后重新检查
    else:
        github_repo_status = 'skip'
        github_repo_action = 'skip'

    # 判断 cloudflare 是否已配置（无占位符）
    cf = config.get('deployment', {}).get('cloudflare', {})
    cloudflare_configured = (
        cf.get('api_token', '') not in ('', '<your-cloudflare-api-token>') and
        cf.get('account_id', '') not in ('', '<your-cloudflare-account-id>')
    )

    # 构建 next_actions
    next_actions = []
    for ph in placeholders:
        if 'finnhub' in ph:
            next_actions.append({'action': 'edit_config', 'fields': ['finnhub.api_key'], 'hint': 'https://finnhub.io/register'})
        elif 'alphavantage' in ph:
            next_actions.append({'action': 'edit_config', 'fields': ['alphavantage.api_key'], 'hint': 'https://www.alphavantage.support/free-api-key'})
        elif 'feishu' in ph:
            next_actions.append({'action': 'edit_config', 'fields': ['feishu.webhook_url'], 'hint': '飞书群 → 设置 → 群机器人 → 添加自定义机器人'})
        elif 'cloudflare-api-token' in ph:
            next_actions.append({'action': 'edit_config', 'fields': ['deployment.cloudflare.api_token'], 'hint': 'https://dash.cloudflare.com/profile/api-tokens'})
        elif 'cloudflare-account-id' in ph:
            next_actions.append({'action': 'edit_config', 'fields': ['deployment.cloudflare.account_id'], 'hint': 'Cloudflare Dashboard 右侧栏'})

    if github_required and gh_status == 'not_logged_in':
        next_actions.append({'action': 'gh_auth_login', 'reason': 'deployment.targets 含 github 且 gh auth status 未登录'})
    elif github_required and gh_status == 'gh_not_installed':
        next_actions.append({'action': 'install_gh', 'reason': 'deployment.targets 含 github 但 gh CLI 未安装'})

    # 状态判定
    if not placeholders and (not github_required or gh_status == 'logged_in'):
        status = 'ok'
    elif placeholders:
        status = 'warn'
    else:
        status = 'warn'

    return {
        'status': status,
        'mode': mode,
        'collected_fields': collected_meta.get('collected_fields', []),
        'company_library_choice': collected_meta.get('company_library_choice', 'skip'),
        'company_library_tickers': collected_meta.get('company_library_tickers', []),
        'schedule_cron': collected_meta.get('schedule_cron', ''),
        'schedule_timezone': collected_meta.get('schedule_timezone', 'Asia/Shanghai'),
        'placeholders_remaining': placeholders,
        'cloudflare_configured': cloudflare_configured,
        'github_login_required': github_required,
        'github_login_status': gh_status,
        'github_repo_name': github_repo_name,
        'github_repo_full': github_repo_full,
        'github_repo_status': github_repo_status,
        'github_repo_action': github_repo_action,
        'next_actions': next_actions,
    }


def ensure_config_exists(config_path):
    """若 config.local.json 不存在，从 config.example.json 复制模板"""
    p = Path(config_path)
    if p.exists():
        return True
    # 查找同目录下的 config.example.json
    example = p.parent / 'config.example.json'
    if not example.exists():
        # 子技能默认模板
        example = CHILD_EXAMPLE
    if not example.exists():
        log(f'模板文件不存在: {example}', 'ERROR')
        return False
    try:
        import shutil
        shutil.copy2(example, p)
        log(f'已从模板创建: {p}')
        return True
    except Exception as e:
        log(f'创建配置文件失败: {e}', 'ERROR')
        return False


def main():
    parser = argparse.ArgumentParser(
        description='用户信息收集主入口（collect-user-info.py）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
调用示例：
  # 阶段 A（输出弹窗规范 JSON）
  python collect-user-info.py --mode standalone
  python collect-user-info.py --mode proxy --parent-config /path/to/parent/config.local.json

  # 阶段 B（应用答案并输出最终状态 JSON）
  python collect-user-info.py --mode standalone --answers /path/to/answers.json
  python collect-user-info.py --mode proxy --parent-config /path/to/parent/config.local.json --answers /path/to/answers.json

  # 仅检测占位符
  python collect-user-info.py --mode standalone --check-only
"""
    )
    parser.add_argument('--mode', choices=['standalone', 'proxy'], required=True,
                        help='收集模式：standalone=子技能独立使用；proxy=被父技能调用代理收集')
    parser.add_argument('--parent-config', default='',
                        help='父技能 config.local.json 路径（proxy 模式必填）')
    parser.add_argument('--child-config', default=str(CHILD_CONFIG),
                        help=f'子技能 config.local.json 路径（默认 {CHILD_CONFIG}）')
    parser.add_argument('--answers', default='',
                        help='LLM 执行弹窗后回传的答案 JSON 路径（阶段 B 必填）')
    parser.add_argument('--check-only', action='store_true',
                        help='仅检测占位符和登录状态，不执行收集')

    args = parser.parse_args()

    # 参数校验
    if args.mode == 'proxy' and not args.parent_config:
        log('proxy 模式必须指定 --parent-config 参数', 'ERROR')
        return 1

    if args.check_only:
        # 仅检测模式：读取配置并输出检测结果
        target_config = args.parent_config if args.mode == 'proxy' else args.child_config
        if not Path(target_config).exists():
            print(json.dumps({
                'status': 'error',
                'message': f'配置文件不存在: {target_config}',
                'placeholders_remaining': [p[1] for p in PLACEHOLDERS],
            }, ensure_ascii=False, indent=2))
            return 1
        config = load_config(target_config)
        placeholders = detect_placeholders(config)
        targets = config.get('deployment', {}).get('targets', [])
        github_required = 'github' in targets
        gh_status = check_gh_auth_status() if github_required else 'not_required'
        print(json.dumps({
            'status': 'warn' if placeholders else 'ok',
            'mode': args.mode,
            'placeholders_remaining': placeholders,
            'github_login_required': github_required,
            'github_login_status': gh_status,
        }, ensure_ascii=False, indent=2))
        return 0

    if not args.answers:
        # 阶段 A：输出弹窗规范 JSON
        spec = build_dialogs_spec(args.mode)
        print(json.dumps(spec, ensure_ascii=False, indent=2))
        return 0

    # 阶段 B：读取答案并应用
    answers_path = Path(args.answers)
    if not answers_path.exists():
        log(f'答案文件不存在: {answers_path}', 'ERROR')
        return 1
    try:
        answers = json.loads(answers_path.read_text(encoding='utf-8'))
    except Exception as e:
        log(f'解析答案文件失败: {e}', 'ERROR')
        return 1

    # 确定目标配置文件路径
    if args.mode == 'proxy':
        target_config = args.parent_config
    else:
        target_config = args.child_config

    # 确保配置文件存在
    if not ensure_config_exists(target_config):
        return 1

    # 加载现有配置
    config = load_config(target_config)

    # 应用答案
    collected_meta = apply_answers(config, answers, args.mode)
    collected_meta['collected_fields'] = [
        'paths.output_root',
        'finnhub.api_key', 'alphavantage.api_key', 'feishu.webhook_url',
        'deployment.targets', 'deployment.github.enabled'
    ]
    if args.mode == 'proxy':
        collected_meta['collected_fields'].extend(['schedule.cron', 'schedule.timezone'])

    # 保存配置
    save_config(target_config, config)

    # 输出最终状态 JSON
    final_status = build_final_status(config, args.mode, collected_meta)
    print(json.dumps(final_status, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
