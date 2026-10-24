"""快速创作流水线：主题/文案 → LLM 脚本 → 分镜 → 逐帧配音+画面 → 字幕分段 → 拼接+BGM。

分镜画面由模板类型决定：
- static_* 静态样式：模板 HTML + 文案直接渲染成帧图（不跑 AI 出图）
- image_*  生成插图：逐镜 AI 出图注入模板 {{image}} 后再渲染（模板无 {{image}} 则等同静态）
- video_*  生成视频：逐镜跑视频工作流得到片段，循环对齐配音时长
"""

from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext
from liberastra.media import ffmpeg
from liberastra.media.htmlframe import render_html
from liberastra.models import Job
from liberastra.providers.base import ProviderError
from liberastra.services.image import produce_images
from liberastra.services.preferences import get_pref
from liberastra.services.providers import (
    build_llm_adapter,
    build_tts_adapter,
    pick_llm_with_model,
    pick_provider,
)
from liberastra.services.templates import TemplateInfo, get_template, list_templates
from liberastra.services.templates import render as render_template
from liberastra.services.workflows import get_pack
from liberastra.storage import create_asset, resolve, save_bytes

ASPECT_SIZES = {"9:16": (720, 1280), "1:1": (960, 960), "16:9": (1280, 720)}

SCRIPT_PROMPT = (
    "你是短视频编导。根据用户主题写 {n} 个分镜的口播文案，每句 20-40 字、口语化、有钩子。"
    '只输出 JSON：{{"title": "视频标题", "segments": ["第一句", "第二句"]}}'
)

