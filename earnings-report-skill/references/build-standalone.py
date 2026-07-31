#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨平台单文件构建脚本

合并自原 build-standalone.ps1 + build-standalone.sh，单文件覆盖 Windows/Mac/Linux。

处理步骤：
  1. 读取源 HTML、echarts.min.js、charts.js
  2. 转义 JS 中的 </script> 为 <\\/script>，避免内联后提前闭合标签
  3. 将 <script src="./_shared/js/echarts.min.js"></script> 替换为内联 <script>
  4. 将 <script src="assets/charts.js"></script> 替换为内联 <script>
  5. 输出单文件到输出目录（目录不存在则自动创建）

输出目录优先级：--output-dir 参数 → config.paths.output_dir → 平台默认值

用法：
  python build-standalone.py --source-dir /path/to/source-dir
  python build-standalone.py --source-dir /path/to/source-dir --output-dir /tmp/output
"""
import sys
import os
import re
import json
import argparse
import platform
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
COLOR_CYAN = '\033[36m'
COLOR_GREEN = '\033[32m'
COLOR_YELLOW = '\033[33m'
COLOR_RED = '\033[31m'
COLOR_GRAY = '\033[90m'
COLOR_RESET = '\033[0m'

if sys.platform == 'win32':
    os.system('')


def log(msg, level='INFO'):
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
SCRIPT_DIR = Path(__file__).resolve().parent  # references/
SKILL_ROOT = SCRIPT_DIR.parent                # skill 根
CONFIG_FILE = SKILL_ROOT / 'config.local.json'


def load_config():
    """加载 config.local.json"""
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def get_nested(obj, *keys, default=''):
    cur = obj
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur if cur else default


def resolve_output_dir(arg_output_dir, config):
    """解析仓库根目录优先级：参数 → 代码推导(output_root/Output/项目名) → 抛错"""
    if arg_output_dir:
        return arg_output_dir
    # 推导仓库根目录：output_root/Output/项目名
    output_root = get_nested(config, 'paths', 'output_root')
    github_repo = get_nested(config, 'deployment', 'github', 'repo')
    project_name = github_repo.split('/')[-1] if github_repo else ''
    if output_root and project_name:
        return os.path.join(output_root, 'Output', project_name)
    # 无法推导，抛错提示用户配置
    raise RuntimeError(
        "无法推导仓库根目录。请确保 config.local.json 的 paths.output_root "
        "（盘符+文件夹，如 d:/TraeAutomaticTools）和 deployment.github.repo 已配置，"
        "或通过 --output-dir 参数传入。"
    )


def read_text_file(path):
    """读取文本文件（UTF-8，自动去 BOM）"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到文件: {path}")
    with open(path, 'r', encoding='utf-8-sig') as f:
        return f.read()


def escape_script_close(js):
    """转义 JS 中的 </script> 为 <\\/script>"""
    return re.sub(r'(?i)</script\s*>', '<\\/script>', js)


# echarts CDN 引用模板（与 report-template.md 保持一致）
ECHARTS_CDN_TAGS = '''<script src="https://cdn.staticfile.org/echarts/5.5.0/echarts.min.js"></script>
<script>window.echarts||document.write('<script src="https://cdn.bootcdn.net/ajax/libs/echarts/5.5.0/echarts.min.js"><\\/script>')</script>
<script>window.echarts||document.write('<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"><\\/script>')</script>'''


def detect_and_clean_inline_echarts(html):
    """
    检测并清理内联的 echarts.min.js（历史报告兼容）
    返回: (cleaned_html, was_cleaned)
    """
    import re
    was_cleaned = False

    # 特征 1：检测 <script src="./_shared/js/echarts.min.js"></script> 本地引用（旧模板）
    local_echarts_pattern = r'<script\s+src=["\']\./_shared/js/echarts\.min\.js["\']\s*></script>'
    if re.search(local_echarts_pattern, html, re.IGNORECASE):
        html = re.sub(local_echarts_pattern, '', html, flags=re.IGNORECASE)
        was_cleaned = True
        log("  检测到本地 echarts.min.js 引用，已移除", 'WARN')

    # 特征 2：检测内联的 echarts 库代码（大段 minified JS 含 echarts 标识）
    # echarts 库的特征字符串：包含 "zrender" 或 "echartsCharts" 或 "function(t,e,i)" 且长度 > 10000
    inline_pattern = r'<script>(.*?)</script>'
    for match in re.finditer(inline_pattern, html, re.DOTALL):
        script_content = match.group(1)
        # 检测 echarts 库特征
        has_echarts_marker = (
            ('zrender' in script_content and len(script_content) > 5000) or
            ('echartsCharts' in script_content) or
            ('echarts' in script_content and 'function(t,e,i)' in script_content and len(script_content) > 10000)
        )
        if has_echarts_marker:
            # 移除内联的 echarts 脚本块
            html = html.replace(match.group(0), '', 1)
            was_cleaned = True
            log(f"  检测到内联 echarts.min.js（{len(script_content)} 字符），已移除", 'WARN')
            break  # 只处理第一个匹配

    # 如果进行了清理，在 charts.js 引用之前插入 CDN 引用
    if was_cleaned:
        charts_ref = '<script src="assets/charts.js"></script>'
        if charts_ref in html:
            html = html.replace(charts_ref, ECHARTS_CDN_TAGS + '\n' + charts_ref)
        else:
            # 如果 charts.js 已被内联，插入到 </body> 之前
            if '</body>' in html:
                html = html.replace('</body>', ECHARTS_CDN_TAGS + '\n</body>')
        log("  已插入 echarts CDN 引用（onerror 链式回退）", 'GRAY')

    return html, was_cleaned


