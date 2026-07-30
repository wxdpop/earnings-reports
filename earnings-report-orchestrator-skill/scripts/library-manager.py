#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公司库管理脚本（跨平台 Python 3.8+）

功能：
  - add          添加单个公司（自动拉取 Finnhub profile + 下次财报日期）
  - list         列出所有公司
  - show         查看单个公司详情
  - update-next  更新下次财报日期
  - update-status 更新报告状态（waiting → completed / failed）
  - remove       移除公司
  - today        导出今日待发布财报公司列表（供定时任务调度使用）
  - import-presets 批量导入预设（mag7 或自定义 ticker 列表）

依赖：Python 3.8+ 标准库 + requests
用法见 SKILL.md 阶段 0
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

# 美股 7 巨头预设（Magnificent 7）
MAGNIFICENT_7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]

# 预设映射
PRESETS = {
    "mag7": MAGNIFICENT_7,
}

# ★ 常见美股公司中文映射表（ticker → 中文名）
# add/import-presets 时优先使用此映射表，而非 Finnhub 返回的英文名
TICKER_NAME_CN_MAP = {
    # 美股 7 巨头
    "AAPL": "苹果", "MSFT": "微软", "GOOGL": "谷歌", "AMZN": "亚马逊",
    "NVDA": "英伟达", "META": "Meta平台", "TSLA": "特斯拉",
    # 中概股
    "BABA": "阿里巴巴", "PDD": "拼多多", "JD": "京东", "BIDU": "百度",
    "NIO": "蔚来", "LI": "理想汽车", "XPEV": "小鹏汽车", "NTES": "网易",
    "BILI": "哔哩哔哩", "TME": "腾讯音乐", "WB": "微博", "DIDI": "滴滴",
    # 消费/零售
    "KO": "可口可乐", "PEP": "百事可乐", "SBUX": "星巴克", "MCD": "麦当劳",
    "NKE": "耐克", "COST": "好市多", "WMT": "沃尔玛", "TGT": "塔吉特",
    "HD": "家得宝", "LOW": "劳氏", "DIS": "迪士尼", "NFLX": "奈飞",
    "ABNB": "爱彼迎", "UBER": "优步", "LYFT": "来福车", "SHOP": "Shopify",
    # 金融
    "JPM": "摩根大通", "GS": "高盛", "MS": "摩根士丹利", "WFC": "富国银行",
    "BAC": "美国银行", "C": "花旗集团", "AXP": "美国运通", "BLK": "贝莱德",
    "SCHW": "嘉信理财", "CB": "安达保险", "HOOD": "Robinhood",
    # 医疗/制药
    "JNJ": "强生", "UNH": "联合健康", "PFE": "辉瑞", "MRK": "默沙东",
    "ABT": "雅培", "TMO": "赛默飞世尔", "AZN": "阿斯利康", "GSK": "葛兰素史克",
    "SNY": "赛诺菲", "NVO": "诺和诺德", "LLY": "礼来", "DHR": "丹纳赫",
    # 科技/半导体
    "INTC": "英特尔", "AMD": "超威半导体", "QCOM": "高通", "AVGO": "博通",
    "TXN": "德州仪器", "CSCO": "思科", "ORCL": "甲骨文", "IBM": "IBM",
    "CRM": "赛富时", "ADBE": "Adobe", "PYPL": "PayPal", "NOW": "ServiceNow",
    "SAP": "SAP", "PLTR": "Palantir", "SNOW": "Snowflake", "CRWD": "CrowdStrike",
    "NET": "Cloudflare", "OKTA": "Okta", "ZM": "Zoom", "DOCU": "DocuSign",
    "COIN": "Coinbase", "AFRM": "Affirm",
    # 工业/航空/汽车
    "F": "福特汽车", "GM": "通用汽车", "BA": "波音", "CAT": "卡特彼勒",
    "GE": "通用电气", "MMM": "3M", "HON": "霍尼韦尔", "LMT": "洛克希德马丁",
    "RTX": "雷神技术", "UPS": "联合包裹", "FDX": "联邦快递",
    "RKLB": "火箭实验室", "SPCE": "维珍银河", "ASTS": "AST SpaceMobile",
    # 通信
    "T": "美国电话电报", "VZ": "威瑞森通信", "TMUS": "T-Mobile",
    "CMCSA": "康卡斯特", "NOK": "诺基亚", "ERIC": "爱立信",
    "VOD": "沃达丰", "BT": "英国电信",
    # 能源
    "XOM": "埃克森美孚", "CVX": "雪佛龙", "COP": "康菲石油",
    # AI/新兴
    "NBIS": "Nebius",
}


