"""
工具函数模块 - 提供进度条、二维码生成、格式化等通用工具
"""

import sys
import time
import math
import struct
import zlib
import re


def format_size(size_bytes):
    """将字节数格式化为人类可读的字符串

    Args:
        size_bytes: 文件大小（字节）

    Returns:
        格式化后的字符串，如 '1.5 MB'
    """
    if size_bytes is None:
        return "0 B"
    if size_bytes < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    size = float(size_bytes)
    while size >= 1024.0 and index < len(units) - 1:
        size /= 1024.0
        index += 1
    if index == 0:
        return f"{int(size)} {units[index]}"
    return f"{size:.1f} {units[index]}"


def format_time(seconds):
    """将秒数格式化为人类可读的时间字符串

    Args:
        seconds: 时间（秒）

    Returns:
        格式化后的字符串，如 '2h 30m' 或 '45s'
    """
    if seconds is None or seconds < 0:
        return "0s"
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def format_datetime(dt_str):
    """格式化日期时间字符串

    Args:
        dt_str: ISO格式的日期时间字符串

    Returns:
        格式化后的字符串
    """
    if not dt_str:
        return "N/A"
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return dt_str


class ProgressBar:
    """终端进度条，使用 \\r 回车符实现原地更新

    Args:
        total: 总大小（字节）
        prefix: 进度条前缀文字
        width: 进度条宽度（字符数）
    """

    def __init__(self, total, prefix="", width=40):
        self.total = total
        self.prefix = prefix
        self.width = width
        self.current = 0
        self.start_time = time.time()
        self.last_print = 0
        self.finished = False

    def update(self, current):
        """更新进度条

        Args:
            current: 当前进度（字节）
        """
        self.current = current
        now = time.time()
        # 限制刷新频率，至少间隔0.1秒
        if now - self.last_print < 0.1 and current < self.total:
            return
        self.last_print = now
        self._print()

    def finish(self):
        """完成进度条"""
        self.current = self.total
        self.finished = True
        self._print()
        sys.stdout.write("\n")
        sys.stdout.flush()

    def _print(self):
        """打印进度条"""
        if self.total <= 0:
            percent = 100.0
        else:
            percent = min(100.0, (self.current / self.total) * 100)

        filled = int(self.width * percent / 100)
        bar = "█" * filled + "░" * (self.width - filled)

        elapsed = time.time() - self.start_time
        if elapsed > 0 and self.current > 0:
            speed = self.current / elapsed
            remaining = (self.total - self.current) / speed if speed > 0 else 0
            speed_str = format_size(speed) + "/s"
            eta_str = format_time(remaining)
        else:
            speed_str = "--"
            eta_str = "--"

        line = (
            f"\r{self.prefix} |{bar}| {percent:.1f}% "
            f"{format_size(self.current)}/{format_size(self.total)} "
            f"{speed_str} ETA {eta_str}"
        )
        sys.stdout.write(line)
        sys.stdout.flush()


