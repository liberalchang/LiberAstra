"""简单视频流水线：图生视频、数字人口播、动作迁移、自定义素材。

前三个交给具备对应能力的 ComfyUI 工作流包；自定义素材在平台侧合成。
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext
from liberastra.media import ffmpeg
from liberastra.models import Job
from liberastra.pipelines.quick import (
    _chat_json,
    _single_cue_srt,
    job_path,
    split_script,
)
from liberastra.providers.video.comfyui import ComfyUIVideo
from liberastra.services.providers import (
    build_llm_adapter,
    build_tts_adapter,
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
    videos = await adapter.generate(
        pack=pack,
        inputs=inputs,
        on_progress=lambda p: ctx.report(db, job, progress=0.1 + 0.85 * p),
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
        asset = create_asset(
            db, kind="video", rel_path=rel_path, job_id=job.id, owner_id=job.owner_id,
            meta={**base_meta, "source_name": filename},
        )
        outputs.append(
            {"type": "asset", "asset_id": asset.id, "kind": "video", "filename": f"video_{i}.{ext}"}
        )
    ctx.report(db, job, progress=1.0)
    return outputs


async def run_i2v_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """图生视频：图片 + 提示词 → first_frame_i2v 工作流。"""
    params = job.params
    inputs = {"prompt": params.get("prompt", ""), **params.get("inputs", {})}
    image_keys = _input_keys(params["workflow"], "image")
    if image_keys:
        inputs[image_keys[0]] = params["image_path"]
    return await _run_video_pack(db, job, ctx, inputs)


async def run_motion_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """动作迁移：参考视频（≤30s）+ 目标图片 + 提示词 → action_transfer 工作流。"""
    params = job.params
    inputs = {"prompt": params.get("prompt", ""), **params.get("inputs", {})}
    video_keys = _input_keys(params["workflow"], "video")
    image_keys = _input_keys(params["workflow"], "image")
    if video_keys:
        inputs[video_keys[0]] = params["video_path"]
    if image_keys:
        inputs[image_keys[0]] = params["image_path"]
    return await _run_video_pack(db, job, ctx, inputs)


async def run_avatar_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """数字人口播：人物图 + 文案 → TTS → digital_human 工作流。"""
    params = job.params
    tts_provider = pick_provider(db, "tts", params.get("tts_provider_id"))
    tts = build_tts_adapter(tts_provider)
    ctx.report(db, job, progress=0.05, step="tts")
    audio = await tts.synthesize(text=params["text"], voice=params["voice"], fmt="mp3")
    audio_path = job_path(job, "voiceover.mp3")
    audio_path.write_bytes(audio)
    if ctx.cancelled():
        return []

    audio_rel = f"outputs/{job.id}/voiceover.mp3"
    inputs = {"prompt": params.get("prompt", params["text"]), **params.get("inputs", {})}
    image_keys = _input_keys(params["workflow"], "image")
    audio_keys = _input_keys(params["workflow"], "audio")
    if image_keys:
        inputs[image_keys[0]] = params["image_path"]
    if audio_keys:
        inputs[audio_keys[0]] = audio_rel
    return await _run_video_pack(db, job, ctx, inputs)


async def run_assets_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """自定义素材：上传图片 + 文案/主题 → TTS + 字幕分段 → 拼接（不生成图像）。"""
    started = time.monotonic()
    params = job.params
    image_paths: list[str] = params["image_paths"]
    tts_provider = pick_provider(db, "tts", params.get("providers", {}).get("tts"))
    tts = build_tts_adapter(tts_provider)

    # 文案：优先固定文案切分，否则 LLM 按主题逐图写一句
    if params.get("script"):
        texts = split_script(params["script"], params.get("split_mode", "line"))
    else:
        llm_provider = pick_provider(db, "llm", params.get("providers", {}).get("llm"))
        llm = build_llm_adapter(llm_provider)
        ctx.report(db, job, progress=0.05, step="narration")
        data = await _chat_json(
            llm, llm_provider,
            "为短视频的每个画面写一句口播文案（20-40 字、口语化）。"
            '只输出 JSON：{"segments": ["...", "..."]}，数量必须与画面数一致。',
            f"主题：{params.get('topic', '未命名')}，共 {len(image_paths)} 个画面",
        )
        texts = [str(s) for s in data.get("segments", [])]
    if not texts:
        from liberastra.providers.base import ProviderError

        raise ProviderError("文案为空，无法继续")

    from liberastra.pipelines.quick import ASPECT_SIZES

    width, height = ASPECT_SIZES.get(params.get("aspect", "9:16"), ASPECT_SIZES["9:16"])
    voice = params["voice"]
    segments_out = []
    total = len(image_paths)
    for i, rel in enumerate(image_paths):
        if ctx.cancelled():
            return []
        text = texts[i % len(texts)]
        audio = await tts.synthesize(text=text, voice=voice, fmt="mp3")
        audio_path = job_path(job, f"frame_{i:02d}.mp3")
        audio_path.write_bytes(audio)
        duration = await ffmpeg.probe_duration(audio_path)
        srt_path = job_path(job, f"frame_{i:02d}.srt")
        srt_path.write_text(_single_cue_srt(text, duration), encoding="utf-8")
        segment_path = job_path(job, f"segment_{i:02d}.mp4")
        await ffmpeg.make_segment(
            image=resolve(rel), audio=audio_path, out=segment_path,
            width=width, height=height, subtitle=srt_path,
        )
        segments_out.append(segment_path)
        ctx.report(db, job, progress=0.1 + 0.8 * (i + 1) / total, step=f"frame {i + 1}/{total}")

    concat_path = job_path(job, "final.mp4")
    await ffmpeg.concat_segments(segments_out, concat_path, list_file=job_path(job, "concat.txt"))
    meta = {
        "type": "assets",
        "title": params.get("topic"),
        "aspect": params.get("aspect", "9:16"),
        "voice": voice,
        "frames": total,
        "duration_s": round(time.monotonic() - started, 1),
    }
    asset = create_asset(
        db, kind="video", rel_path=f"outputs/{job.id}/final.mp4", job_id=job.id,
        owner_id=job.owner_id, meta={k: v for k, v in meta.items() if v not in (None, "")},
    )
    ctx.report(db, job, progress=1.0)
    return [{"type": "asset", "asset_id": asset.id, "kind": "video", "filename": "final.mp4"}]


def _input_keys(pack_name: str, input_type: str) -> list[str]:
    pack = get_pack(pack_name)
    return [k for k, s in pack.inputs.items() if s.get("type") == input_type]
