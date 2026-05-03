"""工具函数模块测试"""

import unittest
import sys
import os
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFormatSize(unittest.TestCase):
    """文件大小格式化测试"""

    def test_bytes(self):
        from filedrop.utils import format_size
        self.assertEqual(format_size(0), "0 B")
        self.assertEqual(format_size(100), "100 B")
        self.assertEqual(format_size(999), "999 B")

    def test_kilobytes(self):
        from filedrop.utils import format_size
        self.assertEqual(format_size(1024), "1.0 KB")
        self.assertEqual(format_size(1536), "1.5 KB")

    def test_megabytes(self):
        from filedrop.utils import format_size
        self.assertEqual(format_size(1024 * 1024), "1.0 MB")
        self.assertEqual(format_size(1024 * 1024 * 2.5), "2.5 MB")

    def test_gigabytes(self):
        from filedrop.utils import format_size
        self.assertEqual(format_size(1024 ** 3), "1.0 GB")

    def test_none(self):
        from filedrop.utils import format_size
        self.assertEqual(format_size(None), "0 B")

    def test_negative(self):
        from filedrop.utils import format_size
        self.assertEqual(format_size(-100), "0 B")


class TestFormatTime(unittest.TestCase):
    """时间格式化测试"""

    def test_seconds(self):
        from filedrop.utils import format_time
        self.assertEqual(format_time(30), "30s")
        self.assertEqual(format_time(0), "0s")

    def test_minutes(self):
        from filedrop.utils import format_time
        self.assertEqual(format_time(90), "1m 30s")
        self.assertEqual(format_time(300), "5m 0s")

    def test_hours(self):
        from filedrop.utils import format_time
        self.assertEqual(format_time(3661), "1h 1m")

    def test_none(self):
        from filedrop.utils import format_time
        self.assertEqual(format_time(None), "0s")


class TestSanitizeFilename(unittest.TestCase):
    """文件名清理测试"""

    def test_normal_filename(self):
        from filedrop.utils import sanitize_filename
        self.assertEqual(sanitize_filename("test.txt"), "test.txt")

    def test_path_traversal(self):
        from filedrop.utils import sanitize_filename
        self.assertEqual(sanitize_filename("../../etc/passwd"), "passwd")
        self.assertEqual(sanitize_filename("..\\windows\\system32"), "system32")

    def test_null_bytes(self):
        from filedrop.utils import sanitize_filename
        self.assertEqual(sanitize_filename("file\x00.txt"), "file.txt")

    def test_empty_filename(self):
        from filedrop.utils import sanitize_filename
        self.assertEqual(sanitize_filename(""), "unnamed")
        self.assertEqual(sanitize_filename("..."), "unnamed")


class TestIsTextFile(unittest.TestCase):
    """文本文件判断测试"""

    def test_text_extensions(self):
        from filedrop.utils import is_text_file
        self.assertTrue(is_text_file("test.txt"))
        self.assertTrue(is_text_file("test.py"))
        self.assertTrue(is_text_file("test.md"))
        self.assertTrue(is_text_file("test.json"))
        self.assertTrue(is_text_file("test.csv"))

    def test_binary_extensions(self):
        from filedrop.utils import is_text_file
        self.assertFalse(is_text_file("test.exe"))
        self.assertFalse(is_text_file("test.png"))
        self.assertFalse(is_text_file("test.pdf"))


class TestIsImageFile(unittest.TestCase):
    """图片文件判断测试"""

    def test_image_extensions(self):
        from filedrop.utils import is_image_file
        self.assertTrue(is_image_file("test.png"))
        self.assertTrue(is_image_file("test.jpg"))
        self.assertTrue(is_image_file("test.jpeg"))
        self.assertTrue(is_image_file("test.gif"))
        self.assertTrue(is_image_file("test.svg"))
        self.assertTrue(is_image_file("test.webp"))

    def test_non_image_extensions(self):
        from filedrop.utils import is_image_file
        self.assertFalse(is_image_file("test.txt"))
        self.assertFalse(is_image_file("test.pdf"))


class TestParseContentRange(unittest.TestCase):
    """Content-Range解析测试"""

    def test_full_range(self):
        from filedrop.utils import parse_content_range
        result = parse_content_range("bytes=0-99", 200)
        self.assertEqual(result, (0, 99, 200))

    def test_open_ended_range(self):
        from filedrop.utils import parse_content_range
        result = parse_content_range("bytes=100-", 500)
        self.assertEqual(result, (100, 499, 500))

    def test_invalid_range(self):
        from filedrop.utils import parse_content_range
        result = parse_content_range("bytes=500-600", 200)
        self.assertIsNone(result)

    def test_empty_range(self):
        from filedrop.utils import parse_content_range
        result = parse_content_range("", 200)
        self.assertIsNone(result)

    def test_malformed_range(self):
        from filedrop.utils import parse_content_range
        result = parse_content_range("invalid", 200)
        self.assertIsNone(result)


class TestProgressBar(unittest.TestCase):
    """进度条测试"""

    def test_progress_creation(self):
        from filedrop.utils import ProgressBar
        pb = ProgressBar(1000, prefix="Test")
        self.assertEqual(pb.total, 1000)
        self.assertEqual(pb.current, 0)

    def test_progress_update(self):
        from filedrop.utils import ProgressBar
        pb = ProgressBar(1000, prefix="Test")
        pb.update(500)
        self.assertEqual(pb.current, 500)

    def test_progress_finish(self):
        from filedrop.utils import ProgressBar
        pb = ProgressBar(1000, prefix="Test")
        pb.finish()
        self.assertEqual(pb.current, 1000)
        self.assertTrue(pb.finished)


