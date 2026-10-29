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
    "16:9横版角色设定图，浅灰纯色影棚背景，四段使用同一浅灰背景，段与段之间留出空白间隔，"
    "头发、披帛和手臂不要伸进间隔或其他栏。"
    "画面从左到右依次展示完整全身正面、完整全身侧面、"
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
    "空白间隔",
    "不要伸进",
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


def apply_split(character: Character, turnaround: bytes) -> None:
    """保存四段式原图，并写入正面、侧面、背面和面部特写。"""
    front, side, back, portrait = split_turnaround(turnaround)
    character.turnaround_path = save_character_bytes(turnaround, _ext_of(turnaround))
    character.front_path = save_character_bytes(front, ".png")
    character.side_path = save_character_bytes(side, ".png")
    character.back_path = save_character_bytes(back, ".png")
    character.portrait_path = save_character_bytes(portrait, ".png")


BODY_VIEWS = ("front", "side", "back")
REF_VIEWS = ("portrait", "front", "side", "back")


def reference_views(capability: str, slot_count: int, primary: str) -> list[str]:
    """按下游图片槽位数决定送哪些视角。口播只送特写；动作迁移只送全身。

    选了定妆照时只送整张四段式原图，不再拆成正面、侧面、背面或特写。
    """
    if slot_count <= 0:
        return []
    if primary == "turnaround":
        return ["turnaround"]
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
        meta={
            "character_id": character.id,
            "character_slot": slot,
            "character_name": character.name,
        },
    )


def paths_for_task(character: Character, view: str, *, multi: bool) -> list[str]:
    """按任务取图。多视角任务只用正/侧/背全身图，单图任务按所选视角取一张。

    定妆照是整张四段式原图，选中后不再改送切分后的单人图。
    """
    if view == "turnaround":
        if not character.turnaround_path:
            raise ProviderError("这个角色还没有定妆照")
        return [character.turnaround_path]
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


def sheet_prompt(text: str, *, references: int = 0) -> str:
    """用户没写四段式构图时，补上固定的定妆照要求。有参考图时先写明要保住的外观。"""
    body = text.strip()
    if references == 1:
        anchor = "保持参考图中的人物面部五官、发型与核心穿搭一致。"
    elif references > 1:
        anchor = "综合参考图中的正面、侧面、背面形象，保持同一人物与服装。"
    else:
        anchor = ""
    if anchor:
        body = f"{anchor}{body}" if body else anchor
    if "完整全身正面" in body or "16:9" in body:
        return body
    if body.endswith("。"):
        return body + SHEET_PROMPT
    return f"{body}。{SHEET_PROMPT}"


def prepare_character_ref_images(ref_bytes_list: list[bytes]) -> list[bytes]:
    """第一张贴进 16:9 浅灰画布，让图生图的输出画幅固定为横版定妆照。"""
    prepared: list[bytes] = []
    for index, raw in enumerate(ref_bytes_list[:3]):
        image = Image.open(io.BytesIO(raw))
        if index == 0:
            canvas = Image.new("RGB", (1920, 1080), (230, 230, 230))
            source = image.convert("RGB")
            scale = min(1920 / source.width, 1080 / source.height)
            fitted = source.resize(
                (max(1, int(source.width * scale)), max(1, int(source.height * scale))),
                Image.Resampling.LANCZOS,
            )
            canvas.paste(fitted, ((1920 - fitted.width) // 2, (1080 - fitted.height) // 2))
            image = canvas
        else:
            image = image.convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        prepared.append(buffer.getvalue())
    return prepared


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
    ref_paths = [path for path in params.get("ref_image_paths") or [] if path][:3]
    prompt = sheet_prompt(description, references=len(ref_paths))
    inputs = {"prompt": prompt}
    if ref_paths:
        prepared = prepare_character_ref_images([resolve(path).read_bytes() for path in ref_paths])
        saved: list[str] = []
        for index, content in enumerate(prepared):
            rel = f"outputs/{job.id}/ref_{index}.png"
            save_bytes(content, rel)
            saved.append(rel)
        if len(saved) == 1:
            workflow = get_str_pref(db, "default_character_i2i_workflow").strip() or "qwen_image_21_edit"
        else:
            workflow = (
                get_str_pref(db, "default_character_i2i_multi_workflow").strip()
                or "qwen_image_21_edit_multi"
            )
        pack = get_pack(workflow)
        image_keys = [key for key, spec in pack.inputs.items() if spec.get("type") == "image"]
        inputs = {"prompt": prompt}
        for key, path in zip(image_keys, saved, strict=False):
            inputs[key] = path
    else:
        inputs = _sheet_inputs(workflow, prompt)

    ctx.report(db, job, progress=0.1, step="sheet")
    images = await produce_images(
        provider,
        workflow=workflow,
        inputs=inputs,
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
