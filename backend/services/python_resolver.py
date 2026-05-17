"""Python 依赖解析器"""
import re
import json
import subprocess
import tempfile
from typing import Optional
from loguru import logger
from backend.database import db


class PythonResolver:
    """Python 包依赖解析（利用 pip 内部 API）"""

    @staticmethod
    def search_pypi(query: str, mirror: str = "") -> list[dict]:
        """搜索 PyPI 包（含缓存 + 镜像优先）"""
        from backend.services.api_cache import ApiCache
        import httpx
        from backend.config import MIRRORS

        # 尝试从镜像源获取 JSON 元数据（速度快）
        # 注意：镜像的 JSON API 格式与官方一致，只是通过国内 CDN 加速
        mirror_json_urls = PythonResolver._get_mirror_json_urls(query)

        for json_url in mirror_json_urls:
            cached = ApiCache.get(json_url)
            if cached:
                info = cached.get("info", {})
                return [
                    {
                        "name": info.get("name", query),
                        "version": info.get("version", ""),
                        "description": (info.get("summary", "") or "")[:200],
                        "source": "pypi",
                        "has_windows_build": True,
                    }
                ]
            try:
                resp = httpx.get(json_url, timeout=20, verify=False)
                if resp.status_code == 200:
                    data = resp.json()
                    ApiCache.set(json_url, data)
                    info = data.get("info", {})
                    logger.info("镜像 JSON 搜索成功: {} <- {}", query, json_url[:50])
                    return [
                        {
                            "name": info.get("name", query),
                            "version": info.get("version", ""),
                            "description": (info.get("summary", "") or "")[:200],
                            "source": "pypi",
                            "has_windows_build": True,
                        }
                    ]
            except Exception:
                continue

        # 回退：官方 PyPI JSON API
        official_url = f"https://pypi.org/pypi/{query}/json"
        cached = ApiCache.get(official_url)
        if cached:
            info = cached.get("info", {})
            return [
                {
                    "name": info.get("name", query),
                    "version": info.get("version", ""),
                    "description": (info.get("summary", "") or "")[:200],
                    "source": "pypi",
                    "has_windows_build": True,
                }
            ]

        try:
            resp = httpx.get(official_url, timeout=30, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                ApiCache.set(official_url, data)
                info = data.get("info", {})
                return [
                    {
                        "name": info.get("name", query),
                        "version": info.get("version", ""),
                        "description": (info.get("summary", "") or "")[:200],
                        "source": "pypi",
                        "has_windows_build": True,
                    }
                ]
            elif resp.status_code == 404:
                return []
            else:
                logger.warning("PyPI search failed: {} {}", resp.status_code, query)
                return []
        except Exception as e:
            logger.error("PyPI search error: {} {}", query, e)
            return []

    @staticmethod
    def _get_mirror_json_urls(name: str) -> list[str]:
        """获取各镜像的 PyPI JSON API URL（镜像源 JSON 接口通常路径不同）"""
        from backend.config import MIRRORS
        mirrors = MIRRORS.get("pypi", {})
        urls = []
        mirror_order = ["清华", "阿里", "豆瓣", "官方"]
        for mirror_name in mirror_order:
            base_url = mirrors.get(mirror_name, "")
            if not base_url:
                continue
            # 镜像 Simple URL 如 https://pypi.tuna.tsinghua.edu.cn/simple
            # 转换为 JSON API URL
            base = base_url.rstrip("/")
            if "pypi.org/simple" in base:
                # 官方源
                pass
            elif "tuna.tsinghua" in base:
                # 清华: /simple/{name}/ → JSON 可能为 /pypi/{name}/json
                urls.append(f"{base.replace('/simple', '')}/pypi/{name}/json")
            elif "aliyun" in base:
                # 阿里云: /simple/{name}/ → JSON 为 /pypi/{name}/json
                urls.append(f"{base.replace('/simple', '')}/pypi/{name}/json")
            elif "douban" in base:
                # 豆瓣: 尝试 /pypi/{name}/json
                urls.append(f"{base.replace('/simple', '')}/pypi/{name}/json")
        return urls

    @staticmethod
    def get_versions(name: str) -> list[dict]:
        """获取包的所有版本（含缓存 + 镜像优先）"""
        from backend.services.api_cache import ApiCache
        import httpx

        # 优先尝试镜像 JSON
        for json_url in PythonResolver._get_mirror_json_urls(name):
            cached = ApiCache.get(json_url)
            if cached:
                return PythonResolver._parse_versions(cached, name)
            try:
                resp = httpx.get(json_url, timeout=20, verify=False)
                if resp.status_code == 200:
                    data = resp.json()
                    ApiCache.set(json_url, data, ttl=1800)
                    return PythonResolver._parse_versions(data, name)
            except Exception:
                continue

        # 回退官方
        official_url = f"https://pypi.org/pypi/{name}/json"
        cached = ApiCache.get(official_url)
        if cached:
            return PythonResolver._parse_versions(cached, name)
        try:
            resp = httpx.get(official_url, timeout=30, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                ApiCache.set(official_url, data, ttl=1800)
                return PythonResolver._parse_versions(data, name)
        except Exception as e:
            logger.error("Get PyPI versions error: {} {}", name, e)
        return []

    @staticmethod
    def _parse_versions(data: dict, name: str) -> list[dict]:
        """从 PyPI JSON 数据解析版本列表"""
        import re
        releases = data.get("releases", {})
        versions = []
        for ver, files in releases.items():
            python_ver = ""
            has_win = any(
                f.get("filename", "").endswith(("win_amd64.whl", "win32.whl", "none-any.whl"))
                for f in files
            )
            for f in files:
                fn = f.get("filename", "")
                if "cp" in fn and re.search(r"cp3\d{1,2}", fn):
                    match = re.search(r"cp3\d{1,2}", fn)
                    if match:
                        py_ver = match.group()
                        python_ver = f"cp{py_ver[2:]}"
                        break
            versions.append({
                "version": ver,
                "source": "pypi",
                "published_at": "",
                "python_ver": python_ver,
                "has_windows_build": has_win,
            })
        return sorted(versions, key=lambda v: v["version"], reverse=True)

    @staticmethod
    def _fetch_json(url: str, timeout: int = 50, retries: int = 2) -> dict | None:
        """获取 JSON，支持重试和缓存（verify=False 绕过 httpx SSL 兼容问题）"""
        from backend.services.api_cache import ApiCache
        import httpx

        # 先查缓存
        cached = ApiCache.get(url)
        if cached:
            return cached

        for attempt in range(retries):
            try:
                resp = httpx.get(url, timeout=timeout, verify=False)
                if resp.status_code == 200:
                    data = resp.json()
                    # 自动写入缓存
                    ApiCache.set(url, data)
                    return data
                return None
            except Exception:
                if attempt < retries - 1:
                    import time
                    time.sleep(2)
                    continue
                return None

    @staticmethod
    def _is_valid_version(version: str) -> bool:
        """检查版本号是否有效（符合PEP 440，过滤如2013d等非标准格式）"""
        import re
        # 符合PEP 440的标准版本格式
        return bool(re.match(r'^\d+\.\d+(\.\d+)?([a-zA-Z0-9.+-]*)?$', version))

    @staticmethod
    def _resolve_specifier(pkg_name: str, spec_str: str) -> str:
        """将版本规格说明符（如 >=1.20,!=1.24.0）解析为实际最新版本号
        优先利用 get_versions 的镜像缓存，免额外网络请求
        无版本约束时返回最新稳定版本
        """
        try:
            from packaging.specifiers import SpecifierSet
            versions = PythonResolver.get_versions(pkg_name)
            if not versions:
                return spec_str

            valid_versions = [v["version"] for v in versions if PythonResolver._is_valid_version(v["version"])]
            if not valid_versions:
                return versions[0]["version"] if versions else spec_str

            # 无版本约束（空字符串）→ 返回最新版本
            if not spec_str:
                logger.debug("版本解析: {} 无约束 → 最新 {}", pkg_name, valid_versions[0])
                return valid_versions[0]

            # 检查是否已是具体版本号（无运算符）
            import re
            if not re.search(r'[<>=!~]', spec_str):
                return spec_str  # 已经是具体版本号

            spec = SpecifierSet(spec_str)
            matching = [v for v in valid_versions if spec.contains(v)]
            if matching:
                resolved = max(matching)
                logger.debug("版本解析: {} {} → {}", pkg_name, spec_str, resolved)
                return resolved
            # 如果没有匹配的版本，返回最新的有效版本
            logger.warning("版本 {} 无匹配，返回最新版本: {}", spec_str, valid_versions[0])
            return valid_versions[0]
        except Exception as e:
            logger.warning("版本解析失败: {} {} - {}", pkg_name, spec_str, e)
            versions = PythonResolver.get_versions(pkg_name)
            if versions:
                valid_versions = [v["version"] for v in versions if PythonResolver._is_valid_version(v["version"])]
                if valid_versions:
                    return valid_versions[0]
                return versions[0]["version"]
            return spec_str

    @staticmethod
    def resolve_dependencies(
        name: str,
        version: Optional[str] = None,
        python_version: str = "3.11",
    ) -> list[dict]:
        """解析依赖树，返回扁平化依赖列表（优先从镜像 JSON 获取数据）"""
        from packaging.requirements import Requirement

        data = None
        # 优先尝试镜像 JSON
        for json_url in PythonResolver._get_mirror_json_urls(name):
            data = PythonResolver._fetch_json(json_url, 25)
            if data:
                break

        # 回退官方
        if not data:
            data = PythonResolver._fetch_json(
                f"https://pypi.org/pypi/{name}/json", 50
            )

        if not data:
            logger.warning("无法获取包信息: {} (镜像+官方均失败)", name)
            return [{"name": name, "version": version or "latest", "source": "pypi"}]

        try:
            info = data.get("info", {})
            result = [{"name": name, "version": version or info.get("version", ""), "source": "pypi"}]

            # 解析 requires_dist → 只列直接依赖名，不递归查版本
            requires_dist = info.get("requires_dist") or []
            for req_str in requires_dist:
                try:
                    req = Requirement(req_str)
                    if req.marker and "extra ==" in str(req.marker):
                        continue
                    if req.name not in [r["name"] for r in result]:
                        # 将规格说明符解析为实际版本号
                        ver = str(req.specifier) if req.specifier else ""
                        resolved_ver = PythonResolver._resolve_specifier(req.name, ver)
                        result.append({
                            "name": req.name,
                            "version": resolved_ver,
                            "source": "pypi",
                        })
                except Exception:
                    continue

            return result

        except Exception as e:
            logger.error("依赖解析失败: {} {}", name, e)
            return [{"name": name, "version": version or "latest", "source": "pypi"}]

    @staticmethod
    def _get_wheel_from_mirror_simple(
        name: str, version: str, python_ver: str = "cp311"
    ) -> tuple[str | None, str | None]:
        """
        通过国内源镜像的 Simple API 获取 wheel 下载链接和文件名。
        返回 (download_url, filename)，均 None 表示全部镜像失败。
        """
        from backend.config import MIRRORS
        import httpx
        import re

        mirrors = MIRRORS.get("pypi", {})
        # 优先尝试国内源
        mirror_order = ["清华", "阿里", "豆瓣", "官方"]

        for mirror_name in mirror_order:
            base_url = mirrors.get(mirror_name)
            if not base_url:
                continue
            simple_url = f"{base_url.rstrip('/')}/{name}/"

            try:
                resp = httpx.get(simple_url, timeout=20, verify=False, follow_redirects=True)
                if resp.status_code != 200:
                    logger.debug("镜像 {} Simple API 返回 {}: {}", mirror_name, resp.status_code, simple_url)
                    continue

                html = resp.text
                # 解析 <a href="...url...">filename</a>
                links = re.findall(
                    r'<a\s+[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', html, re.IGNORECASE
                )

                # 选 wheel 文件
                wheel_links = []
                for href, fn in links:
                    fn = fn.strip()
                    if not fn.endswith(".whl"):
                        continue
                    # 版本匹配
                    norm_version = version.replace("-", ".").replace("_", ".")
                    norm_fn = fn.replace("-", ".").replace("_", ".")
                    if norm_version not in norm_fn:
                        continue
                    wheel_links.append((href, fn))

                if not wheel_links:
                    continue

                # 优先级匹配
                # 1. 精确匹配 python_ver + win_amd64
                for href, fn in wheel_links:
                    if fn.endswith("win_amd64.whl") and python_ver in fn:
                        final_url = href if href.startswith("http") else (
                            simple_url.rstrip("/") + "/" + href.lstrip("/")
                        )
                        logger.info("镜像 {} 命中 wheel: {} | {}", mirror_name, fn, final_url[:80])
                        return final_url, fn

                # 2. 任意 Windows wheel
                for href, fn in wheel_links:
                    if fn.endswith(("win_amd64.whl", "win32.whl")):
                        final_url = href if href.startswith("http") else (
                            simple_url.rstrip("/") + "/" + href.lstrip("/")
                        )
                        logger.info("镜像 {} 命中 Windows wheel: {} | {}", mirror_name, fn, final_url[:80])
                        return final_url, fn

                # 3. 纯 Python wheel（回退）
                for href, fn in wheel_links:
                    if fn.endswith(("py3-none-any.whl", "py2.py3-none-any.whl")):
                        final_url = href if href.startswith("http") else (
                            simple_url.rstrip("/") + "/" + href.lstrip("/")
                        )
                        logger.info("镜像 {} 命中 pure wheel: {} | {}", mirror_name, fn, final_url[:80])
                        return final_url, fn

            except Exception as e:
                logger.warning("镜像 {} Simple API 访问失败: {} - {}", mirror_name, simple_url, e)
                continue

        logger.warning("所有镜像均无法获取 wheel 信息: {} {}", name, version)
        return None, None

    @staticmethod
    def get_wheel_download_url(name: str, version: str, python_ver: str = "cp311") -> str | None:
        """获取 Windows wheel 下载链接（优先从镜像源获取）"""
        # 优先尝试镜像 Simple API（快+直接指向镜像 CDN）
        mirror_url, mirror_fn = PythonResolver._get_wheel_from_mirror_simple(name, version, python_ver)
        if mirror_url:
            return mirror_url

        # 回退：官方 PyPI JSON API
        logger.info("镜像获取失败，回退 PyPI JSON API: {} {}", name, version)
        try:
            data = PythonResolver._fetch_json(
                f"https://pypi.org/pypi/{name}/{version}/json", 50
            )
            if not data:
                return None
            urls = data.get("urls", [])
            # 优先匹配 Python 版本的 win_amd64
            for f in urls:
                fn = f.get("filename", "")
                if fn.endswith("win_amd64.whl") and python_ver in fn:
                    return f["url"]
            # 任意 Windows wheel
            for f in urls:
                fn = f.get("filename", "")
                if fn.endswith(("win_amd64.whl", "win32.whl")):
                    return f["url"]
            # 纯 Python wheel
            for f in urls:
                fn = f.get("filename", "")
                if fn.endswith("py3-none-any.whl") or fn.endswith("py2.py3-none-any.whl"):
                    return f["url"]
            return None
        except Exception as e:
            logger.error("获取下载链接失败: {} {} {}", name, version, e)
            return None

    @staticmethod
    def get_wheel_filename(name: str, version: str, python_ver: str = "cp311") -> str | None:
        """获取 Windows wheel 文件名（优先从镜像源获取）"""
        # 优先尝试镜像 Simple API
        mirror_url, mirror_fn = PythonResolver._get_wheel_from_mirror_simple(name, version, python_ver)
        if mirror_fn:
            return mirror_fn

        # 回退：官方 PyPI JSON API
        logger.info("镜像获取文件名失败，回退 PyPI JSON API: {} {}", name, version)
        try:
            data = PythonResolver._fetch_json(
                f"https://pypi.org/pypi/{name}/{version}/json", 50
            )
            if not data:
                return None
            for f in data.get("urls", []):
                fn = f.get("filename", "")
                if fn.endswith("win_amd64.whl") and python_ver in fn:
                    return fn
            for f in data.get("urls", []):
                fn = f.get("filename", "")
                if fn.endswith(("win_amd64.whl", "win32.whl")):
                    return fn
            for f in data.get("urls", []):
                fn = f.get("filename", "")
                if fn.endswith("py3-none-any.whl") or fn.endswith("py2.py3-none-any.whl"):
                    return fn
            return None
        except Exception as e:
            logger.error("获取文件名失败: {} {} {}", name, version, e)
            return None
