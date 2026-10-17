"""工作流包路由：列表、详情、导入、编辑、导出、删除（编辑/删除仅用户包）。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from liberastra.api.deps import CurrentUser
from liberastra.providers.base import ProviderError
from liberastra.schemas.workflow import WorkflowImportRequest, WorkflowPackOut
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
    )


@router.get("", response_model=list[WorkflowPackOut])
def list_workflows(user: CurrentUser, capability: str | None = None) -> list[WorkflowPackOut]:
    return [_to_out(p) for p in list_packs(capability)]


@router.get("/{name}", response_model=WorkflowPackOut)
def get_workflow(name: str, user: CurrentUser) -> WorkflowPackOut:
    try:
        return _to_out(get_pack(name))
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/import", response_model=WorkflowPackOut, status_code=status.HTTP_201_CREATED)
def import_workflow(body: WorkflowImportRequest, user: CurrentUser) -> WorkflowPackOut:
    try:
        pack = import_pack(
            body.name,
            body.workflow,
            {
                "name": body.name,
                "capability": body.capability,
                "description": body.description,
                "inputs": body.inputs,
                "outputs": body.outputs,
                "requirements": body.requirements,
            },
            overwrite=body.overwrite,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_out(pack)


@router.put("/{name}", response_model=WorkflowPackOut)
def update_workflow(name: str, body: WorkflowImportRequest, user: CurrentUser) -> WorkflowPackOut:
    try:
        pack = update_pack(
            name,
            body.workflow,
            {
                "name": name,
                "capability": body.capability,
                "description": body.description,
                "inputs": body.inputs,
                "outputs": body.outputs,
                "requirements": body.requirements,
            },
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
