"""API 路由包。"""

from fastapi import APIRouter

from liberastra.api.routes import auth, tokens

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(tokens.router)
