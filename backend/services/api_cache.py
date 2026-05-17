"""API 响应缓存层（SQLite 持久化，免重复请求外部 API）"""
import hashlib
import json
from datetime import datetime, timedelta
from loguru import logger
from backend.database import db


class ApiCache:
    """API 响应缓存"""

    # 默认 TTL（秒）
    TTL = {
        "pypi_search": 600,       # PyPI 搜索：10 分钟
        "pypi_metadata": 3600,    # PyPI 包元数据：1 小时
        "pypi_versions": 1800,    # PyPI 版本列表：30 分钟
        "github_search": 300,     # GitHub 搜索：5 分钟
        "cran_metadata": 3600,    # CRAN 元数据：1 小时
    }

    @staticmethod
    def _make_key(url: str) -> str:
        """根据 URL 生成缓存 key"""
        return hashlib.md5(url.encode("utf-8")).hexdigest()

    @staticmethod
    def _detect_type(url: str) -> str:
        """根据 URL 检测缓存类型"""
        if "pypi.org/pypi" in url:
            if url.endswith("/json"):
                return "pypi_metadata"
            return "pypi_search"
        if "api.github.com" in url:
            return "github_search"
        if "cran.r-project.org" in url or "crandb.r-pkg.org" in url:
            return "cran_metadata"
        return "pypi_metadata"

    @staticmethod
    def get(url: str) -> dict | None:
        """从缓存获取，返回解析后的 dict，None 表示缓存不存在或已过期"""
        key = ApiCache._make_key(url)
        row = db.fetchone(
            "SELECT response, expires_at FROM api_cache WHERE cache_key = ?",
            (key,),
        )
        if not row:
            return None

        # 检查是否过期
        expires_at = row.get("expires_at")
        if expires_at:
            try:
                exp = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
                if datetime.now() > exp:
                    # 惰性过期
                    return None
            except (ValueError, TypeError):
                pass

        try:
            return json.loads(row["response"])
        except (json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def set(url: str, data: dict, ttl: int | None = None) -> None:
        """写入缓存"""
        key = ApiCache._make_key(url)
        if ttl is None:
            cache_type = ApiCache._detect_type(url)
            ttl = ApiCache.TTL.get(cache_type, 1800)  # 默认 30 分钟

        expires_at = (datetime.now() + timedelta(seconds=ttl)).strftime("%Y-%m-%d %H:%M:%S")
        response_str = json.dumps(data, ensure_ascii=False, default=str)

        db.execute(
            """INSERT OR REPLACE INTO api_cache (cache_key, url, response, expires_at)
               VALUES (?, ?, ?, ?)""",
            (key, url, response_str, expires_at),
        )

    @staticmethod
    def clear() -> int:
        """清理所有已过期的缓存，返回清理条数"""
        db.execute("DELETE FROM api_cache WHERE expires_at < datetime('now')")
        # 也清理一下超过 7 天的缓存（防止膨胀）
        db.execute(
            "DELETE FROM api_cache WHERE created_at < datetime('now', '-7 days')"
        )
        return 0

    @staticmethod
    def clear_all() -> None:
        """清空全部缓存"""
        db.execute("DELETE FROM api_cache")
        logger.info("API 缓存已全部清空")
