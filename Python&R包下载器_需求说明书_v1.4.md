# Python&R包下载器 · 项目书

> 版本：v1.4 | 日期：2026-05-16 | 状态：待确认

---

## 一、项目概述

**软件名称**：Python&R包下载器（简称「下载器」）

**核心价值**：在内网/离线/受限网络环境中，用户只需在A电脑浏览器中访问部署在B服务器上的下载器，输入包名，即可自动递归下载该包及其全部依赖，打包后一键下载并安装在A电脑上。

**部署环境**：Ubuntu Server（B服务器），通过 Web 界面供 A 电脑浏览器访问。

**关键约束**：
- A电脑为纯离线/受限环境，无法直接连接互联网
- A电脑可能为**白板电脑**（未安装 Python、R 等运行时），下载器需一并提供对应语言的安装包
- A电脑的目标平台为 **Windows**，所有下载的包须为 Windows 兼容格式
- 所有依赖（含 Rtools 等工具）必须由下载器一并提供

---

## 二、功能需求

### 2.1 核心功能

| # | 功能 | 说明 |
|---|------|------|
| F1 | 包搜索 | 输入包名，搜索 PyPI（Python）或 CRAN/Bioconductor（R），返回匹配结果及版本信息 |
| F2 | **包版本选择** | 版本号为**非必填**，不输入则默认下载最新版，输入则按指定版本下载 |
| F3 | 依赖递归解析 | 自动解析目标包的**直接依赖→间接依赖→全部依赖**，构建完整依赖树 |
| F4 | 批量下载 | 从选中源/镜像源下载所有依赖包；若R包需编译源码，自动下载 Rtools 安装包一并打包 |
| F5 | 打包归档 | 将所有下载的包+安装脚本+（可选）Python/R 运行时安装包，压缩为单个 `.zip` 文件（Windows 友好） |
| F6 | 一键下载 | 用户从浏览器下载打包文件到 A 电脑 |
| F7 | 一键安装 | 提供安装脚本，在 A 电脑上执行即可离线安装全部包及依赖；若 Python/R 未安装，脚本自动引导安装 |

### 2.2 缓存与复用功能（核心）

| # | 功能 | 说明 |
|---|------|------|
| F8 | **包永久保留** | 已完成任务下载的包**不删除**，永久保存在服务器本地仓库中 |
| F9 | **包索引** | 对仓库中所有包建立索引（包名、版本、语言、平台、文件路径、SHA256），支持快速检索 |
| F10 | **智能比对复用** | 新任务分析完依赖后，与仓库已有包按「包名+版本+平台」比对，匹配的**直接复用，跳过下载** |
| F11 | **历史任务检索** | 用户可搜索历史任务（按包名/版本/语言），发现相同任务后**一键复用**，直接下载到本地安装 |

### 2.3 辅助功能

| # | 功能 | 说明 |
|---|------|------|
| F12 | 包信息展示 | 显示包名、版本、大小、依赖数、描述等 |
| F13 | **任务进度条** | 整体进度条+每个包的独立状态，实时更新；复用的包标记「📦复用」 |
| F14 | **智能错误提示** | 任务失败时自动分析原因，翻译为用户可读懂的中文提示和建议操作 |
| F15 | 版本选择 | 目标平台固定为 **Windows**，可选 Python/R 版本 |
| F16 | 源镜像配置 | 支持配置国内镜像源（清华、阿里等），加速下载 |
| F17 | **任务一览表** | 保存所有任务清单，记录任务信息及**用户登录IP地址** |

### 2.4 新增功能

| # | 功能 | 说明 |
|---|------|------|
| F18 | **运行时下载** | B 服务器预置 Python（Windows exe 安装包）和 R（Windows exe 安装包）及 Rtools，用户可单独下载，或在打包时一并包含 |
| F19 | **多来源搜索** | 支持搜索 **PyPI 官方源**、**CRAN 官方源**、**GitHub Releases** 等多个来源的包，搜索结果显示包来源标签，用户可选择来源下载，默认优选官方源 |
| F20 | **智能环境检测** | 安装脚本自动检测 A 电脑是否已安装 Python/R，未安装时提示并提供运行时安装引导 |

---

## 三、缓存与复用设计（核心模块）

### 3.1 包仓库架构

```
服务器本地仓库: /var/lib/pkgdl/repository/
├── python/
│   ├── numpy-2.1.0-cp311-win_amd64.whl        # 原始包文件，永久保留
│   ├── numpy-2.1.0-cp312-win_amd64.whl
│   ├── pandas-3.2.1-cp311-win_amd64.whl
│   ├── six-1.16.0-py2.py3-none-any.whl
│   └── ...
├── r/
│   ├── ggplot2_3.5.0.zip                       # R Windows binary
│   ├── dplyr_1.1.4.zip
│   ├── rtools43.exe                            # Rtools 安装包
│   └── ...
├── runtimes/                                    # 运行时安装包（预置+自动更新）
│   ├── python-3.11.9-amd64.exe
│   ├── python-3.12.3-amd64.exe
│   ├── R-4.3.3-win.exe
│   └── rtools43.exe
└── index.db                                    # SQLite 索引数据库
```

### 3.2 包索引数据库设计

