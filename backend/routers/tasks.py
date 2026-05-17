"""任务一览表 + 搜索 + 一键复用"""
from pathlib import Path
from fastapi import APIRouter, Query, Request
from loguru import logger
from backend.models.schemas import TaskListResponse, TaskDetail, TaskListItem
from backend.services.task_manager import TaskManager
from backend.services.package_index import PackageIndex
from backend.services.packager import Packager
from backend.database import db

router = APIRouter(prefix="/api", tags=["tasks"])


@router.get("/tasks")
async def get_task_list_v2(
    lang: str = Query("", description="语言过滤"),
    status: str = Query("", description="状态过滤"),
    search: str = Query("", description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """任务一览表"""
    result = TaskManager.get_task_list(
        lang=lang, status=status, search=search,
        page=page, page_size=page_size,
    )
    tasks = []
    for t in result["tasks"]:
        tasks.append(
            TaskListItem(
                id=t["id"],
                lang=t["lang"],
                source=t.get("source", ""),
                package_name=t["package_name"],
                package_version=t.get("package_version"),
                status=t["status"],
                total_pkgs=t.get("total_pkgs", 0),
                cached_pkgs=t.get("cached_pkgs", 0),
                downloaded_pkgs=t.get("downloaded_pkgs", 0),
                failed_pkgs=t.get("failed_pkgs", 0),
                file_size=t.get("file_size", 0),
                client_ip=t["client_ip"],
                created_at=t.get("created_at", ""),
                finished_at=t.get("finished_at"),
            )
        )
    return TaskListResponse(tasks=tasks, total=result["total"])


@router.get("/tasks/search")
async def search_tasks(
    q: str = Query(..., description="搜索关键词"),
    lang: str = Query("", description="语言"),
    source: str = Query("", description="来源"),
):
    """搜索历史任务"""
    tasks = TaskManager.search_tasks(query=q, lang=lang, source=source)
    return {"tasks": tasks}


@router.get("/tasks/{task_id}")
async def get_task_detail(task_id: str):
    """任务详情"""
    task = TaskManager.get_task(task_id)
    if not task:
        return {"error": "任务不存在"}

    packages = []
    for p in task.get("packages", []):
        packages.append({
            "pkg_name": p["pkg_name"],
            "pkg_version": p.get("pkg_version", ""),
            "lang": p.get("lang", ""),
            "source": p.get("source", ""),
            "status": p["status"],
            "is_cached": bool(p.get("is_cached", 0)),
            "error_msg": p.get("error_msg"),
            "friendly_error": p.get("friendly_error"),
        })

    return TaskDetail(
        id=task["id"],
        lang=task["lang"],
        source=task.get("source", ""),
        package_name=task["package_name"],
        package_version=task.get("package_version"),
        python_ver=task.get("python_ver"),
        r_ver=task.get("r_ver"),
        status=task["status"],
        total_pkgs=task.get("total_pkgs", 0),
        cached_pkgs=task.get("cached_pkgs", 0),
        downloaded_pkgs=task.get("downloaded_pkgs", 0),
        failed_pkgs=task.get("failed_pkgs", 0),
        file_size=task.get("file_size", 0),
        export_path=task.get("export_path"),
        client_ip=task["client_ip"],
        created_at=task.get("created_at", ""),
        finished_at=task.get("finished_at"),
        packages=packages,
    )


@router.post("/tasks/{task_id}/reuse")
async def reuse_task(task_id: str):
    """一键复用：检查完整性 → 打包 → 返回下载链接"""
    task = TaskManager.get_task(task_id)
    if not task:
        return {"error": "任务不存在"}

    packages = task.get("packages", [])
    if not packages:
        return {"error": "任务无包记录"}

    # 检查完整性
    missing_pkgs = []
    all_packages = []
    for p in packages:
        file_path = p.get("file_path")
        if not file_path or not Path(file_path).exists():
            missing_pkgs.append(p["pkg_name"])
        else:
            all_packages.append(p)

    if missing_pkgs:
        return {
            "error": "部分包已从仓库移除",
            "missing_packages": missing_pkgs,
            "hint": "是否补充下载后打包？",
        }

    # 直接打包
    success, zip_path = Packager.create_package(
        task_id=task_id,
        packages=all_packages,
        source=task.get("source", ""),
        lang=task["lang"],
        include_runtime=False,
        python_ver=task.get("python_ver", ""),
    )

    if success:
        return {
            "success": True,
            "export_path": zip_path,
            "message": "打包完成，可下载",
        }
    else:
        return {"error": f"打包失败: {zip_path}"}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """删除任务记录（不删仓库包文件）"""
    TaskManager.delete_task(task_id)
    return {"message": "任务已删除"}
