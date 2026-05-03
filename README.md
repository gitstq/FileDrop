<p align="center">
  <h1 align="center">📦 FileDrop</h1>
  <p align="center">
    <strong>Lightweight Self-Hosted File Sharing Server CLI</strong>
  </p>
  <p align="center">
    <a href="#-简体中文">简体中文</a> ·
    <a href="#-繁體中文">繁體中文</a> ·
    <a href="#-english">English</a>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python 3.8+">
    <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License">
    <img src="https://img.shields.io/badge/Dependencies-Zero-success.svg" alt="Zero Dependencies">
    <img src="https://img.shields.io/badge/Tests-86%20Passed-brightgreen.svg" alt="86 Tests Passed">
  </p>
</p>

---

<a id="-简体中文"></a>

## 🎉 项目介绍

**FileDrop** 是一款轻量级自托管文件共享服务器 CLI 工具，纯 Python 标准库实现，**零第三方依赖**。只需一行命令即可在局域网或公网快速搭建私有文件共享服务。

### 💡 灵感来源

在日常开发与团队协作中，经常需要快速在设备间传输文件。现有方案要么过于笨重（如 Nextcloud），要么需要复杂配置（如 FTP/Samba），要么依赖第三方服务（如网盘）。FileDrop 致力于提供一个**开箱即用、安全可控、功能完整**的轻量级替代方案。

### 🌟 自研差异化亮点

- **零依赖** — 仅使用 Python 标准库，无需 `pip install` 任何第三方包
- **SHA256 文件去重** — 自动检测重复文件，节省存储空间
- **密码保护分享** — 支持 PBKDF2 密码哈希、过期时间、下载次数限制
- **断点续传** — 上传和下载均支持断点续传，大文件传输更可靠
- **ASCII 二维码** — 纯代码生成二维码，无需图形库
- **现代 Web 界面** — 拖拽上传、文件预览、响应式设计

---

## ✨ 核心特性

| 特性 | 描述 |
|------|------|
| 🚀 **一键启动** | `python -m filedrop serve` 即可启动文件共享服务 |
| 📤 **拖拽上传** | Web 界面支持拖拽上传、多文件批量上传 |
| 🔗 **分享链接** | 自动生成唯一分享链接，支持密码/过期/次数限制 |
| 🔒 **安全防护** | PBKDF2 密码哈希、速率限制、路径遍历防护 |
| 📋 **文件去重** | SHA256 哈希检测，相同文件自动引用不重复存储 |
| 📊 **断点续传** | 支持 Range 请求，大文件传输中断后可续传 |
| 👁️ **文件预览** | 图片缩略图、文本/Markdown 在线预览 |
| 📱 **二维码分享** | ASCII Art 风格二维码，终端直接显示 |
| 📑 **记录导出** | 分享记录支持 JSON/CSV/Markdown 多格式导出 |
| 🎨 **现代 UI** | 响应式 Web 界面，支持桌面端和移动端 |

---

## 🚀 快速开始

### 环境要求

- **Python 3.8+**（无需任何第三方依赖）

### 安装

```bash
# 克隆仓库
git clone https://github.com/gitstq/FileDrop.git
cd FileDrop

# 或者直接下载
wget https://github.com/gitstq/FileDrop/archive/refs/heads/main.zip
unzip FileDrop-main.zip && cd FileDrop-main
```

### 启动服务器

```bash
# 一键启动（默认端口 8080）
python -m filedrop serve

# 指定端口和目录
python -m filedrop serve --port 9090 --dir ~/shared

# 启用密码保护
python -m filedrop serve --password mysecret

# 允许公网访问
python -m filedrop serve --host 0.0.0.0 --port 80
```

### CLI 命令

