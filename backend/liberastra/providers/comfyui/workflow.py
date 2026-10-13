"""ComfyUI 工作流包执行器：图像/视频适配器共用的提交-等待-取件逻辑。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from liberastra.providers.base import ProviderError
from liberastra.providers.comfyui.client import ComfyClient
from liberastra.services.workflows import WorkflowPack, apply_inputs, inject_image_input
from liberastra.storage import resolve

# 输入类型 → ComfyUI 上传后回填（图像/视频/音频都走 /upload/image 端点）
_UPLOAD_INPUT_TYPES = ("image", "video", "audio")


async def run_workflow_pack(
    client: ComfyClient,
    pack: WorkflowPack,
    inputs: dict[str, Any],
    *,
    on_progress: Callable[[float], None] | None = None,
    use_ws: bool = True,
) -> dict[str, Any]:
    """注入参数、上传媒体输入、提交并等待完成，返回 ComfyUI outputs 字典。"""
    workflow = apply_inputs(pack, inputs)
    for key, spec in pack.inputs.items():
        if spec.get("type") not in _UPLOAD_INPUT_TYPES or key not in inputs:
            continue
        local_path = resolve(str(inputs[key]))
        if not local_path.exists():
            raise ProviderError(f"输入文件不存在: {inputs[key]}")
        comfy_name = await client.upload_image(local_path.name, local_path.read_bytes())
        inject_image_input(workflow, pack, key, comfy_name)

    prompt_id = await client.queue_prompt(workflow)
    result = await client.wait_result(prompt_id, on_progress=on_progress, use_ws=use_ws)
    return result.get("outputs", {})  # type: ignore[no-any-return]


def extract_files(
    client_outputs: dict[str, Any],
    pack: WorkflowPack,
    keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    """从 outputs 提取指定类型（images / videos / gifs）的文件描述列表。"""
    node_ids = [str(pack.outputs["node"])] if pack.outputs.get("node") else list(client_outputs)
    files: list[dict[str, Any]] = []
    for node_id in node_ids:
        node_out = client_outputs.get(node_id, {})
        for key in keys:
            files.extend(node_out.get(key, []))
    return files


async def download_files(
    client: ComfyClient, files: list[dict[str, Any]]
) -> list[tuple[str, bytes]]:
    result: list[tuple[str, bytes]] = []
    for f in files:
        content = await client.download(
            f["filename"], f.get("subfolder", ""), f.get("type", "output")
        )
        result.append((f["filename"], content))
    return result