class TestSecurityValidator(unittest.TestCase):
    """安全验证器测试"""

    def test_safe_filename(self):
        from filedrop.security import SecurityValidator
        self.assertTrue(SecurityValidator.is_safe_filename("test.txt"))
        self.assertTrue(SecurityValidator.is_safe_filename("my-file_v2.py"))
        self.assertTrue(SecurityValidator.is_safe_filename("data 2024.csv"))

    def test_unsafe_filename(self):
        from filedrop.security import SecurityValidator
        self.assertFalse(SecurityValidator.is_safe_filename(""))
        self.assertFalse(SecurityValidator.is_safe_filename("."))
        self.assertFalse(SecurityValidator.is_safe_filename(".."))
        self.assertFalse(SecurityValidator.is_safe_filename("../test.txt"))
        self.assertFalse(SecurityValidator.is_safe_filename(".hidden"))
        self.assertFalse(SecurityValidator.is_safe_filename("a" * 256))

    def test_dangerous_file(self):
        from filedrop.security import SecurityValidator
        self.assertTrue(SecurityValidator.is_dangerous_file("virus.exe"))
        self.assertTrue(SecurityValidator.is_dangerous_file("script.bat"))
        self.assertTrue(SecurityValidator.is_dangerous_file("payload.ps1"))
        self.assertFalse(SecurityValidator.is_dangerous_file("document.pdf"))
        self.assertFalse(SecurityValidator.is_dangerous_file("image.png"))

    def test_safe_path(self):
        from filedrop.security import SecurityValidator
        self.assertTrue(SecurityValidator.is_safe_path("/tmp/data", "/tmp/data/file.txt"))
        self.assertFalse(SecurityValidator.is_safe_path("/tmp/data", "/etc/passwd"))

    def test_sanitize_input(self):
        from filedrop.security import SecurityValidator
        self.assertEqual(
            SecurityValidator.sanitize_input("<script>alert('xss')</script>"),
            "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
        )
        self.assertEqual(SecurityValidator.sanitize_input("normal text"), "normal text")


class TestPasswordManager(unittest.TestCase):
    """密码管理器测试"""

    def test_hash_and_verify(self):
        from filedrop.security import PasswordManager
        pm = PasswordManager()
        hashed = pm.hash_password("test123")
        self.assertTrue(pm.verify_password("test123", hashed))

    def test_wrong_password(self):
        from filedrop.security import PasswordManager
        pm = PasswordManager()
        hashed = pm.hash_password("correct")
        self.assertFalse(pm.verify_password("wrong", hashed))

    def test_empty_password(self):
        from filedrop.security import PasswordManager
        pm = PasswordManager()
        hashed = pm.hash_password("")
        self.assertTrue(pm.verify_password("", hashed))

    def test_generate_token(self):
        from filedrop.security import PasswordManager
        pm = PasswordManager()
        token = pm.generate_token()
        self.assertEqual(len(token), 64)  # 32 bytes = 64 hex chars

    def test_password_strength(self):
        from filedrop.security import SecurityValidator
        valid, msg = SecurityValidator.validate_password_strength("test")
        self.assertTrue(valid)
        valid, msg = SecurityValidator.validate_password_strength("")
        self.assertFalse(valid)
        valid, msg = SecurityValidator.validate_password_strength("ab")
        self.assertFalse(valid)


class TestRateLimiter(unittest.TestCase):
    """速率限制器测试"""

    def test_allow_within_limit(self):
        from filedrop.security import RateLimiter
        rl = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            allowed, _, _ = rl.is_allowed("test_client")
            self.assertTrue(allowed)

    def test_block_over_limit(self):
        from filedrop.security import RateLimiter
        rl = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            rl.is_allowed("test_client")
        allowed, remaining, _ = rl.is_allowed("test_client")
        self.assertFalse(allowed)
        self.assertEqual(remaining, 0)

    def test_different_clients(self):
        from filedrop.security import RateLimiter
        rl = RateLimiter(max_requests=2, window_seconds=60)
        rl.is_allowed("client_a")
        rl.is_allowed("client_a")
        allowed_a, _, _ = rl.is_allowed("client_a")
        self.assertFalse(allowed_a)

        allowed_b, _, _ = rl.is_allowed("client_b")
        self.assertTrue(allowed_b)

    def test_reset(self):
        from filedrop.security import RateLimiter
        rl = RateLimiter(max_requests=2, window_seconds=60)
        rl.is_allowed("test_client")
        rl.is_allowed("test_client")
        rl.reset("test_client")
        allowed, _, _ = rl.is_allowed("test_client")
        self.assertTrue(allowed)


class TestGetMimeType(unittest.TestCase):
    """MIME类型测试"""

    def test_known_types(self):
        from filedrop.utils import get_mime_type
        self.assertEqual(get_mime_type("test.txt"), "text/plain")
        self.assertEqual(get_mime_type("test.html"), "text/html")
        self.assertEqual(get_mime_type("test.json"), "application/json")
        self.assertEqual(get_mime_type("test.png"), "image/png")
        self.assertEqual(get_mime_type("test.pdf"), "application/pdf")

    def test_unknown_type(self):
        from filedrop.utils import get_mime_type
        self.assertEqual(get_mime_type("test.unknownxyz"), "application/octet-stream")


if __name__ == "__main__":
    unittest.main()
