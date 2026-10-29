"""简单视频流水线：图生视频、数字人口播、动作迁移、自定义素材。

前三个交给具备对应能力的 ComfyUI 工作流包；自定义素材在平台侧合成。
"""

from __future__ import annotations

import math
import re
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext
from liberastra.media import ffmpeg
from liberastra.media.htmlframe import render_html
from liberastra.models import Job
from liberastra.pipelines.quick import (
    _chat_json,
    _single_cue_srt,
    job_path,
    split_script,
)
from liberastra.providers.base import ProviderError
from liberastra.providers.video.comfyui import ComfyUIVideo
from liberastra.services.preferences import get_pref
from liberastra.services.providers import (
    build_llm_adapter,
    build_tts_adapter,
    pick_llm_with_model,
    pick_provider,
)
from liberastra.services.workflows import get_pack
from liberastra.storage import create_asset, resolve


async def _run_video_pack(
    db: Session, job: Job, ctx: JobContext, inputs: dict[str, Any]
) -> list[dict[str, Any]]:
    provider = pick_provider(db, "video", job.provider_id)
    pack = get_pack(job.params["workflow"])
    adapter = ComfyUIVideo(provider.base_url)
    ctx.report(db, job, progress=0.1, step="comfyui")
    started = time.monotonic()
    videos, texts = await adapter.generate(
        pack=pack,
        inputs=inputs,
        on_progress=lambda p: ctx.report(db, job, progress=0.1 + 0.85 * p),
        wait_timeout=float(get_pref(db, "comfy_wait_timeout_seconds")),
    )
    if ctx.cancelled():
        return []
    base_meta = {
        "provider": provider.name,
        "prompt": inputs.get("prompt"),
        "workflow": job.params.get("workflow"),
        "duration_s": round(time.monotonic() - started, 1),
    }
    base_meta = {k: v for k, v in base_meta.items() if v not in (None, "")}
    outputs: list[dict[str, Any]] = []
    for i, (filename, content) in enumerate(videos):
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "mp4"
        rel_path = f"outputs/{job.id}/video_{i}.{ext}"
        from liberastra.storage import save_bytes

        save_bytes(content, rel_path)
        saved = resolve(rel_path)
        reference = None
        if str(job.params.get("audio_mode") or "") == "reference" and job.params.get("video_path"):
            reference = resolve(str(job.params["video_path"]))
        final = await _apply_soundtrack(saved, job.params, reference=reference)
        rel_path = _rel_of(final)
        asset = create_asset(
            db, kind="video", rel_path=rel_path, job_id=job.id, owner_id=job.owner_id,
            meta={**base_meta, "source_name": filename},
        )
        outputs.append(
            {"type": "asset", "asset_id": asset.id, "kind": "video", "filename": f"video_{i}.{ext}"}
        )
    # 增强包等声明了 outputs.texts 时，把增强提示词/报告带回结果页
    for block in texts:
        if block.strip():
            outputs.append({"type": "text", "content": block})
    ctx.report(db, job, progress=1.0)
    return outputs


