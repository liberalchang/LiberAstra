"""角色库：三视图切分、按任务取单视角图、生成主图与三视图。"""

from __future__ import annotations

import io
import re
import uuid
from typing import Any

from PIL import Image
from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext, JobManager
from liberastra.models import Character, Job
from liberastra.providers.base import ProviderError
from liberastra.services.image import produce_images
from liberastra.services.preferences import get_pref, get_str_pref
from liberastra.services.providers import pick_provider
from liberastra.services.workflows import get_pack
from liberastra.storage import resolve, save_bytes

SLOTS = ("portrait", "turnaround", "front", "side", "back")
_SLOT_ATTR = {
    "portrait": "portrait_path",
    "turnaround": "turnaround_path",
    "front": "front_path",
    "side": "side_path",
    "back": "back_path",
}

# 16:9 四段式定妆照。未点提示词优化时，拼在用户外观描述后面。
SHEET_PROMPT = (
    "16:9横版角色设定图，浅灰纯色影棚背景，画面从左到右依次展示完整全身正面、完整全身侧面、"
    "完整全身背面、右侧超大面部半身特写，四个视角保持同一人物、同一脸型、同一发型、同一服装与配饰。"
    "人物全身完整入镜，不裁脚，正面自然站立；右侧特写正面看向镜头，可带轻微俏皮眨眼表情。"
    "写实真人质感，柔和棚拍光，皮肤细腻通透，发丝清晰，服装面料真实，高级时尚Lookbook质感，8K超高清。"
)
SHEET_WIDTH = 1536
SHEET_HEIGHT = 864
# 这些句子是设定图排版，不能写进分镜画面提示词。
_LAYOUT_MARKERS = (
    "16:9",
    "横版角色设定",
    "画面依次展示",
    "画面从左到右",
    "四个视角",
    "完整全身正面",
    "右侧超大面部",
    "右侧特写",
    "不裁脚",
    "浅灰纯色",
    "影棚背景",
    "Lookbook",
    "8K",
    "写实真人质感",
    "柔和棚拍光",
)
_LAYOUT_PHRASES = (
    "角色三视图设定",
    "三视图设定",
    "四段式角色设定图",
    "四段式定妆照",
    "角色定妆照",
)


def save_character_bytes(content: bytes, suffix: str) -> str:
    """把角色图片写到 data/characters/，返回相对路径。"""
    ext = suffix if suffix.startswith(".") else f".{suffix.lstrip('.')}"
    rel = f"characters/{uuid.uuid4().hex[:12]}{ext}"
    save_bytes(content, rel)
    return rel


