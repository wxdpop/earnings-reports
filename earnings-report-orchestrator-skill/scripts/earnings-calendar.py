#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财报日历拉取脚本（跨平台 Python 3.8+）

功能：
  - 拉取指定 ticker 的下次财报日期（Finnhub /calendar/earnings）
  - 批量拉取公司库中所有公司的下次财报日期并更新
  - 输出 JSON 格式结果

依赖：Python 3.8+ 标准库 + requests
用法见 SKILL.md 阶段 0.2 / 阶段 1
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("[ERROR] 缺少 requests 库，请执行: pip install requests", file=sys.stderr)
    sys.exit(1)


# ============================================================
# 常量
# ============================================================

BJT = timezone(timedelta(hours=8))
SCRIPT_DIR = Path(__file__).resolve().parent
PARENT_SKILL_DIR = SCRIPT_DIR.parent
LIBRARY_FILE = PARENT_SKILL_DIR / "company-library.json"
CONFIG_FILE = PARENT_SKILL_DIR / "config.local.json"
FINNHUB_BASE = "https://finnhub.io/api/v1"


# ============================================================
# 工具函数
# ============================================================

def now_iso() -> str:
    return datetime.now(BJT).isoformat(timespec="seconds")


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_finnhub_key() -> str:
    """从配置或环境变量获取 Finnhub API Key（嵌套结构 config.finnhub.api_key）"""
    cfg = load_config()
    # 优先嵌套结构（与子技能一致）
    key = cfg.get("finnhub", {}).get("api_key", "")
    # 兼容扁平结构（旧版）
    if not key:
        key = cfg.get("finnhub_api_key", "")
    # 尝试环境变量
    if not key:
        import os
        key = os.environ.get("FINNHUB_API_KEY", "")
    if not key:
        print("[ERROR] 未找到 finnhub.api_key", file=sys.stderr)
        sys.exit(1)
    return key


def load_library() -> dict:
    if not LIBRARY_FILE.exists():
        return {"version": "1.0", "last_updated": "", "companies": []}
    with LIBRARY_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_library(lib: dict) -> None:
    lib["last_updated"] = now_iso()
    with LIBRARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=2)


# ============================================================
# Finnhub 财报日历
# ============================================================