```bash
# 查看帮助
python -m filedrop --help

# 上传文件到服务器
python -m filedrop upload file1.txt file2.pdf --server http://localhost:8080

# 通过分享链接下载文件
python -m filedrop download abc123 --output ./downloads

# 列出所有文件
python -m filedrop list --server http://localhost:8080

# 创建分享链接（带密码和过期时间）
python -m filedrop share file-id --password secret --expires 24 --max-downloads 10

# 导出分享记录
python -m filedrop export --format json --output shares.json

# 查看服务器信息
python -m filedrop info
```

---

## 📖 详细使用指南

### 服务端配置

| 参数 | 默认值 | 描述 |
|------|--------|------|
| `--host` | `127.0.0.1` | 监听地址 |
| `--port` | `8080` | 监听端口 |
| `--dir` | `./filedrop_data` | 文件存储目录 |
| `--password` | 无 | 访问密码 |
| `--max-size` | `500MB` | 最大上传文件大小 |
| `--no-auth` | `False` | 禁用上传认证 |

### 分享链接管理

```bash
# 创建永久分享链接
python -m filedrop share <file-id>

# 创建带密码保护的分享链接
python -m filedrop share <file-id> --password mypass

# 创建24小时过期的分享链接
python -m filedrop share <file-id> --expires 24

# 限制最多下载10次
python -m filedrop share <file-id> --max-downloads 10

# 组合使用
python -m filedrop share <file-id> --password mypass --expires 48 --max-downloads 5
```

### 典型使用场景

**场景一：团队内部文件共享**
```bash
# 在团队服务器上启动
python -m filedrop serve --host 0.0.0.0 --port 8080 --password team2025
# 团队成员通过浏览器访问 http://server:8080 即可上传下载
```

**场景二：临时文件传输**
```bash
# 在本机启动，生成二维码分享
python -m filedrop serve --port 9999
# 其他设备扫码即可访问
```

**场景三：自动化文件分发**
```bash
# 上传文件并创建分享链接
python -m filedrop upload report.pdf --server http://server:8080
python -m filedrop share <file-id> --expires 72
# 将生成的链接发送给接收方
```

---

## 💡 设计思路与迭代规划

### 设计理念

- **极简主义** — 零依赖，一个 Python 文件即可运行
- **安全优先** — 默认启用安全防护，密码使用 PBKDF2 哈希
- **用户友好** — 现代化 Web 界面，拖拽上传，直观操作
- **可扩展** — 模块化设计，便于二次开发

### 技术选型

| 组件 | 选型 | 原因 |
|------|------|------|
| HTTP 服务器 | `http.server` | 标准库，零依赖 |
| 数据库 | `sqlite3` | 标准库，轻量级，无需安装 |
| 密码哈希 | `hashlib.pbkdf2_hmac` | 标准库，安全可靠 |
| 文件去重 | `hashlib.sha256` | 标准库，高效准确 |

### 后续迭代计划

- [ ] WebSocket 实时通知
- [ ] 文件夹批量上传
- [ ] 图片 EXIF 信息读取
- [ ] 文件版本管理
- [ ] WebDAV 协议支持
- [ ] Docker 镜像发布
- [ ] 插件系统

---

## 📦 打包与部署指南

### 作为模块使用

```bash
# 添加到 Python 路径
export PYTHONPATH=/path/to/FileDrop:$PYTHONPATH

# 直接调用
python -m filedrop serve
```

### 作为库导入

```python
from filedrop.server import FileDropServer
from filedrop.storage import FileStorage

# 初始化存储
storage = FileStorage("./my_files")

# 启动服务器
server = FileDropServer(host="0.0.0.0", port=8080, storage=storage)
server.start()
```

### 系统服务部署（systemd）

