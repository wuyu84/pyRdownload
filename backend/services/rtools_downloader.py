"""Rtools 下载器"""
from pathlib import Path
from loguru import logger
from backend.config import RTOOLS_URL, R_DIR


class RtoolsDownloader:
    """Rtools 安装包下载管理"""

    @staticmethod
    def get_rtools_filename() -> str:
        """获取 Rtools 文件名"""
        return Path(RTOOLS_URL).name

    @staticmethod
    def get_rtools_path() -> Path:
        """获取 Rtools 本地路径"""
        return R_DIR / RtoolsDownloader.get_rtools_filename()

    @staticmethod
    def is_rtools_downloaded() -> bool:
        """检查 Rtools 是否已下载"""
        return RtoolsDownloader.get_rtools_path().exists()

    @staticmethod
    async def download_rtools(task_id: str = "") -> tuple[bool, str, str]:
        """下载 Rtools"""
        from backend.services.downloader import downloader

        filename = RtoolsDownloader.get_rtools_filename()
        dest_path = R_DIR / filename

        if dest_path.exists():
            logger.info("Rtools 已存在，跳过下载")
            return True, "已存在", str(dest_path)

        success, result = await downloader.download_file(
            RTOOLS_URL, dest_path, task_id, "Rtools"
        )

        if success:
            return True, result, str(dest_path)
        else:
            return False, result, ""