```sql
-- 包文件索引表
CREATE TABLE package_index (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,           -- 包名 (如 numpy)
    version     TEXT NOT NULL,           -- 版本 (如 2.1.0)
    lang        TEXT NOT NULL,           -- 语言: python / r
    platform    TEXT NOT NULL,           -- 平台: win_amd64 / none_any / win_binary / source
    python_ver  TEXT,                    -- Python版本要求 (如 cp311)
    source      TEXT NOT NULL DEFAULT 'pypi',  -- 包来源: pypi / cran / github / bioconductor
    source_url  TEXT,                    -- 原始下载URL / GitHub仓库URL
    filename    TEXT NOT NULL,           -- 文件名
    filepath    TEXT NOT NULL,           -- 仓库中完整路径
    file_size   INTEGER,                -- 文件大小(字节)
    sha256      TEXT,                    -- 文件哈希，用于完整性校验
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, version, lang, platform, python_ver, source)  -- 去重（含来源）
);

-- 运行时索引表（Python/R 安装包）
CREATE TABLE runtime_index (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lang        TEXT NOT NULL,           -- python / r
    version     TEXT NOT NULL,           -- 版本号 (如 3.11.9)
    arch        TEXT NOT NULL DEFAULT 'amd64', -- 架构
    filename    TEXT NOT NULL,           -- 文件名
    filepath    TEXT NOT NULL,           -- 仓库中完整路径
    file_size   INTEGER,                -- 文件大小
    sha256      TEXT,                    -- 文件哈希
    download_url TEXT,                   -- 官方下载地址
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(lang, version, arch)
);

-- 任务表
CREATE TABLE tasks (
    id          TEXT PRIMARY KEY,        -- 任务ID (如 T001)
    lang        TEXT NOT NULL,           -- python / r
    package_name TEXT NOT NULL,          -- 主包名
    package_version TEXT,                -- 主包版本 (NULL=最新)
    python_ver  TEXT,                    -- 目标Python版本
    r_ver       TEXT,                    -- 目标R版本
    status      TEXT NOT NULL,           -- pending/downloading/packaging/done/failed
    total_pkgs  INTEGER DEFAULT 0,      -- 总包数
    cached_pkgs INTEGER DEFAULT 0,      -- 复用包数
    downloaded_pkgs INTEGER DEFAULT 0,  -- 新下载包数
    failed_pkgs INTEGER DEFAULT 0,      -- 失败包数
    file_size   INTEGER DEFAULT 0,      -- 打包文件大小
    export_path TEXT,                    -- 打包文件路径
    client_ip   TEXT NOT NULL,           -- 用户IP地址
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME
);

-- 任务-包关联表（一个任务包含多个包）
CREATE TABLE task_packages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL REFERENCES tasks(id),
    pkg_name    TEXT NOT NULL,
    pkg_version TEXT NOT NULL,
    lang        TEXT NOT NULL,
    status      TEXT NOT NULL,           -- cached/downloaded/failed
    is_cached   BOOLEAN DEFAULT 0,      -- 是否从仓库复用
    error_msg   TEXT,                    -- 失败时的原始错误
    friendly_error TEXT,                 -- 智能中文提示
    file_path   TEXT,                    -- 包文件路径
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);

-- 索引
CREATE INDEX idx_pkg_name ON package_index(name);
CREATE INDEX idx_pkg_name_ver ON package_index(name, version);
CREATE INDEX idx_pkg_lang ON package_index(lang);
CREATE INDEX idx_task_status ON tasks(status);
CREATE INDEX idx_task_pkg ON tasks(package_name);
CREATE INDEX idx_task_ip ON tasks(client_ip);
```

### 3.3 智能比对复用流程（含多来源）

```
用户请求下载 pandas 3.2.1 (Python, cp311, 来源: PyPI)
    │
    ▼
Step 1: 依赖解析 → 得到完整依赖列表（标记每个包的来源）
  [pandas 3.2.1(pypi), numpy 2.1.0(pypi), python-dateutil 2.9.0(pypi),
   six 1.16.0(pypi), pytz 2024.1(pypi), tzdata 2024.1(pypi)]
    │
    ▼
Step 2: 逐个与 package_index 比对（**按来源+包名+版本+平台**）
  pandas 3.2.1 pypi cp311 win_amd64  → ✅ 命中！从仓库复用
  numpy 2.1.0 pypi cp311 win_amd64   → ✅ 命中！从仓库复用
  python-dateutil 2.9.0 pypi none    → ✅ 命中！从仓库复用
  six 1.16.0 pypi none               → ✅ 命中！从仓库复用
  pytz 2024.1 pypi none              → ❌ 仓库无此版本，需下载
  tzdata 2024.1 pypi none            → ❌ 仓库无此版本，需下载
    │
    ▼
Step 3: 仅下载缺失的 2 个包（20并发）
    │
    ▼
Step 4: 新下载的包写入仓库 + 更新索引（含 source 字段）
    │
    ▼
Step 5: 从仓库复用 + 新下载的包一起打包

结果：6个包中4个复用，仅下载2个，大幅提速！
```

### 3.4 前端复用展示

```
┌──────────────────────────────────────────────────┐
│ 📥 下载任务: pandas 3.2.1  (来源: PyPI)           │
│                                                   │
│ 总进度: [████████████████████] 100% (6/6)         │
│                                                   │
│ 📦 pandas-3.2.1        仓库复用  [PyPI官方]        │
│ 📦 numpy-2.1.0         仓库复用  [PyPI官方]        │
│ 📦 python-dateutil-2.9 仓库复用  [PyPI官方]        │
│ 📦 six-1.16.0          仓库复用  [PyPI官方]        │
│ ✅ pytz-2024.1         新下载 45KB [PyPI官方]      │
│ ✅ tzdata-2024.1       新下载 210KB [PyPI官方]     │
│                                                   │
│ 仓库复用: 4/6 | 新下载: 2/6 | 节省: 28.1 MB       │
└──────────────────────────────────────────────────┘
```

### 3.5 历史任务检索与一键复用

```
┌──────────────────────────────────────────────────────────────────────┐
│  📋 任务一览表                                                        │
│──────────────────────────────────────────────────────────────────────│
│  🔍 搜索: [pandas________] [搜索历史任务]                             │
│                                                                      │
│  [ 全部 ] [ Python ] [ R ]  [ 进行中 ] [ 已完成 ] [ 失败 ]           │
│                                                                      │
│  ┌──────┬──────────┬─────────┬──────┬────────┬─────────┬──────────┬──────────┬────────┐
│  │ 任务ID│ 包名      │ 版本     │ 语言  │ 包总数  │ 复用率   │ 来源IP    │ 时间      │ 操作   │
│  ├──────┼──────────┼─────────┼──────┼────────┼─────────┼──────────┼──────────┼────────┤
│  │ T001  │ pandas   │ 2.1.0   │ Py   │ 12     │ 4/12    │ 192.168.1.100 │ 05-16 09:15 │ [复用] │
│  │ T002  │ ggplot2  │ 最新    │ R    │ 28     │ 0/28    │ 192.168.1.100 │ 05-16 09:20 │ [复用] │
│  │ T003  │ pandas   │ 2.1.0   │ Py   │ 12     │ 12/12   │ 10.0.0.55     │ 05-16 09:25 │ [复用] │
│  └──────┴──────────┴─────────┴──────┴────────┴─────────┴──────────┴──────────┴────────┘
│                                                                      │
│  💡 T003 全部从仓库复用，可直接下载！                                   │
│                                                                      │
│  点击 [复用] → 检查仓库中包文件完整性 → 直接打包 → 下载                  │
└──────────────────────────────────────────────────────────────────────┘
```

