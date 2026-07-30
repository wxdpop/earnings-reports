#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
子技能调度器（跨平台 Python 3.8+，统一 Python 调用）

功能：
  - 校验父技能初始化标记（.parent-init-done.json）
  - 校验子技能目录存在
  - 统一用 python 命令调用子技能脚本（子技能已统一 Python 单文件，无平台分支）
  - 解析 Python 绝对路径（agent 内置 > 系统 > sys.executable），避免 Windows Store stub 拦截
  - 输出子技能脚本调用序列（LLM 按此序列执行子技能 9 阶段工作流）

设计原则：
  - 脚本仅做参数封装和路径校验，不实际执行子技能脚本
  - 实际执行由 LLM 编排（保证灵活性、可观测性、错误处理）
  - 不改动子技能任何文件

依赖：Python 3.8+ 标准库
用法见 SKILL.md 阶段 3
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


# ============================================================
# 常量
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PARENT_SKILL_DIR = SCRIPT_DIR.parent
CONFIG_FILE = PARENT_SKILL_DIR / "config.local.json"
INIT_MARKER = PARENT_SKILL_DIR / ".parent-init-done.json"

IS_WINDOWS = platform.system() == 'Windows'
IS_MACOS = platform.system() == 'Darwin'
IS_LINUX = platform.system() == 'Linux'


# ============================================================
# 工具函数
# ============================================================

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print(json.dumps({"status": "error", "reason": f"配置文件不存在: {CONFIG_FILE}", "hint": "请先执行父技能初始化（阶段 -1）"}, ensure_ascii=False))
        sys.exit(1)
    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def check_init_marker() -> dict:
    """校验父技能初始化标记"""
    if not INIT_MARKER.exists():
        print(json.dumps({"status": "error", "reason": f"初始化标记不存在: {INIT_MARKER}", "hint": "请先执行父技能初始化（阶段 -1）"}, ensure_ascii=False))
        sys.exit(1)
    with INIT_MARKER.open("r", encoding="utf-8") as f:
        marker = json.load(f)
    if not marker.get("env_check_passed", False):
        print(json.dumps({"status": "error", "reason": "环境检测未通过", "marker": marker}, ensure_ascii=False))
        sys.exit(1)
    return marker


def detect_platform() -> str:
    """检测当前平台，返回 'windows' / 'macos' / 'linux'（仅用于缓存文件名后缀，不影响脚本调用方式）"""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "macos"
    elif system == "linux":
        return "linux"
    return "linux"  # 默认按 Linux 处理


# ============================================================
# Python 可执行文件解析（避免 Windows Store stub 拦截）
# ============================================================

def is_stub_exe(path):
    """检测路径是否为 Windows Store 0 字节 stub 文件"""
    if not path or not IS_WINDOWS:
        return False
    try:
        p = Path(path).resolve()
        winapps = os.environ.get('LOCALAPPDATA', '')
        if not winapps:
            return False
        winapps_dir = Path(winapps) / 'Microsoft' / 'WindowsApps'
        if not winapps_dir.exists():
            return False
        in_winapps = str(p).lower().startswith(str(winapps_dir.resolve()).lower().rstrip('\\'))
        if not in_winapps:
            return False
        return p.stat().st_size == 0
    except Exception:
        return False


def find_agent_python():
    """
    探测 TRAE agent 内置 Python（优先于系统 PATH）
    返回路径字符串或 None
    """
    candidates = []
    if IS_WINDOWS:
        base = os.environ.get('APPDATA', '')
        if base:
            candidates.append(Path(base) / 'TRAE SOLO CN' / 'ModularData' / 'ai-agent' / 'vm' / 'tools' / 'python' / 'python.exe')
            candidates.append(Path(base) / 'TRAE' / 'ModularData' / 'ai-agent' / 'vm' / 'tools' / 'python' / 'python.exe')
    elif IS_MACOS:
        home = os.path.expanduser('~')
        candidates.append(Path(home) / 'Library' / 'Application Support' / 'TRAE SOLO CN' / 'ModularData' / 'ai-agent' / 'vm' / 'tools' / 'python' / 'bin' / 'python3')
        candidates.append(Path(home) / 'Library' / 'Application Support' / 'TRAE' / 'ModularData' / 'ai-agent' / 'vm' / 'tools' / 'python' / 'bin' / 'python3')
    else:
        home = os.path.expanduser('~')
        candidates.append(Path(home) / '.config' / 'TRAE SOLO CN' / 'ModularData' / 'ai-agent' / 'vm' / 'tools' / 'python' / 'bin' / 'python3')
        candidates.append(Path(home) / '.config' / 'TRAE' / 'ModularData' / 'ai-agent' / 'vm' / 'tools' / 'python' / 'bin' / 'python3')

    for cand in candidates:
        try:
            if cand.exists() and cand.stat().st_size > 0:
                r = subprocess.run([str(cand), '--version'], capture_output=True, text=True, timeout=5, encoding='utf-8', errors='replace')
                if r.returncode == 0 and 'Python' in (r.stdout or ''):
                    return str(cand)
        except Exception:
            continue
    return None


