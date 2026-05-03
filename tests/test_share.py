"""分享模块测试"""

import unittest
import tempfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestShare(unittest.TestCase):
    """分享管理模块测试"""

    def setUp(self):
        """创建测试环境"""
        self.temp_dir = tempfile.mkdtemp(prefix="filedrop_share_test_")
        db_path = os.path.join(self.temp_dir, "test.db")

        from filedrop.database import Database
        from filedrop.security import PasswordManager
        from filedrop.share import ShareManager

        self.db = Database(db_path)
        self.pwd_manager = PasswordManager()
        self.share_manager = ShareManager(
            self.db, self.pwd_manager, "http://localhost:8080"
        )

        # 添加测试文件
        self.file_id = self.db.add_file(
            filename="test_storage_path",
            original_name="test_file.txt",
            file_hash="abc123" * 10,
            file_size=1024,
            mime_type="text/plain",
        )

    def tearDown(self):
        """清理测试环境"""
        self.db.close()
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def test_create_share(self):
        """测试创建分享链接"""
        share = self.share_manager.create_share(self.file_id)

        self.assertIsNotNone(share)
        self.assertIn("share_code", share)
        self.assertEqual(len(share["share_code"]), 8)
        self.assertTrue(share["is_active"])

    def test_create_share_with_password(self):
        """测试创建带密码的分享链接"""
        share = self.share_manager.create_share(
            self.file_id, password="test123"
        )

        self.assertIsNotNone(share["password"])
        self.assertTrue(len(share["password"]) > 0)

    def test_create_share_with_expires(self):
        """测试创建有过期时间的分享链接"""
        share = self.share_manager.create_share(
            self.file_id, expires_hours=24
        )

        self.assertIsNotNone(share["expires_at"])
        self.assertIn("T", share["expires_at"])

    def test_create_share_with_max_downloads(self):
        """测试创建有下载次数限制的分享链接"""
        share = self.share_manager.create_share(
            self.file_id, max_downloads=5
        )

        self.assertEqual(share["max_downloads"], 5)

    def test_get_share_url(self):
        """测试获取分享URL"""
        share = self.share_manager.create_share(self.file_id)
        url = self.share_manager.get_share_url(share["share_code"])

        self.assertEqual(url, f"http://localhost:8080/s/{share['share_code']}")

    def test_get_share_info(self):
        """测试获取分享信息"""
        share = self.share_manager.create_share(self.file_id)
        info = self.share_manager.get_share_info(share["share_code"])

        self.assertTrue(info["valid"])
        self.assertEqual(info["share_code"], share["share_code"])
        self.assertEqual(info["filename"], "test_file.txt")
        self.assertEqual(info["file_size"], 1024)
        self.assertFalse(info["password_protected"])

    def test_get_share_info_invalid(self):
        """测试获取无效分享信息"""
        info = self.share_manager.get_share_info("nonexistent")
        self.assertFalse(info["valid"])

    def test_verify_share_password(self):
        """测试分享密码验证"""
        share = self.share_manager.create_share(
            self.file_id, password="secret"
        )

        self.assertTrue(
            self.share_manager.verify_share_password(
                share["share_code"], "secret"
            )
        )
        self.assertFalse(
            self.share_manager.verify_share_password(
                share["share_code"], "wrong"
            )
        )

    def test_verify_share_no_password(self):
        """测试无密码分享验证"""
        share = self.share_manager.create_share(self.file_id)

        self.assertTrue(
            self.share_manager.verify_share_password(
                share["share_code"], ""
            )
        )

    def test_validate_share(self):
        """测试分享链接验证"""
        share = self.share_manager.create_share(self.file_id)

        valid, result = self.share_manager.validate_share(share["share_code"])
        self.assertTrue(valid)
        self.assertEqual(result["share_code"], share["share_code"])

    def test_validate_share_invalid_code(self):
        """测试无效分享码验证"""
        valid, result = self.share_manager.validate_share("invalid")
        self.assertFalse(valid)

    def test_deactivate_share(self):
        """测试停用分享链接"""
        share = self.share_manager.create_share(self.file_id)

        result = self.share_manager.deactivate_share(share["share_code"])
        self.assertTrue(result)

        # 验证已停用
        valid, _ = self.share_manager.validate_share(share["share_code"])
        self.assertFalse(valid)

    def test_deactivate_share_invalid(self):
        """测试停用不存在的分享"""
        result = self.share_manager.deactivate_share("nonexistent")
        self.assertFalse(result)

    def test_list_shares(self):
        """测试列出分享记录"""
        self.share_manager.create_share(self.file_id)
        self.share_manager.create_share(self.file_id, password="test")

        shares = self.share_manager.list_shares()
        self.assertEqual(len(shares), 2)

    def test_list_shares_by_file(self):
        """测试按文件列出分享记录"""
        self.share_manager.create_share(self.file_id)

        # 添加另一个文件
        file_id2 = self.db.add_file(
            filename="test2",
            original_name="test2.txt",
            file_hash="def456" * 10,
            file_size=2048,
            mime_type="text/plain",
        )
        self.share_manager.create_share(file_id2)

        shares = self.share_manager.list_shares(file_id=self.file_id)
        self.assertEqual(len(shares), 1)

    def test_export_shares_json(self):
        """测试导出分享记录为JSON"""
        self.share_manager.create_share(self.file_id)

        content = self.share_manager.export_shares("json")
        data = __import__("json").loads(content)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertIn("share_code", data[0])

    def test_export_shares_csv(self):
        """测试导出分享记录为CSV"""
        self.share_manager.create_share(self.file_id)

        content = self.share_manager.export_shares("csv")
        lines = content.strip().split("\n")
        self.assertGreater(len(lines), 1)  # 至少有header和一行数据

    def test_export_shares_markdown(self):
        """测试导出分享记录为Markdown"""
        self.share_manager.create_share(self.file_id)

        content = self.share_manager.export_shares("markdown")
        self.assertIn("# FileDrop", content)
        self.assertIn("|", content)

    def test_format_share_info(self):
        """测试格式化分享信息"""
        share = self.share_manager.create_share(self.file_id)
        info = self.share_manager.format_share_info(share["share_code"])

        self.assertIn("test_file.txt", info)
        self.assertIn("http://localhost:8080/s/", info)

    def test_format_share_info_invalid(self):
        """测试格式化无效分享信息"""
        info = self.share_manager.format_share_info("invalid")
        self.assertIn("无效", info)

    def test_download_count_limit(self):
        """测试下载次数限制"""
        share = self.share_manager.create_share(
            self.file_id, max_downloads=2
        )

        # 模拟下载
        self.db.increment_download(share["id"])
        self.db.increment_download(share["id"])

        # 验证已达到限制
        valid, _ = self.share_manager.validate_share(share["share_code"])
        self.assertFalse(valid)


if __name__ == "__main__":
    unittest.main()
