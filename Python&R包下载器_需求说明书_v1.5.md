# Python&R 包下载器 · 需求说明书

> 版本：v1.5 | 日期：2026-05-17 | 状态：待确认

---

## 1. 项目概述

**软件名称**：Python&R 包下载器（以下简称"下载器"）

**核心价值**：内网/离线/受限网络环境下，用户在 A 电脑浏览器访问部署于 B 服务器的下载器，输入包名即可自动递归下载该包及其全部依赖，打包后一键下载至 A 电脑完成离线安装。

**部署架构**：
- B 服务器（Ubuntu Server）部署下载器 Web 服务，A 电脑通过浏览器访问
- 目标平台：Windows
- A 电脑可能为白板电脑（无 Python/R 运行时），下载器一并提供运行时安装包

**关键约束**：
- A 电脑纯离线，无法访问互联网
- 所有依赖（含 Rtools 等工具链）须由下载器一并打包

---

## 2. 功能需求

### 2.1 核心功能

| # | 功能 | 说明 |
|---|------|------|
| F1 | 包搜索 | 输入包名，搜索 PyPI（Python）或 CRAN/Bioconductor/GitHub 仓库（R），返回匹配结果及版本 |
| F2 | 版本选择 | 非必填；不填下载最新版，填则按指定版本下载 |
| F3 | 依赖递归解析 | 解析直接依赖→间接依赖→全部依赖，构建完整依赖树（DAG 去重） |
| F4 | 多来源下载 | 支持 PyPI、CRAN、Bioconductor、GitHub Releases 以及各国内镜像站点；来源标签显示，默认优选官方源。R 语言额外支持从 GitHub 仓库直接下载源码（适用于非 CRAN 的个人开发包），自动重打包为 `.tar.gz` 格式 |
| F5 | 批量下载 | 20 并发下载；R 包需编译时自动下载 Rtools 一并打包 |
| F6 | 打包归档 | 所有包 + 安装脚本（根据下载的包和安装语言自动生成），点击下载后压缩为单个 `.zip`，但此压缩包内的每一个R语言的需独立单个打包成.tgz或.tar.gz格式，方便rtudio导入和安装 |
| F7 | 一键下载 | 浏览器直接下载打包文件 |
| F8 | 一键安装 | 安装脚本自动完成离线安装；未安装运行时时自动引导 |

### 2.2 缓存与复用

| # | 功能 | 说明 |
|---|------|------|
| F9 | 包永久保留 | 已下载包不删除，永久存入服务器本地仓库 |
| F10 | 包索引 | 对仓库建立索引（包名、版本、语言、平台、来源、文件路径、SHA256），支持快速检索 |
| F11 | 智能比对复用 | 依赖分析后按「来源+包名+版本+平台」与仓库比对，匹配者直接复用，跳过下载 |
| F12 | 历史任务复用 | 按包名/版本/语言搜索历史任务，一键复用（检查完整性后直接打包，秒级完成） |

### 2.3 辅助功能

| # | 功能 | 说明 |
|---|------|------|
| F13 | 包信息展示 | 显示包名、版本、大小、依赖数、描述 |
| F14 | 实时进度条 | 整体进度 + 每包独立状态 + 来源标签 + 复用/新下载标记；WebSocket 推送 |
| F15 | 智能错误提示 | 自动分析失败原因，翻译为中文并给出操作建议 |
| F16 | 镜像源配置 | 支持配置国内镜像（清华、阿里等），加速下载 |
| F17 | 运行时下载 | 预置 Python/R/Rtools 安装包，可单独下载或随包打包 |
| F18 | 任务日志 | 记录所有任务及用户 IP 地址 |
| F19 | 仓库统计 | 显示包数量、占用空间、运行时效中版本等 |

---

## 3. 系统设计

### 3.1 包仓库架构

```
/var/lib/pkgdl/repository/
├── python/               # Python wheel 文件，永久保留
├── r/                    # R Windows binary + Rtools，永久保留
├── runtimes/             # Python/R 运行时安装包（预置 + 自动更新）
└── index.db              # SQLite 索引库
```

### 3.2 索引数据库

