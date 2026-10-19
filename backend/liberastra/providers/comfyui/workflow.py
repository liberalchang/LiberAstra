"""ComfyUI 工作流包执行器：图像/视频适配器共用的提交-等待-取件逻辑。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from liberastra.providers.base import ProviderError
from liberastra.providers.comfyui.client import ComfyClient
from liberastra.services.workflows import (
    WorkflowPack,
    apply_accel,
    apply_inputs,
    extract_accel,
    inject_image_input,
    resolve_accel_enabled,
    resolve_accel_lora,
)
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
    wait_timeout: float | None = None,
) -> dict[str, Any]:
    """注入参数、上传媒体输入、提交并等待完成，返回 ComfyUI outputs 字典。

    wait_timeout 为 None 时使用 ComfyClient.wait_result 的默认上限（600 秒）。
    inputs 可带保留键 __accel：{enabled, lora, strength}，在 apply_inputs 之后改写加速节点。
    """
    node_inputs, accel = extract_accel(inputs)
    if pack.accel and resolve_accel_enabled(pack, accel):
        lora = resolve_accel_lora(pack, accel)
        if not lora:
            raise ProviderError("开启了加速但没有选择加速模型")
        available = await client.list_model_folder("loras")
        if lora not in available:
            raise ProviderError(f"ComfyUI 的 loras 目录里没有 {lora}，请先上传")

    workflow = apply_inputs(pack, node_inputs)
    if pack.accel:
        workflow = apply_accel(workflow, pack, accel, user_values=node_inputs)

    for key, spec in pack.inputs.items():
        if spec.get("type") not in _UPLOAD_INPUT_TYPES or key not in node_inputs:
            continue
        local_path = resolve(str(node_inputs[key]))
        if not local_path.exists():
            raise ProviderError(f"输入文件不存在: {node_inputs[key]}")
        comfy_name = await client.upload_image(local_path.name, local_path.read_bytes())
        inject_image_input(workflow, pack, key, comfy_name)

    prompt_id = await client.queue_prompt(workflow)
    wait_kwargs: dict[str, Any] = {} if wait_timeout is None else {"timeout": wait_timeout}
    result = await client.wait_result(prompt_id, on_progress=on_progress, use_ws=use_ws, **wait_kwargs)
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


def _node_text_values(node_out: dict[str, Any]) -> list[str]:
    """从一个节点的 ComfyUI outputs 字典里抽出可读文本。"""
    texts: list[str] = []
    # 展示节点常见键；PreviewAny 也可能把内容放在 ui 子字典
    candidates: list[Any] = []
    for key in ("text", "string", "strings", "source", "result"):
        if key in node_out:
            candidates.append(node_out[key])
    ui = node_out.get("ui")
    if isinstance(ui, dict):
        for key in ("text", "string", "strings"):
            if key in ui:
                candidates.append(ui[key])
    for v in candidates:
        if isinstance(v, list):
            texts.extend(str(t) for t in v if str(t).strip())
        elif isinstance(v, str) and v.strip():
            texts.append(v)
        elif v is not None and not isinstance(v, (dict, list)):
            s = str(v).strip()
            if s:
                texts.append(s)
    return texts


def extract_texts(client_outputs: dict[str, Any], pack: WorkflowPack) -> list[str]:
    """从 outputs 提取文本（分析类：ShowText / PreviewAny；或 pack.outputs.texts 声明的节点）。"""
    declared = pack.outputs.get("texts")
    if isinstance(declared, list) and declared:
        texts: list[str] = []
        for item in declared:
            if isinstance(item, dict):
                node_id = str(item.get("node", ""))
                label = str(item.get("label") or "").strip()
            else:
                node_id = str(item)
                label = ""
            if not node_id:
                continue
            chunk = _node_text_values(client_outputs.get(node_id, {}))
            if not chunk:
                continue
            body = "\n".join(chunk)
            texts.append(f"【{label}】\n{body}" if label else body)
        return texts

    node_ids = [str(pack.outputs["node"])] if pack.outputs.get("node") else list(client_outputs)
    texts = []
    for node_id in node_ids:
        texts.extend(_node_text_values(client_outputs.get(node_id, {})))
    return texts


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
