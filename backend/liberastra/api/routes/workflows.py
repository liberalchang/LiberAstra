"""工作流包路由：列表、详情、导入、编辑、导出、删除（编辑/删除仅用户包）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from liberastra.api.deps import CurrentUser
from liberastra.providers.base import ProviderError
from liberastra.schemas.workflow import (
    WorkflowConvertOut,
    WorkflowConvertRequest,
    WorkflowImportRequest,
    WorkflowPackOut,
)
from liberastra.services.canvas_convert import convert_comfy_json
from liberastra.services.workflows import (
    delete_pack,
    export_pack,
    get_pack,
    import_pack,
    list_packs,
    update_pack,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _to_out(pack) -> WorkflowPackOut:  # noqa: ANN001, ANN202
    return WorkflowPackOut(
        name=pack.name,
        capability=pack.capability,
        description=pack.description,
        inputs=pack.inputs,
        outputs=pack.outputs,
        source=pack.source,
        requirements=pack.requirements,
        fps=pack.fps,
        accel=pack.accel or {},
    )


def _manifest_from_body(
    body: WorkflowImportRequest,
    *,
    name: str | None = None,
    existing_accel: dict[str, Any] | None = None,
    existing_llm_note: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": name or body.name,
        "capability": body.capability,
        "description": body.description,
        "inputs": body.inputs,
        "outputs": body.outputs,
        "requirements": body.requirements,
    }
    if body.fps is not None:
        data["fps"] = body.fps
    if body.accel is not None:
        data["accel"] = body.accel
    elif existing_accel:
        data["accel"] = existing_accel
    if body.llm_note is not None:
        data["llm_note"] = body.llm_note
    elif existing_llm_note:
        data["llm_note"] = existing_llm_note
    return data


@router.get("", response_model=list[WorkflowPackOut])
def list_workflows(user: CurrentUser, capability: str | None = None) -> list[WorkflowPackOut]:
    return [_to_out(p) for p in list_packs(capability)]


@router.get("/{name}", response_model=WorkflowPackOut)
def get_workflow(name: str, user: CurrentUser) -> WorkflowPackOut:
    try:
        return _to_out(get_pack(name))
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/convert", response_model=WorkflowConvertOut)
def convert_workflow(body: WorkflowConvertRequest, user: CurrentUser) -> WorkflowConvertOut:
    """把 ComfyUI 画布 JSON（或 API Format）转成 LiberAstra 包草稿，不落盘。"""
    try:
        result = convert_comfy_json(body.data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    manifest = result["manifest"]
    return WorkflowConvertOut(
        workflow=result["workflow"],
        capability=manifest.get("capability", "t2i"),
        description=manifest.get("description", ""),
        inputs=manifest.get("inputs") or {},
        outputs=manifest.get("outputs") or {},
        requirements=manifest.get("requirements") or {},
        fps=manifest.get("fps"),
        accel=manifest.get("accel") or {},
        source=result["source"],
        warnings=result.get("warnings") or [],
        node_count=result.get("node_count", 0),
        node_types=result.get("node_types") or [],
    )


@router.post("/import", response_model=WorkflowPackOut, status_code=status.HTTP_201_CREATED)
def import_workflow(body: WorkflowImportRequest, user: CurrentUser) -> WorkflowPackOut:
    try:
        pack = import_pack(
            body.name,
            body.workflow,
            _manifest_from_body(body),
            overwrite=body.overwrite,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_out(pack)


@router.put("/{name}", response_model=WorkflowPackOut)
def update_workflow(name: str, body: WorkflowImportRequest, user: CurrentUser) -> WorkflowPackOut:
    try:
        existing = get_pack(name)
        pack = update_pack(
            name,
            body.workflow,
            _manifest_from_body(
                body,
                name=name,
                existing_accel=existing.accel or None,
                existing_llm_note=existing.llm_note or None,
            ),
        )
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_out(pack)


@router.get("/{name}/export")
def export_workflow(name: str, user: CurrentUser) -> dict[str, Any]:
    try:
        return export_pack(name)
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(name: str, user: CurrentUser) -> None:
    try:
        delete_pack(name)
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
