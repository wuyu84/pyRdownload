"""运行时管理 API（Python/R 安装包下载）"""
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pathlib import Path
from loguru import logger
from backend.models.schemas import RuntimeListResponse, RuntimeInfo
from backend.services.runtime_manager import RuntimeManager
from backend.config import RUNTIMES_DIR

router = APIRouter(prefix="/api", tags=["runtimes"])


@router.get("/runtimes", response_model=RuntimeListResponse)
async def get_runtimes():
    """获取可用运行时列表"""
    runtimes = RuntimeManager.get_runtimes()
    runtime_list = []
    for r in runtimes:
        runtime_list.append(
            RuntimeInfo(
                lang=r["lang"],
                version=r["version"],
                arch=r.get("arch", "amd64"),
                filename=r["filename"],
                file_size=r.get("file_size", 0),
                download_url=r.get("download_url", ""),
            )
        )
    return RuntimeListResponse(runtimes=runtime_list)


@router.get("/runtimes/download/{type}/{version}")
async def download_runtime(type: str, version: str):
    """下载运行时安装包"""
    runtime = RuntimeManager.get_runtime_by_version(type, version)
    if not runtime:
        return {"error": f"运行时 {type} {version} 未找到"}

    filepath = runtime.get("filepath", "")
    if not filepath or not Path(filepath).exists():
        return {"error": f"运行时安装包未预置，请先下载: {runtime.get('download_url', '')}"}

    return FileResponse(
        path=filepath,
        filename=runtime["filename"],
        media_type="application/octet-stream",
    )


@router.post("/runtimes/sync")
async def sync_runtimes():
    """手动触发运行时版本检查更新"""
    updated = await RuntimeManager.sync_runtimes()
    return {
        "message": f"同步完成，新增 {len(updated)} 个运行时记录",
        "updated": updated,
    }