# ============================================================
# 主流程
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='跨平台单文件构建脚本（将多文件 HTML 合并为单文件）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--source-dir', '-s', required=True,
                        help='报告源目录（必需，应包含 index.html/_shared/js/echarts.min.js/assets/charts.js）')
    parser.add_argument('--output-dir', '-o', default='',
                        help='输出根目录（可选，默认从配置读取）')
    parser.add_argument('--ticker', '-t', default='',
                        help='股票代码大写（如 NVDA），用于创建 reports/{TICKER}/ 子目录。留空时输出到输出根目录')
    args = parser.parse_args()

    source_dir = os.path.abspath(args.source_dir)
    if not os.path.isdir(source_dir):
        log(f"[错误] 找不到报告源目录: {source_dir}", 'ERROR')
        sys.exit(1)

    report_name = os.path.basename(source_dir)

    # 查找 HTML 文件
    html_path = os.path.join(source_dir, f"{report_name}.html")
    if not os.path.isfile(html_path):
        html_path = os.path.join(source_dir, 'index.html')
    if not os.path.isfile(html_path):
        log(f"[错误] 找不到源 HTML: {html_path}", 'ERROR')
        sys.exit(1)

    charts_path = os.path.join(source_dir, 'assets', 'charts.js')

    # 加载配置 + 解析输出目录
    config = load_config()
    output_root = resolve_output_dir(args.output_dir, config)
    # 有 ticker 时输出到 reports/{TICKER}/ 子目录（每个公司用子文件夹隔离）
    if args.ticker:
        ticker = args.ticker.strip().upper()
        output_dir = os.path.join(output_root, 'reports', ticker)
    else:
        output_dir = output_root
    output_file = os.path.join(output_dir, f"{report_name}.html")

    # 校验源文件（charts.js 必须存在，echarts 走 CDN 无需本地文件）
    if not os.path.isfile(charts_path):
        log(f"[错误] 找不到文件: {charts_path}", 'ERROR')
        sys.exit(1)

    log(f"正在构建单文件报告 (跨平台版): {report_name}", 'CYAN')
    log(f"  源目录: {source_dir}", 'GRAY')
    log(f"  HTML:   {html_path}", 'GRAY')
    log(f"  输出到: {output_file}", 'GRAY')

    # 1. 读取源文件
    html = read_text_file(html_path)
    charts_js = read_text_file(charts_path)

    # 2. 转义 JS 中的 </script>
    charts_js = escape_script_close(charts_js)

    # 3. ★ echarts 走 CDN + onerror 链式回退（不再内联）
    #    模板中已是 CDN 引用 + document.write 回退链，无需替换
    #    回退链：Staticfile → BootCDN → jsDelivr → 本地 ./_shared/js/echarts.min.js
    log("  echarts 走 CDN 引用（onerror 链式回退）", 'GRAY')

    # 3.5 ★ 历史报告兼容：检测并清理内联的 echarts.min.js
    html, echarts_cleaned = detect_and_clean_inline_echarts(html)
    if echarts_cleaned:
        log("  ★ 已清理内联 echarts.min.js，替换为 CDN 引用", 'WARN')

    # 4. 内联 charts.js（使用字符串精确匹配）
    charts_ref_tag = '<script src="assets/charts.js"></script>'
    charts_inline_tag = '<script>\n' + charts_js + '\n</script>'
    if charts_ref_tag in html:
        html = html.replace(charts_ref_tag, charts_inline_tag)
        log("  内联脚本: charts.js", 'GRAY')
    else:
        log("警告: 未找到 charts.js 引用标签，跳过内联", 'WARN')

    # 5. 创建输出目录并写入单文件（UTF-8 无 BOM）
    os.makedirs(output_dir, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    size_kb = round(os.path.getsize(output_file) / 1024)
    log('', 'INFO')
    log(f"完成！单文件报告已生成: {output_file}", 'GREEN')
    log(f"文件大小: {size_kb:,} KB (echarts 走 CDN，charts.js 内联)", 'GREEN')

    sys.exit(0)


if __name__ == '__main__':
    main()
