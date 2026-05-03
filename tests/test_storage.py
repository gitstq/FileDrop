"""存储模块测试"""

import unittest
import tempfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestStorage(unittest.TestCase):
    """文件存储管理器测试"""

    def setUp(self):
        """创建临时存储目录"""
        self.temp_dir = tempfile.mkdtemp(prefix="filedrop_storage_test_")
        from filedrop.storage import Storage
        self.storage = Storage(self.temp_dir)

    def tearDown(self):
        """清理临时目录"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def test_compute_hash_bytes(self):
        """测试字节数据哈希计算"""
        data = b"Hello, World!"
        hash1 = self.storage.compute_hash(data)
        hash2 = self.storage.compute_hash(data)
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 64)  # SHA256 hex长度

    def test_compute_hash_file(self):
        """测试文件哈希计算"""
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, "wb") as f:
            f.write(b"Hello, File!")

        hash1 = self.storage.compute_hash(test_file)
        hash2 = self.storage.compute_hash(b"Hello, File!")
        self.assertEqual(hash1, hash2)

    def test_store_bytes(self):
        """测试字节数据存储"""
        data = b"Test file content for storage."
        path, hash_val, size = self.storage.store_bytes(data, "test.txt")

        self.assertIsNotNone(path)
        self.assertEqual(len(hash_val), 64)
        self.assertEqual(size, len(data))
        self.assertTrue(os.path.exists(path))

    def test_store_bytes_dedup(self):
        """测试字节数据去重"""
        data = b"Dedup test data " * 50

        path1, hash1, size1 = self.storage.store_bytes(data, "file1.txt")
        path2, hash2, size2 = self.storage.store_bytes(data, "file2.txt")

        self.assertEqual(hash1, hash2)
        self.assertEqual(path1, path2)
        self.assertEqual(size1, size2)

    def test_store_file(self):
        """测试文件存储"""
        test_file = os.path.join(self.temp_dir, "source.txt")
        test_content = b"File storage test content." * 10
        with open(test_file, "wb") as f:
            f.write(test_content)

        path, hash_val, size = self.storage.store_file(test_file, "source.txt")
        self.assertEqual(size, len(test_content))
        self.assertTrue(os.path.exists(path))

    def test_read_file(self):
        """测试文件读取"""
        data = b"Read test content"
        path, hash_val, size = self.storage.store_bytes(data, "read_test.txt")

        read_data = self.storage.read_file(hash_val)
        self.assertEqual(read_data, data)

    def test_read_file_partial(self):
        """测试文件部分读取"""
        data = b"0123456789ABCDEF" * 10
        path, hash_val, size = self.storage.store_bytes(data, "partial_test.txt")

        # 读取前10字节
        partial = self.storage.read_file(hash_val, offset=0, length=10)
        self.assertEqual(partial, b"0123456789")

        # 读取中间部分
        mid = self.storage.read_file(hash_val, offset=5, length=10)
        self.assertEqual(mid, b"56789ABCDE")

    def test_read_file_chunk(self):
        """测试文件分块读取（断点续传）"""
        data = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 10
        path, hash_val, size = self.storage.store_bytes(data, "chunk_test.txt")

        # 读取0-9
        chunk = self.storage.read_file_chunk(hash_val, 0, 9)
        self.assertEqual(len(chunk), 10)
        self.assertEqual(chunk, b"ABCDEFGHIJ")

        # 读取10-19
        chunk2 = self.storage.read_file_chunk(hash_val, 10, 19)
        self.assertEqual(chunk2, b"KLMNOPQRST")

    def test_get_file_size(self):
        """测试获取文件大小"""
        data = b"Size test " * 100
        path, hash_val, size = self.storage.store_bytes(data, "size_test.txt")

        self.assertEqual(self.storage.get_file_size(hash_val), len(data))

    def test_file_exists(self):
        """测试文件存在检查"""
        data = b"Exists test"
        path, hash_val, size = self.storage.store_bytes(data, "exists_test.txt")

        self.assertTrue(self.storage.file_exists(hash_val))
        self.assertFalse(self.storage.file_exists("nonexistent_hash"))

    def test_delete_file(self):
        """测试文件删除"""
        data = b"Delete test"
        path, hash_val, size = self.storage.store_bytes(data, "delete_test.txt")

        self.assertTrue(self.storage.file_exists(hash_val))
        result = self.storage.delete_file(hash_val)
        self.assertTrue(result)
        self.assertFalse(self.storage.file_exists(hash_val))

    def test_delete_nonexistent(self):
        """测试删除不存在的文件"""
        result = self.storage.delete_file("nonexistent_hash")
        self.assertFalse(result)

    def test_get_storage_info(self):
        """测试存储信息"""
        data = b"Info test " * 50
        self.storage.store_bytes(data, "info_test.txt")

        info = self.storage.get_storage_info()
        self.assertEqual(info["file_count"], 1)
        self.assertEqual(info["total_size"], len(data))
        self.assertEqual(info["storage_path"], self.temp_dir)

    def test_store_chunked(self):
        """测试分块存储"""
        total_data = b"Chunked storage test " * 100
        total_size = len(total_data)
        file_hash = self.storage.compute_hash(total_data)

        # 模拟分块上传
        chunk_size = 100
        chunks = []
        for i in range(0, total_size, chunk_size):
            chunks.append((i, total_data[i:i + chunk_size]))

        def chunk_iter():
            for offset, data in chunks:
                yield (offset, data)

        path, computed_hash, size = self.storage.store_chunked(
            chunk_iter(), "chunked_test.txt", total_size
        )

        self.assertEqual(computed_hash, file_hash)
        self.assertEqual(size, total_size)
        self.assertTrue(os.path.exists(path))

        # 验证内容
        read_data = self.storage.read_file(computed_hash)
        self.assertEqual(read_data, total_data)

    def test_store_chunked_with_hash_validation(self):
        """测试分块存储哈希验证"""
        total_data = b"Hash validation test " * 50
        total_size = len(total_data)
        correct_hash = self.storage.compute_hash(total_data)

        def chunk_iter():
            yield (0, total_data)

        # 正确的哈希
        path, hash_val, size = self.storage.store_chunked(
            chunk_iter(), "hash_test.txt", total_size, file_hash=correct_hash
        )
        self.assertEqual(hash_val, correct_hash)

        # 错误的哈希
        def chunk_iter2():
            yield (0, total_data)

        with self.assertRaises(ValueError):
            self.storage.store_chunked(
                chunk_iter2(), "hash_fail_test.txt", total_size,
                file_hash="wrong_hash_value"
            )


if __name__ == "__main__":
    unittest.main()
