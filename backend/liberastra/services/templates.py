"""分镜模板服务：扫描内置与用户模板目录、解析参数 DSL、上传与删除。

目录约定（与 Pixelle-Video 同构）：
- 内置：backend/templates/<宽高>/，随包分发，只读
- 用户：data/templates/<宽高>/，界面可上传/删除
- 文件名前缀即类型：static_*（静态样式）/ image_*（生成插图）/ video_*（生成视频）/ asset_*（素材）
- 占位符 DSL：{{name}}、{{name=默认值}}、{{name:类型}}、{{name:类型=默认值}}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from liberastra.core.config import get_settings
from liberastra.providers.base import ProviderError

# 画幅 → 模板目录名（目录名同时是帧画布尺寸）
ASPECT_DIRS = {"9:16": "1080x1920", "1:1": "1080x1080", "16:9": "1920x1080"}
DIR_ASPECTS = {v: k for k, v in ASPECT_DIRS.items()}

TEMPLATE_TYPES = {
    "static": "静态样式",
    "image": "生成插图",
    "video": "生成视频",
    "asset": "素材模板",
}

_PARAM_RE = re.compile(r"\{\{\s*(\w+)\s*(?::\s*(\w+)\s*)?(?:=\s*([^}]*?)\s*)?\}\}")
_META_RE = re.compile(
    r'<meta\s+name="template:media-(width|height)"\s+content="(\d+)"', re.IGNORECASE
)
_MAX_TEMPLATE_BYTES = 1024 * 1024


@dataclass
class TemplateParam:
    name: str
    type: str = "text"
    default: Any = ""


@dataclass
class TemplateInfo:
    name: str  # 文件名（不含 .html）
    aspect: str  # 9:16 / 1:1 / 16:9
    type: str  # static / image / video / asset
    source: str  # builtin / user
    path: Path = field(repr=False)
    width: int = 0  # 画布宽（目录名）
    height: int = 0
    media_width: int = 0  # 模板 meta 声明的插图尺寸（无则等于画布）
    media_height: int = 0
    params: dict[str, TemplateParam] = field(default_factory=dict)

    @property
    def type_label(self) -> str:
        return TEMPLATE_TYPES.get(self.type, self.type)

    @property
    def needs_image(self) -> bool:
        """模板是否包含插图占位符（决定 image 模式是否逐镜出图）。"""
        return "image" in self.params


def _builtin_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "templates"


def _user_dir() -> Path:
    return get_settings().data_dir / "templates"


def _parse_template(path: Path, source: str) -> TemplateInfo | None:
    if path.suffix.lower() != ".html":
        return None
    type_prefix = path.stem.split("_", 1)[0]
    if type_prefix not in TEMPLATE_TYPES:
        return None
    aspect = DIR_ASPECTS.get(path.parent.name)
    if aspect is None:
        return None
    try:
        width_s, height_s = path.parent.name.split("x")
        width, height = int(width_s), int(height_s)
    except ValueError:
        return None
    html = path.read_text(encoding="utf-8", errors="replace")
    params: dict[str, TemplateParam] = {}
    for m in _PARAM_RE.finditer(html):
        name, ptype, default = m.group(1), m.group(2) or "text", m.group(3)
        params[name] = TemplateParam(name=name, type=ptype, default=default or "")
    meta = {k: int(v) for k, v in _META_RE.findall(html)}
    return TemplateInfo(
        name=path.stem,
        aspect=aspect,
        type=type_prefix,
        source=source,
        path=path,
        width=width,
        height=height,
        media_width=meta.get("width", width),
        media_height=meta.get("height", height),
        params=params,
    )


def list_templates(aspect: str | None = None, type_: str | None = None) -> list[TemplateInfo]:
    """扫描用户与内置目录；同名用户模板覆盖内置。"""
    found: dict[tuple[str, str], TemplateInfo] = {}
    for root, source in ((_builtin_dir(), "builtin"), (_user_dir(), "user")):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.html")):
            info = _parse_template(path, source)
            if info is not None:
                found[(info.aspect, info.name)] = info
    items = list(found.values())
    if aspect:
        items = [t for t in items if t.aspect == aspect]
    if type_:
        items = [t for t in items if t.type == type_]
    return sorted(items, key=lambda t: (t.aspect, t.type, t.name))


def get_template(name: str, aspect: str) -> TemplateInfo:
    for root, source in ((_user_dir(), "user"), (_builtin_dir(), "builtin")):
        candidate = root / ASPECT_DIRS.get(aspect, "") / f"{name}.html"
        if candidate.exists():
            info = _parse_template(candidate, source)
            if info is not None:
                return info
    raise ProviderError(f"模板不存在: {aspect}/{name}")


def save_template(aspect: str, filename: str, content: bytes) -> TemplateInfo:
    """上传模板到用户目录。文件名前缀必须能识别类型。"""
    if aspect not in ASPECT_DIRS:
        raise ProviderError(f"未知画幅: {aspect}，可用 {sorted(ASPECT_DIRS)}")
    if len(content) > _MAX_TEMPLATE_BYTES:
        raise ProviderError("模板文件不能超过 1MB")
    stem = Path(filename).stem
    if not re.fullmatch(r"[\w\-]+", stem):
        raise ProviderError("模板文件名只能包含字母、数字、下划线和连字符")
    if stem.split("_", 1)[0] not in TEMPLATE_TYPES:
        raise ProviderError("模板文件名须以 static_ / image_ / video_ / asset_ 开头以标识类型")
    text = content.decode("utf-8", errors="replace")
    if "<html" not in text.lower():
        raise ProviderError("不是有效的 HTML 模板文件")
    dest_dir = _user_dir() / ASPECT_DIRS[aspect]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{stem}.html"
    dest.write_bytes(content)
    info = _parse_template(dest, "user")
    assert info is not None
    return info


def delete_template(name: str, aspect: str) -> None:
    path = _user_dir() / ASPECT_DIRS.get(aspect, "") / f"{name}.html"
    if not path.exists():
        raise ProviderError("只能删除用户上传的模板（内置模板不可删）")
    path.unlink()


def render(tpl: TemplateInfo, values: dict[str, Any]) -> str:
    """用 values 替换模板占位符，返回最终 HTML。未提供的参数用模板默认值。"""
    html = tpl.path.read_text(encoding="utf-8")

    def _sub(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in values and values[name] is not None:
            return str(values[name])
        param = tpl.params.get(name)
        return str(param.default) if param else ""

    return _PARAM_RE.sub(_sub, html)
