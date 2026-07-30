#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
跨平台环境检查与自动安装脚本

特性：
  1. 跨平台：Windows / macOS / Linux 全支持
  2. 并行检查：所有依赖并发检测，速度提升 3-5 倍
  3. 国内 IP 检测：自动识别中国大陆 IP，优先使用镜像源加速安装
  4. 自动安装：检测到缺失依赖时，交互式确认后自动安装
  5. 镜像加速：npm/pip/Homebrew/apt 均配置国内镜像
  6. Python 探测优先级（agent 内置 > 系统 > 安装）+ Windows Store stub 跳过
  7. 缓存 py_executable 绝对路径，供 dispatch-child-skill.py / LLM 使用

依赖清单（10 项）：
  运行时：Python 3.8+、Node.js 18+、PowerShell 7+
  浏览器：Google Chrome
  CLI：Git、GitHub CLI (gh)、wrangler (Cloudflare CLI)
  配置：config.local.json、占位符替换、git 仓库

用法：
  python check-and-install.py                  # 仅检查
  python check-and-install.py --install        # 检查 + 自动安装缺失依赖
  python check-and-install.py --install --yes  # 全自动（无需确认）
  python check-and-install.py --china          # 强制使用国内镜像
  python check-and-install.py --fix-config     # 自动创建 config.local.json
  python check-and-install.py --force-check    # 强制重检（忽略缓存）
