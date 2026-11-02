"""画布快捷菜单：读取存档、补出厂项，并把菜单项解析到可用的工作流或模型。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from liberastra.models import AppSetting, Provider
from liberastra.providers.catalog import (
    default_canvas_menu,
    media_slots,
    targets_for_menu_item,
)
from liberastra.providers.schema_registry import model_specs, workflow_specs
from liberastra.services.workflows import list_packs

MENU_SETTING_KEY = "canvas_custom_menu"
# 出厂菜单结构变化时加 1。低于这个版本的存档会按当前出厂菜单重做图像和视频，语音保留。
# 用户在当前版本里删掉的项不再补回。
MENU_REVISION = 5


def decode_menu(raw: str) -> tuple[list[dict], int]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return [], 1
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        items = [item for item in data["items"] if isinstance(item, dict)]
        return items, int(data.get("revision") or 1)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)], 1
    return [], 1


def merge_factory_items(items: list[dict]) -> list[dict]:
    """旧菜单的图像和视频按当前工作流功能整表换掉。语音保留用户已经指定的模型。"""
    factory = default_canvas_menu()
    speech = [dict(item) for item in items if item.get("category") == "speech"]
    if not speech:
        speech = [item for item in factory if item.get("category") == "speech"]
    workflow = [item for item in factory if item.get("category") != "speech"]
    return speech + workflow


def present_menu(items: list[dict]) -> list[dict]:
    """响应里带上该能力的默认媒体槽，没绑到具体模型时前端仍能补前置节点。"""
    presented = []
    for item in items:
        row = dict(item)
        row["enabled"] = bool(item.get("enabled", True))
        row["media_slots"] = media_slots(str(item.get("sub_capability") or ""))
        presented.append(row)
    return presented


def store_menu(db: Session, items: list[dict], revision: int) -> None:
    payload = json.dumps({"revision": revision, "items": items}, ensure_ascii=False)
    row = db.get(AppSetting, MENU_SETTING_KEY)
    if row is None:
        db.add(AppSetting(key=MENU_SETTING_KEY, value=payload))
    else:
        row.value = payload
    db.commit()


def load_menu_items(db: Session, *, persist: bool = True) -> list[dict]:
    row = db.get(AppSetting, MENU_SETTING_KEY)
    if row is None:
        return default_canvas_menu()
    items, revision = decode_menu(row.value)
    if revision < MENU_REVISION:
        items = merge_factory_items(items)
        if persist:
            store_menu(db, items, MENU_REVISION)
    return items


def _slot_brief(slot: dict[str, Any]) -> dict[str, Any]:
    kind = str(slot.get("type") or "")
    return {
        "key": str(slot.get("key") or ""),
        "type": kind,
        "label": str(slot.get("label") or ""),
        "required": bool(slot.get("required", True)),
        "multiple": bool(slot.get("multiple", False)),
        "input_kind": str(slot.get("input_kind") or kind),
    }


def target_brief(spec: dict[str, Any]) -> dict[str, Any]:
    slots = spec.get("media_slots") or []
    return {
        "target_type": spec.get("target_type") or "",
        "target_id": spec.get("target_id") or "",
        "display_name": spec.get("display_name") or "",
        "sub_capability": spec.get("sub_capability") or "",
        "provider_id": spec.get("provider_id"),
        "provider_name": spec.get("provider_name") or "",
        "media_slots": [_slot_brief(slot) for slot in slots],
        "input_keys": sorted((spec.get("inputs") or {}).keys()),
    }


def _matches(spec: dict[str, Any], target: dict[str, Any]) -> bool:
    provider_id = target.get("provider_id")
    return (
        str(spec.get("target_type") or "") == str(target.get("target_type") or "")
        and str(spec.get("target_id") or "") == str(target.get("target_id") or "")
        and (provider_id is None or spec.get("provider_id") == provider_id)
    )


def resolve_menu_items(db: Session, owner_id: int) -> list[dict]:
    """给每个菜单项补上可用目标和解析后的默认目标。只读，不写目录。"""
    items = present_menu(load_menu_items(db, persist=False))
    specs = [spec.to_dict() for spec in workflow_specs(list_packs())]
    providers = db.scalars(
        select(Provider).where(Provider.owner_id == owner_id, Provider.enabled.is_(True))
    ).all()
    for record in providers:
        specs.extend(spec.to_dict() for spec in model_specs(record))

    resolved: list[dict] = []
    for item in items:
        targets = targets_for_menu_item(item, specs)
        default = item.get("default_target") or {}
        default_resolved = next((spec for spec in targets if _matches(spec, default)), None)
        row = dict(item)
        row["available_targets"] = [target_brief(spec) for spec in targets]
        default_brief = target_brief(default_resolved) if default_resolved else None
        row["default_target_resolved"] = default_brief
        if default_brief:
            # 菜单项声明的是该能力的默认槽；具体目标可能更严格，以默认目标为准。
            row["media_slots"] = default_brief["media_slots"]
        row["default_target_missing"] = bool(default) and default_resolved is None
        resolved.append(row)
    return resolved
