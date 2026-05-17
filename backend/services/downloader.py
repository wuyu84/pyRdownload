"""下载管理器（20并发 + 进度追踪）"""
import asyncio
import hashlib
from pathlib import Path
from typing import Optional, Callable
from loguru import logger
import httpx
from backend.config import (
    MAX_CONCURRENT_DOWNLOADS,
    DOWNLOAD_TIMEOUT,
    PYTHON_DIR,
    R_DIR,
)


class DownloadManager:
    """异步下载管理器"""

    def __init__(self):
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
        self._progress_callbacks: dict[str, list[Callable]] = {}

    def on_progress(self, task_id: str, callback: Callable):
        """注册进度回调"""
        if task_id not in self._progress_callbacks:
            self._progress_callbacks[task_id] = []
        self._progress_callbacks[task_id].append(callback)

    async def _notify_progress(
        self,
        task_id: str,
        pkg_name: str,
        status: str,
        progress: float = 0,
        message: str = "",
    ):
        """通知进度"""
        if task_id in self._progress_callbacks:
            for cb in self._progress_callbacks[task_id]:
                try:
                    if asyncio.iscoroutinefunction(cb):
                        await cb(task_id, pkg_name, status, progress, message)
                    else:
                        cb(task_id, pkg_name, status, progress, message)
                except Exception as e:
                    logger.error("进度回调错误: {}", e)

    async def download_file(
        self,
        url: str,
        dest_path: Path,
        task_id: str = "",
        pkg_name: str = "",
    ) -> tuple[bool, str]:
        """下载单个文件，返回 (成功?, 错误信息/SHA256)"""
        async with self._semaphore:
            try:
                async with httpx.AsyncClient(
                    timeout=DOWNLOAD_TIMEOUT,
                    follow_redirects=True,
                ) as client:
                    async with client.stream("GET", url) as response:
                        if response.status_code != 200:
                            err_msg = f"HTTP {response.status_code}"
                            await self._notify_progress(
                                task_id, pkg_name, "failed", 0, err_msg
                            )
                            return False, err_msg

                        total = int(response.headers.get("content-length", 0))
                        downloaded = 0
                        sha256_hash = hashlib.sha256()

                        dest_path.parent.mkdir(parents=True, exist_ok=True)

                        with open(dest_path, "wb") as f:
                            async for chunk in response.aiter_bytes(chunk_size=65536):
                                f.write(chunk)
                                sha256_hash.update(chunk)
                                downloaded += len(chunk)
                                if total > 0 and task_id:
                                    progress = downloaded / total
                                    await self._notify_progress(
                                        task_id, pkg_name, "downloading", progress
                                    )

                        sha256_val = sha256_hash.hexdigest()
                        await self._notify_progress(
                            task_id, pkg_name, "downloaded", 1.0
                        )
                        logger.info("下载完成: {} -> {} ({} bytes)", pkg_name, dest_path.name, downloaded)
                        return True, sha256_val

            except httpx.TimeoutException:
                await self._notify_progress(task_id, pkg_name, "failed", 0, "下载超时")
                return False, "Timeout"
            except Exception as e:
                err_msg = str(e)
                await self._notify_progress(task_id, pkg_name, "failed", 0, err_msg)
                return False, err_msg

    async def download_python_package(
        self,
        name: str,
        version: str,
        python_ver: str = "cp311",
        task_id: str = "",
    ) -> tuple[bool, str, str, str]:
        """下载 Python 包，返回 (成功?, 错误/SHA256, 文件名, 文件路径)
        策略：先一次性遍历所有镜像获取 wheel URL，再从镜像 CDN 下载；
        若镜像 CDN 下载失败，回退到官方 PyPI JSON API。
        """
        from backend.services.python_resolver import PythonResolver

        # 阶段1：从镜像 Simple API 一次性获取 wheel 链接
        download_url, filename = PythonResolver._get_wheel_from_mirror_simple(
            name, version, python_ver
        )

        if download_url and filename:
            dest_path = PYTHON_DIR / filename
            success, result = await self.download_file(
                download_url, dest_path, task_id, name
            )
            if success:
                return True, result, filename, str(dest_path)
            logger.warning("镜像 CDN 下载失败 ({}): {} - {}", result, name, version)

        # 阶段2：回退到官方 PyPI JSON API 获取下载链接
        logger.info("镜像获取失败，回退官方 PyPI: {} {}", name, version)
        download_url = PythonResolver.get_wheel_download_url(name, version, python_ver)
        filename = PythonResolver.get_wheel_filename(name, version, python_ver)

        if download_url and filename:
            dest_path = PYTHON_DIR / filename
            success, result = await self.download_file(
                download_url, dest_path, task_id, name
            )
            if success:
                return True, result, filename, str(dest_path)
            logger.warning("官方回退也下载失败 ({}): {} - {}", result, name, version)

        error_msg = f"NoWinWheel: 镜像+官方均无法获取 {name}=={version}"
        return False, error_msg, "", ""

    async def download_r_package(
        self,
        name: str,
        version: str,
        r_version: str = "4.3",
        task_id: str = "",
    ) -> tuple[bool, str, str, str, bool]:
        """下载 R 包，返回 (成功?, 错误/SHA256, 文件名, 文件路径, 是否需要Rtools)"""
        from backend.services.r_resolver import RResolver

        # 先尝试 Windows binary
        binary_url = RResolver.get_windows_binary_url(name, version, r_version)

        if binary_url:
            filename = f"{name}_{version}.zip"
            dest_path = R_DIR / filename
            success, result = await self.download_file(binary_url, dest_path, task_id, name)
            if success:
                return True, result, filename, str(dest_path), False

        # 回退到源码包
        source_url = RResolver.get_source_url(name, version)
        if source_url:
            filename = f"{name}_{version}.tar.gz"
            dest_path = R_DIR / filename
            success, result = await self.download_file(source_url, dest_path, task_id, name)
            if success:
                return True, result, filename, str(dest_path), True  # 需要 Rtools

        return False, "NoBinaryOrSource: 无法找到该包的下载链接", "", "", False

    async def download_r_github_package(
        self,
        name: str,
        repo_url: str = "",
        task_id: str = "",
    ) -> tuple[bool, str, str, str, bool]:
        """从 GitHub 下载 R 包源码（非 CRAN 包），返回 (成功?, SHA256/错误, 文件名, 文件路径, 是否需要Rtools)"""
        from backend.services.r_resolver import RResolver

        # 如果没有提供 repo_url，自动搜索
        resolved_repo_url = repo_url
        if not resolved_repo_url:
            repo_info = await asyncio.get_event_loop().run_in_executor(
                None, RResolver.search_github_r_repo, name
            )
            if not repo_info:
                return False, "GitHubRepoNotFound: 未找到匹配的 GitHub R 包仓库", "", "", False
            resolved_repo_url = repo_info["repo_url"]
            logger.info("自动解析到 GitHub R 包仓库: {} -> {}", name, resolved_repo_url)

        # 下载 GitHub 源码
        success, result, filename, filepath = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: RResolver.download_github_r_source(
                resolved_repo_url, name, R_DIR
            ),
        )

        if success:
            await self._notify_progress(task_id, name, "downloaded", 1.0)
            logger.info("GitHub R 包下载完成: {} -> {}", name, filename)
            return True, result, filename, filepath, True  # 源码包安装需要 Rtools

        return False, result, "", "", False

    async def download_runtime(
        self, url: str, filename: str, task_id: str = ""
    ) -> tuple[bool, str]:
        """下载运行时安装包"""
        from backend.config import RUNTIMES_DIR

        dest_path = RUNTIMES_DIR / filename
        return await self.download_file(url, dest_path, task_id, filename)


# 全局单例
downloader = DownloadManager()
