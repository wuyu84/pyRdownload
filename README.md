# Python&R 包下载器

> 内网/离线环境下，一键递归下载 Python 和 R 包及其全部依赖，打包后离线安装。

在 **A 电脑纯离线、无互联网** 的环境下，需要安装 Python 或 R 的包及全部依赖时，只需在 B 服务器上部署本下载器，A 电脑打开浏览器即可搜索、下载、打包，拿到离线安装包。

---

## 功能特性

### 核心功能

| # | 功能 | 说明 |
|---|------|------|
| F1 | 包搜索 | 输入包名，搜索 PyPI（Python）或 CRAN/Bioconductor/GitHub 仓库（R） |
| F2 | 版本选择 | 非必填；不填下载最新版，填则按指定版本下载 |
| F3 | 依赖递归解析 | 自动解析直接依赖 → 间接依赖 → 全部依赖，构建完整依赖树（DAG 去重） |
| F4 | 多来源下载 | PyPI、CRAN、Bioconductor、GitHub Releases 及国内镜像；R 语言额外支持从 GitHub 仓库直接下载源码 |
| F5 | 批量下载 | 20 并发下载；R 包需编译时自动附带 Rtools |
| F6 | 打包归档 | 所有包 + 安装脚本（`.bat`）压缩为单个 `.zip`；R 包独立打包为 `.tar.gz`，兼容 RStudio |
| F7 | 一键下载 | 浏览器直接下载打包文件 |
| F8 | 一键安装 | 运行安装脚本自动完成离线安装；未安装运行时时自动引导 |

### 缓存与复用

- **包永久保留**：已下载的包不删除，永久存入本地仓库
- **智能复用**：依赖分析后按「来源 + 包名 + 版本 + 平台」与仓库比对，匹配的直接复用，跳过下载
- **历史任务复用**：搜索历史任务，一键复用（检查完整性后直接打包，秒级完成）

### 辅助功能

- 实时进度条（WebSocket 推送）
- 智能错误提示（中文分析 + 操作建议）
- 镜像源配置（清华、阿里、豆瓣等国内镜像）
- 运行时安装包管理（Python/R/Rtools 预置）
- 仓库统计面板

---

## 技术栈

| 层级 | 选型 |
|------|------|
| 后端 | Python 3.11+ / FastAPI |
| 前端 | Vue 3 + Element Plus + Vite (TypeScript) |
| 依赖解析 | pipdeptree / CRAN API / GitHub REST API |
| 下载引擎 | httpx 异步 HTTP（20 并发） |
| 实时通信 | WebSocket |
| 数据存储 | SQLite（零运维） |
| 包格式 | `.whl` / `.tar.gz` / `.zip` |

---

## 安装部署

### 环境要求

- **操作系统**：Ubuntu 20.04+ / Debian 11+ / 任何 Linux 发行版
- **Python**：3.10 及以上
- **Node.js**：18 及以上（仅构建前端时需要）
- **磁盘空间**：取决于下载的包数量，建议 50G+

### 快速安装

```bash
# 1. 克隆仓库
git clone https://github.com/wuyu84/pyRdownload.git
cd pyRdownload

# 2. 安装后端依赖
pip install -r backend/requirements.txt

# 3. 构建前端
cd frontend
npm install
npm run build
cd ..

# 4. 创建仓库目录
sudo mkdir -p /var/lib/pkgdl/repository/{python,r,runtimes,exports}
sudo chown -R $(whoami) /var/lib/pkgdl

# 5. 启动服务
python3 -m backend.main
```

启动后访问 **http://服务器IP:3579** 即可使用。

### 使用 systemd 自启动（推荐）

创建服务文件 `/etc/systemd/system/pkg-downloader.service`：

```ini
[Unit]
Description=Python&R包下载器
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/pyRdownload
ExecStart=/usr/bin/python3 -m backend.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable pkg-downloader.service
sudo systemctl start pkg-downloader.service
```

| 命令 | 说明 |
|------|------|
| `systemctl status pkg-downloader` | 查看状态 |
| `systemctl restart pkg-downloader` | 重启 |
| `systemctl stop pkg-downloader` | 停止 |
| `journalctl -u pkg-downloader -f` | 查看实时日志 |

### Docker 部署（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/wuyu84/pyRdownload.git
cd pyRdownload

# 2. 构建并启动
docker compose up -d

# 访问 http://服务器IP:3579
```

**环境变量**：通过 `.env` 文件或 `docker compose run -e` 传入：

```bash
# .env 文件（可选）
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

**数据持久化**：包仓库存储在 Docker 命名卷 `pkgdl_data` 中，重建容器数据不丢失。

**常用命令**：

| 命令 | 说明 |
|------|------|
| `docker compose up -d` | 后台启动 |
| `docker compose down` | 停止 |
| `docker compose logs -f` | 查看日志 |
| `docker compose build --no-cache` | 重新构建（清除缓存） |
| `docker compose exec pkg-downloader bash` | 进入容器 |

### 手动部署

---

## 使用指南

### 搜索包

1. 打开浏览器访问 `http://服务器IP:3579`
2. 选择语言（Python 包 / R 包）
3. 输入包名，选择来源，点击搜索
4. 从搜索结果中选择需要的包

### 下载包

