"""ComfyUI 工作流包执行器：图像/视频适配器共用的提交-等待-取件逻辑。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from liberastra.providers.base import ProviderError
from liberastra.providers.comfyui.client import ComfyClient, upload_too_large_message
from liberastra.services.canvas_graph import translate_prompt_slots
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
    prepare_pack_inputs(pack, node_inputs)
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

    # 未提供的可选媒体输入：断开 TextEncode 等对 Load* 的连线，避免 Comfy 去读占位 example.png
    _detach_unused_media_links(workflow, pack, node_inputs)

    for key, spec in pack.inputs.items():
        if spec.get("type") not in _UPLOAD_INPUT_TYPES or key not in node_inputs:
            continue
        local_path = resolve(str(node_inputs[key]))
        if not local_path.exists():
            raise ProviderError(f"输入文件不存在: {node_inputs[key]}")
        size = local_path.stat().st_size
        if size > client.max_upload_bytes:
            # 超限时不读入内存、也不向 ComfyUI 发请求
            raise ProviderError(upload_too_large_message(local_path.name, size, client.max_upload_bytes))
        comfy_name = await client.upload_image(local_path.name, local_path.read_bytes())
        inject_image_input(workflow, pack, key, comfy_name)

    prompt_id = await client.queue_prompt(workflow)
    wait_kwargs: dict[str, Any] = {} if wait_timeout is None else {"timeout": wait_timeout}
    result = await client.wait_result(prompt_id, on_progress=on_progress, use_ws=use_ws, **wait_kwargs)
    return result.get("outputs", {})  # type: ignore[no-any-return]


def prepare_pack_inputs(pack: WorkflowPack, node_inputs: dict[str, Any]) -> dict[str, Any]:
    """补齐声明了 fallback 的可选媒体，并在两张图不同时换用双图提示词。

    360° 环绕只传一张图时，尾帧必须仍是这张图。断开 last_frame 镜头会漂走，回不到起点。
    """
    _translate_written_prompt(pack, node_inputs)
    _fill_media_fallbacks(pack, node_inputs)
    _apply_distinct_image_prompt(pack, node_inputs)
    _apply_reference_picture_prompt(pack, node_inputs)
    return node_inputs


def _translate_written_prompt(pack: WorkflowPack, node_inputs: dict[str, Any]) -> None:
    """页面和画布都可能写下槽位名。提交前换成这个包登记的称呼。空提示词留给包内默认句。"""
    current = node_inputs.get("prompt")
    if current is None or not str(current).strip():
        return
    node_inputs["prompt"] = translate_prompt_slots(str(current), pack.inputs)


def _fill_media_fallbacks(pack: WorkflowPack, node_inputs: dict[str, Any]) -> None:
    for key, spec in pack.inputs.items():
        if spec.get("type") not in _UPLOAD_INPUT_TYPES:
            continue
        source_key = spec.get("fallback")
        if not source_key:
            continue
        if str(node_inputs.get(key) or "").strip():
            continue
        origin = str(node_inputs.get(str(source_key)) or "").strip()
        if origin:
            node_inputs[key] = origin


def _apply_distinct_image_prompt(pack: WorkflowPack, node_inputs: dict[str, Any]) -> None:
    """两张图路径不同，且提示词仍是默认句或空白时，换成 manifest 里的双图提示词。"""
    spec = pack.inputs.get("prompt") or {}
    variant = spec.get("distinct_image_2")
    if not isinstance(variant, str) or not variant.strip():
        return
    first = str(node_inputs.get("image") or "").strip()
    second = str(node_inputs.get("image_2") or "").strip()
    if not first or not second or first == second:
        return
    current = node_inputs.get("prompt")
    default = spec.get("default")
    blank = current is None or not str(current).strip()
    same_as_default = default is not None and str(current).strip() == str(default).strip()
    if blank or same_as_default:
        node_inputs["prompt"] = variant


def _pack_uses_picture_reference(pack: WorkflowPack) -> bool:
    """参考图生视频：有 ReferenceToVideo，且没有参考视频槽。动作迁移两者都有，不走这里。"""
    has_reference = any(
        isinstance(node, dict) and node.get("class_type") == "MiniMaxH3ReferenceToVideo"
        for node in pack.workflow.values()
    )
    has_video = any(spec.get("type") == "video" for spec in pack.inputs.values())
    return has_reference and not has_video


def _apply_reference_picture_prompt(pack: WorkflowPack, node_inputs: dict[str, Any]) -> None:
    """用户自己写了动作但没标 <Picture 1> 时补上。空白提示词留给包内默认句。"""
    if not _pack_uses_picture_reference(pack):
        return
    current = node_inputs.get("prompt")
    if current is None or not str(current).strip():
        return
    text = str(current).strip()
    if "<Picture" in text:
        return
    node_inputs["prompt"] = (
        "参考 <Picture 1> 的脸、发型和服装。这张图只提供外观，不是视频第一帧。"
        f"{text}"
    )


def _detach_unused_media_links(
    workflow: dict[str, Any],
    pack: WorkflowPack,
    node_inputs: dict[str, Any],
) -> None:
    """去掉未上传的可选 image/video/audio 在图中的引用边。

    LiberAstra API Format 里常见 ``images.image_N: [load_node, 0]``；
    槽位未提交文件时必须断开，否则 Comfy 会加载工作流里的占位图。
    """
    unused_nodes: set[str] = set()
    for key, spec in pack.inputs.items():
        if spec.get("type") not in _UPLOAD_INPUT_TYPES:
            continue
        if key in node_inputs and str(node_inputs[key]).strip():
            continue
        unused_nodes.add(str(spec["node"]))
    if not unused_nodes:
        return
    for node in workflow.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            continue
        for field, value in list(inputs.items()):
            if (
                isinstance(value, list)
                and len(value) >= 1
                and str(value[0]) in unused_nodes
            ):
                del inputs[field]


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