"""
import sys
import os
import platform
import subprocess
import shutil
import json
import urllib.request
import urllib.error
import concurrent.futures
import time
import re
from pathlib import Path

# ============================================================
# 全局配置
# ============================================================
IS_WINDOWS = platform.system() == 'Windows'
IS_MACOS = platform.system() == 'Darwin'
IS_LINUX = platform.system() == 'Linux'
PLATFORM_NAME = platform.system()

# 颜色（Windows 10+ 支持 ANSI）
class Color:
    CYAN = '\033[36m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    RED = '\033[31m'
    GRAY = '\033[90m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

# 启用 Windows ANSI 颜色支持
if IS_WINDOWS:
    os.system('')  # 激活 ANSI 处理

# 脚本所在目录
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
CONFIG_FILE = SKILL_ROOT / 'config.local.json'
EXAMPLE_FILE = SKILL_ROOT / 'config.example.json'
# 缓存按平台分文件，避免跨平台命中错误缓存
_PLATFORM_TAG = IS_WINDOWS and 'windows' or (IS_MACOS and 'macos' or 'linux')
CACHE_FILE = SKILL_ROOT / f'.env-check-result.{_PLATFORM_TAG}.json'  # 环境检查结果缓存（按平台分文件）

# 镜像源配置
MIRRORS = {
    'npm': 'https://registry.npmmirror.com',           # 淘宝 npm 镜像
    'pip': 'https://pypi.tuna.tsinghua.edu.cn/simple', # 清华 PyPI 镜像
    'homebrew_brew': 'https://mirrors.tuna.tsinghua.edu.cn/homebrew/brew.git',
    'homebrew_core': 'https://mirrors.tuna.tsinghua.edu.cn/homebrew/homebrew-core.git',
    'homebrew_bottles': 'https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles',
    'apt_ubuntu': 'https://mirrors.tuna.tsinghua.edu.cn/ubuntu',
    'apt_debian': 'https://mirrors.tuna.tsinghua.edu.cn/debian',
    'nodesource': 'https://deb.nodesource.com/setup_18.x',
    'gh_deb': 'https://cli.github.com/packages/githubcli-cli.list',
}

# 默认官方源
OFFICIAL = {
    'npm': 'https://registry.npmjs.org',
    'pip': 'https://pypi.org/simple',
}

# 检查结果状态
PASS = 'PASS'
WARN = 'WARN'
FAIL = 'FAIL'

# 探测到的 Python 可执行文件绝对路径（全局变量，供 save_cache 写入缓存）
# 优先级：sys.executable → agent 内置 → py launcher → python3（跳过 stub）→ python（跳过 stub）
PYTHON_EXECUTABLE = ''

# Windows Store「应用执行别名」stub 检测
# WindowsApps 目录下的 python.exe / python3.exe 通常是 0 字节的占位 stub，
# 命中时会打开 Microsoft Store 而非真正执行 Python，必须跳过。
WINAPPS_DIR_CANDIDATES = [
    os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'WindowsApps'),
    'C:\\Users\\Default\\AppData\\Local\\Microsoft\\WindowsApps',
]


def is_stub_exe(path):
    """检测路径是否为 Windows Store 0 字节 stub 文件"""
    if not path or not IS_WINDOWS:
        return False
    try:
        p = Path(path).resolve()
        # 路径在 WindowsApps 目录下
        in_winapps = any(
            str(p).lower().startswith(str(Path(c).resolve()).lower().rstrip('\\'))
            for c in WINAPPS_DIR_CANDIDATES
            if c and Path(c).exists()
        )
        if not in_winapps:
            return False
        # 文件大小为 0 字节即为 stub
        return p.stat().st_size == 0
    except Exception:
        return False


def find_agent_python():
    """
    探测 TRAE agent 内置 Python（优先于系统 PATH）
    返回 (path, version_str) 或 (None, None)
    覆盖 Windows / macOS / Linux 三个平台
    """
    candidates = []
    if IS_WINDOWS:
        # TRAE SOLO CN / TRAE CN 内置 Python（沙箱环境，requests 等常用库已预装）
        base = os.environ.get('APPDATA', '')
        if base:
            candidates.append(Path(base) / 'TRAE SOLO CN' / 'ModularData' / 'ai-agent' / 'vm' / 'tools' / 'python' / 'python.exe')
            candidates.append(Path(base) / 'TRAE' / 'ModularData' / 'ai-agent' / 'vm' / 'tools' / 'python' / 'python.exe')
    elif IS_MACOS:
        # macOS：TRAE 应用包内置 Python
        home = os.path.expanduser('~')
        candidates.append(Path(home) / 'Library' / 'Application Support' / 'TRAE SOLO CN' / 'ModularData' / 'ai-agent' / 'vm' / 'tools' / 'python' / 'bin' / 'python3')
        candidates.append(Path(home) / 'Library' / 'Application Support' / 'TRAE' / 'ModularData' / 'ai-agent' / 'vm' / 'tools' / 'python' / 'bin' / 'python3')
    else:  # Linux
        home = os.path.expanduser('~')
        candidates.append(Path(home) / '.config' / 'TRAE SOLO CN' / 'ModularData' / 'ai-agent' / 'vm' / 'tools' / 'python' / 'bin' / 'python3')
        candidates.append(Path(home) / '.config' / 'TRAE' / 'ModularData' / 'ai-agent' / 'vm' / 'tools' / 'python' / 'bin' / 'python3')

    for cand in candidates:
        try:
            if cand.exists() and cand.stat().st_size > 0:
                rc, out, _ = run_cmd(f'"{cand}" --version', timeout=5)
                if rc == 0 and out and 'Python' in out:
                    return str(cand), out.strip()
        except Exception:
            continue
    return None, None


def resolve_python_executable():
    """
    解析可用的 Python 可执行文件绝对路径
    优先级：
      1. sys.executable（当前正在运行 Python，肯定可用）
      2. agent 内置 Python（TRAE 沙箱）
      3. py launcher（Windows）
      4. python3（跳过 0 字节 stub）
      5. python（跳过 0 字节 stub）
    返回 (path, version_str) 或 (None, None)
    """
    # 优先级 1：当前 Python（最可靠）
    if sys.executable and sys.executable not in ('', 'python', 'python3'):
        try:
            exe = Path(sys.executable).resolve()
            if exe.exists() and exe.stat().st_size > 0 and not is_stub_exe(str(exe)):
                ver = f'Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'
                return str(exe), ver
        except Exception:
            pass

    # 优先级 2：agent 内置 Python
    p, v = find_agent_python()
    if p:
        return p, v

    # 优先级 3：Windows py launcher
    if IS_WINDOWS:
        py_launcher = which('py')
        if py_launcher and not is_stub_exe(py_launcher):
            rc, out, _ = run_cmd(f'"{py_launcher}" --version', timeout=5)
            if rc == 0 and out and 'Python' in out:
                return py_launcher, out.strip()

    # 优先级 4 & 5：python3 / python（跳过 stub）
    for cmd in ('python3', 'python'):
        found = which(cmd)
        if found and not is_stub_exe(found):
            rc, out, _ = run_cmd(f'"{found}" --version', timeout=5)
            if rc == 0 and out and 'Python' in out:
                return found, out.strip()

    return None, None


# ============================================================
# 工具函数
# ============================================================
def log(msg, level='INFO', color=None):
    """带时间戳的日志输出"""
    ts = time.strftime('%H:%M:%S')
    c = color or Color.GRAY
    if level == 'OK':
        c = Color.GREEN
    elif level == 'WARN':
        c = Color.YELLOW
    elif level == 'ERROR':
        c = Color.RED
    elif level == 'INFO':
        c = Color.CYAN
    print(f"[{ts}] {c}{msg}{Color.RESET}")


def run_cmd(cmd, timeout=10, shell=False):
    """运行命令，返回 (returncode, stdout, stderr)"""
    try:
        if isinstance(cmd, str) and not shell:
            if IS_WINDOWS:
                # Windows: .cmd/.bat 文件和含引号的复杂命令需要 shell=True
                # 对包含 npx/npm/winget/gh 或路径引号的命令使用 shell
                if any(c in cmd.lower() for c in ('npx', 'npm', 'winget', 'gh ', '"')):
                    shell = True
                else:
                    cmd = cmd.split()
            else:
                cmd = cmd.split()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=shell, encoding='utf-8', errors='replace')
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, '', 'timeout'
    except FileNotFoundError:
        return -2, '', 'not found'
    except Exception as e:
        return -3, '', str(e)


def which(cmd):
    """查找命令路径（ shutil.which 包装）"""
    return shutil.which(cmd)


def detect_china(timeout=3):
    """检测是否为国内 IP（并发请求多个 API，任一成功即返回）"""
    apis = [
        'https://ipapi.co/json',
        'https://ipinfo.io/json',
    ]
    def fetch(url):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'curl/7.64'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode('utf-8'))
                country = data.get('country_code') or data.get('country') or ''
                return country.upper() == 'CN'
        except Exception:
            return None

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            futures = [ex.submit(fetch, u) for u in apis]
            try:
                for f in concurrent.futures.as_completed(futures, timeout=timeout + 1):
                    result = f.result()
                    if result is not None:
                        return result
            except concurrent.futures.TimeoutError:
                # 超时仍未获取结果，返回默认值
                pass
    except Exception:
        pass
    return False  # 检测失败默认非国内


def confirm(prompt, default_yes=False):
    """交互式确认"""
    try:
        hint = '[Y/n]' if default_yes else '[y/N]'
        ans = input(f"{prompt} {hint} ").strip().lower()
        if not ans:
            return default_yes
        return ans in ('y', 'yes')
    except (EOFError, KeyboardInterrupt):
        return False


# ============================================================
# 安装器（按平台）
# ============================================================
class Installer:
    def __init__(self, is_china=False):
        self.is_china = is_china
        self.npm_registry = MIRRORS['npm'] if is_china else OFFICIAL['npm']
        self.pip_index = MIRRORS['pip'] if is_china else OFFICIAL['pip']

    def _run_admin(self, cmd):
        """以管理员/sudo 权限运行命令"""
        if IS_WINDOWS:
            # Windows: winget 不需要管理员权限（用户级安装）
            return run_cmd(cmd, timeout=300)
        else:
            # Mac/Linux: 使用 sudo
            if isinstance(cmd, str):
                cmd = f'sudo {cmd}'
            else:
                cmd = ['sudo'] + cmd
            return run_cmd(cmd, timeout=300)

    def install_python(self):
        """
        安装 Python 3.8+
        安装后必须校验 PATH 配置 + 重新探测 + 写入 PYTHON_EXECUTABLE
        """
        global PYTHON_EXECUTABLE
        if IS_WINDOWS:
            log("  安装 Python 3.12 (winget)...", 'INFO')
            rc, out, err = run_cmd('winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements', timeout=300)
        elif IS_MACOS:
            log("  安装 Python 3.12 (Homebrew)...", 'INFO')
            self._ensure_homebrew_mirror()
            rc, out, err = run_cmd('brew install python@3.12', timeout=300)
        else:  # Linux
            log("  安装 Python 3 (apt)...", 'INFO')
            self._ensure_apt_mirror()
            rc, out, err = self._run_admin('apt-get install -y python3 python3-pip')

        if rc != 0:
            log(f"  Python 安装失败: {err}", 'ERROR')
            return False

        # 安装后 PATH 校验（关键）
        # winget/brew/apt 安装后可能需要重启终端才能让 PATH 生效，
        # 此处主动刷新 PATH 并重新探测
        log("  校验 Python PATH 配置...", 'INFO')
        self._refresh_path_env()
        py_path, ver_str = resolve_python_executable()
        if not py_path:
            log("  ⚠️ Python 已安装但 PATH 未生效", 'WARN')
            log("  请重启终端后再次执行 check-and-install.py，或手动将 Python 添加到 PATH", 'WARN')
            # 尝试从已知安装路径 fallback
            py_path = self._fallback_find_installed_python()
            if py_path:
                log(f"  已从已知路径定位 Python: {py_path}", 'OK')
                PYTHON_EXECUTABLE = py_path
                return True
            return False
        m = re.match(r'Python (\d+)\.(\d+)', ver_str or '')
        if m:
            major, minor = int(m.group(1)), int(m.group(2))
            if major > 3 or (major == 3 and minor >= 8):
                PYTHON_EXECUTABLE = py_path
                log(f"  ✓ Python 安装并 PATH 校验通过: {py_path} ({ver_str})", 'OK')
                return True
            log(f"  ⚠️ 安装后版本仍低于 3.8: {ver_str}", 'WARN')
            return False
        # 版本号解析失败但路径有效，仍标记成功
        PYTHON_EXECUTABLE = py_path
        return True

    def _refresh_path_env(self):
        """
        刷新当前进程的 PATH 环境变量
        Windows: 从注册表读取 Machine + User PATH 重新拼接
        macOS/Linux: 重新读取 /etc/paths + ~/.profile
        """
        try:
            if IS_WINDOWS:
                import winreg
                # 读取系统 PATH
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 0, winreg.KEY_READ) as key:
                    machine_path, _ = winreg.QueryValueEx(key, 'PATH')
                # 读取用户 PATH
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Environment', 0, winreg.KEY_READ) as key:
                    user_path, _ = winreg.QueryValueEx(key, 'PATH')
                # 合并（用户 PATH 优先）
                os.environ['PATH'] = user_path + ';' + machine_path + ';' + os.environ.get('PATH', '')
            else:
                # macOS/Linux：执行 shell -l -c 重新加载 PATH
                rc, out, _ = run_cmd('bash -l -c "echo $PATH"', timeout=5, shell=True)
                if rc == 0 and out:
                    os.environ['PATH'] = out + ':' + os.environ.get('PATH', '')
        except Exception as e:
            log(f"  PATH 刷新失败（不影响安装，仅影响本次探测）: {e}", 'WARN')

    def _fallback_find_installed_python(self):
        """
        PATH 未生效时从已知安装路径 fallback 查找 Python
        返回路径字符串或 None
        """
        candidates = []
        if IS_WINDOWS:
            pf = os.environ.get('ProgramFiles', '')
            pf86 = os.environ.get('ProgramFiles(x86)', '')
            la = os.environ.get('LOCALAPPDATA', '')
            for base in [pf, pf86]:
                if base:
                    for ver_folder in ['Python312', 'Python311', 'Python310', 'Python39']:
                        candidates.append(Path(base) / 'Python' / ver_folder / 'python.exe')
            if la:
                candidates.append(Path(la) / 'Programs' / 'Python' / 'Python312' / 'python.exe')
                candidates.append(Path(la) / 'Programs' / 'Python' / 'Python311' / 'python.exe')
        elif IS_MACOS:
            candidates.append(Path('/usr/local/bin/python3'))
            candidates.append(Path('/opt/homebrew/bin/python3'))
        else:
            candidates.append(Path('/usr/bin/python3'))
            candidates.append(Path('/usr/local/bin/python3'))

        for cand in candidates:
            try:
                if cand.exists() and cand.stat().st_size > 0:
                    rc, out, _ = run_cmd(f'"{cand}" --version', timeout=5)
                    if rc == 0 and out and 'Python' in out:
                        return str(cand)
            except Exception:
                continue
        return None

    def install_node(self):
        """安装 Node.js 18+"""
        if IS_WINDOWS:
            log("  安装 Node.js LTS (winget)...", 'INFO')
            rc, out, err = run_cmd('winget install OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements', timeout=300)
        elif IS_MACOS:
            log("  安装 Node.js 18 (Homebrew)...", 'INFO')
            rc, out, err = run_cmd('brew install node@18', timeout=300)
        else:
            log("  安装 Node.js 18 (NodeSource)...", 'INFO')
            # 添加 NodeSource 源
            rc1, _, _ = run_cmd(f"curl -fsSL {MIRRORS['nodesource']} | sudo -E bash -", timeout=60, shell=True)
            rc, out, err = self._run_admin('apt-get install -y nodejs')
        # 配置 npm 镜像
        if self.is_china:
            run_cmd(f'npm config set registry {self.npm_registry}', timeout=5)
            log(f"  npm 镜像已设置为: {self.npm_registry}", 'OK')
        return rc == 0

    def install_chrome(self):
        """安装 Google Chrome"""
        if IS_WINDOWS:
            log("  安装 Google Chrome (winget)...", 'INFO')
            rc, out, err = run_cmd('winget install Google.Chrome --accept-source-agreements --accept-package-agreements', timeout=300)
        elif IS_MACOS:
            log("  安装 Google Chrome (Homebrew cask)...", 'INFO')
            rc, out, err = run_cmd('brew install --cask google-chrome', timeout=300)
        else:
            log("  安装 Google Chrome (apt)...", 'INFO')
            # 添加 Google Chrome 源
            setup_script = """
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt-get update
sudo apt-get install -y google-chrome-stable
"""
            rc, out, err = run_cmd(setup_script, timeout=300, shell=True)
        return rc == 0

    def install_git(self):
        """安装 Git"""
        if IS_WINDOWS:
            log("  安装 Git (winget)...", 'INFO')
            rc, out, err = run_cmd('winget install Git.Git --accept-source-agreements --accept-package-agreements', timeout=300)
        elif IS_MACOS:
            log("  安装 Git (Homebrew)...", 'INFO')
            rc, out, err = run_cmd('brew install git', timeout=300)
        else:
            log("  安装 Git (apt)...", 'INFO')
            rc, out, err = self._run_admin('apt-get install -y git')
        return rc == 0

    def install_gh(self):
        """安装 GitHub CLI"""
        if IS_WINDOWS:
            log("  安装 GitHub CLI (winget)...", 'INFO')
            rc, out, err = run_cmd('winget install GitHub.cli --accept-source-agreements --accept-package-agreements', timeout=300)
        elif IS_MACOS:
            log("  安装 GitHub CLI (Homebrew)...", 'INFO')
            rc, out, err = run_cmd('brew install gh', timeout=300)
        else:
            log("  安装 GitHub CLI (apt)...", 'INFO')
            # 添加 GitHub CLI 源
            setup_script = """
