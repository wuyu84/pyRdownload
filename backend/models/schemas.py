"""Pydantic 数据模型"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── 包搜索 ──

class PackageSearchResult(BaseModel):
    """搜索结果项"""
    name: str
    version: str
    lang: str
    source: str
    description: str = ""
    dependencies: int = 0
    file_size: int = 0
    cached_count: int = 0
    total_in_repo: int = 0
    has_windows_build: bool = True


class SearchResponse(BaseModel):
    """搜索响应"""
    results: list[PackageSearchResult]


# ── 包版本 ──

class VersionInfo(BaseModel):
    """版本信息"""
    version: str
    source: str
    published_at: str = ""
    python_ver: str = ""
    is_cached: bool = False


class PackageDetail(BaseModel):
    """包详细信息"""
    name: str
    lang: str
    versions: list[VersionInfo]
    description: str = ""
    source: str = ""


# ── 依赖树 ──

class DepNode(BaseModel):
    """依赖树节点"""
    name: str
    version: str
    source: str = ""
    status: str = "pending"  # pending / cached / downloading / downloaded / failed
    is_cached: bool = False
    children: list["DepNode"] = []


# ── 下载 ──

class DownloadRequest(BaseModel):
    """下载请求"""
    lang: str  # python / r
    packages: list[dict] = Field(..., description="包列表 [{name: str, version: Optional[str]}]")
    source: str = "pypi"  # pypi / cran / github / bioconductor
    python_version: Optional[str] = None
    r_version: Optional[str] = None
    include_runtime: bool = False
    mirror: str = ""


class DownloadResponse(BaseModel):
    """下载响应"""
    task_id: str
    message: str = "任务已创建"


# ── 任务 ──

class TaskPackage(BaseModel):
    """任务中的包"""
    pkg_name: str
    pkg_version: str
    lang: str
    source: str = ""
    status: str  # cached / downloaded / failed
    is_cached: bool = False
    error_msg: Optional[str] = None
    friendly_error: Optional[str] = None


class TaskDetail(BaseModel):
    """任务详情"""
    id: str
    lang: str
    source: str
    package_name: str
    package_version: Optional[str]
    python_ver: Optional[str] = None
    r_ver: Optional[str] = None
    status: str
    total_pkgs: int
    cached_pkgs: int
    downloaded_pkgs: int
    failed_pkgs: int
    file_size: int = 0
    export_path: Optional[str] = None
    client_ip: str
    created_at: str
    finished_at: Optional[str] = None
    packages: list[TaskPackage] = []


class TaskListItem(BaseModel):
    """任务列表项"""
    id: str
    lang: str
    source: str
    package_name: str
    package_version: Optional[str]
    status: str
    total_pkgs: int
    cached_pkgs: int
    downloaded_pkgs: int
    failed_pkgs: int
    file_size: int = 0
    client_ip: str
    created_at: str
    finished_at: Optional[str] = None


class TaskListResponse(BaseModel):
    """任务列表响应"""
    tasks: list[TaskListItem]
    total: int


# ── 仓库统计 ──

class RepositoryStats(BaseModel):
    """仓库统计"""
    python_pkgs: int = 0
    r_pkgs: int = 0
    runtimes_count: int = 0
    active_tasks: int = 0
    total_size: int = 0  # 字节


# ── 运行时 ──

class RuntimeInfo(BaseModel):
    """运行时信息"""
    lang: str
    version: str
    arch: str = "amd64"
    filename: str
    file_size: int = 0
    download_url: str = ""


class RuntimeListResponse(BaseModel):
    """运行时列表响应"""
    runtimes: list[RuntimeInfo]


# ── 配置 ──

class ConfigResponse(BaseModel):
    """配置响应"""
    mirrors: dict
    python_versions: list[str]
    r_versions: list[str]
    sources: dict


# ── 源选择 ──

class GitHubSearchRequest(BaseModel):
    """GitHub 搜索请求"""
    q: str
    lang: str = "python"


class SourceSelectResult(BaseModel):
    """源选择结果"""
    source: str
    name: str
    version: str
    url: str = ""
    description: str = ""
    is_preferred: bool = False
