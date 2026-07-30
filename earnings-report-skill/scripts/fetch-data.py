#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨平台 API 数据拉取脚本

合并自原 fetch-data.ps1 + fetch-data.sh，使用 urllib 实现 HTTP 请求，
单文件覆盖 Windows/Mac/Linux。

拉取 5 类数据：
  1. Finnhub 公司 profile
  2. Finnhub 分析师评级
  3. Alpha Vantage 收入报表（每次调用间隔 12 秒以规避频率限制）
  4. Alpha Vantage 资产负债表
  5. Alpha Vantage 现金流量表

API Key 加载：config.local.json（统一入口）
输出目录解析优先级：--out-dir 参数 → 代码推导(output_root/Output/项目名/data) → 抛错

用法：
  python fetch-data.py --symbol JNJ
  python fetch-data.py --symbol JNJ --out-dir /path/to/data
"""
import sys
import os
import json
import time
import argparse
import urllib.request
import urllib.error
import platform
from pathlib import Path

# ============================================================
# Windows stdout UTF-8 处理（避免 cp936 终端 UnicodeEncodeError）
# ============================================================
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        pass

# ============================================================
# 颜色（跨平台 ANSI）
# ============================================================
COLOR_CYAN = '\033[36m'
COLOR_GREEN = '\033[32m'
COLOR_YELLOW = '\033[33m'
COLOR_RED = '\033[31m'
COLOR_GRAY = '\033[90m'
COLOR_RESET = '\033[0m'

if sys.platform == 'win32':
    os.system('')  # 激活 Windows ANSI 颜色支持


def log(msg, level='INFO'):
    """带颜色日志输出"""
    color = {
        'INFO': COLOR_CYAN,
        'OK': COLOR_GREEN,
        'WARN': COLOR_YELLOW,
        'ERROR': COLOR_RED,
        'GRAY': COLOR_GRAY,
        'CYAN': COLOR_CYAN,
        'GREEN': COLOR_GREEN,
        'YELLOW': COLOR_YELLOW,
        'RED': COLOR_RED,
    }.get(level, '')
    print(f"{color}{msg}{COLOR_RESET}")


# ============================================================
# 路径与配置加载
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
CONFIG_FILE = SKILL_ROOT / 'config.local.json'


def load_config():
    """加载 config.local.json，返回 (config_dict, skill_root)。
    配置文件不存在时返回 ({}, skill_root)。"""
    if not CONFIG_FILE.exists():
        return {}, SKILL_ROOT
    try:
        return json.loads(CONFIG_FILE.read_text(encoding='utf-8')), SKILL_ROOT
    except Exception as e:
        log(f"config.local.json 解析失败: {e}", 'WARN')
        return {}, SKILL_ROOT


def get_nested(obj, *keys, default=''):
    """安全读取嵌套字段，如 get_nested(cfg, 'finnhub', 'api_key')"""
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur if cur else default


def resolve_output_dir(arg_out_dir, config):
    """解析数据输出目录优先级：参数 → 代码推导(output_root/Output/项目名/data) → 抛错"""
    if arg_out_dir:
        return arg_out_dir
    # 推导仓库根目录：output_root/Output/项目名，再拼接 /data
    output_root = get_nested(config, 'paths', 'output_root')
    github_repo = get_nested(config, 'deployment', 'github', 'repo')
    project_name = github_repo.split('/')[-1] if github_repo else ''
    if output_root and project_name:
        return os.path.join(output_root, 'Output', project_name, 'data')
    # 无法推导，抛错提示用户配置
    raise RuntimeError(
        "无法推导数据输出目录。请确保 config.local.json 的 paths.output_root "
        "（盘符+文件夹，如 d:/TraeAutomaticTools）和 deployment.github.repo 已配置，"
        "或通过 --out-dir 参数传入。"
    )


def http_get_json(url, timeout=30):
    """发起 GET 请求，返回解析后的 JSON 对象。失败抛异常。"""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode('utf-8')
    return json.loads(body)


def save_json(data, path):
    """保存 JSON 到文件（UTF-8 无 BOM，ensure_ascii=False）"""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# 主流程
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='跨平台 API 数据拉取脚本（Finnhub + Alpha Vantage）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--symbol', '-s', required=True,
                        help='股票代码（必需，如 JNJ、TSLA）')
    parser.add_argument('--out-dir', '-o', default='',
                        help='输出目录（可选，默认从配置读取）')
    args = parser.parse_args()

    symbol = args.symbol.strip().upper()
    sym_lower = symbol.lower()

    # 加载配置
    config, _ = load_config()

    # 读取 API Key：config.local.json（统一入口）
    finnhub_token = get_nested(config, 'finnhub', 'api_key')
    alpha_key = get_nested(config, 'alphavantage', 'api_key')

    if not finnhub_token or not alpha_key:
        log('[错误] 未找到 API Key。请：', 'ERROR')
        log('  创建 config.local.json（参考 config.example.json，嵌套结构：finnhub.api_key / alphavantage.api_key）', 'ERROR')
        sys.exit(1)

    if CONFIG_FILE.exists():
        log('[config] 已加载 config.local.json', 'GRAY')

    # 解析输出目录
    out_dir = resolve_output_dir(args.out_dir, config)
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    log(f"=== {symbol} 数据拉取 ===", 'CYAN')

    # ------------------------------------------------------------
    # 1. Finnhub - 公司 profile
    # ------------------------------------------------------------
    log('[1/5] Finnhub 公司profile...', 'YELLOW')
    try:
        url = f"https://finnhub.io/api/v1/stock/profile2?symbol={symbol}&token={finnhub_token}"
        profile = http_get_json(url, timeout=30)
        save_json(profile, os.path.join(out_dir, f"{sym_lower}-profile.json"))
        if isinstance(profile, dict) and profile:
            name = profile.get('name', 'N/A')
            industry = profile.get('finnhubIndustry', 'N/A')
            mcap = profile.get('marketCapitalization', 'N/A')
            log(f"  名称: {name} | 行业: {industry} | 市值: {mcap}M$", 'GREEN')
        else:
            log(f"  已保存（响应为空或非对象）", 'GREEN')
    except Exception as e:
        log(f"  失败: {e}", 'RED')

    time.sleep(2)

    # ------------------------------------------------------------
    # 2. Finnhub - 分析师评级
    # ------------------------------------------------------------
    log('[2/5] Finnhub 分析师评级...', 'YELLOW')
    try:
        url = f"https://finnhub.io/api/v1/stock/recommendation?symbol={symbol}&token={finnhub_token}"
        recs = http_get_json(url, timeout=30)
        save_json(recs, os.path.join(out_dir, f"{sym_lower}-recommendations.json"))
        if isinstance(recs, list) and recs:
            latest = recs[0]
            period = latest.get('period', 'N/A')
            sb = latest.get('strongBuy', 0)
            ss = latest.get('strongSell', 0)
            log(f"  期间: {period} | 买入: {sb} | 卖出: {ss}", 'GREEN')
        else:
            log(f"  已保存", 'GREEN')
    except Exception as e:
        log(f"  失败: {e}", 'RED')

    # Alpha Vantage 频率限制：每次调用间隔 12 秒
    time.sleep(12)

    # ------------------------------------------------------------
    # 3. Alpha Vantage - 收入报表
    # ------------------------------------------------------------
    log('[3/5] Alpha Vantage 收入报表...', 'YELLOW')
    try:
        url = f"https://www.alphavantage.co/query?function=INCOME_STATEMENT&symbol={symbol}&apikey={alpha_key}"
        income = http_get_json(url, timeout=30)
        save_json(income, os.path.join(out_dir, f"{sym_lower}-income-statement.json"))
        reports = income.get('quarterlyReports', []) if isinstance(income, dict) else []
        log(f"  季度报告: {len(reports)}", 'GREEN')
        if reports:
            latest_q = reports[0]
            log(f"  最新季度: {latest_q.get('fiscalDateEnding', 'N/A')} | 营收: {latest_q.get('totalRevenue', 'N/A')} | 净利: {latest_q.get('netIncome', 'N/A')}", 'GREEN')
    except Exception as e:
        log(f"  失败: {e}", 'RED')

    time.sleep(12)

    # ------------------------------------------------------------
    # 4. Alpha Vantage - 资产负债表
    # ------------------------------------------------------------
    log('[4/5] Alpha Vantage 资产负债表...', 'YELLOW')
    try:
        url = f"https://www.alphavantage.co/query?function=BALANCE_SHEET&symbol={symbol}&apikey={alpha_key}"
        balance = http_get_json(url, timeout=30)
        save_json(balance, os.path.join(out_dir, f"{sym_lower}-balance-sheet.json"))
        reports = balance.get('quarterlyReports', []) if isinstance(balance, dict) else []
        log(f"  季度报告: {len(reports)}", 'GREEN')
    except Exception as e:
        log(f"  失败: {e}", 'RED')

    time.sleep(12)

    # ------------------------------------------------------------
    # 5. Alpha Vantage - 现金流
    # ------------------------------------------------------------
    log('[5/5] Alpha Vantage 现金流...', 'YELLOW')
    try:
        url = f"https://www.alphavantage.co/query?function=CASH_FLOW&symbol={symbol}&apikey={alpha_key}"
        cashflow = http_get_json(url, timeout=30)
        save_json(cashflow, os.path.join(out_dir, f"{sym_lower}-cashflow.json"))
        reports = cashflow.get('quarterlyReports', []) if isinstance(cashflow, dict) else []
        log(f"  季度报告: {len(reports)}", 'GREEN')
    except Exception as e:
        log(f"  失败: {e}", 'RED')

    # ------------------------------------------------------------
    # 汇总输出
    # ------------------------------------------------------------
    log('', 'INFO')
    log('=== 数据拉取完成 ===', 'CYAN')
    log(f"输出目录: {out_dir}")
    log("文件列表:", 'GRAY')
    for f in sorted(Path(out_dir).glob(f"{sym_lower}-*.json")):
        size_kb = f.stat().st_size / 1024
        log(f"  {f.name} ({size_kb:.1f} KB)", 'GRAY')

    # ------------------------------------------------------------
    # 自动输出财务数据摘要（调用 parse-financial-data.py）
    # ------------------------------------------------------------
    parse_script = SCRIPT_DIR / 'parse-financial-data.py'
    if parse_script.exists():
        py_cmd = sys.executable or 'python3'
        log('', 'INFO')
        log('=== 财务数据摘要（供生成 sections JSON 使用）===', 'CYAN')
        import subprocess
        try:
            result = subprocess.run(
                [py_cmd, str(parse_script), out_dir],
                capture_output=False,
                timeout=60,
            )
            if result.returncode != 0:
                log('  [提示] 摘要生成失败，可直接读取 JSON 文件', 'YELLOW')
        except Exception as e:
            log(f'  [提示] 摘要生成异常: {e}', 'YELLOW')

    sys.exit(0)


if __name__ == '__main__':
    main()