```ini
[Unit]
Description=FileDrop File Sharing Server
After=network.target

[Service]
Type=simple
User=filedrop
ExecStart=/usr/bin/python3 -m filedrop serve --host 0.0.0.0 --port 8080 --dir /var/lib/filedrop
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 🤝 贡献指南

欢迎社区贡献！请遵循以下规范：

1. **Fork** 本仓库
2. 创建特性分支：`git checkout -b feat/amazing-feature`
3. 提交更改：`git commit -m 'feat: add amazing feature'`
4. 推送分支：`git push origin feat/amazing-feature`
5. 提交 **Pull Request**

### 提交规范

遵循 Angular 提交规范：
- `feat:` 新功能
- `fix:` 修复问题
- `docs:` 文档更新
- `refactor:` 代码重构
- `test:` 测试相关
- `chore:` 构建/工具变更

---

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 开源。

---

<a id="-繁體中文"></a>

## 🎉 專案介紹

**FileDrop** 是一款輕量級自託管檔案共享伺服器 CLI 工具，純 Python 標準函式庫實現，**零第三方依賴**。只需一行指令即可在區域網路或公網快速搭建私有檔案共享服務。

### 💡 靈感來源

在日常開發與團隊協作中，經常需要快速在裝置間傳輸檔案。現有方案要麼過於笨重（如 Nextcloud），要麼需要複雜配置（如 FTP/Samba），要麼依賴第三方服務（如雲端硬碟）。FileDrop 致力於提供一個**開箱即用、安全可控、功能完整**的輕量級替代方案。

### 🌟 自研差異化亮點

- **零依賴** — 僅使用 Python 標準函式庫，無需 `pip install` 任何第三方套件
- **SHA256 檔案去重** — 自動偵測重複檔案，節省儲存空間
- **密碼保護分享** — 支援 PBKDF2 密碼雜湊、過期時間、下載次數限制
- **斷點續傳** — 上傳和下載均支援斷點續傳，大檔案傳輸更可靠
- **ASCII 二維碼** — 純程式碼生成二維碼，無需圖形函式庫
- **現代 Web 介面** — 拖放上傳、檔案預覽、響應式設計

---

## ✨ 核心特性

| 特性 | 描述 |
|------|------|
| 🚀 **一鍵啟動** | `python -m filedrop serve` 即可啟動檔案共享服務 |
| 📤 **拖放上傳** | Web 介面支援拖放上傳、多檔案批次上傳 |
| 🔗 **分享連結** | 自動生成唯一分享連結，支援密碼/過期/次數限制 |
| 🔒 **安全防護** | PBKDF2 密碼雜湊、速率限制、路徑遍歷防護 |
| 📋 **檔案去重** | SHA256 雜湊偵測，相同檔案自動引用不重複儲存 |
| 📊 **斷點續傳** | 支援 Range 請求，大檔案傳輸中斷後可續傳 |
| 👁️ **檔案預覽** | 圖片縮圖、文字/Markdown 線上預覽 |
| 📱 **二維碼分享** | ASCII Art 風格二維碼，終端直接顯示 |
| 📑 **記錄匯出** | 分享記錄支援 JSON/CSV/Markdown 多格式匯出 |
| 🎨 **現代 UI** | 響應式 Web 介面，支援桌面端和行動端 |

---

## 🚀 快速開始

### 環境需求

- **Python 3.8+**（無需任何第三方依賴）

### 安裝

```bash
# 克隆倉庫
git clone https://github.com/gitstq/FileDrop.git
cd FileDrop

# 或直接下載
wget https://github.com/gitstq/FileDrop/archive/refs/heads/main.zip
unzip FileDrop-main.zip && cd FileDrop-main
```

### 啟動伺服器

```bash
# 一鍵啟動（預設連接埠 8080）
python -m filedrop serve

# 指定連接埠和目錄
python -m filedrop serve --port 9090 --dir ~/shared

# 啟用密碼保護
python -m filedrop serve --password mysecret

# 允許公網存取
python -m filedrop serve --host 0.0.0.0 --port 80
```

### CLI 指令

```bash
# 查看說明
python -m filedrop --help

# 上傳檔案到伺服器
python -m filedrop upload file1.txt file2.pdf --server http://localhost:8080

# 透過分享連結下載檔案
python -m filedrop download abc123 --output ./downloads

