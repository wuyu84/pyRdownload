"""搜索 API（多来源搜索）"""
from fastapi import APIRouter, Query, Request
from backend.models.schemas import SearchResponse, PackageSearchResult, PackageDetail, VersionInfo
from backend.services.python_resolver import PythonResolver
from backend.services.r_resolver import RResolver
from backend.services.source_selector import SourceSelector

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search_packages(
    q: str = Query(..., description="搜索关键词"),
    lang: str = Query("python", description="语言: python / r"),
    source: str = Query("all", description="来源: pypi / cran / github / bioconductor / all"),
):
    """多来源搜索包"""
    if source == "all":
        if lang == "python":
            sources = ["pypi", "github"]
        else:
            sources = ["cran", "bioconductor", "github"]
    else:
        sources = [source]

    results = SourceSelector.search_all_sources(q, lang, sources)

    search_results = []
    for r in results:
        search_results.append(
            PackageSearchResult(
                name=r.get("name", q),
                version=r.get("version", ""),
                lang=lang,
                source=r.get("source", source),
                description=r.get("description", ""),
                has_windows_build=r.get("has_windows_build", True),
            )
        )

    # 如果没有搜索结果
    if not search_results:
        return SearchResponse(results=[])

    return SearchResponse(results=search_results)


@router.get("/package/{lang}/{name}", response_model=PackageDetail)
async def get_package_detail(
    lang: str,
    name: str,
    source: str = Query("pypi", description="来源"),
):
    """包详情+版本列表"""
    versions = []

    if lang == "python":
        ver_list = PythonResolver.get_versions(name)
        for v in ver_list:
            versions.append(
                VersionInfo(
                    version=v["version"],
                    source=v["source"],
                    published_at=v.get("published_at", ""),
                    python_ver=v.get("python_ver", ""),
                )
            )
        return PackageDetail(
            name=name,
            lang=lang,
            versions=versions,
            source=source,
        )
    elif lang == "r":
        ver_list = RResolver.get_versions(name)
        for v in ver_list:
            versions.append(
                VersionInfo(
                    version=v["version"],
                    source=v["source"],
                    published_at=v.get("published_at", ""),
                )
            )
        return PackageDetail(
            name=name,
            lang=lang,
            versions=versions,
            source=source,
        )

    return PackageDetail(name=name, lang=lang, versions=[], source=source)


@router.get("/package/{lang}/{name}/versions")
async def get_package_versions(
    lang: str,
    name: str,
    source: str = Query("pypi", description="来源"),
):
    """历史版本列表（含来源标注）"""
    if lang == "python":
        versions = PythonResolver.get_versions(name)
    elif lang == "r":
        versions = RResolver.get_versions(name)
    else:
        versions = []

    return {"name": name, "lang": lang, "source": source, "versions": versions}


@router.get("/package/{lang}/{name}/dependencies")
async def get_package_dependencies(
    lang: str,
    name: str,
    version: str = Query("", description="版本号，为空则使用最新版"),
    source: str = Query("cran", description="pypi/cran"),
    python_ver: str = Query("", description="Python 版本，仅 Python 包有效"),
):
    """获取包及其依赖列表（用于前端依赖树展示）"""
    from backend.config import PYTHON_VERSIONS

    deps = []
    try:
        import asyncio
        loop = asyncio.get_event_loop()

        if lang == "python":
            if not python_ver:
                python_ver = PYTHON_VERSIONS[-1] if PYTHON_VERSIONS else "3.11"
            # 异步解析依赖，最多等 60 秒
            resolved = await asyncio.wait_for(
                loop.run_in_executor(
                    None, PythonResolver.resolve_dependencies, name, version or None, python_ver
                ),
                timeout=60,
            )
            for dep in resolved:
                deps.append({
                    "name": dep["name"],
                    "version": dep.get("version", ""),
                    "source": dep.get("source", source),
                })
        else:
            resolved = RResolver.resolve_dependencies(name, version or None)
            for dep in resolved:
                deps.append({
                    "name": dep["name"],
                    "version": dep.get("version", ""),
                    "source": dep.get("source", source),
                })
    except asyncio.TimeoutError:
        from loguru import logger
        logger.warning("依赖解析超时: {} {} {}s", lang, name, 60)
        # 超时至少返回主包
        deps = [{"name": name, "version": version or "", "source": source}]
    except Exception as e:
        from loguru import logger
        logger.warning("获取依赖失败: {} {} {}", lang, name, e)

    return {"name": name, "lang": lang, "dependencies": deps}


@router.get("/config/mirrors")
async def get_mirrors():
    """获取镜像源列表"""
    from backend.config import MIRRORS, PYTHON_VERSIONS, R_VERSIONS, SOURCES

    return {
        "mirrors": MIRRORS,
        "python_versions": PYTHON_VERSIONS,
        "r_versions": R_VERSIONS,
        "sources": SOURCES,
    }
