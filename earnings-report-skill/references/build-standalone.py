#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨平台单文件构建脚本（v5.5.0）

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
    """解析输出目录优先级：参数 → config.paths.output_dir → 抛错（★ v5.5.3 移除硬编码兜底）"""
    if arg_output_dir:
        return arg_output_dir
    cfg_output = get_nested(config, 'paths', 'output_dir')
    if cfg_output:
        return cfg_output
    # ★ v5.5.3：输出目录不在技能安装路径推断，必须由用户在 config.local.json 显式配置
    raise RuntimeError(
        "paths.output_dir 未配置。请在 config.local.json 的 paths.output_dir 填写输出根目录"
        "（如 d:/TraeAutomaticTools/Output/earnings-reports），或通过 --output-dir 参数传入。"
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
                        help='输出目录（可选，默认从配置读取）')
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
    output_dir = resolve_output_dir(args.output_dir, config)
    output_file = os.path.join(output_dir, f"{report_name}.html")

    # 校验源文件（charts.js 必须存在，echarts 走 CDN 无需本地文件）
    if not os.path.isfile(charts_path):
        log(f"[错误] 找不到文件: {charts_path}", 'ERROR')
        sys.exit(1)

    log(f"正在构建单文件报告 (v5.5.0 跨平台版): {report_name}", 'CYAN')
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