(type -p wget >/dev/null || (sudo apt update && sudo apt-get install wget -y)) \\
&& sudo mkdir -p -m 755 /etc/apt/keyrings \\
&& out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \\
&& cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \\
&& sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \\
&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \\
&& sudo apt update \\
&& sudo apt install gh -y
"""
            rc, out, err = run_cmd(setup_script, timeout=300, shell=True)
        return rc == 0

    def install_wrangler(self):
        """安装 wrangler (Cloudflare CLI)"""
        log("  安装 wrangler (npm)...", 'INFO')
        if self.is_china:
            run_cmd(f'npm config set registry {self.npm_registry}', timeout=5)
        rc, out, err = run_cmd('npm i -g wrangler', timeout=180)
        return rc == 0

    def install_powershell(self):
        """安装 PowerShell 7+（Mac/Linux 需要，Windows 通常已有）"""
        if IS_WINDOWS:
            log("  安装 PowerShell 7 (winget)...", 'INFO')
            rc, out, err = run_cmd('winget install Microsoft.PowerShell --accept-source-agreements --accept-package-agreements', timeout=300)
        elif IS_MACOS:
            log("  安装 PowerShell 7 (Homebrew)...", 'INFO')
            rc, out, err = run_cmd('brew install powershell/tap/powershell', timeout=300)
        else:
            log("  安装 PowerShell 7 (apt)...", 'INFO')
            setup_script = """