1. 选中一个搜索结果
2. 可选：选择具体版本
3. 可选：配置目标平台和目标 Python/R 版本
4. 可选：选择镜像源加速
5. 可选：勾选「打包时附带运行时」
6. 点击「开始下载」
7. 等待进度完成，下载打包的 `.zip` 文件

### 在离线电脑上安装

下载后，将 `.zip` 文件传输到离线电脑并解压：

**Python 包**：双击运行 `install_python.bat`

**R 包**：双击运行 `install_r.bat`

安装脚本会自动检测运行时环境、校验文件完整性、执行安装。

---

## API 概述

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/search` | 搜索包 |
| GET | `/api/package/{lang}/{name}` | 包详情 + 版本列表 |
| POST | `/api/download` | 触发下载任务 |
| WS | `/ws/download/{task_id}` | WebSocket 实时进度 |
| GET | `/api/download/{task_id}/status` | 任务状态 |
| GET | `/api/download/{task_id}/export` | 下载打包文件 |
| GET | `/api/tasks` | 任务一览表 |
| POST | `/api/tasks/{task_id}/reuse` | 一键复用 |
| DELETE | `/api/tasks/{task_id}` | 删除任务 |
| GET | `/api/repository/stats` | 仓库统计 |
| GET | `/api/runtimes` | 可用运行时列表 |
| POST | `/api/runtimes/sync` | 同步运行时版本 |
| GET | `/api/health` | 健康检查 |

---

## 配置

所有配置项通过环境变量设定，默认值位于 `backend/config.py`：

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `SERVER_PORT` | `3579` | 服务端口 |
| `HOST` | `0.0.0.0` | 监听地址 |
| `REPOSITORY_DIR` | `/var/lib/pkgdl/repository` | 包仓库路径 |
| `MAX_CONCURRENT_DOWNLOADS` | `20` | 最大并发下载数 |
| `DOWNLOAD_TIMEOUT` | `120` | 下载超时（秒） |
| `GITHUB_TOKEN` | `""` | GitHub API 令牌（提升限速至 5000次/小时） |
| `PIP_INDEX_URL` | `https://pypi.tuna.tsinghua.edu.cn/simple` | PyPI 镜像源 |
| `CRAN_MIRROR` | `https://mirrors.tuna.tsinghua.edu.cn/CRAN` | CRAN 镜像源 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

---

## 系统架构

### 包仓库目录结构

```
/var/lib/pkgdl/repository/
├── python/          # Python wheel 文件，永久保留
├── r/               # R 包文件（.tar.gz），永久保留
├── runtimes/        # Python/R 运行时安装包
└── index.db         # SQLite 索引库
```

### 下载流程

```
输入包名 → 多来源搜索 → 依赖解析 → DAG 去重
→ 仓库比对（按来源+包名+版本+平台） → 仅下载缺失包
→ 写入仓库 + 更新索引 → 生成 install.bat → 可选附运行时 → 打包为 .zip
```

### 三层加速架构

| 层级 | 策略 | 效果 |
|------|------|------|
| 第一层 | SQLite 持久化缓存 | 命中后零网络请求，秒级响应 |
| 第二层 | 国内镜像 JSON API 优先 | 搜索从 40s 降至 0.5s（83×） |
| 第三层 | 镜像 Simple API 获取 CDN 链接 | 下载从数分钟降至 5s |

> 任意单层失效时自动回退到下一层，确保服务不中断。

---

## 已知限制

| # | 限制 | 应对 |
|---|------|------|
| 1 | R 包无 Windows binary 时需 Rtools 编译 | 下载器自动下载 Rtools 一并打包 |
| 2 | 仓库永久保留占用磁盘空间 | 管理员可通过统计页面手动清理 |
| 3 | 部分 Python 包依赖系统级库 | 安装脚本提示系统依赖 |
| 4 | GitHub API 未认证限速 60次/小时 | 配置 `GITHUB_TOKEN` 提升至 5000次/小时 |
| 5 | 运行时安装包体积较大 | 按需下载，不强制包含 |

---

## 开发

```bash
# 后端热重载开发
cd backend
uvicorn backend.main:app --reload --port 3579

# 前端开发
cd frontend
npm run dev
```

### 项目结构

```
├── backend/
│   ├── main.py               # FastAPI 入口
│   ├── config.py              # 配置
│   ├── database.py            # SQLite 数据库
│   ├── requirements.txt       # Python 依赖
│   ├── models/
│   │   └── schemas.py         # Pydantic 数据模型
│   ├── routers/
│   │   ├── search.py          # 搜索 API
│   │   ├── download.py        # 下载 API + WebSocket
│   │   ├── tasks.py           # 任务管理 API
│   │   ├── repository.py      # 仓库统计 API
│   │   └── runtimes.py        # 运行时管理 API
│   └── services/
│       ├── python_resolver.py  # Python 依赖解析
│       ├── r_resolver.py       # R 依赖解析
│       ├── github_resolver.py  # GitHub 搜索
│       ├── source_selector.py  # 源选择引擎
│       ├── downloader.py       # 下载管理器
│       ├── packager.py         # 打包 + 生成 .bat
│       ├── package_index.py    # 包索引引擎
│       ├── task_manager.py     # 任务管理器
│       └── api_cache.py        # API 响应缓存
├── frontend/
│   └── src/
│       ├── views/              # 页面
│       ├── components/         # 组件
│       └── api/                # API 请求封装
└── logs/
    └── pkg-downloader.log      # 运行日志
```

---

## License

MIT
