"""
分享链接生成与管理模块
"""

from datetime import datetime, timezone, timedelta
from .database import Database
from .security import PasswordManager
from .utils import format_size, format_datetime, generate_qr_code


class ShareManager:
    """分享链接管理器

    管理文件分享链接的创建、验证、查询和导出。

    Args:
        database: 数据库实例
        password_manager: 密码管理器实例
        base_url: 服务器基础URL
    """

    def __init__(self, database, password_manager, base_url="http://localhost:8080"):
        """初始化分享管理器

        Args:
            database: 数据库实例
            password_manager: 密码管理器实例
            base_url: 服务器基础URL
        """
        self.db = database
        self.pwd_manager = password_manager
        self.base_url = base_url.rstrip("/")

    def create_share(self, file_id, password=None, expires_hours=0,
                     max_downloads=0):
        """创建分享链接

        Args:
            file_id: 文件ID
            password: 保护密码（可选）
            expires_hours: 过期时间（小时），0表示永不过期
            max_downloads: 最大下载次数，0表示不限制

        Returns:
            分享记录字典
        """
        # 验证文件存在
        file_record = self.db.get_file(file_id)
        if not file_record:
            raise ValueError(f"文件不存在: {file_id}")

        # 哈希密码
        hashed_password = ""
        if password:
            hashed_password = self.pwd_manager.hash_password(password)

        share = self.db.create_share(
            file_id=file_id,
            password=hashed_password,
            expires_hours=expires_hours,
            max_downloads=max_downloads
        )

        return share

    def get_share_url(self, share_code):
        """获取分享URL

        Args:
            share_code: 分享码

        Returns:
            完整的分享URL
        """
        return f"{self.base_url}/s/{share_code}"

    def get_share_info(self, share_code):
        """获取分享信息

        Args:
            share_code: 分享码

        Returns:
            包含分享详细信息的字典
        """
        valid, result = self.db.is_share_valid(share_code)
        if not valid:
            return {"valid": False, "error": result}

        share = result
        file_record = self.db.get_file(share["file_id"])

        return {
            "valid": True,
            "share_code": share["share_code"],
            "share_url": self.get_share_url(share_code),
            "filename": file_record["original_name"] if file_record else "未知",
            "file_size": file_record["file_size"] if file_record else 0,
            "password_protected": bool(share["password"]),
            "expires_at": share["expires_at"],
            "max_downloads": share["max_downloads"],
            "download_count": share["download_count"],
            "created_at": share["created_at"],
        }

    def verify_share_password(self, share_code, password):
        """验证分享密码

        Args:
            share_code: 分享码
            password: 用户输入的密码

        Returns:
            密码是否正确
        """
        share = self.db.get_share_by_code(share_code)
        if not share:
            return False

        if not share["password"]:
            return True  # 无密码保护

        return self.pwd_manager.verify_password(password, share["password"])

    def validate_share(self, share_code):
        """验证分享链接是否有效

        Args:
            share_code: 分享码

        Returns:
            (是否有效, 分享记录或错误信息)
        """
        return self.db.is_share_valid(share_code)

    def list_shares(self, file_id=None, active_only=True):
        """列出分享记录

        Args:
            file_id: 文件ID（可选）
            active_only: 是否只返回活跃的分享

        Returns:
            分享记录列表
        """
        return self.db.list_shares(file_id=file_id, active_only=active_only)

    def deactivate_share(self, share_code):
        """停用分享链接

        Args:
            share_code: 分享码

        Returns:
            是否成功
        """
        share = self.db.get_share_by_code(share_code)
        if not share:
            return False
        return self.db.deactivate_share(share["id"])

    def export_shares(self, format_type="json"):
        """导出分享记录

        Args:
            format_type: 导出格式 (json/csv/markdown)

        Returns:
            格式化后的字符串
        """
        return self.db.export_shares(format_type=format_type)

    def generate_qr(self, share_code):
        """为分享链接生成ASCII二维码

        Args:
            share_code: 分享码

        Returns:
            ASCII二维码字符串
        """
        url = self.get_share_url(share_code)
        return generate_qr_code(url)

    def format_share_info(self, share_code):
        """格式化分享信息为可读字符串

        Args:
            share_code: 分享码

        Returns:
            格式化后的分享信息字符串
        """
        info = self.get_share_info(share_code)

        if not info["valid"]:
            return f"分享链接无效: {info['error']}"

        lines = [
            f"文件名: {info['filename']}",
            f"文件大小: {format_size(info['file_size'])}",
            f"分享链接: {info['share_url']}",
            f"密码保护: {'是' if info['password_protected'] else '否'}",
            f"过期时间: {info['expires_at'] or '永不过期'}",
            f"下载次数: {info['download_count']}",
        ]

        if info["max_downloads"] > 0:
            lines.append(
                f"最大下载次数: {info['download_count']}/{info['max_downloads']}"
            )

        lines.append(f"创建时间: {format_datetime(info['created_at'])}")

        return "\n".join(lines)
