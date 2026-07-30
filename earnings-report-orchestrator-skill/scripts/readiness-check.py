#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
就绪检查脚本（跨平台 Python 3.8+）

功能：
  - 对指定公司执行就绪检查三验证：
    ① 财报是否已发布（IR 页面有最新季度财报链接）
    ② 电话会议是否已结束（IR 页面有 replay/audio 链接，或媒体报道"电话会议结束"）
    ③ 格隆汇/富途是否已发布财报分析文章
  - 输出待检查 URL 列表 + 判定规则（LLM 用 WebFetch 完成实际抓取并回填结果）
  - 支持 --result-file 参数回填检查结果，输出最终就绪判定

设计原则：
  - 脚本不直接抓取页面（避免反爬、兼容不同 agent）
  - 脚本输出检查任务清单，LLM 执行 WebFetch 后回填 JSON 结果
  - 保守策略：三项全 PASS 才 ready=true

依赖：Python 3.8+ 标准库 + requests（可选，用于辅助检查）
用法见 SKILL.md 阶段 2
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ============================================================
# 常量
# ============================================================

BJT = timezone(timedelta(hours=8))
SCRIPT_DIR = Path(__file__).resolve().parent
PARENT_SKILL_DIR = SCRIPT_DIR.parent
LIBRARY_FILE = PARENT_SKILL_DIR / "company-library.json"


# ============================================================
# 工具函数
# ============================================================

def now_iso() -> str:
    return datetime.now(BJT).isoformat(timespec="seconds")


def today_str() -> str:
    return datetime.now(BJT).date().isoformat()


def load_library() -> dict:
    if not LIBRARY_FILE.exists():
        return {"version": "1.0", "last_updated": "", "companies": []}
    with LIBRARY_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_company(lib: dict, ticker: str) -> dict | None:
    upper = ticker.upper()
    for c in lib.get("companies", []):
        if c.get("ticker", "").upper() == upper:
            return c
    return None


# ============================================================
# 检查任务生成
# ============================================================

def build_check_tasks(company: dict, quarter: str) -> dict:
    """
    根据公司信息构建检查任务清单（供 LLM 用 WebFetch 执行）

    ★ 无电话会议公司处理（LLM 必读）：
    - 公司库字段 has_earnings_call（默认 True）标记公司是否有电话会议
    - 若 has_earnings_call=False（如部分公司不发电话会议）：
      → 检查项 2_earnings_call_ended 标记为 skipped（无需检查）
      → pass_criteria.ready 改为"1 + 3"（不需要 2）
    - 若 has_earnings_call=True（默认）：
      → 检查项 2_earnings_call_ended 必须检查
      → pass_criteria.ready 为"1 + 2 + 3"（全部 PASS）
    """
    ticker = company.get("ticker", "")
    ir_url = company.get("ir_url", "")
    gelonghui_kw = company.get("gelonghui_keyword", ticker)
    futunn_kw = company.get("futunn_keyword", ticker)
    today = today_str()
    # ★ 读取是否有电话会议（默认 True）
    has_earnings_call = company.get("has_earnings_call", True)

    # ★ 根据是否有电话会议，构建检查项2
    if has_earnings_call:
        task_2 = {
            "desc": "电话会议是否已结束",
            "method": "WebFetch",
            "urls": [ir_url] if ir_url else [],
            "fallback_urls": [
                f"https://www.gelonghui.com/search?q={gelonghui_kw}+电话会议",
                f"https://www.futunn.com/search?q={futunn_kw}+earnings+call"
            ],
            "rules": [
                f"IR 页面存在 audio replay / webcast replay 链接，标题包含 {quarter}",
                "或财经媒体报道'电话会议结束/会议要点/会议纪要'",
                "返回证据：replay 链接 URL 或媒体报道 URL"
            ],
            "required": True
        }
        ready_criteria = "三项全部 PASS（含 media_updated 至少一家）"
    else:
        # ★ 无电话会议：检查项2 跳过，ready 只需 1 + 3
        task_2 = {
            "desc": "电话会议检查（★ 本公司无电话会议，自动跳过）",
            "method": "skip",
            "urls": [],
            "rules": ["公司库 has_earnings_call=False，此项自动 PASS，无需 WebFetch"],
            "required": False,
            "skipped": True,  # ★ 标记跳过，action_evaluate 据此跳过判定
            "default_passed": True
        }
        ready_criteria = "1 + 3 两项 PASS（本公司无电话会议，跳过检查项2）"

    tasks = {
        "checklist": {
            "1_earnings_released": {
                "desc": "财报是否已发布",
                "method": "WebFetch",
                "urls": [ir_url] if ir_url else [],
                "rules": [
                    f"页面存在包含 {quarter} 关键词的财报链接（PDF / news / press release）",
                    f"链接发布时间 >= {company.get('next_earnings_date', today)} {company.get('next_earnings_time', '')}",
                    "返回证据：财报链接 URL + 发布时间"
                ],
                "required": True
            },
            "2_earnings_call_ended": task_2,
            "3a_gelonghui_updated": {
                "desc": "格隆汇是否已发布财报分析文章",
                "method": "WebFetch",
                "urls": [
                    f"https://www.gelonghui.com/search?q={gelonghui_kw}+{quarter}",
                    f"https://www.gelonghui.com/search?q={gelonghui_kw}+财报"
                ],
                "rules": [
                    f"搜索结果中有标题包含 {gelonghui_kw} + ({quarter} 或 '财报' 或 '业绩') 的文章",
                    f"文章发布日期 = {today}",
                    "返回证据：文章 URL + 标题 + 发布日期"
                ],
                "required": False  # 3a 和 3b 至少一项 PASS 即可
            },
            "3b_futunn_updated": {
                "desc": "富途是否已发布财报分析文章",
                "method": "WebFetch",
                "urls": [
                    f"https://www.futunn.com/search?q={futunn_kw}+{quarter}",
                    f"https://www.futunn.com/search?q={futunn_kw}+财报"
                ],
                "rules": [
                    f"搜索结果中有标题包含 {futunn_kw} + ({quarter} 或 '财报' 或 '业绩') 的文章",
                    f"文章发布日期 = {today}",
                    "返回证据：文章 URL + 标题 + 发布日期"
                ],
                "required": False  # 3a 和 3b 至少一项 PASS 即可
            }
        },
        "pass_criteria": {
            "1_earnings_released": "passed == true",
            "2_earnings_call_ended": "passed == true" if has_earnings_call else "skipped (has_earnings_call=false)",
            "media_updated": "3a_gelonghui_updated.passed == true OR 3b_futunn_updated.passed == true",
            "ready": ready_criteria
        },
        # ★ 元信息：供 action_evaluate 读取，决定是否跳过检查项2
        "meta": {
            "has_earnings_call": has_earnings_call
        }
    }
    return tasks


