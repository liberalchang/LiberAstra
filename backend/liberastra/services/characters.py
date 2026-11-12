"""角色库：四段式/四宫格切分、按任务取单视角图、生成双排版定妆照。"""

from __future__ import annotations

import base64
import io
import re
import uuid
from typing import Any

from fastapi import HTTPException
from loguru import logger
from PIL import Image
from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext, JobManager
from liberastra.models import Character, Job
from liberastra.providers.base import ProviderError
from liberastra.services.image import produce_images
from liberastra.services.preferences import get_pref, get_str_pref
from liberastra.services.providers import build_image_adapter, pick_provider
from liberastra.services.workflows import get_pack
from liberastra.storage import resolve, save_bytes

SLOTS = ("portrait", "turnaround", "turnaround_grid", "front", "side", "back")
_SLOT_ATTR = {
    "portrait": "portrait_path",
    "turnaround": "turnaround_path",
    "turnaround_grid": "turnaround_grid_path",
    "front": "front_path",
    "side": "side_path",
    "back": "back_path",
}

CHARACTER_VIEW_SLOTS = ("portrait", "front", "side", "back")
CHARACTER_VIEW_LABELS = {
    "portrait": "面部特写",
    "front": "正面全身",
    "side": "侧面全身",
    "back": "背面全身",
}
MIN_VIEW_SHORT_EDGE = 640
VIEW_RATIO_TOLERANCE = 0.01
VIEW_WIDTH = 864
VIEW_HEIGHT = 1536
VIEW_ORDER = {
    "face": ("portrait", "front", "side", "back"),
    "body": ("front", "portrait", "side", "back"),
}
_VIEW_LAYOUTS = {
    "portrait": (
        "9:16竖版角色面部特写，半身构图，头顶到肩部完整入镜，面部居中且清晰，"
        "完整展示五官、发型和发色。"
    ),
    "front": (
        "9:16竖版角色正面全身照，镜头正对人物，自然站姿，双臂自然下垂，"
        "完整全身入镜，头顶和脚底都保留余量，不裁脚。"
    ),
    "side": (
        "9:16竖版角色正侧面全身照，90度侧身，自然站姿，"
        "完整全身入镜，头顶和脚底都保留余量，不裁脚。"
    ),
    "back": (
        "9:16竖版角色背面全身照，背对镜头，自然站姿，"
        "完整全身入镜，头顶和脚底都保留余量，不裁脚。"
    ),
}
_VIEW_STYLE = (
    "浅灰纯色影棚背景，柔和棚拍光，写实真人质感，皮肤细腻通透，发丝清晰，"
    "服装面料真实，8K超高清。表情自然中性，除非外观描述明确指定；不要主动添加具体表情。"
)


def view_prompt(
    description: str,
    slot: str,
    *,
    references: int = 0,
    edit_prompt: str = "",
) -> str:
    """构建单视角提示词；修改模式只写改什么，其余保持不变。"""
    label = CHARACTER_VIEW_LABELS.get(slot, slot)
    parts: list[str] = []
    body = str(description or "").strip()
    if body:
        parts.append(f"角色外观：{body}。")
    if references:
        parts.append("参考图中的人物是同一身份，保持同一脸型、发型、肤色、体型与服装配饰。")
    if edit_prompt.strip():
        parts.append(
            f"修改要求：{edit_prompt.strip()}。"
            f"只修改{label}中用户指定的内容，人物身份、脸型、发型、肤色、体型和未提及的细节保持不变。"
        )
    else:
        parts.append(_VIEW_LAYOUTS.get(slot, _VIEW_LAYOUTS["front"]))
        parts.append(f"这是同一角色的{label}，保持四视图之间的身份与服装一致。")
    parts.append(_VIEW_STYLE)
    return "".join(parts)


def _data_url(filename: str, content: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "webp": "webp"}.get(ext, "png")
    return f"data:image/{mime};base64,{base64.b64encode(content).decode('ascii')}"