def resolve_python_executable(cfg: dict, child_skill_dir: Path) -> str:
    """
    解析可用的 Python 可执行文件绝对路径
    优先级：
      1. config.local.json 的 python_executable 字段（初始化时探测并缓存）
      2. 子技能 .env-check-result.{platform}.json 缓存中的 py_executable
      3. sys.executable（当前正在运行 Python，肯定可用）
      4. agent 内置 Python（TRAE 沙箱）
      5. py launcher（Windows，跳过 stub）
      6. python3 / python（系统 PATH，跳过 stub）
      7. fallback "python"（最后兜底）
    """
    # 优先级 1：config.local.json 配置
    cfg_py = cfg.get("python_executable", "")
    if cfg_py and Path(cfg_py).exists() and not is_stub_exe(cfg_py):
        return cfg_py

    # 优先级 2：子技能环境检测缓存
    plat = detect_platform()
    cache_file = child_skill_dir / f".env-check-result.{plat}.json"
    if cache_file.exists():
        try:
            with cache_file.open("r", encoding="utf-8") as f:
                cache = json.load(f)
            cached_py = cache.get("py_executable", "")
            if cached_py and Path(cached_py).exists() and not is_stub_exe(cached_py):
                return cached_py
        except Exception:
            pass

    # 优先级 3：sys.executable（当前 Python）
    if sys.executable and sys.executable not in ('', 'python', 'python3'):
        try:
            exe = Path(sys.executable).resolve()
            if exe.exists() and exe.stat().st_size > 0 and not is_stub_exe(str(exe)):
                return str(exe)
        except Exception:
            pass

    # 优先级 4：agent 内置 Python
    p = find_agent_python()
    if p:
        return p

    # 优先级 5 & 6：系统 PATH 中的 python（跳过 stub）
    for cmd in ('python3', 'python'):
        found = shutil.which(cmd)
        if found and not is_stub_exe(found):
            try:
                r = subprocess.run([found, '--version'], capture_output=True, text=True, timeout=5, encoding='utf-8', errors='replace')
                if r.returncode == 0 and 'Python' in (r.stdout or ''):
                    return found
            except Exception:
                continue

    # Windows: py launcher
    if IS_WINDOWS:
        py_launcher = shutil.which('py')
        if py_launcher and not is_stub_exe(py_launcher):
            try:
                r = subprocess.run([py_launcher, '--version'], capture_output=True, text=True, timeout=5, encoding='utf-8', errors='replace')
                if r.returncode == 0 and 'Python' in (r.stdout or ''):
                    return py_launcher
            except Exception:
                pass

    # 兜底（带告警，可能被 stub 拦截）
    print(json.dumps({"status": "warn", "reason": "未能解析到可靠的 Python 绝对路径，回退到 'python'（可能受 Windows Store stub 影响）"}, ensure_ascii=False), file=sys.stderr)
    return "python"


def slugify(name: str, ticker: str = "") -> str:
    """
    将公司名转换为 slug（小写英文无空格）
    - 中文名（非 ASCII）→ 用 ticker 小写作为 slug
    - 英文名 → 保留字母数字，其余转小写
    """
    # 检测是否包含非 ASCII 字符（中文等）
    has_non_ascii = any(ord(c) > 127 for c in name)
    if has_non_ascii:
        # 中文名 → 用 ticker 小写
        return ticker.lower() if ticker else "company"
    # 英文名 → 保留字母数字
    slug = "".join(c.lower() if c.isalnum() else "" for c in name).strip()
    return slug if slug else (ticker.lower() if ticker else "company")


def quarter_to_slug(quarter: str) -> str:
    """将季度标识转换为路径 slug（如 'Q2 FY2026' → 'q2-fy2026'）"""
    return quarter.lower().replace(" ", "-").replace("fy", "fy")


