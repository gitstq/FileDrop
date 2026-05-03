"""
安全模块 - 密码验证、速率限制、路径遍历防护
"""

import hashlib
import hmac
import time
import threading
import secrets
import re
import os


class PasswordManager:
    """密码管理器

    使用PBKDF2-HMAC-SHA256进行密码哈希和验证。

    Args:
        pepper: 密钥 peppers（可选，增加安全性）
    """

    def __init__(self, pepper=None):
        """初始化密码管理器

        Args:
            pepper: 额外的密钥 pepper
        """
        self.pepper = pepper or secrets.token_hex(16)

    def hash_password(self, password):
        """对密码进行哈希处理

        使用PBKDF2-HMAC-SHA256算法，自动生成盐值。

        Args:
            password: 明文密码

        Returns:
            格式为 'salt:hash' 的字符串
        """
        salt = secrets.token_hex(16)
        password_with_pepper = (password + self.pepper).encode("utf-8")
        salt_bytes = bytes.fromhex(salt)

        hashed = hashlib.pbkdf2_hmac(
            "sha256",
            password_with_pepper,
            salt_bytes,
            iterations=100000,
            dklen=32
        )

        return f"{salt}:{hashed.hex()}"

    def verify_password(self, password, stored_hash):
        """验证密码

        Args:
            password: 明文密码
            stored_hash: 存储的哈希值（'salt:hash'格式）

        Returns:
            密码是否正确
        """
        try:
            salt, expected_hash = stored_hash.split(":", 1)
            password_with_pepper = (password + self.pepper).encode("utf-8")
            salt_bytes = bytes.fromhex(salt)

            computed = hashlib.pbkdf2_hmac(
                "sha256",
                password_with_pepper,
                salt_bytes,
                iterations=100000,
                dklen=32
            )

            return hmac.compare_digest(computed.hex(), expected_hash)
        except (ValueError, AttributeError):
            return False

    def generate_token(self, length=32):
        """生成安全的随机令牌

        Args:
            length: 令牌长度（字节数）

        Returns:
            十六进制令牌字符串
        """
        return secrets.token_hex(length)


class RateLimiter:
    """基于滑动窗口的速率限制器

    使用线程安全的字典记录每个客户端的请求次数。

    Args:
        max_requests: 时间窗口内最大请求数
        window_seconds: 时间窗口（秒）
    """

    def __init__(self, max_requests=60, window_seconds=60):
        """初始化速率限制器

        Args:
            max_requests: 时间窗口内最大请求数
            window_seconds: 时间窗口（秒）
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests = {}  # {client_key: [timestamp, ...]}
        self._lock = threading.Lock()

    def is_allowed(self, client_key):
        """检查请求是否被允许

        Args:
            client_key: 客户端标识（通常是IP地址）

        Returns:
            (是否允许, 剩余请求数, 重置时间)
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            if client_key not in self._requests:
                self._requests[client_key] = []

            # 清理过期记录
            self._requests[client_key] = [
                ts for ts in self._requests[client_key]
                if ts > window_start
            ]

            current_count = len(self._requests[client_key])

            if current_count >= self.max_requests:
                # 计算重置时间
                oldest = min(self._requests[client_key])
                reset_time = int(oldest + self.window_seconds - now)
                if reset_time < 1:
                    reset_time = 1
                return False, 0, reset_time

            # 记录本次请求
            self._requests[client_key].append(now)
            remaining = self.max_requests - current_count - 1
            return True, remaining, self.window_seconds

    def reset(self, client_key):
        """重置指定客户端的速率限制

        Args:
            client_key: 客户端标识
        """
        with self._lock:
            if client_key in self._requests:
                del self._requests[client_key]

    def cleanup(self):
        """清理所有过期的记录"""
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            expired_keys = []
            for key, timestamps in self._requests.items():
                timestamps[:] = [ts for ts in timestamps if ts > window_start]
                if not timestamps:
                    expired_keys.append(key)

            for key in expired_keys:
                del self._requests[key]


class SecurityValidator:
    """安全验证器 - 提供各种安全检查"""

    # 危险的文件扩展名
    DANGEROUS_EXTENSIONS = {
        ".exe", ".bat", ".cmd", ".com", ".msi", ".scr", ".pif",
        ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh", ".hta",
        ".ps1", ".psm1", ".sh", ".bash", ".csh", ".tcsh",
        ".lnk", ".inf", ".reg", ".dll", ".sys", ".drv",
    }

    # 允许的文件名字符模式
    SAFE_FILENAME_PATTERN = re.compile(
        r'^[\w\-. ]+$', re.UNICODE
    )

    @staticmethod
    def is_safe_path(base_dir, requested_path):
        """检查请求的路径是否安全（防止路径遍历）

        Args:
            base_dir: 基础目录
            requested_path: 请求的路径

        Returns:
            路径是否安全
        """
        try:
            base = os.path.realpath(base_dir)
            requested = os.path.realpath(requested_path)

            # 确保请求的路径在基础目录下
            return requested.startswith(base + os.sep) or \
                   requested == base
        except (ValueError, OSError):
            return False

    @staticmethod
    def is_safe_filename(filename):
        """检查文件名是否安全

        Args:
            filename: 文件名

        Returns:
            文件名是否安全
        """
        if not filename or not filename.strip():
            return False

        # 检查长度
        if len(filename) > 255:
            return False

        # 检查是否包含路径分隔符
        if "/" in filename or "\\" in filename:
            return False

        # 检查是否包含空字节
        if "\x00" in filename:
            return False

        # 检查是否为特殊文件名
        if filename in (".", "..", "", " "):
            return False

        # 检查是否以点开头（隐藏文件）
        if filename.startswith("."):
            return False

        return True

    @classmethod
    def is_dangerous_file(cls, filename):
        """检查文件是否为危险文件类型

        Args:
            filename: 文件名

        Returns:
            是否为危险文件类型
        """
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return ext in cls.DANGEROUS_EXTENSIONS

    @staticmethod
    def sanitize_input(text):
        """清理用户输入，防止XSS和注入攻击

        Args:
            text: 用户输入文本

        Returns:
            清理后的文本
        """
        if not text:
            return ""
        # 移除控制字符（保留换行和制表符）
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        # HTML转义
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        text = text.replace("'", "&#x27;")
        return text

    @staticmethod
    def validate_password_strength(password):
        """验证密码强度

        Args:
            password: 密码

        Returns:
            (是否有效, 错误信息) 元组
        """
        if not password:
            return False, "密码不能为空"

        if len(password) < 4:
            return False, "密码长度不能少于4个字符"

        if len(password) > 128:
            return False, "密码长度不能超过128个字符"

        return True, ""