sudo apt-get update
sudo apt-get install -y wget apt-transport-https software-properties-common
source /etc/os-release
wget -q https://packages.microsoft.com/config/ubuntu/$VERSION_ID/packages-microsoft-prod.deb
sudo dpkg -i packages-microsoft-prod.deb
rm packages-microsoft-prod.deb
sudo apt-get update
sudo apt-get install -y powershell
"""
            rc, out, err = run_cmd(setup_script, timeout=300, shell=True)
        return rc == 0

    def _ensure_homebrew_mirror(self):
        """配置 Homebrew 镜像（国内）"""
        if not self.is_china or not IS_MACOS:
            return
        log("  配置 Homebrew 清华镜像...", 'INFO')
        env_setup = f"""
export HOMEBREW_API_DOMAIN="{MIRRORS['homebrew_bottles']}"
export HOMEBREW_BOTTLE_DOMAIN="{MIRRORS['homebrew_bottles']}"
export HOMEBREW_BREW_GIT_REMOTE="{MIRRORS['homebrew_brew']}"
export HOMEBREW_CORE_GIT_REMOTE="{MIRRORS['homebrew_core']}"
"""
        # 写入 ~/.bashrc 或 ~/.zshrc
        rc_file = os.path.expanduser('~/.zshrc' if IS_MACOS else '~/.bashrc')
        try:
            with open(rc_file, 'a') as f:
                f.write('\n# Homebrew 清华镜像（check-and-install.py 自动配置）\n')
                f.write(env_setup)
            log(f"  Homebrew 镜像已写入 {rc_file}", 'OK')
        except:
            pass

    def _ensure_apt_mirror(self):
        """配置 apt 镜像（国内，仅提示，不自动改 sources.list 避免破坏系统）"""
        if not self.is_china or not IS_LINUX:
            return
        log("  [提示] 国内用户建议手动配置 apt 镜像（清华/阿里云）以加速下载", 'WARN')


# ============================================================
# 检查器
# ============================================================
def check_python():
    """
    检查 Python 3.8+
    使用 resolve_python_executable() 优先探测 agent 内置 Python，
                跳过 Windows Store 0 字节 stub，写入全局 PYTHON_EXECUTABLE 供缓存使用
    """
    global PYTHON_EXECUTABLE
    py_path, ver_str = resolve_python_executable()
    if not py_path:
        return FAIL, '未安装', 'python3'
    m = re.match(r'Python (\d+)\.(\d+)', ver_str or '')
    if not m:
        # 探测到了但版本号解析失败，仍标记为 PASS（避免误判）
        PYTHON_EXECUTABLE = py_path
        return PASS, f'已安装（{py_path}）', ''
    major, minor = int(m.group(1)), int(m.group(2))
    if major > 3 or (major == 3 and minor >= 8):
        PYTHON_EXECUTABLE = py_path
        return PASS, f'已安装 {ver_str}（{py_path}）', ''
    # 版本低于 3.8：不写入 PYTHON_EXECUTABLE（后续 install_python 会重新探测）
    return WARN, f'已安装 {ver_str}，版本低于 3.8', 'python3'


def check_node():
    """检查 Node.js 18+"""
    node_cmd = which('node')
    if not node_cmd:
        return FAIL, '未安装', 'node'
    rc, out, _ = run_cmd('node --version', timeout=5)
    m = re.match(r'v(\d+)', out)
    if not m:
        return PASS, f'已安装', ''
    major = int(m.group(1))
    if major >= 18:
        return PASS, f'已安装 {out}', ''
    return WARN, f'已安装 {out}，版本低于 18', 'node'


def check_chrome():
    """检查 Google Chrome"""
    # 跨平台路径检测
    paths = []
    if IS_WINDOWS:
        paths = [
            os.path.join(os.environ.get('ProgramFiles', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
        ]
    elif IS_MACOS:
        paths = [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            os.path.expanduser('~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
        ]
    else:  # Linux
        paths = [
            '/usr/bin/google-chrome',
            '/usr/bin/google-chrome-stable',
            '/usr/bin/chromium-browser',
            '/usr/bin/chromium',
            '/usr/local/bin/google-chrome',
        ]

    for p in paths:
        if p and os.path.exists(p):
            return PASS, f'已安装（{p}）', ''

    # 回退：从 PATH 查找
    for cmd in ['google-chrome', 'google-chrome-stable', 'chromium-browser', 'chromium', 'chrome']:
        found = which(cmd)
        if found:
            return PASS, f'已安装（{found}）', ''

    return FAIL, '未找到 Chrome', 'chrome'


def check_git():
    """检查 Git"""
    git_cmd = which('git')
    if not git_cmd:
        return FAIL, '未安装', 'git'
    rc, out, _ = run_cmd('git --version', timeout=5)
    return PASS, f'已安装 {out}', ''


def check_gh():
    """检查 GitHub CLI"""
    gh_cmd = which('gh')
    if not gh_cmd:
        return FAIL, '未安装', 'gh'
    rc, ver, _ = run_cmd('gh --version', timeout=5)
    # 检查登录状态
    rc2, status, _ = run_cmd('gh auth status', timeout=5)
    first_line = (ver.split('\n')[0] if ver else '')
    if rc2 == 0 and ('Logged in' in status or '已登录' in status):
        return PASS, f'已安装并已登录（{first_line}）', ''
    return WARN, f'已安装但未登录（{first_line}）', 'gh_login'


def check_wrangler():
    """检查 wrangler (Cloudflare CLI)"""
    wrangler_cmd = which('wrangler')
    exec_str = 'wrangler'
    if not wrangler_cmd:
        # 尝试 npx
        npx_cmd = which('npx')
        if npx_cmd:
            rc, out, _ = run_cmd('npx --no-install wrangler --version', timeout=10)
            if rc == 0 and out:
                exec_str = 'npx wrangler'
                wrangler_cmd = exec_str
    if not wrangler_cmd:
        return FAIL, '未安装', 'wrangler'
    # 版本
    rc, ver, _ = run_cmd(f'{exec_str} --version', timeout=10)
    ver_line = (ver.split('\n')[-1] if ver else '').strip()
    # 认证状态
    rc2, whoami, _ = run_cmd(f'{exec_str} whoami', timeout=10)
    if rc2 == 0 and ('logged in' in whoami.lower() or 'account' in whoami.lower()):
        return PASS, f'已安装并已认证（{ver_line}）', ''
    return WARN, f'已安装但未认证（{ver_line}）', 'wrangler_login'


def check_powershell():
    """检查 PowerShell 7+"""
    # Linux/Mac 平台 PowerShell 为可选项，不阻断流程
    if IS_LINUX or IS_MACOS:
        pwsh = which('pwsh')
        if pwsh:
            rc, out, _ = run_cmd(f'{pwsh} --version', timeout=5)
            return PASS, f'已安装 {out}', ''
        return PASS, 'Linux/Mac 平台无需 PowerShell（使用 bash 脚本）', ''  # 不阻断
    pwsh = which('pwsh')
    if pwsh:
        rc, out, _ = run_cmd(f'{pwsh} --version', timeout=5)
        return PASS, f'已安装 {out}', ''
    # Windows: 检查自带的 Windows PowerShell
    if IS_WINDOWS:
        ps5 = which('powershell') or shutil.which('powershell.exe')
        if ps5:
            return WARN, '仅 Windows PowerShell 5.x，建议升级到 7+', 'powershell'
    return FAIL, '未安装', 'powershell'


def check_config():
    """检查 config.local.json"""
    if not CONFIG_FILE.exists():
        if EXAMPLE_FILE.exists():
            return FAIL, '配置文件不存在（模板已存在）', 'config'
        return FAIL, '配置文件和模板都不存在', ''
    try:
        content = CONFIG_FILE.read_text(encoding='utf-8')
        # 占位符检测扩展为 5 项（补齐 cloudflare 2 项）
        placeholders = [
            '<your-feishu-webhook-url>',
            '<your-finnhub-api-key>',
            '<your-alphavantage-api-key>',
            '<your-cloudflare-api-token>',
            '<your-cloudflare-account-id>',
        ]
        unreplaced = [p for p in placeholders if p in content]
        if unreplaced:
            return WARN, f'含未替换占位符: {", ".join(unreplaced)}（可执行 collect-user-info.py 引导收集）', 'config_edit'
        return PASS, '配置文件存在且占位符已替换', ''
    except Exception as e:
        return FAIL, f'读取失败: {e}', ''


def check_git_repo():
    """检查 git 仓库（仓库目录由 output_root + 项目名推导，不再从 paths.repo_dir 读取）"""
    if not CONFIG_FILE.exists():
        return FAIL, 'config.local.json 不存在', ''

    try:
        cfg = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    except Exception as e:
        return FAIL, f'读取配置失败: {e}', ''

    # 推导仓库目录：output_root/Output/项目名
    output_root = cfg.get('paths', {}).get('output_root', '')
    github_repo = cfg.get('deployment', {}).get('github', {}).get('repo', '')
    project_name = github_repo.split('/')[-1] if github_repo else ''
    targets = cfg.get('deployment', {}).get('targets', [])

    if not output_root:
        return FAIL, (
            'paths.output_root 未配置。请在 config.local.json 的 paths.output_root 填写输出根目录'
            '（盘符+文件夹，如 d:/TraeAutomaticTools）。'
        ), ''
    if not project_name:
        return FAIL, 'deployment.github.repo 未配置，无法推导仓库目录', ''

    git_repo = os.path.join(output_root, 'Output', project_name)

    # 仅双部署时需要检查 .git 目录
    if 'github' not in targets:
        return PASS, f'仅 Cloudflare 部署，仓库目录 {git_repo} 不需要 git init', ''

    git_dir = os.path.join(git_repo, '.git')
    if not os.path.isdir(git_dir):
        return FAIL, f'未找到 .git 目录: {git_repo}（双部署方案需在仓库目录执行 git init）', ''

    # 检查 remote
    rc, out, _ = run_cmd(f'git -C "{git_repo}" remote get-url origin', timeout=5)
    if rc == 0 and out:
        return PASS, f'已初始化，remote: {out}', ''
    return WARN, '已初始化但未配置 remote origin', ''


# 依赖清单（名称, 检查函数, 安装方法名, 显示顺序）
DEPENDENCIES = [
    ('Python 3.8+',      check_python,     'install_python',     'python3'),
    ('Node.js 18+',      check_node,       'install_node',       'node'),
    ('Google Chrome',    check_chrome,     'install_chrome',     'chrome'),
    ('Git',              check_git,        'install_git',        'git'),
    ('GitHub CLI (gh)',  check_gh,         'install_gh',         'gh'),
    ('wrangler',         check_wrangler,   'install_wrangler',   'wrangler'),
    ('PowerShell 7+',    check_powershell, 'install_powershell', 'powershell'),
    ('config.local.json', check_config,    None,                 'config'),
    ('git 仓库',         check_git_repo,   None,                 ''),
]


# ============================================================
# 主流程
# ============================================================
def run_checks(parallel=True):
    """并行执行所有检查"""
    results = []
    if parallel:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(dep[1]): dep for dep in DEPENDENCIES}
            for f in concurrent.futures.as_completed(futures):
                dep = futures[f]
                try:
                    status, message, action = f.result()
                except Exception as e:
                    status, message, action = FAIL, f'检查异常: {e}', ''
                results.append((dep[0], status, message, action, dep[2], dep[3]))
    else:
        for dep in DEPENDENCIES:
            status, message, action = dep[1]()
            results.append((dep[0], status, message, action, dep[2], dep[3]))
    # 按原始顺序排序
    order_map = {dep[0]: i for i, dep in enumerate(DEPENDENCIES)}
    results.sort(key=lambda r: order_map.get(r[0], 999))
    return results


def print_results(results):
    """打印检查结果"""
    print()
    print(f"{Color.BOLD}{'='*60}{Color.RESET}")
    print(f"{Color.BOLD}  检查结果汇总{Color.RESET}")
    print(f"{Color.BOLD}{'='*60}{Color.RESET}")
    print()
    pass_n = warn_n = fail_n = 0
    for name, status, message, action, _, _ in results:
        if status == PASS:
            color = Color.GREEN
            icon = '[PASS]'
            pass_n += 1
        elif status == WARN:
            color = Color.YELLOW
            icon = '[WARN]'
            warn_n += 1
        else:
            color = Color.RED
            icon = '[FAIL]'
            fail_n += 1
        print(f"{color}{icon:<8}{Color.RESET}{name:<22}{message}")
        if action:
            print(f"{Color.GRAY}          -> 修复: {action}{Color.RESET}")
    print()
    print(f"{Color.CYAN}汇总: PASS={pass_n}  WARN={warn_n}  FAIL={fail_n}{Color.RESET}")
    return fail_n, warn_n


def install_missing(results, auto_yes=False, installer=None):
    """安装缺失依赖（检测到缺失即自动安装，无需用户确认）"""
    if installer is None:
        installer = Installer()

    # 需要安装的项（FAIL + 部分可安装的 WARN）
    to_install = []
    for name, status, message, action, install_method, action_key in results:
        if status == FAIL and install_method:
            to_install.append((name, install_method, action_key))
        elif status == WARN and install_method and action_key in ('node', 'python3', 'powershell'):
            # 版本过低的也自动升级
            to_install.append((name, install_method, action_key))

    if not to_install:
        log('无需安装的依赖（全部 PASS 或仅配置类警告）', 'OK')
        return True

    print()
    print(f"{Color.BOLD}检测到缺失/过期依赖，自动开始安装：{Color.RESET}")
    for i, (name, _, _) in enumerate(to_install, 1):
        print(f"  {i}. {name}")
    print()

    # 移除交互确认，检测到缺失即自动安装
    # （auto_yes 参数保留兼容，但默认行为已改为自动安装）

    # 按顺序安装（Python → Node → 其他，因为 wrangler 依赖 Node）
    success_count = 0
    for name, install_method, action_key in to_install:
        print()
        log(f"开始安装: {name}", 'INFO')
        method = getattr(installer, install_method, None)
        if method is None:
            log(f"  跳过 {name}（无自动安装方法）", 'WARN')
            continue
        try:
            ok = method()
            if ok:
                log(f"  {name} 安装成功", 'OK')
                success_count += 1
            else:
                log(f"  {name} 安装失败，请手动安装", 'ERROR')
        except Exception as e:
            log(f"  {name} 安装异常: {e}", 'ERROR')

    print()
    log(f"安装完成: {success_count}/{len(to_install)} 项成功", 'INFO')
    return success_count == len(to_install)


def fix_config():
    """自动创建 config.local.json"""
    if CONFIG_FILE.exists():
        log('config.local.json 已存在，跳过创建', 'INFO')
        return
    if not EXAMPLE_FILE.exists():
        log('config.example.json 模板不存在，无法创建', 'ERROR')
        return
    try:
        import shutil as _shutil
        _shutil.copy2(EXAMPLE_FILE, CONFIG_FILE)
        log(f'已从模板创建: {CONFIG_FILE}', 'OK')
        log('请编辑该文件填入真实的 API Key 和 Webhook URL', 'WARN')
    except Exception as e:
        log(f'创建失败: {e}', 'ERROR')


def load_cache():
    """加载环境检查结果缓存（永久有效，直到依赖变更或手动清除）"""
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 校验缓存格式
        if not isinstance(data, dict) or 'all_pass' not in data or 'results' not in data:
            return None
        if not data.get('all_pass'):
            return None  # 缓存显示有失败项，不使用
        return data
    except Exception:
        return None


def save_cache(results):
    """保存环境检查结果到缓存文件（仅全部 PASS 时保存）"""
    fail_n = sum(1 for r in results if r[1] == FAIL)
    if fail_n > 0:
        return  # 有失败项不缓存
    try:
        cache_data = {
            'check_time': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'platform': f'{PLATFORM_NAME} {platform.release()}',
            'all_pass': True,
            # 缓存探测到的 Python 绝对路径，供 dispatch-child-skill.py / LLM 调用使用
            'py_executable': PYTHON_EXECUTABLE,
            'results': [
                {'name': r[0], 'status': r[1], 'message': r[2]}
                for r in results
            ]
        }
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        log(f'检查结果已缓存到 {CACHE_FILE.name}（下次跳过检查）', 'OK')
        if PYTHON_EXECUTABLE:
            log(f'  Python 调用路径已缓存: {PYTHON_EXECUTABLE}', 'INFO')
    except Exception as e:
        log(f'缓存保存失败: {e}', 'WARN')


def main():
    import argparse
    parser = argparse.ArgumentParser(description='跨平台环境检查与自动安装')
    parser.add_argument('--install', action='store_true', help='自动安装缺失依赖（后默认自动安装，保留兼容）')
    parser.add_argument('--yes', '-y', action='store_true', help='全自动（无需确认，后默认自动，保留兼容）')
    parser.add_argument('--china', action='store_true', help='强制使用国内镜像')
    parser.add_argument('--fix-config', action='store_true', help='自动创建 config.local.json')
    parser.add_argument('--no-parallel', action='store_true', help='禁用并行检查（调试用）')
    parser.add_argument('--skip-check', action='store_true', help='跳过检查（仅安装，配合 --install）')
    parser.add_argument('--force-check', action='store_true', help='强制重新检查（忽略缓存）')
    args = parser.parse_args()

    print(f"{Color.BOLD}{'='*60}{Color.RESET}")
    print(f"{Color.BOLD}  earnings-report skill 环境检查与自动安装{Color.RESET}")
    print(f"{Color.BOLD}{'='*60}{Color.RESET}")
    print(f"{Color.GRAY}平台: {PLATFORM_NAME} {platform.release()}{Color.RESET}")
    print(f"{Color.GRAY}Skill 目录: {SKILL_ROOT}{Color.RESET}")

    # 检查缓存（永久有效，--force-check 可忽略）
    if not args.force_check and not args.fix_config and not args.skip_check:
        cached = load_cache()
        if cached:
            print()
            log(f'★ 使用缓存检查结果（{cached.get("check_time", "未知时间")}）', 'OK')
            log(f'平台: {cached.get("platform", "未知")}', 'INFO')
            print()
            for item in cached.get('results', []):
                icon = '[PASS]' if item.get('status') == 'PASS' else '[FAIL]'
                color = Color.GREEN if item.get('status') == 'PASS' else Color.RED
                print(f"  {color}{icon}{Color.RESET} {item.get('name', '?')}: {item.get('message', '')}")
            print()
            pass_n = sum(1 for r in cached.get('results', []) if r.get('status') == 'PASS')
            log(f'汇总: {pass_n} 项全部 PASS（缓存命中，跳过检查）', 'OK')
            log(f'如需强制重新检查，使用 --force-check 参数', 'INFO')
            sys.exit(0)

    # 创建 config.local.json
    if args.fix_config:
        fix_config()

    # 检测国内 IP
    if args.china:
        is_china = True
        log('强制使用国内镜像（--china）', 'INFO')
    else:
        log('检测网络环境（国内 IP 自动启用镜像）...', 'INFO')
        is_china = detect_china()
    if is_china:
        log('检测到国内 IP，将使用镜像源加速安装', 'OK')
    else:
        log('非国内 IP 或检测失败，使用官方源', 'INFO')

    installer = Installer(is_china=is_china)

    # 执行检查
    if not args.skip_check:
        log('开始并行检查所有依赖...', 'INFO')
        t0 = time.time()
        results = run_checks(parallel=not args.no_parallel)
        elapsed = time.time() - t0
        log(f'检查完成，耗时 {elapsed:.1f}s', 'INFO')
        fail_n, warn_n = print_results(results)

        # 自动安装（检测到缺失即自动安装，无需 --install 参数）
        if fail_n > 0 or warn_n > 0:
            install_missing(results, auto_yes=True, installer=installer)
            # 安装后重新检查一次，确认结果
            print()
            log('安装后重新检查...', 'INFO')
            results = run_checks(parallel=not args.no_parallel)
            fail_n, warn_n = print_results(results)

        # 退出码
        if fail_n > 0:
            print()
            log(f'仍存在 {fail_n} 项未通过，请手动处理', 'WARN')
            sys.exit(1)
        else:
            # 全部通过，保存缓存
            save_cache(results)
    else:
        # 仅安装模式
        if args.install:
            log('跳过检查，直接安装全部依赖...', 'WARN')
            for name, install_method, _ in [
                ('Python', 'install_python', 'python3'),
                ('Node.js', 'install_node', 'node'),
                ('Chrome', 'install_chrome', 'chrome'),
                ('Git', 'install_git', 'git'),
                ('GitHub CLI', 'install_gh', 'gh'),
                ('wrangler', 'install_wrangler', 'wrangler'),
                ('PowerShell', 'install_powershell', 'powershell'),
            ]:
                method = getattr(installer, install_method, None)
                if method and (args.yes or confirm(f'安装 {name}？')):
                    method()

    sys.exit(0)


if __name__ == '__main__':
    main()