class ASCIIQRCode:
    """纯ASCII Art二维码生成器

    基于简化版的QR编码算法，支持编码URL等短文本。
    使用Reed-Solomon纠错码实现基本的错误恢复。

    注意：这是一个简化实现，仅支持字母数字和字节模式，
    适用于编码较短的URL（<50字符）。
    """

    # QR版本1的纠错级别参数
    # (数据码字数, 纠错码字数, 块数)
    EC_LEVELS = {
        "L": (19, 7, 1),   # 7%纠错
        "M": (16, 10, 1),  # 15%纠错
        "Q": (13, 13, 1),  # 25%纠错
        "H": (9, 17, 1),   # 30%纠错
    }

    # 字母数字模式字符集
    ALPHANUMERIC = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"

    def __init__(self, ec_level="L"):
        """初始化QR码生成器

        Args:
            ec_level: 纠错级别 (L/M/Q/H)
        """
        self.ec_level = ec_level
        self.size = 21  # QR版本1为21x21

    def encode(self, text):
        """将文本编码为二维码矩阵

        Args:
            text: 要编码的文本

        Returns:
            二维布尔矩阵 (True=黑色模块)
        """
        text = str(text)
        # 将文本编码为字节数据
        data = text.encode("utf-8")

        # 获取纠错参数
        ec_params = self.EC_LEVELS[self.ec_level]
        data_codewords = ec_params[0]
        ec_codewords = ec_params[1]

        # 构建数据比特流
        bit_stream = self._build_data_bitstream(data, data_codewords)

        # 添加终止符和填充
        bit_stream = self._add_terminator(bit_stream, data_codewords * 8)

        # 转换为字节
        data_bytes = self._bits_to_bytes(bit_stream, data_codewords)

        # 生成纠错码
        ec_bytes = self._generate_ec(data_bytes, ec_codewords)

        # 组合数据和纠错码
        codewords = data_bytes + ec_bytes

        # 创建QR矩阵
        matrix = self._create_matrix()

        # 放置查找器图案
        self._place_finder_patterns(matrix)

        # 放置定时图案
        self._place_timing_patterns(matrix)

        # 放置数据和纠错码
        self._place_data(matrix, codewords)

        # 应用掩码
        matrix = self._apply_mask(matrix)

        return matrix

    def _build_data_bitstream(self, data, max_codewords):
        """构建数据比特流"""
        bits = []

        # 模式指示符：字节模式 = 0100
        bits.extend([0, 1, 0, 0])

        # 字符计数指示符（版本1字节模式为8位）
        count = len(data)
        for i in range(7, -1, -1):
            bits.append((count >> i) & 1)

        # 数据
        for byte in data:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)

        return bits

    def _add_terminator(self, bits, total_bits):
        """添加终止符和填充比特"""
        # 终止符（最多4个0）
        for _ in range(min(4, total_bits - len(bits))):
            bits.append(0)

        # 对齐到字节边界
        while len(bits) % 8 != 0:
            bits.append(0)

        # 填充码字
        pad_bytes = [0xEC, 0x11]
        pad_idx = 0
        while len(bits) < total_bits:
            pad_byte = pad_bytes[pad_idx % 2]
            for i in range(7, -1, -1):
                bits.append((pad_byte >> i) & 1)
            pad_idx += 1

        return bits[:total_bits]

    def _bits_to_bytes(self, bits, num_bytes):
        """将比特流转换为字节数组"""
        result = []
        for i in range(num_bytes):
            byte = 0
            for j in range(8):
                idx = i * 8 + j
                if idx < len(bits):
                    byte = (byte << 1) | bits[idx]
                else:
                    byte = byte << 1
            result.append(byte)
        return result

    def _generate_ec(self, data, ec_count):
        """生成Reed-Solomon纠错码"""
        # 简化的RS纠错码生成（使用GF(256)多项式除法）
        # 生成多项式
        generator = self._rs_generator_poly(ec_count)

        # 多项式除法
        result = list(data) + [0] * ec_count
        for i in range(len(data)):
            coef = result[i]
            if coef != 0:
                for j in range(len(generator)):
                    result[i + j] ^= generator[j]

        return result[len(data):]

    def _rs_generator_poly(self, degree):
        """生成RS生成多项式"""
        g = [1]
        for i in range(degree):
            g = self._poly_multiply(g, [1, self._gf_exp(i)])
        return g

    def _gf_exp(self, n):
        """GF(256)指数运算 (使用x^8 + x^4 + x^3 + x^2 + 1)"""
        if n == 0:
            return 1
        result = 1
        for _ in range(n):
            result <<= 1
            if result >= 256:
                result ^= 0x11D
        return result

    def _poly_multiply(self, p1, p2):
        """GF(256)多项式乘法"""
        result = [0] * (len(p1) + len(p2) - 1)
        for i in range(len(p1)):
            for j in range(len(p2)):
                result[i + j] ^= self._gf_mul(p1[i], p2[j])
        return result

    def _gf_mul(self, a, b):
        """GF(256)乘法"""
        if a == 0 or b == 0:
            return 0
        result = 0
        while b:
            if b & 1:
                result ^= a
            a <<= 1
            if a >= 256:
                a ^= 0x11D
            b >>= 1
        return result

    def _create_matrix(self):
        """创建空白QR矩阵"""
        return [[None for _ in range(self.size)] for _ in range(self.size)]

    def _place_finder_patterns(self, matrix):
        """放置三个查找器图案"""
        positions = [(0, 0), (0, self.size - 7), (self.size - 7, 0)]
        for row, col in positions:
            for r in range(9):
                for c in range(9):
                    rr, cc = row + r - 1, col + c - 1
                    if 0 <= rr < self.size and 0 <= cc < self.size:
                        if r == 0 or r == 8 or c == 0 or c == 8:
                            matrix[rr][cc] = False  # 分隔符（白色）
                        elif (1 <= r <= 6 and (c == 1 or c == 6)) or \
                             (1 <= c <= 6 and (r == 1 or r == 6)):
                            matrix[rr][cc] = True   # 外框（黑色）
                        elif 2 <= r <= 5 and 2 <= c <= 5:
                            if r == 2 or r == 5 or c == 2 or c == 5:
                                matrix[rr][cc] = True
                            else:
                                matrix[rr][cc] = True   # 内部（黑色）
                        else:
                            matrix[rr][cc] = False

    def _place_timing_patterns(self, matrix):
        """放置定时图案"""
        for i in range(8, self.size - 8):
            matrix[6][i] = bool(i % 2 == 0)
            matrix[i][6] = bool(i % 2 == 0)

    def _place_data(self, matrix, codewords):
        """将数据码字放置到矩阵中"""
        # 将码字转换为比特
        bits = []
        for byte in codewords:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)

        # 从右下角开始，按Z字形放置
        bit_idx = 0
        col = self.size - 1
        upward = True

        while col >= 0:
            if col == 6:
                col -= 1
                continue

            if upward:
                rows = range(self.size - 1, -1, -1)
            else:
                rows = range(self.size)

            for row in rows:
                for c_offset in [0, -1]:
                    c = col + c_offset
                    if c < 0 or c >= self.size:
                        continue
                    if matrix[row][c] is not None:
                        continue
                    if bit_idx < len(bits):
                        matrix[row][c] = bool(bits[bit_idx])
                        bit_idx += 1
                    else:
                        matrix[row][c] = False

            upward = not upward
            col -= 2

    def _apply_mask(self, matrix):
        """应用掩码图案（使用掩码0）"""
        result = [[None for _ in range(self.size)] for _ in range(self.size)]

        for row in range(self.size):
            for col in range(self.size):
                if matrix[row][col] is not None:
                    # 掩码0: (row + col) % 2 == 0
                    if (row + col) % 2 == 0:
                        result[row][col] = not matrix[row][col]
                    else:
                        result[row][col] = matrix[row][col]

        # 添加格式信息
        self._add_format_info(result)

        return result

    def _add_format_info(self, matrix):
        """添加格式信息区域"""
        ec_bits = {"L": 1, "M": 0, "Q": 3, "H": 2}
        ec_val = ec_bits[self.ec_level]

        # 格式信息 = 纠错级别(2位) + 掩码图案(3位) + BCH纠错(10位)
        format_data = (ec_val << 3) | 0  # 掩码0
        # BCH(15,5)编码
        bch = self._bch_encode(format_data)
        format_info = (format_data << 10) | bch
        # XOR掩码
        format_info ^= 0x5412

        # 放置格式信息
        bits = []
        for i in range(14, -1, -1):
            bits.append((format_info >> i) & 1)

        # 水平格式信息（左上角）
        for i, bit in enumerate(bits[:6]):
            matrix[8][i] = bool(bit)
        matrix[8][7] = bool(bits[6])
        matrix[8][8] = bool(bits[7])
        for i, bit in enumerate(bits[8:]):
            matrix[7 - i][8] = bool(bit)

        # 垂直格式信息（左上角和左下角）
        for i, bit in enumerate(bits[:7]):
            matrix[i][8] = bool(bit)
        matrix[7][8] = bool(bits[7])
        matrix[8][8] = bool(bits[8])
        for i, bit in enumerate(bits[9:]):
            matrix[self.size - 1 - i][8] = bool(bit)

    def _bch_encode(self, data):
        """BCH(15,5)编码"""
        generator = 0x537  # x^10 + x^8 + x^5 + x^4 + x^2 + x + 1
        result = data << 10
        for i in range(4, -1, -1):
            if result & (1 << (i + 10)):
                result ^= generator << i
        return result

    def to_ascii(self, text, scale=1):
        """将文本编码为ASCII Art二维码字符串

        Args:
            text: 要编码的文本
            scale: 缩放比例（每个模块的字符数）

        Returns:
            ASCII Art二维码字符串
        """
        matrix = self.encode(text)

        # 添加静区（4个模块的白色边框）
        quiet = 2
        full_size = self.size + quiet * 2
        full_matrix = [[False] * full_size for _ in range(full_size)]
        for r in range(self.size):
            for c in range(self.size):
                full_matrix[r + quiet][c + quiet] = matrix[r][c]

        # 转换为ASCII
        lines = []
        for r in range(full_size):
            line = ""
            for c in range(full_size):
                if full_matrix[r][c]:
                    line += "██" * scale
                else:
                    line += "  " * scale
            lines.append(line)

        return "\n".join(lines)

    def to_terminal(self, text, scale=1):
        """生成适合终端显示的二维码

        Args:
            text: 要编码的文本
            scale: 缩放比例

        Returns:
            终端友好的二维码字符串
        """
        matrix = self.encode(text)

        quiet = 1
        full_size = self.size + quiet * 2
        full_matrix = [[False] * full_size for _ in range(full_size)]
        for r in range(self.size):
            for c in range(self.size):
                full_matrix[r + quiet][c + quiet] = matrix[r][c]

        lines = []
        # 使用半块字符实现更高分辨率
        for r in range(0, full_size, 2):
            line = ""
            for c in range(full_size):
                top = full_matrix[r][c] if r < full_size else False
                bottom = full_matrix[r + 1][c] if r + 1 < full_size else False
                if top and bottom:
                    line += "█"
                elif top:
                    line += "▀"
                elif bottom:
                    line += "▄"
                else:
                    line += " "
            lines.append(line)

        return "\n".join(lines)