STORYBOARD_PROMPT = (
    "根据口播分镜，为每句写对应的画面提示词（主体、场景、构图、光线，风格统一）。"
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


def resolve_quick_template(name: str, aspect: str) -> TemplateInfo:
    """指定了名字就取它；否则优先该画幅的第一个静态模板，再退到任意模板。"""
    if name:
        return get_template(name, aspect)
    for type_ in ("static", "image", "video"):
        items = list_templates(aspect, type_)
        if items:
            return items[0]
    raise ProviderError(f"没有 {aspect} 画幅的分镜模板，请到「模板管理」上传")


def _image_data_uri(filename: str, content: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(ext, "image/png")
    return f"data:{mime};base64,{base64.b64encode(content).decode('ascii')}"


def _quick_needs_llm(params: dict[str, Any], tpl: TemplateInfo) -> tuple[bool, bool]:
    """返回 (需要写口播, 需要写画面提示词)。已有 storyboard 时两者皆否。"""
    if params.get("storyboard") is not None:
        return False, False
    need_script = not params.get("script")
    optimize = bool(params.get("optimize_visuals", True))
    need_visuals = tpl.type in ("image", "video") and optimize
    return need_script, need_visuals


async def run_quick_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    started = time.monotonic()
    params = job.params
    provider_ids = params.get("providers", {})
    aspect = params.get("aspect", "9:16")
    tpl = resolve_quick_template(params.get("template", ""), aspect)
    use_native_audio = str(params.get("audio_mode") or "custom") == "auto" and tpl.type == "video"
    tts_provider = None
    tts = None
    if not use_native_audio:
        tts_provider = pick_provider(db, "tts", provider_ids.get("tts"))
        tts = build_tts_adapter(tts_provider, db=db)
    need_script_llm, need_visual_llm = _quick_needs_llm(params, tpl)
    llm_provider = None
    llm = None
    llm_model = params.get("llm_model", "")
    if need_script_llm or need_visual_llm:
        llm_provider, llm_model = pick_llm_with_model(
            db, provider_ids.get("llm"), params.get("llm_model", "")
        )
        llm = build_llm_adapter(llm_provider, db=db)
    wait_timeout = float(get_pref(db, "comfy_wait_timeout_seconds"))
    # 文字显隐与字号（模板标题/文案 + 视频烧录字幕）
    show_title = bool(params.get("show_title", True))
    show_text = bool(params.get("show_text", True))
    show_subtitle = bool(params.get("show_subtitle", True))
    title_scale = float(params.get("title_scale", 1.0))
    text_scale = float(params.get("text_scale", 1.0))
    subtitle_size = float(params.get("subtitle_size", 0))
    subtitle_color = str(params.get("subtitle_color", ""))

    # ---- 1. 脚本 + 分镜 ----
    storyboard = params.get("storyboard")
    if storyboard is None:
        count = int(params.get("storyboard_count", 4))
        if params.get("script"):
            # 固定文案：标题用用户输入的主题，文案原样切分，都不经过 AI
            title = params.get("title") or "自定义文案"
            segments = split_script(params["script"], params.get("split_mode", "paragraph"))
        else:
            ctx.report(db, job, progress=0.05, step="script")
            assert llm is not None and llm_provider is not None
            data = await _chat_json(
                llm, llm_provider, SCRIPT_PROMPT.format(n=count), params["topic"], llm_model
            )
            # AI 创作：主题即视频标题（用户给定优先），AI 只生成口播内容
            title = params.get("title") or params.get("topic") or str(data.get("title", "未命名"))
            segments = [str(s) for s in data.get("segments", [])]
        if not segments:
            raise ProviderError("脚本为空，无法继续")

        if need_visual_llm:
            # LLM 把口播改写成画面提示词（与 Comfy Guide 增强是另一层）
            ctx.report(db, job, progress=0.1, step="storyboard")
            assert llm is not None and llm_provider is not None
            data = await _chat_json(
                llm,
                llm_provider,
                STORYBOARD_PROMPT,
                json.dumps({"title": title, "segments": segments}, ensure_ascii=False),
                llm_model,
            )
            frames = data.get("frames", [])
        else:
            # 静态模板 / 关闭画面优化：口播原文即 visual
            frames = []
        if not frames:
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
    width, height = ASPECT_SIZES.get(aspect, ASPECT_SIZES["9:16"])
    style_prefix = params.get("style_prefix", "")
    voice = params.get("voice", "")
    title = storyboard.get("title", "")
    segments_out: list[Path] = []
    total = len(frames)

    image_provider = (
        pick_provider(db, "image", provider_ids.get("image"))
        if tpl.type == "image" and tpl.needs_image
        else None
    )
    video_provider = None
    video_adapter = None
    if tpl.type == "video":
        video_provider = pick_provider(db, "video", provider_ids.get("video"))
        from liberastra.providers.video.comfyui import ComfyUIVideo

        video_adapter = ComfyUIVideo(video_provider.base_url)

    async def _synth_frame_audio(i: int, text: str) -> Path:
        """逐帧配音：comfyui 走语音工作流包，其余走 Provider 的 synthesize。"""
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
                on_progress=lambda p: ctx.report(
                    db, job, progress=0.15 + 0.75 * (i + p) / total, step=f"frame {i + 1}/{total} 配音"
                ),
                wait_timeout=wait_timeout,
            )
            ext = filename.rsplit(".", 1)[-1] if "." in filename else "mp3"
        elif tts_provider.type == "edge_tts":
            from liberastra.providers.tts.edge_tts import speed_to_rate

            inputs = dict(params.get("tts_inputs", {}))
            chosen = str(inputs.get("voice") or voice or "zh-CN-XiaoxiaoNeural")
            opts = dict(params.get("tts_options", {}))
            if "speed" in inputs and "rate" not in opts:
                opts["rate"] = speed_to_rate(inputs.get("speed"))
            audio_bytes = await tts.synthesize(text=text, voice=chosen, fmt="mp3", **opts)
            ext = "mp3"
        else:
            extra = dict(params.get("tts_options") or {})
            if tts_provider.type == "liber_speech" and params.get("language"):
                extra["language"] = str(params["language"])
            if tts_provider.type == "liber_speech" and params.get("ref_audio"):
                extra["ref_audio"] = str(params["ref_audio"])
            audio_bytes = await tts.synthesize(text=text, voice=voice, fmt="mp3", **extra)
            ext = "mp3"
        audio_path = job_path(job, f"frame_{i:02d}.{ext}")
        audio_path.write_bytes(audio_bytes)
        return audio_path

    for i, frame in enumerate(frames):
        if ctx.cancelled():
            return []
        base = 0.15 + 0.75 * i / total

        visual = f"{style_prefix}{frame.get('visual') or frame['text']}"

        segment_path = job_path(job, f"segment_{i:02d}.mp4")
        srt_path = job_path(job, f"frame_{i:02d}.srt")
        burn_subtitle = srt_path if show_subtitle else None

        if use_native_audio:
            # 保留文生视频自己生成的音轨，不再换成配音。
            assert video_adapter is not None
            if not params.get("video_workflow"):
                raise ProviderError("视频模板需要选择视频工作流包")
            pack = get_pack(params["video_workflow"])
            clips, _texts = await video_adapter.generate(
                pack=pack,
                inputs={
                    **params.get("video_inputs", {}),
                    "prompt": visual,
                    "width": tpl.media_width,
                    "height": tpl.media_height,
                },
                on_progress=lambda p, frame_i=i: ctx.report(
                    db,
                    job,
                    progress=0.15 + 0.75 * (frame_i + p) / total,
                    step=f"frame {frame_i + 1}/{total} 视频",
                ),
                wait_timeout=wait_timeout,
            )
            clip_path = job_path(job, f"frame_{i:02d}.mp4")
            clip_path.write_bytes(clips[0][1])
            duration = await ffmpeg.probe_duration(clip_path)
            srt_path.write_text(_single_cue_srt(frame["text"], duration), encoding="utf-8")
            await ffmpeg.make_native_clip_segment(
                clip=clip_path, out=segment_path,
                width=width, height=height, subtitle=burn_subtitle,
                subtitle_size=subtitle_size, subtitle_color=subtitle_color,
            )
        elif tpl.type == "video":
            audio_path = await _synth_frame_audio(i, frame["text"])
            duration = await ffmpeg.probe_duration(audio_path)
            srt_path.write_text(_single_cue_srt(frame["text"], duration), encoding="utf-8")
            assert video_adapter is not None
            if not params.get("video_workflow"):
                raise ProviderError("视频模板需要选择视频工作流包")
            pack = get_pack(params["video_workflow"])
            clips, _texts = await video_adapter.generate(
                pack=pack,
                inputs={
                    **params.get("video_inputs", {}),
                    "prompt": visual,
                    "width": tpl.media_width,
                    "height": tpl.media_height,
                },
                on_progress=lambda p, frame_i=i: ctx.report(
                    db,
                    job,
                    progress=0.15 + 0.75 * (frame_i + p) / total,
                    step=f"frame {frame_i + 1}/{total} 视频",
                ),
                wait_timeout=wait_timeout,
            )
            clip_path = job_path(job, f"frame_{i:02d}.mp4")
            clip_path.write_bytes(clips[0][1])
            await ffmpeg.make_clip_segment(
                clip=clip_path, audio=audio_path, out=segment_path,
                width=width, height=height, subtitle=burn_subtitle,
                subtitle_size=subtitle_size, subtitle_color=subtitle_color,
            )
        else:
            audio_path = await _synth_frame_audio(i, frame["text"])
            duration = await ffmpeg.probe_duration(audio_path)
            srt_path.write_text(_single_cue_srt(frame["text"], duration), encoding="utf-8")
            values: dict[str, Any] = {
                "text": frame["text"],
                "title": title,
                "index": i + 1,
                "total": total,
            }
            if tpl.needs_image:
                assert image_provider is not None
                images = await produce_images(
                    image_provider,
                    workflow=params.get("image_workflow"),
                    inputs={
                        **params.get("image_inputs", {}),
                        "prompt": visual,
                        "width": tpl.media_width,
                        "height": tpl.media_height,
                    },
                    prompt=visual,
                    size=f"{tpl.media_width}x{tpl.media_height}",
                    wait_timeout=wait_timeout,
                )
                values["image"] = _image_data_uri(images[0][0], images[0][1])
            html = render_template(tpl, values)
            frame_png = await render_html(
                html,
                width=tpl.width,
                height=tpl.height,
                adjust={
                    "title": title,
                    "text": frame["text"],
                    "hideTitle": not show_title,
                    "hideText": not show_text,
                    "titleScale": title_scale,
                    "textScale": text_scale,
                },
            )
            image_path = job_path(job, f"frame_{i:02d}.png")
            image_path.write_bytes(frame_png)
            await ffmpeg.make_segment(
                image=image_path, audio=audio_path, out=segment_path,
                width=width, height=height, subtitle=burn_subtitle,
                subtitle_size=subtitle_size, subtitle_color=subtitle_color,
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
        meta={
            "title": title,
            "provider": (image_provider or video_provider or tts_provider).name
            if (image_provider or video_provider or tts_provider)
            else "",
            "aspect": aspect,
            "template": f"{tpl.name}（{tpl.type_label}）",
            # 本次实际使用的工作流与模型，供作品查看页展示
            "workflow": params.get("video_workflow") or params.get("image_workflow"),
            "tts_workflow": params.get("tts_workflow"),
            "llm_model": llm_model
            if llm_provider
            else (params.get("llm_model") or ""),
            "llm_provider": llm_provider.name if llm_provider else "",
            "voice": voice,
            "bgm": Path(params["bgm_path"]).name if params.get("bgm_path") else None,
            "frames": total,
            "duration_s": round(time.monotonic() - started, 1),
        },
    )
    outputs.append(
        {"type": "asset", "asset_id": video_asset.id, "kind": "video", "filename": final_path.name}
    )
    ctx.report(db, job, progress=1.0)
    logger.info("快速创作任务 {} 完成：{} 帧（模板 {}）", job.id, total, tpl.name)
    return outputs


async def _chat_json(llm: Any, provider: Any, system: str, user: str, model: str = "") -> dict:  # noqa: ANN401
    chosen = model or (provider.extra or {}).get("model", "") or "default"
    text = await llm.chat(
        model=chosen,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return _extract_json(text)
