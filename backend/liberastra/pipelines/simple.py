"""简单视频流水线：图生视频、数字人口播、动作迁移、自定义素材。

前三个交给具备对应能力的 ComfyUI 工作流包；自定义素材在平台侧合成。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext
from liberastra.media import ffmpeg
from liberastra.media.htmlframe import render_html
from liberastra.models import Job
from loguru import logger
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


async def run_i2v_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """图生视频：图片 + 提示词 → i2v 工作流。"""
    params = job.params
    inputs = {"prompt": params.get("prompt", ""), **params.get("inputs", {})}
    image_keys = _input_keys(params["workflow"], "image")
    if image_keys:
        inputs[image_keys[0]] = params["image_path"]
    return await _run_video_pack(db, job, ctx, inputs)


async def run_motion_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """动作迁移：参考视频（≤30s）+ 目标图片 + 提示词 → motion 工作流。"""
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
    """数字人口播：人物图 + 文案 → TTS → avatar 工作流。"""
    params = job.params
    tts_provider = pick_provider(db, "tts", params.get("tts_provider_id"))
    tts = build_tts_adapter(tts_provider)
    ctx.report(db, job, progress=0.05, step="tts")
    ext = "mp3"
    if tts_provider.type == "comfyui":
        # comfy 语音工作流：文本按 manifest 注入
        if not params.get("tts_workflow"):
            raise ProviderError("配音 Provider 是 ComfyUI，但没有选择语音工作流包")
        pack = get_pack(params["tts_workflow"])
        inputs = dict(params.get("tts_inputs", {}))
        if "text" in pack.inputs:
            inputs["text"] = params["text"]
        if "voice" in pack.inputs and params.get("voice"):
            inputs["voice"] = params["voice"]
        filename, audio = await tts.synthesize_pack(
            pack=pack,
            inputs=inputs,
            wait_timeout=float(get_pref(db, "comfy_wait_timeout_seconds")),
        )
        if "." in filename:
            ext = filename.rsplit(".", 1)[-1]
    else:
        audio = await tts.synthesize(text=params["text"], voice=params["voice"], fmt="mp3")
    audio_path = job_path(job, f"voiceover.{ext}")
    audio_path.write_bytes(audio)
    if ctx.cancelled():
        return []

    audio_rel = f"outputs/{job.id}/voiceover.{ext}"
    inputs = {"prompt": params.get("prompt", params["text"]), **params.get("inputs", {})}
    image_keys = _input_keys(params["workflow"], "image")
    audio_keys = _input_keys(params["workflow"], "audio")
    if image_keys:
        inputs[image_keys[0]] = params["image_path"]
    if audio_keys:
        inputs[audio_keys[0]] = audio_rel
    return await _run_video_pack(db, job, ctx, inputs)


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


async def run_assets_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    """自定义素材：图片/视频素材 + 文案/主题 → 素材元信息 → TTS →（可选 i2v 动画）→ 字幕分段 → 标题卡 → 拼接+BGM。"""
    started = time.monotonic()
    params = job.params
    # 兼容旧任务（只有 image_paths）
    media: list[dict] = params.get("media") or [
        {"path": p, "kind": "image"} for p in params.get("image_paths", [])
    ]
    if not media:
        raise ProviderError("没有素材，无法继续")
    tts_provider = pick_provider(db, "tts", params.get("providers", {}).get("tts"))
    tts = build_tts_adapter(tts_provider)
    wait_timeout = float(get_pref(db, "comfy_wait_timeout_seconds"))

    # 素材元信息（喂给 LLM：类型/文件名/视频时长），相当于轻量素材分析
    asset_desc: list[str] = []
    for i, m in enumerate(media):
        info = f"素材{i + 1}（{'视频' if m['kind'] == 'video' else '图片'}，文件 {Path(m['path']).name}）"
        if m["kind"] == "video":
            d = await ffmpeg.probe_duration(resolve(m["path"]))
            info += f"，素材时长 {d:.1f} 秒"
        asset_desc.append(info)

    # 素材分析（可选）：Comfy 分析工作流逐素材产出真实内容描述，替换元信息
    if params.get("analysis_image_workflow") or params.get("analysis_video_workflow"):
        analysis_provider = pick_provider(db, "image", params.get("providers", {}).get("analysis"))
        from liberastra.providers.analysis.comfyui import ComfyUIAnalysis

        analysis = ComfyUIAnalysis(analysis_provider.base_url)
        image_pack = get_pack(params["analysis_image_workflow"]) if params.get("analysis_image_workflow") else None
        video_pack = get_pack(params["analysis_video_workflow"]) if params.get("analysis_video_workflow") else None
        for i, m in enumerate(media):
            if ctx.cancelled():
                return []
            pack = image_pack if m["kind"] == "image" else video_pack
            if pack is None:
                continue
            ctx.report(
                db, job, progress=0.02 + 0.03 * (i + 1) / len(media), step=f"analyze {i + 1}/{len(media)}"
            )
            try:
                desc = await analysis.analyze(
                    pack=pack,
                    inputs={**params.get("analysis_inputs", {}), m["kind"]: m["path"]},
                    wait_timeout=wait_timeout,
                )
                asset_desc[i] = (
                    f"素材{i + 1}（{'视频' if m['kind'] == 'video' else '图片'}），内容：{desc.strip()}"
                )
            except ProviderError as exc:
                logger.warning("素材 {} 分析失败，退回元信息：{}", m["path"], exc)

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
            audio_bytes = await tts.synthesize(text=text, voice=voice, fmt="mp3")
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
        audio_path = await _synth(text, i)
        segment_path = job_path(job, f"segment_{i:02d}.mp4")
        srt_path = job_path(job, f"frame_{i:02d}.srt")
        duration = await ffmpeg.probe_duration(audio_path)
        srt_path.write_text(_single_cue_srt(text, duration), encoding="utf-8")
        if m["kind"] == "video":
            # 视频素材：循环/截断对齐配音时长
            await ffmpeg.make_clip_segment(
                clip=resolve(m["path"]), audio=audio_path, out=segment_path,
                width=width, height=height, subtitle=srt_path,
            )
        elif animate and video_adapter is not None and video_pack is not None:
            # 素材动画：图片经 i2v 工作流动画化后再合成
            clips, _texts = await video_adapter.generate(
                pack=video_pack,
                inputs={
                    **params.get("video_inputs", {}),
                    "image": m["path"],  # 相对路径，run_workflow_pack 负责上传
                    "prompt": (
                        params.get("animate_prompt")
                        or f"subtle natural cinematic motion, slow camera push in. {params.get('topic') or ''}"
                    ),
                },
                on_progress=lambda p: ctx.report(
                    db, job, progress=0.1 + 0.8 * (done + p) / total, step=f"frame {done + 1}/{total} 动画"
                ),
                wait_timeout=wait_timeout,
            )
            clip_path = job_path(job, f"anim_{i:02d}.mp4")
            clip_path.write_bytes(clips[0][1])
            await ffmpeg.make_clip_segment(
                clip=clip_path, audio=audio_path, out=segment_path,
                width=width, height=height, subtitle=srt_path,
            )
        else:
            await ffmpeg.make_segment(
                image=resolve(m["path"]), audio=audio_path, out=segment_path,
                width=width, height=height, subtitle=srt_path,
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
