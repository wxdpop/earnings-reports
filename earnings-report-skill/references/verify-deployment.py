#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨平台部署地址可达性验证脚本（阶段 8.5）

功能：
  - 验证 Cloudflare Pages URL（必选）和 GitHub Pages URL（可选）是否可达
  - HTTP GET 请求 + 状态码 + 响应内容校验
  - 失败时自动诊断原因（DNS / 网络 / 404 / 5xx / 部署未生效等）
  - 内置 3 次重试，间隔递增（5s / 15s / 30s），适配 Cloudflare Pages 部署延迟
  - 输出 JSON 结果，便于 LLM 编排
  - 3 次重试后仍失败则直接终止任务（exit 1），由 LLM 弹窗提示用户介入

用法：
  python verify-deployment.py \
      --cf-pages-url "https://earnings-reports.pages.dev/reports/NVDA/nvidia-q2-fy2026-earnings.html" \
      --ticker NVDA --quarter "Q2 FY2026"

  # 可选追加 GitHub Pages 验证
  python verify-deployment.py \
      --cf-pages-url "https://earnings-reports.pages.dev/reports/NVDA/nvidia-q2-fy2026-earnings.html" \
      --github-pages-url "https://wxdpop.github.io/earnings-reports/reports/NVDA/nvidia-q2-fy2026-earnings.html" \
      --ticker NVDA --quarter "Q2 FY2026"

退出码：
  0 = 全部 URL 验证通过
  1 = 任一 URL 3 次重试后仍失败（任务终止）
