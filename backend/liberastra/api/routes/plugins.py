"""本机插件：安装/卸载与启用/禁用（启停本地附加服务）。"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.services.plugins import (
    disable_plugin,
    enable_plugin,
    install_plugin,
    list_plugins,
    uninstall_plugin,
)

router = APIRouter(prefix="/plugins", tags=["plugins"])


class PluginOut(BaseModel):
    id: str
    name: str
    description: str
    port: int
    installed: bool
    enabled: bool
    running: bool
    device: str
    models_dir: str
    code_dir: str
    launch: str
    model_status: str
    env_status: str
    env_dir: str
    install_progress: int
    install_phase: str
    last_error: str


class PluginInstallIn(BaseModel):
    device: str | None = None
    models_dir: str | None = Field(default=None, max_length=512)


@router.get("", response_model=list[PluginOut])
def get_plugins(_user: CurrentUser) -> list[PluginOut]:
    return [PluginOut.model_validate(item) for item in list_plugins()]


@router.post("/{plugin_id}/install", response_model=PluginOut)
def install(
    plugin_id: str,
    user: CurrentUser,
    db: DbSession,
    body: PluginInstallIn = PluginInstallIn(),
) -> PluginOut:
    return PluginOut.model_validate(
        install_plugin(db, user.id, plugin_id, device=body.device)
    )


@router.post("/{plugin_id}/uninstall", response_model=PluginOut)
def uninstall(plugin_id: str, user: CurrentUser, db: DbSession) -> PluginOut:
    return PluginOut.model_validate(uninstall_plugin(db, user.id, plugin_id))


@router.post("/{plugin_id}/enable", response_model=PluginOut)
def enable(plugin_id: str, user: CurrentUser, db: DbSession) -> PluginOut:
    return PluginOut.model_validate(enable_plugin(db, user.id, plugin_id))


@router.post("/{plugin_id}/disable", response_model=PluginOut)
def disable(plugin_id: str, user: CurrentUser, db: DbSession) -> PluginOut:
    return PluginOut.model_validate(disable_plugin(db, user.id, plugin_id))