def get_company_name_cn(ticker: str, profile: dict = None, name_cn_arg: str = "") -> str:
    """获取公司中文名（优先级：--name-cn 参数 > 映射表 > Finnhub 返回的 name > ticker）"""
    ticker_upper = ticker.upper()
    # 优先级1：用户显式传入的 --name-cn
    if name_cn_arg:
        return name_cn_arg
    # 优先级2：内置中文映射表
    if ticker_upper in TICKER_NAME_CN_MAP:
        return TICKER_NAME_CN_MAP[ticker_upper]
    # 优先级3：Finnhub 返回的 name
    if profile and profile.get("name"):
        return profile["name"]
    # 优先级4：ticker 本身
    return ticker_upper


# 北京时区（UTC+8）
BJT = timezone(timedelta(hours=8))

# 公司库文件路径（脚本所在目录的上一级）
SCRIPT_DIR = Path(__file__).resolve().parent
PARENT_SKILL_DIR = SCRIPT_DIR.parent
LIBRARY_FILE = PARENT_SKILL_DIR / "company-library.json"
CONFIG_FILE = PARENT_SKILL_DIR / "config.local.json"

# Finnhub API 基址
FINNHUB_BASE = "https://finnhub.io/api/v1"

# ★ 时区校验提醒常量（LLM 读到此字段后必须校验时区是否已转换为北京时间）
TIMEZONE_REMINDER = (
    "★ 时区校验提醒：公司库要求所有时间字段为北京时间（UTC+8）。"
    "若数据来源为 Finnhub earningsCalendar（美东时间 UTC-5/-4），"
    "LLM 必须先转换为北京时间再写入：夏令时 +12h，冬令时 +13h，跨日则 date 加一天。"
    "示例：美东 2026-07-29 08:00 → 北京 2026-07-29 20:00；美东 2026-07-28 16:00 → 北京 2026-07-29 04:00。"
)


# ============================================================
# 工具函数
# ============================================================

def now_iso() -> str:
    """返回当前北京时间 ISO 格式字符串"""
    return datetime.now(BJT).isoformat(timespec="seconds")


def load_library() -> dict:
    """加载公司库 JSON"""
    if not LIBRARY_FILE.exists():
        return {"version": "1.0", "last_updated": "", "companies": []}
    with LIBRARY_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_library(lib: dict) -> None:
    """保存公司库 JSON"""
    lib["last_updated"] = now_iso()
    with LIBRARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=2)


def load_config() -> dict:
    """加载配置文件"""
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
        print("[ERROR] 未找到 finnhub.api_key，请配置 config.local.json 或环境变量 FINNHUB_API_KEY", file=sys.stderr)
        sys.exit(1)
    return key


def find_company(lib: dict, ticker: str) -> dict | None:
    """按 ticker 查找公司（大小写不敏感）"""
    upper = ticker.upper()
    for c in lib.get("companies", []):
        if c.get("ticker", "").upper() == upper:
            return c
    return None


# ============================================================
# Finnhub API 调用
# ============================================================

def fetch_profile(ticker: str, api_key: str) -> dict:
    """调用 Finnhub /stock/profile2 拉取公司 profile"""
    url = f"{FINNHUB_BASE}/stock/profile2"
    params = {"symbol": ticker.upper(), "token": api_key}
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"[WARN] 拉取 {ticker} profile 失败: {e}", file=sys.stderr)
        return {}


