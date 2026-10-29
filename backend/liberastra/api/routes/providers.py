"""Provider 管理路由：CRUD、测试连接、拉取模型、能力清单。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from liberastra.api.deps import CurrentUser, DbSession
from liberastra.models import Provider, User
from liberastra.providers import PROVIDER_TYPES
from liberastra.providers.base import ProviderError
from liberastra.schemas.provider import (
    ModelCatalogIn,
    ProviderCreate,
    ProviderOut,
    ProviderUpdate,
    TestResult,
)
from liberastra.services.providers import (
    backfill_catalog,
    encrypt_api_key,
    fetch_model_folder,
    fetch_models,
    replace_model_catalog,
    seed_model_catalog,
    test_connection,
)

router = APIRouter(prefix="/providers", tags=["providers"])


def _get_owned(db, provider_id: int, user: User) -> Provider:  # noqa: ANN001
    record = db.get(Provider, provider_id)
    if record is None or record.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider 不存在")
    return record


def _ensure_local_edge_tts(db: DbSession, user: User) -> None:
    """确保当前用户有一条名为「本地」的 edge_tts Provider（微软 Edge 在线 TTS）。"""
    exists = db.scalars(
        select(Provider).where(Provider.owner_id == user.id, Provider.type == "edge_tts")
    ).first()
    if exists is not None:
        return
    info = PROVIDER_TYPES["edge_tts"]
    db.add(
        Provider(
            name="本地",
            type="edge_tts",
            base_url="",
            capabilities=list(info.capabilities),
            concurrency=2,
            enabled=True,
            owner_id=user.id,
        )
    )
    db.commit()


@router.get("", response_model=list[ProviderOut])
def list_providers(user: CurrentUser, db: DbSession) -> list[ProviderOut]:
    _ensure_local_edge_tts(db, user)
    records = db.scalars(select(Provider).where(Provider.owner_id == user.id)).all()
    if any(backfill_catalog(record) for record in records):
        db.commit()
    return [ProviderOut.from_record(r) for r in records]


@router.get("/execution-specs")
def execution_specs(
    user: CurrentUser,
    db: DbSession,
    sub_capability: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """工作流包与已启用云端模型的统一参数契约。"""
    from liberastra.providers.schema_registry import filter_specs, model_specs, workflow_specs
    from liberastra.services.workflows import list_packs

    specs = workflow_specs(list_packs())
    records = db.scalars(
        select(Provider).where(Provider.owner_id == user.id, Provider.enabled.is_(True))
    ).all()
    changed = False
    for record in records:
        changed = backfill_catalog(record) or changed
        specs.extend(model_specs(record))
    if changed:
        db.commit()
    return filter_specs(specs, sub_capability=sub_capability, category=category)


@router.post("", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
def create_provider(body: ProviderCreate, user: CurrentUser, db: DbSession) -> ProviderOut:
    info = PROVIDER_TYPES.get(body.type)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"未知 Provider 类型: {body.type}，可用: {sorted(PROVIDER_TYPES)}",
        )
    if info.requires_api_key and not body.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="该类型需要 API Key"
        )
    record = Provider(
        name=body.name,
        type=body.type,
        base_url=(body.base_url or info.default_base_url or "").rstrip("/"),
        api_key_encrypted=encrypt_api_key(body.api_key) if body.api_key else None,
        capabilities=list(info.capabilities),
        concurrency=body.concurrency,
        enabled=body.enabled,
        extra=body.extra,
        owner_id=user.id,
    )
    seed_model_catalog(record)
    db.add(record)
    db.commit()
    db.refresh(record)
    return ProviderOut.from_record(record)


@router.patch("/{provider_id}", response_model=ProviderOut)
def update_provider(
    provider_id: int, body: ProviderUpdate, user: CurrentUser, db: DbSession
) -> ProviderOut:
    record = _get_owned(db, provider_id, user)
    if body.name is not None:
        record.name = body.name
    if body.base_url is not None:
        record.base_url = body.base_url.rstrip("/")
    if body.api_key is not None:
        record.api_key_encrypted = encrypt_api_key(body.api_key) if body.api_key else None
    if body.concurrency is not None:
        record.concurrency = body.concurrency
    if body.enabled is not None:
        record.enabled = body.enabled
    if body.extra is not None:
        record.extra = body.extra
    db.commit()
    db.refresh(record)
    return ProviderOut.from_record(record)


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider(provider_id: int, user: CurrentUser, db: DbSession) -> None:
    db.delete(_get_owned(db, provider_id, user))
    db.commit()


@router.post("/{provider_id}/test", response_model=TestResult)
async def test_provider(provider_id: int, user: CurrentUser, db: DbSession) -> TestResult:
    record = _get_owned(db, provider_id, user)
    try:
        message = await test_connection(record)
    except ProviderError as exc:
        return TestResult(ok=False, message=str(exc))
    return TestResult(ok=True, message=message)


@router.get("/{provider_id}/models", response_model=list[str])
async def list_provider_models(provider_id: int, user: CurrentUser, db: DbSession) -> list[str]:
    """实时拉取模型列表并缓存到 Provider 记录。"""
    record = _get_owned(db, provider_id, user)
    try:
        models = await fetch_models(record)
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    record.models = models
    db.commit()
    return models


@router.put("/{provider_id}/catalog", response_model=ProviderOut)
def update_catalog(
    provider_id: int, body: ModelCatalogIn, user: CurrentUser, db: DbSession
) -> ProviderOut:
    record = _get_owned(db, provider_id, user)
    try:
        replace_model_catalog(record, body.models)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(record)
    return ProviderOut.from_record(record)


@router.get("/{provider_id}/models/{folder}", response_model=list[str])
async def list_provider_model_folder(
    provider_id: int, folder: str, user: CurrentUser, db: DbSession
) -> list[str]:
    """列出某个模型子目录的文件名（如 checkpoints、upscale_models），供工作流参数下拉选择。"""
    record = _get_owned(db, provider_id, user)
    try:
        return await fetch_model_folder(record, folder)
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