def generate_qr_code(text, ec_level="L"):
    """生成ASCII二维码的便捷函数

    Args:
        text: 要编码的文本
        ec_level: 纠错级别

    Returns:
        ASCII二维码字符串
    """
    qr = ASCIIQRCode(ec_level=ec_level)
    return qr.to_terminal(text)


def parse_content_range(range_header, file_size):
    """解析HTTP Content-Range头

    Args:
        range_header: Range请求头值
        file_size: 文件总大小

    Returns:
        (start, end, total) 元组，解析失败返回None
    """
    if not range_header:
        return None

    match = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not match:
        return None

    start = int(match.group(1))
    end_str = match.group(2)

    if end_str:
        end = int(end_str)
    else:
        end = file_size - 1

    if start >= file_size:
        return None

    end = min(end, file_size - 1)

    return (start, end, file_size)


def sanitize_filename(filename):
    """清理文件名，移除危险字符

    Args:
        filename: 原始文件名

    Returns:
        安全的文件名
    """
    # 移除路径分隔符和特殊字符
    filename = filename.replace("\\", "/").split("/")[-1]
    filename = filename.replace("\x00", "")
    # 移除 .. 防止路径遍历
    filename = filename.replace("..", "")
    # 只保留文件名部分
    filename = filename.strip(". ")
    if not filename:
        filename = "unnamed"
    return filename