# 列出所有檔案
python -m filedrop list --server http://localhost:8080

# 建立分享連結（帶密碼和過期時間）
python -m filedrop share file-id --password secret --expires 24 --max-downloads 10

# 匯出分享記錄
python -m filedrop export --format json --output shares.json

# 查看伺服器資訊
python -m filedrop info
```

---

## 📖 詳細使用指南

### 伺服器端配置

| 參數 | 預設值 | 描述 |
|------|--------|------|
| `--host` | `127.0.0.1` | 監聽位址 |
| `--port` | `8080` | 監聽連接埠 |
| `--dir` | `./filedrop_data` | 檔案儲存目錄 |
| `--password` | 無 | 存取密碼 |
| `--max-size` | `500MB` | 最大上傳檔案大小 |
| `--no-auth` | `False` | 停用上傳認證 |

### 分享連結管理

```bash
# 建立永久分享連結
python -m filedrop share <file-id>

# 建立帶密碼保護的分享連結
python -m filedrop share <file-id> --password mypass

# 建立24小時過期的分享連結
python -m filedrop share <file-id> --expires 24

# 限制最多下載10次
python -m filedrop share <file-id> --max-downloads 10

# 組合使用
python -m filedrop share <file-id> --password mypass --expires 48 --max-downloads 5
```

### 典型使用場景

**場景一：團隊內部檔案共享**
```bash
# 在團隊伺服器上啟動
python -m filedrop serve --host 0.0.0.0 --port 8080 --password team2025
# 團隊成員透過瀏覽器存取 http://server:8080 即可上傳下載
```

**場景二：臨時檔案傳輸**
```bash
# 在本機啟動，生成二維碼分享
python -m filedrop serve --port 9999
# 其他裝置掃碼即可存取
```

**場景三：自動化檔案分發**
```bash
# 上傳檔案並建立分享連結
python -m filedrop upload report.pdf --server http://server:8080
python -m filedrop share <file-id> --expires 72
# 將生成的連結發送給接收方
```

---

## 💡 設計思路與迭代規劃

### 設計理念

- **極簡主義** — 零依賴，一個 Python 檔案即可執行
- **安全優先** — 預設啟用安全防護，密碼使用 PBKDF2 雜湊
- **使用者友善** — 現代化 Web 介面，拖放上傳，直觀操作
- **可擴展** — 模組化設計，便於二次開發

### 技術選型

| 元件 | 選型 | 原因 |
|------|------|------|
| HTTP 伺服器 | `http.server` | 標準函式庫，零依賴 |
| 資料庫 | `sqlite3` | 標準函式庫，輕量級，無需安裝 |
| 密碼雜湊 | `hashlib.pbkdf2_hmac` | 標準函式庫，安全可靠 |
| 檔案去重 | `hashlib.sha256` | 標準函式庫，高效準確 |

### 後續迭代計畫

- [ ] WebSocket 即時通知
- [ ] 資料夾批次上傳
- [ ] 圖片 EXIF 資訊讀取
- [ ] 檔案版本管理
- [ ] WebDAV 協定支援
- [ ] Docker 映像檔發布
- [ ] 外掛系統

---

## 📦 打包與部署指南

### 作為模組使用

```bash
# 新增到 Python 路徑
export PYTHONPATH=/path/to/FileDrop:$PYTHONPATH

# 直接呼叫
python -m filedrop serve
```

### 作為函式庫匯入

```python
from filedrop.server import FileDropServer
from filedrop.storage import FileStorage

# 初始化儲存
storage = FileStorage("./my_files")

# 啟動伺服器
server = FileDropServer(host="0.0.0.0", port=8080, storage=storage)
server.start()
```

### 系統服務部署（systemd）

```ini
[Unit]
Description=FileDrop File Sharing Server
After=network.target

[Service]
Type=simple
User=filedrop
ExecStart=/usr/bin/python3 -m filedrop serve --host 0.0.0.0 --port 8080 --dir /var/lib/filedrop
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 🤝 貢獻指南