def fetch_next_earnings(ticker: str, api_key: str) -> dict:
    """
    拉取指定 ticker 的下次财报日期（★ ADR 兼容 + 已发布财报检测）

    ╔══════════════════════════════════════════════════════════════════╗
    ║ ★ ADR 兼容说明（LLM 必读）                                       ║
    ╠══════════════════════════════════════════════════════════════════╣
    ║ 背景：Finnhub 对 ADR 公司（如阿斯利康 AZN 美股 ADR）             ║
    ║       用美股代码 AZN 查询 earningsCalendar 时，                  ║
    ║       返回的 symbol 字段是底层原上市代码（AZN.L 伦交所），        ║
    ║       而非查询时用的美股 ADR 代码 AZN。                          ║
    ║                                                                  ║
    ║ 旧逻辑（BUG）：item.symbol == ticker → "AZN.L" != "AZN" → 失败   ║
    ║ 新逻辑（修复）：item.symbol.split(".")[0] == ticker              ║
    ║              → "AZN.L".split(".")[0] = "AZN" == "AZN" → 命中 ✓  ║
    ║                                                                  ║
    ║ ADR 检测信号：profile2 返回的 ticker 字段含 "."（如 AZN.L）      ║
    ║ 常见 ADR 后缀：.L（伦敦）、.TO（多伦多）、.PA（巴黎）、          ║
    ║               .DE（法兰克福）、.O（纳斯达克）、.N（纽交所）      ║
    ╚══════════════════════════════════════════════════════════════════╝

    查询范围：过去7天 + 未来90天（用于检测刚发布的财报 + 下次财报）
    返回字段：
      - date/hour/minute：财报日期时间
      - quarter/year：季度与年份
      - eps_actual/revenue_actual：实际 EPS/营收（已填=已发布）
      - eps_estimated/revenue_estimated：预估 EPS/营收
      - already_released：True 表示该财报已发布
    """
    # ★ 查询范围：过去7天 + 未来90天（用于检测刚发布的财报 + 下次财报）
    today = datetime.now(BJT).date()
    from_date = today - timedelta(days=7)
    to_date = today + timedelta(days=90)
    url = f"{FINNHUB_BASE}/calendar/earnings"
    params = {
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
        "symbol": ticker.upper(),
        "token": api_key,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        # ★ ADR 兼容匹配：去掉 "." 后缀后比较（AZN.L → AZN）
        ticker_upper = ticker.upper()
        matched = []
        for item in data.get("earningsCalendar", []):
            item_symbol = item.get("symbol", "").upper()
            # 去掉交易所后缀：AZN.L → AZN, AZN.O → AZN, NVDA → NVDA
            item_symbol_base = item_symbol.split(".")[0]
            if item_symbol_base == ticker_upper:
                matched.append(item)

        if not matched:
            return {}

        # 按日期升序排序
        matched.sort(key=lambda x: x.get("date", ""))
        today_str = today.isoformat()

        # 优先返回未来或今天的财报（下次财报）
        for item in matched:
            if item.get("date", "") >= today_str:
                return {
                    "date": item.get("date", ""),
                    "hour": str(item.get("hour", "")),
                    "minute": str(item.get("minute", "")),
                    "quarter": item.get("quarter", ""),
                    "year": item.get("year", ""),
                    "eps_estimated": item.get("epsEstimate", None),
                    "revenue_estimated": item.get("revenueEstimate", None),
                    "eps_actual": item.get("epsActual"),
                    "revenue_actual": item.get("revenueActual"),
                    "already_released": bool(item.get("epsActual") is not None),
                }

        # 若无未来财报，返回最后一条（最近发布的财报）
        last = matched[-1]
        return {
            "date": last.get("date", ""),
            "hour": str(last.get("hour", "")),
            "minute": str(last.get("minute", "")),
            "quarter": last.get("quarter", ""),
            "year": last.get("year", ""),
            "eps_estimated": last.get("epsEstimate", None),
            "revenue_estimated": last.get("revenueEstimate", None),
            "eps_actual": last.get("epsActual"),
            "revenue_actual": last.get("revenueActual"),
            "already_released": True,  # 过去的财报必然已发布
        }
    except requests.RequestException as e:
        print(f"[WARN] 拉取 {ticker} 财报日历失败: {e}", file=sys.stderr)
        return {}


def fetch_single(args) -> None:
    """拉取单个 ticker 的下次财报日期（★ ADR 兼容，返回 already_released 字段）"""
    api_key = get_finnhub_key()
    result = fetch_next_earnings(args.ticker, api_key)
    if not result:
        print(json.dumps({"status": "not_found", "ticker": args.ticker, "reason": "过去7天+未来90天内无财报日历"}, ensure_ascii=False))
        return
    print(json.dumps({"status": "ok", "ticker": args.ticker, "earnings": result}, ensure_ascii=False, indent=2))


def fetch_all(args) -> None:
    """
    批量更新公司库中所有公司的下次财报日期（★ ADR 兼容 + 已发布财报处理）

    更新规则：
    - 若 result.already_released=False（未来财报）：更新 next_earnings_date/time
    - 若 result.already_released=True（已发布财报）：
      → next_earnings_date/time 置空（下次日期未知）
      → next_quarter 填入已发布季度（如 "Q2 2026"）
      → last_report_status.quarter 填入已发布季度（若原为空）
    """
    lib = load_library()
    api_key = get_finnhub_key()
    updated, failed, unchanged = [], [], []

    for company in lib.get("companies", []):
        ticker = company.get("ticker", "")
        if not ticker:
            continue
        result = fetch_next_earnings(ticker, api_key)
        if not result:
            failed.append(ticker)
            continue

        already_released = result.get("already_released", False)
        new_date = result.get("date", "")
        old_date = company.get("next_earnings_date", "")

        if already_released:
            # ★ 已发布财报：next_earnings_date/time 置空，填充 quarter
            released_quarter = ""
            if result.get("quarter") and result.get("year"):
                released_quarter = f"Q{result['quarter']} {result['year']}"
            company["next_earnings_date"] = ""
            company["next_earnings_time"] = ""
            if released_quarter:
                company["next_quarter"] = released_quarter
                # 同步更新 last_report_status.quarter（若原为空）
                if not company.get("last_report_status", {}).get("quarter", ""):
                    company["last_report_status"]["quarter"] = released_quarter
            updated.append({"ticker": ticker, "type": "already_released", "quarter": released_quarter, "date": new_date})
        else:
            # 未来财报：更新 next_earnings_date/time
            if new_date and new_date != old_date:
                company["next_earnings_date"] = new_date
                company["next_earnings_time"] = f"{result.get('hour', '')}:{result.get('minute', '')}".strip(":")
                updated.append({"ticker": ticker, "type": "upcoming", "old": old_date, "new": new_date})
            else:
                unchanged.append(ticker)

    save_library(lib)
    print(json.dumps({
        "status": "ok",
        "total": len(lib.get("companies", [])),
        "updated_count": len(updated),
        "unchanged_count": len(unchanged),
        "failed_count": len(failed),
        "updated": updated,
        "failed": failed
    }, ensure_ascii=False, indent=2))


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="财报日历拉取脚本（父技能 earnings-report-orchestrator）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python earnings-calendar.py --ticker NVDA
  python earnings-calendar.py --all
        """
    )
    parser.add_argument("--ticker", help="单个公司股票代码")
    parser.add_argument("--all", action="store_true", help="批量更新公司库中所有公司的下次财报日期")

    args = parser.parse_args()
    if not args.ticker and not args.all:
        parser.error("必须指定 --ticker 或 --all")
    if args.ticker and args.all:
        parser.error("--ticker 和 --all 互斥")

    if args.ticker:
        fetch_single(args)
    else:
        fetch_all(args)


if __name__ == "__main__":
    main()
