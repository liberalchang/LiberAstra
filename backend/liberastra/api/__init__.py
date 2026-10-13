"""API 路由包。"""

from fastapi import APIRouter

from liberastra.api.routes import auth, capabilities, jobs, llm, providers, tokens

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(tokens.router)
api_router.include_router(providers.router)
api_router.include_router(capabilities.router)
api_router.include_router(jobs.router)
api_router.include_router(llm.router)
