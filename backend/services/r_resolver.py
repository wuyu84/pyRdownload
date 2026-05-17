"""R 依赖解析器"""
import re
from pathlib import Path
from typing import Optional
from loguru import logger


class RResolver:
    """R 包依赖解析（通过 CRAN API）"""

    CRAN_API = "https://cran.r-project.org"
    BIOC_API = "https://bioconductor.org"

    @staticmethod
    def search_cran(query: str, mirror: str = "") -> list[dict]:
        """搜索 CRAN 包"""
        import httpx

        cran_url = mirror or RResolver.CRAN_API
        # 尝试使用 CRAN 的搜索 API
        search_url = f"{cran_url}/web/packages/available_packages.rds"
        # 使用 CRAN JSON API（某些镜像支持）
        json_url = f"https://crandb.r-pkg.org/-/latest"

        try:
            # 先尝试搜索单个包
            pkg_url = f"https://crandb.r-pkg.org/{query}"
            resp = httpx.get(pkg_url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return [
                    {
                        "name": data.get("Package", query),
                        "version": data.get("Version", ""),
                        "description": (data.get("Title", "") or "")[:200],
                        "source": "cran",
                        "has_windows_build": True,
                    }
                ]
            return []
        except Exception as e:
            logger.error("CRAN search error: {} {}", query, e)
            return []

    @staticmethod
    def search_bioconductor(query: str) -> list[dict]:
        """搜索 Bioconductor 包"""
        import httpx

        try:
            url = f"https://bioconductor.org/packages/release/bioc/json/{query}/"
            resp = httpx.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                return [
                    {
                        "name": data.get("Package", query),
                        "version": data.get("Version", ""),
                        "description": (data.get("Title", "") or "")[:200],
                        "source": "bioconductor",
                        "has_windows_build": True,
                    }
                ]
            return []
        except Exception as e:
            logger.error("Bioconductor search error: {} {}", query, e)
            return []

    @staticmethod
    def get_versions(name: str) -> list[dict]:
        """获取包的所有版本（从 CRAN）"""
        import httpx

        try:
            url = f"https://crandb.r-pkg.org/{name}/all"
            resp = httpx.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                versions_data = data.get("versions", {})
                timeline = data.get("timeline", {})
                versions = []
                for ver_key, ver_data in versions_data.items():
                    # ver_data 是 dict，包含 Package/Title/Version 等字段
                    if not isinstance(ver_data, dict):
                        continue
                    versions.append({
                        "version": ver_key,
                        "source": "cran",
                        "published_at": timeline.get(ver_key, ""),
                        "python_ver": "",
                        "has_windows_build": True,
                    })
                return sorted(versions, key=lambda v: v["version"], reverse=True)
            return []
        except Exception as e:
            logger.error("Get CRAN versions error: {} {}", name, e)
            return []

    @staticmethod
    def _parse_dep_list(dep_list) -> list[dict]:
        """统一解析 Depends/Imports/LinkingTo（支持 dict 和 str 两种格式）"""
        # R系统内置包，不需要下载
        EXCLUDED = {
            "R", "methods", "utils", "stats", "graphics", "grDevices",
            "grid", "base", "compiler", "datasets", "parallel",
            "splines", "stats4", "tcltk", "tools", "nlme", "MASS"
        }
        deps = []
        if isinstance(dep_list, dict):
            for dep_name, dep_version in dep_list.items():
                if dep_name in EXCLUDED:
                    continue
                ver_spec = dep_version if dep_version and dep_version != "*" else ""
                deps.append({"name": dep_name, "version_spec": ver_spec, "source": "cran"})
        elif isinstance(dep_list, str):
            for dep_item in re.split(r",\s*", dep_list.strip(" \n")):
                dep_item = dep_item.strip()
                if not dep_item:
                    continue
                m = re.match(r"([\w.]+)\s*(\(.*?\))?", dep_item)
                if m and m.group(1) not in EXCLUDED:
                    deps.append({"name": m.group(1), "version_spec": m.group(2) or "", "source": "cran"})
        return deps

    @staticmethod
    def resolve_dependencies(
        name: str,
        version: Optional[str] = None,
    ) -> list[dict]:
        """解析 R 包依赖（含递归）"""
        import httpx

        try:
            pkg_url = f"https://crandb.r-pkg.org/{name}"
            resp = httpx.get(pkg_url, timeout=15)
            if resp.status_code != 200:
                return [{"name": name, "version": version or "latest", "source": "cran"}]

            data = resp.json()
            pkg_version = version or data.get("Version", "")

            result = [{"name": name, "version": pkg_version, "source": "cran"}]

            # 获取所有直接依赖
            deps = []
            for dep_type in ("Depends", "Imports", "LinkingTo"):
                deps.extend(RResolver._parse_dep_list(data.get(dep_type, "")))

            # 递归解析间接依赖
            for dep in deps:
                dep_name = dep["name"]
                if dep_name in [r["name"] for r in result]:
                    continue
                try:
                    dep_resp = httpx.get(f"https://crandb.r-pkg.org/{dep_name}", timeout=10)
                    if dep_resp.status_code == 200:
                        dep_data = dep_resp.json()
                        result.append({
                            "name": dep_name,
                            "version": dep_data.get("Version", ""),
                            "source": "cran",
                        })
                        # 解析子依赖
                        sub_deps = []
                        for dt in ("Depends", "Imports", "LinkingTo"):
                            sub_deps.extend(RResolver._parse_dep_list(dep_data.get(dt, "")))
                        for sub_name in sub_deps:
                            sn = sub_name["name"]
                            if sn not in [r["name"] for r in result]:
                                try:
                                    sub_resp = httpx.get(
                                        f"https://crandb.r-pkg.org/{sn}", timeout=10
                                    )
                                    if sub_resp.status_code == 200:
                                        sub_data = sub_resp.json()
                                        result.append({
                                            "name": sn,
                                            "version": sub_data.get("Version", ""),
                                            "source": "cran",
                                        })
                                except Exception:
                                    result.append({
                                        "name": sn,
                                        "version": "",
                                        "source": "cran",
                                    })
                except Exception as e:
                    logger.warning("解析R依赖失败: {} {}", dep_name, e)
                    result.append({
                        "name": dep_name,
                        "version": dep.get("version_spec", ""),
                        "source": "cran",
                    })

            # 去重
            seen = set()
            unique_result = []
            for item in result:
                key = f"{item['name']}-{item['version']}"
                if key not in seen:
                    seen.add(key)
                    unique_result.append(item)

            return unique_result

        except Exception as e:
            logger.error("R 依赖解析失败: {} {}", name, e)
            return [{"name": name, "version": version or "latest", "source": "cran"}]

    @staticmethod
    def get_windows_binary_url(name: str, version: str, r_version: str = "4.3") -> str | None:
        """获取 Windows binary (.zip) 下载链接"""
        import httpx

        # 优先在用户指定的 R 版本路径下查找，再尝试其他版本
        preferred = [r_version] + [v for v in ["4.4", "4.3", "4.2", "4.1", "4.0"] if v != r_version]
        for r_ver in preferred:
            url = f"{RResolver.CRAN_API}/bin/windows/contrib/{r_ver}/{name}_{version}.zip"
            try:
                resp = httpx.get(url, timeout=10, headers={"Range": "bytes=0-1"})
                if resp.status_code in (200, 206):
                    return url
            except Exception:
                continue
        return None

    @staticmethod
    def get_source_url(name: str, version: str) -> str | None:
        """获取源码包 (.tar.gz) 下载链接"""
        return f"{RResolver.CRAN_API}/src/contrib/{name}_{version}.tar.gz"

    # ── GitHub R 包支持 ──────────────────────────────────────

    @staticmethod
    def search_github_r_repo(name: str) -> dict | None:
        """通过 GitHub 搜索查找 R 包仓库，返回仓库信息"""
        import httpx
        from backend.config import GITHUB_TOKEN, GITHUB_API_URL

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "pkg-downloader/1.0",
        }
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        try:
            # 精确搜索仓库名 + R 语言
            url = f"{GITHUB_API_URL}/search/repositories"
            params = {"q": f"{name} in:name language:r", "sort": "stars", "per_page": 5}
            resp = httpx.get(url, headers=headers, params=params, timeout=15)

            if resp.status_code != 200:
                logger.warning("GitHub repo search failed: {} {}", resp.status_code, name)
                return None

            data = resp.json()
            for item in data.get("items", []):
                repo_name = item.get("name", "")
                # 精确匹配包名（忽略大小写）
                if repo_name.lower() == name.lower():
                    return {
                        "owner": item["owner"]["login"],
                        "repo": repo_name,
                        "default_branch": item.get("default_branch", "main"),
                        "repo_url": item.get("html_url", ""),
                    }

            # 没找到精确匹配，返回第一个结果（如果有的话）
            if data.get("items"):
                first = data["items"][0]
                logger.info("GitHub R 包未精确匹配 '{}'，使用最接近结果: {}/{}",
                            name, first["owner"]["login"], first["name"])
                return {
                    "owner": first["owner"]["login"],
                    "repo": first["name"],
                    "default_branch": first.get("default_branch", "main"),
                    "repo_url": first.get("html_url", ""),
                }

            return None

        except Exception as e:
            logger.error("GitHub R repo search error: {} {}", name, e)
            return None

    @staticmethod
    def _extract_version_from_gh_archive(archive_path: Path) -> str:
        """从 GitHub 下载的 R 包 tarball 中提取版本号"""
        import tarfile

        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                # 查找 DESCRIPTION 文件（在第一级子目录中）
                desc_members = [m for m in tar.getmembers()
                                if m.name.endswith("/DESCRIPTION") and m.name.count("/") == 1]
                if desc_members:
                    f = tar.extractfile(desc_members[0])
                    if f:
                        content = f.read().decode("utf-8", errors="replace")
                        m = re.search(r"^Version:\s*(\S+)", content, re.MULTILINE)
                        if m:
                            return m.group(1)
        except Exception as e:
            logger.warning("从 GitHub 归档提取版本号失败: {}", e)

        return ""

    @staticmethod
    def download_github_r_source(
        repo_url: str, name: str, dest_dir: Path
    ) -> tuple[bool, str, str, str]:
        """
        从 GitHub 下载 R 包源码，打包为标准 .tar.gz 格式（顶层目录为包名）
        返回: (成功?, SHA256/错误, 文件名, 文件路径)
        """
        import httpx
        import hashlib
        import tarfile
        import tempfile
        import shutil
        from backend.config import GITHUB_TOKEN

        # 从 URL 解析 owner/repo
        parts = repo_url.rstrip("/").split("/")
        if len(parts) < 2:
            return False, f"InvalidRepoURL: {repo_url}", "", ""
        owner = parts[-2]
        repo = parts[-1]

        # GitHub 源码归档 URL
        archive_url = f"https://api.github.com/repos/{owner}/{repo}/tarball"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "pkg-downloader/1.0",
        }
        if GITHUB_TOKEN:
            headers["Authorization"] = f"token {GITHUB_TOKEN}"

        try:
            logger.info("正在从 GitHub 下载 R 包源码: {}/{}", owner, repo)
            resp = httpx.get(archive_url, headers=headers, follow_redirects=True, timeout=120)
            if resp.status_code != 200:
                return False, f"GitHubDownloadFailed: HTTP {resp.status_code}", "", ""

            dest_dir.mkdir(parents=True, exist_ok=True)

            # 下载原始归档到临时文件
            tmp_archive = dest_dir / f"{name}_gh_tmp.tar.gz"
            with open(tmp_archive, "wb") as f:
                f.write(resp.content)

            # 读取版本号（从 DESCRIPTION）
            version = RResolver._extract_version_from_gh_archive(tmp_archive)
            version_part = f"_{version}" if version else ""
            final_name = f"{name}{version_part}.tar.gz"
            final_path = dest_dir / final_name

            # 重新打包：将顶层目录标准化为 {name}/
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                # 解压原始归档
                with tarfile.open(tmp_archive, "r:gz") as tar:
                    # 获取顶层目录名
                    members = tar.getmembers()
                    if not members:
                        return False, "EmptyArchive: GitHub 返回空归档", "", ""
                    top_dir = members[0].name.split("/")[0]

                    # 解压到临时目录
                    tar.extractall(tmp_path)

                # 将顶层目录重命名为包名
                src_pkg_dir = tmp_path / top_dir
                dst_pkg_dir = tmp_path / name
                if src_pkg_dir.exists() and src_pkg_dir.is_dir():
                    if dst_pkg_dir.exists():
                        shutil.rmtree(dst_pkg_dir)
                    src_pkg_dir.rename(dst_pkg_dir)

                # 重新打包为标准格式
                with tarfile.open(final_path, "w:gz") as tar:
                    tar.add(dst_pkg_dir, arcname=name)

            # 清理临时归档
            if tmp_archive.exists():
                tmp_archive.unlink()

            # 计算 SHA256
            sha256_val = hashlib.sha256()
            with open(final_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256_val.update(chunk)

            logger.info("GitHub R 包下载完成: {} ({} bytes, version={})",
                        final_name, final_path.stat().st_size, version or "unknown")
            return True, sha256_val.hexdigest(), final_name, str(final_path)

        except httpx.TimeoutException:
            return False, "GitHubTimeout: 下载 GitHub 源码超时", "", ""
        except Exception as e:
            logger.error("GitHub R 包下载失败: {}/{}, {}", owner, repo, e)
            return False, f"GitHubRDownloadError: {str(e)[:60]}", "", ""
