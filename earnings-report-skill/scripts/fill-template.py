#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨平台模板填充脚本（含结构完整性校验）

合并自原 fill-template.ps1 + fill-template.sh，单文件覆盖 Windows/Mac/Linux。

功能：
  1. 读取模板 HTML 和 sections JSON
  2. 替换 meta 占位符（10 个：{{COMPANY_NAME}}/{{QUARTER}} 等）
  3. 替换 header 块
  4. 替换 12 个 section 块
  5. 结构完整性校验（检查每个 section 的必需子元素）
  6. 替换 footer 块
  7. 清理剩余占位符
  8. 输出 HTML 文件

用法：
  python fill-template.py --template-file template.html --sections-file sections.json --output-file output.html
"""
import sys
import os
import re
import json
import argparse
from datetime import datetime
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
# 颜色与日志
# ============================================================
COLOR_CYAN = '\033[36m'
COLOR_GREEN = '\033[32m'
COLOR_YELLOW = '\033[33m'
COLOR_RED = '\033[31m'
COLOR_RESET = '\033[0m'

if sys.platform == 'win32':
    os.system('')


def log(msg, level='INFO'):
    color = {
        'INFO': '',
        'OK': COLOR_GREEN,
        'WARN': COLOR_YELLOW,
        'ERROR': COLOR_RED,
    }.get(level, '')
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}][{level}] {color}{msg}{COLOR_RESET}")


def get_prop(obj, name):
    """安全读取 dict 字段"""
    if obj is None:
        return None
    if isinstance(obj, dict) and name in obj:
        return obj[name]
    return None


# ============================================================
# 主流程
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description='跨平台模板填充脚本（含结构完整性校验）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--template-file', '-t', required=True,
                        help='模板 HTML 文件路径（必需）')
    parser.add_argument('--sections-file', '-j', required=True,
                        help='sections JSON 文件路径（必需）')
    parser.add_argument('--output-file', '-o', required=True,
                        help='输出 HTML 文件路径（必需）')
    args = parser.parse_args()

    template_path = args.template_file
    sections_path = args.sections_file
    output_path = args.output_file

    log("=== v5 fill-template start ===")
    log(f"Template: {template_path}")
    log(f"Sections: {sections_path}")
    log(f"Output:   {output_path}")

    # 校验输入文件
    if not os.path.isfile(template_path):
        log(f"模板文件不存在: {template_path}", 'ERROR')
        sys.exit(1)
    if not os.path.isfile(sections_path):
        log(f"sections 文件不存在: {sections_path}", 'ERROR')
        sys.exit(1)

    # 创建输出目录
    output_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(output_dir, exist_ok=True)

    # Step 1: 读取模板（utf-8-sig 自动去 BOM）
    log("--- Step 1: read template ---")
    with open(template_path, 'r', encoding='utf-8-sig') as f:
        template_html = f.read()
    log(f"Template size: {len(template_html)} chars")

    # Step 2: 读取 sections JSON
    log("--- Step 2: read sections JSON ---")
    with open(sections_path, 'r', encoding='utf-8-sig') as f:
        sections_json = f.read()
    try:
        data = json.loads(sections_json)
    except json.JSONDecodeError as e:
        log(f"JSON parse failed: {e}", 'ERROR')
        # ★ 输出错误位置的上下文，帮助 LLM 定位并修复
        lines = sections_json.split('\n')
        err_line = e.lineno if e.lineno else 1
        err_col = e.colno if e.colno else 0
        start_line = max(0, err_line - 2)
        end_line = min(len(lines), err_line + 2)
        log(f"错误位置: 第 {err_line} 行, 第 {err_col} 列 (char {e.pos})", 'ERROR')
        log(f"错误类型: {e.msg}", 'ERROR')
        log("上下文:", 'ERROR')
        for i in range(start_line, end_line):
            marker = " >>> " if (i + 1) == err_line else "     "
            log(f"{marker}L{i+1}: {lines[i][:200]}", 'ERROR')
        log("", 'ERROR')
        log("★ 常见原因：HTML 属性中的双引号未转义", 'ERROR')
        log("  错误示例: <div class=\"callout-title\">指引点评</div>", 'ERROR')
        log("  正确示例: <div class=\\\"callout-title\\\">指引点评</div>", 'ERROR')
        log("★ 修复方法：在 sections JSON 中，所有 HTML 内容的双引号必须用 \\\" 转义", 'ERROR')
        log("  或使用 Python json.dumps() 生成 sections JSON 自动转义", 'ERROR')
        sys.exit(1)

    # Step 3: 替换 meta 占位符
    log("--- Step 3: replace meta placeholders ---")
    meta = get_prop(data, 'meta')
    replace_count = 0
    if meta:
        meta_map = {
            '{{COMPANY_NAME}}': get_prop(meta, 'company_name') or '',
            '{{QUARTER}}': get_prop(meta, 'quarter') or '',
            '{{REPORT_TYPE}}': get_prop(meta, 'report_type') or '',
            '{{REPORT_DATE}}': get_prop(meta, 'report_date') or '',
            '{{EARNINGS_DATE}}': get_prop(meta, 'earnings_date') or '',
            '{{DATA_SOURCE}}': get_prop(meta, 'data_source') or '',
            '{{CURRENCY_UNIT}}': get_prop(meta, 'currency_unit') or '',
            '{{GENERATED_AT}}': get_prop(meta, 'generated_at') or '',
            '{{REPORT_VERSION}}': get_prop(meta, 'report_version') or '',
            '{{DISCLAIMER_TEXT}}': get_prop(meta, 'disclaimer_text') or '',
        }
        for key, val in meta_map.items():
            if val:
                template_html = template_html.replace(key, str(val))
                replace_count += 1
        log(f"meta placeholders replaced: {replace_count}", 'OK')

    # Step 4: 替换 header 块
    log("--- Step 4: replace header block ---")
    header_html = get_prop(data, 'header')
    if header_html:
        header_pattern = r'<header class="report-head">[\s\S]*?</header>'
        header_match = re.search(header_pattern, template_html)
        if header_match:
            template_html = template_html.replace(header_match.group(0), header_html)
            log("header replaced", 'OK')
        else:
            log("header pattern not found", 'WARN')
    else:
        log("header data missing, skip", 'WARN')

    # Step 5: 替换 12 个 section 块
    log("--- Step 5: replace 12 section blocks ---")
    sections = get_prop(data, 'sections')
    if not sections:
        log("sections data missing", 'ERROR')
        sys.exit(1)
    for i in range(1, 13):
        sec_id = f"sec{i:02d}"
        section_html = get_prop(sections, sec_id)
        if section_html:
            pattern = rf'<section id="{sec_id}"[^>]*>[\s\S]*?</section>'
            sec_match = re.search(pattern, template_html)
            if sec_match:
                template_html = template_html.replace(sec_match.group(0), section_html)
                log(f"  {sec_id} replaced", 'OK')
            else:
                log(f"  {sec_id} pattern not found", 'WARN')
        else:
            log(f"  {sec_id} data missing, skip", 'WARN')

    # Step 5.5: 结构校验
    log("--- Step 5.5: structure validation ---")
    section_required = {
        'sec01': ['highlights-box', 'callout'],
        'sec02': ['chart-revenue-trend', '<table'],
        'sec03': ['chart-revenue-mix', '<table', 'callout'],
        'sec04': ['stat-grid', 'chart-margin-trend', '<table', 'callout'],
        'sec05': ['chart-cashflow', '<table', 'insight-grid'],
        'sec06': ['stat-grid', 'chart-kpi-trend'],
        'sec07': ['chart-geo', '<table', 'insight-grid'],
        'sec08': ['<table', 'timeline', 'callout'],
        'sec09': ['callout', 'highlights-box'],
        'sec10': ['risk-list', 'callout'],
        'sec11': ['stat-grid', 'insight-grid', 'callout'],
        'sec12': ['glossary', 'chart-radar'],
    }
    section_forbidden = {'sec01': ['stat-grid']}
    validation_warnings = 0

    for i in range(1, 13):
        sec_id = f"sec{i:02d}"
        pattern = rf'<section id="{sec_id}"[^>]*>[\s\S]*?</section>'
        sec_match = re.search(pattern, template_html)
        if not sec_match:
            log(f"  {sec_id} section block not found", 'ERROR')
            continue
        sec_content = sec_match.group(0)
        required = section_required.get(sec_id, [])
        missing = [r for r in required if r not in sec_content]
        forbidden = section_forbidden.get(sec_id, [])
        forbidden_found = [fb for fb in forbidden if fb in sec_content]
        if missing:
            log(f"  {sec_id} missing: {', '.join(missing)}", 'WARN')
            validation_warnings += len(missing)
        if forbidden_found:
            log(f"  {sec_id} forbidden: {', '.join(forbidden_found)}", 'WARN')
            validation_warnings += len(forbidden_found)
        if not missing and not forbidden_found:
            log(f"  {sec_id} structure OK", 'OK')

    chart_ids = ['chart-revenue-trend', 'chart-revenue-mix', 'chart-margin-trend',
                 'chart-cashflow', 'chart-kpi-trend', 'chart-geo', 'chart-radar']
    chart_in_html = [cid for cid in chart_ids if f'id="{cid}"' in template_html]
    log(f"Chart containers: {len(chart_in_html)} / {len(chart_ids)}")
    if len(chart_in_html) < 5:
        log("Charts insufficient", 'WARN')
        validation_warnings += 1

    cite_count = len(re.findall(r'id="cite-\d+"', template_html))
    log(f"References: {cite_count}")
    if cite_count < 5:
        log("References insufficient", 'WARN')
        validation_warnings += 1

    stat_card_count = len(re.findall(r'class="stat-card"', template_html))
    log(f"stat-card count: {stat_card_count}")
    if stat_card_count < 12:
        log("stat-card insufficient", 'WARN')
        validation_warnings += 1

    if validation_warnings > 0:
        log(f"Validation: {validation_warnings} warnings", 'WARN')
    else:
        log("Validation: all pass", 'OK')

    # Step 6: 替换 footer 块
    log("--- Step 6: replace footer block ---")
    footer_html = get_prop(data, 'footer')
    footer_replaced = False
    if footer_html:
        footer_pattern = r'<footer>[\s\S]*?</footer>'
        footer_match = re.search(footer_pattern, template_html)
        if footer_match:
            template_html = template_html.replace(footer_match.group(0), footer_html)
            log("footer replaced", 'OK')
            footer_replaced = True
        else:
            log("footer pattern not found", 'WARN')
    else:
        log("footer data missing, skip", 'WARN')

    # Step 7: 清理剩余占位符
    log("--- Step 7: cleanup remaining placeholders ---")
    placeholder_pattern = r'\{\{[A-Z_0-9]+\}\}'
    remaining = re.findall(placeholder_pattern, template_html)
    if remaining:
        log(f"Found {len(remaining)} remaining placeholders, cleaning...", 'WARN')
        template_html = re.sub(placeholder_pattern, '', template_html)
        log("Remaining placeholders cleaned", 'OK')
    else:
        log("No remaining placeholders", 'OK')

    # Step 8: 写入输出文件（UTF-8 无 BOM）
    log("--- Step 8: write output file ---")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(template_html)
    out_size = os.path.getsize(output_path)
    log(f"Output: {output_path} ({out_size/1024:.1f} KB)", 'OK')

    log("")
    log("=== Fill complete ===")
    log(f"meta replaced: {replace_count}")
    log(f"sections replaced: 12")
    log(f"footer replaced: {'yes' if footer_replaced else 'no'}")
    log(f"validation warnings: {validation_warnings}")
    log(f"output size: {out_size/1024:.1f} KB")

    sys.exit(0)


if __name__ == '__main__':
    main()
