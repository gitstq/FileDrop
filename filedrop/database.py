"""
SQLite数据库管理模块 - 管理文件元数据和分享记录
"""

import os
import sqlite3
import json
import uuid
import threading
from datetime import datetime, timezone


class Database:
    """SQLite数据库管理器

    管理文件元数据表和分享记录表，提供CRUD操作接口。
    所有数据库操作通过线程锁保护，支持多线程访问。

    Args:
        db_path: 数据库文件路径
    """

    def __init__(self, db_path=None):
        """初始化数据库连接并创建表结构

        Args:
            db_path: 数据库文件路径，默认为内存数据库
        """
        if db_path is None:
            self.db_path = ":memory:"
        else:
            self.db_path = db_path

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    def _create_tables(self):
        """创建数据库表结构"""
        cursor = self.conn.cursor()

        # 文件元数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                original_name TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                mime_type TEXT NOT NULL DEFAULT 'application/octet-stream',
                upload_time TEXT NOT NULL,
                upload_ip TEXT DEFAULT '',
                description TEXT DEFAULT '',
                is_public INTEGER DEFAULT 1
            )
        """)

        # 分享记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shares (
                id TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                share_code TEXT UNIQUE NOT NULL,
                password TEXT DEFAULT '',
                expires_at TEXT DEFAULT '',
                max_downloads INTEGER DEFAULT 0,
                download_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                last_download_at TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (file_id) REFERENCES files(id)
            )
        """)

        # 下载日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS download_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                share_id TEXT NOT NULL,
                file_id TEXT NOT NULL,
                download_time TEXT NOT NULL,
                download_ip TEXT DEFAULT '',
                user_agent TEXT DEFAULT '',
                FOREIGN KEY (share_id) REFERENCES shares(id),
                FOREIGN KEY (file_id) REFERENCES files(id)
            )
        """)

        # 创建索引
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_files_hash ON files(file_hash)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_shares_code ON shares(share_code)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_shares_file_id ON shares(file_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_download_logs_share ON download_logs(share_id)"
        )

        self.conn.commit()

    def add_file(self, filename, original_name, file_hash, file_size,
                 mime_type="application/octet-stream", upload_ip="",
                 description="", is_public=True):
        """添加文件记录

        Args:
            filename: 存储文件名
            original_name: 原始文件名
            file_hash: SHA256哈希值
            file_size: 文件大小（字节）
            mime_type: MIME类型
            upload_ip: 上传者IP
            description: 文件描述
            is_public: 是否公开

        Returns:
            文件ID
        """
        file_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            self.conn.execute(
                """INSERT INTO files
                   (id, filename, original_name, file_hash, file_size, mime_type,
                    upload_time, upload_ip, description, is_public)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (file_id, filename, original_name, file_hash, file_size,
                 mime_type, now, upload_ip, description, int(is_public))
            )
            self.conn.commit()
        return file_id

    def get_file(self, file_id):
        """根据ID获取文件记录

        Args:
            file_id: 文件ID

        Returns:
            文件记录字典，不存在返回None
        """
        with self._lock:
            cursor = self.conn.execute(
                "SELECT * FROM files WHERE id = ?", (file_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_file_by_hash(self, file_hash):
        """根据哈希值查找文件

        Args:
            file_hash: SHA256哈希值

        Returns:
            文件记录字典，不存在返回None
        """
        with self._lock:
            cursor = self.conn.execute(
                "SELECT * FROM files WHERE file_hash = ? LIMIT 1", (file_hash,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_files(self, search=None, sort_by="upload_time", sort_order="desc",
                   offset=0, limit=100):
        """列出文件

        Args:
            search: 搜索关键词
            sort_by: 排序字段
            sort_order: 排序方向 (asc/desc)
            offset: 偏移量
            limit: 返回数量

        Returns:
            文件记录列表
        """
        allowed_sort = {"upload_time", "filename", "file_size", "original_name"}
        if sort_by not in allowed_sort:
            sort_by = "upload_time"
        if sort_order.lower() not in ("asc", "desc"):
            sort_order = "desc"

        if search:
            query = f"""
                SELECT * FROM files
                WHERE original_name LIKE ? OR description LIKE ?
                ORDER BY {sort_by} {sort_order}
                LIMIT ? OFFSET ?
            """
            params = (f"%{search}%", f"%{search}%", limit, offset)
        else:
            query = f"""
                SELECT * FROM files
                ORDER BY {sort_by} {sort_order}
                LIMIT ? OFFSET ?
            """
            params = (limit, offset)

        with self._lock:
            cursor = self.conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def delete_file(self, file_id):
        """删除文件记录

        Args:
            file_id: 文件ID

        Returns:
            是否删除成功
        """
        with self._lock:
            cursor = self.conn.execute(
                "DELETE FROM files WHERE id = ?", (file_id,)
            )
            # 同时删除相关的分享记录
            self.conn.execute(
                "DELETE FROM shares WHERE file_id = ?", (file_id,)
            )
            self.conn.commit()
            return cursor.rowcount > 0

    def get_file_count(self):
        """获取文件总数

        Returns:
            文件数量
        """
        with self._lock:
            cursor = self.conn.execute("SELECT COUNT(*) as count FROM files")
            return cursor.fetchone()["count"]

    def get_total_size(self):
        """获取所有文件的总大小

        Returns:
            总大小（字节）
        """
        with self._lock:
            cursor = self.conn.execute(
                "SELECT COALESCE(SUM(file_size), 0) as total FROM files"
            )
            return cursor.fetchone()["total"]

    def create_share(self, file_id, password="", expires_hours=0,
                     max_downloads=0):
        """创建分享链接

        Args:
            file_id: 文件ID
            password: 保护密码（明文，由security模块处理）
            expires_hours: 过期时间（小时），0表示永不过期
            max_downloads: 最大下载次数，0表示不限制

        Returns:
            分享记录字典
        """
        share_id = str(uuid.uuid4())
        share_code = uuid.uuid4().hex[:8]
        now = datetime.now(timezone.utc).isoformat()

        expires_at = ""
        if expires_hours > 0:
            from datetime import timedelta
            exp_time = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
            expires_at = exp_time.isoformat()

        with self._lock:
            self.conn.execute(
                """INSERT INTO shares
                   (id, file_id, share_code, password, expires_at,
                    max_downloads, download_count, created_at, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, 0, ?, 1)""",
                (share_id, file_id, share_code, password, expires_at,
                 max_downloads, now)
            )
            self.conn.commit()

        return self.get_share(share_id)

    def get_share(self, share_id):
        """根据ID获取分享记录

        Args:
            share_id: 分享ID

        Returns:
            分享记录字典
        """
        with self._lock:
            cursor = self.conn.execute(
                "SELECT * FROM shares WHERE id = ?", (share_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_share_by_code(self, share_code):
        """根据分享码获取分享记录

        Args:
            share_code: 分享码

        Returns:
            分享记录字典
        """
        with self._lock:
            cursor = self.conn.execute(
                "SELECT * FROM shares WHERE share_code = ?", (share_code,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_shares(self, file_id=None, active_only=True):
        """列出分享记录

        Args:
            file_id: 文件ID（可选，用于筛选）
            active_only: 是否只返回活跃的分享

        Returns:
            分享记录列表
        """
        with self._lock:
            if file_id:
                if active_only:
                    query = """
                        SELECT s.*, f.original_name, f.file_size
                        FROM shares s
                        JOIN files f ON s.file_id = f.id
                        WHERE s.file_id = ? AND s.is_active = 1
                        ORDER BY s.created_at DESC
                    """
                else:
                    query = """
                        SELECT s.*, f.original_name, f.file_size
                        FROM shares s
                        JOIN files f ON s.file_id = f.id
                        WHERE s.file_id = ?
                        ORDER BY s.created_at DESC
                    """
                cursor = self.conn.execute(query, (file_id,))
            else:
                if active_only:
                    query = """
                        SELECT s.*, f.original_name, f.file_size
                        FROM shares s
                        JOIN files f ON s.file_id = f.id
                        WHERE s.is_active = 1
                        ORDER BY s.created_at DESC
                    """
                else:
                    query = """
                        SELECT s.*, f.original_name, f.file_size
                        FROM shares s
                        JOIN files f ON s.file_id = f.id
                        ORDER BY s.created_at DESC
                    """
                cursor = self.conn.execute(query)

            return [dict(row) for row in cursor.fetchall()]

    def increment_download(self, share_id, download_ip="", user_agent=""):
        """增加下载计数

        Args:
            share_id: 分享ID
            download_ip: 下载者IP
            user_agent: 用户代理

        Returns:
            是否成功
        """
        share = self.get_share(share_id)
        if not share:
            return False

        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            # 更新下载计数
            self.conn.execute(
                """UPDATE shares
                   SET download_count = download_count + 1,
                       last_download_at = ?
                   WHERE id = ?""",
                (now, share_id)
            )

            # 记录下载日志
            self.conn.execute(
                """INSERT INTO download_logs
                   (share_id, file_id, download_time, download_ip, user_agent)
                   VALUES (?, ?, ?, ?, ?)""",
                (share_id, share["file_id"], now, download_ip, user_agent)
            )

            # 检查是否达到最大下载次数
            if share["max_downloads"] > 0:
                cursor = self.conn.execute(
                    "SELECT download_count FROM shares WHERE id = ?", (share_id,)
                )
                row = cursor.fetchone()
                if row and row["download_count"] >= share["max_downloads"]:
                    self.conn.execute(
                        "UPDATE shares SET is_active = 0 WHERE id = ?",
                        (share_id,)
                    )

            self.conn.commit()
        return True

    def deactivate_share(self, share_id):
        """停用分享链接

        Args:
            share_id: 分享ID

        Returns:
            是否成功
        """
        with self._lock:
            cursor = self.conn.execute(
                "UPDATE shares SET is_active = 0 WHERE id = ?", (share_id,)
            )
            self.conn.commit()
            return cursor.rowcount > 0

    def is_share_valid(self, share_code):
        """检查分享链接是否有效

        Args:
            share_code: 分享码

        Returns:
            (是否有效, 分享记录或错误信息)
        """
        share = self.get_share_by_code(share_code)
        if not share:
            return False, "分享链接不存在"

        if not share["is_active"]:
            return False, "分享链接已失效"

        # 检查过期时间
        if share["expires_at"]:
            try:
                expires = datetime.fromisoformat(
                    share["expires_at"].replace("Z", "+00:00")
                )
                now = datetime.now(timezone.utc)
                if now > expires:
                    # 自动停用过期的分享
                    self.deactivate_share(share["id"])
                    return False, "分享链接已过期"
            except ValueError:
                pass

        # 检查下载次数
        if share["max_downloads"] > 0 and \
           share["download_count"] >= share["max_downloads"]:
            self.deactivate_share(share["id"])
            return False, "已达到最大下载次数"

        return True, share

    def export_shares(self, format_type="json"):
        """导出分享记录

        Args:
            format_type: 导出格式 (json/csv/markdown)

        Returns:
            格式化后的字符串
        """
        shares = self.list_shares(active_only=False)

        if format_type == "json":
            return self._export_json(shares)
        elif format_type == "csv":
            return self._export_csv(shares)
        elif format_type == "markdown":
            return self._export_markdown(shares)
        else:
            return self._export_json(shares)

    def _export_json(self, shares):
        """导出为JSON格式"""
        export_data = []
        for share in shares:
            export_data.append({
                "share_code": share["share_code"],
                "filename": share["original_name"],
                "file_size": share["file_size"],
                "password_protected": bool(share["password"]),
                "expires_at": share["expires_at"] or "永不过期",
                "max_downloads": share["max_downloads"] or "不限制",
                "download_count": share["download_count"],
                "created_at": share["created_at"],
                "last_download_at": share["last_download_at"] or "从未下载",
                "is_active": bool(share["is_active"]),
            })
        return json.dumps(export_data, indent=2, ensure_ascii=False)

    def _export_csv(self, shares):
        """导出为CSV格式"""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        header = [
            "分享码", "文件名", "文件大小", "密码保护", "过期时间",
            "最大下载次数", "已下载次数", "创建时间", "最后下载时间", "状态"
        ]
        writer.writerow(header)

        for share in shares:
            from .utils import format_size
            row = [
                share["share_code"],
                share["original_name"],
                format_size(share["file_size"]),
                "是" if share["password"] else "否",
                share["expires_at"] or "永不过期",
                share["max_downloads"] or "不限制",
                share["download_count"],
                share["created_at"],
                share["last_download_at"] or "从未下载",
                "活跃" if share["is_active"] else "已失效",
            ]
            writer.writerow(row)

        return output.getvalue()

    def _export_markdown(self, shares):
        """导出为Markdown格式"""
        from .utils import format_size, format_datetime

        lines = [
            "# FileDrop 分享记录",
            "",
            f"> 导出时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"> 共 {len(shares)} 条记录",
            "",
            "| 分享码 | 文件名 | 大小 | 密码保护 | 过期时间 | 下载次数 | 状态 |",
            "|--------|--------|------|----------|----------|----------|------|",
        ]

        for share in shares:
            expires = share["expires_at"] or "永不过期"
            password = "是" if share["password"] else "否"
            status = "活跃" if share["is_active"] else "已失效"
            downloads = f"{share['download_count']}"
            if share["max_downloads"] > 0:
                downloads += f"/{share['max_downloads']}"

            lines.append(
                f"| `{share['share_code']}` | {share['original_name']} | "
                f"{format_size(share['file_size'])} | {password} | "
                f"{expires} | {downloads} | {status} |"
            )

        return "\n".join(lines)

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """支持上下文管理器"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文时关闭连接"""
        self.close()
        return False
