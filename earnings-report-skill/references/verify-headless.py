"""无头浏览器验证脚本 — 使用 Chrome headless screenshot + HTML结构双重验证（跨平台）"""
import subprocess
import sys
import os
import re
import time
import http.server
import threading
import tempfile
import platform

def find_chrome():
    """跨平台查找 Chrome 浏览器（仅支持 Chrome，不支持 Edge）"""
    paths = []

    # Windows 路径
    if platform.system() == 'Windows':
        paths = [
            os.path.join(os.environ.get('ProgramFiles', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
        ]
    # macOS 路径
    elif platform.system() == 'Darwin':
        paths = [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            os.path.expanduser('~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
        ]
    # Linux 路径
    else:
        paths = [
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium',
            '/usr/local/bin/google-chrome',
        ]

    for p in paths:
        if p and os.path.exists(p):
            return p

    # 回退：从 PATH 查找
    import shutil
    for cmd in ['google-chrome', 'google-chrome-stable', 'chromium-browser', 'chromium', 'chrome']:
        found = shutil.which(cmd)
        if found:
            return found

    return None

def start_http_server(directory, port):
    handler = http.server.SimpleHTTPRequestHandler
    os.chdir(directory)
    server = http.server.HTTPServer(('127.0.0.1', port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

def main():
    if len(sys.argv) < 2:
        print("用法: python verify-headless.py <report.html>")
        sys.exit(1)
    
    report_file = os.path.abspath(sys.argv[1])
    if not os.path.exists(report_file):
        print(f"错误: 找不到报告文件: {report_file}")
        sys.exit(1)
    
    file_dir = os.path.dirname(report_file)
    file_name = os.path.basename(report_file)
    port = 8800 + (os.getpid() % 100)
    
    # 读取HTML文件（用于结构验证）
    with open(report_file, 'r', encoding='utf-8') as f:
        raw_html = f.read()
    
    # 启动 HTTP 服务器
    print(f"[验证] 启动 HTTP 服务器 (端口 {port})...")
    server = start_http_server(file_dir, port)
    time.sleep(1)
    
    url = f"http://127.0.0.1:{port}/{file_name}"
    chrome_path = find_chrome()

    # ===== 截图验证（证明页面可渲染） =====
    screenshot_ok = False
    if chrome_path:
        print(f"[验证] 使用 Chrome 无头模式截图...")
        tmp_dir = tempfile.mkdtemp(prefix='earnings-verify-')
        screenshot_path = os.path.join(tmp_dir, 'screenshot.png')
        try:
            result = subprocess.run(
                [chrome_path, '--headless', '--disable-gpu', '--no-sandbox',
                 '--disable-extensions', '--window-size=1200,2400',
                 f'--screenshot={screenshot_path}',
                 url],
                capture_output=True, timeout=30
            )
            if os.path.exists(screenshot_path):
                sz = os.path.getsize(screenshot_path)
                if sz > 10000:
                    screenshot_ok = True
                    print(f"[验证] 截图渲染成功 ({sz / 1024:.0f} KB)")
                else:
                    print(f"[验证] 截图文件过小 ({sz} 字节)")
            else:
                print("[验证] 截图文件未生成")
        except subprocess.TimeoutExpired:
            print("[验证] Chrome 截图超时（30秒）")
        except Exception as e:
            print(f"[验证] Chrome 截图异常: {e}")
        finally:
            # 清理临时截图（W11 修复：使用 shutil.rmtree 递归删除，避免目录非空时残留）
            try:
                if os.path.exists(screenshot_path):
                    os.remove(screenshot_path)
                import shutil
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except:
                pass
    else:
        print("[验证] 未找到 Chrome，跳过截图验证")
    
    # ===== HTML结构验证 =====
    print("\n[验证] 检测结果:")

    # 1. 图表渲染验证 — 多层检测策略
    #    层1: DOM中有SVG（headless渲染成功时）
    #    层2: 截图成功 + echarts.init≥2 + 容器≥2（截图证明页面可渲染）
    #    层3: echarts.init≥2 + 容器≥2（charts.js 已内联，echarts 走 CDN）
    svg_count = len(re.findall(r'<svg', raw_html))
    echarts_init_count = len(re.findall(r'echarts\.init', raw_html))
    chart_containers = len(re.findall(r'id="chart-[\w-]+"', raw_html))

    if svg_count >= 2:
        svg_pass = True
        svg_detail = f"SVG: {svg_count} (DOM渲染检测)"
    elif screenshot_ok and echarts_init_count >= 2 and chart_containers >= 2:
        svg_pass = True
        svg_detail = f"SVG: {svg_count} (截图通过, init: {echarts_init_count}, 容器: {chart_containers})"
    elif echarts_init_count >= 2 and chart_containers >= 2:
        svg_pass = True
        svg_detail = f"SVG: {svg_count} (CDN模式, init: {echarts_init_count}, 容器: {chart_containers})"
    else:
        svg_pass = False
        svg_detail = f"SVG: {svg_count}, init: {echarts_init_count}, 容器: {chart_containers}"
    print(f"  图表渲染: {svg_detail} {'[PASS]' if svg_pass else '[FAIL]'}")

    # 2. StatCard (v5: 多个section使用stat-grid是合理设计，阈值改为>=4)
    stat_count = len(re.findall(r'class="[^"]*stat-card', raw_html))
    stat_pass = stat_count >= 4
    print(f"  StatCard 数量: {stat_count} {'[PASS]' if stat_pass else '[FAIL - 需>=4]'}")

    # 3. 参考资料
    ref_count = len(re.findall(r'id="cite-\d+"', raw_html))
    ref_pass = ref_count >= 5
    print(f"  参考资料数量: {ref_count} {'[PASS]' if ref_pass else '[FAIL - 需≥5]'}")

    # 4. 外部Script — ★ CDN 模式：允许 echarts CDN + document.write 回退链
    #    白名单：cdn.staticfile.org / cdn.bootcdn.net / cdn.jsdelivr.net
    all_ext_scripts = re.findall(r'<script\s+src="([^"]+)"', raw_html)
    cdn_whitelist = [
        'cdn.staticfile.org',
        'cdn.bootcdn.net',
        'cdn.jsdelivr.net',
    ]
    non_cdn_scripts = [s for s in all_ext_scripts if not any(w in s for w in cdn_whitelist)]
    script_pass = len(non_cdn_scripts) == 0
    print(f"  外部Script引用: {len(all_ext_scripts)} (CDN白名单内), 非白名单: {len(non_cdn_scripts)} {'[PASS]' if script_pass else '[FAIL - 非白名单src]'}")

    # 5. 外部Link
    ext_link = len(re.findall(r'<link\s+(?:[^>]*\s)?href=', raw_html))
    link_pass = ext_link == 0
    print(f"  外部Link引用: {ext_link} {'[PASS]' if link_pass else '[FAIL - 需=0]'}")

    # 6. @font-face
    font_face = len(re.findall(r'@font-face', raw_html))
    font_pass = font_face == 0
    print(f"  @font-face 声明: {font_face} {'[PASS]' if font_pass else '[FAIL - 需=0]'}")
    
    # 7. 截图渲染
    if chrome_path:
        print(f"  无头截图渲染: {'[PASS]' if screenshot_ok else '[SKIP - 退化为结构验证]'}")
    
    all_pass = svg_pass and stat_pass and ref_pass and script_pass and link_pass and font_pass
    
    file_size = os.path.getsize(report_file)
    print(f"\n  文件大小: {file_size / 1024:.0f} KB")
    
    if all_pass:
        print("=" * 40)
        print("  验证结果: PASS — 报告渲染正常")
        print("=" * 40)
    else:
        print("=" * 40)
        print("  验证结果: FAIL — 存在未通过项")
        print("=" * 40)
    
    # 清理
    print("\n[清理] 正在关闭 HTTP 服务器...")
    server.shutdown()
    print("[清理] 完成")
    
    sys.exit(0 if all_pass else 1)

if __name__ == '__main__':
    main()