"""
import sys
import os
import json
import time
import socket
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
# 常量
# ============================================================
MAX_RETRIES = 3
RETRY_INTERVALS = [5, 15, 30]  # 秒，递增间隔
HTTP_TIMEOUT = 30  # 单次请求超时秒数
EXPECTED_CONTENT_HINTS = ['<html', '<!doctype html', '<head', '<body']  # 响应内容至少包含其一


# ============================================================
# 诊断函数
# ============================================================
def diagnose_failure(url: str, error: Exception, http_code: int = None, body_snippet: str = "") -> dict:
    """
    根据失败类型诊断原因并给出修复建议
    返回 {reason, suggestion, category}
    """
    err_str = str(error).lower() if error else ""
    host = url.split('/')[2] if '://' in url else url

    # DNS 解析失败
    if isinstance(error, socket.gaierror) or 'name or service not known' in err_str or 'getaddrinfo' in err_str or 'nodename nor servname' in err_str:
        return {
            "category": "dns",
            "reason": f"DNS 解析失败：{host} 无法解析。可能是域名配置错误、DNS 未生效，或本地网络/DNS 服务器问题。",
            "suggestion": "1) 检查 Cloudflare Pages 项目名是否正确；2) 等待 1-5 分钟 DNS 全球生效后重试；3) 切换 DNS（如 1.1.1.1 / 8.8.8.8）；4) 确认 wrangler pages deploy 已成功完成。",
        }

    # 连接超时 / 拒绝
    if isinstance(error, (socket.timeout, TimeoutError)) or 'timed out' in err_str or 'timeout' in err_str:
        return {
            "category": "timeout",
            "reason": f"连接超时：{host} 在 {HTTP_TIMEOUT}s 内未响应。可能是网络问题、服务未启动，或本地防火墙拦截。",
            "suggestion": "1) 检查本地网络是否正常；2) 确认 Cloudflare Pages 部署状态为 ready；3) 尝试访问同域名其他路径验证服务可用性；4) 关闭 VPN/代理后重试。",
        }
    if 'connection refused' in err_str or 'connection reset' in err_str:
        return {
            "category": "connection",
            "reason": f"连接被拒绝/重置：{host} 拒绝连接。服务可能未启动或端口不可达。",
            "suggestion": "1) 确认部署命令 wrangler pages deploy 已成功完成；2) 检查 Cloudflare Pages 项目状态；3) 等待 30s-2min 服务冷启动后重试。",
        }

    # SSL 证书问题
    if 'ssl' in err_str or 'certificate' in err_str:
        return {
            "category": "ssl",
            "reason": f"SSL 证书验证失败：{host} 证书无效或过期。",
            "suggestion": "1) Cloudflare Pages 默认提供有效证书，确认域名正确；2) 检查系统时间是否准确；3) 更新根证书。",
        }

    # HTTP 错误码
    if http_code is not None:
        if http_code == 404:
            return {
                "category": "not_found",
                "reason": f"HTTP 404：路径不存在。部署的文件路径与 URL 路径不匹配。\n  URL: {url}\n  可能原因：wrangler 部署目录错误（应从 cf-pages-deploy 父目录部署，保持 /reports/ 前缀），或文件名 slug 不一致。",
                "suggestion": "1) 检查 wrangler pages deploy 是否从包含 reports/ 子目录的父目录部署；2) 核对本地 reports/{TICKER}/{filename}.html 文件是否存在；3) 重新执行部署命令。",
            }
        if 500 <= http_code < 600:
            return {
                "category": "server_error",
                "reason": f"HTTP {http_code}：服务端错误。Cloudflare/GitHub 服务异常或部署文件损坏。",
                "suggestion": "1) 等待 1-2 分钟服务自愈后重试；2) 重新执行 wrangler pages deploy；3) 查看 Cloudflare Dashboard 部署日志。",
            }
        if http_code == 403:
            return {
                "category": "forbidden",
                "reason": f"HTTP 403：访问被拒绝。可能是仓库设为 private 或 Pages 访问权限限制。",
                "suggestion": "1) GitHub 仓库需为 public；2) GitHub Pages 设置中确认 source 为 main 分支；3) Cloudflare Pages 项目访问策略检查。",
            }
        if http_code == 301 or http_code == 302:
            return {
                "category": "redirect",
                "reason": f"HTTP {http_code}：重定向。URL 被重定向到其他地址。",
                "suggestion": "1) 检查 URL 是否正确；2) Cloudflare Pages 自定义域名重定向规则检查。",
            }
        return {
            "category": "http_error",
            "reason": f"HTTP {http_code}：未预期的状态码。",
            "suggestion": "1) 检查 URL 是否正确；2) 重新部署后重试。",
        }

    # 响应内容为空或不包含 HTML
    if body_snippet is not None and not any(hint in body_snippet.lower() for hint in EXPECTED_CONTENT_HINTS):
        return {
            "category": "empty_content",
            "reason": f"HTTP 200 但响应内容非 HTML（首 200 字符：{body_snippet[:200]}）。部署文件可能损坏或被覆盖。",
            "suggestion": "1) 检查本地 reports/{TICKER}/{filename}.html 文件是否完整；2) 重新执行 build-standalone.py + wrangler pages deploy。",
        }

    return {
        "category": "unknown",
        "reason": f"未知失败：{error or '无异常信息'}",
        "suggestion": "1) 检查 URL 是否可访问；2) 查看详细错误信息；3) 重新部署后重试。",
    }


# ============================================================
# 单次验证
# ============================================================
def verify_url_once(url: str) -> dict:
    """
    对单个 URL 执行一次 HTTP GET 验证
    返回 {passed, http_code, response_time_ms, body_snippet, error}
    """
    start = time.time()
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; EarningsReportVerifier/1.0)',
                'Accept': 'text/html,application/xhtml+xml',
            },
            method='GET',
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            body = resp.read(4096).decode('utf-8', errors='replace')  # 只读前 4KB 用于内容校验
            elapsed = int((time.time() - start) * 1000)
            http_code = resp.getcode()
            # 200 且内容包含 HTML 标志 → 通过
            if http_code == 200 and any(hint in body.lower() for hint in EXPECTED_CONTENT_HINTS):
                return {
                    "passed": True,
                    "http_code": http_code,
                    "response_time_ms": elapsed,
                    "body_snippet": body[:200],
                    "error": None,
                }
            # 200 但内容异常
            return {
                "passed": False,
                "http_code": http_code,
                "response_time_ms": elapsed,
                "body_snippet": body[:200],
                "error": None,
            }
    except urllib.error.HTTPError as e:
        elapsed = int((time.time() - start) * 1000)
        return {
            "passed": False,
            "http_code": e.code,
            "response_time_ms": elapsed,
            "body_snippet": "",
            "error": e,
        }
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        return {
            "passed": False,
            "http_code": None,
            "response_time_ms": elapsed,
            "body_snippet": "",
            "error": e,
        }


# ============================================================
# 带重试验证
# ============================================================
def verify_url_with_retry(url: str, label: str, max_retries: int = MAX_RETRIES) -> dict:
    """
    对单个 URL 执行带重试的验证
    返回 {url, label, passed, attempts, last_http_code, last_response_time_ms, diagnosis}
    """
    log(f"[验证] {label}: {url}", 'INFO')
    attempts = 0
    last_result = None
    while attempts < max_retries:
        attempts += 1
        result = verify_url_once(url)
        last_result = result
        if result["passed"]:
            log(f"  ✓ 第 {attempts} 次验证通过（HTTP {result['http_code']}, {result['response_time_ms']}ms）", 'OK')
            return {
                "url": url,
                "label": label,
                "passed": True,
                "attempts": attempts,
                "last_http_code": result["http_code"],
                "last_response_time_ms": result["response_time_ms"],
                "diagnosis": None,
            }
        # 失败
        if attempts < max_retries:
            wait = RETRY_INTERVALS[attempts - 1] if attempts - 1 < len(RETRY_INTERVALS) else 30
            log(f"  ✗ 第 {attempts} 次验证失败（HTTP {result['http_code']}, {result['response_time_ms']}ms），{wait}s 后重试...", 'WARN')
            time.sleep(wait)
        else:
            log(f"  ✗ 第 {attempts} 次验证失败（已用尽 {max_retries} 次重试）", 'ERROR')

    # 全部失败 → 诊断
    diagnosis = diagnose_failure(
        url,
        error=last_result["error"] if last_result else None,
        http_code=last_result["http_code"] if last_result else None,
        body_snippet=last_result["body_snippet"] if last_result else "",
    )
    return {
        "url": url,
        "label": label,
        "passed": False,
        "attempts": attempts,
        "last_http_code": last_result["http_code"] if last_result else None,
        "last_response_time_ms": last_result["response_time_ms"] if last_result else None,
        "diagnosis": diagnosis,
    }


# ============================================================
# 主流程
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='跨平台部署地址可达性验证脚本（阶段 8.5，3 次重试后终止）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--cf-pages-url', required=True, help='Cloudflare Pages URL（必选，始终验证）')
    parser.add_argument('--github-pages-url', default='', help='GitHub Pages URL（可选，仅 deployment.targets 含 github 时传入）')
    parser.add_argument('--ticker', required=True, help='公司股票代码（如 NVDA，用于日志标识）')
    parser.add_argument('--quarter', required=True, help='季度标识（如 Q2 FY2026，用于日志标识）')
    parser.add_argument('--max-retries', type=int, default=MAX_RETRIES, help=f'最大重试次数（默认 {MAX_RETRIES}）')
    args = parser.parse_args()

    log(f"========== 阶段 8.5 部署地址可达性验证 ==========", 'INFO')
    log(f"公司: {args.ticker} | 季度: {args.quarter}", 'INFO')
    log(f"最大重试次数: {args.max_retries}（间隔 {RETRY_INTERVALS}s 递增）", 'INFO')
    log(f"-" * 60, 'GRAY')

    # 构建待验证 URL 列表
    urls_to_verify = [
        {"url": args.cf_pages_url, "label": "Cloudflare Pages（主链接）"},
    ]
    if args.github_pages_url:
        urls_to_verify.append({"url": args.github_pages_url, "label": "GitHub Pages（备用链接）"})

    # 逐个验证
    results = []
    for item in urls_to_verify:
        result = verify_url_with_retry(item["url"], item["label"], max_retries=args.max_retries)
        results.append(result)

    # 汇总
    all_passed = all(r["passed"] for r in results)
    failed = [r for r in results if not r["passed"]]

    summary = {
        "status": "ok" if all_passed else "fail",
        "ticker": args.ticker,
        "quarter": args.quarter,
        "all_passed": all_passed,
        "verified_urls": results,
        "failed_count": len(failed),
        "max_retries": args.max_retries,
    }

    if all_passed:
        log(f"\n[✓] 全部 URL 验证通过，可继续阶段 9 飞书推送", 'OK')
    else:
        log(f"\n[✗] {len(failed)} 个 URL 在 {args.max_retries} 次重试后仍失败，任务终止", 'ERROR')
        for r in failed:
            log(f"  - {r['label']}: {r['url']}", 'ERROR')
            if r["diagnosis"]:
                log(f"    原因: {r['diagnosis']['reason']}", 'ERROR')
                log(f"    建议: {r['diagnosis']['suggestion']}", 'WARN')

    print("\n" + json.dumps(summary, ensure_ascii=False, indent=2))

    # 退出码：0=全部通过，1=有失败（任务终止）
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
