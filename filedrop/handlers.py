"""
HTTP请求处理器模块 - 处理上传/下载/列表/删除/预览请求
"""

import os
import io
import json
import re
import html
import urllib.parse
import tempfile
import mimetypes
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone


class MultipartParser:
    """multipart/form-data 解析器

    纯Python实现，不依赖第三方库。
    支持文件上传和表单字段解析。

    Args:
        content_type: Content-Type头
        body: 请求体字节数据
    """

    def __init__(self, content_type, body):
        """初始化解析器

        Args:
            content_type: Content-Type头值
            body: 请求体字节数据
        """
        self.content_type = content_type
        self.body = body
        self.boundary = self._extract_boundary(content_type)
        self.fields = {}
        self.files = []

    def _extract_boundary(self, content_type):
        """从Content-Type中提取boundary

        Args:
            content_type: Content-Type头值

        Returns:
            boundary字符串
        """
        match = re.search(r'boundary=([^\s;]+)', content_type)
        if match:
            boundary = match.group(1)
            # 去除可能的引号
            boundary = boundary.strip('"')
            return boundary.encode("utf-8") if isinstance(boundary, str) else boundary
        raise ValueError("无法从Content-Type中提取boundary")

    def parse(self):
        """解析multipart数据

        Returns:
            (fields, files) 元组
            fields: {name: value} 字典
            files: [{'name': ..., 'filename': ..., 'content_type': ..., 'data': ...}] 列表
        """
        if not self.boundary:
            return self.fields, self.files

        boundary = b"--" + self.boundary
        delimiter = boundary + b"\r\n"
        end_delimiter = boundary + b"--"

        # 分割各个part
        parts = self.body.split(delimiter)

        # 第一个part是空的（boundary之前的内容），跳过
        for part in parts[1:]:
            # 检查是否是结束标记
            if part.startswith(end_delimiter) or part.strip() == end_delimiter:
                break

            # 分离header和body
            if b"\r\n\r\n" in part:
                header_data, part_body = part.split(b"\r\n\r\n", 1)
            else:
                continue

            # 去除末尾的结束边界标记（如果有）
            # 最后一个part可能包含 \r\n--boundary--
            end_marker = b"\r\n" + end_delimiter
            if part_body.endswith(end_marker):
                part_body = part_body[:-len(end_marker)]
            elif end_delimiter in part_body:
                # 如果结束标记在中间（不应该发生），截断到标记前
                idx = part_body.find(end_delimiter)
                part_body = part_body[:idx]

            # 去除末尾的\r\n
            if part_body.endswith(b"\r\n"):
                part_body = part_body[:-2]

            # 解析header
            headers = self._parse_headers(header_data)

            # 获取Content-Disposition
            disposition = headers.get("content-disposition", "")

            # 提取name
            name_match = re.search(r'name="([^"]*)"', disposition)
            name = name_match.group(1) if name_match else ""

            # 检查是否是文件
            filename_match = re.search(r'filename="([^"]*)"', disposition)
            if filename_match:
                filename = filename_match.group(1)
                content_type = headers.get("content-type", "application/octet-stream")

                self.files.append({
                    "name": name,
                    "filename": filename,
                    "content_type": content_type,
                    "data": part_body,
                })
            else:
                # 普通表单字段
                try:
                    value = part_body.decode("utf-8")
                except UnicodeDecodeError:
                    value = part_body.decode("latin-1")
                self.fields[name] = value

        return self.fields, self.files

    def _parse_headers(self, header_data):
        """解析part的header

        Args:
            header_data: header字节数据

        Returns:
            header字典（键名小写）
        """
        headers = {}
        for line in header_data.decode("utf-8", errors="replace").split("\r\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        return headers


class FileDropHandler(BaseHTTPRequestHandler):
    """FileDrop HTTP请求处理器

    处理所有HTTP请求，包括文件上传、下载、列表、删除和预览。

    类属性:
        server_state: 服务器状态对象，包含database, storage, share_manager等
    """

    server_state = None

    def log_message(self, format, *args):
        """自定义日志格式"""
        if self.server_state and hasattr(self.server_state, "verbose"):
            if self.server_state.verbose:
                timestamp = datetime.now(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                client = self.client_address[0] if self.client_address else "?"
                message = format % args
                print(f"[{timestamp}] {client} - {message}")

    def _send_json_response(self, data, status_code=200):
        """发送JSON响应

        Args:
            data: 要发送的数据（字典或列表）
            status_code: HTTP状态码
        """
        response_body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def _send_html_response(self, html_content, status_code=200):
        """发送HTML响应

        Args:
            html_content: HTML内容
            status_code: HTTP状态码
        """
        response_body = html_content.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def _send_error_page(self, status_code, message=""):
        """发送错误页面

        Args:
            status_code: HTTP状态码
            message: 错误消息
        """
        status_messages = {
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
            413: "Payload Too Large",
            429: "Too Many Requests",
            500: "Internal Server Error",
        }

        title = status_messages.get(status_code, "Error")
        if not message:
            message = title

        error_html = self._render_template("error.html", {
            "title": f"{status_code} - {title}",
            "status_code": status_code,
            "message": html.escape(message),
        })
        self._send_html_response(error_html, status_code)

    def _check_auth(self):
        """检查认证

        Returns:
            是否通过认证
        """
        state = self.server_state
        if not state or not state.get("password"):
            return True

        # 检查Authorization头
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if state["password_manager"].verify_password(token, state["password_hash"]):
                return True

        # 检查Cookie
        cookie_header = self.headers.get("Cookie", "")
        if "filedrop_auth=" in cookie_header:
            for part in cookie_header.split(";"):
                part = part.strip()
                if part.startswith("filedrop_auth="):
                    token = part[len("filedrop_auth="):]
                    token = urllib.parse.unquote(token)
                    if state["password_manager"].verify_password(
                        token, state["password_hash"]
                    ):
                        return True

        return False

    def _check_rate_limit(self):
        """检查速率限制

        Returns:
            是否被允许
        """
        state = self.server_state
        if not state or not state.get("rate_limiter"):
            return True

        client_ip = self.client_address[0] if self.client_address else "unknown"
        allowed, remaining, reset_time = state["rate_limiter"].is_allowed(client_ip)

        if not allowed:
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Retry-After", str(reset_time))
            self.send_header("X-RateLimit-Remaining", "0")
            self.end_headers()
            error_msg = json.dumps({
                "error": "请求过于频繁，请稍后再试",
                "retry_after": reset_time
            }).encode("utf-8")
            self.wfile.write(error_msg)
            return False

        return True

    def _render_template(self, template_name, context=None):
        """渲染HTML模板

        Args:
            template_name: 模板文件名
            context: 模板上下文变量

        Returns:
            渲染后的HTML字符串
        """
        if context is None:
            context = {}

        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        template_path = os.path.join(template_dir, template_name)

        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template_content = f.read()
        except FileNotFoundError:
            return f"<html><body><h1>Template not found: {template_name}</h1></body></html>"

        # 简单的模板变量替换 {{variable}}
        for key, value in context.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            elif not isinstance(value, str):
                value = str(value)
            template_content = template_content.replace(
                f"{{{{{key}}}}}", html.escape(value)
            )

        return template_content

    def do_GET(self):
        """处理GET请求"""
        if not self._check_rate_limit():
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        state = self.server_state
        if not state:
            self._send_error_page(500, "服务器未初始化")
            return

        # 路由分发
        if path == "/" or path == "/index.html":
            self._handle_index(query)
        elif path == "/upload":
            self._handle_upload_page()
        elif path == "/api/files":
            self._handle_list_files(query)
        elif path == "/api/info":
            self._handle_server_info()
        elif path.startswith("/api/download/"):
            file_id = path[len("/api/download/"):]
            self._handle_download(file_id, query)
        elif path.startswith("/api/file/"):
            file_id = path[len("/api/file/"):]
            self._handle_get_file(file_id)
        elif path.startswith("/api/preview/"):
            file_id = path[len("/api/preview/"):]
            self._handle_preview(file_id)
        elif path.startswith("/api/delete/"):
            file_id = path[len("/api/delete/"):]
            self._handle_delete_file(file_id)
        elif path.startswith("/s/"):
            share_code = path[len("/s/"):]
            self._handle_share_page(share_code)
        elif path.startswith("/api/share/"):
            share_code = path[len("/api/share/"):]
            self._handle_share_download(share_code, query)
        elif path == "/api/shares":
            self._handle_list_shares(query)
        elif path == "/api/export":
            self._handle_export(query)
        else:
            self._send_error_page(404, "页面不存在")

    def do_POST(self):
        """处理POST请求"""
        if not self._check_rate_limit():
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        state = self.server_state
        if not state:
            self._send_error_page(500, "服务器未初始化")
            return

        if path == "/api/upload":
            self._handle_upload()
        elif path == "/api/upload/chunk":
            self._handle_chunk_upload()
        elif path.startswith("/api/share/create/"):
            file_id = path[len("/api/share/create/"):]
            self._handle_create_share(file_id)
        elif path.startswith("/api/share/deactivate/"):
            share_code = path[len("/api/share/deactivate/"):]
            self._handle_deactivate_share(share_code)
        elif path == "/api/auth":
            self._handle_auth()
        else:
            self._send_error_page(404, "接口不存在")

    def do_DELETE(self):
        """处理DELETE请求"""
        if not self._check_rate_limit():
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/file/"):
            file_id = path[len("/api/file/"):]
            self._handle_delete_file(file_id)
        elif path.startswith("/api/share/"):
            share_code = path[len("/api/share/"):]
            self._handle_deactivate_share(share_code)
        else:
            self._send_error_page(404)

    # ---- 页面处理器 ----

    def _handle_index(self, query):
        """处理首页"""
        search = query.get("search", [""])[0]
        sort = query.get("sort", ["upload_time"])[0]
        order = query.get("order", ["desc"])[0]

        state = self.server_state
        files = state["database"].list_files(
            search=search or None,
            sort_by=sort,
            sort_order=order
        )

        file_list = []
        for f in files:
            file_list.append({
                "id": f["id"],
                "name": html.escape(f["original_name"]),
                "size": f["file_size"],
                "size_formatted": self._format_size(f["file_size"]),
                "type": f["mime_type"],
                "upload_time": f["upload_time"],
                "hash": f["file_hash"][:16],
            })

        page_html = self._render_template("index.html", {
            "title": "FileDrop - 文件共享",
            "files_json": json.dumps(file_list, ensure_ascii=False),
            "total_files": state["database"].get_file_count(),
            "total_size": self._format_size(state["database"].get_total_size()),
            "search": html.escape(search),
            "version": "1.0.0",
        })
        self._send_html_response(page_html)

    def _handle_upload_page(self):
        """处理上传页面"""
        state = self.server_state
        max_size = state.get("max_size", 0)
        max_size_str = self._format_size(max_size) if max_size > 0 else "无限制"

        page_html = self._render_template("upload.html", {
            "title": "FileDrop - 上传文件",
            "max_size": max_size_str,
            "max_size_bytes": str(max_size),
            "version": "1.0.0",
        })
        self._send_html_response(page_html)

    def _handle_share_page(self, share_code):
        """处理分享页面"""
        state = self.server_state
        share_manager = state["share_manager"]

        info = share_manager.get_share_info(share_code)

        if not info["valid"]:
            self._send_error_page(404, info.get("error", "分享链接无效"))
            return

        share_page_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FileDrop - 文件分享</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        .share-card {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.1);
            padding: 40px;
            max-width: 480px;
            width: 100%;
            text-align: center;
        }}
        .share-card h1 {{
            color: #333;
            margin-bottom: 8px;
            font-size: 24px;
        }}
        .file-info {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            text-align: left;
        }}
        .file-name {{
            font-size: 16px;
            font-weight: 600;
            color: #333;
            word-break: break-all;
            margin-bottom: 8px;
        }}
        .file-meta {{
            color: #666;
            font-size: 14px;
        }}
        .password-section {{
            margin: 20px 0;
            display: none;
        }}
        .password-section input {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 12px;
        }}
        .password-section input:focus {{
            outline: none;
            border-color: #4a90d9;
        }}
        .btn {{
            display: inline-block;
            padding: 12px 32px;
            background: #4a90d9;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
            text-decoration: none;
            transition: background 0.2s;
        }}
        .btn:hover {{ background: #357abd; }}
        .btn:disabled {{ background: #ccc; cursor: not-allowed; }}
        .error-msg {{
            color: #e74c3c;
            font-size: 14px;
            margin-top: 8px;
            display: none;
        }}
    </style>
</head>
<body>
    <div class="share-card">
        <h1>文件分享</h1>
        <div class="file-info">
            <div class="file-name">{html.escape(info['filename'])}</div>
            <div class="file-meta">
                大小: {self._format_size(info['file_size'])}
                {'&nbsp;|&nbsp;密码保护' if info['password_protected'] else ''}
            </div>
        </div>
        <div class="password-section" id="passwordSection">
            <input type="password" id="sharePassword" placeholder="请输入提取密码">
            <div class="error-msg" id="passwordError">密码错误</div>
        </div>
        <button class="btn" id="downloadBtn" onclick="downloadFile()">
            下载文件
        </button>
    </div>
    <script>
        const shareCode = "{html.escape(share_code)}";
        const hasPassword = {str(info['password_protected']).lower()};

        if (hasPassword) {{
            document.getElementById('passwordSection').style.display = 'block';
        }}

        async function downloadFile() {{
            const btn = document.getElementById('downloadBtn');
            const errorEl = document.getElementById('passwordError');
            let password = '';

            if (hasPassword) {{
                password = document.getElementById('sharePassword').value;
                if (!password) {{
                    errorEl.textContent = '请输入密码';
                    errorEl.style.display = 'block';
                    return;
                }}
            }}

            btn.disabled = true;
            btn.textContent = '正在下载...';
            errorEl.style.display = 'none';

            try {{
                let url = '/api/share/' + shareCode;
                const params = new URLSearchParams();
                if (password) params.append('password', password);

                const resp = await fetch(url + '?' + params.toString());
                if (!resp.ok) {{
                    const data = await resp.json();
                    throw new Error(data.error || '下载失败');
                }}

                const blob = await resp.blob();
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = '{html.escape(info["filename"])}';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(a.href);
                btn.textContent = '下载完成';
            }} catch (e) {{
                errorEl.textContent = e.message;
                errorEl.style.display = 'block';
                btn.disabled = false;
                btn.textContent = '下载文件';
            }}
        }}
    </script>
</body>
</html>"""
        self._send_html_response(share_page_html)

    # ---- API处理器 ----

    def _handle_upload(self):
        """处理文件上传"""
        state = self.server_state

        # 检查Content-Type
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_json_response({"error": "不支持的Content-Type"}, 400)
            return

        # 检查文件大小限制
        content_length = int(self.headers.get("Content-Length", 0))
        max_size = state.get("max_size", 0)
        if max_size > 0 and content_length > max_size:
            self._send_json_response(
                {"error": f"文件大小超过限制 ({self._format_size(max_size)})"},
                413
            )
            return

        # 读取请求体
        body = self._read_request_body(content_length)
        if body is None:
            self._send_json_response({"error": "请求体读取失败"}, 400)
            return

        # 解析multipart数据
        try:
            parser = MultipartParser(content_type, body)
            fields, files = parser.parse()
        except ValueError as e:
            self._send_json_response({"error": str(e)}, 400)
            return

        if not files:
            self._send_json_response({"error": "未找到上传文件"}, 400)
            return

        # 处理每个文件
        uploaded = []
        for file_info in files:
            filename = file_info["filename"]
            if not filename:
                filename = "unnamed"

            # 安全检查
            from .security import SecurityValidator
            if not SecurityValidator.is_safe_filename(filename):
                filename = "unnamed_file"

            try:
                # 存储文件
                storage_path, file_hash, file_size = state["storage"].store_bytes(
                    file_info["data"], filename
                )

                # 获取MIME类型
                mime_type = file_info.get("content_type", "application/octet-stream")
                if not mime_type or mime_type == "application/octet-stream":
                    import mimetypes as mt
                    mime_type, _ = mt.guess_type(filename)
                    if not mime_type:
                        mime_type = "application/octet-stream"

                # 检查是否已存在相同哈希的文件记录
                existing = state["database"].get_file_by_hash(file_hash)
                if existing:
                    uploaded.append({
                        "id": existing["id"],
                        "filename": existing["original_name"],
                        "size": existing["file_size"],
                        "hash": file_hash,
                        "duplicate": True,
                    })
                else:
                    # 添加文件记录
                    file_id = state["database"].add_file(
                        filename=storage_path,
                        original_name=filename,
                        file_hash=file_hash,
                        file_size=file_size,
                        mime_type=mime_type,
                        upload_ip=self.client_address[0] if self.client_address else "",
                    )
                    uploaded.append({
                        "id": file_id,
                        "filename": filename,
                        "size": file_size,
                        "hash": file_hash,
                        "duplicate": False,
                    })
            except Exception as e:
                uploaded.append({
                    "filename": filename,
                    "error": str(e),
                })

        self._send_json_response({
            "success": True,
            "uploaded": uploaded,
            "count": len(uploaded),
        })

    def _handle_chunk_upload(self):
        """处理分块上传（断点续传）"""
        state = self.server_state

        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", 0))

        # 读取请求体
        body = self._read_request_body(content_length)
        if body is None:
            self._send_json_response({"error": "请求体读取失败"}, 400)
            return

        # 解析multipart数据
        try:
            parser = MultipartParser(content_type, body)
            fields, files = parser.parse()
        except ValueError as e:
            self._send_json_response({"error": str(e)}, 400)
            return

        if not files:
            self._send_json_response({"error": "未找到上传数据"}, 400)
            return

        file_info = files[0]
        chunk_offset = int(fields.get("offset", "0"))
        total_size = int(fields.get("total", "0"))
        file_hash = fields.get("hash", "")
        filename = fields.get("filename", file_info.get("filename", "unnamed"))

        # 存储分块
        def chunk_iter():
            yield (chunk_offset, file_info["data"])

        try:
            storage_path, computed_hash, file_size = state["storage"].store_chunked(
                chunk_iter(), filename, total_size,
                file_hash=file_hash if file_hash else None
            )

            # 添加数据库记录
            existing = state["database"].get_file_by_hash(computed_hash)
            if existing:
                file_id = existing["id"]
            else:
                import mimetypes as mt
                mime_type, _ = mt.guess_type(filename)
                if not mime_type:
                    mime_type = "application/octet-stream"
                file_id = state["database"].add_file(
                    filename=storage_path,
                    original_name=filename,
                    file_hash=computed_hash,
                    file_size=file_size,
                    mime_type=mime_type,
                    upload_ip=self.client_address[0] if self.client_address else "",
                )

            self._send_json_response({
                "success": True,
                "file_id": file_id,
                "hash": computed_hash,
                "size": file_size,
            })
        except ValueError as e:
            self._send_json_response({"error": str(e)}, 400)
        except Exception as e:
            self._send_json_response({"error": str(e)}, 500)

    def _handle_list_files(self, query):
        """处理文件列表API"""
        state = self.server_state

        search = query.get("search", [""])[0]
        sort = query.get("sort", ["upload_time"])[0]
        order = query.get("order", ["desc"])[0]
        offset = int(query.get("offset", ["0"])[0])
        limit = int(query.get("limit", ["100"])[0])

        files = state["database"].list_files(
            search=search or None,
            sort_by=sort,
            sort_order=order,
            offset=offset,
            limit=limit,
        )

        file_list = []
        for f in files:
            file_list.append({
                "id": f["id"],
                "filename": f["original_name"],
                "size": f["file_size"],
                "size_formatted": self._format_size(f["file_size"]),
                "mime_type": f["mime_type"],
                "upload_time": f["upload_time"],
                "hash": f["file_hash"][:16],
            })

        self._send_json_response({
            "files": file_list,
            "total": state["database"].get_file_count(),
            "offset": offset,
            "limit": limit,
        })

    def _handle_get_file(self, file_id):
        """获取单个文件信息"""
        state = self.server_state
        file_record = state["database"].get_file(file_id)

        if not file_record:
            self._send_json_response({"error": "文件不存在"}, 404)
            return

        shares = state["share_manager"].list_shares(file_id=file_id)

        self._send_json_response({
            "id": file_record["id"],
            "filename": file_record["original_name"],
            "size": file_record["file_size"],
            "size_formatted": self._format_size(file_record["file_size"]),
            "mime_type": file_record["mime_type"],
            "upload_time": file_record["upload_time"],
            "hash": file_record["file_hash"],
            "shares": [{
                "code": s["share_code"],
                "url": state["share_manager"].get_share_url(s["share_code"]),
                "download_count": s["download_count"],
                "is_active": bool(s["is_active"]),
            } for s in shares],
        })

    def _handle_download(self, file_id, query):
        """处理文件下载"""
        state = self.server_state
        file_record = state["database"].get_file(file_id)

        if not file_record:
            self._send_error_page(404, "文件不存在")
            return

        file_hash = file_record["file_hash"]
        file_size = state["storage"].get_file_size(file_hash)

        if file_size == 0:
            self._send_error_page(404, "文件数据不存在")
            return

        filename = file_record["original_name"]
        mime_type = file_record["mime_type"]

        # 支持断点续传
        range_header = self.headers.get("Range")
        if range_header:
            from .utils import parse_content_range
            range_info = parse_content_range(range_header, file_size)
            if range_info:
                start, end, total = range_info
                data = state["storage"].read_file_chunk(file_hash, start, end)
                if data is not None:
                    self.send_response(206)
                    self.send_header("Content-Type", mime_type)
                    self.send_header(
                        "Content-Disposition",
                        f'attachment; filename="{urllib.parse.quote(filename)}"'
                    )
                    self.send_header(
                        "Content-Range",
                        f"bytes {start}-{end}/{total}"
                    )
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Accept-Ranges", "bytes")
                    self.end_headers()
                    self.wfile.write(data)
                    return

        # 完整下载
        data = state["storage"].read_file(file_hash)
        if data is None:
            self._send_error_page(404, "文件读取失败")
            return

        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="{urllib.parse.quote(filename)}"'
        )
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self.wfile.write(data)

    def _handle_share_download(self, share_code, query):
        """处理通过分享链接下载"""
        state = self.server_state
        share_manager = state["share_manager"]

        # 验证分享链接
        valid, result = share_manager.validate_share(share_code)
        if not valid:
            self._send_json_response({"error": str(result)}, 404)
            return

        share = result

        # 验证密码
        password = query.get("password", [""])[0]
        if share["password"]:
            if not password or not share_manager.verify_share_password(
                share_code, password
            ):
                self._send_json_response({"error": "密码错误"}, 401)
                return

        # 获取文件
        file_record = state["database"].get_file(share["file_id"])
        if not file_record:
            self._send_json_response({"error": "文件不存在"}, 404)
            return

        file_hash = file_record["file_hash"]
        data = state["storage"].read_file(file_hash)
        if data is None:
            self._send_json_response({"error": "文件读取失败"}, 500)
            return

        # 记录下载
        state["database"].increment_download(
            share["id"],
            download_ip=self.client_address[0] if self.client_address else "",
            user_agent=self.headers.get("User-Agent", ""),
        )

        # 发送文件
        filename = file_record["original_name"]
        mime_type = file_record["mime_type"]

        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="{urllib.parse.quote(filename)}"'
        )
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_preview(self, file_id):
        """处理文件预览"""
        state = self.server_state
        file_record = state["database"].get_file(file_id)

        if not file_record:
            self._send_json_response({"error": "文件不存在"}, 404)
            return

        filename = file_record["original_name"]
        file_hash = file_record["file_hash"]
        mime_type = file_record["mime_type"]

        # 图片预览
        if mime_type and mime_type.startswith("image/"):
            data = state["storage"].read_file(file_hash)
            if data is None:
                self._send_error_page(404, "文件读取失败")
                return

            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(data)
            return

        # 文本预览
        from .utils import is_text_file
        if is_text_file(filename):
            data = state["storage"].read_file(file_hash)
            if data is None:
                self._send_error_page(404, "文件读取失败")
                return

            # 限制预览大小（最大1MB）
            max_preview = 1024 * 1024
            if len(data) > max_preview:
                data = data[:max_preview]
                truncated = True
            else:
                truncated = False

            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = data.decode("latin-1")

            # Markdown渲染（简单版本）
            if filename.lower().endswith(".md"):
                text = self._render_markdown(text)

            preview_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>预览 - {html.escape(filename)}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #1e1e1e;
            color: #d4d4d4;
        }}
        pre {{
            white-space: pre-wrap;
            word-break: break-all;
            line-height: 1.6;
            font-size: 14px;
        }}
        .markdown {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            color: #e0e0e0;
            line-height: 1.8;
        }}
        .markdown h1 {{ font-size: 2em; border-bottom: 1px solid #444; padding-bottom: 8px; }}
        .markdown h2 {{ font-size: 1.5em; border-bottom: 1px solid #333; padding-bottom: 6px; }}
        .markdown h3 {{ font-size: 1.25em; }}
        .markdown code {{
            background: #2d2d2d;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.9em;
        }}
        .markdown pre {{
            background: #2d2d2d;
            padding: 16px;
            border-radius: 6px;
            overflow-x: auto;
        }}
        .markdown pre code {{
            background: none;
            padding: 0;
        }}
        .truncated {{
            color: #888;
            font-style: italic;
            margin-top: 16px;
        }}
    </style>
</head>
<body>
    <h3 style="color:#4a90d9;">{html.escape(filename)}</h3>
    <div class="{'markdown' if filename.lower().endswith('.md') else ''}">
        <pre>{html.escape(text) if not filename.lower().endswith('.md') else text}</pre>
    </div>
    {"<p class='truncated'>文件过大，仅显示前1MB内容</p>" if truncated else ""}
</body>
</html>"""
            self._send_html_response(preview_html)
            return

        # 不支持的预览类型
        self._send_json_response(
            {"error": "不支持预览此文件类型"}, 400
        )

    def _render_markdown(self, text):
        """简单的Markdown渲染器

        Args:
            text: Markdown文本

        Returns:
            HTML字符串
        """
        lines = text.split("\n")
        html_parts = []
        in_code_block = False
        in_list = False

        for line in lines:
            # 代码块
            if line.strip().startswith("```"):
                if in_code_block:
                    html_parts.append("</code></pre>")
                    in_code_block = False
                else:
                    html_parts.append("<pre><code>")
                    in_code_block = True
                continue

            if in_code_block:
                html_parts.append(html.escape(line))
                continue

            # 标题
            if line.startswith("### "):
                html_parts.append(f"<h3>{html.escape(line[4:])}</h3>")
                continue
            elif line.startswith("## "):
                html_parts.append(f"<h2>{html.escape(line[3:])}</h2>")
                continue
            elif line.startswith("# "):
                html_parts.append(f"<h1>{html.escape(line[2:])}</h1>")
                continue

            # 列表
            if line.strip().startswith("- ") or line.strip().startswith("* "):
                if not in_list:
                    html_parts.append("<ul>")
                    in_list = True
                html_parts.append(
                    f"<li>{html.escape(line.strip()[2:])}</li>"
                )
                continue
            elif in_list and not line.strip():
                html_parts.append("</ul>")
                in_list = False
                continue

            # 段落
            if line.strip():
                # 行内代码
                line = re.sub(
                    r'`([^`]+)`',
                    r'<code>\1</code>',
                    html.escape(line)
                )
                # 粗体
                line = re.sub(
                    r'\*\*([^*]+)\*\*',
                    r'<strong>\1</strong>',
                    line
                )
                # 斜体
                line = re.sub(
                    r'\*([^*]+)\*',
                    r'<em>\1</em>',
                    line
                )
                # 链接
                line = re.sub(
                    r'\[([^\]]+)\]\(([^)]+)\)',
                    r'<a href="\2">\1</a>',
                    line
                )
                html_parts.append(f"<p>{line}</p>")
            else:
                html_parts.append("<br>")

        if in_list:
            html_parts.append("</ul>")

        return "\n".join(html_parts)

    def _handle_delete_file(self, file_id):
        """处理文件删除"""
        state = self.server_state
        file_record = state["database"].get_file(file_id)

        if not file_record:
            self._send_json_response({"error": "文件不存在"}, 404)
            return

        # 删除存储文件
        state["storage"].delete_file(file_record["file_hash"])
        # 删除数据库记录
        state["database"].delete_file(file_id)

        self._send_json_response({"success": True, "message": "文件已删除"})

    def _handle_create_share(self, file_id):
        """处理创建分享链接"""
        state = self.server_state

        file_record = state["database"].get_file(file_id)
        if not file_record:
            self._send_json_response({"error": "文件不存在"}, 404)
            return

        # 读取请求体
        content_length = int(self.headers.get("Content-Length", 0))
        body = self._read_request_body(content_length)
        if body is None:
            body = b"{}"

        try:
            params = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            params = {}

        password = params.get("password", "")
        expires_hours = int(params.get("expires", 0))
        max_downloads = int(params.get("max_downloads", 0))

        try:
            share = state["share_manager"].create_share(
                file_id=file_id,
                password=password or None,
                expires_hours=expires_hours,
                max_downloads=max_downloads,
            )

            self._send_json_response({
                "success": True,
                "share_code": share["share_code"],
                "share_url": state["share_manager"].get_share_url(share["share_code"]),
                "expires_at": share["expires_at"] or "永不过期",
                "max_downloads": share["max_downloads"] or "不限制",
            })
        except ValueError as e:
            self._send_json_response({"error": str(e)}, 400)

    def _handle_deactivate_share(self, share_code):
        """处理停用分享链接"""
        state = self.server_state
        success = state["share_manager"].deactivate_share(share_code)

        if success:
            self._send_json_response({"success": True, "message": "分享链接已停用"})
        else:
            self._send_json_response({"error": "分享链接不存在"}, 404)

    def _handle_list_shares(self, query):
        """处理列出分享记录"""
        state = self.server_state
        file_id = query.get("file_id", [""])[0]

        shares = state["share_manager"].list_shares(
            file_id=file_id or None,
            active_only=False
        )

        share_list = []
        for s in shares:
            share_list.append({
                "share_code": s["share_code"],
                "share_url": state["share_manager"].get_share_url(s["share_code"]),
                "filename": s.get("original_name", ""),
                "file_size": s.get("file_size", 0),
                "download_count": s["download_count"],
                "max_downloads": s["max_downloads"],
                "is_active": bool(s["is_active"]),
                "created_at": s["created_at"],
                "expires_at": s["expires_at"],
            })

        self._send_json_response({"shares": share_list})

    def _handle_export(self, query):
        """处理导出分享记录"""
        state = self.server_state
        format_type = query.get("format", ["json"])[0]

        content = state["share_manager"].export_shares(format_type=format_type)

        mime_types = {
            "json": "application/json",
            "csv": "text/csv",
            "markdown": "text/markdown",
        }
        mime_type = mime_types.get(format_type, "application/json")

        response_body = content.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", f"{mime_type}; charset=utf-8")
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="filedrop_shares.{format_type}"'
        )
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def _handle_server_info(self):
        """处理服务器信息API"""
        state = self.server_state
        storage_info = state["storage"].get_storage_info()

        self._send_json_response({
            "version": "1.0.0",
            "total_files": state["database"].get_file_count(),
            "total_size": state["database"].get_total_size(),
            "storage_info": storage_info,
        })

    def _handle_auth(self):
        """处理认证请求"""
        state = self.server_state

        content_length = int(self.headers.get("Content-Length", 0))
        body = self._read_request_body(content_length)
        if body is None:
            body = b"{}"

        try:
            params = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json_response({"error": "无效的请求数据"}, 400)
            return

        password = params.get("password", "")
        if not password:
            self._send_json_response({"error": "请输入密码"}, 400)
            return

        if state["password_manager"].verify_password(
            password, state["password_hash"]
        ):
            self._send_json_response({"success": True, "message": "认证成功"})
        else:
            self._send_json_response({"error": "密码错误"}, 401)

    # ---- 辅助方法 ----

    def _read_request_body(self, content_length):
        """读取请求体

        Args:
            content_length: Content-Length头值

        Returns:
            请求体字节数据，读取失败返回None
        """
        try:
            if content_length > 0:
                body = self.rfile.read(content_length)
            else:
                body = self.rfile.read()
            return body
        except Exception:
            return None

    @staticmethod
    def _format_size(size_bytes):
        """格式化文件大小"""
        if size_bytes is None or size_bytes < 0:
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