def fetch_earnings_calendar(ticker: str, api_key: str) -> dict:
    """
    调用 Finnhub /calendar/earnings 拉取财报日历（★ ADR 兼容 + 已发布财报检测）

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

    ╔══════════════════════════════════════════════════════════════════╗
    ║ ★ 已发布财报检测说明                                             ║
    ╠══════════════════════════════════════════════════════════════════╣
    ║ 查询范围从"今日起未来90天"扩展为"过去7天 + 未来90天"             ║
    ║ 这样能发现刚发布的财报（epsActual/revenueActual 已填）           ║
    ║                                                                  ║
    ║ 返回字段说明：                                                   ║
    ║   - date/hour/minute：财报日期时间                               ║
    ║   - quarter/year：季度与年份                                     ║
    ║   - eps_actual/revenue_actual：实际 EPS/营收（已填=已发布）       ║
    ║   - already_released：True 表示该财报已发布                      ║
    ╚══════════════════════════════════════════════════════════════════╝

    返回: dict（含 date/hour/minute/quarter/year/eps_actual/revenue_actual/already_released/timezone_raw）或空 dict

    ★★★ 时区警告（LLM 必读）★★★
    Finnhub earningsCalendar 返回的 date/hour/minute 为【美东时间】（UTC-5 冬令时 / UTC-4 夏令时）。
    公司库要求所有时间字段为【北京时间】（UTC+8）。
    LLM 在写入公司库前必须做时区转换：
      - 夏令时（3月第二周日 ~ 11月第一周日）：北京时间 = 美东时间 + 12 小时
      - 冬令时（11月第一周日 ~ 3月第二周日）：北京时间 = 美东时间 + 13 小时
      - 若跨日，next_earnings_date 也要相应加一天
    示例：美东 2026-07-29 08:00 (盘前 bmo) → 北京 2026-07-29 20:00
          美东 2026-07-28 16:00 (盘后 amc) → 北京 2026-07-29 04:00
    本函数返回 timezone_raw="US/Eastern" 标记原始时区，LLM 据此判断是否需要转换。
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
                    "eps_actual": item.get("epsActual"),
                    "revenue_actual": item.get("revenueActual"),
                    "already_released": bool(item.get("epsActual") is not None),
                    # ★ 标记原始时区为美东，LLM 写入公司库前需转换为北京时间
                    "timezone_raw": "US/Eastern",
                }

        # 若无未来财报，返回最后一条（最近发布的财报）
        last = matched[-1]
        return {
            "date": last.get("date", ""),
            "hour": str(last.get("hour", "")),
            "minute": str(last.get("minute", "")),
            "quarter": last.get("quarter", ""),
            "year": last.get("year", ""),
            "eps_actual": last.get("epsActual"),
            "revenue_actual": last.get("revenueActual"),
            "already_released": True,  # 过去的财报必然已发布
            # ★ 标记原始时区为美东，LLM 写入公司库前需转换为北京时间
            "timezone_raw": "US/Eastern",
        }
    except requests.RequestException as e:
        print(f"[WARN] 拉取 {ticker} 财报日历失败: {e}", file=sys.stderr)
        return {}


# ============================================================
# 公司库 CRUD
# ============================================================

def action_add(args) -> None:
    """
    添加单个公司（★ ADR 兼容 + 已发布财报处理）

    ADR 兼容：
    - profile2(AZN) 返回 ticker="AZN.L"（含 "."），说明是 ADR
    - earningsCalendar 用 AZN 查询，返回 symbol="AZN.L"，去后缀后匹配

    已发布财报处理：
    - 若 cal.already_released=True，说明该财报已发布
      → next_earnings_date/time 置空（下次日期未知）
      → next_quarter 填入已发布季度（如 "Q2 2026"）
      → last_report_status.quarter 也填入已发布季度，status=waiting（待生成报告）
    - 若 cal.already_released=False（未来财报），按原逻辑填入 next_earnings_date/time
    """
    lib = load_library()
    if find_company(lib, args.ticker):
        print(json.dumps({"status": "skipped", "ticker": args.ticker, "reason": "已存在"}, ensure_ascii=False))
        return

    api_key = get_finnhub_key()
    ticker = args.ticker.upper()

    # 拉 profile
    profile = fetch_profile(ticker, api_key)
    # 拉财报日历（★ ADR 兼容，返回 already_released 字段）
    cal = fetch_earnings_calendar(ticker, api_key)

    # ★ 解析已发布财报的季度标识（quarter=2, year=2026 → "Q2 2026"）
    released_quarter = ""
    if cal.get("already_released") and cal.get("quarter") and cal.get("year"):
        released_quarter = f"Q{cal['quarter']} {cal['year']}"

    # ★ 使用中文映射表获取中文名（优先级：--name-cn > 映射表 > Finnhub name > ticker）
    name_cn = get_company_name_cn(ticker, profile, args.name_cn)

    company = {
        "ticker": ticker,
        "company_name_cn": name_cn,
        "company_name_en": profile.get("name", ""),
        "currency": profile.get("currency", "USD"),
        "exchange": profile.get("exchange", ""),
        "ir_url": profile.get("weburl", ""),
        "gelonghui_keyword": name_cn,
        "futunn_keyword": ticker,
        # ★ 已发布财报：next_earnings_date/time 置空（下次未知）；未来财报：填入日期
        "next_earnings_date": "" if cal.get("already_released") else cal.get("date", ""),
        "next_earnings_time": "" if cal.get("already_released") else f"{cal.get('hour', '')}:{cal.get('minute', '')}".strip(":"),
        # ★ next_quarter 优先用 --quarter 参数，否则用已发布财报季度，再否则空
        "next_quarter": args.quarter or (released_quarter if cal.get("already_released") else ""),
        # ★ next_earnings_status：下一次财报状态（waiting=待处理, completed=已处理完毕且下次日期未知）
        "next_earnings_status": "waiting",
        # ★ 是否有电话会议（默认 True；部分公司无电话会议时设 False，就绪检查只查 1+3）
        "has_earnings_call": not args.no_earnings_call,
        "last_report_status": {
            # ★ 已发布财报：quarter 填入已发布季度，便于后续生成报告；status=waiting（待生成）
            "quarter": released_quarter if cal.get("already_released") else "",
            "generated_at": "",
            "report_path": "",
            "status": "waiting"  # ★ 初始为 waiting，按用户要求
        },
        "enabled": True,
        "created_at": now_iso()
    }

    lib["companies"].append(company)
    save_library(lib)

    result = {
        "status": "added",
        "ticker": ticker,
        "company_name": company["company_name_cn"],
        "next_earnings_date": company["next_earnings_date"],
        "next_earnings_time": company["next_earnings_time"],
        "next_quarter": company["next_quarter"],
        "already_released": cal.get("already_released", False),
        "released_quarter": released_quarter,
        "currency": company["currency"],
        "ir_url": company["ir_url"],
        # ★ 时区校验提醒：LLM 必须校验 next_earnings_date/time 是否为北京时间
        "timezone_raw": cal.get("timezone_raw", ""),
        "timezone_reminder": TIMEZONE_REMINDER,
        "timezone_action_required": "LLM 必须校验上述 next_earnings_date/time 是否已转换为北京时间（UTC+8）。若仍为美东时间，请调用 update-next 命令修正。"
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def action_list(args) -> None:
    """列出所有公司"""
    lib = load_library()
    companies = lib.get("companies", [])
    if not companies:
        print(json.dumps({"status": "empty", "companies": []}, ensure_ascii=False))
        return
    summary = [
        {
            "ticker": c["ticker"],
            "name": c.get("company_name_cn", c["ticker"]),
            "next_earnings_date": c.get("next_earnings_date", ""),
            "next_quarter": c.get("next_quarter", ""),
            "next_earnings_status": c.get("next_earnings_status", "waiting"),
            "last_status": c.get("last_report_status", {}).get("status", "waiting"),
            "enabled": c.get("enabled", True)
        }
        for c in companies
    ]
    print(json.dumps({"status": "ok", "count": len(summary), "companies": summary}, ensure_ascii=False, indent=2))


def action_show(args) -> None:
    """查看单个公司详情"""
    lib = load_library()
    company = find_company(lib, args.ticker)
    if not company:
        print(json.dumps({"status": "not_found", "ticker": args.ticker}, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps({"status": "ok", "company": company}, ensure_ascii=False, indent=2))


def action_update_next(args) -> None:
    """
    更新下次财报日期

    ★ 时区校验：本命令写入的 date/time 必须为北京时间（UTC+8）。
    LLM 调用本命令前，若数据来源为 Finnhub 或其他美东时间源，必须先转换为北京时间。
    """
    lib = load_library()
    company = find_company(lib, args.ticker)
    if not company:
        print(json.dumps({"status": "not_found", "ticker": args.ticker}, ensure_ascii=False))
        sys.exit(1)
    company["next_earnings_date"] = args.date
    if args.time:
        company["next_earnings_time"] = args.time
    if args.quarter:
        company["next_quarter"] = args.quarter
    # ★ 更新 next_earnings_status 为 waiting（等待发布）
    company["next_earnings_status"] = "waiting"
    save_library(lib)
    print(json.dumps({
        "status": "updated",
        "ticker": args.ticker,
        "next_earnings_date": args.date,
        "next_earnings_time": company.get("next_earnings_time", ""),
        "next_earnings_status": "waiting",
        "timezone_reminder": TIMEZONE_REMINDER,
        "timezone_action_required": "LLM 必须确认写入的 date/time 为北京时间（UTC+8）。若数据来源为美东时间，请先转换。"
    }, ensure_ascii=False, indent=2))


def action_update_status(args) -> None:
    """
    更新报告状态（waiting → completed / failed）

    ★ 当 status=completed 时，自动回写下一次财报信息：
    1. 更新 last_report_status 为 completed
    2. 自动调用 Finnhub API 拉取下一次财报日期（或使用 --next-date 手动指定）
    3. 更新 next_earnings_date/time/next_quarter 为下一次财报
    4. 更新 next_earnings_status = "waiting"（等待下一次发布）
    """
    lib = load_library()
    company = find_company(lib, args.ticker)
    if not company:
        print(json.dumps({"status": "not_found", "ticker": args.ticker}, ensure_ascii=False))
        sys.exit(1)
    valid_statuses = {"waiting", "completed", "failed"}
    if args.status not in valid_statuses:
        print(json.dumps({"status": "error", "reason": f"非法状态: {args.status}, 允许: {valid_statuses}"}, ensure_ascii=False))
        sys.exit(1)

    # 更新 last_report_status
    company["last_report_status"] = {
        "quarter": args.quarter or company.get("last_report_status", {}).get("quarter", ""),
        "generated_at": now_iso() if args.status == "completed" else "",
        "report_path": args.path or "",
        "status": args.status
    }

    # ★ 当 status=completed 时，自动回写下一次财报信息
    next_earnings_updated = False
    if args.status == "completed":
        # 优先使用手动指定的 --next-date
        if args.next_date:
            company["next_earnings_date"] = args.next_date
            if args.next_time:
                company["next_earnings_time"] = args.next_time
            if args.next_quarter:
                company["next_quarter"] = args.next_quarter
            company["next_earnings_status"] = "waiting"
            next_earnings_updated = True
        else:
            # ★ 自动调用 Finnhub API 拉取下一次财报日期
            try:
                api_key = get_finnhub_key()
                cal = fetch_earnings_calendar(args.ticker, api_key)
                if cal and cal.get("date"):
                    # ★ 确保拉取的是未来的财报（严格大于今天，避免重复触发）
                    today_str = datetime.now(BJT).date().isoformat()
                    if cal["date"] > today_str:
                        company["next_earnings_date"] = cal["date"]
                        company["next_earnings_time"] = f"{cal.get('hour', '')}:{cal.get('minute', '')}".strip(":")
                        # 解析季度标识
                        if cal.get("quarter") and cal.get("year"):
                            company["next_quarter"] = f"Q{cal['quarter']} {cal['year']}"
                        company["next_earnings_status"] = "waiting"
                        next_earnings_updated = True
                    else:
                        # 未拉取到未来财报，保持空值
                        company["next_earnings_date"] = ""
                        company["next_earnings_time"] = ""
                        company["next_quarter"] = ""
                        company["next_earnings_status"] = "waiting"
                        next_earnings_updated = True
                else:
                    # API 无返回，保持空值
                    company["next_earnings_date"] = ""
                    company["next_earnings_time"] = ""
                    company["next_quarter"] = ""
                    company["next_earnings_status"] = "waiting"
                    next_earnings_updated = True
            except Exception as e:
                # ★ API 调用失败：next_earnings_date 保持空，next_earnings_status 保持 waiting
                # 空日期不会被 action_today 命中（不会重复触发），但等待兜底任务补全
                print(f"[WARN] 拉取 {args.ticker} 下一次财报失败: {e}", file=sys.stderr)
                company["next_earnings_date"] = ""
                company["next_earnings_time"] = ""
                company["next_quarter"] = ""
                company["next_earnings_status"] = "waiting"
                next_earnings_updated = True

    save_library(lib)

    result = {
        "status": "updated",
        "ticker": args.ticker,
        "report_status": args.status,
        "next_earnings_updated": next_earnings_updated,
        "next_earnings_date": company.get("next_earnings_date", ""),
        "next_earnings_time": company.get("next_earnings_time", ""),
        "next_quarter": company.get("next_quarter", ""),
        "next_earnings_status": company.get("next_earnings_status", "waiting"),
        # ★ 时区校验提醒：若 next_earnings_updated=True 且未传 --next-date（自动拉取 Finnhub），LLM 必须校验时区
        "timezone_reminder": TIMEZONE_REMINDER if (next_earnings_updated and not args.next_date) else "",
        "timezone_action_required": "若 next_earnings_date/time 来自 Finnhub 自动拉取（美东时间），LLM 必须校验并转换为北京时间（UTC+8），必要时调用 update-next 修正。" if (next_earnings_updated and not args.next_date) else ""
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def action_backfill_next(args) -> None:
    """
    ★ 兜底任务：检查所有 next_earnings_date 为空的公司，重新拉取 Finnhub 补全下一次财报信息

    使用场景：每次财报生成任务完毕后执行，确保所有公司的下一次财报信息完整。
    跳过条件：next_earnings_date 非空 或 next_earnings_status == "completed" 或 enabled == False
    """
    lib = load_library()
    companies = lib.get("companies", [])

    # ★ 筛选需要补全的公司：next_earnings_date 为空且未标记 completed 且 enabled
    need_backfill = [
        c for c in companies
        if not c.get("next_earnings_date")
        and c.get("next_earnings_status", "waiting") != "completed"
        and c.get("enabled", True)
    ]

    if not need_backfill:
        print(json.dumps({
            "status": "ok",
            "checked": len(companies),
            "need_backfill": 0,
            "backfilled": 0,
            "failed": 0,
            "message": "所有公司下一次财报信息完整，无需补全"
        }, ensure_ascii=False, indent=2))
        return

    print(f"[兜底补全] 发现 {len(need_backfill)} 家公司 next_earnings_date 为空，开始拉取 Finnhub API...", file=sys.stderr)

    api_key = get_finnhub_key()
    backfilled = []
    failed = []

    for company in need_backfill:
        ticker = company["ticker"]
        try:
            cal = fetch_earnings_calendar(ticker, api_key)
            if cal and cal.get("date"):
                today_str = datetime.now(BJT).date().isoformat()
                # ★ 只更新未来的财报日期（严格大于今天，避免重复触发）
                if cal["date"] > today_str:
                    company["next_earnings_date"] = cal["date"]
                    company["next_earnings_time"] = f"{cal.get('hour', '')}:{cal.get('minute', '')}".strip(":")
                    if cal.get("quarter") and cal.get("year"):
                        company["next_quarter"] = f"Q{cal['quarter']} {cal['year']}"
                    company["next_earnings_status"] = "waiting"
                    backfilled.append({
                        "ticker": ticker,
                        "next_earnings_date": cal["date"],
                        "next_quarter": company.get("next_quarter", "")
                    })
                    print(f"[兜底补全] {ticker} → {cal['date']} ({company.get('next_quarter', '')})", file=sys.stderr)
                else:
                    # API 返回的是已发布财报，不是未来的，保持空值
                    failed.append({"ticker": ticker, "reason": "API 仅返回已发布财报，无未来日期"})
            else:
                failed.append({"ticker": ticker, "reason": "API 无返回数据"})
        except Exception as e:
            failed.append({"ticker": ticker, "reason": str(e)})

    save_library(lib)

    result = {
        "status": "ok",
        "checked": len(companies),
        "need_backfill": len(need_backfill),
        "backfilled": len(backfilled),
        "failed": len(failed),
        "backfilled_list": backfilled,
        "failed_list": failed,
        # ★ 时区校验提醒：backfilled_list 中的 next_earnings_date/time 来自 Finnhub（美东时间），LLM 必须校验
        "timezone_reminder": TIMEZONE_REMINDER if backfilled else "",
        "timezone_action_required": "backfilled_list 中的 next_earnings_date/time 来自 Finnhub（美东时间 UTC-5/-4），LLM 必须校验并转换为北京时间（UTC+8），必要时调用 update-next 修正。" if backfilled else ""
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def action_remove(args) -> None:
    """移除公司"""
    lib = load_library()
    upper = args.ticker.upper()
    before = len(lib.get("companies", []))
    lib["companies"] = [c for c in lib.get("companies", []) if c.get("ticker", "").upper() != upper]
    after = len(lib["companies"])
    if before == after:
        print(json.dumps({"status": "not_found", "ticker": args.ticker}, ensure_ascii=False))
        sys.exit(1)
    save_library(lib)
    print(json.dumps({"status": "removed", "ticker": args.ticker}, ensure_ascii=False))


def action_today(args) -> None:
    """
    导出待处理财报公司列表（供定时任务调度使用）

    ★★★ 窗口匹配：过去 24 小时已发布未生成 + 今天即将发布 ★★★

    设计目标：
      避免昨天发布的财报在今天调度时漏报（旧逻辑 next_earnings_date == today 会漏）。

    窗口范围：[now - 24h, 今天 23:59:59]
      - 过去 24 小时已发布但未生成报告的公司（released=true）
      - 今天即将发布的公司（released=false，静默等待）
      - 明天及以后的公司不命中（避免提前触发）

    防重复机制：
      - last_report_status.status == "completed" → 跳过（已生成过报告）
      - 其余公司走后续 released 判断逻辑

    时区：所有时间均为北京时间（UTC+8），由 datetime.now(BJT) 获取真实系统时间。
    """
    lib = load_library()
    # ★ 获取真实系统北京时间，不依赖外部传入的时间信息
    now_bjt = datetime.now(BJT)
    today_str = now_bjt.date().isoformat()
    now_iso = now_bjt.isoformat(timespec="seconds")

    # ★ 窗口：[now - 24h, 今天 23:59:59]
    window_start = now_bjt - timedelta(hours=24)
    window_end = now_bjt.replace(hour=23, minute=59, second=59, microsecond=0)

    hits = []
    all_released = True  # 标记所有命中公司是否都已过发布时间
    for c in lib.get("companies", []):
        # ★ 跳过未启用公司
        if not c.get("enabled", True):
            continue
        # ★ 防重复：last_report_status.status == completed → 已生成过报告，跳过
        last_status = c.get("last_report_status", {})
        if last_status.get("status") == "completed":
            continue

        next_date_str = c.get("next_earnings_date", "")
        if not next_date_str:
            continue

        # ★ 解析发布日期
        try:
            release_date = datetime.strptime(next_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        # ★ 解析发布时间（HH:MM），默认 00:00
        release_time_str = c.get("next_earnings_time", "")
        if release_time_str:
            try:
                hh, mm = release_time_str.split(":")
                release_dt = datetime(release_date.year, release_date.month, release_date.day,
                                      int(hh), int(mm), 0, tzinfo=BJT)
            except (ValueError, AttributeError):
                # 时间格式异常，回退到当天 00:00
                release_dt = datetime(release_date.year, release_date.month, release_date.day,
                                      0, 0, 0, tzinfo=BJT)
        else:
            # 无发布时间，按当天 00:00 处理
            release_dt = datetime(release_date.year, release_date.month, release_date.day,
                                  0, 0, 0, tzinfo=BJT)

        # ★ 窗口匹配：[now - 24h, 今天 23:59:59]
        if not (window_start <= release_dt <= window_end):
            continue

        # ★ 判断当前时间是否已过发布时间
        released = now_bjt >= release_dt
        hours_until_release = (release_dt - now_bjt).total_seconds() / 3600.0

        if not released:
            all_released = False

        hits.append({
            "ticker": c["ticker"],
            "company_name_cn": c.get("company_name_cn", c["ticker"]),
            "next_earnings_date": next_date_str,
            "next_earnings_time": release_time_str,
            "next_quarter": c.get("next_quarter", ""),
            "next_earnings_status": c.get("next_earnings_status", "waiting"),
            "currency": c.get("currency", "USD"),
            "ir_url": c.get("ir_url", ""),
            "gelonghui_keyword": c.get("gelonghui_keyword", c["ticker"]),
            "futunn_keyword": c.get("futunn_keyword", c["ticker"]),
            # ★ 核心字段
            "released": released,
            "hours_until_release": round(hours_until_release, 2),
            "release_status": "已过发布时间，可执行就绪检查" if released else "未到发布时间，静默等待下一次调度"
        })

    print(json.dumps({
        "status": "ok",
        "today": today_str,
        # ★ 输出真实系统时间，供 LLM 校验
        "current_time": now_iso,
        "current_time_note": "★ 此为真实系统北京时间（UTC+8），LLM 必须以此时间为准，不得依赖 topics.md 或用户输入的调度说明中的时间。",
        # ★ 窗口范围（过去 24 小时 + 今天全天）
        "window": [window_start.isoformat(timespec="seconds"), window_end.isoformat(timespec="seconds")],
        "count": len(hits),
        "all_released": all_released if hits else None,
        "companies": hits,
        # ★ 调度决策建议
        "dispatch_advice": (
            "所有命中公司已过发布时间，可执行就绪检查" if hits and all_released
            else "存在未到发布时间的公司，静默等待下一次调度" if hits
            else "当日无财报更新，静默终止"
        )
    }, ensure_ascii=False, indent=2))


def action_import_presets(args) -> None:
    """批量导入预设（mag7 或自定义 ticker 列表）"""
    lib = load_library()

    # 确定 ticker 列表
    if args.preset:
        if args.preset not in PRESETS:
            print(json.dumps({"status": "error", "reason": f"未知预设: {args.preset}, 可用: {list(PRESETS.keys())}"}, ensure_ascii=False))
            sys.exit(1)
        tickers = PRESETS[args.preset]
    elif args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        print(json.dumps({"status": "error", "reason": "必须指定 --preset 或 --tickers"}, ensure_ascii=False))
        sys.exit(1)

    api_key = get_finnhub_key()
    added, skipped, failed = [], [], []

    for ticker in tickers:
        if find_company(lib, ticker):
            skipped.append(ticker)
            continue
        try:
            profile = fetch_profile(ticker, api_key)
            cal = fetch_earnings_calendar(ticker, api_key)
            # ★ 使用中文映射表获取中文名
            name_cn = get_company_name_cn(ticker, profile)
            company = {
                "ticker": ticker,
                "company_name_cn": name_cn,
                "company_name_en": profile.get("name", ""),
                "currency": profile.get("currency", "USD"),
                "exchange": profile.get("exchange", ""),
                "ir_url": profile.get("weburl", ""),
                "gelonghui_keyword": name_cn,
                "futunn_keyword": ticker,
                "next_earnings_date": cal.get("date", ""),
                "next_earnings_time": f"{cal.get('hour', '')}:{cal.get('minute', '')}".strip(":"),
                "next_quarter": "",
                # ★ next_earnings_status：下一次财报状态（waiting=待处理）
                "next_earnings_status": "waiting",
                # ★ 默认有电话会议；如需标记无电话会议，后续用 add --no-earnings-call 或手动修改
                "has_earnings_call": True,
                "last_report_status": {
                    "quarter": "",
                    "generated_at": "",
                    "report_path": "",
                    "status": "waiting"  # ★ 初始 waiting
                },
                "enabled": True,
                "created_at": now_iso()
            }
            lib["companies"].append(company)
            added.append(ticker)
        except Exception as e:
            failed.append({"ticker": ticker, "error": str(e)})

    save_library(lib)
    print(json.dumps({
        "status": "ok",
        "total_requested": len(tickers),
        "added": added,
        "skipped": skipped,
        "failed": failed,
        # ★ 时区校验提醒：新入库公司的 next_earnings_date/time 来自 Finnhub（美东时间），LLM 必须校验
        "timezone_reminder": TIMEZONE_REMINDER if added else "",
        "timezone_action_required": "added 列表中的公司 next_earnings_date/time 来自 Finnhub（美东时间 UTC-5/-4），LLM 必须校验并转换为北京时间（UTC+8），必要时调用 update-next 修正。" if added else ""
    }, ensure_ascii=False, indent=2))


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="公司库管理脚本（财报编排调度器父技能）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python library-manager.py --action add --ticker NVDA --name-cn 英伟达
  python library-manager.py --action list
  python library-manager.py --action show --ticker NVDA
  python library-manager.py --action update-next --ticker NVDA --date 2026-08-26 --time 05:00
  python library-manager.py --action update-status --ticker NVDA --status completed --quarter "Q2 FY2026" --path "reports/NVDA/nvidia-q2-fy2026-earnings.html"
  python library-manager.py --action remove --ticker NVDA
  python library-manager.py --action today
  python library-manager.py --action import-presets --preset mag7
  python library-manager.py --action import-presets --tickers "NVDA,TSLA,AMD"
  python library-manager.py --action backfill-next
        """
    )
    parser.add_argument("--action", required=True,
                        choices=["add", "list", "show", "update-next", "update-status", "backfill-next", "remove", "today", "import-presets"],
                        help="操作类型")
    parser.add_argument("--ticker", help="公司股票代码（如 NVDA）")
    parser.add_argument("--name-cn", help="公司中文名（add 时可选，默认用 Finnhub 返回的 name）")
    parser.add_argument("--quarter", help="季度标识（如 Q2 FY2026）")
    parser.add_argument("--date", help="下次财报日期（YYYY-MM-DD）")
    parser.add_argument("--time", help="下次财报时间（HH:MM）")
    parser.add_argument("--status", help="报告状态（waiting/completed/failed）")
    parser.add_argument("--path", help="报告路径（如 reports/NVDA/nvidia-q2-fy2026-earnings.html）")
    parser.add_argument("--next-date", help="下一次财报日期（YYYY-MM-DD，update-status status=completed 时可选，不传则自动拉取 Finnhub）")
    parser.add_argument("--next-time", help="下一次财报时间（HH:MM，与 --next-date 配合使用）")
    parser.add_argument("--next-quarter", help="下一次财报季度（如 Q3 2026，与 --next-date 配合使用）")
    parser.add_argument("--preset", help="预设名称（如 mag7）")
    parser.add_argument("--tickers", help="自定义 ticker 列表，逗号分隔（如 NVDA,TSLA,AMD）")
    # ★ 无电话会议公司标记：部分公司发布财报但不召开电话会议，就绪检查只查 1+3
    parser.add_argument("--no-earnings-call", action="store_true", help="标记本公司无电话会议（就绪检查跳过检查项2，只查 1+3）")

    args = parser.parse_args()

    # 参数校验
    actions_need_ticker = {"add", "show", "update-next", "update-status", "remove"}
    if args.action in actions_need_ticker and not args.ticker:
        parser.error(f"action {args.action} 需要 --ticker 参数")

    # 分发
    dispatch = {
        "add": action_add,
        "list": action_list,
        "show": action_show,
        "update-next": action_update_next,
        "update-status": action_update_status,
        "backfill-next": action_backfill_next,
        "remove": action_remove,
        "today": action_today,
        "import-presets": action_import_presets,
    }
    dispatch[args.action](args)


if __name__ == "__main__":
    main()