**一键复用流程**：
```
用户点击 [复用]
    │
    ▼
系统检查该任务所有包是否仍在仓库中
    │
    ├── 全部存在 → 直接打包 → 提供下载链接（秒级完成）
    │
    └── 部分缺失 → 提示 "3个包已从仓库移除，是否补充下载后打包？"
                    [补充下载并打包] / [仅打包已有包]
```

---

## 四、技术方案

### 4.1 架构设计

```
┌──────────────────────────────────────────────────────┐
│                A 电脑 · Windows（浏览器）               │
│  ┌──────────────────────────────────────────────────┐ │
│  │          Web 前端（Vue 3 + Element Plus）          │ │
│  │ 搜索→选版本→看依赖树→触发下载→看进度→下载→一键安装    │ │
│  │ 搜索历史任务→一键复用→下载到本地                     │ │
│  └──────────────────────────────────────────────────┘ │
└──────────────────────┬───────────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼───────────────────────────────┐
│              B 服务器（Ubuntu）· 端口 3579              │
│  ┌──────────────────────────────────────────────────┐ │
│  │           后端服务（Python FastAPI）                 │ │
│  │                                                    │ │
│  │  ┌──────────┐  ┌───────────┐  ┌───────────────┐  │ │
│  │  │ PyPI 解析 │  │ CRAN 解析  │  │ GitHub 解析器  │  │ │
│  │  └──────────┘  └───────────┘  └───────────────┘  │ │
│  │  ┌──────────┐  ┌───────────┐  ┌───────────────┐  │ │
│  │  │ 下载管理器 │  │ 包索引引擎 │  │  打包 & 安装   │  │ │
│  │  │ (20并发)  │  │ (智能比对) │  │ (Win+Rtools)  │  │ │
│  │  └──────────┘  └───────────┘  └───────────────┘  │ │
│  │  ┌──────────┐  ┌───────────┐  ┌───────────────┐  │ │
│  │  │错误分析器 │  │运行时管理器 │  │ 源选择引擎     │  │ │
│  │  │(智能提示) │  │(预置更新)  │  │(多来源优选)   │  │ │
│  │  └──────────┘  └───────────┘  └───────────────┘  │ │
│  │  ┌───────────────────────────────────────────────┐ │ │
│  │  │                包仓库                          │ │ │
│  │  │  ├── python/   (所有Python包文件)               │ │ │
│  │  │  ├── r/        (所有R包文件+Rtools)             │ │ │
│  │  │  ├── runtimes/ (Python/R 运行时安装包)          │ │ │
│  │  │  └── index.db  (SQLite索引,含来源字段)          │ │ │
│  │  └───────────────────────────────────────────────┘ │ │
└──────────────────────────────────────────────────────┘
```

### 4.2 技术栈

| 层级 | 技术选型 | 理由 |
|------|---------|------|
| **后端** | Python 3.11 + FastAPI | 异步高性能，pip API 生态丰富 |
| **前端** | Vue 3 + Element Plus + Vite | 现代化 SPA，组件丰富，中文友好 |
| **Python 依赖解析** | pip 内部 API + pipdeptree | 利用 pip 自身能力，解析最准确 |
| **R 依赖解析** | CRAN API + tools::package_dependencies() | R 原生依赖解析 |
| **GitHub 解析** | GitHub REST API (Releases) | 搜索 GitHub Releases 中的 Python/R 包，按版本解析依赖 |
| **下载** | httpx（异步 HTTP，20并发） | 高并发下载，性能好 |
| **打包** | Python zipfile | Windows 友好，标准库无额外依赖 |
| **进程通信** | WebSocket（FastAPI 原生支持） | 实时推送下载进度 |
| **数据存储** | SQLite | 包索引+任务数据+运行时索引，零运维 |
| **运行时管理** | 预置脚本（周期检查更新） | Python/R 官方安装包预下载+版本管理 |
| **部署** | Docker + Docker Compose | 一键部署，环境隔离 |

### 4.3 关键流程

#### 流程1：Python 包（来源选择）

```
输入包名 → 搜索 PyPI + GitHub → 用户选择来源（默认 PyPI）
→ 用户选择版本 → pip解析依赖树 → 构建DAG去重
→ 与仓库索引比对(含来源+包名+版本+平台) → 仅下载缺失的包(20并发, Windows wheel)
→ 新包写入仓库+更新索引(含 source 字段) → 生成install_python.bat → 可选附带运行时 → 打包为.zip
```

#### 流程2：R 包（来源选择）

```
输入包名 → 搜索 CRAN + Bioconductor → 用户选择来源（默认 CRAN）
→ 用户选择版本 → CRAN API解析依赖 → 构建DAG去重
→ 与仓库索引比对(含来源+包名+版本+平台) → 仅下载缺失的包(20并发, Windows binary优先)
→ 无binary时下载源码包+自动下载Rtools → 新包写入仓库+更新索引
→ 生成install_r.bat(R CMD INSTALL导入library) → 可选附带运行时 → 打包为.zip
```

#### 流程3：一键复用

```
用户搜索历史任务 → 找到相同任务 → 点击[复用]
→ 系统检查仓库中包文件完整性(SHA256校验)
→ 全部存在: 直接打包(秒级) → 提供下载
→ 部分缺失: 提示补充下载或仅打包已有包
```

---

## 五、前端页面设计

### 5.1 搜索页