| 表名 | 用途 |
|------|------|
| `package_index` | 包文件索引（name, version, lang, platform, python_ver, source, sha256...） |
| `runtime_index` | 运行时索引（lang, version, arch, filepath, sha256...） |
| `tasks` | 任务表（ID, 包名, 版本, 来源, 状态, 复用率, 客户端IP, 创建/完成时间） |
| `task_packages` | 任务-包关联（task_id, 包名, 版本, 状态, 是否复用, 错误信息） |
| `api_cache` | API 响应缓存（TTL：元数据 1h，版本 30min，搜索 10min） |

### 3.3 智能复用流程

```
用户请求下载 pandas 3.2.1（来源: PyPI）
    │
    ▼
依赖解析 → [pandas, numpy, python-dateutil, six, pytz, tzdata]（均标记来源）
    │
    ▼
逐个与仓库按「来源+包名+版本+平台」比对
    │
    ├─ pandas/numpy/six/python-dateutil → ✅ 命中，从仓库复用
    └─ pytz/tzdata → ❌ 缺失，20并发下载
    │
    ▼
新包写入仓库 + 更新索引 → 合并打包
```

**效果**：6 个包中 4 个复用，下载量大幅减少。

### 3.4 多层加速架构

| 层级 | 策略 | 效果 |
|------|------|------|
| 第一层 | SQLite 持久化缓存 | 缓存命中后零网络请求，秒级响应 |
| 第二层 | 国内镜像 JSON API 优先（清华→阿里→豆瓣→官方） | 搜索从 40s 降至 0.5s（83×） |
| 第三层 | 镜像 Simple API 获取 wheel CDN 链接 | 下载从数分钟降至 5s（数十倍） |

> 任意单层失效时自动回退到下一层，确保服务不中断。

---

## 4. 技术方案

### 4.1 技术栈

| 层级 | 选型 | 说明 |
|------|------|------|
| 后端 | Python 3.11 + FastAPI | 异步高性能，生态丰富 |
| 前端 | Vue 3 + Element Plus + Vite | 现代化 SPA |
| Python 依赖解析 | pipdeptree + packaging.specifiers | DAG 去重，规格符解析为具体版本 |
| R 依赖解析 | CRAN API + tools::package_dependencies() | R 原生解析 |
| GitHub | GitHub REST API (Releases) | 搜索 Releases 中的包 |
| 下载 | httpx 异步 HTTP，20 并发 | 高并发 |
| 实时通信 | WebSocket | 进度推送 |
| 数据存储 | SQLite | 零运维 |
| 部署 | Docker + Docker Compose | 一键部署 |

### 4.2 关键处理流程

**Python/R 包下载流程**：
```
输入包名 → 多来源搜索（用户选来源） → 依赖解析 → DAG 去重
→ 仓库比对（按来源+包名+版本+平台） → 仅下载缺失包 → 写入仓库+更新索引
→ 生成 install.bat → 可选附运行时 → 打包为 .zip
```

**一键复用流程**：
```
搜索历史任务 → 点击复用 → 检查仓库包完整性（SHA256）
→ 全部存在：秒级打包下载
→ 部分缺失：提示补充下载或仅打包已有包
```

---

