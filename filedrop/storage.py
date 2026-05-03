"""
文件存储管理模块 - 处理文件去重、组织和存储
"""

import os
import hashlib
import shutil
import re
from datetime import datetime, timezone


class Storage:
    """文件存储管理器

    基于SHA256哈希实现文件去重，使用两级目录结构组织文件。

    Args:
        base_dir: 存储根目录
    """

    def __init__(self, base_dir):
        """初始化存储管理器

        Args:
            base_dir: 存储根目录路径
        """
        self.base_dir = os.path.abspath(base_dir)
        self.files_dir = os.path.join(self.base_dir, "files")
        self.temp_dir = os.path.join(self.base_dir, "temp")
        self._ensure_dirs()

    def _ensure_dirs(self):
        """确保必要的目录存在"""
        os.makedirs(self.files_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)

    @staticmethod
    def compute_hash(file_path_or_data, chunk_size=8192):
        """计算文件的SHA256哈希值

        Args:
            file_path_or_data: 文件路径或字节数据
            chunk_size: 分块读取大小

        Returns:
            SHA256哈希值的十六进制字符串
        """
        sha256 = hashlib.sha256()

        if isinstance(file_path_or_data, (bytes, bytearray)):
            sha256.update(file_path_or_data)
        elif isinstance(file_path_or_data, str):
            with open(file_path_or_data, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    sha256.update(chunk)
        else:
            raise TypeError("参数必须是文件路径字符串或字节数据")

        return sha256.hexdigest()

    def _get_storage_path(self, file_hash, filename):
        """根据哈希值计算存储路径

        使用两级目录结构：files/ab/cdef...hash/filename
        避免单个目录下文件过多。

        Args:
            file_hash: 文件哈希值
            filename: 文件名

        Returns:
            存储路径
        """
        prefix = file_hash[:2]
        subdir = os.path.join(self.files_dir, prefix)
        os.makedirs(subdir, exist_ok=True)
        return os.path.join(subdir, file_hash)

    def store_file(self, file_path, original_name, progress_callback=None):
        """存储文件（带去重检测）

        Args:
            file_path: 源文件路径
            original_name: 原始文件名
            progress_callback: 进度回调函数 callback(bytes_read, total_size)

        Returns:
            (存储路径, 文件哈希, 文件大小) 元组
        """
        file_size = os.path.getsize(file_path)
        file_hash = self.compute_hash(file_path)

        storage_path = self._get_storage_path(file_hash, original_name)

        # 去重检查：如果文件已存在，直接返回
        if os.path.exists(storage_path):
            if progress_callback:
                progress_callback(file_size, file_size)
            return storage_path, file_hash, file_size

        # 复制文件到存储目录
        self._copy_file(file_path, storage_path, progress_callback)

        return storage_path, file_hash, file_size

    def store_bytes(self, data, original_name, progress_callback=None):
        """存储字节数据（带去重检测）

        Args:
            data: 字节数据
            original_name: 原始文件名
            progress_callback: 进度回调函数

        Returns:
            (存储路径, 文件哈希, 文件大小) 元组
        """
        file_hash = self.compute_hash(data)
        file_size = len(data)

        storage_path = self._get_storage_path(file_hash, original_name)

        if os.path.exists(storage_path):
            if progress_callback:
                progress_callback(file_size, file_size)
            return storage_path, file_hash, file_size

        with open(storage_path, "wb") as f:
            f.write(data)

        if progress_callback:
            progress_callback(file_size, file_size)

        return storage_path, file_hash, file_size

    def store_chunked(self, chunk_iterator, original_name, total_size,
                      file_hash=None, progress_callback=None):
        """分块存储文件（支持断点续传）

        Args:
            chunk_iterator: 数据块迭代器，每项为 (offset, data) 元组
            original_name: 原始文件名
            total_size: 文件总大小
            file_hash: 预期的文件哈希（可选）
            progress_callback: 进度回调函数

        Returns:
            (存储路径, 文件哈希, 文件大小) 元组
        """
        temp_path = os.path.join(self.temp_dir, f"upload_{id(original_name)}")

        # 写入临时文件
        sha256 = hashlib.sha256()
        written = 0

        with open(temp_path, "wb") as f:
            for offset, chunk_data in chunk_iterator:
                # 确保写入位置正确
                f.seek(offset)
                f.write(chunk_data)
                sha256.update(chunk_data)
                written = max(written, offset + len(chunk_data))

                if progress_callback:
                    progress_callback(written, total_size)

        # 截断到正确大小
        with open(temp_path, "r+b") as f:
            f.truncate(total_size)

        # 验证哈希
        computed_hash = sha256.hexdigest()
        if file_hash and computed_hash != file_hash:
            os.remove(temp_path)
            raise ValueError(
                f"文件哈希不匹配: 期望 {file_hash}, 实际 {computed_hash}"
            )

        # 移动到最终位置
        storage_path = self._get_storage_path(computed_hash, original_name)

        if os.path.exists(storage_path):
            os.remove(temp_path)
        else:
            # 确保目标目录存在
            os.makedirs(os.path.dirname(storage_path), exist_ok=True)
            shutil.move(temp_path, storage_path)

        return storage_path, computed_hash, total_size

    def _copy_file(self, src, dst, progress_callback=None):
        """复制文件并支持进度回调

        Args:
            src: 源文件路径
            dst: 目标文件路径
            progress_callback: 进度回调函数
        """
        file_size = os.path.getsize(src)
        copied = 0
        chunk_size = 8192

        with open(src, "rb") as f_src, open(dst, "wb") as f_dst:
            while True:
                chunk = f_src.read(chunk_size)
                if not chunk:
                    break
                f_dst.write(chunk)
                copied += len(chunk)
                if progress_callback:
                    progress_callback(copied, file_size)

    def get_file_path(self, file_hash):
        """根据哈希值获取文件存储路径

        Args:
            file_hash: 文件哈希值

        Returns:
            文件路径，不存在返回None
        """
        storage_path = self._get_storage_path(file_hash, "")
        if os.path.exists(storage_path):
            return storage_path
        return None

    def read_file(self, file_hash, offset=0, length=-1):
        """读取文件内容

        Args:
            file_hash: 文件哈希值
            offset: 起始偏移量
            length: 读取长度，-1表示读取到文件末尾

        Returns:
            文件字节数据，文件不存在返回None
        """
        storage_path = self.get_file_path(file_hash)
        if not storage_path:
            return None

        with open(storage_path, "rb") as f:
            f.seek(offset)
            if length < 0:
                return f.read()
            return f.read(length)

    def read_file_chunk(self, file_hash, start, end):
        """读取文件片段（支持断点续传下载）

        Args:
            file_hash: 文件哈希值
            start: 起始字节位置
            end: 结束字节位置（包含）

        Returns:
            文件片段字节数据，文件不存在返回None
        """
        storage_path = self.get_file_path(file_hash)
        if not storage_path:
            return None

        file_size = os.path.getsize(storage_path)
        end = min(end, file_size - 1)

        with open(storage_path, "rb") as f:
            f.seek(start)
            return f.read(end - start + 1)

    def get_file_size(self, file_hash):
        """获取文件大小

        Args:
            file_hash: 文件哈希值

        Returns:
            文件大小（字节），不存在返回0
        """
        storage_path = self.get_file_path(file_hash)
        if not storage_path:
            return 0
        return os.path.getsize(storage_path)

    def delete_file(self, file_hash):
        """删除存储的文件

        Args:
            file_hash: 文件哈希值

        Returns:
            是否删除成功
        """
        storage_path = self.get_file_path(file_hash)
        if not storage_path:
            return False

        try:
            os.remove(storage_path)
            # 尝试删除空目录
            parent_dir = os.path.dirname(storage_path)
            try:
                os.rmdir(parent_dir)
            except OSError:
                pass  # 目录不为空，忽略
            return True
        except OSError:
            return False

    def file_exists(self, file_hash):
        """检查文件是否存在

        Args:
            file_hash: 文件哈希值

        Returns:
            文件是否存在
        """
        return self.get_file_path(file_hash) is not None

    def get_storage_info(self):
        """获取存储信息

        Returns:
            包含存储统计信息的字典
        """
        total_size = 0
        file_count = 0

        for root, dirs, files in os.walk(self.files_dir):
            for filename in files:
                filepath = os.path.join(root, filename)
                try:
                    total_size += os.path.getsize(filepath)
                    file_count += 1
                except OSError:
                    pass

        return {
            "total_size": total_size,
            "file_count": file_count,
            "storage_path": self.base_dir,
        }

    def cleanup_temp(self):
        """清理临时文件目录"""
        if os.path.exists(self.temp_dir):
            for filename in os.listdir(self.temp_dir):
                filepath = os.path.join(self.temp_dir, filename)
                try:
                    # 删除超过1小时的临时文件
                    if os.path.isfile(filepath):
                        mtime = os.path.getmtime(filepath)
                        age = datetime.now(timezone.utc).timestamp() - mtime
                        if age > 3600:
                            os.remove(filepath)
                except OSError:
                    pass
