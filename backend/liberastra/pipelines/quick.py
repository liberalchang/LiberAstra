"""快速创作流水线：主题/文案 → LLM 脚本 → LLM 分镜 → 逐帧 TTS+图像 → 字幕分段 → 拼接+BGM。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext
from liberastra.media import ffmpeg
from liberastra.models import Job
from liberastra.providers.base import ProviderError
from liberastra.services.image import produce_images
from liberastra.services.providers import (
    build_llm_adapter,
    build_tts_adapter,
    pick_provider,
)
from liberastra.storage import create_asset, resolve, save_bytes

ASPECT_SIZES = {"9:16": (720, 1280), "1:1": (960, 960), "16:9": (1280, 720)}

SCRIPT_PROMPT = (
    "你是短视频编导。根据用户主题写 {n} 个分镜的口播文案，每句 20-40 字、口语化、有钩子。"
    '只输出 JSON：{{"title": "视频标题", "segments": ["第一句", "第二句"]}}'
)

STORYBOARD_PROMPT = (
    "根据口播分镜，为每句写对应的文生图画面提示词（主体、场景、构图、光线，风格统一）。"
    '输入：{{"title":..,"segments":[..]}}。只输出 JSON：'
    '{{"frames": [{{"text": "口播句", "visual": "画面提示词"}}]}}'
)

_SENTENCE_SPLIT = re.compile(r"[^。！？!?；;]+[。！？!?；;]?")


def split_script(script: str, mode: str) -> list[str]:
    if mode == "line":
        return [line.strip() for line in script.splitlines() if line.strip()]
    if mode == "sentence":
        return [m.group().strip() for m in _SENTENCE_SPLIT.finditer(script) if m.group().strip()]
    return [p.strip() for p in re.split(r"\n\s*\n", script) if p.strip()]


def _extract_json(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ProviderError(f"LLM 未返回 JSON: {text[:200]}")
    try:
        return json.loads(cleaned[start : end + 1])  # type: ignore[no-any-return]
    except json.JSONDecodeError as exc:
        raise ProviderError(f"LLM JSON 解析失败: {exc}") from exc


def job_path(job: Job, name: str) -> Path:
    path = resolve(f"outputs/{job.id}/{name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _single_cue_srt(text: str, duration: float) -> str:
    from liberastra.media.subtitles import to_srt
    from liberastra.providers.base import ASRResult, ASRSegment

    return to_srt(ASRResult(text=text, segments=[ASRSegment(0.0, max(duration, 0.5), text)]))


async def run_quick_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    params = job.params
    provider_ids = params.get("providers", {})
    llm_provider = pick_provider(db, "llm", provider_ids.get("llm"))
    tts_provider = pick_provider(db, "tts", provider_ids.get("tts"))
    image_provider = pick_provider(db, "image", provider_ids.get("image"))
    llm = build_llm_adapter(llm_provider)
    tts = build_tts_adapter(tts_provider)

    # ---- 1. 脚本 + 分镜 ----
    storyboard = params.get("storyboard")
    if storyboard is None:
        count = int(params.get("storyboard_count", 4))
        if params.get("script"):
            title = "自定义文案"
            segments = split_script(params["script"], params.get("split_mode", "paragraph"))
        else:
            ctx.report(db, job, progress=0.05, step="script")
            data = await _chat_json(llm, llm_provider, SCRIPT_PROMPT.format(n=count), params["topic"])
            title = str(data.get("title", "未命名"))
            segments = [str(s) for s in data.get("segments", [])]
        if not segments:
            raise ProviderError("脚本为空，无法继续")

        ctx.report(db, job, progress=0.1, step="storyboard")
        data = await _chat_json(
            llm,
            llm_provider,
            STORYBOARD_PROMPT,
            json.dumps({"title": title, "segments": segments}, ensure_ascii=False),
        )
        frames = data.get("frames", [])
        if not frames:  # LLM 没给分镜则退化为纯文案
            frames = [{"text": s, "visual": s} for s in segments]
        storyboard = {"title": title, "frames": frames}

    storyboard_rel = f"outputs/{job.id}/storyboard.json"
    save_bytes(
        json.dumps(storyboard, ensure_ascii=False, indent=2).encode("utf-8"), storyboard_rel
    )
    storyboard_asset = create_asset(
        db, kind="text", rel_path=storyboard_rel, job_id=job.id, owner_id=job.owner_id,
        meta={"type": "storyboard"},
    )
    outputs: list[dict[str, Any]] = [
        {"type": "asset", "asset_id": storyboard_asset.id, "kind": "storyboard",
         "filename": "storyboard.json"}
    ]
    ctx.report(db, job, progress=0.15, step="storyboard")
    if params.get("storyboard_only"):
        return outputs

    # ---- 2. 逐帧合成 ----
    frames = storyboard["frames"]
    width, height = ASPECT_SIZES.get(params.get("aspect", "9:16"), ASPECT_SIZES["9:16"])
    style_prefix = params.get("style_prefix", "")
    voice = params["voice"]
    segments_out: list[Path] = []
    total = len(frames)

    for i, frame in enumerate(frames):
        if ctx.cancelled():
            return []
        base = 0.15 + 0.75 * i / total

        audio_bytes = await tts.synthesize(
            text=frame["text"], voice=voice, fmt="mp3", **params.get("tts_options", {})
        )
        audio_path = job_path(job, f"frame_{i:02d}.mp3")
        audio_path.write_bytes(audio_bytes)

        visual = f"{style_prefix}{frame['visual']}"
        images = await produce_images(
            image_provider,
            workflow=params.get("image_workflow"),
            inputs={
                **params.get("image_inputs", {}),
                "prompt": visual,
                "width": width,
                "height": height,
            },
            prompt=visual,
            size=f"{width}x{height}",
        )
        ext = images[0][0].rsplit(".", 1)[-1] if "." in images[0][0] else "png"
        image_path = job_path(job, f"frame_{i:02d}.{ext}")
        image_path.write_bytes(images[0][1])

        duration = await ffmpeg.probe_duration(audio_path)
        srt_path = job_path(job, f"frame_{i:02d}.srt")
        srt_path.write_text(_single_cue_srt(frame["text"], duration), encoding="utf-8")

        segment_path = job_path(job, f"segment_{i:02d}.mp4")
        await ffmpeg.make_segment(
            image=image_path, audio=audio_path, out=segment_path,
            width=width, height=height, subtitle=srt_path,
        )
        segments_out.append(segment_path)
        ctx.report(db, job, progress=base + 0.75 * (i + 1) / total, step=f"frame {i + 1}/{total}")

    # ---- 3. 拼接 + BGM ----
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

    video_asset = create_asset(
        db, kind="video", rel_path=f"outputs/{job.id}/{final_path.name}", job_id=job.id,
        owner_id=job.owner_id,
        meta={"title": storyboard.get("title", ""), "provider": image_provider.name},
    )
    outputs.append(
        {"type": "asset", "asset_id": video_asset.id, "kind": "video", "filename": final_path.name}
    )
    ctx.report(db, job, progress=1.0)
    logger.info("快速创作任务 {} 完成：{} 帧", job.id, total)
    return outputs


async def _chat_json(llm: Any, provider: Any, system: str, user: str) -> dict:  # noqa: ANN401
    model = (provider.extra or {}).get("model", "") or "default"
    text = await llm.chat(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return _extract_json(text)
