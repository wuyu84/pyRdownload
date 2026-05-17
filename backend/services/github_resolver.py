"""GitHub Releases 搜索与下载"""
import re
from typing import Optional
from loguru import logger
from backend.config import GITHUB_TOKEN, GITHUB_API_URL


class GitHubResolver:
    """GitHub Releases 搜索与下载"""

    @staticmethod
    def _get_headers() -> dict:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "pkg-downloader/1.0",
        }
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"
        return headers

    @staticmethod
    def search_releases(query: str, lang: str = "python") -> list[dict]:
        """搜索 GitHub Releases 中的 Python/R 包"""
        import httpx

        # 构建搜索查询
        if lang == "python":
            search_query = f"{query} language:python"
            file_ext = ".whl"
        else:
            search_query = f"{query} language:r"
            file_ext = ".zip"

        try:
            url = f"{GITHUB_API_URL}/search/repositories"
            params = {"q": search_query, "sort": "stars", "order": "desc", "per_page": 10}

            resp = httpx.get(url, headers=GitHubResolver._get_headers(), params=params, timeout=15)

            if resp.status_code == 403:
                logger.warning("GitHub API 频率限制，请配置 GITHUB_TOKEN")
                return [
                    {
                        "name": query,
                        "version": "unknown",
                        "description": "GitHub API 频率限制，无法搜索",
                        "source": "github",
                        "has_windows_build": False,
                        "error": "rate_limit",
                    }
                ]

            if resp.status_code != 200:
                logger.warning("GitHub search failed: {} {}", resp.status_code, query)
                return []

            data = resp.json()
            results = []
            for item in data.get("items", [])[:5]:
                results.append({
                    "name": item.get("name", query),
                    "version": f"latest ({item.get('default_branch', 'main')})",
                    "description": (item.get("description", "") or "")[:200],
                    "source": "github",
                    "has_windows_build": True,
                    "repo_url": item.get("html_url", ""),
                    "stars": item.get("stargazers_count", 0),
                })

            return results

        except Exception as e:
            logger.error("GitHub search error: {} {}", query, e)
            return []

    @staticmethod
    def get_releases(repo_full_name: str) -> list[dict]:
        """获取仓库的 Releases 列表"""
        import httpx

        try:
            url = f"{GITHUB_API_URL}/repos/{repo_full_name}/releases"
            params = {"per_page": 20}

            resp = httpx.get(url, headers=GitHubResolver._get_headers(), params=params, timeout=15)

            if resp.status_code != 200:
                return []

            releases = []
            for item in resp.json():
                tag = item.get("tag_name", "")
                version = tag.lstrip("v")
                releases.append({
                    "version": version,
                    "source": "github",
                    "published_at": item.get("published_at", "")[:10],
                    "python_ver": "",
                    "has_windows_build": True,
                })

            return releases

        except Exception as e:
            logger.error("GitHub releases error: {} {}", repo_full_name, e)
            return []

    @staticmethod
    def get_asset_download_url(repo_full_name: str, version: str, file_pattern: str = "") -> list[dict]:
        """获取 Release 中的文件下载链接"""
        import httpx

        try:
            # 通过 tag 查找 release
            tag = f"v{version}" if not version.startswith("v") else version
            url = f"{GITHUB_API_URL}/repos/{repo_full_name}/releases/tags/{tag}"

            resp = httpx.get(url, headers=GitHubResolver._get_headers(), timeout=15)

            if resp.status_code != 200:
                # 尝试不带 v 前缀
                tag = version
                url = f"{GITHUB_API_URL}/repos/{repo_full_name}/releases/tags/{tag}"
                resp = httpx.get(url, headers=GitHubResolver._get_headers(), timeout=15)

            if resp.status_code != 200:
                return []

            data = resp.json()
            assets = []
            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if file_pattern and file_pattern not in name:
                    continue
                assets.append({
                    "name": name,
                    "url": asset.get("browser_download_url", ""),
                    "size": asset.get("size", 0),
                    "content_type": asset.get("content_type", ""),
                })

            return assets

        except Exception as e:
            logger.error("GitHub asset error: {} {} {}", repo_full_name, version, e)
            return []