```
┌──────────────────────────────────────────────────────┐
│  📦 Python&R包下载器                                   │
│──────────────────────────────────────────────────────│
│  [ Python包 ]  [ R包 ]  [ 任务一览表 ]  ← 顶部Tab     │
│──────────────────────────────────────────────────────│
│  🔍 包名: [________________] (必填)                   │
│  📌 版本: [________________] (选填，默认最新)          │
│  📡 来源: [PyPI官方 ▼]  ▼可选: PyPI/GitHub/CRAN/全部  │
│                                                       │
│                                             [搜索]    │
│                                                       │
│  ┌─────────────────────────────────────────────┐     │
│  │ 搜索结果                                     │     │
│  │  ┌─── 来自 PyPI 官方 ──────────────────────┐ │     │
│  │  │ pandas  最新版: 3.2.1 | 12 依赖 | 15.2MB │ │     │
│  │  │ 📦 仓库已有: numpy, six, pytz (3/12可复用)│ │     │
│  │  └────────────────────────────────────────┘ │     │
│  │  ┌─── 来自 GitHub Releases ────────────────┐ │     │
│  │  │ pandas  最新版: 3.2.1 | 来自 devtools   │ │     │
│  │  │ ⚠ 非官方源，依赖树可能不完整              │ │     │
│  │  └────────────────────────────────────────┘ │     │
│  └─────────────────────────────────────────────┘     │
│                                                       │
│  ┌─────────────────────────────────────────────┐     │
│  │ 📋 依赖树                                     │     │
│  │  pandas 3.2.1  [PyPI]                        │     │
│  │  ├── numpy 2.1.0         📦仓库已有 [PyPI]    │     │
│  │  ├── python-dateutil 2.9 ⬇需下载   [PyPI]   │     │
│  │  │   └── six 1.16.0     📦仓库已有 [PyPI]    │     │
│  │  ├── pytz 2024.1        📦仓库已有 [PyPI]    │     │
│  │  └── tzdata 2024.1      ⬇需下载   [PyPI]    │     │
│  └─────────────────────────────────────────────┘     │
│                                                       │
│  目标平台: Windows   Python版本: [3.11 ▼]             │
│  镜像源: [清华 ▼]  包来源: [PyPI官方 ▼]              │
│                                                       │
│  ☑ 打包时附带 Python 运行时 [python-3.11.9-amd64 ▼]   │
│  ☑ 打包时附带 R 运行时 [R-4.3.3-win ▼]               │
│  ☑ 打包时附带 Rtools [rtools43 ▼]                    │
│                                                       │
│  [ 🚀 开始下载 ]  预计: 需新下载3个, 仓库复用9个      │
│                                                       │
│  ┌─────────────────────────────────────────────┐     │
│  │ 📥 任务进度 (来源: PyPI官方)                   │     │
│  │ 总进度: [████████████░░░░░░] 75% (9/12)      │     │
│  │ 📦 pandas-3.2.1    仓库复用 [PyPI]  15.2MB   │     │
│  │ 📦 numpy-2.1.0     仓库复用 [PyPI]  12.8MB   │     │
│  │ ✅ python-dateutil 新下载 ✅ [PyPI]  340KB    │     │
│  │ 📦 six-1.16.0      仓库复用 [PyPI]  14KB     │     │
│  │ ⏳ pytz-2024.1     下载中 [PyPI] [██░░] 20% │     │
│  │ ⏸ tzdata-2024.1   等待中 [PyPI]              │     │
│  │ 仓库复用: 9/12 | 新下载: 1/12 | 剩余: 8s     │     │
│  └─────────────────────────────────────────────┘     │
│                                                       │
│  [ 📥 下载打包文件 ] pandas_with_deps_py311.zip       │
│  [ ⬇ 单独下载 Python 3.11.9 安装包 ]                 │
│  [ ⬇ 单独下载 R 4.3.3 安装包 ]                      │
└──────────────────────────────────────────────────────┘
```

### 5.2 任务一览表页

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  📋 任务一览表                                                                    │
│──────────────────────────────────────────────────────────────────────────────────│
│  🔍 搜索历史任务: [pandas________] [搜索]  (按包名/来源/版本搜索)                  │
│                                                                                  │
│  [ 全部 ] [ Python ] [ R ]  [ 进行中 ] [ 已完成 ] [ 失败 ]                       │
│                                                                                  │
│  ┌──────┬──────────┬─────────┬──────┬────────┬─────────┬──────────┬──────┬──────┬──────┬──────┐
│  │ 任务ID│ 包名      │ 来源     │ 版本  │ 语言   │ 包总数  │ 复用率   │ 来源IP  │ 时间  │ 状态 │ 操作  │
│  ├──────┼──────────┼─────────┼──────┼────────┼─────────┼──────────┼──────┼──────┼──────┼──────┤
│  │ T001  │ pandas   │ PyPI    │ 2.1.0│ Py     │ 12     │ 4/12     │ 192.168.│ 09:15│ ✅完 │[复用]│
│  │ T002  │ ggplot2  │ CRAN    │ 最新 │ R      │ 28     │ 0/28     │ 192.168.│ 09:20│ ✅完 │[复用]│
│  │ T003  │ pandas   │ GitHub  │ 2.1.0│ Py     │ 12     │ 12/12    │ 10.0.0.│ 09:25│ ✅完 │[复用]│
│  │ T004  │ requests │ PyPI    │ 2.31.│ Py     │ 5      │ 3/5      │ 10.0.0.│ 09:30│ ⏳下 │  --   │
│  └──────┴──────────┴─────────┴──────┴────────┴─────────┴──────────┴──────┴──────┴──────┴──────┘
│                                                                                  │
│  💡 T003 复用率100%，所有包均从仓库获取，点击[复用]可秒级打包下载                   │
│                                                                                  │
│  仓库统计: Python包 256个 | R包 183个 | 运行时效中: 3 | 总占用 4.2 GB             │
│  [ ⚙ 管理运行时效中 → 检查更新 / 下载新版本 ]                                     │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 六、API 设计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/search` | 搜索包 `?q=pandas&lang=python&source=pypi` （source可选：pypi/cran/github/all） |
| GET | `/api/package/{lang}/{name}` | 包详情+版本列表+仓库已有标记 `?source=pypi` |
| GET | `/api/package/{lang}/{name}/versions` | 历史版本列表（含来源标注） |
| POST | `/api/download` | 触发下载 `{lang, packages:[{name,version?}], source, python_version/r_version, include_runtime}` |
| WS | `/ws/download/{task_id}` | WebSocket 实时进度 |
| GET | `/api/download/{task_id}/status` | 任务状态 |
| GET | `/api/download/{task_id}/export` | 下载打包文件 |
| GET | `/api/tasks` | 任务一览表（含来源、IP、版本、复用率、状态） |
| GET | `/api/tasks/{task_id}` | 任务详情（含每包状态：来源、复用/新下载/失败） |
| GET | `/api/tasks/search` | 搜索历史任务 `?q=pandas&source=pypi&lang=python` |
| POST | `/api/tasks/{task_id}/reuse` | 一键复用：检查完整性→打包→返回下载链接 |
| DELETE | `/api/tasks/{task_id}` | 删除任务记录（不删仓库包文件） |
| GET | `/api/repository/stats` | 仓库统计（包数量、运行时效中数量、占用空间等） |
| GET | `/api/config/mirrors` | 镜像源列表 |
| **新增** | | |
| GET | `/api/runtimes` | 获取可用运行时列表（Python/R 各版本及下载链接） |
| GET | `/api/runtimes/download/{type}/{version}` | 下载运行时安装包（python/R/rtools） |
| POST | `/api/runtimes/sync` | 管理员手动触发运行时版本检查更新 |
| POST | `/api/github/search` | 搜索 GitHub Releases `{q:pandas, lang:python}` |

---

## 七、智能错误提示设计

### 错误分析器

```
原始错误 → 自动分析 → 中文提示 + 建议操作

