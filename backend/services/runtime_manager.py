"""运行时管理器（Python/R 安装包预置 + 版本检查更新）"""
import json
from pathlib import Path
from loguru import logger
from backend.database import db
from backend.config import RUNTIMES_DIR


class RuntimeManager:
    """运行时管理器"""

    # 官方下载地址模板
    PYTHON_DOWNLOADS = {
        "3.8.10": "https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe",
        "3.9.13": "https://www.python.org/ftp/python/3.9.13/python-3.9.13-amd64.exe",
        "3.10.11": "https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe",
        "3.11.9": "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe",
        "3.12.3": "https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe",
        "3.13.0": "https://www.python.org/ftp/python/3.13.0/python-3.13.0-amd64.exe",
    }

    R_DOWNLOADS = {
        "4.0.5": "https://cran.r-project.org/bin/windows/base/R-4.0.5-win.exe",
        "4.1.3": "https://cran.r-project.org/bin/windows/base/R-4.1.3-win.exe",
        "4.2.3": "https://cran.r-project.org/bin/windows/base/R-4.2.3-win.exe",
        "4.3.3": "https://cran.r-project.org/bin/windows/base/R-4.3.3-win.exe",
        "4.4.0": "https://cran.r-project.org/bin/windows/base/R-4.4.0-win.exe",
    }

    RTOOLS_DOWNLOADS = {
        "43": "https://cran.r-project.org/bin/windows/Rtools/rtools43.exe",
        "42": "https://cran.r-project.org/bin/windows/Rtools/rtools42.exe",
    }

    @staticmethod
    def get_runtimes() -> list[dict]:
        """获取可用运行时列表"""
        runtimes = db.fetchall(
            "SELECT * FROM runtime_index ORDER BY lang, version DESC"
        )
        return runtimes

    @staticmethod
    def get_runtime_by_version(lang: str, version: str) -> dict | None:
        """获取指定版本的运行时"""
        return db.fetchone(
            "SELECT * FROM runtime_index WHERE lang = ? AND version = ?",
            (lang, version),
        )

    @staticmethod
    def register_runtime(
        lang: str,
        version: str,
        filename: str,
        filepath: str,
        file_size: int = 0,
        sha256: str = "",
        download_url: str = "",
    ):
        """注册运行时到索引"""
        arch = "amd64"
        db.execute(
            """
            INSERT OR REPLACE INTO runtime_index
                (lang, version, arch, filename, filepath, file_size, sha256, download_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (lang, version, arch, filename, filepath, file_size, sha256, download_url),
        )

    @staticmethod
    def scan_local_runtimes():
        """扫描本地已下载的运行时并更新索引"""
        if not RUNTIMES_DIR.exists():
            return

        for f in RUNTIMES_DIR.iterdir():
            if not f.is_file():
                continue
            name = f.name
            size = f.stat().st_size

            # 识别 Python 安装包
            if name.startswith("python-") and name.endswith("-amd64.exe"):
                # python-3.11.9-amd64.exe
                parts = name.replace("-amd64.exe", "").split("-")
                if len(parts) >= 2:
                    ver = parts[1]
                    url = RuntimeManager.PYTHON_DOWNLOADS.get(ver, "")
                    RuntimeManager.register_runtime(
                        lang="python",
                        version=ver,
                        filename=name,
                        filepath=str(f),
                        file_size=size,
                        download_url=url,
                    )
                    logger.info("注册 Python 运行时: {} ({})", ver, name)

            # 识别 R 安装包
            elif name.startswith("R-") and name.endswith("-win.exe"):
                # R-4.3.3-win.exe
                ver = name[2:].replace("-win.exe", "")
                url = RuntimeManager.R_DOWNLOADS.get(ver, "")
                RuntimeManager.register_runtime(
                    lang="r",
                    version=ver,
                    filename=name,
                    filepath=str(f),
                    file_size=size,
                    download_url=url,
                )
                logger.info("注册 R 运行时: {} ({})", ver, name)

            # 识别 Rtools
            elif name.startswith("rtools") and name.endswith(".exe"):
                # rtools43.exe
                ver = name.replace("rtools", "").replace(".exe", "")
                url = RuntimeManager.RTOOLS_DOWNLOADS.get(ver, "")
                RuntimeManager.register_runtime(
                    lang="rtools",
                    version=ver,
                    filename=name,
                    filepath=str(f),
                    file_size=size,
                    download_url=url,
                )
                logger.info("注册 Rtools: {} ({})", ver, name)

    @staticmethod
    async def sync_runtimes():
        """检查并更新运行时版本（从官方源下载缺失的运行时信息）"""
        import httpx
        from packaging.version import Version

        updated = []

        # 检查 Python 新版本
        try:
            resp = httpx.get("https://www.python.org/ftp/python/", timeout=15)
            if resp.status_code == 200:
                # 解析页面获取版本列表（简化版）
                import re
                versions = re.findall(r'<a href="(\d+\.\d+\.\d+)/"', resp.text)
                for ver in sorted(set(versions), key=lambda v: Version(v), reverse=True)[:10]:
                    major_minor = ".".join(ver.split(".")[:2])
                    # 检查是否已在索引中
                    existing = db.fetchone(
                        "SELECT id FROM runtime_index WHERE lang = 'python' AND version = ?",
                        (ver,),
                    )
                    if not existing:
                        download_url = RuntimeManager.PYTHON_DOWNLOADS.get(ver, "")
                        if not download_url:
                            download_url = f"https://www.python.org/ftp/python/{ver}/python-{ver}-amd64.exe"
                        RuntimeManager.register_runtime(
                            lang="python",
                            version=ver,
                            filename=f"python-{ver}-amd64.exe",
                            filepath=str(RUNTIMES_DIR / f"python-{ver}-amd64.exe"),
                            download_url=download_url,
                        )
                        updated.append(f"python-{ver}")
                        logger.info("新增 Python 运行时记录: {}", ver)
        except Exception as e:
            logger.error("同步 Python 版本失败: {}", e)

        # 检查 R 新版本
        try:
            resp = httpx.get("https://cran.r-project.org/bin/windows/base/", timeout=15)
            if resp.status_code == 200:
                import re
                # 简化版：只识别已知版本
                pass
        except Exception as e:
            logger.error("同步 R 版本失败: {}", e)

        return updated
