"""ComfyUI 画布 JSON → LiberAstra API Format，并启发式生成 manifest 草稿。"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# 画布 → API Format（由 scripts/canvas_to_api.py 迁入）
# ---------------------------------------------------------------------------


def is_canvas_format(data: Any) -> bool:
    """是否为 ComfyUI 画布格式（含 nodes 列表），而非 API Format / LiberAstra 包。"""
    if not isinstance(data, dict):
        return False
    if isinstance(data.get("workflow"), dict):
        return False  # LiberAstra 完整包
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return False
    # API Format：值是 {class_type, inputs}
    if all(isinstance(v, dict) and "class_type" in v for v in data.values() if isinstance(v, dict)):
        # 少数画布也会有无关键；以 nodes 列表为准
        sample = nodes[0]
        return isinstance(sample, dict) and "type" in sample and "id" in sample
    return isinstance(nodes[0], dict) and "type" in nodes[0]


def is_api_format(data: Any) -> bool:
    if not isinstance(data, dict) or not data:
        return False
    if "nodes" in data and isinstance(data["nodes"], list):
        return False
    nodes = [v for v in data.values() if isinstance(v, dict) and "class_type" in v]
    return len(nodes) >= 1


def _widget_map(node: dict[str, Any]) -> dict[str, Any]:
    named = node.get("widgets_values_named")
    if isinstance(named, dict) and named:
        return dict(named)
    return {}


def _link_index(links: list[Any]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for item in links or []:
        if isinstance(item, dict):
            out[int(item["id"])] = item
        elif isinstance(item, (list, tuple)) and len(item) >= 5:
            out[int(item[0])] = {
                "id": int(item[0]),
                "origin_id": item[1],
                "origin_slot": item[2],
                "target_id": item[3],
                "target_slot": item[4],
                "type": item[5] if len(item) > 5 else None,
            }
    return out


def _node_to_api(
    node: dict[str, Any],
    links_by_id: dict[int, dict[str, Any]],
    *,
    id_map: dict[Any, str],
) -> dict[str, Any] | None:
    ntype = node.get("type", "")
    if ntype in ("MarkdownNote", "Note", "Reroute"):
        return None
    if node.get("mode") == 4:
        return None

    inputs: dict[str, Any] = {}
    widgets = _widget_map(node)
    for key, val in widgets.items():
        inputs[key] = val

    for inp in node.get("inputs") or []:
        name = inp.get("name")
        if not name:
            continue
        link_id = inp.get("link")
        if link_id is None:
            continue
        link = links_by_id.get(int(link_id))
        if not link:
            continue
        origin = id_map.get(link["origin_id"])
        if origin is None:
            continue
        inputs[name] = [origin, int(link["origin_slot"])]

    return {"class_type": ntype, "inputs": inputs}


def convert_canvas(canvas: dict[str, Any]) -> dict[str, Any]:
    """展开一层 subgraph 实例，生成 API Format。"""
    subgraphs = {
        sg["id"]: sg for sg in (canvas.get("definitions") or {}).get("subgraphs") or []
    }
    top_links = _link_index(canvas.get("links") or [])
    api: dict[str, Any] = {}
    top_id_map = {n["id"]: str(n["id"]) for n in canvas.get("nodes") or []}

    for node in canvas.get("nodes") or []:
        ntype = node.get("type", "")
        if ntype in subgraphs:
            continue
        converted = _node_to_api(node, top_links, id_map=top_id_map)
        if not converted:
            continue
        if converted["class_type"] in ("MarkdownNote", "Note", "Reroute", "GetNode", "SetNode"):
            continue
        if converted["class_type"] in subgraphs:
            continue
        api[str(node["id"])] = converted

    for inst in canvas.get("nodes") or []:
        sg = subgraphs.get(inst.get("type"))
        if not sg:
            continue
        parent_id = str(inst["id"])
        inner_nodes = sg.get("nodes") or []
        inner_links = _link_index(sg.get("links") or [])
        input_node_id = (sg.get("inputNode") or {}).get("id")
        output_node_id = (sg.get("outputNode") or {}).get("id")

        id_map: dict[Any, str] = {}
        for n in inner_nodes:
            if n["id"] in (input_node_id, output_node_id):
                continue
            id_map[n["id"]] = f"{parent_id}:{n['id']}"

        inst_widgets = _widget_map(inst)
        if not inst_widgets and isinstance(inst.get("widgets_values"), list):
            wnames = []
            for i in inst.get("inputs") or []:
                w = i.get("widget")
                if isinstance(w, dict) and w.get("name"):
                    wnames.append(w["name"])
            vals = inst.get("widgets_values") or []
            inst_widgets = dict(zip(wnames, vals, strict=False))

        boundary_from_outside: dict[str, Any] = {}
        for inp in inst.get("inputs") or []:
            name = inp.get("name")
            if not name:
                continue
            if inp.get("link") is not None:
                link = top_links.get(int(inp["link"]))
                if link:
                    boundary_from_outside[name] = [str(link["origin_id"]), int(link["origin_slot"])]
            elif name in inst_widgets:
                boundary_from_outside[name] = inst_widgets[name]
            elif isinstance(inp.get("widget"), dict):
                wname = inp["widget"].get("name")
                if wname and wname in inst_widgets:
                    boundary_from_outside[name] = inst_widgets[wname]

        input_slot_names = [i.get("name") for i in (sg.get("inputs") or [])]

        for n in inner_nodes:
            if n["id"] in (input_node_id, output_node_id):
                continue
            if n.get("type") in ("MarkdownNote", "Note", "Reroute"):
                continue
            converted = _node_to_api(
                n,
                inner_links,
                id_map={**id_map, input_node_id: "__INPUT__", output_node_id: "__OUTPUT__"},
            )
            if not converted:
                continue
            new_inputs: dict[str, Any] = {}
            for key, val in converted["inputs"].items():
                if isinstance(val, list) and len(val) == 2 and val[0] == "__INPUT__":
                    slot = int(val[1])
                    bname = input_slot_names[slot] if slot < len(input_slot_names) else None
                    if bname and bname in boundary_from_outside:
                        new_inputs[key] = boundary_from_outside[bname]
                elif isinstance(val, list) and len(val) == 2 and val[0] == "__OUTPUT__":
                    continue
                else:
                    new_inputs[key] = val
            converted["inputs"] = new_inputs
            api[id_map[n["id"]]] = converted

        out_slot_sources: dict[int, list] = {}
        for link in sg.get("links") or []:
            item = link if isinstance(link, dict) else None
            if not item:
                continue
            if item.get("target_id") == output_node_id:
                src = id_map.get(item["origin_id"])
                if src:
                    out_slot_sources[int(item["target_slot"])] = [src, int(item["origin_slot"])]

        for _other_id, other in list(api.items()):
            for key, val in list(other.get("inputs", {}).items()):
                if isinstance(val, list) and len(val) == 2 and str(val[0]) == parent_id:
                    slot = int(val[1])
                    if slot in out_slot_sources:
                        other["inputs"][key] = out_slot_sources[slot]

    return api


# ---------------------------------------------------------------------------
# 启发式 manifest
# ---------------------------------------------------------------------------

# (参数名, 优先匹配的 input 字段名, 类型推断)
_FIELD_HINTS: list[tuple[str, tuple[str, ...], str]] = [
    ("prompt", ("prompt", "text", "manual_prompt", "positive"), "str"),
    ("negative_prompt", ("negative_prompt", "negative", "neg_prompt"), "str"),
    ("seed", ("noise_seed", "seed"), "int"),
    ("steps", ("steps",), "int"),
    ("width", ("width",), "int"),
    ("height", ("height",), "int"),
    ("length", ("length", "frames", "frame_count"), "int"),
    ("cfg", ("cfg", "cfg_scale", "guidance"), "float"),
    ("sampler_name", ("sampler_name",), "str"),
    ("scheduler", ("scheduler",), "str"),
    ("unet_name", ("unet_name",), "str"),
    ("clip_name", ("clip_name",), "str"),
    ("vae_name", ("vae_name",), "str"),
    ("ckpt_name", ("ckpt_name",), "str"),
    ("tail_file", ("tail_file",), "str"),
]


def _is_link(val: Any) -> bool:
    return isinstance(val, list) and len(val) == 2 and isinstance(val[0], (str, int))


def _guess_capability(api: dict[str, Any]) -> str:
    types = {n.get("class_type", "") for n in api.values()}
    has_load_image = "LoadImage" in types
    has_video = bool(types & {"SaveVideo", "CreateVideo", "MiniMaxH3ImageToVideo", "VHS_VideoCombine"})
    has_i2v = bool(types & {"MiniMaxH3ImageToVideo", "WanImageToVideo", "ImageOnlyCheckpointLoader"})
    has_upscale = bool(types & {"ImageUpscaleWithModel", "UpscaleModelLoader"})
    has_t2i = bool(types & {"KSampler", "SamplerCustomAdvanced", "CheckpointLoaderSimple", "UNETLoader"})

    if has_video or has_i2v:
        # 有 LoadImage 且连到 first_frame → i2v；否则 t2v
        if has_load_image:
            for node in api.values():
                if node.get("class_type") == "MiniMaxH3ImageToVideo":
                    ff = node.get("inputs", {}).get("first_frame")
                    if _is_link(ff):
                        return "i2v"
            # 其它视频图生
            return "i2v"
        return "t2v"
    if has_upscale:
        return "upscale"
    if has_load_image and has_t2i:
        return "i2i"
    return "t2i"


def _guess_outputs(api: dict[str, Any]) -> dict[str, Any]:
    texts: list[dict[str, str]] = []
    save_video = None
    save_image = None
    for nid, node in api.items():
        ct = node.get("class_type", "")
        if ct == "SaveVideo" and save_video is None:
            save_video = nid
        if ct in ("SaveImage", "SaveImageWebsocket") and save_image is None:
            save_image = nid
        if ct == "PreviewAny":
            texts.append({"node": nid, "label": f"预览 {nid}"})

    out: dict[str, Any]
    if save_video:
        out = {"node": save_video, "key": "images"}
    elif save_image:
        out = {"node": save_image, "key": "images"}
    else:
        # 兜底：最后一个节点
        last = sorted(api.keys())[-1] if api else "9"
        out = {"node": last, "key": "images"}
    if texts:
        out["texts"] = texts
    return out


def _guess_fps(api: dict[str, Any]) -> int | None:
    for node in api.values():
        if node.get("class_type") == "CreateVideo":
            fps = node.get("inputs", {}).get("fps")
            if isinstance(fps, (int, float)) and not _is_link(fps):
                return int(fps)
    return None


def _guess_accel(api: dict[str, Any]) -> dict[str, Any] | None:
    """找 LoraLoaderModelOnly：model 来自 UNET，且被 Guider/Scheduler 引用。"""
    for nid, node in api.items():
        if node.get("class_type") != "LoraLoaderModelOnly":
            continue
        inputs = node.get("inputs") or {}
        model_in = inputs.get("model")
        if not _is_link(model_in):
            continue
        src = api.get(str(model_in[0]))
        if not src or src.get("class_type") not in ("UNETLoader", "CheckpointLoaderSimple"):
            # 仍可能是加速节点
            pass
        # 下游是否引用本节点
        used = False
        for other in api.values():
            for val in (other.get("inputs") or {}).values():
                if _is_link(val) and str(val[0]) == str(nid):
                    used = True
                    break
            if used:
                break
        if not used:
            continue
        lora_name = inputs.get("lora_name", "")
        strength_field = "strength_model" if "strength_model" in inputs else "strength"
        match = "minimax_h3" if "minimax" in str(lora_name).lower() else "turbo"
        recommended = lora_name if isinstance(lora_name, str) and lora_name else None
        accel: dict[str, Any] = {
            "label": "Turbo 加速",
            "default_enabled": False,
            "node": str(nid),
            "bypass_input": "model",
            "lora": {
                "field": "inputs.lora_name",
                "options_from": "loras",
                "match": match,
            },
            "strength": {
                "field": f"inputs.{strength_field}",
                "default": float(inputs.get(strength_field, 1.0) or 1.0),
                "min": 0.5,
                "max": 1.5,
            },
            "preset": {"steps": 8},
        }
        if recommended:
            accel["lora"]["recommended"] = recommended
        # 家族提示
        if "minimax" in match:
            accel["family"] = "minimax_h3"
        return accel
    return None


def _add_input(
    inputs: dict[str, dict[str, Any]],
    key: str,
    node_id: str,
    field: str,
    typ: str,
    value: Any,
    *,
    required: bool = False,
    label: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    if key in inputs:
        return
    spec: dict[str, Any] = {
        "node": node_id,
        "field": field,
        "type": typ,
    }
    if required:
        spec["required"] = True
    if label:
        spec["label"] = label
    if value is not None and not required:
        spec["default"] = value
    if typ == "int" and isinstance(value, int):
        if key in ("width", "height"):
            spec.setdefault("min", 256)
            spec.setdefault("max", 2560)
            spec.setdefault("multiple", 32 if key in ("width", "height") else None)
            if spec.get("multiple") is None:
                del spec["multiple"]
        if key == "seed":
            spec["default"] = -1
        if key == "steps":
            spec.setdefault("min", 1)
            spec.setdefault("max", 50)
        if key == "length":
            spec.setdefault("min", 1)
            spec.setdefault("max", 362)
            spec.setdefault("align_base", 17)
            spec.setdefault("align_offset", 5)
            spec["label"] = label or "帧数"
    if typ == "str" and key in ("unet_name", "clip_name", "vae_name", "ckpt_name", "tail_file"):
        options = {
            "unet_name": "diffusion_models",
            "clip_name": "text_encoders",
            "vae_name": "vae",
            "ckpt_name": "checkpoints",
            "tail_file": "text_encoders",
        }.get(key)
        if options:
            spec["options_from"] = options
    if extra:
        spec.update(extra)
    inputs[key] = spec


def suggest_manifest(api: dict[str, Any]) -> dict[str, Any]:
    """根据 API Format 启发式生成 inputs / outputs / capability / fps / accel。"""
    inputs: dict[str, dict[str, Any]] = {}
    types = {nid: n.get("class_type", "") for nid, n in api.items()}

    # 图像输入：LoadImage
    for nid, ct in types.items():
        if ct == "LoadImage":
            _add_input(
                inputs, "image", nid, "inputs.image", "image", None,
                required=True, label="图片",
            )
            break

    # 按字段启发式扫一遍（先出现的节点优先）
    claimed_fields: set[tuple[str, str]] = set()
    for param, field_names, typ in _FIELD_HINTS:
        for nid, node in api.items():
            node_inputs = node.get("inputs") or {}
            for fname in field_names:
                if fname not in node_inputs:
                    continue
                val = node_inputs[fname]
                if _is_link(val):
                    continue
                mark = (nid, fname)
                if mark in claimed_fields:
                    continue
                # prompt 优先 TextEncode / Enhancer / MiniMaxH3ImageToVideo
                if param == "prompt":
                    ct = node.get("class_type", "")
                    if ct not in (
                        "CLIPTextEncode",
                        "MiniMaxH3PromptEnhancer",
                        "MiniMaxH3ImageToVideo",
                        "WanTextToImage",
                        "TextEncodeQwenImageEdit",
                    ) and fname not in ("prompt", "manual_prompt"):
                        continue
                claimed_fields.add(mark)
                required = param == "prompt"
                _add_input(
                    inputs, param, nid, f"inputs.{fname}", typ, val,
                    required=required,
                )
                break
            if param in inputs:
                break

    capability = _guess_capability(api)
    outputs = _guess_outputs(api)
    fps = _guess_fps(api)
    accel = _guess_accel(api)

    # i2v 必须有 image；t2v 不应强制 image
    if capability == "t2v" and "image" in inputs:
        # 若 first_frame 未连接，去掉 image 要求
        for node in api.values():
            if node.get("class_type") == "MiniMaxH3ImageToVideo":
                if "first_frame" not in (node.get("inputs") or {}):
                    inputs.pop("image", None)
                break

    requirements: dict[str, Any] = {
        "nodes": sorted({n.get("class_type") for n in api.values() if n.get("class_type")}),
    }

    manifest: dict[str, Any] = {
        "capability": capability,
        "description": f"由 ComfyUI 画布自动转换（能力猜测：{capability}，请核对参数映射）",
        "inputs": inputs,
        "outputs": outputs,
        "requirements": {"nodes": requirements["nodes"][:20]},  # 避免过长
    }
    if fps is not None:
        manifest["fps"] = fps
    if accel:
        manifest["accel"] = accel
    return manifest


def convert_comfy_json(data: dict[str, Any]) -> dict[str, Any]:
    """统一入口：画布 → API + 建议 manifest；已是 API Format 则只生成建议。"""
    warnings: list[str] = []
    if is_canvas_format(data):
        workflow = convert_canvas(data)
        if not workflow:
            raise ValueError("画布转换结果为空，请确认 JSON 含有效节点")
        warnings.append(f"已从画布格式转换为 API Format（{len(workflow)} 个节点）")
        source = "canvas"
    elif is_api_format(data):
        workflow = {
            k: v for k, v in data.items()
            if isinstance(v, dict) and "class_type" in v
        }
        source = "api"
        warnings.append("已识别为 API Format，仅生成参数映射草稿")
    else:
        raise ValueError("无法识别：既不是 ComfyUI 画布（nodes/links），也不是 API Format")

    manifest = suggest_manifest(workflow)
    warnings.append("参数映射为启发式草稿，导入前请核对 node / field")
    return {
        "workflow": workflow,
        "manifest": manifest,
        "source": source,
        "warnings": warnings,
        "node_count": len(workflow),
        "node_types": sorted({n.get("class_type", "") for n in workflow.values()}),
    }
