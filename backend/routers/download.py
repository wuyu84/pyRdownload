"""下载 API + WebSocket 实时进度"""
import asyncio
import json
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from loguru import logger
from backend.models.schemas import DownloadRequest, DownloadResponse
from backend.services.python_resolver import PythonResolver
from backend.services.r_resolver import RResolver
from backend.services.downloader import downloader
from backend.services.package_index import PackageIndex
from backend.services.packager import Packager
from backend.services.task_manager import TaskManager
from backend.services.rtools_downloader import RtoolsDownloader
from backend.config import RUNTIMES_DIR

router = APIRouter(prefix="/api", tags=["download"])

# 活跃的 WebSocket 连接
active_connections: dict[str, list[WebSocket]] = {}


async def broadcast_progress(
    task_id: str,
    pkg_name: str,
    status: str,
    progress: float = 0,
    message: str = "",
):
    """广播进度到所有 WebSocket 连接"""
    if task_id in active_connections:
        data = json.dumps({
            "task_id": task_id,
            "pkg_name": pkg_name,
            "status": status,
            "progress": progress,
            "message": message,
        })
        for ws in active_connections[task_id][:]:
            try:
                await ws.send_text(data)
            except Exception:
                active_connections[task_id].remove(ws)


@router.websocket("/ws/download/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """WebSocket 实时进度"""
    await websocket.accept()
    if task_id not in active_connections:
        active_connections[task_id] = []
    active_connections[task_id].append(websocket)
    logger.info("WebSocket 连接: {}", task_id)

    try:
        # 保持连接
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if task_id in active_connections:
            active_connections[task_id].remove(websocket)
            if not active_connections[task_id]:
                del active_connections[task_id]
        logger.info("WebSocket 断开: {}", task_id)


@router.post("/download", response_model=DownloadResponse)
async def start_download(
    req: DownloadRequest,
    request: Request,
):
    """触发下载任务"""
    client_ip = request.client.host if request.client else "unknown"
    packages = req.packages

    if not packages:
        return DownloadResponse(task_id="", message="包列表为空")

    main_pkg = packages[0]
    pkg_name = main_pkg.get("name", "")
    pkg_version = main_pkg.get("version")

    # 创建任务
    task_id = TaskManager.create_task(
        lang=req.lang,
        package_name=pkg_name,
        package_version=pkg_version,
        source=req.source,
        client_ip=client_ip,
        python_ver=req.python_version,
        r_ver=req.r_version,
    )

    # 在后台执行下载
    asyncio.create_task(
        _execute_download(task_id, req)
    )

    return DownloadResponse(task_id=task_id, message="任务已创建")


async def _execute_download(task_id: str, req: DownloadRequest):
    """执行下载任务"""
    try:
        TaskManager.update_task_status(task_id, "downloading")

        # 注册进度回调：DownloadManager 内部的 _notify_progress → WebSocket 广播
        downloader.on_progress(task_id, broadcast_progress)

        # 根据语言设置版本参数
        if req.lang == "python":
            python_ver = req.python_version or "3.11"
            cp_ver = f"cp{python_ver.replace('.', '')}"
            r_ver = None
        else:
            python_ver = None
            cp_ver = ""
            r_ver = req.r_version or "4.3"

        # 1. 解析依赖
        all_packages = []
        for pkg in req.packages:
            name = pkg.get("name", "")
            version = pkg.get("version")

            if req.lang == "python":
                loop = asyncio.get_event_loop()
                deps = await loop.run_in_executor(
                    None, PythonResolver.resolve_dependencies, name, version, python_ver
                )
            elif req.lang == "r" and req.source == "github":
                # GitHub 源 R 包：跳过 CRAN 依赖解析，仅下载主包本身
                deps = [{"name": name, "version": version or "", "source": "github"}]
            else:
                # CRAN / Bioconductor 源 R 包
                deps = RResolver.resolve_dependencies(name, version)

            for dep in deps:
                dep["lang"] = req.lang
                dep["source"] = req.source
                dep["python_ver"] = cp_ver if req.lang == "python" else ""
            all_packages.extend(deps)

        # 去重
        seen = set()
        unique_packages = []
        for pkg in all_packages:
            key = f"{pkg['name']}-{pkg.get('version', '')}"
            if key not in seen:
                seen.add(key)
                unique_packages.append(pkg)

        # 2. 与仓库比对
        check_results = PackageIndex.batch_check(unique_packages)

        # 3. 逐个处理包
        cached_count = 0
        downloaded_count = 0
        failed_count = 0
        need_rtools = False

        for pkg in unique_packages:
            pkg_key = f"{pkg['name']}-{pkg.get('version', '')}"
            check = check_results.get(pkg_key, {})

            if check.get("exists"):
                # 复用
                record = check["record"]
                TaskManager.add_task_package(
                    task_id=task_id,
                    pkg_name=pkg["name"],
                    pkg_version=pkg.get("version", ""),
                    lang=req.lang,
                    source=req.source,
                    status="cached",
                    is_cached=True,
                    file_path=record["filepath"],
                )
                cached_count += 1
                await broadcast_progress(
                    task_id, pkg["name"], "cached", 1.0, "📦 仓库复用"
                )
            else:
                # 需要下载
                TaskManager.add_task_package(
                    task_id=task_id,
                    pkg_name=pkg["name"],
                    pkg_version=pkg.get("version", ""),
                    lang=req.lang,
                    source=req.source,
                    status="downloading",
                )
                await broadcast_progress(
                    task_id, pkg["name"], "downloading", 0, "⏳ 下载中"
                )

                try:
                    if req.lang == "python":
                        success, sha256, filename, filepath = (
                            await downloader.download_python_package(
                                pkg["name"],
                                pkg.get("version", ""),
                                cp_ver,
                                task_id,
                            )
                        )
                    elif pkg.get("source") == "github":
                        # GitHub 源 R 包：从 GitHub 下载源码
                        success, sha256, filename, filepath, needs_rtools = (
                            await downloader.download_r_github_package(
                                pkg["name"],
                                repo_url="",
                                task_id=task_id,
                            )
                        )
                        if needs_rtools:
                            need_rtools = True
                    else:
                        success, sha256, filename, filepath, needs_rtools = (
                            await downloader.download_r_package(
                                pkg["name"],
                                pkg.get("version", ""),
                                r_ver,
                                task_id,
                            )
                        )
                        if needs_rtools:
                            need_rtools = True

                    if success:
                        # 添加到索引
                        platform = PackageIndex.detect_platform(filename)
                        PackageIndex.add_package(
                            name=pkg["name"],
                            version=pkg.get("version", ""),
                            lang=req.lang,
                            platform=platform,
                            filename=filename,
                            filepath=filepath,
                            source=req.source,
                            python_ver=cp_ver if req.lang == "python" else "",
                            sha256=sha256,
                        )
                        TaskManager.update_task_package_status(
                            task_id, pkg["name"], "downloaded",
                            file_path=filepath,
                        )
                        downloaded_count += 1
                        await broadcast_progress(
                            task_id, pkg["name"], "downloaded", 1.0, "✅ 下载完成"
                        )
                    else:
                        TaskManager.update_task_package_status(
                            task_id, pkg["name"], "failed",
                            error_msg=sha256,
                        )
                        failed_count += 1
                        await broadcast_progress(
                            task_id, pkg["name"], "failed", 0, f"❌ {sha256}"
                        )
                except Exception as e:
                    TaskManager.update_task_package_status(
                        task_id, pkg["name"], "failed", error_msg=str(e)
                    )
                    failed_count += 1
                    await broadcast_progress(
                        task_id, pkg["name"], "failed", 0, f"❌ {str(e)[:50]}"
                    )

                # 更新任务计数
                TaskManager.update_task_counts(task_id)

        # 4. 下载 Rtools（如果需要）
        if need_rtools and not RtoolsDownloader.is_rtools_downloaded():
            await broadcast_progress(task_id, "Rtools", "downloading", 0, "⏳ 下载 Rtools")
            await RtoolsDownloader.download_rtools(task_id)
            await broadcast_progress(task_id, "Rtools", "downloaded", 1.0, "✅ Rtools 下载完成")

        # 5. 打包
        TaskManager.update_task_status(task_id, "packaging")
        await broadcast_progress(task_id, "", "packaging", 0, "📦 正在打包...")

        # 获取所有已下载/复用的包文件
        task_packages = TaskManager.get_task(task_id)["packages"]

        runtime_info = None
        if req.include_runtime:
            if req.lang == "python" and req.python_version:
                runtime_info = PackageIndex.get_runtime_info("python", req.python_version)
            elif req.lang == "r" and req.r_version:
                runtime_info = PackageIndex.get_runtime_info("r", req.r_version)

        success, zip_path = Packager.create_package(
            task_id=task_id,
            packages=task_packages,
            source=req.source,
            lang=req.lang,
            include_runtime=req.include_runtime,
            runtime_info=runtime_info,
            python_ver=cp_ver if req.lang == "python" else "",
            has_rtools=need_rtools,
        )

        if success:
            await broadcast_progress(
                task_id, "", "done", 1.0, f"✅ 打包完成: {Path(zip_path).name}"
            )
        else:
            await broadcast_progress(
                task_id, "", "failed", 0, f"❌ 打包失败: {zip_path}"
            )

    except Exception as e:
        logger.error("下载任务执行异常: {} {}", task_id, e)
        TaskManager.update_task_status(task_id, "failed")
        await broadcast_progress(task_id, "", "failed", 0, f"❌ 任务异常: {str(e)[:100]}")


@router.get("/download/{task_id}/status")
async def get_task_status(task_id: str):
    """获取任务状态"""
    task = TaskManager.get_task(task_id)
    if not task:
        return {"error": "任务不存在"}
    return task


@router.get("/download/{task_id}/export")
async def download_export(request: Request, task_id: str):
    """下载打包文件"""
    from fastapi.responses import FileResponse

    task = TaskManager.get_task(task_id)
    if not task:
        return {"error": "任务不存在"}

    export_path = task.get("export_path")
    if not export_path or not Path(export_path).exists():
        return {"error": "打包文件不存在"}

    return FileResponse(
        path=export_path,
        filename=Path(export_path).name,
        media_type="application/zip",
    )


@router.post("/github/search")
async def search_github(req_data: dict):
    """搜索 GitHub Releases"""
    from backend.services.github_resolver import GitHubResolver

    q = req_data.get("q", "")
    lang = req_data.get("lang", "python")
    results = GitHubResolver.search_releases(q, lang)
    return {"results": results}
