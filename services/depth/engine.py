"""MiDaS 深度图推理。

从 naked-eye-3d-plus 的 DepthGenerator 抽出：BGR 转 RGB，按模型名选择边长
（large 384 / beit 512 / small 256）。Swin 按正方形和 0.5 归一化，其余保持比例并做 ImageNet 归一化，
再双三次插值回原图尺寸，归一化成 8 位灰度 PNG。越亮表示越近。

权重是 state_dict（.pt / .pth），不是完整模块。优先用本机已有的 midas 包加载；
没有时再走 torch.hub 的 intel-isl/MiDaS。主服务不导入本模块。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_MODEL = "dpt_swin2_large_384"
# torch.hub 上与本地权重文件名对应的结构名。
_HUB_NAMES = {
    "dpt_swin2_large_384": "DPT_SwinV2_L_384",
    "dpt_swin2_tiny_256": "DPT_SwinV2_T_256",
    "dpt_beit_large_512": "DPT_BEiT_L_512",
    "dpt_large_384": "DPT_Large",
    "dpt_hybrid_384": "DPT_Hybrid",
    "midas_v21_small_256": "MiDaS_small",
}
_IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
# Swin / BEiT 的 MiDaS v3.1 权重按 0.5 归一化，并且按正方形边长训练。
_MIDAS_MEAN = np.array([0.5, 0.5, 0.5], dtype=np.float32)
_MIDAS_STD = np.array([0.5, 0.5, 0.5], dtype=np.float32)


def models_dir() -> Path:
    raw = os.environ.get("LIBER_DEPTH_MODELS_DIR", "./models").strip() or "./models"
    return Path(raw).expanduser()


def results_dir() -> Path:
    raw = os.environ.get("LIBER_DEPTH_RESULTS_DIR", "./results").strip() or "./results"
    path = Path(raw).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_device() -> str:
    raw = os.environ.get("LIBER_DEPTH_DEVICE", "cuda").strip().lower() or "cuda"
    return raw if raw in {"cuda", "cpu"} else "cuda"


def default_model() -> str:
    return os.environ.get("LIBER_DEPTH_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def depth_output_name(filename: str) -> str:
    """原文件名去后缀后加 _depth.png。photo.jpg → photo_depth.png。"""
    stem = Path(filename or "image").stem.strip() or "image"
    stem = Path(stem).name
    return f"{stem}_depth.png"


def scan_models(directory: Path | None = None) -> list[dict[str, str]]:
    """扫描模型目录里的 .pt / .pth。id 用文件名去后缀。"""
    root = directory or models_dir()
    if not root.is_dir():
        return []
    found: list[dict[str, str]] = []
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".pt", ".pth"}:
            continue
        found.append({"id": path.stem, "label": path.name, "path": str(path)})
    return found


def _net_size(model_id: str) -> int:
    name = model_id.lower()
    if "beit" in name or "512" in name:
        return 512
    if "small" in name or "256" in name:
        return 256
    return 384


def _upper_bound_size(width: int, height: int, net: int) -> tuple[int, int]:
    """保持比例，长边不超过 net，并且宽高都是 32 的倍数。"""
    scale = net / max(width, height)
    out_w = max(32, int(width * scale))
    out_h = max(32, int(height * scale))
    out_w = max(32, (out_w // 32) * 32)
    out_h = max(32, (out_h // 32) * 32)
    return out_w, out_h


def _square_input(model_id: str) -> bool:
    """Swin 的窗口在建网时按固定边长算好了，输入必须是那个正方形。"""
    return "swin" in model_id.lower()


def _preprocess(rgb: np.ndarray, model_id: str) -> np.ndarray:
    """RGB uint8 → NCHW float32。Swin 用正方形，Swin 和 BEiT 用 0.5 归一化，其余保持比例。"""
    import cv2

    height, width = rgb.shape[:2]
    net = _net_size(model_id)
    if _square_input(model_id):
        out_w, out_h = net, net
        mean, std = _MIDAS_MEAN, _MIDAS_STD
    else:
        out_w, out_h = _upper_bound_size(width, height, net)
        mean, std = (_MIDAS_MEAN, _MIDAS_STD) if "beit" in model_id.lower() else (_IMAGENET_MEAN, _IMAGENET_STD)
    resized = cv2.resize(rgb, (out_w, out_h), interpolation=cv2.INTER_CUBIC)
    image = resized.astype(np.float32) / 255.0
    image = (image - mean) / std
    chw = np.transpose(image, (2, 0, 1))
    return np.ascontiguousarray(chw[None, ...])


def _state_dict(blob: Any) -> dict[str, Any]:
    if isinstance(blob, dict):
        for key in ("state_dict", "model", "model_state"):
            inner = blob.get(key)
            if isinstance(inner, dict):
                return inner
        if blob and all(hasattr(v, "shape") or hasattr(v, "detach") for v in list(blob.values())[:3]):
            return blob
    raise RuntimeError("权重不是 state_dict")


def _drop_runtime_buffers(state: dict[str, Any]) -> dict[str, Any]:
    """丢掉 timm 1.0 不再写入 state_dict 的缓冲区。BEiT 的 relative_position_index 就在这里。"""
    skip = ("relative_position_index", "relative_coords_table", "attn_mask")
    return {key: value for key, value in state.items() if not any(token in key for token in skip)}


def _adapt_swin_state(state: dict[str, Any]) -> dict[str, Any]:
    """把 MiDaS 官方 Swin 权重改成 timm 1.0 的键。

    timm 1.0 把 downsample 放到下一层，分类头放进 head.fc，并且不再保存 attn_mask。
    """
    if any("head.fc.weight" in key for key in state):
        return state
    if not any("layers.0.downsample" in key for key in state):
        return state
    adapted: dict[str, Any] = {}
    for key, value in state.items():
        if "attn_mask" in key or "relative_position_index" in key or "relative_coords_table" in key:
            continue
        name = re.sub(
            r"layers\.(\d+)\.downsample",
            lambda match: f"layers.{int(match.group(1)) + 1}.downsample",
            str(key),
        )
        name = name.replace("head.weight", "head.fc.weight").replace("head.bias", "head.fc.bias")
        adapted[name] = value
    return adapted


def _patch_swin_features(network: Any) -> None:
    """timm 1.0 的 Swin block 输出 NHWC。MiDaS 的后处理还按 (B, N, C) 写，这里改成直接换成 NCHW。"""
    import torch
    from torch import nn

    pretrained = getattr(network, "pretrained", None)
    backbone = getattr(pretrained, "model", None)
    layers = getattr(backbone, "layers", None)
    if not layers or not hasattr(layers[0], "output_nchw") or layers[0].output_nchw:
        return

    class _NhwcToNchw(nn.Module):
        def forward(self, value: torch.Tensor) -> torch.Tensor:
            if value.ndim == 4:
                return value.permute(0, 3, 1, 2).contiguous()
            return value

    for index in range(1, 5):
        name = f"act_postprocess{index}"
        if hasattr(pretrained, name):
            setattr(pretrained, name, _NhwcToNchw())


def _patch_beit_blocks(network: Any) -> None:
    """timm 1.0 把 DropPath 拆成 drop_path1 / drop_path2。MiDaS 的 BEiT 前向还在读 drop_path。"""
    pretrained = getattr(network, "pretrained", None)
    backbone = getattr(pretrained, "model", None)
    blocks = getattr(backbone, "blocks", None)
    if not blocks:
        return
    for block in blocks:
        if not hasattr(block, "drop_path") and hasattr(block, "drop_path1"):
            block.drop_path = block.drop_path1


def _load_network_state(network: Any, state: dict[str, Any]) -> None:
    expects_new = any(key.endswith("head.fc.weight") for key in network.state_dict())
    prepared = _adapt_swin_state(state) if expects_new else state
    network.load_state_dict(_drop_runtime_buffers(prepared))


def _strip_prefix(state: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in state.items():
        name = str(key)
        if name.startswith("module."):
            name = name[len("module.") :]
        cleaned[name] = value
    return cleaned


class DepthEngine:
    """按模型 id 缓存一份网络。换 device 或换模型时重新加载。"""

    def __init__(self) -> None:
        self._model: Any = None
        self._model_id = ""
        self._device = ""

    def health(self) -> dict[str, Any]:
        models = scan_models()
        device = self._resolve_device(default_device())
        return {
            "status": "ok",
            "device": device,
            "default_model": default_model(),
            "models": [item["id"] for item in models],
        }

    def convert(self, image_bytes: bytes, filename: str, model: str | None, device: str | None) -> tuple[str, bytes]:
        import cv2

        model_id = (model or "").strip() or default_model()
        wanted = self._resolve_device(device or default_device())
        buffer = np.frombuffer(image_bytes, dtype=np.uint8)
        bgr = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if bgr is None:
            raise RuntimeError("无法解码图片")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        network, torch_device = self._load(model_id, wanted)
        import torch

        batch = torch.from_numpy(_preprocess(rgb, model_id)).to(torch_device)
        with torch.no_grad():
            prediction = network(batch)
            if prediction.ndim == 3:
                prediction = prediction.unsqueeze(1)
            prediction = torch.nn.functional.interpolate(
                prediction,
                size=bgr.shape[:2],
                mode="bicubic",
                align_corners=False,
            ).squeeze()
        depth = prediction.detach().float().cpu().numpy()
        gray = cv2.normalize(depth, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
        ok, encoded = cv2.imencode(".png", gray)
        if not ok:
            raise RuntimeError("深度图编码失败")
        self._empty_cache(torch_device)
        return depth_output_name(filename), encoded.tobytes()

    def _resolve_device(self, device: str) -> str:
        wanted = (device or "cuda").strip().lower()
        if wanted == "cuda":
            try:
                import torch

                if torch.cuda.is_available():
                    return "cuda"
            except Exception:
                return "cpu"
            return "cpu"
        return "cpu"

    def _load(self, model_id: str, device: str) -> tuple[Any, Any]:
        if self._model is not None and self._model_id == model_id and self._device == device:
            return self._model, self._torch_device(device)
        import torch

        torch_device = self._torch_device(device)
        weight = self._weight_path(model_id)
        network = self._build_network(model_id, weight, torch_device)
        network.eval()
        self._model = network
        self._model_id = model_id
        self._device = device
        return network, torch_device

    def _torch_device(self, device: str) -> Any:
        import torch

        return torch.device("cuda" if device == "cuda" else "cpu")

    def _weight_path(self, model_id: str) -> Path | None:
        root = models_dir()
        for suffix in (".pt", ".pth"):
            path = root / f"{model_id}{suffix}"
            if path.is_file():
                return path
        return None

    def _build_network(self, model_id: str, weight: Path | None, torch_device: Any) -> Any:
        import torch

        local = self._load_local_midas(model_id, weight, torch_device)
        if local is not None:
            return local
        hub_name = _HUB_NAMES.get(model_id)
        if hub_name is None:
            if "beit" in model_id:
                hub_name = "DPT_BEiT_L_512"
            elif "swin" in model_id and "tiny" in model_id:
                hub_name = "DPT_SwinV2_T_256"
            elif "swin" in model_id:
                hub_name = "DPT_SwinV2_L_384"
            elif "small" in model_id:
                hub_name = "MiDaS_small"
            elif "hybrid" in model_id:
                hub_name = "DPT_Hybrid"
            else:
                hub_name = "DPT_Large"
        # pretrained=False：hub 默认会按旧键加载官方权重，在 timm 1.0 上直接失败。
        network = torch.hub.load(
            "intel-isl/MiDaS",
            hub_name,
            pretrained=False,
            trust_repo=True,
            skip_validation=True,
        )
        _patch_swin_features(network)
        _patch_beit_blocks(network)
        if weight is not None:
            blob = torch.load(weight, map_location="cpu", weights_only=False)
            state = _strip_prefix(_state_dict(blob))
            _load_network_state(network, state)
        return network.to(torch_device)

    def _load_local_midas(self, model_id: str, weight: Path | None, torch_device: Any) -> Any | None:
        """本机已经装了 intel-isl 的 midas 源码包时，直接用它的 load_model。权重对不上就改走 hub。"""
        if weight is None:
            return None
        try:
            from midas.model_loader import load_model
        except Exception:
            return None
        try:
            model, _transform, _net_w, _net_h = load_model(torch_device, str(weight), model_id, optimize=False)
        except Exception:
            return None
        _patch_swin_features(model)
        _patch_beit_blocks(model)
        return model

    def _empty_cache(self, torch_device: Any) -> None:
        import torch

        if torch_device.type == "cuda":
            torch.cuda.empty_cache()


engine = DepthEngine()