歡迎社群貢獻！請遵循以下規範：

1. **Fork** 本倉庫
2. 建立特性分支：`git checkout -b feat/amazing-feature`
3. 提交變更：`git commit -m 'feat: add amazing feature'`
4. 推送分支：`git push origin feat/amazing-feature`
5. 提交 **Pull Request**

### 提交規範

遵循 Angular 提交規範：
- `feat:` 新功能
- `fix:` 修復問題
- `docs:` 文件更新
- `refactor:` 程式碼重構
- `test:` 測試相關
- `chore:` 建構/工具變更

---

## 📄 開源協議

本專案基於 [MIT License](LICENSE) 開源。

---

<a id="-english"></a>

## 🎉 Introduction

**FileDrop** is a lightweight self-hosted file sharing server CLI tool, built entirely with Python's standard library — **zero third-party dependencies**. Set up a private file sharing service on your LAN or the public internet with a single command.

### 💡 Inspiration

In daily development and team collaboration, there's a frequent need to quickly transfer files between devices. Existing solutions are either too heavy (like Nextcloud), require complex configuration (like FTP/Samba), or depend on third-party services (like cloud storage). FileDrop aims to provide a **ready-to-use, secure, and feature-complete** lightweight alternative.

### 🌟 Differentiation Highlights

- **Zero Dependencies** — Uses only Python standard library, no `pip install` needed
- **SHA256 File Deduplication** — Automatically detects duplicate files to save storage
- **Password-Protected Sharing** — PBKDF2 password hashing, expiry time, download count limits
- **Resumable Transfers** — Both upload and download support resume on interruption
- **ASCII QR Codes** — Generate QR codes in pure code, no graphics library needed
- **Modern Web UI** — Drag-and-drop upload, file preview, responsive design

---

## ✨ Core Features

| Feature | Description |
|---------|-------------|
| 🚀 **One-Command Start** | `python -m filedrop serve` to launch the file sharing service |
| 📤 **Drag & Drop Upload** | Web UI supports drag-and-drop and batch file uploads |
| 🔗 **Share Links** | Auto-generated unique share links with password/expiry/download limits |
| 🔒 **Security** | PBKDF2 password hashing, rate limiting, path traversal protection |
| 📋 **File Dedup** | SHA256 hash detection, duplicate files auto-referenced without re-storage |
| 📊 **Resumable Transfer** | Range request support for reliable large file transfers |
| 👁️ **File Preview** | Image thumbnails, text/Markdown inline preview |
| 📱 **QR Code Sharing** | ASCII Art style QR codes displayed directly in terminal |
| 📑 **Record Export** | Share records exportable in JSON/CSV/Markdown formats |
| 🎨 **Modern UI** | Responsive web interface for desktop and mobile |

---

## 🚀 Quick Start

### Requirements

- **Python 3.8+** (no third-party dependencies required)

### Installation

```bash
# Clone the repository
git clone https://github.com/gitstq/FileDrop.git
cd FileDrop

# Or download directly
wget https://github.com/gitstq/FileDrop/archive/refs/heads/main.zip
unzip FileDrop-main.zip && cd FileDrop-main
```

### Start the Server

```bash
# One-command start (default port 8080)
python -m filedrop serve

# Specify port and directory
python -m filedrop serve --port 9090 --dir ~/shared

# Enable password protection
python -m filedrop serve --password mysecret

# Allow public access
python -m filedrop serve --host 0.0.0.0 --port 80
```

### CLI Commands

```bash
# Show help
python -m filedrop --help

# Upload files to server
python -m filedrop upload file1.txt file2.pdf --server http://localhost:8080

# Download via share link
python -m filedrop download abc123 --output ./downloads

# List all files
python -m filedrop list --server http://localhost:8080

# Create share link with password and expiry
python -m filedrop share file-id --password secret --expires 24 --max-downloads 10

# Export share records
python -m filedrop export --format json --output shares.json

# Show server info
python -m filedrop info
```

