"""Provider 的请求/响应模型。api_key 只进不出，响应里只有 has_api_key。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    type: str
    base_url: str = ""
    api_key: str | None = None
    concurrency: int = Field(default=2, ge=1, le=16)
    enabled: bool = True
    extra: dict = Field(default_factory=dict)


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    base_url: str | None = None
    api_key: str | None = None  # 传空字符串表示清除
    concurrency: int | None = Field(default=None, ge=1, le=16)
    enabled: bool | None = None
    extra: dict | None = None


class ProviderOut(BaseModel):
    id: int
    name: str
    type: str
    base_url: str
    has_api_key: bool
    models: list[str]
    capabilities: list[str]
    concurrency: int
    enabled: bool
    extra: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_record(cls, record) -> ProviderOut:  # noqa: ANN001
        from liberastra.services.providers import effective_capabilities

        data = {k: getattr(record, k) for k in cls.model_fields if k not in ("has_api_key", "capabilities")}
        return cls(
            **data,
            has_api_key=bool(record.api_key_encrypted),
            capabilities=effective_capabilities(record),
        )


class ProviderTypeInfoOut(BaseModel):
    type: str
    label: str
    capabilities: list[str]
    requires_api_key: bool
    default_base_url: str | None
    description: str
    group: str = ""


class CapabilitiesOut(BaseModel):
    provider_types: list[ProviderTypeInfoOut]
    capabilities: list[str]


class TestResult(BaseModel):
    ok: bool
    message: str


class ModelCatalogIn(BaseModel):
    """整份模型目录。前端保存启停、简称和手动添加的接入点。"""

    models: list[dict] = Field(default_factory=list)
