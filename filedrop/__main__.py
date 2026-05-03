"""
FileDrop CLI入口 - 命令行接口
"""

import sys
import os
import argparse
import json
import urllib.request
import urllib.parse
import urllib.error


def cmd_serve(args):
    """启动文件共享服务器"""
    from .server import FileDropServer

    # 解析大小限制
    max_size = 0
    if args.max_size:
        max_size = parse_size(args.max_size)

    server = FileDropServer(
        host=args.host,
        port=args.port,
        storage_dir=args.dir,
        password=args.password,
        max_size=max_size,
        verbose=not args.quiet,
    )
    server.start()


def cmd_upload(args):
    """上传文件到服务器"""
    server_url = args.server.rstrip("/")

    for filepath in args.files:
        if not os.path.isfile(filepath):
            print(f"错误: 文件不存在 - {filepath}", file=sys.stderr)
            continue

        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath)

        print(f"正在上传: {filename} ({format_size(file_size)})")

        try:
            # 构建multipart请求
            boundary = "----FileDropBoundary" + os.urandom(8).hex()

            with open(filepath, "rb") as f:
                file_data = f.read()

            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
                f"Content-Type: application/octet-stream\r\n"
                f"\r\n"
            ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

            url = f"{server_url}/api/upload"
            req = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers={
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                },
            )

            # 添加认证
            if args.password:
                import base64
                credentials = base64.b64encode(
                    f":{args.password}".encode("utf-8")
                ).decode("utf-8")
                req.add_header("Authorization", f"Basic {credentials}")

            # 上传进度
            last_percent = -1

            def progress_hook(block_num, block_size, total_size):
                nonlocal last_percent
                if total_size > 0:
                    percent = int(block_num * block_size * 100 / total_size)
                    percent = min(percent, 100)
                    if percent != last_percent:
                        last_percent = percent
                        bar_width = 30
                        filled = int(bar_width * percent / 100)
                        bar = "=" * filled + "-" * (bar_width - filled)
                        sys.stdout.write(
                            f"\r  [{bar}] {percent}% "
                            f"({format_size(block_num * block_size)}/{format_size(total_size)})"
                        )
                        sys.stdout.flush()

            # 使用简单的进度显示
            print(f"  上传中...", end="")
            sys.stdout.flush()

            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            print(f"\r  上传完成! {'  ' * 20}")

            if result.get("success"):
                for item in result.get("uploaded", []):
                    if item.get("error"):
                        print(f"  错误: {item['filename']} - {item['error']}")
                    elif item.get("duplicate"):
                        print(f"  去重: {item['filename']} (已存在)")
                    else:
                        print(f"  成功: {item['filename']} (ID: {item['id'][:8]}...)")
            else:
                print(f"  错误: {result.get('error', '未知错误')}")

        except urllib.error.HTTPError as e:
            print(f"\r  上传失败: HTTP {e.code}")
            try:
                error_body = e.read().decode("utf-8")
                error_data = json.loads(error_body)
                print(f"  详情: {error_data.get('error', '')}")
            except Exception:
                pass
        except urllib.error.URLError as e:
            print(f"\r  连接失败: {e.reason}")
        except Exception as e:
            print(f"\r  上传失败: {e}")