---

## 📖 Detailed Usage Guide

### Server Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--host` | `127.0.0.1` | Listen address |
| `--port` | `8080` | Listen port |
| `--dir` | `./filedrop_data` | File storage directory |
| `--password` | None | Access password |
| `--max-size` | `500MB` | Maximum upload file size |
| `--no-auth` | `False` | Disable upload authentication |

### Share Link Management

```bash
# Create a permanent share link
python -m filedrop share <file-id>

# Create a password-protected share link
python -m filedrop share <file-id> --password mypass

# Create a share link that expires in 24 hours
python -m filedrop share <file-id> --expires 24

# Limit to 10 downloads max
python -m filedrop share <file-id> --max-downloads 10

# Combine options
python -m filedrop share <file-id> --password mypass --expires 48 --max-downloads 5
```

### Typical Use Cases

**Scenario 1: Team Internal File Sharing**
```bash
# Start on team server
python -m filedrop serve --host 0.0.0.0 --port 8080 --password team2025
# Team members access http://server:8080 via browser to upload/download
```

**Scenario 2: Quick File Transfer**
```bash
# Start locally, generate QR code for sharing
python -m filedrop serve --port 9999
# Other devices scan the QR code to access
```

**Scenario 3: Automated File Distribution**
```bash
# Upload file and create share link
python -m filedrop upload report.pdf --server http://server:8080
python -m filedrop share <file-id> --expires 72
# Send the generated link to recipients
```

---

## 💡 Design Philosophy & Roadmap

### Design Principles

- **Minimalism** — Zero dependencies, runs with a single Python command
- **Security First** — Security protections enabled by default, PBKDF2 password hashing
- **User Friendly** — Modern web UI, drag-and-drop upload, intuitive operations
- **Extensible** — Modular design for easy secondary development

### Technology Choices

| Component | Choice | Reason |
|-----------|--------|--------|
| HTTP Server | `http.server` | Standard library, zero dependencies |
| Database | `sqlite3` | Standard library, lightweight, no installation |
| Password Hashing | `hashlib.pbkdf2_hmac` | Standard library, secure and reliable |
| File Dedup | `hashlib.sha256` | Standard library, efficient and accurate |

### Roadmap

- [ ] WebSocket real-time notifications
- [ ] Folder batch upload
- [ ] Image EXIF information reading
- [ ] File version management
- [ ] WebDAV protocol support
- [ ] Docker image release
- [ ] Plugin system

---

## 📦 Packaging & Deployment

### Use as a Module

```bash
# Add to Python path
export PYTHONPATH=/path/to/FileDrop:$PYTHONPATH

# Run directly
python -m filedrop serve
```

### Import as a Library

```python
from filedrop.server import FileDropServer
from filedrop.storage import FileStorage

# Initialize storage
storage = FileStorage("./my_files")

# Start server
server = FileDropServer(host="0.0.0.0", port=8080, storage=storage)
server.start()
```

### System Service Deployment (systemd)

```ini
[Unit]
Description=FileDrop File Sharing Server
After=network.target

[Service]
Type=simple
User=filedrop
ExecStart=/usr/bin/python3 -m filedrop serve --host 0.0.0.0 --port 8080 --dir /var/lib/filedrop
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 🤝 Contributing

Community contributions are welcome! Please follow these guidelines:

1. **Fork** this repository
2. Create a feature branch: `git checkout -b feat/amazing-feature`
3. Commit your changes: `git commit -m 'feat: add amazing feature'`
4. Push the branch: `git push origin feat/amazing-feature`
5. Submit a **Pull Request**

### Commit Convention

Follow the Angular commit convention:
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation update
- `refactor:` Code refactoring
- `test:` Test related
- `chore:` Build/tooling changes

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/gitstq">gitstq</a>
</p>