def _fit_image(
    content: bytes,
    width: int,
    height: int,
    *,
    background: tuple[int, int, int] = (230, 230, 230),
) -> bytes:
    """等比放进目标画布，避免裁掉头发或脚；空余用浅灰补齐。"""
    source = Image.open(io.BytesIO(content)).convert("RGB")
    scale = min(width / source.width, height / source.height)
    fitted = source.resize(
        (max(1, int(source.width * scale)), max(1, int(source.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGB", (width, height), background)
    canvas.paste(fitted, ((width - fitted.width) // 2, (height - fitted.height) // 2))
    return _encode_png(canvas)


def normalize_character_view(content: bytes) -> bytes:
    return _fit_image(content, VIEW_WIDTH, VIEW_HEIGHT)


def normalize_character_wide(content: bytes) -> bytes:
    return _fit_image(content, SHEET_WIDTH, SHEET_HEIGHT)


def compose_character_grid(
    parts: dict[str, bytes],
    *,
    size: tuple[int, int] = (1152, 2048),
    gutter: int = 8,
) -> bytes:
    """2×2 程序合成：左上特写、右上正面、左下侧面、右下背面。"""
    width, height = size
    cell_width, cell_height = width // 2, height // 2
    canvas = Image.new("RGB", size, (230, 230, 230))
    for index, key in enumerate(CHARACTER_VIEW_SLOTS):
        raw = parts.get(key)
        if not raw:
            raise ProviderError(f"缺少{CHARACTER_VIEW_LABELS[key]}，无法合成四宫格")
        source = Image.open(io.BytesIO(raw)).convert("RGB")
        inner_width = max(1, cell_width - gutter * 2)
        inner_height = max(1, cell_height - gutter * 2)
        scale = min(inner_width / source.width, inner_height / source.height)
        fitted = source.resize(
            (max(1, int(source.width * scale)), max(1, int(source.height * scale))),
            Image.Resampling.LANCZOS,
        )
        column, row = index % 2, index // 2
        x = column * cell_width + (cell_width - fitted.width) // 2
        y = row * cell_height + (cell_height - fitted.height) // 2
        canvas.paste(fitted, (x, y))
    return _encode_png(canvas)


def validate_character_view_image(content: bytes, slot: str) -> tuple[int, int]:
    """上传的单视角必须是 9:16 且短边至少 640。"""
    try:
        with Image.open(io.BytesIO(content)) as image:
            width, height = image.size
    except Exception as exc:  # noqa: BLE001
        raise ProviderError(f"{CHARACTER_VIEW_LABELS.get(slot, slot)}不是有效图片") from exc
    if min(width, height) < MIN_VIEW_SHORT_EDGE:
        raise ProviderError(
            f"{CHARACTER_VIEW_LABELS.get(slot, slot)}短边至少 {MIN_VIEW_SHORT_EDGE}px"
        )
    if abs(width * 16 - height * 9) > height * 9 * VIEW_RATIO_TOLERANCE:
        raise ProviderError(f"{CHARACTER_VIEW_LABELS.get(slot, slot)}必须是 9:16")
    return width, height


def character_needs_generation(slot_paths: dict[str, str | None], prompt: str) -> bool:
    """有修改提示词，或四槽缺任意一张，就需要调用生成服务。"""
    if str(prompt or "").strip():
        return True
    return any(not slot_paths.get(slot) for slot in CHARACTER_VIEW_SLOTS)


def character_generation_config(
    db: Session, provider_id: int | None = None
) -> dict[str, Any]:
    """读取并校验角色生成配置；返回可直接放进任务参数的快照。"""
    try:
        provider = pick_provider(db, "image", provider_id)
    except (ProviderError, HTTPException):
        return {
            "provider": None,
            "mode": "workflow",
            "workflows": {},
            "model": "",
            "missing": ["图像服务商"],
        }
    if provider.type == "comfyui":
        workflows = {
            "t2i": get_str_pref(db, "default_character_workflow").strip(),
            "single": get_str_pref(db, "default_character_i2i_workflow").strip(),
            "multi": get_str_pref(db, "default_character_i2i_multi_workflow").strip(),
        }
        missing: list[str] = []
        for key, label in (
            ("t2i", "文生图工作流包"),
            ("single", "单图 i2i 工作流包"),
            ("multi", "多图 i2i 工作流包"),
        ):
            name = workflows[key]
            if not name:
                missing.append(label)
                continue
            try:
                pack = get_pack(name)
            except ProviderError:
                missing.append(f"{label}（{name} 不存在）")
                continue
            expected = "t2i" if key == "t2i" else "i2i"
            if pack.capability != expected:
                missing.append(f"{label}（{name} 不是 {expected} 包）")
                continue
            image_keys = [k for k, s in pack.inputs.items() if s.get("type") == "image"]
            if key == "t2i" and any((pack.inputs.get(k) or {}).get("required") for k in image_keys):
                missing.append(f"{label}（{name} 需要参考图）")
            elif key == "single" and len(image_keys) < 1:
                missing.append(f"{label}（{name} 没有图片槽）")
            elif key == "multi" and len(image_keys) < 2:
                missing.append(f"{label}（{name} 图片槽不足）")
        return {
            "provider": provider,
            "mode": "workflow",
            "workflows": workflows,
            "model": "",
            "missing": missing,
        }
    model = get_str_pref(db, "default_character_model").strip()
    return {
        "provider": provider,
        "mode": "model",
        "workflows": {},
        "model": model,
        "missing": [] if model else ["角色生图模型"],
    }

# 16:9 四段式定妆照。未点提示词优化时，拼在用户外观描述后面。
SHEET_PROMPT = (
    "16:9横版角色设定图，浅灰纯色影棚背景，四段使用同一背景，段与段之间留出空白间隔，"
    "头发、披帛和手臂不要伸进间隔或其他栏。"
    "画面从左到右依次展示完整全身正面、完整全身侧面、"
    "完整全身背面、右侧超大面部半身特写，四个视角保持同一人物、同一脸型、同一发型、同一服装与配饰。"
    "人物全身完整入镜，不裁脚；正面站姿按用户描述，未指定时自然站立。"
    "右侧特写展示面部，表情和视线按用户描述，未指定时中性自然；不要主动添加具体表情。"
    "写实真人质感，柔和棚拍光，皮肤细腻通透，发丝清晰，服装面料真实，高级人像质感，8K超高清。"
)
SHEET_GRID_PROMPT = (
    "9:16竖版角色设定图，2×2等大四宫格，每格为9:16竖构图，四格使用同一浅灰纯色影棚背景，"
    "格与格之间留出空白间隔，头发、披帛、手臂和服装不要越过中线、横线或进入其他格。"
    "左上格为正面面部半身特写；右上格为完整全身正面；左下格为完整全身侧面；右下格为完整全身背面。"
    "四格保持同一人物、同一脸型、同一发型、同一服装与配饰。三张全身图人物完整入镜，不裁脚；"
    "正面站姿按用户描述，未指定时自然站立。左上特写展示面部，表情和视线按用户描述，未指定时中性自然；"
    "不要主动添加具体表情。写实真人质感，柔和棚拍光，皮肤细腻通透，发丝清晰，服装面料真实，"
    "高级人像质感，8K超高清。"
)
WIDE_REFERENCE_PROMPT = (
    "参考图 1 是四张 9:16 视角拼成的底图，只用于确定四个视角；其余参考图提供同一人物细节。"
    "请重新绘制为连续横版定妆照，四栏等宽，人物填满各自一栏，不要保留四宫格、拼图边框或灰色留白。"
)
SHEET_WIDTH = 1536
SHEET_HEIGHT = 864
SHEET_GRID_WIDTH = 1152
SHEET_GRID_HEIGHT = 2048
# 这些句子是设定图排版，不能写进分镜画面提示词。
_LAYOUT_MARKERS = (
    "16:9",
    "9:16",
    "横版角色设定",
    "竖版角色设定",
    "画面依次展示",
    "画面从左到右",
    "四个视角",
    "四宫格",
    "2×2",
    "2x2",
    "左上格",
    "右上格",
    "左下格",
    "右下格",
    "四格等大",
    "每格为",
    "完整全身正面",
    "正面面部半身",
    "右侧超大面部",
    "右侧特写",
    "不裁脚",
    "浅灰纯色",
    "影棚背景",
    "空白间隔",
    "不要伸进",
    "不要越过",
    "Lookbook",
    "8K",
    "写实真人质感",
    "高级人像质感",
    "柔和棚拍光",
)
_LAYOUT_PHRASES = (
    "角色三视图设定",
    "三视图设定",
    "四段式角色设定图",
    "四段式定妆照",
    "四宫格角色设定图",
    "9:16四宫格",
    "四宫格定妆照",
    "角色定妆照",
)
_WIDE_LAYOUT_MARKERS = (
    "横版角色设定",
    "四段式角色",
    "画面从左到右",
    "四个视角",
    "完整全身正面",
    "右侧超大面部",
)
_GRID_LAYOUT_MARKERS = (
    "竖版角色设定",
    "四宫格",
    "2×2",
    "左上格",
    "右上格",
    "左下格",
    "右下格",
    "正面面部半身",
)


def save_character_bytes(content: bytes, suffix: str) -> str:
    """把角色图片写到 data/characters/，返回相对路径。"""
    ext = suffix if suffix.startswith(".") else f".{suffix.lstrip('.')}"
    rel = f"characters/{uuid.uuid4().hex[:12]}{ext}"
    save_bytes(content, rel)
    return rel


def split_turnaround(content: bytes) -> tuple[bytes, bytes, bytes, bytes]:
    """把横版四段式设定图切成正面、侧面、背面、面部特写四张 PNG。

    在人物之间的空隙中点下刀。特写若换成另一种背景，再把左缘收到背景色跳变之后，
    避免把全身图的灰边留进特写。
    """
    image = Image.open(io.BytesIO(content)).convert("RGB")
    width, height = image.size
    if width < 8 or height < 8:
        raise ProviderError("设定图尺寸过小，无法拆分")
    cuts = _nudge_portrait_cut(image, _sheet_cuts(_column_activity(image)))
    edges = [0, *cuts, width]
    boxes = [(edges[index], edges[index + 1]) for index in range(len(edges) - 1)]
    parts: list[bytes] = []
    for left, right in boxes:
        if right - left < 2:
            raise ProviderError("设定图切分失败，请改用四段式横版图")
        buffer = io.BytesIO()
        image.crop((left, 0, right, height)).save(buffer, format="PNG")
        parts.append(buffer.getvalue())
    return parts[0], parts[1], parts[2], parts[3]


def _encode_png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _normalize_aspect_sheet(
    image: Image.Image, ratio_width: int, ratio_height: int, label: str
) -> Image.Image:
    width, height = image.size
    if width < ratio_width * 8 or height < ratio_height * 8:
        raise ProviderError(f"{label}尺寸过小，无法拆分")
    ratio = width / height
    target = ratio_width / ratio_height
    if abs(ratio - target) > 0.03:
        raise ProviderError(f"{label}必须是 {ratio_width}:{ratio_height}")
    scale = min(width // ratio_width, height // ratio_height)
    scale = max(2, (scale // 2) * 2)
    target_size = (ratio_width * scale, ratio_height * scale)
    if image.size != target_size:
        image = image.resize(target_size, Image.Resampling.LANCZOS)
    return image


def split_turnaround_grid(content: bytes) -> tuple[bytes, bytes, bytes, bytes, bytes]:
    """把 9:16 四宫格切成左上特写、右上正面、左下侧面、右下背面。

    返回 (归一化四宫格, portrait, front, side, back)。固定四等分，每张仍是 9:16。
    """
    image = Image.open(io.BytesIO(content)).convert("RGB")
    image = _normalize_aspect_sheet(image, 9, 16, "9:16 四宫格定妆照")
    width, height = image.size
    half_width, half_height = width // 2, height // 2
    boxes = (
        (0, 0, half_width, half_height),
        (half_width, 0, width, half_height),
        (0, half_height, half_width, height),
        (half_width, half_height, width, height),
    )
    parts = [_encode_png(image.crop(box)) for box in boxes]
    return _encode_png(image), parts[0], parts[1], parts[2], parts[3]


def apply_split(character: Character, turnaround: bytes) -> None:
    """保存四段式原图，并写入正面、侧面、背面和面部特写。"""
    front, side, back, portrait = split_turnaround(turnaround)
    character.turnaround_path = save_character_bytes(turnaround, _ext_of(turnaround))
    character.front_path = save_character_bytes(front, ".png")
    character.side_path = save_character_bytes(side, ".png")
    character.back_path = save_character_bytes(back, ".png")
    character.portrait_path = save_character_bytes(portrait, ".png")


def apply_grid_split(character: Character, turnaround: bytes) -> dict[str, bytes]:
    """保存 9:16 四宫格，并把四格写入角色视角。"""
    normalized, portrait, front, side, back = split_turnaround_grid(turnaround)
    character.turnaround_grid_path = save_character_bytes(normalized, ".png")
    character.portrait_path = save_character_bytes(portrait, ".png")
    character.front_path = save_character_bytes(front, ".png")
    character.side_path = save_character_bytes(side, ".png")
    character.back_path = save_character_bytes(back, ".png")
    return {
        "grid": normalized,
        "portrait": portrait,
        "front": front,
        "side": side,
        "back": back,
    }


BODY_VIEWS = ("front", "side", "back")
REF_VIEWS = ("portrait", "front", "side", "back", "turnaround", "turnaround_grid")


def reference_views(capability: str, slot_count: int, primary: str) -> list[str]:
    """按下游图片槽位数决定送哪些视角。口播只送特写；动作迁移只送全身。

    选整张定妆照时只送对应排版原图，不再拆成正面、侧面、背面或特写。
    """
    if slot_count <= 0:
        return []
    if primary in ("turnaround", "turnaround_grid"):
        return [primary]
    primary = primary if primary in REF_VIEWS else "front"
    if capability == "avatar":
        return ["portrait"]
    if capability == "motion":
        return list(BODY_VIEWS)[:slot_count]
    if slot_count <= 1:
        return [primary]
    # 第一张是这一镜的入镜视角，其余槽补还没用到的全身视角。特写只在入镜就是特写时出现。
    ordered = [primary]
    for view in BODY_VIEWS:
        if view not in ordered:
            ordered.append(view)
    return ordered[:slot_count]


def _paths_for_views(paths: dict[str, str], views: list[str]) -> list[str]:
    """按视角取已有文件。跳过缺图和重复路径。整张定妆照只在视图列表写明 turnaround 时使用。"""
    chosen: list[str] = []
    seen: set[str] = set()
    for view in views:
        if view not in SLOTS:
            continue
        path = paths.get(view) or ""
        if not path or path in seen:
            continue
        seen.add(path)
        chosen.append(path)
    return chosen


def expand_reference_paths(capability: str, slot_count: int, items: list[dict[str, Any]]) -> list[str]:
    """把普通图片和角色节点展开成工作流图片槽。

    只有一个角色时，普通图片先占槽，剩下的槽按 reference_views 补视角。
    多个角色时，每个角色只送自己的入镜视角，顺序跟连线一致。
    """
    if slot_count <= 0:
        return []
    characters = [item for item in items if item.get("type") == "character"]
    plains = [item for item in items if item.get("type") == "path"]
    if len(characters) == 1:
        if len(plains) >= slot_count:
            return [str(item["path"]) for item in plains][:slot_count]
        remaining = slot_count - len(plains)
        views = reference_views(capability, remaining, str(characters[0].get("primary") or "front"))
        result: list[str] = []
        for item in items:
            if item.get("type") == "path":
                result.append(str(item["path"]))
            elif item.get("type") == "character":
                result.extend(_paths_for_views(item.get("paths") or {}, views))
        return result[:slot_count]
    result = []
    for item in items:
        if item.get("type") == "path":
            result.append(str(item["path"]))
        elif item.get("type") == "character":
            primary = str(item.get("primary") or "front")
            result.extend(_paths_for_views(item.get("paths") or {}, [primary]))
    return result[:slot_count]


def reference_paths(character: Character, capability: str, slot_count: int, primary: str) -> list[str]:
    """从角色档取出这一次生成要用的图片路径。"""
    paths = {
        view: slot_path(character, view) or ""
        for view in SLOTS
    }
    chosen = _paths_for_views(paths, reference_views(capability, max(slot_count, 1), primary))
    if not chosen:
        raise ProviderError("这个角色还没有可用的单人图")
    return chosen


def ensure_character_asset(db: Session, character: Character, slot: str):  # noqa: ANN201
    """把已有的角色视角登记成图片资产。同一角色同一视角同一文件只登记一次。"""
    from sqlalchemy import select

    from liberastra.models import Asset
    from liberastra.storage import create_asset

    if slot not in SLOTS:
        raise ProviderError("视角不存在")
    rel = slot_path(character, slot)
    if not rel:
        raise ProviderError("这个视角还没有图片")
    rows = db.scalars(
        select(Asset).where(Asset.owner_id == character.owner_id, Asset.kind == "image")
    ).all()
    for asset in rows:
        meta = asset.meta or {}
        same_character = meta.get("character_id") == character.id and meta.get("character_slot") == slot
        if same_character and asset.path == rel:
            return asset
    return create_asset(
        db,
        kind="image",
        rel_path=rel,
        owner_id=character.owner_id,
        origin="character",
        meta={
            "character_id": character.id,
            "character_slot": slot,
            "character_name": character.name,
        },
    )


def paths_for_task(character: Character, view: str, *, multi: bool) -> list[str]:
    """按任务取图。多视角任务只用正/侧/背全身图，单图任务按所选视角取一张。

    整张定妆照选中后不再改送切分后的单人图；对应排版缺失时回退到另一种排版。
    """
    if view in ("turnaround", "turnaround_grid"):
        path = (
            character.turnaround_path
            if view == "turnaround"
            else character.turnaround_grid_path
        ) or (
            character.turnaround_grid_path
            if view == "turnaround"
            else character.turnaround_path
        )
        if not path:
            raise ProviderError("这个角色还没有定妆照")
        return [path]
    if multi:
        ordered = [character.front_path or character.portrait_path, character.side_path, character.back_path]
        paths = [path for path in ordered if path]
        if not paths:
            raise ProviderError("这个角色还没有可用的单人图")
        return paths
    chosen = {
        "front": character.front_path or character.portrait_path,
        "side": character.side_path or character.front_path or character.portrait_path,
        "back": character.back_path or character.front_path or character.portrait_path,
        "portrait": character.portrait_path or character.front_path,
    }.get(view, character.portrait_path or character.front_path)
    if not chosen:
        raise ProviderError("这个角色还没有可用的单人图")
    return [chosen]


def clean_appearance(text: str) -> str:
    """去掉横版/四宫格排版句，只留能写进分镜的人物外观。"""
    kept: list[str] = []
    for chunk in re.split(r"[。\n]", text):
        piece = chunk.strip(" ，,;；")
        if not piece or any(marker in piece for marker in _LAYOUT_MARKERS):
            continue
        for phrase in _LAYOUT_PHRASES:
            piece = piece.replace(phrase, "")
        piece = piece.strip(" ，,;；")
        if piece:
            kept.append(piece)
    return "。".join(kept)


def sheet_prompt(text: str, *, references: int = 0, layout: str = "wide") -> str:
    """用户没写目标排版时，补上对应定妆照要求。有参考图时先写明要保住的外观。"""
    layout = "grid" if layout == "grid" else "wide"
    markers = _GRID_LAYOUT_MARKERS if layout == "grid" else _WIDE_LAYOUT_MARKERS
    prompt = SHEET_GRID_PROMPT if layout == "grid" else SHEET_PROMPT
    body = text.strip()
    if body and any(marker in body for marker in markers):
        return body
    if body and any(marker in body for marker in (*_WIDE_LAYOUT_MARKERS, *_GRID_LAYOUT_MARKERS)):
        body = clean_appearance(body)
    if references == 1:
        anchor = "保持参考图中的人物面部五官、发型与核心穿搭一致。"
    elif references > 1:
        anchor = "综合参考图中的正面、侧面、背面形象，保持同一人物与服装。"
    else:
        anchor = ""
    if anchor and anchor not in body:
        body = f"{anchor}{body}" if body else anchor
    if not body:
        return prompt
    if body.endswith("。"):
        return body + prompt
    return f"{body}。{prompt}"


def prepare_character_ref_images(
    ref_bytes_list: list[bytes], *, target: tuple[int, int] = (1920, 1080)
) -> list[bytes]:
    """第一张贴进目标比例浅灰画布，让图生图的输出画幅固定。"""
    target_width, target_height = target
    prepared: list[bytes] = []
    for index, raw in enumerate(ref_bytes_list):
        image = Image.open(io.BytesIO(raw))
        if index == 0:
            canvas = Image.new("RGB", (target_width, target_height), (230, 230, 230))
            source = image.convert("RGB")
            scale = min(target_width / source.width, target_height / source.height)
            fitted = source.resize(
                (max(1, int(source.width * scale)), max(1, int(source.height * scale))),
                Image.Resampling.LANCZOS,
            )
            canvas.paste(
                fitted,
                ((target_width - fitted.width) // 2, (target_height - fitted.height) // 2),
            )
            image = canvas
        else:
            image = image.convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        prepared.append(buffer.getvalue())
    return prepared


def build_wide_sheet_reference(
    parts: dict[str, bytes], *, size: tuple[int, int] = (1920, 1080)
) -> bytes:
    """把四张 9:16 视角拼成 16:9 参考底图，供第二次图生图重排。"""
    width, height = size
    canvas = Image.new("RGB", size, (230, 230, 230))
    cell_width = width // 4
    for index, key in enumerate(("front", "side", "back", "portrait")):
        raw = parts.get(key)
        if not raw:
            continue
        source = Image.open(io.BytesIO(raw)).convert("RGB")
        scale = min(cell_width / source.width, height / source.height)
        fitted = source.resize(
            (max(1, int(source.width * scale)), max(1, int(source.height * scale))),
            Image.Resampling.LANCZOS,
        )
        canvas.paste(
            fitted,
            (index * cell_width + (cell_width - fitted.width) // 2, (height - fitted.height) // 2),
        )
    return _encode_png(canvas)


def appearance_prefix(character: Character) -> str:
    """写进画面提示词前面的固定外观。"""
    detail = clean_appearance(character.description)
    if detail:
        return f"角色{character.name}：{detail}。"
    return f"角色{character.name}。"


def slot_path(character: Character, slot: str) -> str | None:
    attr = _SLOT_ATTR.get(slot)
    if attr is None:
        return None
    return getattr(character, attr, None)


def _fit_sheet_size(
    pack: Any, width: int, height: int
) -> tuple[int, int]:
    """按工作流宽高上限等比缩小；保持 16:9 或 9:16 的精确比例。"""
    max_width = int((pack.inputs.get("width") or {}).get("max") or width)
    max_height = int((pack.inputs.get("height") or {}).get("max") or height)
    if width * 16 == height * 9:
        scale = min(width // 9, height // 16, max_width // 9, max_height // 16)
        scale = max(2, (scale // 2) * 2)
        return 9 * scale, 16 * scale
    if width * 9 == height * 16:
        scale = min(width // 16, height // 9, max_width // 16, max_height // 9)
        scale = max(2, (scale // 2) * 2)
        return 16 * scale, 9 * scale
    factor = min(1.0, max_width / width, max_height / height)
    return (
        max(256, int(width * factor) // 32 * 32),
        max(256, int(height * factor) // 32 * 32),
    )


def _sheet_inputs(
    pack_name: str,
    prompt: str,
    *,
    width: int = SHEET_WIDTH,
    height: int = SHEET_HEIGHT,
) -> dict[str, Any]:
    """按工作流包的宽高上限，给出目标排版尺寸。"""
    pack = get_pack(pack_name)
    inputs: dict[str, Any] = {"prompt": prompt}
    if "width" in pack.inputs and "height" in pack.inputs:
        inputs["width"], inputs["height"] = _fit_sheet_size(pack, width, height)
    else:
        if "width" in pack.inputs:
            inputs["width"] = min(width, int(pack.inputs["width"].get("max") or width))
        if "height" in pack.inputs:
            inputs["height"] = min(height, int(pack.inputs["height"].get("max") or height))
    return inputs


def _image_keys(pack: Any) -> list[str]:
    return [key for key, spec in pack.inputs.items() if spec.get("type") == "image"]


def _save_temp_refs(job: Job, prepared: list[bytes], prefix: str) -> list[str]:
    saved: list[str] = []
    for index, content in enumerate(prepared):
        rel = f"outputs/{job.id}/{prefix}_{index}.png"
        save_bytes(content, rel)
        saved.append(rel)
    return saved


def _dedupe_paths(paths: list[str]) -> list[str]:
    chosen: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if path and path not in seen:
            seen.add(path)
            chosen.append(path)
    return chosen


def _modify_ref_paths(
    target: str, slots: dict[str, str | None], supplement: str | None
) -> list[str]:
    """Picture 1 = 当前视角，Picture 2 = 补充参考，其余视角按特写/正/侧/背。"""
    paths = [slots.get(target) or ""]
    if supplement:
        paths.append(supplement)
    for slot in CHARACTER_VIEW_SLOTS:
        if slot != target:
            paths.append(slots.get(slot) or "")
    return _dedupe_paths(paths)


def _completion_refs(
    slot: str,
    slots: dict[str, str | None],
    generated: dict[str, bytes],
    user_refs: list[str],
) -> list[bytes]:
    anchors = {
        "portrait": ("front",),
        "front": ("portrait",),
        "side": ("front", "portrait"),
        "back": ("front", "portrait", "side"),
    }.get(slot, ())
    refs: list[bytes] = []
    for anchor in anchors:
        if anchor in generated:
            refs.append(generated[anchor])
        elif slots.get(anchor):
            refs.append(resolve(str(slots[anchor])).read_bytes())
    refs.extend(resolve(path).read_bytes() for path in user_refs)
    return refs


def _translate_ref_prompt(text: str, pack: Any) -> str:
    """把 <Picture N> 和槽位 label 换成工作流包实际 mention。"""
    for index, key in enumerate(_image_keys(pack), start=1):
        spec = pack.inputs.get(key) or {}
        mention = str(spec.get("mention") or "").strip()
        label = str(spec.get("label") or "").strip()
        replacement = mention or label or f"image {index}"
        text = re.sub(rf"<Picture\s+{index}>", replacement, text, flags=re.IGNORECASE)
        if label and label != replacement:
            text = text.replace(label, replacement)
    return re.sub(
        r"<Picture\s+(\d+)>",
        lambda match: f"image {match.group(1)}",
        text,
        flags=re.IGNORECASE,
    )


def _translate_cloud_prompt(text: str) -> str:
    return re.sub(
        r"<Picture\s+(\d+)>",
        lambda match: f"参考图 {match.group(1)}",
        text,
        flags=re.IGNORECASE,
    )


def _comfy_request(
    config: dict[str, Any],
    refs: list[bytes],
    prompt: str,
    job: Job,
    *,
    prefix: str,
    size: tuple[int, int],
    warnings: list[str],
) -> tuple[str, dict[str, Any], str]:
    workflows = dict(config.get("workflows") or {})
    order = ["multi", "single", "t2i"] if len(refs) > 1 else ["single", "t2i"]
    if not refs:
        order = ["t2i"]
    workflow = ""
    for key in order:
        if str(workflows.get(key) or "").strip():
            workflow = str(workflows[key]).strip()
            break
    if not workflow:
        raise ProviderError("没有可用的角色生图工作流")
    pack = get_pack(workflow)
    keys = _image_keys(pack)
    if refs and not keys:
        if not workflows.get("t2i"):
            raise ProviderError(f"工作流 {workflow} 没有图片槽")
        warnings.append(f"工作流 {workflow} 没有图片槽，已改用文字生成")
        return _comfy_request(
            {**config, "workflows": {**workflows, "t2i": workflows["t2i"]}},
            [],
            prompt,
            job,
            prefix=prefix,
            size=size,
            warnings=warnings,
        )
    limit = len(keys) if keys else 0
    if len(refs) > limit:
        warnings.append(f"当前工作流只有 {limit} 个图片槽，多余参考图已丢弃")
        refs = refs[:limit]
    final_prompt = _translate_ref_prompt(prompt, pack)
    if not refs:
        if "width" in pack.inputs and "height" in pack.inputs:
            inputs = _sheet_inputs(workflow, final_prompt, width=size[0], height=size[1])
        else:
            inputs = {"prompt": final_prompt}
        return workflow, inputs, final_prompt
    prepared = prepare_character_ref_images(refs, target=size)
    saved = _save_temp_refs(job, prepared, prefix)
    inputs: dict[str, Any] = {"prompt": final_prompt}
    for key, path in zip(keys, saved, strict=False):
        inputs[key] = path
    for key in keys:
        spec = pack.inputs.get(key) or {}
        if spec.get("required") and not inputs.get(key):
            raise ProviderError(f"工作流 {workflow} 缺少必需的图像输入：{spec.get('label') or key}")
    return workflow, inputs, final_prompt


def _cloud_size(provider: Any, *, wide: bool) -> str:
    if provider.type == "volcengine_ark":
        return "2K"
    if provider.type == "openai_images":
        return "1536x1024" if wide else "1024x1536"
    return f"{SHEET_WIDTH}x{SHEET_HEIGHT}" if wide else f"{VIEW_WIDTH}x{VIEW_HEIGHT}"


def _cloud_ref_limit(provider: Any) -> int:
    if provider.type == "volcengine_ark":
        return 4
    return 1


async def _generate_cloud_image(
    provider: Any,
    config: dict[str, Any],
    refs: list[bytes],
    prompt: str,
    *,
    wide: bool,
    prefix: str,
    warnings: list[str],
) -> bytes:
    adapter = build_image_adapter(provider)
    model = str(config.get("model") or "").strip() or None
    if not model:
        raise ProviderError("非 ComfyUI 服务商需要配置角色生图模型")
    size = _cloud_size(provider, wide=wide)
    final_prompt = _translate_cloud_prompt(prompt)
    limit = _cloud_ref_limit(provider)
    if len(refs) > limit:
        warnings.append(f"当前服务商最多使用 {limit} 张参考图，多余参考图已丢弃")
        refs = refs[:limit]
    if not refs:
        images = await adapter.generate(prompt=final_prompt, size=size, model=model)
    elif not hasattr(adapter, "edit"):
        warnings.append("当前服务商不支持参考图，已改用纯文字生成")
        images = await adapter.generate(prompt=final_prompt, size=size, model=model)
    else:
        primary = (f"{prefix}.png", refs[0])
        if provider.type == "volcengine_ark" and len(refs) > 1:
            images = await adapter.edit(
                image=primary,
                prompt=final_prompt,
                size=size,
                model=model,
                images=[
                    _data_url(f"{prefix}_{index}.png", content)
                    for index, content in enumerate(refs[1:], 1)
                ],
            )
        else:
            if len(refs) > 1:
                warnings.append("当前服务商只支持单张参考图，多余参考图已丢弃")
            images = await adapter.edit(
                image=primary, prompt=final_prompt, size=size, model=model
            )
    if not images:
        raise ProviderError("角色视角生成失败")
    return images[0][1]


async def _generate_view(
    provider: Any,
    config: dict[str, Any],
    refs: list[bytes],
    prompt: str,
    job: Job,
    timeout: float,
    *,
    slot: str,
    on_progress: Any = None,
    warnings: list[str],
) -> bytes:
    if provider.type == "comfyui":
        workflow, inputs, final_prompt = _comfy_request(
            config,
            refs,
            prompt,
            job,
            prefix=f"view_{slot}",
            size=(VIEW_WIDTH, VIEW_HEIGHT),
            warnings=warnings,
        )
        images = await produce_images(
            provider,
            workflow=workflow,
            inputs=inputs,
            prompt=final_prompt,
            wait_timeout=timeout,
            on_progress=on_progress,
        )
    else:
        images = [
            (
                f"{slot}.png",
                await _generate_cloud_image(
                    provider,
                    config,
                    refs,
                    prompt,
                    wide=False,
                    prefix=f"view_{slot}",
                    warnings=warnings,
                ),
            )
        ]
        if on_progress:
            on_progress(1.0)
    if not images:
        raise ProviderError(f"{CHARACTER_VIEW_LABELS.get(slot, slot)}生成失败")
    return normalize_character_view(images[0][1])


async def _generate_wide_sheet(
    db: Session,
    job: Job,
    ctx: JobContext,
    provider: Any,
    timeout: float,
    description: str,
    parts: dict[str, bytes],
    config: dict[str, Any],
    warnings: list[str],
) -> bytes | None:
    """用四张 9:16 视角和 2×2 合成图，再生成一次原生 16:9 定妆照。"""
    if provider is None or str(config.get("mode") or "") == "compose":
        return None
    composite = build_wide_sheet_reference(parts)
    refs = [composite]
    refs.extend(parts[slot] for slot in ("portrait", "front", "side", "back") if parts.get(slot))
    prompt = (
        sheet_prompt(description, references=len(refs), layout="wide").rstrip("。")
        + "。"
        + WIDE_REFERENCE_PROMPT
    )
    ctx.report(db, job, progress=0.66, step="sheet_wide")
    if provider.type == "comfyui":
        workflow, inputs, final_prompt = _comfy_request(
            config,
            refs,
            prompt,
            job,
            prefix="wide_ref",
            size=(SHEET_WIDTH, SHEET_HEIGHT),
            warnings=warnings,
        )
        images = await produce_images(
            provider,
            workflow=workflow,
            inputs=inputs,
            prompt=final_prompt,
            wait_timeout=timeout,
            on_progress=lambda progress: ctx.report(
                db, job, progress=0.66 + 0.28 * progress, step="sheet_wide"
            ),
        )
    else:
        images = [
            (
                "wide.png",
                await _generate_cloud_image(
                    provider,
                    config,
                    refs,
                    prompt,
                    wide=True,
                    prefix="wide_ref",
                    warnings=warnings,
                ),
            )
        ]
    if not images:
        raise ProviderError("16:9 定妆照生成失败")
    return normalize_character_wide(images[0][1])


async def run_character_generate_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """四张 9:16 单视角 → 程序合成四宫格 → 16:9 定妆照（失败时合成兜底）。"""
    params = job.params
    character = db.get(Character, params["character_id"])
    if character is None or character.owner_id != job.owner_id:
        raise ProviderError("角色不存在")
    config = dict(params.get("config") or {})
    mode = str(config.get("mode") or "compose")
    provider = pick_provider(db, "image", job.provider_id) if mode in ("workflow", "model") else None
    timeout = float(get_pref(db, "comfy_wait_timeout_seconds"))
    description = str(
        params.get("description") or character.description or character.name
    ).strip()
    prompt = str(params.get("prompt") or "").strip()
    target = str(params.get("target_view") or "").strip()
    order = "body" if str(params.get("order") or "") == "body" else "face"
    slot_paths = {
        slot: (params.get("slots") or {}).get(slot) or slot_path(character, slot)
        for slot in CHARACTER_VIEW_SLOTS
    }
    # 兼容旧任务：无目标视角、无槽图时，prompt 就是外观描述。
    if prompt and not target and not any(slot_paths.values()):
        description = prompt
        prompt = ""
    uploaded = {
        slot: path
        for slot, path in (params.get("uploaded_slots") or {}).items()
        if slot in CHARACTER_VIEW_SLOTS and path
    }
    ref_paths = [str(path) for path in params.get("ref_image_paths") or [] if path]
    if params.get("ref_image_path"):
        ref_paths.insert(0, str(params["ref_image_path"]))
    ref_paths = _dedupe_paths(ref_paths)
    if any(slot_paths.values()) and not slot_paths.get("portrait") and not slot_paths.get("front"):
        raise ProviderError("至少需要面部特写或正面全身")

    warnings: list[str] = []
    generated: dict[str, bytes] = {}

    def raw_for(slot: str) -> bytes:
        if slot in generated:
            return generated[slot]
        path = slot_paths.get(slot)
        if not path:
            raise ProviderError(f"缺少{CHARACTER_VIEW_LABELS[slot]}，无法完成四视图")
        return resolve(path).read_bytes()

    steps = [slot for slot in VIEW_ORDER[order] if not slot_paths.get(slot)]
    total_steps = max(1, len(steps) + (1 if prompt else 0))
    step_index = 0

    def progress_callback() -> Any:
        def report(progress: float) -> None:
            ctx.report(
                db,
                job,
                progress=0.05 + 0.55 * min(1.0, progress),
                step="character_view",
            )

        return report

    if prompt:
        if target not in CHARACTER_VIEW_SLOTS:
            raise ProviderError("请选择要修改的目标视角")
        if not slot_paths.get(target):
            raise ProviderError("目标视角还没有图片，无法按提示词修改")
        refs = [
            resolve(path).read_bytes()
            for path in _modify_ref_paths(target, slot_paths, params.get("ref_image_path"))
        ]
        edit_prompt = view_prompt(
            description, target, references=len(refs), edit_prompt=prompt
        )
        generated[target] = await _generate_view(
            provider,
            config,
            refs,
            edit_prompt,
            job,
            timeout,
            slot=target,
            on_progress=progress_callback(),
            warnings=warnings,
        )
        step_index += 1
        if ctx.cancelled():
            return []

    missing = [slot for slot in VIEW_ORDER[order] if not slot_paths.get(slot) and slot not in generated]
    for slot in missing:
        if ctx.cancelled():
            return []
        refs = _completion_refs(slot, slot_paths, generated, ref_paths)
        prompt_text = view_prompt(description, slot, references=len(refs))
        start = 0.05 + 0.55 * (step_index / total_steps)
        span = 0.55 / total_steps

        def report(
            progress: float, start: float = start, span: float = span, slot: str = slot
        ) -> None:
            ctx.report(
                db,
                job,
                progress=start + span * min(1.0, progress),
                step=f"character_{slot}",
            )

        generated[slot] = await _generate_view(
            provider,
            config,
            refs,
            prompt_text,
            job,
            timeout,
            slot=slot,
            on_progress=report,
            warnings=warnings,
        )
        step_index += 1
        if ctx.cancelled():
            return []

    parts = {slot: raw_for(slot) for slot in CHARACTER_VIEW_SLOTS}
    grid = compose_character_grid(parts)
    ctx.report(db, job, progress=0.65, step="grid_compose")

    wide: bytes | None = None
    compose_only = not prompt and all(slot_paths.get(slot) for slot in CHARACTER_VIEW_SLOTS)
    if provider is not None and not compose_only:
        try:
            wide = await _generate_wide_sheet(
                db, job, ctx, provider, timeout, description, parts, config, warnings
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("角色 {} 的 16:9 定妆照生成失败: {}", character.id, exc)
            warnings.append(f"16:9 定妆照生成失败，已改用四视图合成（{exc}）")
    if wide is None:
        wide = build_wide_sheet_reference(parts)
    else:
        wide = normalize_character_wide(wide)

    new_paths: dict[str, str] = {}
    for slot in CHARACTER_VIEW_SLOTS:
        if slot in generated:
            new_paths[slot] = save_character_bytes(generated[slot], ".png")
        elif slot in uploaded:
            new_paths[slot] = str(uploaded[slot])
        else:
            new_paths[slot] = str(slot_paths[slot])
    character.portrait_path = new_paths["portrait"]
    character.front_path = new_paths["front"]
    character.side_path = new_paths["side"]
    character.back_path = new_paths["back"]
    character.turnaround_grid_path = save_character_bytes(grid, ".png")
    character.turnaround_path = save_character_bytes(wide, ".png")
    db.commit()
    ctx.report(db, job, progress=1.0, step="done")
    content = f"角色 {character.name} 的六张设定图已更新"
    if warnings:
        content += "；" + "；".join(dict.fromkeys(warnings))
    return [{"type": "text", "content": content}]


def register_character_jobs(manager: JobManager) -> None:
    manager.register("character.generate", run_character_generate_job)


def _column_activity(image: Image.Image) -> list[float]:
    """每一列的亮度标准差。人身上颜色变化大，空隙和渐变背景几乎是平的。"""
    width, height = image.size
    pixels = image.load()
    step = max(1, height // 180)
    count = sum(1 for _ in range(0, height, step))
    total = [0.0] * width
    total_sq = [0.0] * width
    for y in range(0, height, step):
        for x in range(width):
            red, green, blue = pixels[x, y]
            luma = 0.299 * red + 0.587 * green + 0.114 * blue
            total[x] += luma
            total_sq[x] += luma * luma
    activity: list[float] = []
    for x in range(width):
        mean = total[x] / count
        variance = max(0.0, total_sq[x] / count - mean * mean)
        activity.append(variance**0.5)
    return activity


def _smooth(values: list[float], radius: int) -> list[float]:
    smoothed: list[float] = []
    for index in range(len(values)):
        start = max(0, index - radius)
        end = min(len(values), index + radius + 1)
        smoothed.append(sum(values[start:end]) / (end - start))
    return smoothed


def _interior_gaps(activity: list[float], threshold: float) -> list[tuple[int, int]]:
    """低于阈值的连续列。贴着左右边缘的是画面留白，不当成人物之间的缝。"""
    width = len(activity)
    gaps: list[tuple[int, int]] = []
    start: int | None = None
    for x, value in enumerate(activity):
        if value <= threshold:
            if start is None:
                start = x
        elif start is not None:
            gaps.append((start, x))
            start = None
    if start is not None:
        gaps.append((start, width))
    min_width = max(3, width // 80)
    interior: list[tuple[int, int]] = []
    for gap_start, gap_end in gaps:
        if gap_end - gap_start < min_width:
            continue
        if gap_start <= 1 or gap_end >= width - 1:
            continue
        interior.append((gap_start, gap_end))
    return interior


def _sheet_cuts(activity: list[float]) -> list[int]:
    """返回三条切线的 x。优先取最干净的三条空隙的中点。"""
    width = len(activity)
    smoothed = _smooth(activity, max(2, width // 80))
    ordered = sorted(smoothed)
    baseline = ordered[width // 5]
    peak = ordered[min(width - 1, int(width * 0.9))]
    spread = peak - baseline
    if spread >= 4:
        for factor in (0.08, 0.12, 0.18, 0.28, 0.4, 0.55):
            gaps = _interior_gaps(smoothed, baseline + spread * factor)
            if len(gaps) < 3:
                continue
            chosen = gaps
            if len(chosen) > 3:
                widest = sorted(chosen, key=lambda item: item[1] - item[0], reverse=True)[:3]
                chosen = sorted(widest)
            mids = [(start + end) // 2 for start, end in chosen]
            edges = [0, *mids, width]
            panel_wide = all(edges[index + 1] - edges[index] >= width * 0.08 for index in range(4))
            separated = all(mids[index + 1] - mids[index] >= width * 0.1 for index in range(2))
            if panel_wide and separated:
                return mids
    return [int(width * 0.23), int(width * 0.45), int(width * 0.68)]


def _top_column_colors(image: Image.Image) -> tuple[list[tuple[float, float, float]], list[bool]]:
    """每列顶部的平均色，以及这一小段是不是纯背景。头顶的头发方差会很高。"""
    width, height = image.size
    pixels = image.load()
    top = max(4, height // 8)
    step = max(1, top // 40)
    colors: list[tuple[float, float, float]] = []
    flat: list[bool] = []
    for x in range(width):
        samples = [pixels[x, y] for y in range(0, top, step)]
        count = len(samples)
        mean = tuple(sum(pixel[channel] for pixel in samples) / count for channel in range(3))
        variance = sum(
            sum((pixel[channel] - mean[channel]) ** 2 for channel in range(3)) for pixel in samples
        )
        colors.append(mean)
        flat.append(variance / count < 400)
    return colors, flat


def _color_delta(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return sum(abs(left[channel] - right[channel]) for channel in range(3))


def _nudge_portrait_cut(image: Image.Image, cuts: list[int]) -> list[int]:
    """特写背景和全身不是同一种颜色时，切在跳变结束的那一列。"""
    if len(cuts) != 3:
        return cuts
    width = image.size[0]
    colors, flat = _top_column_colors(image)
    end = int(width * 0.92)
    best_at = -1
    best_delta = 0.0
    for x in range(cuts[1] + 1, end - 1):
        if not flat[x] or not flat[x + 1]:
            continue
        delta = _color_delta(colors[x], colors[x + 1])
        if delta > best_delta:
            best_delta = delta
            best_at = x
    if best_at < 0 or best_delta < 70:
        return cuts
    edge = best_at + 1
    while edge < end - 1 and flat[edge] and flat[edge + 1]:
        if _color_delta(colors[edge], colors[edge + 1]) <= 20:
            break
        edge += 1
    if edge <= cuts[1] + int(width * 0.08) or width - edge < int(width * 0.18):
        return cuts
    return [cuts[0], cuts[1], edge]


def _ext_of(content: bytes, filename: str = "") -> str:
    if filename and "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    if content.startswith(b"\xff\xd8"):
        return ".jpg"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return ".webp"
    return ".png"


def remove_character_assets(db: Session, character: Character) -> int:
    """删除角色登记过的一切资产记录、源文件与缩略图。"""
    from sqlalchemy import select

    from liberastra.media.thumbs import remove_asset_thumb
    from liberastra.models import Asset

    rows = db.scalars(select(Asset).where(Asset.owner_id == character.owner_id)).all()
    removed = 0
    for asset in rows:
        if (asset.meta or {}).get("character_id") != character.id:
            continue
        try:
            resolve(asset.path).unlink(missing_ok=True)
        except ValueError:
            pass
        remove_asset_thumb(asset.id)
        db.delete(asset)
        removed += 1
    return removed


def remove_character_files(character: Character) -> None:
    seen: set[str] = set()
    for slot in SLOTS:
        rel = slot_path(character, slot)
        if not rel or rel in seen:
            continue
        seen.add(rel)
        try:
            resolve(rel).unlink(missing_ok=True)
        except ValueError:
            continue