404         → 包不存在或版本号有误，请检查名称/版本
Timeout     → 网络连接超时，请检查镜像源或稍后重试
SSL Error   → 安全连接失败，请检查网络环境
RateLimit   → GitHub API 请求频率超限，请稍后重试
NoWinWheel  → 该包没有 Windows 版本，无法安装
Conflict    → 依赖版本冲突，建议使用最新版本
HashMismatch→ 文件校验失败，可能下载不完整，请重试
DiskFull    → 服务器磁盘空间不足，请联系管理员
GitHubSrcErr→ GitHub 来源的包可能依赖树不完整，建议切换为官方源
RuntimeNotFound → 运行时安装包未预置，请联系管理员预下载
```

前端：失败包 ❌ + 中文原因 + 建议操作 + 技术详情（可折叠）

---

## 八、安装脚本设计

### Python `install_python.bat`
```bat
@echo off
chcp 65001 >nul
:: ============================================
:: Python 包离线安装脚本
:: ============================================

:: 1. 检测 Python 是否已安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] 未检测到 Python，请先安装 Python 运行时！
    echo 安装包位于本目录下的 runtime\ 文件夹中
    echo 请手动运行: runtime\python-3.11.9-amd64.exe
    echo 安装完成后重新运行此脚本
    pause
    exit /b 1
)

:: 2. 检测 Python 版本兼容性
python -c "import sys; ver=sys.version_info; exit(0 if ver.major==3 and ver.minor>=8 else 1)"
if %errorlevel% neq 0 (
    echo [WARNING] Python 版本过低（需要 ≥ 3.8），请升级后重试
    pause
    exit /b 1
)

:: 3. 校验包文件完整性
echo 正在校验包文件...
python -c "import hashlib, json; f=open('./packages/checksums.json'); d=json.load(f); ok=True\nfor fn,sha in d.items(): h=hashlib.sha256(open(f'./packages/{fn}','rb').read()).hexdigest(); print(f'  {fn}: {"✅" if h==sha else "❌"}'); ok=ok and (h==sha)\nexit(0 if ok else 1)"
if %errorlevel% neq 0 (
    echo [ERROR] 文件校验失败，部分包可能不完整，请重新下载
    pause
    exit /b 1
)

:: 4. 离线安装
pip install --no-index --find-links=./packages <pkg1> <pkg2> ...
if %errorlevel% equ 0 (
    echo ✅ 全部安装成功！
) else (
    echo ❌ 部分包安装失败，请检查错误信息后重试
)

:: 5. 验证安装
python -c "import <pkg1>; print('<pkg1> 安装成功!')"
pause
```

### R `install_r.bat`
```bat
@echo off
chcp 65001 >nul
:: ============================================
:: R 包离线安装脚本
:: ============================================

:: 1. 检测 R 是否已安装
Rscript --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] 未检测到 R，请先安装 R 运行时！
    echo 安装包位于本目录下的 runtime\ 文件夹中
    echo 请手动运行: runtime\R-4.3.3-win.exe
    echo 安装完成后重新运行此脚本
    pause
    exit /b 1
)

:: 2. 获取 R library 路径
for /f "tokens=*" %%i in ('Rscript -e "cat(.libPaths()[1])"') do set R_LIB=%%i

:: 3. 如果包含 rtools/ → 先静默安装 Rtools
if exist .\packages\rtools*.exe (
    echo 检测到 Rtools 安装包，正在静默安装...
    .\packages\rtools*.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
    if %errorlevel% neq 0 (
        echo [WARNING] Rtools 安装失败，请手动安装
    ) else (
        echo ✅ Rtools 安装成功
    )
)

:: 4. 按拓扑序安装
echo 正在安装 R 包...
:: binary 包
R CMD INSTALL --library="%R_LIB%" .\packages\pkg1.zip .\packages\pkg2.zip
:: 源码包（如需编译）
R CMD INSTALL --library="%R_LIB%" .\packages\pkg3.tar.gz

:: 5. 验证安装
Rscript -e "library(pkg1); cat('✅ pkg1 安装成功!')"
if %errorlevel% equ 0 (
    echo ✅ 全部安装成功！
) else (
    echo ❌ 部分包安装失败，请检查错误信息后重试
)
pause
```

---

## 九、目录结构

```
pkg-downloader/
├── docker-compose.yml
├── Dockerfile
├── README.md
├── backend/
│   ├── main.py                  # FastAPI 入口
│   ├── requirements.txt
│   ├── config.py                # 配置（端口3579、20并发、源默认策略、GitHub Token等）
│   ├── database.py              # SQLite 数据库（索引表+任务表+运行时表）
│   ├── routers/
│   │   ├── search.py            # 搜索 API（多来源搜索）
│   │   ├── download.py          # 下载 API + WebSocket
│   │   ├── tasks.py             # 任务一览表 + 搜索 + 一键复用
│   │   ├── repository.py        # 仓库统计 API
│   │   └── runtimes.py          # 运行时管理 API（Python/R 安装包下载）
│   ├── services/
│   │   ├── python_resolver.py   # Python 依赖解析（版本+仅 Windows wheel）
│   │   ├── r_resolver.py        # R 依赖解析（版本+优先 Windows binary）
│   │   ├── github_resolver.py   # GitHub Releases 搜索与下载
│   │   ├── source_selector.py   # 源选择引擎（多来源优选+来源标签管理）
│   │   ├── downloader.py        # 下载管理（20并发 + 进度追踪）
│   │   ├── package_index.py     # 包索引引擎（比对+复用+SHA256校验，含source字段）
│   │   ├── packager.py          # 打包 + 生成 .bat + 可选附带运行时
│   │   ├── runtime_manager.py   # 运行时管理器（Python/R 安装包预置+版本检查更新）
│   │   ├── rtools_downloader.py # Rtools 下载（源码包需编译时自动触发）
│   │   ├── task_manager.py      # 任务管理（含IP记录+来源记录）
│   │   └── error_analyzer.py    # 错误分析器（智能中文提示，含GitHub相关错误）
│   └── models/
│       └── schemas.py           # Pydantic 数据模型
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── src/
│   │   ├── App.vue
│   │   ├── views/
│   │   │   ├── SearchView.vue
│   │   │   └── TaskView.vue
│   │   ├── components/
│   │   │   ├── PackageCard.vue
│   │   │   ├── DepTree.vue
│   │   │   ├── DownloadPanel.vue
│   │   │   ├── ErrorAlert.vue
│   │   │   └── VersionSelect.vue
│   │   └── api/
│   │       └── index.ts
│   └── dist/
└── scripts/
    ├── install_python.bat.tpl
    ├── install_r.bat.tpl
    └── install_rtools.bat.tpl
