"""FastAPI 应用入口。

- 启动时执行 Alembic 迁移（`liberastra.core.db.run_migrations`）。
- lifespan 中启动 Job worker（SQLite 队列 + asyncio），关闭时停止。
- `/api/v1` 挂载原生 REST 路由；`/healthz` 供健康检查。
- 若存在前端构建产物，则以 SPA 方式托管（未知路径回退 index.html）。
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from liberastra import __version__
from liberastra.api import api_router, openai_audio
from liberastra.core.config import get_settings
from liberastra.core.db import run_migrations
from liberastra.core.logging import setup_logging
from liberastra.jobs.manager import JobManager
from liberastra.services.asr import register_asr_jobs
from liberastra.services.llm import register_llm_jobs
from liberastra.services.tts import register_tts_jobs


class SPAStaticFiles(StaticFiles):
    """静态文件托管，404 时回退 index.html（React Router 前端路由）。"""

    async def get_response(self, path: str, scope):  # noqa: ANN001, ANN201
        from starlette.exceptions import HTTPException as StarletteHTTPException

        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.debug)
    run_migrations()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        manager = JobManager()
        register_llm_jobs(manager)
        register_tts_jobs(manager)
        register_asr_jobs(manager)
        app.state.jobs = manager
        manager.start()
        yield
        await manager.stop()

    app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    app.include_router(openai_audio.router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    static_dir: Path | None = settings.resolved_static_dir
    if static_dir is not None:
        app.mount("/", SPAStaticFiles(directory=static_dir, html=True), name="spa")

    return app


app = create_app()
