#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财务数据解析工具

功能：解析 fetch-data 拉取的 JSON 文件，输出完整财务数据摘要。
      供 LLM 生成 sections JSON 时直接使用，避免临时脚本。

用法：
  python3 parse-financial-data.py <data-dir>
  python3 parse-financial-data.py /path/to/data/rklb-q1-2026

输出内容：
  1. 公司 Profile（名称/行业/市值/交易所）
  2. 分析师评级（最近 3 期）
  3. 收入报表（最近 6 季度，含同比计算）
  4. 资产负债表（最近 4 季度）
  5. 现金流（最近 4 季度）
  6. 关键指标汇总（毛利率/净利率/现金储备/资产负债率）
"""
import sys
import os
import json
from pathlib import Path


def fmt_amount(val):
    """格式化金额（美元）"""
    if not val or val == 'None':
        return 'N/A'
    try:
        v = int(val)
        if abs(v) >= 1_000_000_000:
            return f"{v/100_000_000:.2f} 亿美元"
        elif abs(v) >= 1_000_000:
            return f"{v/1_000_000:.2f} 百万美元"
        elif abs(v) >= 1_000:
            return f"{v/1_000:.2f} 千美元"
        else:
            return f"{v} 美元"
    except (ValueError, TypeError):
        return str(val)


def fmt_percent(num, denom):
    """计算百分比"""
    try:
        n = float(num)
        d = float(denom)
        if d == 0:
            return 'N/A'
        return f"{(n/d)*100:.1f}%"
    except (ValueError, TypeError):
        return 'N/A'


def yoy_change(current, previous):
    """计算同比增长率"""
    try:
        c = float(current)
        p = float(previous)
        if p == 0:
            return 'N/A'
        change = ((c - p) / abs(p)) * 100
        sign = '+' if change >= 0 else ''
        return f"{sign}{change:.1f}%"
    except (ValueError, TypeError):
        return 'N/A'


def load_json(path):
    """加载 JSON 文件"""
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"  [错误] 读取 {path.name} 失败: {e}")
        return None


def parse_profile(data_dir, sym_lower):
    """解析公司 Profile"""
    path = data_dir / f'{sym_lower}-profile.json'
    if not path.exists():
        print('[WARN] profile 文件不存在')
        return
    data = load_json(path)
    if not data:
        return
    print('=== 公司 Profile ===')
    print(f"  名称: {data.get('name', 'N/A')}")
    print(f"  股票代码: {data.get('ticker', 'N/A')}")
    print(f"  行业: {data.get('finnhubIndustry', 'N/A')}")
    print(f"  交易所: {data.get('exchange', 'N/A')}")
    print(f"  市值: {fmt_amount(data.get('marketCapitalization', 0) * 1_000_000) if data.get('marketCapitalization') else 'N/A'}")
    print(f"  流通股: {data.get('shareOutstanding', 'N/A')} 百万股")
    print(f"  IPO: {data.get('ipo', 'N/A')}")
    print(f"  货币: {data.get('currency', 'N/A')}")
    print(f"  国家: {data.get('country', 'N/A')}")
    print(f"  网站: {data.get('weburl', 'N/A')}")
    print()


def parse_recommendations(data_dir, sym_lower):
    """解析分析师评级"""
    path = data_dir / f'{sym_lower}-recommendations.json'
    if not path.exists():
        print('[WARN] recommendations 文件不存在')
        return
    data = load_json(path)
    if not data or not isinstance(data, list):
        return
    print('=== 分析师评级（最近 3 期）===')
    for r in data[:3]:
        period = r.get('period', 'N/A')
        sb = r.get('strongBuy', 0)
        b = r.get('buy', 0)
        h = r.get('hold', 0)
        s = r.get('sell', 0)
        ss = r.get('strongSell', 0)
        total = sb + b + h + s + ss
        print(f"  期间: {period} | 强买: {sb} | 买: {b} | 持: {h} | 卖: {s} | 强卖: {ss} | 总计: {total}")
    print()


def parse_income(data_dir, sym_lower):
    """解析收入报表"""
    path = data_dir / f'{sym_lower}-income-statement.json'
    if not path.exists():
        print('[WARN] income-statement 文件不存在')
        return None, None
    data = load_json(path)
    if not data:
        return None, None
    reports = data.get('quarterlyReports', [])
    if not reports:
        return None, None

    print('=== 收入报表（最近 6 季度）===')
    print(f"  字段名: {list(reports[0].keys())[:10]}...")
    print()

    for i, r in enumerate(reports[:6]):
        date = r.get('fiscalDateEnding', 'N/A')
        revenue = r.get('totalRevenue', '0')
        gross = r.get('grossProfit', '0')
        net = r.get('netIncome', '0')
        rd = r.get('researchAndDevelopment', '0')
        op_income = r.get('operatingIncome', '0')

        # 同比计算（去年同期 = 4 个季度前）
        yoy_rev = 'N/A'
        if i + 4 < len(reports):
            prev = reports[i + 4]
            yoy_rev = yoy_change(revenue, prev.get('totalRevenue', '0'))

        gross_margin = fmt_percent(gross, revenue)
        net_margin = fmt_percent(net, revenue)

        print(f"  [{date}] 营收: {fmt_amount(revenue)} ({yoy_rev} YoY)")
        print(f"           毛利: {fmt_amount(gross)} (毛利率: {gross_margin}) | 净利: {fmt_amount(net)} (净利率: {net_margin})")
        print(f"           R&D: {fmt_amount(rd)} | 营业利润: {fmt_amount(op_income)}")
        print()

    return reports, reports[0] if reports else None


def parse_balance_sheet(data_dir, sym_lower):
    """解析资产负债表"""
    path = data_dir / f'{sym_lower}-balance-sheet.json'
    if not path.exists():
        print('[WARN] balance-sheet 文件不存在')
        return None
    data = load_json(path)
    if not data:
        return None
    reports = data.get('quarterlyReports', [])
    if not reports:
        return None

    print('=== 资产负债表（最近 4 季度）===')
    for r in reports[:4]:
        date = r.get('fiscalDateEnding', 'N/A')
        total_assets = r.get('totalAssets', '0')
        cash = r.get('cashAndCashEquivalentsAtCarryingValue', '0')
        inventory = r.get('inventory', '0')
        total_liab = r.get('totalLiabilities', '0')
        equity = r.get('totalShareholderEquity', '0')
        long_term_debt = r.get('longTermDebt', '0')

        debt_ratio = fmt_percent(total_liab, total_assets)

        print(f"  [{date}] 总资产: {fmt_amount(total_assets)} | 现金: {fmt_amount(cash)}")
        print(f"           存货: {fmt_amount(inventory)} | 总负债: {fmt_amount(total_liab)} | 股东权益: {fmt_amount(equity)}")
        print(f"           长期债务: {fmt_amount(long_term_debt)} | 资产负债率: {debt_ratio}")
        print()

    return reports[0] if reports else None


def parse_cashflow(data_dir, sym_lower):
    """解析现金流"""
    path = data_dir / f'{sym_lower}-cashflow.json'
    if not path.exists():
        print('[WARN] cashflow 文件不存在')
        return None
    data = load_json(path)
    if not data:
        return None
    reports = data.get('quarterlyReports', [])
    if not reports:
        return None

    print('=== 现金流（最近 4 季度）===')
    for r in reports[:4]:
        date = r.get('fiscalDateEnding', 'N/A')
        ocf = r.get('operatingCashflow', '0')
        capex = r.get('capitalExpenditures', '0')
        fcf = 0
        try:
            if ocf and capex and ocf != 'None' and capex != 'None':
                fcf = int(float(ocf)) - int(float(capex))
        except (ValueError, TypeError):
            fcf = 0
        fin_cf = r.get('cashflowFromFinancing', '0')
        inv_cf = r.get('cashflowFromInvestment', '0')

        print(f"  [{date}] 经营CF: {fmt_amount(ocf)} | 资本支出: {fmt_amount(capex)} | 自由CF: {fmt_amount(fcf)}")
        print(f"           融资CF: {fmt_amount(fin_cf)} | 投资CF: {fmt_amount(inv_cf)}")
        print()

    return reports[0] if reports else None


def print_summary(latest_income, latest_balance, latest_cashflow, income_reports):
    """打印关键指标汇总"""
    print('=== 关键指标汇总（最新季度）===')
    if latest_income:
        revenue = latest_income.get('totalRevenue', '0')
        gross = latest_income.get('grossProfit', '0')
        net = latest_income.get('netIncome', '0')
        print(f"  营收: {fmt_amount(revenue)}")
        print(f"  毛利: {fmt_amount(gross)} (毛利率: {fmt_percent(gross, revenue)})")
        print(f"  净利: {fmt_amount(net)} (净利率: {fmt_percent(net, revenue)})")

        # 同比
        if income_reports and len(income_reports) >= 4:
            prev = income_reports[3]
            print(f"  营收同比: {yoy_change(revenue, prev.get('totalRevenue', '0'))}")
            prev_gm = fmt_percent(prev.get('grossProfit', '0'), prev.get('totalRevenue', '0'))
            curr_gm = fmt_percent(gross, revenue)
            print(f"  毛利率同比: {prev_gm} → {curr_gm}")

    if latest_balance:
        cash = latest_balance.get('cashAndCashEquivalentsAtCarryingValue', '0')
        total_assets = latest_balance.get('totalAssets', '0')
        total_liab = latest_balance.get('totalLiabilities', '0')
        print(f"  现金储备: {fmt_amount(cash)}")
        print(f"  总资产: {fmt_amount(total_assets)}")
        print(f"  总负债: {fmt_amount(total_liab)} (资产负债率: {fmt_percent(total_liab, total_assets)})")

    if latest_cashflow:
        ocf = latest_cashflow.get('operatingCashflow', '0')
        capex = latest_cashflow.get('capitalExpenditures', '0')
        print(f"  经营现金流: {fmt_amount(ocf)}")
        print(f"  资本支出: {fmt_amount(capex)}")
    print()


def main():
    if len(sys.argv) < 2:
        print("用法: python3 parse-financial-data.py <data-dir>")
        print("示例: python3 parse-financial-data.py /path/to/data/rklb-q1-2026")
        sys.exit(1)

    data_dir = Path(sys.argv[1]).resolve()
    if not data_dir.is_dir():
        print(f"[错误] 数据目录不存在: {data_dir}")
        sys.exit(1)

    # 推断 symbol（从文件名提取，如 rklb-income-statement.json -> rklb）
    sym_lower = ''
    for f in data_dir.iterdir():
        if f.name.endswith('-income-statement.json'):
            sym_lower = f.name.replace('-income-statement.json', '')
            break

    if not sym_lower:
        print(f"[错误] 未找到 *-income-statement.json 文件")
        sys.exit(1)

    print(f'数据目录: {data_dir}')
    print(f'推断 symbol: {sym_lower.upper()}')
    print()

    parse_profile(data_dir, sym_lower)
    parse_recommendations(data_dir, sym_lower)
    income_reports, latest_income = parse_income(data_dir, sym_lower)
    latest_balance = parse_balance_sheet(data_dir, sym_lower)
    latest_cashflow = parse_cashflow(data_dir, sym_lower)
    print_summary(latest_income, latest_balance, latest_cashflow, income_reports)


if __name__ == '__main__':
    main()