# ============================================================
# 主逻辑
# ============================================================

def build_dispatch_plan(args) -> dict:
    """构建子技能调用计划（统一 Python 调用）"""
    cfg = load_config()
    marker = check_init_marker()

    child_skill_dir = Path(cfg.get("child_skill_dir", ""))
    if not child_skill_dir.exists():
        print(json.dumps({"status": "error", "reason": f"子技能目录不存在: {child_skill_dir}"}, ensure_ascii=False))
        sys.exit(1)

    # 推导仓库根目录：output_root/Output/项目名（不再从 paths.output_dir/repo_dir 读取）
    output_root = cfg.get("paths", {}).get("output_root", "")
    github_repo = cfg.get("deployment", {}).get("github", {}).get("repo", "")
    project_name = github_repo.split('/')[-1] if github_repo else ""
    if not output_root:
        print(json.dumps({"status": "error", "reason": "paths.output_root 未配置，请重新执行初始化（输出根目录在用户工作空间，盘符+文件夹）"}, ensure_ascii=False))
        sys.exit(1)
    if not project_name:
        print(json.dumps({"status": "error", "reason": "deployment.github.repo 未配置，无法推导仓库目录"}, ensure_ascii=False))
        sys.exit(1)
    repo_root = Path(output_root) / "Output" / project_name
    # output_dir/repo_dir 统一指向 repo_root（向后兼容变量名）
    output_dir = repo_root
    repo_dir = repo_root

    ticker = args.ticker.upper()
    quarter = args.quarter
    plat = detect_platform()  # 仅用于缓存文件名后缀

    # 从公司库读取公司名（用于生成 slug）
    company_name = ticker
    lib_file = PARENT_SKILL_DIR / "company-library.json"
    if lib_file.exists():
        with lib_file.open("r", encoding="utf-8") as f:
            lib = json.load(f)
        for c in lib.get("companies", []):
            if c.get("ticker", "").upper() == ticker:
                company_name = c.get("company_name_cn", c.get("company_name_en", ticker))
                break

    company_slug = slugify(company_name, ticker)
    quarter_slug = quarter_to_slug(quarter)
    ticker_lower = ticker.lower()
    filename = f"{company_slug}-{quarter_slug}-earnings.html"
    report_path = f"reports/{ticker}/{filename}"

    # 子技能脚本路径（统一 Python，无 .ps1/.sh 分支）
    child_scripts = child_skill_dir / "scripts"
    child_references = child_skill_dir / "references"

    # 数据目录
    data_dir = output_dir / "data" / f"{ticker_lower}-{quarter_slug}"

    # sections JSON 路径
    sections_json = output_dir / "data" / f"{ticker_lower}-{quarter_slug}-sections.json"

    # 构建中间产物目录
    intermediate_dir = output_dir / f"{company_slug}-{quarter_slug}-earnings"

    # 解析 Python 绝对路径（优先 agent 内置 → 配置缓存 → sys.executable → 系统 PATH）
    # 避免 Windows Store 0 字节 stub 拦截导致子技能脚本调用失败
    py_bin = resolve_python_executable(cfg, child_skill_dir)

    # ★ 根据部署配置动态生成阶段 8 note（Cloudflare 必选，GitHub 可选）
    deploy_targets = cfg.get("deployment", {}).get("targets", ["cloudflare"])
    has_github = "github" in deploy_targets
    if has_github:
        deploy_note = "git push → GitHub Pages（可选追加）；wrangler pages deploy → Cloudflare Pages（必选，从 cf-pages-deploy 父目录部署，保持 /reports/ 路径前缀）"
    else:
        deploy_note = "wrangler pages deploy → Cloudflare Pages（必选，从 cf-pages-deploy 父目录部署，保持 /reports/ 路径前缀）；跳过 git push（deployment.targets 不含 github）"

    plan = {
        "status": "ok",
        "platform": plat,
        "script_invocation": py_bin,  # 使用解析后的绝对路径（之前硬编码 "python"）
        "ticker": ticker,
        "quarter": quarter,
        "company_name": company_name,
        "company_slug": company_slug,
        "quarter_slug": quarter_slug,
        "filename": filename,
        "report_path": report_path,
        "child_skill_dir": str(child_skill_dir),
        "init_marker": {
            "initialized_at": marker.get("initialized_at", ""),
            "child_skill_version": marker.get("child_skill_version", ""),
            "env_check_passed": marker.get("env_check_passed", False)
        },
        "execution_sequence": [
            {
                "stage": 1,
                "name": "API 数据拉取",
                "command": f'"{py_bin}" "{child_scripts / "fetch-data.py"}"',
                "args": {
                    "symbol": ticker,
                    "out-dir": str(data_dir)
                },
                "note": "fetch-data 完成后自动调用 parse-financial-data.py 输出 6 季度财务摘要"
            },
            {
                "stage": "1.5",
                "name": "并行 WebFetch 多站点（★ Trae 用 Task 子代理）",
                "note": "LLM 并行 WebFetch 公司 IR + 格隆汇 + 富途 + 汇通财经 + 华盛通，汇总结构化摘要",
                "parallel": True
            },
            {
                "stage": 2,
                "name": "数据整理与汇率换算",
                "note": "LLM 完成（筛选专业来源、交叉验证、汇率换算）"
            },
            {
                "stage": 3,
                "name": "生成 sections JSON",
                "output_file": str(sections_json),
                "note": "LLM 按 templates/sections-reference.md 规范生成完整 sections JSON"
            },
            {
                "stage": 4,
                "name": "模板填充",
                "command": f'"{py_bin}" "{child_scripts / "fill-template.py"}"',
                "args": {
                    "template-file": str(child_references / "report-template.md"),
                    "sections-file": str(sections_json),
                    "output-file": str(intermediate_dir / "index.html")
                }
            },
            {
                "stage": 5,
                "name": "单文件构建",
                "command": f'"{py_bin}" "{child_references / "build-standalone.py"}"',
                "args": {
                    "source-dir": str(intermediate_dir)
                },
                "note": f"构建完成后移动到 {repo_dir / report_path}"
            },
            {
                "stage": 6,
                "name": "无头浏览器验证",
                "command": f'"{py_bin}" "{child_references / "verify-headless.py"}" "{repo_dir / report_path}"',
                "note": "验证项：图表≥2、StatCard≥4、参考资料≥5、外部依赖=0"
            },
            {
                "stage": "7-9",
                "name": "并行执行（★ Trae 用 Task 子代理）",
                "parallel": True,
                "sub_tasks": [
                    {
                        "sub_stage": 7,
                        "name": "资源清理",
                        "note": f"删除临时目录 {intermediate_dir}，保留 {data_dir}"
                    },
                    {
                        "sub_stage": 8,
                        "name": "部署（Cloudflare 必选 + GitHub 可选）",
                        "note": deploy_note
                    },
                    {
                        "sub_stage": 9,
                        "name": "飞书推送",
                        "command": f'"{py_bin}" "{child_references / "send-feishu.py"}"',
                        "args": {
                            "report-file": str(repo_dir / report_path)
                        }
                    }
                ]
            }
        ],
        "post_execution": {
            "update_status_command": f'"{py_bin}" "{SCRIPT_DIR / "library-manager.py"}" --action update-status --ticker {ticker} --status completed --quarter "{quarter}" --path "{report_path}"',
            "note": "报告生成完成后，调用此命令更新公司库状态为 completed"
        },
        "rollback_on_failure": {
            "update_status_command": f'"{py_bin}" "{SCRIPT_DIR / "library-manager.py"}" --action update-status --ticker {ticker} --status failed --quarter "{quarter}"',
            "note": "任一阶段失败时，调用此命令标记 status=failed，弹窗提示用户"
        }
    }
    return plan


def main():
    parser = argparse.ArgumentParser(
        description="子技能调度器（父技能 earnings-report-orchestrator，统一 Python 调用）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
功能：
  校验父技能初始化标记 + 子技能目录，输出子技能脚本调用序列。
  统一用 python 命令调用子技能脚本（子技能已统一 Python 单文件，无平台分支）。
  解析 Python 绝对路径（agent 内置 > 配置缓存 > sys.executable > 系统 PATH），避免 Windows Store stub 拦截。
  LLM 按序列执行子技能 9 阶段工作流（fetch-data → fill-template → build-standalone → verify-headless → 部署 → 飞书推送）。

示例:
  python dispatch-child-skill.py --ticker NVDA --quarter "Q2 FY2026"
        """
    )
    parser.add_argument("--ticker", required=True, help="公司股票代码（如 NVDA）")
    parser.add_argument("--quarter", required=True, help="季度标识（如 Q2 FY2026）")

    args = parser.parse_args()
    plan = build_dispatch_plan(args)
    print(json.dumps(plan, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
