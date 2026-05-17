"""仓库统计 API"""
from fastapi import APIRouter
from backend.services.package_index import PackageIndex

router = APIRouter(prefix="/api", tags=["repository"])


@router.get("/repository/stats")
async def get_repository_stats():
    """获取仓库统计"""
    stats = PackageIndex.get_stats()
    return stats