def cmd_download(args):
    """通过分享链接下载文件"""
    server_url = args.server.rstrip("/") if args.server else ""

    share_code = args.share_id
    output_dir = args.output or "."

    # 构建下载URL
    if share_code.startswith("http"):
        # 完整URL
        download_url = share_code
    else:
        # 分享码
        download_url = f"{server_url}/api/share/{share_code}"

    # 添加密码参数
    if args.password:
        separator = "&" if "?" in download_url else "?"
        download_url += f"{separator}password={urllib.parse.quote(args.password)}"

    print(f"正在下载分享文件: {share_code}")

    try:
        req = urllib.request.Request(download_url)
        with urllib.request.urlopen(req) as resp:
            # 获取文件名
            content_disp = resp.headers.get("Content-Disposition", "")
            filename = "downloaded_file"
            if "filename=" in content_disp:
                filename = content_disp.split("filename=")[1].strip('"')

            file_size = int(resp.headers.get("Content-Length", 0))
            total_read = 0

            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, filename)

            # 避免文件名冲突
            counter = 1
            base, ext = os.path.splitext(filename)
            while os.path.exists(output_path):
                output_path = os.path.join(output_dir, f"{base}_{counter}{ext}")
                counter += 1

            with open(output_path, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    total_read += len(chunk)

                    if file_size > 0:
                        percent = int(total_read * 100 / file_size)
                        bar_width = 30
                        filled = int(bar_width * percent / 100)
                        bar = "=" * filled + "-" * (bar_width - filled)
                        sys.stdout.write(
                            f"\r  [{bar}] {percent}% "
                            f"({format_size(total_read)}/{format_size(file_size)})"
                        )
                        sys.stdout.flush()

            print(f"\r  下载完成: {output_path} ({format_size(total_read)}){' ' * 20}")

    except urllib.error.HTTPError as e:
        print(f"  下载失败: HTTP {e.code}")
        try:
            error_body = e.read().decode("utf-8")
            error_data = json.loads(error_body)
            print(f"  详情: {error_data.get('error', '')}")
        except Exception:
            pass
    except urllib.error.URLError as e:
        print(f"  连接失败: {e.reason}")
    except Exception as e:
        print(f"  下载失败: {e}")


def cmd_list(args):
    """列出服务器上的文件"""
    server_url = args.server.rstrip("/")
    api_url = f"{server_url}/api/files"

    params = {}
    if args.search:
        params["search"] = args.search
    if args.sort:
        params["sort"] = args.sort
    if args.order:
        params["order"] = args.order
    if args.limit:
        params["limit"] = str(args.limit)

    if params:
        api_url += "?" + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(api_url)
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        files = result.get("files", [])
        total = result.get("total", 0)

        if not files:
            print("没有找到文件。")
            return

        print(f"\n文件列表 (共 {total} 个文件)\n")
        print(f"  {'文件名':<40} {'大小':<12} {'上传时间':<20}")
        print(f"  {'-'*40} {'-'*12} {'-'*20}")

        for f in files:
            name = f["filename"]
            if len(name) > 38:
                name = name[:35] + "..."
            size = f.get("size_formatted", format_size(f["size"]))
            upload_time = f.get("upload_time", "")[:19]
            print(f"  {name:<40} {size:<12} {upload_time:<20}")

        print()

    except urllib.error.URLError as e:
        print(f"连接失败: {e.reason}", file=sys.stderr)
    except Exception as e:
        print(f"获取文件列表失败: {e}", file=sys.stderr)


def cmd_share(args):
    """创建分享链接"""
    server_url = args.server.rstrip("/")
    file_id = args.file_id

    # 构建请求
    url = f"{server_url}/api/share/create/{file_id}"
    data = {}
    if args.password:
        data["password"] = args.password
    if args.expires:
        data["expires"] = str(args.expires)
    if args.max_downloads:
        data["max_downloads"] = str(args.max_downloads)

    body = json.dumps(data).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        if result.get("success"):
            print(f"\n分享链接创建成功!\n")
            print(f"  分享码: {result['share_code']}")
            print(f"  链接: {result['share_url']}")
            print(f"  过期: {result.get('expires_at', '永不过期')}")
            print(f"  下载限制: {result.get('max_downloads', '不限制')}")
            print()

            # 生成二维码
            try:
                from .utils import generate_qr_code
                qr = generate_qr_code(result["share_url"])
                print(f"  二维码:")
                for line in qr.split("\n"):
                    print(f"  {line}")
                print()
            except Exception:
                pass
        else:
            print(f"创建失败: {result.get('error', '未知错误')}", file=sys.stderr)

    except urllib.error.HTTPError as e:
        print(f"创建失败: HTTP {e.code}", file=sys.stderr)
        try:
            error_body = e.read().decode("utf-8")
            error_data = json.loads(error_body)
            print(f"详情: {error_data.get('error', '')}", file=sys.stderr)
        except Exception:
            pass
    except urllib.error.URLError as e:
        print(f"连接失败: {e.reason}", file=sys.stderr)


def cmd_export(args):
    """导出分享记录"""
    server_url = args.server.rstrip("/")
    format_type = args.format or "json"
    output_file = args.output

    url = f"{server_url}/api/export?format={format_type}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"已导出到: {output_file}")
        else:
            print(content)

    except urllib.error.URLError as e:
        print(f"导出失败: {e.reason}", file=sys.stderr)


def cmd_info(args):
    """显示服务器信息"""
    server_url = args.server.rstrip("/")
    url = f"{server_url}/api/info"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        print(f"\nFileDrop 服务器信息\n")
        print(f"  版本: {result.get('version', '未知')}")
        print(f"  文件数量: {result.get('total_files', 0)}")
        print(f"  总大小: {format_size(result.get('total_size', 0))}")
        storage = result.get("storage_info", {})
        print(f"  存储路径: {storage.get('storage_path', '未知')}")
        print()

    except urllib.error.URLError as e:
        print(f"连接失败: {e.reason}", file=sys.stderr)


# ---- 辅助函数 ----

def parse_size(size_str):
    """解析大小字符串为字节数

    Args:
        size_str: 大小字符串，如 '100MB', '1GB', '500K'

    Returns:
        字节数
    """
    size_str = size_str.strip().upper()
    multipliers = {
        "B": 1,
        "K": 1024,
        "KB": 1024,
        "M": 1024 ** 2,
        "MB": 1024 ** 2,
        "G": 1024 ** 3,
        "GB": 1024 ** 3,
        "T": 1024 ** 4,
        "TB": 1024 ** 4,
    }

    for suffix, multiplier in sorted(multipliers.items(), key=lambda x: -len(x[0])):
        if size_str.endswith(suffix):
            try:
                number = float(size_str[:-len(suffix)])
                return int(number * multiplier)
            except ValueError:
                break

    try:
        return int(size_str)
    except ValueError:
        print(f"警告: 无法解析大小 '{size_str}'，将使用无限制", file=sys.stderr)
        return 0


def format_size(size_bytes):
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


def build_parser():
    """构建CLI参数解析器

    Returns:
        ArgumentParser实例
    """
    parser = argparse.ArgumentParser(
        prog="filedrop",
        description="FileDrop - 轻量级自托管文件共享服务器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  filedrop serve --port 8080 --password mypass
  filedrop upload file1.txt file2.pdf --server http://localhost:8080
  filedrop download abc12345 --output ./downloads
  filedrop share <file-id> --password secret --expires 24
  filedrop list --server http://localhost:8080
  filedrop export --format markdown --output shares.md
        """,
    )

    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"FileDrop v1.0.0"
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # serve 命令
    serve_parser = subparsers.add_parser("serve", help="启动文件共享服务器")
    serve_parser.add_argument(
        "--host", default="0.0.0.0",
        help="监听地址 (默认: 0.0.0.0)"
    )
    serve_parser.add_argument(
        "--port", type=int, default=8080,
        help="监听端口 (默认: 8080)"
    )
    serve_parser.add_argument(
        "--dir", default=None,
        help="文件存储目录 (默认: ./filedrop_data)"
    )
    serve_parser.add_argument(
        "--password", default=None,
        help="设置访问密码"
    )
    serve_parser.add_argument(
        "--max-size", default=None,
        help="最大文件大小限制 (如: 100MB, 1GB)"
    )
    serve_parser.add_argument(
        "--no-auth", action="store_true",
        help="禁用认证"
    )
    serve_parser.add_argument(
        "--quiet", action="store_true",
        help="安静模式，减少输出"
    )
    serve_parser.set_defaults(func=cmd_serve)

    # upload 命令
    upload_parser = subparsers.add_parser("upload", help="上传文件")
    upload_parser.add_argument(
        "files", nargs="+",
        help="要上传的文件路径"
    )
    upload_parser.add_argument(
        "--server", default="http://localhost:8080",
        help="服务器URL (默认: http://localhost:8080)"
    )
    upload_parser.add_argument(
        "--password", default=None,
        help="访问密码"
    )
    upload_parser.set_defaults(func=cmd_upload)

    # download 命令
    download_parser = subparsers.add_parser("download", help="下载分享文件")
    download_parser.add_argument(
        "share_id",
        help="分享码或完整分享URL"
    )
    download_parser.add_argument(
        "--server", default="http://localhost:8080",
        help="服务器URL (默认: http://localhost:8080)"
    )
    download_parser.add_argument(
        "--output", "-o", default=None,
        help="输出目录 (默认: 当前目录)"
    )
    download_parser.add_argument(
        "--password", default=None,
        help="提取密码"
    )
    download_parser.set_defaults(func=cmd_download)

    # list 命令
    list_parser = subparsers.add_parser("list", help="列出服务器上的文件")
    list_parser.add_argument(
        "--server", default="http://localhost:8080",
        help="服务器URL (默认: http://localhost:8080)"
    )
    list_parser.add_argument(
        "--search", default=None,
        help="搜索关键词"
    )
    list_parser.add_argument(
        "--sort", default="upload_time",
        choices=["upload_time", "filename", "file_size"],
        help="排序字段 (默认: upload_time)"
    )
    list_parser.add_argument(
        "--order", default="desc",
        choices=["asc", "desc"],
        help="排序方向 (默认: desc)"
    )
    list_parser.add_argument(
        "--limit", type=int, default=None,
        help="返回数量限制"
    )
    list_parser.set_defaults(func=cmd_list)

    # share 命令
    share_parser = subparsers.add_parser("share", help="创建分享链接")
    share_parser.add_argument(
        "file_id",
        help="文件ID"
    )
    share_parser.add_argument(
        "--server", default="http://localhost:8080",
        help="服务器URL (默认: http://localhost:8080)"
    )
    share_parser.add_argument(
        "--password", default=None,
        help="设置分享密码"
    )
    share_parser.add_argument(
        "--expires", type=int, default=None,
        help="过期时间（小时）"
    )
    share_parser.add_argument(
        "--max-downloads", type=int, default=None,
        help="最大下载次数"
    )
    share_parser.set_defaults(func=cmd_share)

    # export 命令
    export_parser = subparsers.add_parser("export", help="导出分享记录")
    export_parser.add_argument(
        "--server", default="http://localhost:8080",
        help="服务器URL (默认: http://localhost:8080)"
    )
    export_parser.add_argument(
        "--format", default="json",
        choices=["json", "csv", "markdown"],
        help="导出格式 (默认: json)"
    )
    export_parser.add_argument(
        "--output", default=None,
        help="输出文件路径"
    )
    export_parser.set_defaults(func=cmd_export)

    # info 命令
    info_parser = subparsers.add_parser("info", help="显示服务器信息")
    info_parser.add_argument(
        "--server", default="http://localhost:8080",
        help="服务器URL (默认: http://localhost:8080)"
    )
    info_parser.set_defaults(func=cmd_info)

    return parser


def main():
    """CLI主入口"""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # 执行对应命令
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n操作已取消。")
        sys.exit(0)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
