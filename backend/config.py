"""项目配置"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 仓库配置
REPOSITORY_DIR = Path(os.getenv("REPOSITORY_DIR", "/var/lib/pkgdl/repository"))
INDEX_DB_PATH = REPOSITORY_DIR / "index.db"
PYTHON_DIR = REPOSITORY_DIR / "python"
R_DIR = REPOSITORY_DIR / "r"
RUNTIMES_DIR = REPOSITORY_DIR / "runtimes"
EXPORT_DIR = REPOSITORY_DIR / "exports"

# 服务端口
SERVER_PORT = int(os.getenv("SERVER_PORT", "3579"))
HOST = os.getenv("HOST", "0.0.0.0")

# 下载配置
MAX_CONCURRENT_DOWNLOADS = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "20"))
DEFAULT_SOURCE = os.getenv("DEFAULT_SOURCE", "pypi")  # pypi / cran / github
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "120"))  # 秒

# 镜像源
PIP_INDEX_URL = os.getenv(
    "PIP_INDEX_URL", "https://pypi.tuna.tsinghua.edu.cn/simple"
)
CRAN_MIRROR = os.getenv(
    "CRAN_MIRROR", "https://mirrors.tuna.tsinghua.edu.cn/CRAN"
)
RTOOLS_URL = os.getenv(
    "RTOOLS_URL",
    "https://cran.r-project.org/bin/windows/Rtools/rtools43.exe",
)

# GitHub
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API_URL = "https://api.github.com"

# 运行时
RUNTIME_AUTO_SYNC = os.getenv("RUNTIME_AUTO_SYNC", "true").lower() == "true"

# 日志
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# 镜像源列表
MIRRORS = {
    "pypi": {
        "清华": "https://pypi.tuna.tsinghua.edu.cn/simple",
        "阿里": "https://mirrors.aliyun.com/pypi/simple",
        "豆瓣": "https://pypi.doubanio.com/simple",
        "官方": "https://pypi.org/simple",
    },
    "cran": {
        "清华": "https://mirrors.tuna.tsinghua.edu.cn/CRAN",
        "阿里": "https://mirrors.aliyun.com/CRAN/",
        "中科大": "https://mirrors.ustc.edu.cn/CRAN/",
        "官方": "https://cran.r-project.org",
    },
}

# 可用的 Python 版本列表
PYTHON_VERSIONS = ["3.8", "3.9", "3.10", "3.11", "3.12", "3.13"]

# 可用的 R 版本列表
R_VERSIONS = ["4.0", "4.1", "4.2", "4.3", "4.4"]

# 可用的包来源
SOURCES = {
    "python": ["pypi", "github"],
    "r": ["cran", "bioconductor", "github"],
}