## 5. API 设计

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/search` | 搜索包 `?q=pandas&lang=python&source=pypi` |
| GET | `/api/package/{lang}/{name}` | 包详情 + 版本列表 + 仓库标记 |
| GET | `/api/package/{lang}/{name}/versions` | 历史版本列表 |
| POST | `/api/download` | 触发下载 `{lang, packages, source, python_version/r_version, include_runtime}` |
| WS | `/ws/download/{task_id}` | WebSocket 实时进度 |
| GET | `/api/download/{task_id}/status` | 任务状态 |
| GET | `/api/download/{task_id}/export` | 下载打包文件 |
| GET | `/api/tasks` | 任务一览表 |
| GET | `/api/tasks/search` | 搜索历史任务 |
| POST | `/api/tasks/{task_id}/reuse` | 一键复用 |
| DELETE | `/api/tasks/{task_id}` | 删除任务记录 |
| GET | `/api/repository/stats` | 仓库统计 |
| GET | `/api/runtimes` | 可用运行时列表 |
| GET | `/api/runtimes/download/{type}/{version}` | 下载运行时 |
| POST | `/api/runtimes/sync` | 管理员触发运行时版本检查 |
| POST | `/api/github/search` | 搜索 GitHub Releases |

---

## 6. 错误处理

| 错误类型 | 中文提示 | 建议操作 |
|----------|----------|----------|
| 404 | 包不存在或版本号有误 | 检查名称/版本 |
| Timeout | 网络连接超时 | 检查镜像源或稍后重试 |
| SSL Error | 安全连接失败 | 检查网络环境 |
| RateLimit | GitHub API 频率超限 | 稍后重试 |
| NoWinWheel | 无 Windows 版本 | 该包无法在 Windows 安装 |
| Conflict | 依赖版本冲突 | 建议使用最新版本 |
| HashMismatch | 文件校验失败 | 重新下载 |
| DiskFull | 磁盘空间不足 | 联系管理员 |
| GitHubSrcErr | 非官方源依赖树可能不完整 | 建议切换官方源 |
| RuntimeNotFound | 运行时未预置 | 联系管理员下载 |

---

## 7. 安装脚本

### Python（`install_python.bat`）

1. 检测 Python 是否已安装，未安装则引导安装运行时
2. 校验 SHA256 完整性
3. `pip install --no-index --find-links=./packages <pkgs>`
4. 验证安装成功

### R（`install_r.bat`）

1. 检测 R 是否已安装，未安装则引导安装运行时
2. 检测并静默安装 Rtools（如有）
3. `R CMD INSTALL --library="<lib>" <pkgs>`
4. 验证安装成功

---

## 8. 部署

```bash
git clone <repo> && cd pkg-downloader
docker compose up -d
# 访问 http://<B服务器IP>:3579
```

**运行时预置**：首次部署后，管理员通过管理界面或 `/api/runtimes/sync` 自动下载 Python/R 官方安装包。

---

## 9. 已知限制与风险

| # | 限制 | 应对 |
|---|------|------|
| 1 | R 包无 Windows binary 时需 Rtools 编译 | 下载器自动下载 Rtools 一并打包，静默安装 |
| 2 | 仓库永久保留占用磁盘空间 | 提供统计页面，管理员手动清理 |
| 3 | 部分 Python 包依赖系统级库 | 安装脚本提示系统依赖 |
| 4 | 大型依赖树首次下载耗时长 | 20 并发 + 复用，后续大幅提速 |
| 5 | 旧版本包可能从镜像源移除 | 仓库已有旧版本直接复用；否则提示检查版本 |
| 6 | GitHub 来源包依赖树通常不完整 | 前端标注警告；默认优选官方源 |
| 7 | GitHub API 未认证限速 60次/小时 | 配置 GITHUB_TOKEN 提升至 5000次/小时 |
| 8 | 运行时安装包体积较大（Python ~30MB, R ~100MB+） | 按需下载，不强制包含；需管理员预置 |

---

## 10. 开发规范与注意事项

> 以下条目均为开发过程中实际踩过的坑，开发时应知悉、遵守，避免重蹈覆辙。

### 10.1 依赖解析

| # | 规范 | 说明 |
|---|------|------|
| D1 | **外部 API 返回类型必须做防御性检查** | CRAN API 的 `Depends/Imports` 字段可能返回 dict 或 string，调用 `.strip()` 前必须先判断类型。统一用 `_parse_dep_list()` 兼容两种格式。 |
| D2 | **版本字段流转全链路必须是具体版本号** | `requires_dist` 中的规格说明符（如 `>=1.20,!=1.24.0`）不得直接流入下载逻辑，必须先用 `packaging.specifiers.SpecifierSet` 解析为具体版本号（如 `2.0.1`）。 |
| D3 | **前端必须传递目标 Python/R 版本参数** | 依赖解析必须使用用户指定的 Python/R 版本，不得使用后端默认值。前后端 API 接口必须显式传递 `python_ver` / `r_ver` 参数并校验。 |

### 10.2 网络与下载

| # | 规范 | 说明 |
|---|------|------|
| D4 | **用 `GET + Range` 而非 HEAD 做存在性检查** | HEAD 请求在 CDN/镜像站兼容性差（返回 405/超时），改用 `GET + Range: bytes=0-1` 更可靠。 |
| D5 | **「获取下载链接」与「下载文件」必须分离** | 两个职责不得嵌套在双层循环中，否则 N² 请求量且重复等待超时。应拆分为两阶段：阶段一获取 URL，阶段二下载。 |
| D6 | **海外 PyPI API 必须经 CDN/镜像中转** | 国内直接访问官方 PyPI 极慢（40s+），搜索/版本/依赖解析全部优先走国内镜像 Simple API，始终降级回退。 |
| D7 | **所有网络请求必须设置合理超时 + 重试** | 大型包 JSON 响应可超 900KB，单次超时上限应 ≥50s，重试 ≥2 次。 |

### 10.3 前端交互

| # | 规范 | 说明 |
|---|------|------|
| D8 | **永远不要用 `v-if` 隐式隐藏错误状态** | 加载失败时组件应显示错误信息 + 重试按钮，不得直接消失。应设计四级状态：加载中→失败→成功→空。 |
| D9 | **上下文相关的全局列表必须按上下文过滤** | 语言切换时（如 Python→R），版本选择器、运行时下拉框等全局列表必须按当前语言动态过滤，避免显示无关选项。 |
| D10 | **选中状态样式必须独立于 hover 状态** | 用户操作后的选中态必须清晰可见（左侧竖条/角标），不得依赖 hover 效果，鼠标离开后仍应保持。 |

### 10.4 实时通信与进度

| # | 规范 | 说明 |
|---|------|------|
| D11 | **中间层进度回调必须显式注册** | 异步任务管理器（如 `DownloadManager`）的进度回调不会自动协作，`.on_progress()` 必须显式调用将 `broadcast_progress` 注册进去，否则 WebSocket 永远收不到进度更新。 |

### 10.5 数据与缓存

| # | 规范 | 说明 |
|---|------|------|
| D12 | **镜像 Simple API 返回的 href 是相对路径** | 必须用 `urljoin()` 拼接为完整 URL，不得直接当作绝对路径使用。 |
| D13 | **仓库永久保留，不得自动清理** | 复用是核心性能优化手段。磁盘空间由管理员手动管理，不做自动淘汰策略。 |

### 10.6 包索引比对

| # | 规范 | 说明 |
|---|------|------|
| D14 | **仓库比对必须包含来源字段** | 不同来源的同一包名同一版本可能是不同文件（如 PyPI 和 GitHub），比对键为「来源+包名+版本+平台」，缺一不可。 |

### 10.7 SPA 与静态文件服务

| # | 规范 | 说明 |
|---|------|------|
| D15 | **Vue Router history 模式须做 SPA 路由回退** | 前端使用 history 模式时，刷新非根路径（如 `/search`）会向后端请求该路径。后端必须将未匹配的前端路径统一回退到 `index.html`，否则返回 404。实现方案：继承 `StaticFiles` 覆盖 `get_response`，捕获 404 后对非 `/api/` 路径回退到 `index.html`。 |

### 10.8 生产部署

| # | 规范 | 说明 |
|---|------|------|
| D16 | **生产服务必须配置 systemd 自启动** | 使用 `systemd` 服务管理，配置 `Restart=always` 确保进程崩溃后自动恢复。同时设为 `enable` 实现开机自启。服务文件应包含 `WorkingDirectory`、`ExecStart`、`RestartSec` 等关键字段。 |

### 10.9 非 CRAN R 包支持

| # | 规范 | 说明 |
|---|------|------|
| D17 | **R 语言应支持从 GitHub 仓库下载非 CRAN 包源码** | 个人开发的 R 包（如 `devtools::install_github()` 方式安装）不在 CRAN 上，无法通过 CRAN API 解析依赖和下载。应通过 GitHub API 搜索仓库→下载源码归档→提取版本号→重打包为标准 `{name}_{version}.tar.gz`（顶层目录标准化为包名），确保 `R CMD INSTALL` 可正常安装。下载流程中跳过 CRAN 依赖解析，仅下载主包本身。 |

---

**版本历史**：

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.4 | 2026-05-16 | 初版 |
| v1.5 | 2026-05-17 | 将开发经验从附录升级为第10章「开发规范与注意事项」；新增 D15 SPA路由回退、D16 systemd自启动、D17 非CRAN R包GitHub源码下载；F1/F4 扩展支持GitHub仓库R包搜索与下载 |