async def _run_model_video(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """火山方舟等云端视频模型。产物保存方式与工作流包视频一致。"""
    from liberastra.services.model_media import generate_model_media

    params = job.params
    provider = pick_provider(db, "video", job.provider_id)
    sub = str(params.get("sub_capability") or "i2v_first")
    inputs = dict(params.get("inputs") or {})
    paths = [path for path in params.get("image_paths") or [] if path]
    if not paths and params.get("image_path"):
        paths = [params["image_path"]]
    if sub == "i2v_flf":
        if paths:
            inputs.setdefault("first_frame", paths[0])
        if len(paths) > 1:
            inputs.setdefault("last_frame", paths[1])
    elif sub == "v2v_ref":
        if paths:
            inputs.setdefault("reference_image", paths)
    elif paths:
        inputs.setdefault("first_frame", paths[0])
    ctx.report(db, job, progress=0.1, step="ark")
    started = time.monotonic()
    videos = await generate_model_media(
        provider,
        model=str(job.model or params.get("model") or ""),
        sub_capability=sub,
        prompt=str(params.get("prompt") or ""),
        inputs=inputs,
        on_progress=lambda progress: ctx.report(db, job, progress=0.1 + 0.85 * progress),
        wait_timeout=float(get_pref(db, "comfy_wait_timeout_seconds")),
    )
    if ctx.cancelled():
        return []
    outputs: list[dict[str, Any]] = []
    for index, (filename, content) in enumerate(videos):
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "mp4"
        rel_path = f"outputs/{job.id}/video_{index}.{ext}"
        from liberastra.storage import create_asset, save_bytes

        save_bytes(content, rel_path)
        asset = create_asset(
            db,
            kind="video",
            rel_path=rel_path,
            job_id=job.id,
            owner_id=job.owner_id,
            meta={
                "provider": provider.name,
                "model": job.model,
                "prompt": params.get("prompt"),
                "duration_s": round(time.monotonic() - started, 1),
            },
        )
        outputs.append(
            {"type": "asset", "asset_id": asset.id, "kind": "video", "filename": filename}
        )
    ctx.report(db, job, progress=1.0)
    return outputs


async def run_i2v_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """图生视频：图片 + 提示词 → i2v 工作流。

    提示词留空且包写了 default 时不写入，节点保留作者原句。
    少传的可选图由执行器按 manifest 的 fallback 补齐。
    云端模型不走工作流包，按 sub_capability 提交。
    """
    params = job.params
    if params.get("target_type") == "model":
        return await _run_model_video(db, job, ctx)
    pack = get_pack(params["workflow"])
    inputs = dict(params.get("inputs") or {})
    prompt = str(params.get("prompt") or "")
    prompt_spec = pack.inputs.get("prompt") or {}
    if prompt.strip() or not prompt_spec.get("default"):
        inputs["prompt"] = prompt
    image_keys = [key for key, spec in pack.inputs.items() if spec.get("type") == "image"]
    paths = [path for path in params.get("image_paths") or [] if path]
    if not paths and params.get("image_path"):
        paths = [params["image_path"]]
    for key, path in zip(image_keys, paths, strict=False):
        inputs[key] = path
    return await _run_video_pack(db, job, ctx, inputs)


def motion_prompt(raw_prompt: str, image_count: int) -> str:
    """没写标签时补上「外观跟图片、动作跟视频」。已经写了标签就原样使用。"""
    raw_prompt = raw_prompt.strip()
    if not raw_prompt:
        if image_count >= 3:
            return (
                "参考 <Picture 1>（正面）、<Picture 2>（侧面）、<Picture 3>（背面）里的同一个角色，"
                "让这个角色完整复刻 <Video 1> 的肢体动作、姿态变化与镜头运动，外观、五官和服装保持一致。"
            )
        return (
            "让 <Picture 1> 中的人物完整复刻 <Video 1> 中的肢体动作、姿态变化与镜头运动，"
            "保持 <Picture 1> 的人物外观、五官与服装一致，动作自然流畅。"
        )
    if "<Picture" not in raw_prompt and "<Video" not in raw_prompt:
        return f"参考 <Picture 1> 的人物外观，复刻 <Video 1> 的动作运动：{raw_prompt}"
    return raw_prompt


def max_reference_video_seconds(fps: float, spec: dict[str, Any]) -> float:
    """参考视频单段能完整送进模型的最长秒数。

    上限取工作流包 length 的 max，并落到 align_base * k + align_offset。
    """
    return max_aligned_seconds(fps, spec)


def motion_windows(total_seconds: float, fps: float, spec: dict[str, Any]) -> list[tuple[float, int]]:
    """把参考视频切成 (起点秒, 帧数)。每段帧数不超过剩余内容，且满足对齐规则。"""
    if fps <= 0:
        fps = 24.0
    if total_seconds <= 0:
        return []
    window = max_reference_video_seconds(fps, spec)
    base = int(spec.get("align_base") or 0)
    offset = int(spec.get("align_offset") or 0)
    maximum = int(spec.get("max") or 0) or 10**9

    def snap_down(seconds: float) -> int:
        target = max(0, int(seconds * fps + 1e-6))
        target = min(target, maximum)
        if target < 5:
            return 0
        if base <= 0:
            return target
        frames = base * ((target - offset) // base) + offset
        return frames if frames >= 5 else 0

    windows: list[tuple[float, int]] = []
    start = 0.0
    for _ in range(200):
        if start >= total_seconds - 0.02:
            break
        frames = snap_down(min(total_seconds - start, window))
        if frames < 5:
            break
        windows.append((start, frames))
        start += frames / fps
    return windows


def _rel_of(path: Path) -> str:
    return path.resolve().relative_to(resolve(".").resolve()).as_posix()


async def _apply_soundtrack(
    video: Path,
    params: dict[str, Any],
    *,
    reference: Path | None = None,
) -> Path:
    """按音频模式换成参考原声，再按需混入音乐库。没有改动时返回原文件。"""
    current = video
    if str(params.get("audio_mode") or "") == "reference" and reference is not None:
        if await ffmpeg.has_audio_stream(reference):
            swapped = current.with_name(f"{current.stem}_refaudio{current.suffix}")
            await ffmpeg.replace_audio(current, reference, swapped)
            current = swapped
    bgm = str(params.get("bgm_path") or "").strip()
    if bgm:
        mixed = current.with_name(f"{current.stem}_bgm{current.suffix}")
        await ffmpeg.add_bgm(
            video=current,
            bgm=resolve(bgm),
            out=mixed,
            bgm_volume=float(params.get("bgm_volume") or 0.2),
        )
        current = mixed
    return current


async def render_motion_takes(
    *,
    source: Path,
    image_paths: list[str],
    prompt_text: str,
    base_inputs: dict[str, Any],
    windows: list[tuple[float, int]],
    fps: float,
    video_key: str,
    image_keys: list[str],
    generate: Callable[[dict[str, Any], Callable[[float], None]], Awaitable[list[tuple[str, bytes]]]],
    work: Callable[[str], Path],
    rel_of: Callable[[Path], str],
    report: Callable[[float, str], None],
    cancelled: Callable[[], bool],
    slice_video: Callable[..., Awaitable[None]] = ffmpeg.slice_video,
    trim_video: Callable[..., Awaitable[None]] = ffmpeg.trim_video,
    last_frame: Callable[..., Awaitable[None]] = ffmpeg.extract_last_frame,
    concat: Callable[..., Awaitable[None]] = ffmpeg.concat_segments,
) -> Path | None:
    """按窗口切参考视频。下一段的第一张人物图换成上一段尾帧，侧面和背面保留。"""
    if not windows:
        raise ProviderError("参考视频太短，无法做动作迁移")
    if fps <= 0:
        fps = 24.0
    side_back = image_paths[1:]
    current_images = list(image_paths)
    clips: list[Path] = []
    count = len(windows)
    for index, (start, frames) in enumerate(windows):
        if cancelled():
            return None
        seconds = frames / fps
        ref = work(f"ref_{index:02d}.mp4")
        await slice_video(source, start, seconds, ref, fps=fps, frames=frames)
        inputs: dict[str, Any] = {"prompt": prompt_text, **base_inputs, "length": frames}
        inputs[video_key] = rel_of(ref)
        for key, path in zip(image_keys, current_images, strict=False):
            inputs[key] = path

        def on_progress(frac: float, *, _index: int = index) -> None:
            report(0.05 + 0.85 * (_index + frac) / count, f"分段 {_index + 1}/{count}")

        videos = await generate(inputs, on_progress)
        if cancelled():
            return None
        if not videos:
            raise ProviderError("动作迁移没有生成视频")
        raw = work(f"take_{index:02d}.mp4")
        raw.write_bytes(videos[0][1])
        trimmed = work(f"trim_{index:02d}.mp4")
        await trim_video(raw, trimmed, seconds, fps=fps)
        clips.append(trimmed)
        if index < count - 1:
            frame = work(f"last_{index:02d}.png")
            await last_frame(trimmed, frame, fps=fps)
            current_images = [rel_of(frame), *side_back]
    final = work("video_0.mp4")
    if len(clips) == 1:
        final.write_bytes(clips[0].read_bytes())
    else:
        report(0.92, "concat")
        await concat(clips, final, list_file=work("concat.txt"))
    return final


async def slice_audio_takes(
    audio: Path,
    *,
    ceiling: float,
    rel_path: str,
    work: Callable[[str], Path],
    rel_of: Callable[[Path], str],
    probe: Callable[[Path], Awaitable[float]] = ffmpeg.probe_duration,
    slice_audio: Callable[..., Awaitable[None]] = ffmpeg.slice_audio,
) -> list[tuple[str, str, float]]:
    """把已有音频按单段上限切开。不重新合成语音。短于上限时整段作为一次。"""
    duration = await probe(audio)
    if duration <= 0:
        raise ProviderError("无法读取音频时长")
    if duration <= ceiling + 0.05:
        return [("", rel_path, duration)]
    takes: list[tuple[str, str, float]] = []
    start = 0.0
    part = 0
    while start < duration - 0.05 and part < 200:
        piece = min(ceiling, duration - start)
        out = work(f"avatar_a_{part:02d}{audio.suffix or '.wav'}")
        await slice_audio(audio, start, piece, out)
        probed = await probe(out)
        takes.append(("", rel_of(out), probed or piece))
        start += piece
        part += 1
    if not takes:
        raise ProviderError("音频太短，无法做数字人")
    return takes


async def run_motion_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """动作迁移：参考视频按模型单段上限切开，尾帧接力，最后合成一条。"""
    params = job.params
    image_paths = [path for path in params.get("image_paths") or [] if path]
    if not image_paths and params.get("image_path"):
        image_paths = [params["image_path"]]
    prompt_text = motion_prompt(str(params.get("prompt") or ""), len(image_paths))
    source = resolve(str(params["video_path"]))
    pack = get_pack(params["workflow"])
    fps = float(pack.fps or 24)
    length_spec = pack.inputs.get("length") if "length" in pack.inputs else {}
    total = await ffmpeg.probe_duration(source)
    windows = motion_windows(total, fps, length_spec or {})
    if not windows:
        raise ProviderError("参考视频太短，无法做动作迁移")

    provider = pick_provider(db, "video", job.provider_id)
    adapter = ComfyUIVideo(provider.base_url)
    video_keys = _input_keys(params["workflow"], "video")
    image_keys = _input_keys(params["workflow"], "image")
    if not video_keys:
        raise ProviderError("工作流包没有视频输入")
    started = time.monotonic()
    timeout = float(get_pref(db, "comfy_wait_timeout_seconds"))

    async def generate(
        inputs: dict[str, Any], on_progress: Callable[[float], None]
    ) -> list[tuple[str, bytes]]:
        videos, _texts = await adapter.generate(
            pack=pack,
            inputs=inputs,
            on_progress=on_progress,
            wait_timeout=timeout,
        )
        return videos

    final = await render_motion_takes(
        source=source,
        image_paths=image_paths,
        prompt_text=prompt_text,
        base_inputs=dict(params.get("inputs") or {}),
        windows=windows,
        fps=fps,
        video_key=video_keys[0],
        image_keys=image_keys,
        generate=generate,
        work=lambda name: job_path(job, name),
        rel_of=_rel_of,
        report=lambda progress, step: ctx.report(db, job, progress=progress, step=step),
        cancelled=ctx.cancelled,
    )
    if final is None or ctx.cancelled():
        return []
    final = await _apply_soundtrack(final, params, reference=source)
    rel_path = _rel_of(final)
    asset = create_asset(
        db,
        kind="video",
        rel_path=rel_path,
        job_id=job.id,
        owner_id=job.owner_id,
        meta={
            "provider": provider.name,
            "workflow": params.get("workflow"),
            "prompt": prompt_text,
            "segments": len(windows),
            "audio_mode": params.get("audio_mode") or "model",
            "bgm": Path(str(params["bgm_path"])).name if params.get("bgm_path") else None,
            "duration_s": round(time.monotonic() - started, 1),
        },
    )
    ctx.report(db, job, progress=1.0, step="done")
    return [{"type": "asset", "asset_id": asset.id, "kind": "video", "filename": final.name}]


# 中文口播约 4.25 字/秒，英文约 2.5 词/秒。估算只用来合并分句，真正的帧数看 TTS 时长。
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")
_SENTENCE_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;\n]*")
_CLAUSE_RE = re.compile(r"[^，,、]+[，,、]*")
_CJK_PER_SEC = 4.25
_WORDS_PER_SEC = 2.5
# 比 H3 单段上限（约 15 秒）再留余量，避免合成后略超时又要重切
_GROUP_CAP_SECONDS = 12.0


def estimate_speech_seconds(text: str) -> float:
    """按字数粗估口播秒数，只用于分段，不用于最终帧数。"""
    cjk = len(_CJK_RE.findall(text))
    words = _WORD_RE.findall(_CJK_RE.sub(" ", text))
    seconds = cjk / _CJK_PER_SEC + len(words) / _WORDS_PER_SEC
    if seconds <= 0 and text.strip():
        seconds = max(len(text.strip()) / _CJK_PER_SEC, 0.4)
    return seconds


def frames_for_duration(duration: float, fps: float, spec: dict[str, Any]) -> int:
    """把秒数向上吸附到工作流允许的帧数。MiniMax H3 为 17k+5。"""
    if fps <= 0:
        fps = 24.0
    base = int(spec.get("align_base") or 0)
    offset = int(spec.get("align_offset") or 0)
    minimum = int(spec.get("min") or 1)
    maximum = int(spec.get("max") or 0) or 10**9
    target = max(1, math.ceil(max(0.0, duration) * fps))
    if base > 0:
        k = math.ceil(max(0, target - offset) / base)
        frames = base * k + offset
        if frames < minimum:
            k = math.ceil(max(0, minimum - offset) / base)
            frames = base * k + offset
    else:
        frames = target
    return max(minimum, min(maximum, frames))


def max_aligned_seconds(fps: float, spec: dict[str, Any]) -> float:
    """单段能完整播完的最长秒数：不超过 max、且满足对齐规则的最大帧数 / fps。"""
    if fps <= 0:
        fps = 24.0
    maximum = int(spec.get("max") or 0)
    if maximum <= 0:
        return 600.0
    base = int(spec.get("align_base") or 0)
    offset = int(spec.get("align_offset") or 0)
    minimum = int(spec.get("min") or 1)
    if base > 0:
        k = max(0, (maximum - offset) // base)
        frames = base * k + offset
        if frames < minimum:
            frames = minimum
    else:
        frames = maximum
    return frames / fps


def _text_pieces(text: str, pattern: re.Pattern[str]) -> list[str]:
    return [piece for piece in pattern.findall(text) if piece.strip()]


def _hard_split(text: str, max_seconds: float) -> list[str]:
    """没有标点的长句按估算字数切开，避免一段超过模型帧数上限。

    切点上的空格留在前一段末尾，合并时单词才不会粘在一起。
    """
    budget = max(8, int(max_seconds * _CJK_PER_SEC))
    parts: list[str] = []
    rest = text.strip()
    while rest:
        if estimate_speech_seconds(rest) <= max_seconds:
            parts.append(rest)
            break
        head, rest = rest[:budget], rest[budget:]
        if not head.strip():
            rest = rest.lstrip()
            continue
        parts.append(head)
    return parts


def split_avatar_script(text: str, max_seconds: float) -> list[str]:
    """先按句末标点切开，过长的句子再按逗号切，最后贪心合并到估算时长以内。"""
    raw = text.strip()
    if not raw:
        return []
    limit = max(max_seconds, 1.0)
    pieces = _text_pieces(raw, _SENTENCE_RE) or [raw]
    expanded: list[str] = []
    for piece in pieces:
        if estimate_speech_seconds(piece) <= limit:
            expanded.append(piece)
            continue
        clauses = _text_pieces(piece, _CLAUSE_RE) or [piece]
        for clause in clauses:
            if estimate_speech_seconds(clause) <= limit:
                expanded.append(clause)
            else:
                expanded.extend(_hard_split(clause, limit))
    grouped: list[str] = []
    buf = ""
    for piece in expanded:
        candidate = piece if not buf else f"{buf}{piece}"
        if buf and estimate_speech_seconds(candidate) > limit:
            grouped.append(buf.strip())
            buf = piece
        else:
            buf = candidate
    if buf.strip():
        grouped.append(buf.strip())
    return grouped


def split_text_half(text: str) -> list[str]:
    """在最靠近中点的标点处对半切。合成后仍超长时用来重做 TTS。"""
    marks = "。！？!?；;，,、\n "
    mid = len(text) // 2
    best: int | None = None
    for index, char in enumerate(text):
        if char in marks and 0 < index < len(text) - 1:
            if best is None or abs(index - mid) < abs(best - mid):
                best = index
    cleaned = text.strip()
    if best is None:
        if len(cleaned) < 8:
            return [cleaned] if cleaned else []
        return [part for part in (cleaned[:mid].strip(), cleaned[mid:].strip()) if part]
    left, right = text[: best + 1].strip(), text[best + 1 :].strip()
    if not left or not right:
        return [cleaned] if cleaned else []
    return [left, right]


async def _trim_take(video: Path, out: Path, seconds: float, fps: float) -> None:
    await ffmpeg.trim_video(video, out, seconds, fps=fps)


async def _concat_takes(segments: list[Path], out: Path, list_file: Path) -> None:
    await ffmpeg.concat_segments(segments, out, list_file=list_file)


def avatar_segment_prompt(text: str, custom: str) -> str:
    """每段提示词都带上这一段自己的台词，避免后段还在念整篇文案。

    画布按时间切开已有音频时没有逐句台词。text 为空则只保留画面提示。
    """
    spoken = text.strip()
    line = f'台词："{spoken}"' if spoken else ""
    custom = custom.strip()
    if custom and line:
        return f"{custom} {line}"
    if custom:
        return custom
    base = "正面人物面对镜头自然说话，口型与语音同步，面部表情生动自然。"
    return f"{base}{line}" if line else base


async def render_avatar_takes(
    *,
    takes: list[tuple[str, str, float]],
    first_image: str,
    base_inputs: dict[str, Any],
    length_spec: dict[str, Any] | None,
    fps: float,
    image_key: str,
    audio_key: str,
    custom_prompt: str,
    generate: Callable[[dict[str, Any], Callable[[float], None]], Awaitable[list[tuple[str, bytes]]]],
    work: Callable[[str], Path],
    rel_of: Callable[[Path], str],
    report: Callable[[float, str], None],
    cancelled: Callable[[], bool],
    trim: Callable[[Path, Path, float, float], Awaitable[None]] = _trim_take,
    last_frame: Callable[[Path, Path], Awaitable[None]] = ffmpeg.extract_last_frame,
    concat: Callable[[list[Path], Path, Path], Awaitable[None]] = _concat_takes,
) -> Path | None:
    """逐段生成口播，裁到配音时长，下一段用上一段尾帧，最后合成一条视频。"""
    if not takes:
        raise ProviderError("口播文案为空")
    total = len(takes)
    current_image = first_image
    clips: list[Path] = []
    for index, (line, audio_rel, duration) in enumerate(takes):
        if cancelled():
            return None
        start = 0.08 + 0.84 * index / total
        span = 0.84 / total

        def on_progress(frac: float, *, _start: float = start, _span: float = span, _i: int = index) -> None:
            report(_start + _span * frac, f"分段 {_i + 1}/{total}")

        inputs = {**base_inputs, "prompt": avatar_segment_prompt(line, custom_prompt)}
        if length_spec:
            # 向上取整到对齐帧数，多出来的画面在裁切时去掉，避免段间停顿叠在一起
            inputs["length"] = frames_for_duration(duration + 0.1, fps, length_spec)
        if image_key:
            inputs[image_key] = current_image
        if audio_key:
            inputs[audio_key] = audio_rel
        videos = await generate(inputs, on_progress)
        if not videos:
            raise ProviderError("ComfyUI 完成但未产出视频")
        raw = work(f"take_{index:02d}_raw.mp4")
        raw.write_bytes(videos[0][1])
        clip = work(f"take_{index:02d}.mp4")
        # 只多留一帧，尾帧就是观众看到的最后一帧，下一段不会往回跳
        await trim(raw, clip, duration + (1.0 / fps if fps > 0 else 0.04), fps)
        clips.append(clip)
        if index < total - 1:
            frame = work(f"take_{index:02d}_last.png")
            await last_frame(clip, frame)
            current_image = rel_of(frame)
    if cancelled():
        return None
    final = work("video_0.mp4")
    if len(clips) == 1:
        final.write_bytes(clips[0].read_bytes())
    else:
        report(0.94, "concat")
        await concat(clips, final, work("concat.txt"))
    return final


async def run_avatar_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """数字人口播：按配音时长出画面；超过单段上限则分段，并用上一段尾帧衔接。"""
    params = job.params
    spoken = str(params.get("text") or "").strip()
    if not spoken:
        raise ProviderError("口播文案为空")
    video_pack = get_pack(params["workflow"])
    length_spec = video_pack.inputs.get("length") if "length" in video_pack.inputs else None
    fps = float(video_pack.fps or 24)
    ceiling = max_aligned_seconds(fps, length_spec or {})
    group_limit = min(_GROUP_CAP_SECONDS, max(1.0, ceiling - 0.5))
    chunks = split_avatar_script(spoken, group_limit) or [spoken]

    tts_provider = pick_provider(db, "tts", params.get("tts_provider_id"))
    tts = build_tts_adapter(tts_provider, db=db)
    ctx.report(db, job, progress=0.05, step="tts")
    takes = await _speak_avatar_chunks(
        db, job, ctx, tts_provider, tts, chunks, ceiling=ceiling
    )
    if ctx.cancelled() or not takes:
        return []

    provider = pick_provider(db, "video", job.provider_id)
    adapter = ComfyUIVideo(provider.base_url)
    image_keys = _input_keys(params["workflow"], "image")
    audio_keys = _input_keys(params["workflow"], "audio")
    started = time.monotonic()

    async def generate(
        inputs: dict[str, Any], on_progress: Callable[[float], None]
    ) -> list[tuple[str, bytes]]:
        videos, _texts = await adapter.generate(
            pack=video_pack,
            inputs=inputs,
            on_progress=on_progress,
            wait_timeout=float(get_pref(db, "comfy_wait_timeout_seconds")),
        )
        return videos

    final = await render_avatar_takes(
        takes=takes,
        first_image=str(params.get("image_path") or ""),
        base_inputs=dict(params.get("inputs") or {}),
        length_spec=length_spec,
        fps=fps,
        image_key=image_keys[0] if image_keys else "",
        audio_key=audio_keys[0] if audio_keys else "",
        custom_prompt=str(params.get("prompt") or ""),
        generate=generate,
        work=lambda name: job_path(job, name),
        rel_of=lambda path: path.resolve().relative_to(resolve(".").resolve()).as_posix(),
        report=lambda progress, step: ctx.report(db, job, progress=progress, step=step),
        cancelled=ctx.cancelled,
    )
    if final is None or ctx.cancelled():
        return []
    final = await _apply_soundtrack(final, params)
    rel_path = _rel_of(final)
    asset = create_asset(
        db,
        kind="video",
        rel_path=rel_path,
        job_id=job.id,
        owner_id=job.owner_id,
        meta={
            "provider": provider.name,
            "workflow": params.get("workflow"),
            "prompt": spoken,
            "segments": len(takes),
            "bgm": Path(str(params["bgm_path"])).name if params.get("bgm_path") else None,
            "duration_s": round(time.monotonic() - started, 1),
        },
    )
    return [{"type": "asset", "asset_id": asset.id, "kind": "video", "filename": final.name}]


async def _speak_avatar_chunks(
    db: Session,
    job: Job,
    ctx: JobContext,
    tts_provider: Any,
    tts: Any,
    chunks: list[str],
    *,
    ceiling: float,
) -> list[tuple[str, str, float]]:
    """逐段合成语音。测得时长仍超过单段上限时，对半重做；切不开再按时间切音频。"""
    takes: list[tuple[str, str, float]] = []
    serial = 0

    async def speak(text: str, depth: int) -> None:
        nonlocal serial
        if ctx.cancelled():
            return
        ext, data = await _synthesize_avatar_line(db, tts_provider, tts, text, job.params)
        path = job_path(job, f"voiceover_{serial:02d}.{ext}")
        serial += 1
        path.write_bytes(data)
        duration = await ffmpeg.probe_duration(path)
        rel = f"outputs/{job.id}/{path.name}"
        if duration <= ceiling + 0.05 or depth >= 6:
            if duration > ceiling + 0.05:
                await _slice_overlong_audio(job, text, path, duration, ceiling, takes)
            else:
                takes.append((text, rel, duration))
            return
        halves = split_text_half(text)
        if len(halves) < 2:
            await _slice_overlong_audio(job, text, path, duration, ceiling, takes)
            return
        for half in halves:
            await speak(half, depth + 1)

    for chunk in chunks:
        await speak(chunk, 0)
        if ctx.cancelled():
            return []
    return takes


async def _synthesize_avatar_line(
    db: Session, tts_provider: Any, tts: Any, text: str, params: dict[str, Any]
) -> tuple[str, bytes]:
    """合成一句口播，返回 (扩展名, 音频字节)。"""
    if tts_provider.type == "comfyui":
        if not params.get("tts_workflow"):
            raise ProviderError("配音 Provider 是 ComfyUI，但没有选择语音工作流包")
        pack = get_pack(params["tts_workflow"])
        inputs = dict(params.get("tts_inputs") or {})
        if "text" in pack.inputs:
            inputs["text"] = text
        if "voice" in pack.inputs and params.get("voice"):
            inputs["voice"] = params["voice"]
        filename, audio = await tts.synthesize_pack(
            pack=pack,
            inputs=inputs,
            wait_timeout=float(get_pref(db, "comfy_wait_timeout_seconds")),
        )
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "mp3"
        return ext, audio
    extra: dict[str, Any] = {}
    if tts_provider.type == "liber_speech" and params.get("language"):
        extra["language"] = str(params["language"])
    if tts_provider.type == "liber_speech" and params.get("ref_audio"):
        extra["ref_audio"] = str(params["ref_audio"])
    audio = await tts.synthesize(text=text, voice=params.get("voice"), fmt="mp3", **extra)
    return "mp3", audio


async def _slice_overlong_audio(
    job: Job,
    text: str,
    audio: Path,
    duration: float,
    ceiling: float,
    takes: list[tuple[str, str, float]],
) -> None:
    """文案已经切不开时，把音频按单段上限切开，避免一帧都超限。"""
    start = 0.0
    part = 0
    while start < duration - 0.05:
        piece = min(ceiling, duration - start)
        out = job_path(job, f"{audio.stem}_p{part:02d}{audio.suffix}")
        await ffmpeg.slice_audio(audio, start, piece, out)
        probed = await ffmpeg.probe_duration(out)
        takes.append((text, f"outputs/{job.id}/{out.name}", probed or piece))
        start += piece
        part += 1


def _title_card_html(title: str, width: int, height: int) -> str:
    """标题卡 HTML：渐变底 + 居中大标题，经模板渲染线程截成帧图。"""
    import html as _html

    t = _html.escape(title)
    return (
        '<!doctype html><html><head><meta charset="utf-8"><style>'
        f"body{{margin:0;width:{width}px;height:{height}px;display:grid;place-items:center;"
        "background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff;"
        "font-family:'PingFang SC','Microsoft YaHei',sans-serif;}"
        f"h1{{font-size:{max(28, int(width * 0.09))}px;font-weight:700;text-align:center;"
        "padding:0 8%;line-height:1.4;text-shadow:0 4px 20px rgba(0,0,0,.35);}}"
        "</style></head><body><h1>" + t + "</h1></body></html>"
    )


def media_of(params: dict[str, Any]) -> list[dict]:
    """任务里的素材列表。旧任务只有 image_paths。"""
    return params.get("media") or [
        {"path": p, "kind": "image"} for p in params.get("image_paths", [])
    ]


def analysis_pack_gaps(media: list[dict], image_workflow: str, video_workflow: str) -> str:
    """看素材写文案时，缺哪一类分析包。都齐则返回空串。"""
    if any(m.get("kind") != "video" for m in media) and not image_workflow:
        return "有图片素材，请选择图片分析工作流"
    if any(m.get("kind") == "video" for m in media) and not video_workflow:
        return "有视频素材，请选择视频分析工作流"
    return ""


def segments_from_reply(data: dict, count: int) -> list[str]:
    """LLM JSON 里的 segments，数量必须和素材一致且每句非空。"""
    segments = data.get("segments")
    if not isinstance(segments, list) or len(segments) != count:
        raise ProviderError("文案分段数量与素材不一致，请重试")
    texts = [str(s).strip() for s in segments]
    if any(not s for s in texts):
        raise ProviderError("文案有空句，请重试")
    return texts


async def _media_briefs(media: list[dict]) -> list[str]:
    """文件名和视频时长，视觉分析失败时的回退说明。"""
    briefs: list[str] = []
    for i, m in enumerate(media):
        info = f"素材{i + 1}（{'视频' if m['kind'] == 'video' else '图片'}，文件 {Path(m['path']).name}）"
        if m["kind"] == "video":
            d = await ffmpeg.probe_duration(resolve(m["path"]))
            info += f"，素材时长 {d:.1f} 秒"
        briefs.append(info)
    return briefs


async def _fill_vision_descriptions(
    db: Session,
    job: Job,
    ctx: JobContext,
    media: list[dict],
    briefs: list[str],
    *,
    image_workflow: str,
    video_workflow: str,
    inputs: dict[str, Any],
    provider_id: int | None,
    strict: bool,
) -> list[str]:
    """用分析工作流替换每条素材说明。strict 时失败直接中断，否则退回文件信息。"""
    if not image_workflow and not video_workflow:
        return briefs
    analysis_provider = pick_provider(db, "image", provider_id)
    from liberastra.providers.analysis.comfyui import ComfyUIAnalysis

    analysis = ComfyUIAnalysis(analysis_provider.base_url)
    wait_timeout = float(get_pref(db, "comfy_wait_timeout_seconds"))
    image_pack = get_pack(image_workflow) if image_workflow else None
    video_pack = get_pack(video_workflow) if video_workflow else None
    described = list(briefs)
    for i, m in enumerate(media):
        if ctx.cancelled():
            return []
        pack = video_pack if m["kind"] == "video" else image_pack
        if pack is None:
            if strict:
                kind = "视频" if m["kind"] == "video" else "图片"
                raise ProviderError(f"素材 {i + 1} 是{kind}，还没有对应的分析工作流")
            continue
        # 出片任务保持原来很短的分析进度；单独写文案时把进度拉满到写口播之前
        progress = (
            0.05 + 0.67 * i / len(media)
            if strict
            else 0.02 + 0.03 * (i + 1) / len(media)
        )
        ctx.report(db, job, progress=progress, step=f"分析素材 {i + 1}/{len(media)}")
        try:
            desc = await analysis.analyze(
                pack=pack,
                inputs={**inputs, m["kind"]: m["path"]},
                wait_timeout=wait_timeout,
            )
        except ProviderError as exc:
            if strict:
                raise ProviderError(f"素材 {i + 1} 分析失败: {exc}") from exc
            logger.warning("素材 {} 分析失败，退回元信息：{}", m["path"], exc)
            continue
        if strict and not desc.strip():
            raise ProviderError(f"素材 {i + 1} 分析没有返回内容")
        kind = "视频" if m["kind"] == "video" else "图片"
        described[i] = f"素材{i + 1}（{kind}），内容：{desc.strip()}"
    return described


async def run_assets_script_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """看素材写文案：视觉描述每一段素材，再写成可编辑的口播。不出片。"""
    params = job.params
    media = media_of(params)
    if not media:
        raise ProviderError("没有素材，无法写文案")
    gap = analysis_pack_gaps(
        media,
        str(params.get("analysis_image_workflow") or ""),
        str(params.get("analysis_video_workflow") or ""),
    )
    if gap:
        raise ProviderError(gap)
    briefs = await _media_briefs(media)
    if ctx.cancelled():
        return []
    described = await _fill_vision_descriptions(
        db,
        job,
        ctx,
        media,
        briefs,
        image_workflow=str(params.get("analysis_image_workflow") or ""),
        video_workflow=str(params.get("analysis_video_workflow") or ""),
        inputs=dict(params.get("analysis_inputs") or {}),
        provider_id=(params.get("providers") or {}).get("analysis"),
        strict=True,
    )
    if ctx.cancelled() or not described:
        return []
    ctx.report(db, job, progress=0.8, step="narration")
    llm_provider, llm_model = pick_llm_with_model(db, None, "")
    llm = build_llm_adapter(llm_provider, db=db)
    hint = str(params.get("hint") or "").strip() or "无"
    duration = int(params.get("duration") or 30)
    data = await _chat_json(
        llm,
        llm_provider,
        "你在看短视频的每个画面描述，为每个画面写一句口语口播。"
        f"目标总时长约 {duration} 秒，按每秒 4 到 5 个字估算每句长度。"
        "只根据给出的画面写，不要编画面里没有的情节。"
        '只输出 JSON：{"segments": ["...", "..."]}，数量必须与画面数一致。',
        f"补充要求：{hint}\n画面：\n" + "\n".join(described),
        llm_model,
    )
    texts = segments_from_reply(data, len(media))
    ctx.report(db, job, progress=1.0, step="文案已生成")
    return [{"type": "text", "content": "\n".join(texts)}]


async def run_assets_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """自定义素材：图片/视频素材 + 文案/主题 → 元信息 → TTS → 可选动画 → 字幕 → 标题卡 → 拼接。"""
    started = time.monotonic()
    params = job.params
    media = media_of(params)
    if not media:
        raise ProviderError("没有素材，无法继续")
    native_audio = str(params.get("audio_mode") or "custom") == "auto" and (
        bool(params.get("animate")) or any(item["kind"] == "video" for item in media)
    )
    show_subtitle = bool(params.get("show_subtitle", True))
    subtitle_size = float(params.get("subtitle_size") or 0)
    subtitle_color = str(params.get("subtitle_color") or "")

    def burn_subtitle(path: Path) -> dict[str, Any]:
        """关闭烧录时不把字幕画进画面；打开时带上字号和颜色。"""
        if not show_subtitle:
            return {"subtitle": None}
        return {
            "subtitle": path,
            "subtitle_size": subtitle_size,
            "subtitle_color": subtitle_color,
        }

    tts_provider = None
    tts = None
    if not native_audio:
        tts_provider = pick_provider(db, "tts", params.get("providers", {}).get("tts"))
        tts = build_tts_adapter(tts_provider, db=db)
    wait_timeout = float(get_pref(db, "comfy_wait_timeout_seconds"))

    asset_desc = await _media_briefs(media)
    asset_desc = await _fill_vision_descriptions(
        db,
        job,
        ctx,
        media,
        asset_desc,
        image_workflow=str(params.get("analysis_image_workflow") or ""),
        video_workflow=str(params.get("analysis_video_workflow") or ""),
        inputs=dict(params.get("analysis_inputs") or {}),
        provider_id=(params.get("providers") or {}).get("analysis"),
        strict=False,
    )
    if ctx.cancelled():
        return []

    # 文案：优先固定文案切分，否则 LLM 按主题+素材元信息逐图写一句
    if params.get("script"):
        texts = split_script(params["script"], params.get("split_mode", "line"))
    else:
        llm_provider, llm_model = pick_llm_with_model(
            db, params.get("providers", {}).get("llm"), params.get("llm_model", "")
        )
        llm = build_llm_adapter(llm_provider, db=db)
        ctx.report(db, job, progress=0.05, step="narration")
        duration = int(params.get("duration", 30))
        data = await _chat_json(
            llm,
            llm_provider,
            "为短视频的每个画面写一句口播文案（口语化）。"
            f"目标总时长约 {duration} 秒，按每秒 4 到 5 字估算每句长度。"
            '只输出 JSON：{"segments": ["...", "..."]}，数量必须与画面数一致。',
            f"主题：{params.get('topic', '未命名')}\n画面素材：\n" + "\n".join(asset_desc),
            llm_model,
        )
        texts = [str(s) for s in data.get("segments", [])]
    if not texts:
        raise ProviderError("文案为空，无法继续")

    from liberastra.pipelines.quick import ASPECT_SIZES

    width, height = ASPECT_SIZES.get(params.get("aspect", "9:16"), ASPECT_SIZES["9:16"])
    voice = params.get("voice", "")
    animate = bool(params.get("animate"))
    video_adapter = None
    video_pack = None
    if animate and any(m["kind"] == "image" for m in media):
        video_provider = pick_provider(db, "video", params.get("providers", {}).get("video"))
        video_adapter = ComfyUIVideo(video_provider.base_url)
        video_pack = get_pack(params["video_workflow"])

    segments_out: list[Path] = []
    total = len(media) + (1 if params.get("title") else 0)
    done = 0

    async def _synth(text: str, i: int) -> Path:
        """逐素材配音：comfyui 走语音工作流包，其余走 Provider 的 synthesize。"""
        if tts_provider is None or tts is None:
            raise ProviderError("当前配音模式需要配音服务")
        if tts_provider.type == "comfyui":
            if not params.get("tts_workflow"):
                raise ProviderError("配音 Provider 是 ComfyUI，但没有选择语音工作流包")
            pack = get_pack(params["tts_workflow"])
            inputs = dict(params.get("tts_inputs", {}))
            if "text" in pack.inputs:
                inputs["text"] = text
            if "voice" in pack.inputs and voice:
                inputs["voice"] = voice
            filename, audio_bytes = await tts.synthesize_pack(
                pack=pack,
                inputs=inputs,
                wait_timeout=wait_timeout,
            )
            ext = filename.rsplit(".", 1)[-1] if "." in filename else "mp3"
        else:
            extra: dict[str, Any] = {}
            if tts_provider.type == "liber_speech" and params.get("language"):
                extra["language"] = str(params["language"])
            if tts_provider.type == "liber_speech" and params.get("ref_audio"):
                extra["ref_audio"] = str(params["ref_audio"])
            audio_bytes = await tts.synthesize(text=text, voice=voice, fmt="mp3", **extra)
            ext = "mp3"
        audio_path = job_path(job, f"frame_{i:02d}.{ext}")
        audio_path.write_bytes(audio_bytes)
        return audio_path

    # 标题卡：2 秒静音分段，放在最前
    if params.get("title"):
        ctx.report(db, job, progress=0.06, step="title")
        silence = job_path(job, "title_silence.mp3")
        await ffmpeg.make_silence(silence, 2.0)
        png = await render_html(
            _title_card_html(params["title"], width * 2, height * 2),
            width=width * 2,
            height=height * 2,
        )
        img_path = job_path(job, "title.png")
        img_path.write_bytes(png)
        seg = job_path(job, "segment_title.mp4")
        await ffmpeg.make_segment(image=img_path, audio=silence, out=seg, width=width, height=height)
        segments_out.append(seg)
        done = 1
        ctx.report(db, job, progress=0.1, step="title")

    for i, m in enumerate(media):
        if ctx.cancelled():
            return []
        text = texts[i % len(texts)]
        segment_path = job_path(job, f"segment_{i:02d}.mp4")
        srt_path = job_path(job, f"frame_{i:02d}.srt")
        keep_model_audio = native_audio and (
            m["kind"] == "video" or (animate and m["kind"] == "image" and video_adapter is not None)
        )
        if keep_model_audio and m["kind"] == "video":
            clip_path = resolve(m["path"])
            duration = await ffmpeg.probe_duration(clip_path)
            srt_path.write_text(_single_cue_srt(text, duration), encoding="utf-8")
            await ffmpeg.make_native_clip_segment(
                clip=clip_path, out=segment_path, width=width, height=height, **burn_subtitle(srt_path),
            )
        elif keep_model_audio and video_adapter is not None and video_pack is not None:
            clips, _texts = await video_adapter.generate(
                pack=video_pack,
                inputs={
                    **params.get("video_inputs", {}),
                    "image": m["path"],
                    "prompt": params.get("animate_prompt")
                    or "subtle natural cinematic motion, slow camera push in. "
                    + (params.get("topic") or ""),
                },
                on_progress=lambda p, step_done=done: ctx.report(
                    db,
                    job,
                    progress=0.1 + 0.8 * (step_done + p) / total,
                    step=f"frame {step_done + 1}/{total} 动画",
                ),
                wait_timeout=wait_timeout,
            )
            clip_path = job_path(job, f"anim_{i:02d}.mp4")
            clip_path.write_bytes(clips[0][1])
            duration = await ffmpeg.probe_duration(clip_path)
            srt_path.write_text(_single_cue_srt(text, duration), encoding="utf-8")
            await ffmpeg.make_native_clip_segment(
                clip=clip_path, out=segment_path, width=width, height=height, **burn_subtitle(srt_path),
            )
        elif native_audio:
            silence = job_path(job, f"silence_{i:02d}.mp3")
            await ffmpeg.make_silence(silence, 3.0)
            srt_path.write_text(_single_cue_srt(text, 3.0), encoding="utf-8")
            await ffmpeg.make_segment(
                image=resolve(m["path"]), audio=silence, out=segment_path,
                width=width, height=height, **burn_subtitle(srt_path),
            )
        else:
            audio_path = await _synth(text, i)
            duration = await ffmpeg.probe_duration(audio_path)
            srt_path.write_text(_single_cue_srt(text, duration), encoding="utf-8")
            if m["kind"] == "video":
                await ffmpeg.make_clip_segment(
                    clip=resolve(m["path"]), audio=audio_path, out=segment_path,
                    width=width, height=height, **burn_subtitle(srt_path),
                )
            elif animate and video_adapter is not None and video_pack is not None:
                clips, _texts = await video_adapter.generate(
                    pack=video_pack,
                    inputs={
                        **params.get("video_inputs", {}),
                        "image": m["path"],
                        "prompt": params.get("animate_prompt")
                        or "subtle natural cinematic motion, slow camera push in. "
                        + (params.get("topic") or ""),
                    },
                    on_progress=lambda p, step_done=done: ctx.report(
                        db,
                        job,
                        progress=0.1 + 0.8 * (step_done + p) / total,
                        step=f"frame {step_done + 1}/{total} 动画",
                    ),
                    wait_timeout=wait_timeout,
                )
                clip_path = job_path(job, f"anim_{i:02d}.mp4")
                clip_path.write_bytes(clips[0][1])
                await ffmpeg.make_clip_segment(
                    clip=clip_path, audio=audio_path, out=segment_path,
                    width=width, height=height, **burn_subtitle(srt_path),
                )
            else:
                await ffmpeg.make_segment(
                    image=resolve(m["path"]), audio=audio_path, out=segment_path,
                    width=width, height=height, **burn_subtitle(srt_path),
                )
        segments_out.append(segment_path)
        done += 1
        ctx.report(db, job, progress=0.1 + 0.8 * done / total, step=f"frame {done}/{total}")

    ctx.report(db, job, progress=0.92, step="concat")
    concat_path = job_path(job, "concat.mp4")
    await ffmpeg.concat_segments(segments_out, concat_path, list_file=job_path(job, "concat.txt"))
    final_path = concat_path
    if params.get("bgm_path"):
        ctx.report(db, job, progress=0.96, step="bgm")
        final_path = job_path(job, "final.mp4")
        await ffmpeg.add_bgm(
            video=concat_path, bgm=resolve(params["bgm_path"]), out=final_path,
            bgm_volume=float(params.get("bgm_volume", 0.2)),
        )
    meta = {
        "type": "assets",
        "title": params.get("title") or params.get("topic"),
        "aspect": params.get("aspect", "9:16"),
        "voice": voice,
        "provider": tts_provider.name,
        "workflow": params.get("video_workflow") if animate else None,
        "bgm": Path(params["bgm_path"]).name if params.get("bgm_path") else None,
        "frames": total,
        "duration_s": round(time.monotonic() - started, 1),
    }
    asset = create_asset(
        db, kind="video", rel_path=f"outputs/{job.id}/{final_path.name}", job_id=job.id,
        owner_id=job.owner_id, meta={k: v for k, v in meta.items() if v not in (None, "")},
    )
    ctx.report(db, job, progress=1.0)
    return [{"type": "asset", "asset_id": asset.id, "kind": "video", "filename": final_path.name}]


def _input_keys(pack_name: str, input_type: str) -> list[str]:
    pack = get_pack(pack_name)
    return [k for k, s in pack.inputs.items() if s.get("type") == input_type]