def get_mime_type(filename):
    """获取文件的MIME类型

    Args:
        filename: 文件名

    Returns:
        MIME类型字符串
    """
    import mimetypes
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type is None:
        mime_type = "application/octet-stream"
    return mime_type


def is_text_file(filename, content=None):
    """判断文件是否为文本文件

    Args:
        filename: 文件名
        content: 文件内容（可选）

    Returns:
        是否为文本文件
    """
    text_extensions = {
        ".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm", ".css",
        ".js", ".ts", ".py", ".java", ".c", ".cpp", ".h", ".hpp", ".go",
        ".rs", ".rb", ".php", ".sh", ".bash", ".zsh", ".fish", ".ps1",
        ".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf", ".log",
        ".sql", ".r", ".swift", ".kt", ".scala", ".lua", ".pl", ".ex",
        ".exs", ".erl", ".hrl", ".clj", ".cljs", ".hs", ".ml", ".mli",
        ".vim", ".el", ".lisp", ".scm", ".tcl", ".mak", ".cmake",
        ".gradle", ".properties", ".bat", ".cmd",
    }
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in text_extensions


def is_image_file(filename):
    """判断文件是否为图片文件

    Args:
        filename: 文件名

    Returns:
        是否为图片文件
    """
    image_extensions = {
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp",
        ".ico", ".tiff", ".tif",
    }
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in image_extensions
