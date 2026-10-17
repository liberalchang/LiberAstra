"""API 路由包。"""

from fastapi import APIRouter

from liberastra.api.routes import (
    asr,
    assets,
    auth,
    bgm,
    capabilities,
    images,
    jobs,
    llm,
    openai_audio,
    openai_compat,
    providers,
    system,
    templates,
    tokens,
    tts,
    uploads,
    videos,
    voices,
    workflows,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(tokens.router)
api_router.include_router(providers.router)
api_router.include_router(capabilities.router)
api_router.include_router(jobs.router)
api_router.include_router(llm.router)
api_router.include_router(tts.router)
api_router.include_router(asr.router)
api_router.include_router(voices.router)
api_router.include_router(bgm.router)
api_router.include_router(assets.router)
api_router.include_router(images.router)
api_router.include_router(workflows.router)
api_router.include_router(templates.router)
api_router.include_router(videos.router)
api_router.include_router(uploads.router)
api_router.include_router(system.router)

__all__ = ["api_router", "openai_audio", "openai_compat"]