```

---

## 十、部署方案

```bash
git clone <repo> && cd pkg-downloader
docker compose up -d
# 访问 http://<B服务器IP>:3579
```

> **运行时预置说明**：首次启动后，管理员需通过管理界面或手动下载 Python/R 官方安装包放入 `./repository/runtimes/` 目录，或触发 `/api/runtimes/sync` 自动检查更新。

```yaml
services:
  pkg-downloader:
    build: .
    ports:
      - "3579:3579"
    volumes:
      - ./repository:/var/lib/pkgdl/repository  # 包仓库+索引+运行时效中化（永久保留）
    environment:
      - SERVER_PORT=3579
      - MAX_CONCURRENT_DOWNLOADS=20
      - DEFAULT_SOURCE=pypi                     # 默认包来源: pypi/cran/github
      - PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
      - CRAN_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/CRAN
      - RTOOLS_URL=https://cran.r-project.org/bin/windows/Rtools/rtools43.exe
      - GITHUB_TOKEN=                           # (可选) GitHub API Token，提升频率限制
      - RUNTIME_AUTO_SYNC=true                  # 是否定期自动检查运行时版本更新
```

---

## 十一、已知限制与风险

| # | 限制 | 应对策略 |
|---|------|---------|
| 1 | R 包无 Windows binary 需 Rtools 编译 | 下载器自动下载 Rtools 一并打包，脚本静默安装后再编译 |
| 2 | 仓库永久保留占用磁盘空间 | 提供仓库统计页面，管理员可手动清理；默认不自动删除 |
| 3 | 部分 Python 包依赖系统级库 | 安装脚本列出系统依赖提示 |
| 4 | 大型依赖树下载耗时 | 20并发+仓库复用+进度条，复用后大幅减少下载量 |
| 5 | 旧版本包可能从镜像源移除 | 智能错误提示引导检查版本或使用最新版；仓库中已有的旧版本可直接复用 |
| 6 | A 电脑纯离线 | 所有依赖（含Rtools）由下载器一并提供 |
| 7 | 私有包不在公开源 | v1.0 仅支持公开源，v2.0 扩展 |
| 8 | GitHub 来源包的依赖树通常不完整 | 前端标注"非官方源，依赖树可能不完整"警告；默认优选官方源 |
| 9 | GitHub API 有频率限制（未认证60次/小时） | 支持配置 GITHUB_TOKEN 提升至 5000次/小时 |
| 10 | 运行时安装包体积较大（Python ~30MB, R ~100MB+） | 按需下载，不强制包含在打包文件中；首次部署需管理员预置 |
| 11 | PyPI 官方 JSON API 响应慢（大型包如 scikit-learn 超 40s），下载链接指向 files.pythonhosted.org（国外 CDN 慢） | ① **SQLite 持久化缓存**：包元数据 1h，版本列表 30min，搜索 10min；② **多镜像源 Simple API 加速**：通过清华/阿里/豆瓣/官方镜像的 `/simple/{name}/` 接口获取 wheel 下载链接，链接直接指向镜像 CDN（速度快 10 倍以上）；③ **多镜像容错**：4 个镜像按优先级依次尝试，全部失败才回退官方 PyPI JSON API |

---

## 十二、开发计划

| 阶段 | 内容 | 预估工时 |
|------|------|---------|
| **P1 - 基础骨架** | 项目搭建+FastAPI+Vue+Docker+SQLite索引表 | 0.5天 |
| **P2 - Python核心** | 搜索+版本+依赖解析+仓库比对复用+多来源(含GitHub)+Windows wheel下载+打包+.bat | 2.5天 |
| **P3 - R核心** | 搜索+版本+依赖解析+仓库比对复用+Windows binary下载+Rtools+打包+.bat | 2天 |
| **P4 - 仓库索引引擎** | 包索引+SHA256校验+智能比对(含source字段)+永久保留+统计 | 1天 |
| **P5 - 历史任务复用** | 任务搜索+一键复用+完整性检查+秒级打包 | 0.5天 |
| **P6 - 运行时管理** | 运行时预置下载+版本检查更新+API+前端管理入口 | 1天 |
| **P7 - 进度与错误** | WebSocket进度条+来源标记+错误分析器+智能提示 | 0.5天 |
| **P8 - 前端完善** | 搜索页(含来源选择)+任务页(含来源列)+依赖树(来源标记)+运行时管理+仓库统计 | 1.5天 |
| **P9 - 测试优化** | 端到端测试+错误处理+文档 | 1天 |

---

## 十三、已确认配置总览

| # | 配置项 | 值 |
|---|--------|-----|
| 1 | 服务端口 | **3579** |
| 2 | 目标平台 | **Windows**（仅下载 Windows 兼容包） |
| 3 | 并发下载数 | **20** |
| 4 | 包仓库策略 | **永久保留**，建立索引，支持比对复用 |
| 5 | 缓存清理 |  **不再自动清理**，管理员可手动清理 |
| 6 | 任务一览表 | 含**用户IP**+**复用率**+**一键复用** |
| 7 | 历史任务检索 | 按包名/版本搜索，一键复用下载 |
| 8 | 安装脚本 | **.bat**，Python用pip，R用R CMD INSTALL导入library |
| 9 | 打包格式 | **.zip**（Windows 友好） |
| 10 | 包版本选择 | **非必填**，默认最新，指定版本按指定版下载 |
| 11 | 进度条 | **WebSocket实时**，总进度+每包状态+复用/新下载标记+来源标记 |
| 12 | 错误提示 | **智能分析**，中文提示+建议操作（含GitHub源相关提示） |
| 13 | Rtools | 需编译源码时**自动下载一并打包**，脚本静默安装 |
| 14 | 离线环境 | A电脑无互联网，所有依赖由下载器一并提供 |
| 15 | **包来源** | **默认 PyPI/CRAN 官方源**，可选 **GitHub Releases**，结果标注来源标签 |
| 16 | **运行时下载** | **Python/R 运行时安装包** 由管理员预置，可单独下载或随包打包 |
| 18 | **PyPI API 缓存** | 包元数据 1h，版本列表 30min，搜索 10min，GitHub 搜索 5min |

---

## 十五、开发过程经验总结

### 15.1 R 包依赖解析：CRAN API 字段类型不兼容

**问题**：`crandb.r-pkg.org` 的 `Depends`/`Imports`/`LinkingTo` 在某些 R 包中返回 **dict** 格式（如 `{'R': '>= 3.6', 'tibble': '>= 2.0.1'}`），但代码误以为始终是字符串，调用 `.strip()` 方法导致 `AttributeError` 崩溃，回退到 `version = "latest"`，后续在 CRAN 上找不到该版本链接而报错。

**修复**（`r_resolver.py`）：新增 `_parse_dep_list()` 统一处理 dict 和 str 两种格式，逐项提取包名和版本号。

**教训**：外部 API 返回的数据结构应做类型防御性检查，不能假设字段类型固定。

---

### 15.2 R 包下载：CRAN HEAD 请求不稳定

**问题**：`get_windows_binary_url` 使用 `httpx.head()` 检查 URL 存在性，部分 CRAN 镜像对 HEAD 请求响应不稳定（返回 405 或超时），导致误判为 binary 不存在，回退到源码包。

**修复**：改用 `GET + Range: bytes=0-1` 请求只读首字节，兼容性更好；同时改进 binary URL 构造逻辑，优先匹配 R 版本。

**教训**：HEAD 请求在 CDN/镜像站上兼容性差，改用 GET + Range 做存在性检查更可靠。

---

### 15.3 前端运行时下拉框：未按语言过滤

**问题**：搜索 R 包时，"打包时附带运行时" 下拉框仍显示 Python 运行时版本。

**修复**（`SearchView.vue`）：新增 `filteredRuntimes` 计算属性，按 `searchForm.lang` 动态过滤运行时列表，语言切换时联动更新。

**教训**：全局列表必须关联上下文状态，否则用户在切换语言时看到不相关的选项。

---

### 15.4 依赖树组件：加载失败后隐藏

**问题**：`DepTree.vue` 使用 `v-if="deps.length > 0 || loadingDeps"`，当依赖解析 API 调用失败时，`deps` 为空且 `loadingDeps=false`，整个依赖树卡片从界面消失，用户看不到任何错误提示，也无法重试。

**修复**（`DepTree.vue`）：
- 移除 `v-if`，改为始终显示卡片
- 增加三级状态展示：加载中（加载动画）→ 失败（错误信息 + 「重新解析」按钮）→ 成功（表格展示）→ 空（"该包无额外依赖"）
- `catch` 中记录 `loadError` 而非直接清空

**教训**：永远不要在组件内部用 `v-if` 隐式隐藏错误状态，应给用户明确的反馈和操作入口。

---

### 15.5 搜索结果选中反馈：视觉区分不够

**问题**：搜索结果卡片点击选中后，鼠标移开就看不出哪张被选中 — `PackageCard` 的 `.selected` 样式仅有 `border-color` 和浅蓝色背景，在 el-card 的 hover 效果下几乎没有视觉差异。

**修复**（`PackageCard.vue`）：
- 左侧 4px 蓝色实心竖条（`::before` 伪元素）
- 右上角蓝色圆形 ✔ 勾选徽章
- `box-shadow: inset` 边框强化感知
- 所有选中样式独立于 hover，鼠标离开后依然清晰可见

---

### 15.6 依赖解析超时：大型包 PyPI JSON 过大

**问题**：scikit-learn 等大型包的 PyPI JSON 响应超过 900KB，`_fetch_json` 在 40s 内无法下载完整，触发超时异常，依赖树和下载链路均中断。

**修复**（`python_resolver.py`、新增 `api_cache.py`）：
- `_fetch_json` 超时从 40s 提升至 50s，重试从 1 次增至 2 次
- 后端 `get_package_dependencies` 接口超时从 50s 提升至 60s
- **引入 SQLite 持久化缓存层**：API 响应自动缓存到 `api_cache` 表
  - 包元数据：1 小时
  - 版本列表：30 分钟
  - 搜索：10 分钟
  - 缓存命中后零网络请求，秒级响应

**效果**：scikit-learn 首次解析 42s，缓存后 0.0s，后续操作全部瞬时。

---

### 15.7 前端依赖树未传递 Python 版本参数

**问题**：`DepTree.vue` 的 `loadDeps()` 未将 `pythonVer` prop 传给后端 API，后端始终用 `PYTHON_VERSIONS[-1]`（3.13），而前端默认是 3.11，可能导致解析结果不匹配。

**修复**：`api/index.ts` 的 `getPackageDependencies` 新增 `pythonVer` 参数；后端 `get_package_dependencies` 新增 `python_ver` Query 参数，优先使用前端传入的版本。

---

### 15.8 前端版本选择器：R 包显示 Python 选项

**问题**：下载配置区不论搜索什么语言都显示 "Python 版本" 选择器和 "Python 运行时"。

**修复**（`SearchView.vue`）：使用 `v-if="searchForm.lang === 'python'"` / `v-else` 动态切换 Python 版本和 R 版本选择器。

---

### 15.9 下载进度：WebSocket 回调未注册

**问题**：下载过程中前端进度条完全不动，用户看不到任何进度。定位发现 `DownloadManager._notify_progress()` 依赖已注册的回调函数来通知进度，但 `_execute_download()`（`routers/download.py`）从未调用 `downloader.on_progress()` 将 `broadcast_progress` 注册为回调。导致 `download_file` 虽在内部持续计算并通知 progress（如 `downloaded/total`），但没有任何接收者——WebSocket 从未收到进度更新。

用户只看到初始的「⏳ 下载中」和完成后的「✅ 下载完成」，中间的实际百分比进度全部被吞。

**修复**（`download.py`）：在 `_execute_download` 开始时添加一行：
```python
downloader.on_progress(task_id, broadcast_progress)
```
使 `DownloadManager` 内部的 `_notify_progress` 正确广播到前端 WebSocket 连接。

**教训**：异步任务管理器与 WebSocket 广播之间需要显式「绑定」关系，不能假设框架自动协作。任何中间层（如 DownloadManager）的进度回调都必须显式注册，否则 WebSocket 广播无效。

---

### 15.10 依赖版本规格说明符未解析为具体版本号

**问题**：`resolve_dependencies()` 将 `requires_dist` 中的版本约束直接存储为依赖包的 `version` 字段，例如 `numpy>=1.20,!=1.24.0`。但下游 `_get_wheel_from_mirror_simple()` 用这个字符串去匹配 wheel 文件名：
```python
if norm_version not in norm_fn:  # '>=1.20,!=1.24.0' in 'numpy-1.26.3-cp311-...'
    continue
