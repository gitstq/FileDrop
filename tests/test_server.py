"""服务器模块测试"""

import unittest
import threading
import time
import json
import urllib.request
import urllib.parse
import urllib.error
import tempfile
import os
import sys

# 确保可以导入filedrop模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestServerBasic(unittest.TestCase):
    """服务器基础功能测试"""

    @classmethod
    def setUpClass(cls):
        """启动测试服务器"""
        from filedrop.server import FileDropServer

        cls.temp_dir = tempfile.mkdtemp(prefix="filedrop_test_")
        cls.port = 18766  # 使用不常见的端口避免冲突

        cls.server = FileDropServer(
            host="127.0.0.1",
            port=cls.port,
            storage_dir=cls.temp_dir,
            verbose=False,
        )
        cls.server_thread = cls.server.serve_background()
        # 等待服务器启动
        time.sleep(1.0)

    @classmethod
    def tearDownClass(cls):
        """关闭测试服务器"""
        cls.server.stop()
        # 清理临时目录
        import shutil
        try:
            shutil.rmtree(cls.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def _url(self, path):
        """构建测试URL"""
        return f"http://127.0.0.1:{self.port}{path}"

    def _api_request(self, path, method="GET", data=None, content_type=None):
        """发送API请求"""
        url = self._url(path)
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8") if isinstance(data, dict) else data
        req = urllib.request.Request(url, data=body, method=method)
        if content_type:
            req.add_header("Content-Type", content_type)
        elif body:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body_resp = e.read().decode("utf-8")
            try:
                return e.code, json.loads(body_resp)
            except Exception:
                return e.code, {"error": body_resp}

    def _upload_file(self, filename, content, boundary=None):
        """上传文件的辅助方法"""
        if boundary is None:
            boundary = "----TestBoundary" + os.urandom(4).hex()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n"
            f"\r\n"
        ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")

        url = self._url("/api/upload")
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )

        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_server_info(self):
        """测试服务器信息API"""
        status, data = self._api_request("/api/info")
        self.assertEqual(status, 200)
        self.assertIn("version", data)
        self.assertEqual(data["version"], "1.0.0")
        self.assertIn("total_files", data)
        self.assertIsInstance(data["total_files"], int)

    def test_index_page(self):
        """测试首页"""
        url = self._url("/")
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            html_content = resp.read().decode("utf-8")
            self.assertIn("FileDrop", html_content)

    def test_upload_page(self):
        """测试上传页面"""
        url = self._url("/upload")
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            html_content = resp.read().decode("utf-8")
            self.assertIn("上传", html_content)

    def test_file_upload_and_download(self):
        """测试文件上传和下载"""
        test_content = b"Hello, FileDrop! This is a test file."
        filename = "test_upload.txt"

        result = self._upload_file(filename, test_content)

        self.assertTrue(result["success"])
        self.assertEqual(len(result["uploaded"]), 1)
        self.assertIn("id", result["uploaded"][0])
        file_id = result["uploaded"][0]["id"]

        # 验证文件列表
        status, data = self._api_request("/api/files")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(data["total"], 1)

        # 下载文件
        download_url = self._url(f"/api/download/{file_id}")
        req = urllib.request.Request(download_url)
        with urllib.request.urlopen(req) as resp:
            downloaded = resp.read()
        self.assertEqual(downloaded, test_content)

        # 删除文件
        status, data = self._api_request(f"/api/file/{file_id}", method="DELETE")
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])

    def test_file_deduplication(self):
        """测试文件去重"""
        test_content = b"Dedup test content " * 100
        filename = "dedup_test.txt"

        # 第一次上传
        result1 = self._upload_file(filename, test_content)
        self.assertTrue(result1["success"])
        self.assertFalse(result1["uploaded"][0].get("duplicate", False))

        # 第二次上传相同内容（不同文件名）
        filename2 = "dedup_test_copy.txt"
        result2 = self._upload_file(filename2, test_content)
        self.assertTrue(result2["success"])
        # 第二次上传应该是去重的
        self.assertTrue(result2["uploaded"][0].get("duplicate", False))

    def test_share_create_and_download(self):
        """测试分享链接创建和下载"""
        test_content = b"Share test file content."
        filename = "share_test.txt"

        result = self._upload_file(filename, test_content)
        self.assertTrue(result["success"])
        file_id = result["uploaded"][0]["id"]

        # 创建分享链接
        status, data = self._api_request(
            f"/api/share/create/{file_id}",
            method="POST",
            data={"password": "test123", "expires": 24, "max_downloads": 10}
        )
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        share_code = data["share_code"]

        # 通过分享链接下载（无密码应该失败）
        download_url = self._url(f"/api/share/{share_code}")
        req = urllib.request.Request(download_url)
        try:
            with urllib.request.urlopen(req) as resp:
                self.fail("应该返回401错误")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 401)

        # 通过分享链接下载（正确密码）
        download_url = self._url(f"/api/share/{share_code}?password=test123")
        req = urllib.request.Request(download_url)
        with urllib.request.urlopen(req) as resp:
            downloaded = resp.read()
        self.assertEqual(downloaded, test_content)

    def test_404_page(self):
        """测试404页面"""
        url = self._url("/nonexistent_page")
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req) as resp:
                self.fail("应该返回404")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)

    def test_search_files(self):
        """测试文件搜索"""
        status, data = self._api_request("/api/files?search=nonexistent_xyz")
        self.assertEqual(status, 200)
        self.assertIn("files", data)


if __name__ == "__main__":
    unittest.main()
