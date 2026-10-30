"""能力清单：Provider 类型注册表与能力标签全集。"""

from __future__ import annotations

from fastapi import APIRouter

from liberastra.providers import PROVIDER_TYPES
from liberastra.providers.catalog import model_profile
from liberastra.schemas.provider import CapabilitiesOut, ProviderTypeInfoOut

router = APIRouter(tags=["capabilities"])


@router.get("/capabilities", response_model=CapabilitiesOut)
def capabilities() -> CapabilitiesOut:
    types = []
    for info in PROVIDER_TYPES.values():
        profile = model_profile(info.type)
        types.append(
            ProviderTypeInfoOut(
                **{**vars(info), "capabilities": list(info.capabilities)},
                model_kinds=profile["model_kinds"],
                sub_capabilities_by_kind=profile["sub_capabilities_by_kind"],
                param_schemas=profile["param_schemas"],
            )
        )
    all_caps = sorted({cap for info in PROVIDER_TYPES.values() for cap in info.capabilities})
    return CapabilitiesOut(provider_types=types, capabilities=all_caps)
