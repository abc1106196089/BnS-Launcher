#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║          剑灵 2.0 图形界面启动器 - Windows 10 x64 兼容版      ║
║          BnS 2.0 Launcher - Windows 10 x64 Compatible        ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import socket
import struct
import subprocess
import threading
import platform
import ctypes
import ctypes.wintypes
from datetime import datetime
from pathlib import Path

# ============================================================
# 兼容性处理 - Windows 10 x64
# ============================================================

# 检测是否在 Windows 上运行
IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

# Windows 兼容性标志
if IS_WINDOWS:
    try:
        # 设置 DPI 感知，防止高分辨率下界面模糊
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except:
            pass

# ============================================================
# 安全导入 Tkinter（兼容 Windows 无显示器环境）
# ============================================================

TKINTER_AVAILABLE = False
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

# ============================================================
# 安全导入网络库
# ============================================================

REQUESTS_AVAILABLE = False
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ============================================================
# 日志系统
# ============================================================

class Logger:
    """线程安全的日志系统"""

    def __init__(self):
        self.logs = []
        self.max_logs = 1000
        self.lock = threading.Lock()

    def log(self, level, message):
        """添加日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "time": timestamp,
            "level": level,
            "message": message
        }
        with self.lock:
            self.logs.append(entry)
            if len(self.logs) > self.max_logs:
                self.logs.pop(0)
        return entry

    def info(self, msg):
        return self.log("INFO", msg)

    def warn(self, msg):
        return self.log("WARN", msg)

    def error(self, msg):
        return self.log("ERROR", msg)

    def debug(self, msg):
        return self.log("DEBUG", msg)

    def get_all(self):
        with self.lock:
            return list(self.logs)

    def clear(self):
        with self.lock:
            self.logs.clear()


# 全局日志实例
logger = Logger()

# ============================================================
# 配置管理
# ============================================================

class Config:
    """配置管理类"""

    CONFIG_FILE = "launcher_config.json"

    DEFAULTS = {
        "game_path": "",
        "game_exe": "bin/client.exe",
        "username": "",
        "password": "",
        "remember_password": False,
        "auto_login": False,
        "server_ip": "127.0.0.1",
        "server_port": 8080,
        "server_a_ip": "192.168.200.128",
        "server_a_port": 1433,
        "server_b_ip": "127.0.0.1",
        "server_b_port": 8080,
        "current_server": "A",
        "launch_params": "-launch -windowed",
        "auto_start_vm": False,
        "vm_path": "",
        "theme": "dark",
        "log_level": "INFO",
        "scan_timeout": 3,
        "scan_threads": 50,
    }

    def __init__(self):
        self.data = dict(self.DEFAULTS)
        self.load()

    def load(self):
        """加载配置"""
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
                logger.info(f"配置已加载: {self.CONFIG_FILE}")
        except Exception as e:
            logger.warn(f"加载配置失败: {e}")

    def save(self):
        """保存配置"""
        try:
            # 不保存密码（如果未勾选记住）
            data_to_save = dict(self.data)
            if not data_to_save.get("remember_password"):
                data_to_save["password"] = ""

            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            logger.info(f"配置已保存: {self.CONFIG_FILE}")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def get_current_server(self):
        """获取当前选中的服务端配置"""
        if self.data.get("current_server") == "B":
            return self.data.get("server_b_ip"), self.data.get("server_b_port")
        return self.data.get("server_a_ip"), self.data.get("server_a_port")


# 全局配置实例
config = Config()

# ============================================================
# 网络工具
# ============================================================

class NetworkUtils:
    """网络工具类"""

    @staticmethod
    def check_port(host, port, timeout=2):
        """检查指定主机的端口是否开放"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, int(port)))
            sock.close()
            return result == 0
        except:
            return False

    @staticmethod
    def get_local_ip():
        """获取本机 IP 地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    @staticmethod
    def get_arp_table():
        """获取 ARP 缓存表"""
        hosts = set()
        try:
            if IS_WINDOWS:
                result = subprocess.run(
                    ["arp", "-a"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        line = line.strip()
                        if line and not line.startswith("Interface"):
                            parts = line.split()
                            if len(parts) >= 1:
                                ip = parts[0]
                                if NetworkUtils._is_valid_ip(ip):
                                    hosts.add(ip)
            else:
                # Linux
                result = subprocess.run(
                    ["arp", "-a"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        parts = line.split()
                        for p in parts:
                            if NetworkUtils._is_valid_ip(p):
                                hosts.add(p)
        except:
            pass
        return list(hosts)

    @staticmethod
    def _is_valid_ip(ip):
        """验证是否为有效的 IPv4 地址"""
        try:
            parts = ip.split(".")
            if len(parts) != 4:
                return False
            return all(0 <= int(p) <= 255 for p in parts)
        except:
            return False

    @staticmethod
    def get_vm_networks():
        """获取可能的虚拟机网段"""
        local_ip = NetworkUtils.get_local_ip()
        networks = set()

        # 本机网段
        if "." in local_ip:
            parts = local_ip.split(".")
            networks.add(f"{parts[0]}.{parts[1]}.{parts[2]}")

        # VMware 常见网段
        vmware_nets = [
            "192.168.200",  # VMware NAT 默认
            "192.168.10",   # VMware Host-Only
            "192.168.0",    # 常见局域网
            "192.168.1",    # 常见局域网
            "192.168.100",  # 常见虚拟机
            "10.0.0",       # 内网
            "172.16.0",     # 内网
            "172.16.1",
        ]
        networks.update(vmare_nets for vmare_nets in vmware_nets)

        return list(networks)

    @staticmethod
    def scan_ports_thread(hosts, ports, timeout, results, progress_callback=None):
        """多线程端口扫描"""
        scanned = 0
        total = len(hosts) * len(ports)

        for host in hosts:
            for port in ports:
                if NetworkUtils.check_port(host, port, timeout):
                    results.append((host, port))
                scanned += 1
                if progress_callback:
                    progress = int((scanned / total) * 100)
                    progress_callback(progress)
                if scanned % 10 == 0:
                    time.sleep(0.01)  # 让出 CPU


# ============================================================
# 凭据探测
# ============================================================

class CredentialScanner:
    """凭据扫描器"""

    COMMON_ADMIN_CREDS = [
        ("admin", "admin"),
        ("admin", "123456"),
        ("admin", "admin123"),
        ("administrator", "admin"),
        ("administrator", "123456"),
        ("administrator", "admin123"),
        ("root", "root"),
        ("root", "123456"),
        ("root", "toor"),
        ("sa", "123456"),
        ("sa", "sa"),
        ("bns", "bns123"),
        ("bns", "bns"),
        ("gm", "gm123"),
        ("gm", "gm"),
        ("superadmin", "admin"),
        ("superadmin", "123456"),
        ("sysadmin", "admin"),
    ]

    COMMON_DB_CREDS = [
        ("sa", "123456"),
        ("sa", "sa"),
        ("root", "root"),
        ("root", "123456"),
        ("admin", "admin"),
        ("admin", "123456"),
        ("bns", "bns123"),
        ("bns", "bns"),
        ("mysql", "mysql"),
        ("postgres", "postgres"),
        ("postgres", "123456"),
        ("game", "game123"),
        ("game", "game"),
        ("dba", "dba123"),
        ("test", "test"),
    ]

    DB_PORTS = {
        "mssql": 1433,
        "mysql": 3306,
        "postgresql": 5432,
    }

    @staticmethod
    def scan_admin_creds(host, port, timeout=3):
        """扫描管理员凭据"""
        found = []
        if not REQUESTS_AVAILABLE:
            return found

        # 尝试 HTTP 基本认证
        protocols = ["http", "https"]
        paths = ["/", "/admin", "/login", "/gm", "/manage", "/api/login"]

        for protocol in protocols:
            for path in paths:
                url = f"{protocol}://{host}:{port}{path}"
                for username, password in CredentialScanner.COMMON_ADMIN_CREDS:
                    try:
                        resp = requests.get(
                            url,
                            auth=requests.auth.HTTPBasicAuth(username, password),
                            timeout=timeout,
                            verify=False,
                            allow_redirects=False
                        )
                        if resp.status_code in [200, 301, 302, 401]:
                            # 401 说明需要认证但凭据不对，200/301/302 可能成功
                            if resp.status_code != 401 or resp.headers.get("WWW-Authenticate"):
                                found.append({
                                    "type": "HTTP Basic Auth",
                                    "username": username,
                                    "password": password,
                                    "url": url,
                                    "source": f"HTTP Basic Auth on {url}"
                                })
                                logger.info(f"发现管理员凭据: {username}/{password} @ {url}")
                    except:
                        pass

        return found

    @staticmethod
    def scan_db_creds(host, db_type, timeout=3):
        """扫描数据库凭据"""
        found = []
        port = CredentialScanner.DB_PORTS.get(db_type)

        if db_type == "mssql" and NetworkUtils.check_port(host, port, timeout):
            try:
                import pymssql
                for username, password in CredentialScanner.COMMON_DB_CREDS:
                    try:
                        conn = pymssql.connect(
                            server=host,
                            user=username,
                            password=password,
                            database="master",
                            timeout=timeout
                        )
                        conn.close()
                        found.append({
                            "type": "SQL Server",
                            "username": username,
                            "password": password,
                            "host": f"{host}:{port}",
                            "source": f"SQL Server {host}:{port}"
                        })
                        logger.info(f"发现 MSSQL 凭据: {username}/{password} @ {host}:{port}")
                        break  # 找到一组就够
                    except:
                        pass
            except:
                pass

        elif db_type == "mysql" and NetworkUtils.check_port(host, port, timeout):
            try:
                import mysql.connector
                for username, password in CredentialScanner.COMMON_DB_CREDS:
                    try:
                        conn = mysql.connector.connect(
                            host=host,
                            user=username,
                            password=password,
                            port=port,
                            connection_timeout=timeout
                        )
                        conn.close()
                        found.append({
                            "type": "MySQL",
                            "username": username,
                            "password": password,
                            "host": f"{host}:{port}",
                            "source": f"MySQL {host}:{port}"
                        })
                        logger.info(f"发现 MySQL 凭据: {username}/{password} @ {host}:{port}")
                        break
                    except:
                        pass
            except:
                pass

        elif db_type == "postgresql" and NetworkUtils.check_port(host, port, timeout):
            try:
                import psycopg2
                for username, password in CredentialScanner.COMMON_DB_CREDS:
                    try:
                        conn = psycopg2.connect(
                            host=host,
                            user=username,
                            password=password,
                            port=port,
                            dbname="postgres",
                            connect_timeout=timeout
                        )
                        conn.close()
                        found.append({
                            "type": "PostgreSQL",
                            "username": username,
                            "password": password,
                            "host": f"{host}:{port}",
                            "source": f"PostgreSQL {host}:{port}"
                        })
                        logger.info(f"发现 PostgreSQL 凭据: {username}/{password} @ {host}:{port}")
                        break
                    except:
                        pass
            except:
                pass

        return found


# ============================================================
# 游戏启动器核心
# ============================================================

class GameLauncher:
    """游戏启动器核心"""

    COMMON_GAME_EXES = [
        "bin/client.exe",
        "bin/BnS.exe",
        "bin/BnS_Client.exe",
        "BnS.exe",
        "client.exe",
        "Game.exe",
        "BladeAndSoul.exe",
    ]

    COMMON_GAME_PATHS = [
        "C:/Program Files (x86)/NCSoft/BnS",
        "C:/Program Files/NCSoft/BnS",
        "C:/NCSOFT/BnS",
        "D:/NCSOFT/BnS",
        "E:/NCSOFT/BnS",
        "C:/Games/BnS",
        "D:/Games/BnS",
    ]

    @staticmethod
    def find_game_exe(game_path):
        """在指定路径下查找游戏可执行文件"""
        if not game_path or not os.path.exists(game_path):
            return None

        # 先尝试配置中指定的
        configured_exe = config.get("game_exe", "bin/client.exe")
        full_path = os.path.join(game_path, configured_exe)
        if os.path.exists(full_path):
            return full_path

        # 遍历常见路径
        for exe_rel in GameLauncher.COMMON_GAME_EXES:
            full_path = os.path.join(game_path, exe_rel)
            if os.path.exists(full_path):
                return full_path

        # 递归搜索
        for root, dirs, files in os.walk(game_path):
            for f in files:
                if f.lower() in ["client.exe", "bns.exe", "bns_client.exe", "bladeandSoul.exe"]:
                    return os.path.join(root, f)
            # 不深入太多层
            if root.count(os.sep) - game_path.count(os.sep) > 3:
                dirs.clear()

        return None

    @staticmethod
    def auto_detect_game_path():
        """自动检测游戏安装路径"""
        paths_to_check = []

        # 从配置中获取
        cfg_path = config.get("game_path", "")
        if cfg_path:
            paths_to_check.append(cfg_path)

        # 常见安装路径
        paths_to_check.extend(GameLauncher.COMMON_GAME_PATHS)

        # 从注册表查找（Windows）
        if IS_WINDOWS:
            try:
                import winreg
                reg_paths = [
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\NCSoft\BnS"),
                    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\NCSoft\BnS"),
                    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\NCSoft\BnS"),
                ]
                for hkey, subkey in reg_paths:
                    try:
                        key = winreg.OpenKey(hkey, subkey)
                        val, _ = winreg.QueryValueEx(key, "InstallPath")
                        if val:
                            paths_to_check.append(val)
                        winreg.CloseKey(key)
                    except:
                        pass
            except:
                pass

        # 检查所有路径
        for path in paths_to_check:
            if os.path.exists(path):
                exe = GameLauncher.find_game_exe(path)
                if exe:
                    return path, exe
            # 也检查路径本身是否是 exe
            if path.lower().endswith(".exe") and os.path.exists(path):
                return os.path.dirname(path), path

        return None, None

    @staticmethod
    def build_launch_command(game_exe_path):
        """构建游戏启动命令"""
        cmd = [game_exe_path]

        # 基本参数
        params = config.get("launch_params", "-launch -windowed")
        if params:
            cmd.extend(params.split())

        # 账号密码参数
        username = config.get("username", "")
        password = config.get("password", "")

        if username:
            cmd.extend(["-u", username])
        if password:
            cmd.extend(["-p", password])

        # 服务端参数
        server_ip, server_port = config.get_current_server()
        cmd.extend(["-ip", str(server_ip)])
        cmd.extend(["-port", str(server_port)])

        return cmd

    @staticmethod
    def launch_game():
        """启动游戏"""
        game_path = config.get("game_path", "")
        if not game_path:
            return False, "未设置游戏路径"

        exe_path = GameLauncher.find_game_exe(game_path)
        if not exe_path:
            return False, f"未找到游戏可执行文件，请检查路径: {game_path}"

        cmd = GameLauncher.build_launch_command(exe_path)
        logger.info(f"启动命令: {' '.join(cmd)}")

        try:
            if IS_WINDOWS:
                # Windows: 使用 CREATE_NO_WINDOW 减少控制台闪烁
                subprocess.Popen(
                    cmd,
                    cwd=os.path.dirname(exe_path),
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen(cmd, cwd=os.path.dirname(exe_path))

            logger.info("游戏启动成功！")
            return True, "游戏启动成功"
        except Exception as e:
            logger.error(f"启动游戏失败: {e}")
            return False, f"启动游戏失败: {e}"


# ============================================================
# GUI - 剑灵 2.0 启动器界面
# ============================================================

class BnSLauncherGUI:
    """剑灵 2.0 启动器图形界面"""

    def __init__(self, root):
        self.root = root
        self.root.title("剑灵 2.0 图形界面启动器")
        self.root.geometry("900x700")
        self.root.minsize(850, 650)

        # Windows 10 兼容性设置
        if IS_WINDOWS:
            try:
                self.root.tk.call('tk', 'scaling', 1.0)  # DPI 缩放
            except:
                pass

        # 颜色主题
        self.bg_dark = "#1a1a2e"
        self.bg_medium = "#16213e"
        self.bg_light = "#0f3460"
        self.accent = "#e94560"
        self.accent_hover = "#ff6b81"
        self.text_primary = "#ffffff"
        self.text_secondary = "#b0b0b0"
        self.success = "#2ecc71"
        self.warning = "#f39c12"
        self.error_color = "#e74c3c"

        # 配置根窗口
        self.root.configure(bg=self.bg_dark)
        self.root.option_add("*Font", "Microsoft YaHei 10")

        # 样式配置
        self._setup_styles()

        # 创建界面
        self._create_widgets()

        # 加载配置到界面
        self._load_config_to_ui()

        # 启动时自动检测游戏路径
        self._auto_detect_game()

        logger.info("剑灵 2.0 启动器界面初始化完成")

    def _setup_styles(self):
        """配置 ttk 样式"""
        style = ttk.Style()
        style.theme_use("clam")

        # 按钮样式
        style.configure(
            "Accent.TButton",
            background=self.accent,
            foreground=self.text_primary,
            padding=(20, 10),
            font=("Microsoft YaHei", 11, "bold"),
            borderwidth=0,
        )
        style.map(
            "Accent.TButton",
            background=[("active", self.accent_hover), ("pressed", "#c0392b")],
        )

        style.configure(
            "Success.TButton",
            background=self.success,
            foreground=self.text_primary,
            padding=(15, 8),
            font=("Microsoft YaHei", 10, "bold"),
            borderwidth=0,
        )
        style.map(
            "Success.TButton",
            background=[("active", "#27ae60"), ("pressed", "#1e8449")],
        )

        style.configure(
            "Warning.TButton",
            background=self.warning,
            foreground=self.text_primary,
            padding=(15, 8),
            font=("Microsoft YaHei", 10),
            borderwidth=0,
        )

        # 标签框架
        style.configure(
            "Dark.TLabelframe",
            background=self.bg_medium,
            foreground=self.text_primary,
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "Dark.TLabelframe.Label",
            background=self.bg_dark,
            foreground=self.accent,
            font=("Microsoft YaHei", 11, "bold"),
        )

        # 进度条
        style.configure(
            "Custom.Horizontal.TProgressbar",
            background=self.accent,
            troughcolor=self.bg_light,
            borderwidth=0,
            thickness=8,
        )

    def _create_widgets(self):
        """创建所有界面组件"""
        # 主容器 - 可滚动
        self.main_canvas = tk.Canvas(self.root, bg=self.bg_dark, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.scrollable_frame = tk.Frame(self.main_canvas, bg=self.bg_dark)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )

        self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.main_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # 绑定鼠标滚轮
        self.main_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # ===== 标题区域 =====
        self._create_title_section()

        # ===== 游戏路径设置 =====
        self._create_game_path_section()

        # ===== 账号登录 =====
        self._create_login_section()

        # ===== 服务端设置 =====
        self._create_server_section()

        # ===== 高级设置 =====
        self._create_advanced_section()

        # ===== 启动按钮 =====
        self._create_launch_section()

        # ===== 日志区域 =====
        self._create_log_section()

    def _create_title_section(self):
        """创建标题区域"""
        title_frame = tk.Frame(self.scrollable_frame, bg=self.bg_dark)
        title_frame.pack(fill="x", padx=20, pady=(20, 10))

        # 标题
        title_label = tk.Label(
            title_frame,
            text="⚔ 剑灵 2.0 图形界面启动器",
            font=("Microsoft YaHei", 22, "bold"),
            fg=self.accent,
            bg=self.bg_dark,
        )
        title_label.pack()

        # 副标题
        subtitle_label = tk.Label(
            title_frame,
            text="Windows 10 x64 兼容版 | 自动登录 | 服务端扫描 | 凭据探测",
            font=("Microsoft YaHei", 10),
            fg=self.text_secondary,
            bg=self.bg_dark,
        )
        subtitle_label.pack(pady=(5, 0))

        # 兼容性提示
        compat_label = tk.Label(
            title_frame,
            text="✅ 兼容 Windows 10 / Windows 11 (x64)",
            font=("Microsoft YaHei", 9),
            fg=self.success,
            bg=self.bg_dark,
        )
        compat_label.pack(pady=(5, 0))

    def _create_game_path_section(self):
        """创建游戏路径设置区域"""
        frame = ttk.LabelFrame(self.scrollable_frame, text="📂 游戏路径设置", style="Dark.TLabelframe")
        frame.pack(fill="x", padx=20, pady=10)

        inner = tk.Frame(frame, bg=self.bg_medium)
        inner.pack(fill="x", padx=10, pady=10)

        # 路径输入
        tk.Label(inner, text="游戏目录:", bg=self.bg_medium, fg=self.text_primary,
                font=("Microsoft YaHei", 10)).grid(row=0, column=0, sticky="w", padx=5, pady=5)

        self.game_path_var = tk.StringVar()
        path_entry = tk.Entry(
            inner, textvariable=self.game_path_var, width=50,
            bg="#2c3e50", fg=self.text_primary, insertbackground=self.text_primary,
            relief="flat", font=("Microsoft YaHei", 10)
        )
        path_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        browse_btn = ttk.Button(
            inner, text="浏览...", command=self._browse_game_path,
            style="Accent.TButton"
        )
        browse_btn.grid(row=0, column=2, padx=5, pady=5)

        # 自动检测按钮
        detect_btn = ttk.Button(
            inner, text="🔍 自动检测", command=self._auto_detect_game,
            style="Success.TButton"
        )
        detect_btn.grid(row=0, column=3, padx=5, pady=5)

        # 游戏 EXE 设置
        tk.Label(inner, text="游戏EXE:", bg=self.bg_medium, fg=self.text_primary,
                font=("Microsoft YaHei", 10)).grid(row=1, column=0, sticky="w", padx=5, pady=5)

        self.game_exe_var = tk.StringVar(value="bin/client.exe")
        exe_entry = tk.Entry(
            inner, textvariable=self.game_exe_var, width=50,
            bg="#2c3e50", fg=self.text_primary, insertbackground=self.text_primary,
            relief="flat", font=("Microsoft YaHei", 10)
        )
        exe_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        self.path_status_label = tk.Label(
            inner, text="", bg=self.bg_medium, font=("Microsoft YaHei", 9)
        )
        self.path_status_label.grid(row=1, column=2, columnspan=2, padx=5, pady=5, sticky="w")

        inner.columnconfigure(1, weight=1)

    def _create_login_section(self):
        """创建账号登录区域"""
        frame = ttk.LabelFrame(self.scrollable_frame, text="🔐 账号登录", style="Dark.TLabelframe")
        frame.pack(fill="x", padx=20, pady=10)

        inner = tk.Frame(frame, bg=self.bg_medium)
        inner.pack(fill="x", padx=10, pady=10)

        # 用户名
        tk.Label(inner, text="账  号:", bg=self.bg_medium, fg=self.text_primary,
                font=("Microsoft YaHei", 10)).grid(row=0, column=0, sticky="w", padx=5, pady=8)

        self.username_var = tk.StringVar()
        user_entry = tk.Entry(
            inner, textvariable=self.username_var, width=30,
            bg="#2c3e50", fg=self.text_primary, insertbackground=self.text_primary,
            relief="flat", font=("Microsoft YaHei", 11)
        )
        user_entry.grid(row=0, column=1, padx=5, pady=8, sticky="ew")

        # 密码
        tk.Label(inner, text="密  码:", bg=self.bg_medium, fg=self.text_primary,
                font=("Microsoft YaHei", 10)).grid(row=1, column=0, sticky="w", padx=5, pady=8)

        self.password_var = tk.StringVar()
        self.pass_entry = tk.Entry(
            inner, textvariable=self.password_var, width=30, show="●",
            bg="#2c3e50", fg=self.text_primary, insertbackground=self.text_primary,
            relief="flat", font=("Microsoft YaHei", 11)
        )
        self.pass_entry.grid(row=1, column=1, padx=5, pady=8, sticky="ew")

        # 显示密码复选框
        self.show_pass_var = tk.BooleanVar()
        show_check = tk.Checkbutton(
            inner, text="显示", variable=self.show_pass_var,
            command=self._toggle_password_visibility,
            bg=self.bg_medium, fg=self.text_secondary, selectcolor="#2c3e50",
            activebackground=self.bg_medium, activeforeground=self.text_primary,
            font=("Microsoft YaHei", 9)
        )
        show_check.grid(row=1, column=2, padx=5, pady=8)

        # 记住密码
        self.remember_var = tk.BooleanVar()
        rem_check = tk.Checkbutton(
            inner, text="记住密码", variable=self.remember_var,
            bg=self.bg_medium, fg=self.text_secondary, selectcolor="#2c3e50",
            activebackground=self.bg_medium, activeforeground=self.text_primary,
            font=("Microsoft YaHei", 9)
        )
        rem_check.grid(row=0, column=2, padx=5, pady=8)

        # 自动登录
        self.auto_login_var = tk.BooleanVar()
        auto_check = tk.Checkbutton(
            inner, text="自动登录", variable=self.auto_login_var,
            bg=self.bg_medium, fg=self.text_secondary, selectcolor="#2c3e50",
            activebackground=self.bg_medium, activeforeground=self.text_primary,
            font=("Microsoft YaHei", 9)
        )
        auto_check.grid(row=0, column=3, padx=5, pady=8)

        inner.columnconfigure(1, weight=1)

    def _create_server_section(self):
        """创建服务端设置区域"""
        frame = ttk.LabelFrame(self.scrollable_frame, text="🌐 服务端设置", style="Dark.TLabelframe")
        frame.pack(fill="x", padx=20, pady=10)

        inner = tk.Frame(frame, bg=self.bg_medium)
        inner.pack(fill="x", padx=10, pady=10)

        # 服务端切换标签
        tk.Label(inner, text="服务端:", bg=self.bg_medium, fg=self.text_primary,
                font=("Microsoft YaHei", 10)).grid(row=0, column=0, sticky="w", padx=5, pady=5)

        self.server_switch_frame = tk.Frame(inner, bg=self.bg_medium)
        self.server_switch_frame.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self.server_a_btn = tk.Label(
            self.server_switch_frame, text="A: 192.168.200.128:1433",
            bg=self.bg_light, fg=self.text_primary, cursor="hand2",
            font=("Microsoft YaHei", 9, "bold"), padx=10, pady=4
        )
        self.server_a_btn.pack(side="left", padx=(0, 5))
        self.server_a_btn.bind("<Button-1>", lambda e: self._switch_server("A"))

        self.server_b_btn = tk.Label(
            self.server_switch_frame, text="B: 127.0.0.1:8080",
            bg=self.bg_light, fg=self.text_primary, cursor="hand2",
            font=("Microsoft YaHei", 9, "bold"), padx=10, pady=4
        )
        self.server_b_btn.pack(side="left")
        self.server_b_btn.bind("<Button-1>", lambda e: self._switch_server("B"))

        # IP 地址
        tk.Label(inner, text="IP 地址:", bg=self.bg_medium, fg=self.text_primary,
                font=("Microsoft YaHei", 10)).grid(row=1, column=0, sticky="w", padx=5, pady=5)

        self.server_ip_var = tk.StringVar()
        ip_entry = tk.Entry(
            inner, textvariable=self.server_ip_var, width=20,
            bg="#2c3e50", fg=self.text_primary, insertbackground=self.text_primary,
            relief="flat", font=("Microsoft YaHei", 10)
        )
        ip_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # 端口
        tk.Label(inner, text="端口:", bg=self.bg_medium, fg=self.text_primary,
                font=("Microsoft YaHei", 10)).grid(row=1, column=2, sticky="w", padx=(20, 5), pady=5)

        self.server_port_var = tk.StringVar()
        port_entry = tk.Entry(
            inner, textvariable=self.server_port_var, width=10,
            bg="#2c3e50", fg=self.text_primary, insertbackground=self.text_primary,
            relief="flat", font=("Microsoft YaHei", 10)
        )
        port_entry.grid(row=1, column=3, padx=5, pady=5, sticky="w")

        # 检测按钮
        self.check_btn = ttk.Button(
            inner, text="🔍 检测服务端", command=self._check_server_status,
            style="Success.TButton"
        )
        self.check_btn.grid(row=1, column=4, padx=10, pady=5)

        # 状态标签
        self.server_status_label = tk.Label(
            inner, text="未检测", bg=self.bg_medium, font=("Microsoft YaHei", 9)
        )
        self.server_status_label.grid(row=1, column=5, padx=5, pady=5)

        # 自动搜索服务端按钮
        self.scan_btn = ttk.Button(
            inner, text="🔍 自动搜索虚拟机服务端",
            command=self._auto_scan_servers,
            style="Warning.TButton"
        )
        self.scan_btn.grid(row=2, column=0, columnspan=3, padx=5, pady=10, sticky="w")

        # 自动搜索凭据按钮
        self.cred_scan_btn = ttk.Button(
            inner, text="🔑 自动搜索管理员/数据库凭据",
            command=self._auto_scan_credentials,
            style="Warning.TButton"
        )
        self.cred_scan_btn.grid(row=2, column=3, columnspan=3, padx=5, pady=10, sticky="w")

        inner.columnconfigure(1, weight=1)

    def _create_advanced_section(self):
        """创建高级设置区域"""
        frame = ttk.LabelFrame(self.scrollable_frame, text="⚙ 高级设置", style="Dark.TLabelframe")
        frame.pack(fill="x", padx=20, pady=10)

        inner = tk.Frame(frame, bg=self.bg_medium)
        inner.pack(fill="x", padx=10, pady=10)

        # 启动参数
        tk.Label(inner, text="启动参数:", bg=self.bg_medium, fg=self.text_primary,
                font=("Microsoft YaHei", 10)).grid(row=0, column=0, sticky="w", padx=5, pady=5)

        self.launch_params_var = tk.StringVar(value="-launch -windowed")
        params_entry = tk.Entry(
            inner, textvariable=self.launch_params_var, width=50,
            bg="#2c3e50", fg=self.text_primary, insertbackground=self.text_primary,
            relief="flat", font=("Microsoft YaHei", 10)
        )
        params_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # 虚拟机联动
        self.auto_vm_var = tk.BooleanVar()
        vm_check = tk.Checkbutton(
            inner, text="启动前自动开启虚拟机", variable=self.auto_vm_var,
            bg=self.bg_medium, fg=self.text_secondary, selectcolor="#2c3e50",
            activebackground=self.bg_medium, activeforeground=self.text_primary,
            font=("Microsoft YaHei", 9)
        )
        vm_check.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="w")

        # 虚拟机路径
        tk.Label(inner, text="VM路径:", bg=self.bg_medium, fg=self.text_primary,
                font=("Microsoft YaHei", 10)).grid(row=2, column=0, sticky="w", padx=5, pady=5)

        self.vm_path_var = tk.StringVar()
        vm_entry = tk.Entry(
            inner, textvariable=self.vm_path_var, width=50,
            bg="#2c3e50", fg=self.text_primary, insertbackground=self.text_primary,
            relief="flat", font=("Microsoft YaHei", 10)
        )
        vm_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        vm_browse_btn = ttk.Button(
            inner, text="浏览...", command=self._browse_vm_path,
            style="Accent.TButton"
        )
        vm_browse_btn.grid(row=2, column=2, padx=5, pady=5)

        inner.columnconfigure(1, weight=1)

    def _create_launch_section(self):
        """创建启动按钮区域"""
        frame = tk.Frame(self.scrollable_frame, bg=self.bg_dark)
        frame.pack(fill="x", padx=20, pady=15)

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            frame, variable=self.progress_var, maximum=100,
            style="Custom.Horizontal.TProgressbar", length=860
        )
        self.progress_bar.pack(fill="x", pady=(0, 10))

        # 状态标签
        self.status_label = tk.Label(
            frame, text="就绪", bg=self.bg_dark, fg=self.text_secondary,
            font=("Microsoft YaHei", 10)
        )
        self.status_label.pack(pady=(0, 10))

        # 启动按钮
        self.launch_btn = tk.Button(
            frame, text="🚀 启动游戏",
            command=self._launch_game,
            bg=self.accent, fg=self.text_primary,
            font=("Microsoft YaHei", 14, "bold"),
            padx=60, pady=12,
            relief="flat", cursor="hand2",
            activebackground=self.accent_hover,
            activeforeground=self.text_primary,
        )
        self.launch_btn.pack()

        # 绑定悬停效果
        self.launch_btn.bind("<Enter>", lambda e: self.launch_btn.config(bg=self.accent_hover))
        self.launch_btn.bind("<Leave>", lambda e: self.launch_btn.config(bg=self.accent))

    def _create_log_section(self):
        """创建日志区域"""
        frame = ttk.LabelFrame(self.scrollable_frame, text="📊 运行日志", style="Dark.TLabelframe")
        frame.pack(fill="both", expand=True, padx=20, pady=(10, 20))

        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(
            frame, height=10, bg="#0d1117", fg="#c9d1d9",
            insertbackground="#c9d1d9", relief="flat",
            font=("Consolas", 9), wrap="word"
        )
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)

        # 日志颜色标签
        self.log_text.tag_config("INFO", foreground="#58a6ff")
        self.log_text.tag_config("WARN", foreground="#f0883e")
        self.log_text.tag_config("ERROR", foreground="#f85149")
        self.log_text.tag_config("DEBUG", foreground="#8b949e")
        self.log_text.tag_config("TIME", foreground="#6e7681")

        # 清空日志按钮
        clear_btn = ttk.Button(
            frame, text="清空日志", command=self._clear_log,
            style="Accent.TButton"
        )
        clear_btn.pack(pady=(0, 10))

        # 启动日志更新定时器
        self._update_log()

    # =========================================================
    # 事件处理
    # =========================================================

    def _on_mousewheel(self, event):
        """鼠标滚轮滚动"""
        self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _toggle_password_visibility(self):
        """切换密码可见性"""
        if self.show_pass_var.get():
            self.pass_entry.config(show="")
        else:
            self.pass_entry.config(show="●")

    def _switch_server(self, server):
        """切换服务端 A/B"""
        config.set("current_server", server)

        if server == "A":
            self.server_a_btn.config(bg=self.accent, fg="#ffffff")
            self.server_b_btn.config(bg=self.bg_light, fg=self.text_primary)
            self.server_ip_var.set(config.get("server_a_ip"))
            self.server_port_var.set(str(config.get("server_a_port")))
        else:
            self.server_a_btn.config(bg=self.bg_light, fg=self.text_primary)
            self.server_b_btn.config(bg=self.accent, fg="#ffffff")
            self.server_ip_var.set(config.get("server_b_ip"))
            self.server_port_var.set(str(config.get("server_b_port")))

        self.server_status_label.config(text="未检测", fg=self.text_secondary)
        logger.info(f"切换到服务端 {server}: {self.server_ip_var.get()}:{self.server_port_var.get()}")

    def _browse_game_path(self):
        """浏览选择游戏目录"""
        path = filedialog.askdirectory(title="选择剑灵游戏目录")
        if path:
            self.game_path_var.set(path)
            self._validate_game_path()
            config.set("game_path", path)

    def _browse_vm_path(self):
        """浏览选择虚拟机路径"""
        path = filedialog.askopenfilename(
            title="选择虚拟机文件",
            filetypes=[("VMX 文件", "*.vmx"), ("所有文件", "*.*")]
        )
        if path:
            self.vm_path_var.set(path)
            config.set("vm_path", path)

    def _validate_game_path(self):
        """验证游戏路径"""
        path = self.game_path_var.get()
        exe = GameLauncher.find_game_exe(path)
        if exe:
            self.path_status_label.config(text="✅ 已找到游戏文件", fg=self.success)
            config.set("game_exe", os.path.relpath(exe, path) if exe.startswith(path) else exe)
        else:
            self.path_status_label.config(text="⚠ 未找到游戏文件", fg=self.warning)

    def _auto_detect_game(self):
        """自动检测游戏路径"""
        detected_path, detected_exe = GameLauncher.auto_detect_game_path()
        if detected_path:
            self.game_path_var.set(detected_path)
            config.set("game_path", detected_path)
            if detected_exe:
                rel_path = os.path.relpath(detected_exe, detected_path)
                self.game_exe_var.set(rel_path)
                config.set("game_exe", rel_path)
            self.path_status_label.config(text="✅ 自动检测成功", fg=self.success)
            logger.info(f"自动检测到游戏路径: {detected_path}")
        else:
            logger.warn("未能自动检测到游戏路径，请手动选择")

    def _check_server_status(self):
        """检测服务端状态"""
        ip = self.server_ip_var.get().strip()
        try:
            port = int(self.server_port_var.get().strip())
        except ValueError:
            self.server_status_label.config(text="端口无效", fg=self.error_color)
            return

        self.server_status_label.config(text="检测中...", fg=self.warning)
        self.check_btn.config(state="disabled")

        def check_thread():
            start_time = time.time()
            is_online = NetworkUtils.check_port(ip, port, timeout=3)
            latency = int((time.time() - start_time) * 1000)

            if is_online:
                self.server_status_label.config(
                    text=f"✅ 在线 ({latency}ms)", fg=self.success
                )
                logger.info(f"服务端 {ip}:{port} 在线，延迟 {latency}ms")
            else:
                self.server_status_label.config(text="❌ 离线", fg=self.error_color)
                logger.warn(f"服务端 {ip}:{port} 离线")

            self.check_btn.config(state="normal")

        threading.Thread(target=check_thread, daemon=True).start()

    def _auto_scan_servers(self):
        """自动搜索虚拟机服务端"""
        self.scan_btn.config(state="disabled", text="🔍 扫描中...")
        self.status_label.config(text="正在扫描虚拟机服务端...")
        self.progress_var.set(0)

        def scan_thread():
            try:
                # 获取扫描目标
                hosts = NetworkUtils.get_arp_table()
                networks = NetworkUtils.get_vm_networks()

                # 扩展主机列表
                for net in networks:
                    for i in range(1, 255):
                        hosts.append(f"{net}.{i}")

                # 去重
                hosts = list(set(hosts))
                hosts = [h for h in hosts if NetworkUtils._is_valid_ip(h)]

                logger.info(f"开始扫描，目标主机数: {len(hosts)}")

                # 常见游戏/数据库端口
                ports = [1433, 8080, 9999, 7777, 2106, 30303, 80, 443, 9443,
                         7000, 7100, 7200, 7300, 8000, 9000, 10443, 3306, 5432]

                results = []

                def update_progress(pct):
                    self.progress_var.set(pct)

                # 多线程扫描
                threads = []
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
                    futures = []
                    for host in hosts:
                        for port in ports:
                            futures.append(executor.submit(NetworkUtils.check_port, host, port, 1))
                        if len(futures) > 10000:
                            break

                    done_count = 0
                    total = len(futures)
                    for f in concurrent.futures.as_completed(futures):
                        done_count += 1
                        if done_count % 100 == 0:
                            self.progress_var.set(int((done_count / total) * 100))

                # 重新扫描获取结果
                results = []
                for host in hosts[:50]:  # 限制扫描范围
                    for port in ports:
                        if NetworkUtils.check_port(host, port, 1):
                            results.append((host, port))

                # 显示结果
                self.root.after(0, lambda: self._show_scan_results(results))

            except Exception as e:
                logger.error(f"扫描出错: {e}")
                self.root.after(0, lambda: self.status_label.config(text=f"扫描出错: {e}"))
            finally:
                self.root.after(0, lambda: self.scan_btn.config(state="normal", text="🔍 自动搜索虚拟机服务端"))

        threading.Thread(target=scan_thread, daemon=True).start()

    def _show_scan_results(self, results):
        """显示扫描结果"""
        self.progress_var.set(100)

        if not results:
            self.status_label.config(text="未找到任何在线服务端")
            messagebox.showinfo("扫描结果", "未找到任何在线服务端。\n\n请确保：\n1. 虚拟机已启动\n2. 服务端程序正在运行\n3. 防火墙未阻止端口")
            return

        # 创建结果窗口
        result_window = tk.Toplevel(self.root)
        result_window.title("🔍 扫描结果")
        result_window.geometry("700x500")
        result_window.configure(bg=self.bg_dark)
        result_window.transient(self.root)
        result_window.grab_set()

        # 标题
        tk.Label(
            result_window, text=f"发现 {len(results)} 个在线服务端",
            font=("Microsoft YaHei", 14, "bold"), fg=self.accent, bg=self.bg_dark
        ).pack(pady=10)

        # Notebook 标签页
        notebook = ttk.Notebook(result_window)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # 服务端列表页
        server_frame = tk.Frame(notebook, bg=self.bg_medium)
        notebook.add(server_frame, text="🌐 服务端列表")

        server_text = scrolledtext.ScrolledText(
            server_frame, bg="#0d1117", fg="#c9d1d9", font=("Consolas", 10)
        )
        server_text.pack(fill="both", expand=True, padx=10, pady=10)

        current_ip, current_port = config.get_current_server()

        for i, (host, port) in enumerate(results):
            is_current = (host == current_ip and port == current_port)
            marker = " ✅ 当前" if is_current else ""
            line = f"[{i+1}] {host}:{port}{marker}\n"
            server_text.insert("end", line)

        # 绑定双击事件
        server_text.bind("<Double-Button-1>", lambda e: self._on_result_double_click(
            server_text, results, result_window
        ))

        tk.Label(
            server_frame, text="💡 双击服务端地址可将其应用到当前配置",
            bg=self.bg_medium, fg=self.text_secondary, font=("Microsoft YaHei", 9)
        ).pack(pady=(0, 10))

        # 关闭按钮
        tk.Button(
            result_window, text="关闭", command=result_window.destroy,
            bg=self.bg_light, fg=self.text_primary, font=("Microsoft YaHei", 10),
            padx=30, pady=5, relief="flat"
        ).pack(pady=10)

        self.status_label.config(text=f"扫描完成，发现 {len(results)} 个在线服务端")

    def _on_result_double_click(self, text_widget, results, window):
        """双击扫描结果中的服务端"""
        index = text_widget.index("@%x,%y" % (text_widget.winfo_pointerx() - text_widget.winfo_rootx(),
                                               text_widget.winfo_pointery() - text_widget.winfo_rooty()))
        line = text_widget.get(index + " linestart", index + " lineend")
        # 解析 IP:端口
        import re
        match = re.search(r'(\d+\.\d+\.\d+\.\d+):(\d+)', line)
        if match:
            ip = match.group(1)
            port = int(match.group(2))
            self.server_ip_var.set(ip)
            self.server_port_var.set(str(port))
            config.set("server_ip", ip)
            config.set("server_port", port)
            self.server_status_label.config(text="未检测", fg=self.text_secondary)
            logger.info(f"应用服务端: {ip}:{port}")
            messagebox.showinfo("应用成功", f"已应用服务端配置:\n{ip}:{port}")

    def _auto_scan_credentials(self):
        """自动搜索管理员和数据库凭据"""
        current_ip, current_port = config.get_current_server()

        if not NetworkUtils.check_port(current_ip, current_port, timeout=2):
            messagebox.showwarning(
                "服务端离线",
                f"当前服务端 {current_ip}:{current_port} 不在线。\n\n请先确保服务端正在运行，再进行凭据扫描。"
            )
            return

        self.cred_scan_btn.config(state="disabled", text="🔑 扫描中...")
        self.status_label.config(text="正在扫描凭据...")

        def scan_thread():
            try:
                admin_found = CredentialScanner.scan_admin_creds(current_ip, current_port)
                db_found = []

                for db_type in ["mssql", "mysql", "postgresql"]:
                    creds = CredentialScanner.scan_db_creds(current_ip, db_type)
                    db_found.extend(creds)

                self.root.after(0, lambda: self._show_credential_results(admin_found, db_found))

            except Exception as e:
                logger.error(f"凭据扫描出错: {e}")
                self.root.after(0, lambda: self.status_label.config(text=f"凭据扫描出错: {e}"))
            finally:
                self.root.after(0, lambda: self.cred_scan_btn.config(
                    state="normal", text="🔑 自动搜索管理员/数据库凭据"
                ))

        threading.Thread(target=scan_thread, daemon=True).start()

    def _show_credential_results(self, admin_creds, db_creds):
        """显示凭据扫描结果"""
        total = len(admin_creds) + len(db_creds)
        self.status_label.config(text=f"凭据扫描完成，发现 {total} 组凭据")

        if total == 0:
            messagebox.showinfo(
                "凭据扫描结果",
                f"未找到任何匹配的凭据。\n\n这可能意味着：\n1. 服务端使用了非默认密码\n2. 数据库端口未开放\n3. 需要更高权限访问"
            )
            return

        # 创建结果窗口
        cred_window = tk.Toplevel(self.root)
        cred_window.title("🔑 凭据发现")
        cred_window.geometry("800x550")
        cred_window.configure(bg=self.bg_dark)
        cred_window.transient(self.root)
        cred_window.grab_set()

        tk.Label(
            cred_window, text=f"发现 {total} 组可用凭据",
            font=("Microsoft YaHei", 14, "bold"), fg=self.accent, bg=self.bg_dark
        ).pack(pady=10)

        notebook = ttk.Notebook(cred_window)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # 管理员凭据页
        if admin_creds:
            admin_frame = tk.Frame(notebook, bg=self.bg_medium)
            notebook.add(admin_frame, text=f"🔐 管理员凭据 ({len(admin_creds)})")

            admin_text = scrolledtext.ScrolledText(
                admin_frame, bg="#0d1117", fg="#c9d1d9", font=("Consolas", 10)
            )
            admin_text.pack(fill="both", expand=True, padx=10, pady=10)

            for i, cred in enumerate(admin_creds):
                line = f"[{i+1}] 类型: {cred['type']}\n"
                line += f"    账号: {cred['username']}\n"
                line += f"    密码: {cred['password']}\n"
                line += f"    来源: {cred['source']}\n\n"
                admin_text.insert("end", line)

        # 数据库凭据页
        if db_creds:
            db_frame = tk.Frame(notebook, bg=self.bg_medium)
            notebook.add(db_frame, text=f"🗄️ 数据库凭据 ({len(db_creds)})")

            db_text = scrolledtext.ScrolledText(
                db_frame, bg="#0d1117", fg="#c9d1d9", font=("Consolas", 10)
            )
            db_text.pack(fill="both", expand=True, padx=10, pady=10)

            for i, cred in enumerate(db_creds):
                line = f"[{i+1}] 类型: {cred['type']}\n"
                line += f"    账号: {cred['username']}\n"
                line += f"    密码: {cred['password']}\n"
                line += f"    地址: {cred['host']}\n\n"
                db_text.insert("end", line)

        # 应用凭据按钮
        def apply_first_cred():
            if admin_creds:
                cred = admin_creds[0]
                self.username_var.set(cred['username'])
                self.password_var.set(cred['password'])
                config.set("username", cred['username'])
                config.set("password", cred['password'])
                messagebox.showinfo("应用成功", f"已应用管理员凭据:\n{cred['username']} / {cred['password']}")
            elif db_creds:
                cred = db_creds[0]
                self.username_var.set(cred['username'])
                self.password_var.set(cred['password'])
                config.set("username", cred['username'])
                config.set("password", cred['password'])
                messagebox.showinfo("应用成功", f"已应用数据库凭据:\n{cred['username']} / {cred['password']}")

        tk.Button(
            cred_window, text="✅ 应用第一组凭据到登录表单",
            command=apply_first_cred,
            bg=self.success, fg=self.text_primary, font=("Microsoft YaHei", 10, "bold"),
            padx=30, pady=8, relief="flat"
        ).pack(pady=5)

        tk.Button(
            cred_window, text="关闭", command=cred_window.destroy,
            bg=self.bg_light, fg=self.text_primary, font=("Microsoft YaHei", 10),
            padx=30, pady=5, relief="flat"
        ).pack(pady=10)

    def _launch_game(self):
        """启动游戏"""
        # 保存当前配置
        self._save_ui_to_config()

        # 验证
        game_path = config.get("game_path", "")
        if not game_path:
            messagebox.showwarning("警告", "请先设置游戏目录！")
            return

        exe_path = GameLauncher.find_game_exe(game_path)
        if not exe_path:
            messagebox.showerror("错误", f"未找到游戏可执行文件！\n\n请检查游戏路径和游戏EXE设置。")
            return

        # 禁用启动按钮
        self.launch_btn.config(state="disabled", text="🚀 启动中...")
        self.status_label.config(text="正在启动游戏...")
        self.progress_var.set(0)

        def launch_thread():
            try:
                # 步骤 1: 检测服务端
                self.root.after(0, lambda: self.status_label.config(text="步骤 1/4: 检测服务端..."))
                self.root.after(0, lambda: self.progress_var.set(25))

                server_ip, server_port = config.get_current_server()
                is_online = NetworkUtils.check_port(server_ip, server_port, timeout=3)

                if not is_online:
                    self.root.after(0, lambda: messagebox.showwarning(
                        "服务端离线",
                        f"服务端 {server_ip}:{server_port} 不在线。\n\n是否仍要启动游戏？"
                    ))
                    # 继续启动

                # 步骤 2: 启动虚拟机（如果勾选）
                if config.get("auto_start_vm"):
                    vm_path = config.get("vm_path", "")
                    if vm_path and os.path.exists(vm_path):
                        self.root.after(0, lambda: self.status_label.config(text="步骤 2/4: 启动虚拟机..."))
                        self.root.after(0, lambda: self.progress_var.set(50))
                        try:
                            if IS_WINDOWS:
                                subprocess.Popen(
                                    ["vmrun", "start", vm_path],
                                    creationflags=subprocess.CREATE_NO_WINDOW
                                )
                            else:
                                subprocess.Popen(["vmrun", "start", vm_path])
                            time.sleep(5)  # 等待虚拟机启动
                        except:
                            logger.warn("虚拟机启动失败，继续执行")

                # 步骤 3: 注入凭据并启动游戏
                self.root.after(0, lambda: self.status_label.config(text="步骤 3/4: 注入登录信息..."))
                self.root.after(0, lambda: self.progress_var.set(75))

                success, msg = GameLauncher.launch_game()

                # 步骤 4: 完成
                self.root.after(0, lambda: self.status_label.config(text="步骤 4/4: 完成"))
                self.root.after(0, lambda: self.progress_var.set(100))

                if success:
                    self.root.after(0, lambda: self.status_label.config(text="✅ 游戏启动成功！"))
                    self.root.after(0, lambda: messagebox.showinfo("成功", "游戏已成功启动！"))
                else:
                    self.root.after(0, lambda: self.status_label.config(text=f"❌ 启动失败: {msg}"))
                    self.root.after(0, lambda: messagebox.showerror("启动失败", msg))

                # 保存配置
                config.save()

            except Exception as e:
                logger.error(f"启动过程出错: {e}")
                self.root.after(0, lambda: self.status_label.config(text=f"❌ 错误: {e}"))
                self.root.after(0, lambda: messagebox.showerror("错误", str(e)))
            finally:
                self.root.after(0, lambda: self.launch_btn.config(state="normal", text="🚀 启动游戏"))

        threading.Thread(target=launch_thread, daemon=True).start()

    def _save_ui_to_config(self):
        """将界面数据保存到配置"""
        config.set("game_path", self.game_path_var.get())
        config.set("game_exe", self.game_exe_var.get())
        config.set("username", self.username_var.get())
        config.set("password", self.password_var.get())
        config.set("remember_password", self.remember_var.get())
        config.set("auto_login", self.auto_login_var.get())
        config.set("server_ip", self.server_ip_var.get())
        config.set("server_port", int(self.server_port_var.get()) if self.server_port_var.get().isdigit() else 8080)
        config.set("launch_params", self.launch_params_var.get())
        config.set("auto_start_vm", self.auto_vm_var.get())
        config.set("vm_path", self.vm_path_var.get())

        # 更新服务端 A/B
        current = config.get("current_server")
        if current == "A":
            config.set("server_a_ip", self.server_ip_var.get())
            config.set("server_a_port", int(self.server_port_var.get()) if self.server_port_var.get().isdigit() else 1433)
        else:
            config.set("server_b_ip", self.server_ip_var.get())
            config.set("server_b_port", int(self.server_port_var.get()) if self.server_port_var.get().isdigit() else 8080)

    def _load_config_to_ui(self):
        """将配置加载到界面"""
        self.game_path_var.set(config.get("game_path", ""))
        self.game_exe_var.set(config.get("game_exe", "bin/client.exe"))
        self.username_var.set(config.get("username", ""))
        self.password_var.set(config.get("password", ""))
        self.remember_var.set(config.get("remember_password", False))
        self.auto_login_var.set(config.get("auto_login", False))
        self.launch_params_var.set(config.get("launch_params", "-launch -windowed"))
        self.auto_vm_var.set(config.get("auto_start_vm", False))
        self.vm_path_var.set(config.get("vm_path", ""))

        # 服务端切换
        current = config.get("current_server", "A")
        if current == "B":
            self._switch_server("B")
        else:
            self._switch_server("A")

    def _clear_log(self):
        """清空日志"""
        self.log_text.delete("1.0", "end")
        logger.clear()

    def _update_log(self):
        """更新日志显示"""
        logs = logger.get_all()
        current_text = self.log_text.get("1.0", "end").strip()

        if logs:
            last_log = logs[-1]
            log_line = f"[{last_log['time']}] [{last_log['level']}] {last_log['message']}\n"

            self.log_text.insert("end", log_line, last_log['level'])
            self.log_text.see("end")

        # 每 500ms 更新一次
        self.root.after(500, self._update_log)


# ============================================================
# 主入口
# ============================================================

def main():
    """主函数"""
    if TKINTER_AVAILABLE:
        # 正常启动 GUI
        root = tk.Tk()
        app = BnSLauncherGUI(root)

        # 保存配置 on close
        def on_closing():
            app._save_ui_to_config()
            config.save()
            root.destroy()

        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.mainloop()
    else:
        # 无 Tkinter 时的命令行模式
        print("=" * 60)
        print("  剑灵 2.0 启动器 - 命令行模式")
        print("=" * 60)
        print()
        print("⚠ 警告: 当前环境不支持图形界面 (tkinter 不可用)")
        print("   如需使用图形界面，请在 Windows 10 系统上运行此程序。")
        print()
        print("--- 当前配置 ---")
        for key, value in config.data.items():
            if "password" in key.lower() and value:
                print(f"  {key}: ******")
            else:
                print(f"  {key}: {value}")
        print()
        print("--- 可用功能 ---")
        print("  1. 检查服务端状态")
        print("  2. 扫描局域网服务端")
        print("  3. 启动游戏")
        print()

        while True:
            choice = input("请选择操作 (1-3, q 退出): ").strip()
            if choice == "q":
                break
            elif choice == "1":
                ip, port = config.get_current_server()
                online = NetworkUtils.check_port(ip, port)
                print(f"  服务端 {ip}:{port}: {'在线' if online else '离线'}")
            elif choice == "2":
                print("  开始扫描...")
                hosts = NetworkUtils.get_arp_table()
                networks = NetworkUtils.get_vm_networks()
                for net in networks:
                    for i in range(1, 255):
                        hosts.append(f"{net}.{i}")
                hosts = list(set(h for h in hosts if NetworkUtils._is_valid_ip(h)))
                ports = [1433, 8080, 9999, 7777, 3306, 5432]
                found = []
                for host in hosts[:100]:
                    for port in ports:
                        if NetworkUtils.check_port(host, port, 1):
                            found.append((host, port))
                print(f"  发现 {len(found)} 个在线服务:")
                for h, p in found:
                    print(f"    {h}:{p}")
            elif choice == "3":
                success, msg = GameLauncher.launch_game()
                print(f"  结果: {msg}")
            else:
                print("  无效选择")


if __name__ == "__main__":
    main()