def split_turnaround(content: bytes) -> tuple[bytes, bytes, bytes, bytes]:
    """把横版四段式设定图切成正面、侧面、背面、面部特写四张 PNG。

    优先按浅色竖缝切成四栏；缝不够时按三个全身加右侧特写的比例切。
    """
    image = Image.open(io.BytesIO(content)).convert("RGB")
    width, height = image.size
    if width < 4 or height < 1:
        raise ProviderError("设定图尺寸过小，无法拆分")
    background = image.getpixel((0, 0))
    gaps: list[tuple[int, int]] = []
    gap_start: int | None = None
    min_gap = max(4, width // 40)
    for x in range(width):
        if _column_is_background(image, x, height, background):
            if gap_start is None:
                gap_start = x
        elif gap_start is not None:
            if x - gap_start > min_gap:
                gaps.append((gap_start, x))
            gap_start = None
    interior = [(a, b) for a, b in gaps if a > width * 0.08 and b < width * 0.92]
    if len(interior) >= 3:
        widest = sorted(interior, key=lambda item: item[1] - item[0], reverse=True)[:3]
        mids = sorted((a + b) // 2 for a, b in widest)
        edges = [0, *mids, width]
        boxes = [(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]
    else:
        cuts = [0, int(width * 0.23), int(width * 0.45), int(width * 0.68), width]
        boxes = [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)]
    parts: list[bytes] = []
    for left, right in boxes:
        if right - left < 2:
            raise ProviderError("设定图切分失败，请改用四段式横版图")
        buffer = io.BytesIO()
        image.crop((left, 0, right, height)).save(buffer, format="PNG")
        parts.append(buffer.getvalue())
    return parts[0], parts[1], parts[2], parts[3]


def apply_split(character: Character, turnaround: bytes) -> None:
    """保存四段式原图，并写入正面、侧面、背面和面部特写。"""
    front, side, back, portrait = split_turnaround(turnaround)
    character.turnaround_path = save_character_bytes(turnaround, _ext_of(turnaround))
    character.front_path = save_character_bytes(front, ".png")
    character.side_path = save_character_bytes(side, ".png")
    character.back_path = save_character_bytes(back, ".png")
    character.portrait_path = save_character_bytes(portrait, ".png")


def paths_for_task(character: Character, view: str, *, multi: bool) -> list[str]:
    """按任务取图。多视角任务只用正/侧/背全身图，单图任务按所选视角取一张。"""
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
    """去掉四段式排版句，只留能写进分镜的人物外观。"""
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


def sheet_prompt(text: str) -> str:
    """用户没写四段式构图时，补上固定的定妆照要求。"""
    body = text.strip()
    if "完整全身正面" in body or "16:9" in body:
        return body
    if body.endswith("。"):
        return body + SHEET_PROMPT
    return f"{body}。{SHEET_PROMPT}"


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
    return getattr(character, attr)


def _sheet_inputs(pack_name: str, prompt: str) -> dict[str, Any]:
    """按工作流包的宽高上限，给出 16:9 四段式定妆照参数。"""
    pack = get_pack(pack_name)
    inputs: dict[str, Any] = {"prompt": prompt}
    if "width" in pack.inputs:
        limit = int(pack.inputs["width"].get("max") or SHEET_WIDTH)
        inputs["width"] = min(SHEET_WIDTH, limit)
    if "height" in pack.inputs:
        limit = int(pack.inputs["height"].get("max") or SHEET_HEIGHT)
        inputs["height"] = min(SHEET_HEIGHT, limit)
    return inputs


async def run_character_generate_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """外观描述 → 16:9 四段式定妆照 → 切成正/侧/背/面部特写。"""
    params = job.params
    character = db.get(Character, params["character_id"])
    if character is None or character.owner_id != job.owner_id:
        raise ProviderError("角色不存在")
    provider = pick_provider(db, "image", job.provider_id)
    timeout = float(get_pref(db, "comfy_wait_timeout_seconds"))
    workflow = str(params.get("t2i_workflow") or "").strip()
    if not workflow:
        workflow = get_str_pref(db, "default_character_workflow").strip() or "qwen_image_21"
    description = str(
        params.get("prompt") or params.get("description") or character.description or character.name
    )
    prompt = sheet_prompt(description)

    ctx.report(db, job, progress=0.1, step="sheet")
    images = await produce_images(
        provider,
        workflow=workflow,
        inputs=_sheet_inputs(workflow, prompt),
        prompt=prompt,
        wait_timeout=timeout,
        on_progress=lambda progress: ctx.report(db, job, progress=0.1 + 0.8 * progress, step="sheet"),
    )
    if ctx.cancelled() or not images:
        return []
    apply_split(character, images[0][1])
    db.commit()
    ctx.report(db, job, progress=1.0, step="done")
    return [{"type": "text", "content": f"角色 {character.name} 的四段式定妆照已生成"}]


def register_character_jobs(manager: JobManager) -> None:
    manager.register("character.generate", run_character_generate_job)


def _column_is_background(image: Image.Image, x: int, height: int, background: tuple[int, int, int]) -> bool:
    hits = 0
    samples = 0
    for y in range(0, height, 4):
        pixel = image.getpixel((x, y))
        samples += 1
        if sum(abs(int(a) - int(b)) for a, b in zip(pixel, background, strict=False)) < 36:
            hits += 1
    return samples > 0 and hits / samples > 0.9


def _ext_of(content: bytes, filename: str = "") -> str:
    if filename and "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    if content.startswith(b"\xff\xd8"):
        return ".jpg"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return ".webp"
    return ".png"


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