```
永远匹配不上！结果：遍历 4 个镜像源 × 每个等待 20s 超时 → 最终回退到官方 PyPI JSON API（极慢）。

**修复**（`python_resolver.py`）：
- 新增 `_resolve_specifier()` 静态方法，用 `packaging.specifiers.SpecifierSet` 解析规格符
- 优先利用 `get_versions()` 的镜像缓存获取所有可用版本
- 用 `SpecifierSet.contains()` 筛选出满足约束的版本，取最新的作为实际版本号
- 在 `resolve_dependencies()` 中对每个依赖的 specifier 调用 `_resolve_specifier()`

**效果**：`numpy>=1.20,!=1.24.0` → `2.0.1`，清华镜像 0.2s 命中 wheel，CDN 下载 16.5MB 仅需 5s。

**教训**：程序内部流转的「版本」字段必须始终是具体版本号（如 `2.0.1`），不能携带规格说明符（如 `>=1.20`）。规格符只在用户输入和 API 响应阶段临时存在，进入逻辑处理前必须解析。

---

### 15.11 下载循环：镜像源嵌套遍历导致重复请求

**问题**：`download_python_package()` 为实现「镜像容错」在外层逐个遍历镜像源，但内层 `_get_wheel_from_mirror_simple()` 已经遍历了所有镜像：
- 外层：清华 → 内层：清华→阿里→豆瓣→官方（清华命中）
- 外层：阿里 → 内层：清华→阿里→豆瓣→官方（又清华命中）
- 外层：豆瓣 → 内层：清华→阿里→豆瓣→官方（又双清华命中）
- 外层：官方 → 内层：清华→阿里→豆瓣→官方（又又又清华命中）

不仅造成 N² 的请求量，且每个镜像失败后都等待完整的 20s 超时窗口才切换到下一个，大幅拖累失败路径的响应速度。

**修复**（`downloader.py`）：改为两阶段流水线：
1. **阶段 1**：调用 `_get_wheel_from_mirror_simple()` 一次性获取 wheel URL（内部自动遍历所有镜像）
2. **阶段 2**：从获得的 URL 直接下载，若失败则回退官方 PyPI JSON API

**教训**：函数职责要单一明确。「获取 wheel 链接」和「下载 wheel 文件」是两个独立的关注点，不应在循环中混合，更不应多层嵌套。

---

### 15.12 PyPI 多层加速体系

**问题**：PyPI 官方源（pypi.org）在国内网络环境下响应极慢（搜索 40s+、依赖解析 40s+、下载数分钟），且单点故障时整个服务不可用。

**解决方案**：构建三层加速 + 多层容错体系：

**第一层：SQLite 持久化缓存**（`api_cache.py` + `database.py`）
- 所有 PyPI API 响应自动缓存到 `api_cache` 表，按类型设置不同 TTL
- 包元数据：1 小时 | 版本列表：30 分钟 | 搜索：10 分钟 | GitHub：5 分钟 | CRAN：1 小时
- 缓存命中后零网络请求，秒级响应
- 支持按缓存类型扩展，无需修改现有调用代码

**第二层：国内镜像 JSON API 优先**（`python_resolver.py`）
- 搜索、版本获取、依赖解析全部优先调用国内镜像的 JSON API 接口
- 镜像顺序：清华 → 阿里 → 豆瓣 → 官方
- 镜像 JSON API 格式与官方完全一致，数据通过国内 CDN 加速
- 搜索速度从 40s 降至 0.5s（83 倍），依赖解析降至 0.04s（1000 倍）

**第三层：镜像 Simple API 获取 Wheel 下载链接**（`python_resolver.py`）
- 通过镜像的 PEP 503 Simple API 获取 wheel 列表，避免直接访问 files.pythonhosted.org
- 返回的 wheel URL 指向国内 CDN，下载速度提升显著
- 按优先级筛选 wheel：精确匹配 python_ver+win_amd64 → 任意 Windows wheel → 纯 Python wheel
- 镜像 Simple API 返回的 href 为相对路径（如 `../../packages/...`），需用 `urljoin()` 正确拼接

**镜像配置结构**（`config.py`）：
```python
MIRRORS = {
    "pypi": {
        "清华": "https://pypi.tuna.tsinghua.edu.cn/simple",
        "阿里": "https://mirrors.aliyun.com/pypi/simple",
        "豆瓣": "https://pypi.doubanio.com/simple",
        "官方": "https://pypi.org/simple",
    },
    "cran": {
        "清华": "https://mirrors.tuna.tsinghua.edu.cn/CRAN",
        "官方": "https://cran.r-project.org",
    }
}
```

**效果验证**（清除缓存后首次访问）：

| 场景 | 官方源（修复前） | 镜像优先（修复后） | 提速倍数 |
|------|-----------------|-------------------|---------|
| 🔍 首次搜索 scikit-learn | 40.18s | 0.48s | **83×** |
| 🔍 搜索 cache 后 | 0.03s | 0.03s | 不变 |
| 📋 依赖解析（首次） | ~40s | 0.04s | **1000×** |
| 📦 numpy 16.5MB 下载 | 数分钟+ | 5s | **数十倍** |
| 📦 matplotlib 8MB 下载 | 数分钟+ | 5s | **数十倍** |
| 📦 seaborn 整体任务 | 数分钟+可能失败 | **15s 全部完成** | — |

**教训**：
1. 海外 API 在国内的直接接入必须走 CDN/镜像，这是第一优先级
2. 缓存层先于网络调用检查，可大幅降低海外 API 的重复请求压力
3. 镜像数据可能有轻微滞后（如清华镜像 scikit-learn 为 1.5.1，官方为 1.8.0），但功能不受影响
4. 多层容错设计（缓存→镜像 JSON→镜像 Simple→官方 JSON）确保任意单点失效时服务不中断