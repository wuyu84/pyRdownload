"""FastAPI 入口"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from loguru import logger

from backend.config import SERVER_PORT, HOST, LOG_LEVEL
from backend.database import db
from backend.services.runtime_manager import RuntimeManager


# 配置日志
logger.remove()
logger.add(sys.stdout, level=LOG_LEVEL)
logger.add("logs/pkg-downloader.log", rotation="10 MB", retention="7 days", level="INFO")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    logger.info("Python&R包下载器启动中...")
    try:
        RuntimeManager.scan_local_runtimes()
        logger.info("运行时扫描完成")
    except Exception as e:
        logger.warning("运行时扫描失败: {}", e)
    yield
    logger.info("Python&R包下载器关闭")


app = FastAPI(
    title="Python&R包下载器",
    description="在内网/离线环境中下载 Python 和 R 包及其全部依赖",
    version="1.5.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 健康检查（必须在静态文件挂载前）──
@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "version": "1.5.0"}


# ── 注册路由 ──
from backend.routers import search, download, tasks, repository, runtimes

app.include_router(search.router)
app.include_router(download.router)
app.include_router(tasks.router)
app.include_router(repository.router)
app.include_router(runtimes.router)


# ── 前端 SPA 静态文件服务（支持 Vue Router history 模式回退）──
class SPAStaticFiles(StaticFiles):
    """未匹配的前端路径回退到 index.html（但 /api/ 路径保持原始 404）"""
    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code == 404 and not path.startswith("api/"):
                return await super().get_response("index.html", scope)
            raise

frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", SPAStaticFiles(directory=str(frontend_dist), html=True), name="frontend")
    logger.info("前端静态文件已挂载: {}", frontend_dist)
else:
    logger.warning("前端静态文件不存在，请构建前端: {}", frontend_dist)


# ── 错误处理 ──
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("全局异常: {} {}", request.url, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=SERVER_PORT,
        reload=False,
        log_level=LOG_LEVEL.lower(),
    )