# ============================================================
# 检查任务执行（输出任务清单，等待 LLM 回填）
# ============================================================

def action_check(args) -> None:
    """输出就绪检查任务清单（LLM 用 WebFetch 执行后回填 --result-file）"""
    lib = load_library()
    company = find_company(lib, args.ticker)
    if not company:
        print(json.dumps({"status": "not_found", "ticker": args.ticker}, ensure_ascii=False))
        sys.exit(1)

    quarter = args.quarter or company.get("next_quarter", "")
    if not quarter:
        print(json.dumps({"status": "error", "reason": "未指定 --quarter，且公司库中 next_quarter 为空"}, ensure_ascii=False))
        sys.exit(1)

    tasks = build_check_tasks(company, quarter)
    output = {
        "ticker": args.ticker.upper(),
        "quarter": quarter,
        "check_time": now_iso(),
        "company_info": {
            "name": company.get("company_name_cn", ""),
            "ir_url": company.get("ir_url", ""),
            "gelonghui_keyword": company.get("gelonghui_keyword", ""),
            "futunn_keyword": company.get("futunn_keyword", ""),
            "next_earnings_date": company.get("next_earnings_date", ""),
            "next_earnings_time": company.get("next_earnings_time", ""),
            # ★ 暴露 has_earnings_call 给 LLM，便于回填时保留
            "has_earnings_call": company.get("has_earnings_call", True)
        },
        "tasks": tasks,
        # ★ 顶层 meta 便于 action_evaluate 读取（LLM 回填时应保留此字段）
        "meta": {
            "has_earnings_call": company.get("has_earnings_call", True)
        },
        "next_step": "LLM 用 WebFetch 抓取 tasks.checklist 中每个任务的 urls（跳过 method=skip 的项），按 rules 判定后，将结果写入 JSON 文件（保留 meta 字段），再以 --result-file 参数回填本脚本"
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ============================================================
# 结果回填与最终判定
# ============================================================

def action_evaluate(args) -> None:
    """
    根据 LLM 回填的检查结果，输出最终就绪判定（★ 支持无电话会议公司）

    ★ 无电话会议公司处理（LLM 必读）：
    - 优先从 results.meta.has_earnings_call 读取（build_check_tasks 写入）
    - 其次从公司库读取 has_earnings_call（默认 True）
    - 若 has_earnings_call=False：
      → earnings_call_ended 自动视为 True（跳过）
      → ready = earnings_released and media_updated（不需要电话会议）
    - 若 has_earnings_call=True（默认）：
      → ready = earnings_released and earnings_call_ended and media_updated（三项全 PASS）
    """
    if not args.result_file:
        print(json.dumps({"status": "error", "reason": "需要 --result-file 参数指定 LLM 回填的结果 JSON 文件"}, ensure_ascii=False))
        sys.exit(1)

    result_path = Path(args.result_file)
    if not result_path.exists():
        print(json.dumps({"status": "error", "reason": f"结果文件不存在: {args.result_file}"}, ensure_ascii=False))
        sys.exit(1)

    with result_path.open("r", encoding="utf-8") as f:
        results = json.load(f)

    # ★ 读取是否有电话会议：优先 results.meta，其次公司库，默认 True
    has_earnings_call = results.get("meta", {}).get("has_earnings_call", None)
    if has_earnings_call is None:
        lib = load_library()
        company = find_company(lib, args.ticker)
        has_earnings_call = company.get("has_earnings_call", True) if company else True

    # 校验结果结构
    checklist = results.get("checklist", results)
    earnings_released = checklist.get("1_earnings_released", {}).get("passed", False)
    # ★ 无电话会议时，检查项2 自动 True
    earnings_call_ended = True if not has_earnings_call else checklist.get("2_earnings_call_ended", {}).get("passed", False)
    gelonghui_updated = checklist.get("3a_gelonghui_updated", {}).get("passed", False)
    futunn_updated = checklist.get("3b_futunn_updated", {}).get("passed", False)
    media_updated = gelonghui_updated or futunn_updated

    # ★ 根据 has_earnings_call 决定 ready 逻辑
    if has_earnings_call:
        ready = earnings_released and earnings_call_ended and media_updated
        summary = "三项全部 PASS，可调用子技能生成报告" if ready else "存在未通过项，等下一次调度"
    else:
        # 无电话会议：只需 1 + 3
        ready = earnings_released and media_updated
        summary = "1+3 两项 PASS（无电话会议），可调用子技能生成报告" if ready else "存在未通过项，等下一次调度"

    output = {
        "ticker": results.get("ticker", args.ticker.upper()),
        "quarter": results.get("quarter", ""),
        "check_time": now_iso(),
        "has_earnings_call": has_earnings_call,
        "earnings_released": {
            "passed": earnings_released,
            "evidence": checklist.get("1_earnings_released", {}).get("evidence", "")
        },
        "earnings_call_ended": {
            "passed": earnings_call_ended,
            "skipped": not has_earnings_call,  # ★ 标记是否跳过
            "evidence": checklist.get("2_earnings_call_ended", {}).get("evidence", "") if has_earnings_call else "本公司无电话会议，自动跳过"
        },
        "media_updated": {
            "gelonghui": {"passed": gelonghui_updated, "evidence": checklist.get("3a_gelonghui_updated", {}).get("evidence", "")},
            "futunn": {"passed": futunn_updated, "evidence": checklist.get("3b_futunn_updated", {}).get("evidence", "")}
        },
        "ready": ready,
        "summary": summary
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="就绪检查脚本（父技能 earnings-report-orchestrator）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
工作流：
  步骤1: python readiness-check.py --ticker NVDA --quarter "Q2 FY2026"
          → 输出检查任务清单 JSON（含待抓取 URL 和判定规则）
  步骤2: LLM 用 WebFetch 抓取清单中的 URL，按规则判定每项 passed=true/false
          → 将结果写入 result.json
  步骤3: python readiness-check.py --ticker NVDA --evaluate --result-file result.json
          → 输出最终就绪判定（ready=true/false）

示例:
  python readiness-check.py --ticker NVDA --quarter "Q2 FY2026"
  python readiness-check.py --ticker NVDA --evaluate --result-file /tmp/nvda-check-result.json
        """
    )
    parser.add_argument("--ticker", required=True, help="公司股票代码")
    parser.add_argument("--quarter", help="季度标识（如 Q2 FY2026）")
    parser.add_argument("--evaluate", action="store_true", help="回填模式：根据 --result-file 输出最终判定")
    parser.add_argument("--result-file", help="LLM 回填的检查结果 JSON 文件路径")

    args = parser.parse_args()

    if args.evaluate:
        action_evaluate(args)
    else:
        action_check(args)


if __name__ == "__main__":
    main()
