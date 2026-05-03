"""
HTTP服务器核心模块 - 基于http.server的轻量级文件共享服务器
"""

import os
import sys
import socket
import signal
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """多线程HTTP服务器

    支持同时处理多个请求，每个请求在独立的线程中运行。
    """
    daemon_threads = True
    allow_reuse_address = True

    def server_close(self):
        """关闭服务器"""
        super().server_close()


class FileDropServer:
    """FileDrop文件共享服务器

    封装HTTP服务器的创建、配置和生命周期管理。

    Args:
        host: 监听地址
        port: 监听端口
        storage_dir: 文件存储目录
        db_path: 数据库文件路径
        password: 访问密码（可选）
        max_size: 最大文件大小限制（字节）
        verbose: 是否显示详细日志
    """

    def __init__(self, host="0.0.0.0", port=8080, storage_dir=None,
                 db_path=None, password=None, max_size=0, verbose=True):
        """初始化服务器

        Args:
            host: 监听地址
            port: 监听端口
            storage_dir: 文件存储目录
            db_path: 数据库文件路径
            password: 访问密码
            max_size: 最大文件大小限制
            verbose: 是否显示详细日志
        """
        self.host = host
        self.port = port
        self.verbose = verbose

        # 设置存储目录
        if storage_dir is None:
            storage_dir = os.path.join(os.getcwd(), "filedrop_data")
        self.storage_dir = os.path.abspath(storage_dir)

        # 设置数据库路径
        if db_path is None:
            os.makedirs(self.storage_dir, exist_ok=True)
            db_path = os.path.join(self.storage_dir, "filedrop.db")
        self.db_path = db_path

        # 初始化组件
        from .storage import Storage
        from .database import Database
        from .security import PasswordManager, RateLimiter
        from .share import ShareManager
        from .handlers import FileDropHandler

        self.storage = Storage(self.storage_dir)
        self.database = Database(self.db_path)
        self.password_manager = PasswordManager()
        self.rate_limiter = RateLimiter(max_requests=120, window_seconds=60)

        # 密码处理
        self.password_hash = ""
        if password:
            self.password_hash = self.password_manager.hash_password(password)

        # 分享管理器
        base_url = f"http://{host}:{port}"
        if host == "0.0.0.0":
            base_url = f"http://localhost:{port}"
        self.share_manager = ShareManager(
            self.database, self.password_manager, base_url
        )

        # 服务器状态（传递给请求处理器）
        self.server_state = {
            "storage": self.storage,
            "database": self.database,
            "password_manager": self.password_manager,
            "rate_limiter": self.rate_limiter,
            "share_manager": self.share_manager,
            "password": password,
            "password_hash": self.password_hash,
            "max_size": max_size,
            "verbose": verbose,
            "storage_dir": self.storage_dir,
        }

        # 设置处理器状态
        FileDropHandler.server_state = self.server_state

        # 创建HTTP服务器
        self.httpd = ThreadedHTTPServer((self.host, self.port), FileDropHandler)

        # 注册信号处理
        self._shutdown_event = threading.Event()

    def start(self):
        """启动服务器"""
        if self.verbose:
            print(f"\n  ╔══════════════════════════════════════╗")
            print(f"  ║       FileDrop 文件共享服务器         ║")
            print(f"  ╠══════════════════════════════════════╣")
            print(f"  ║  地址: http://{self.host}:{self.port}")
            print(f"  ║  存储: {self.storage_dir}")
            print(f"  ║  数据库: {self.db_path}")
            if self.password_hash:
                print(f"  ║  认证: 已启用密码保护")
            else:
                print(f"  ║  认证: 未启用")
            max_size_str = self._format_size(self.server_state["max_size"])
            print(f"  ║  大小限制: {max_size_str}")
            print(f"  ╠══════════════════════════════════════╣")
            print(f"  ║  按 Ctrl+C 停止服务器                ║")
            print(f"  ╚══════════════════════════════════════╝\n")

        try:
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            if self.verbose:
                print("\n正在关闭服务器...")
        finally:
            self.stop()

    def stop(self):
        """停止服务器"""
        # 先清除处理器状态，防止新请求访问数据库
        try:
            from .handlers import FileDropHandler
            FileDropHandler.server_state = None
        except Exception:
            pass

        try:
            self.httpd.shutdown()
            self.httpd.server_close()
        except Exception:
            pass

        # 等待工作线程完成
        time.sleep(0.3)

        # 关闭数据库连接
        try:
            self.database.close()
        except Exception:
            pass

        if self.verbose:
            print("服务器已关闭。")

    def serve_background(self):
        """在后台线程中启动服务器

        Returns:
            服务器线程
        """
        server_thread = threading.Thread(target=self.start, daemon=True)
        server_thread.start()
        return server_thread

    def get_url(self):
        """获取服务器URL

        Returns:
            服务器URL字符串
        """
        return f"http://{self.host}:{self.port}"

    @staticmethod
    def _format_size(size_bytes):
        """格式化文件大小"""
        if size_bytes is None or size_bytes <= 0:
            return "无限制"
        units = ["B", "KB", "MB", "GB", "TB"]
        index = 0
        size = float(size_bytes)
        while size >= 1024.0 and index < len(units) - 1:
            size /= 1024.0
            index += 1
        if index == 0:
            return f"{int(size)} {units[index]}"
        return f"{size:.1f} {units[index]}"
