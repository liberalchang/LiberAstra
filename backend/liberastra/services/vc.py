"""换音任务：vc.convert —— 分段 VC、字幕、可选背景音分离和视频合成。"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from liberastra.jobs.manager import JobContext, JobManager
from liberastra.media import ffmpeg
from liberastra.media.subtitles import parse_srt, to_srt, to_vtt
from liberastra.models import Job, Voice
from liberastra.providers.base import ASRResult, ProviderError
from liberastra.services.preferences import get_str_pref
from liberastra.services.providers import build_vc_adapter, pick_provider
from liberastra.storage import create_asset, resolve, save_bytes

MAX_MEDIA_SECONDS = 30 * 60


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _auto_subtitle_size(height: int) -> float:
    """字号 0 时的自动值：原自动字号（视频高度的 4.5%）的三分之一，最低 8px。"""
    return max(8.0, round(height * 0.045, 1) / 3)


def _convert_call(
    model: str,
    segments: list[dict[str, float]],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    call: dict[str, Any] = {"model": model or None, "segments": segments}
    call.update(options or {})
    if call.get("convert_all"):
        call.pop("segments", None)
    return call


def _voice(db: Session, job: Job) -> Voice:
    voice_id = job.params.get("voice_record_id")
    if not voice_id:
        raise ProviderError("换音任务缺少音色记录")
    record = db.get(Voice, int(voice_id))
    if record is None or record.owner_id != job.owner_id:
        raise ProviderError("音色不存在")
    if not record.ref_audio_path:
        raise ProviderError("音色没有参考音频")
    return record


def _asset_meta(
    job: Job,
    provider_name: str,
    model: str,
    voice: Voice,
    params: dict[str, Any],
    *,
    coverage: float | None,
    elapsed: float,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "provider": provider_name,
        "model": model,
        "voice": voice.name,
        "language": params.get("language"),
        "separate_bgm": bool(params.get("separate_bgm")),
        "format": params.get("format", "wav"),
        "source_name": Path(str(params.get("file_path") or "")).name,
        "duration_s": round(elapsed, 1),
    }
    if coverage is not None:
        meta["srt_coverage"] = round(coverage, 4)
    return {key: value for key, value in meta.items() if value not in (None, "")}


async def run_vc_job(db: Session, job: Job, ctx: JobContext) -> list[dict[str, Any]]:
    params = job.params
    provider = pick_provider(db, "vc", job.provider_id)
    adapter = build_vc_adapter(provider, db=db)
    voice = _voice(db, job)

    source = resolve(str(params.get("file_path") or ""))
    if not source.is_file():
        raise ProviderError("换音源文件不存在")
    source_duration = await ffmpeg.probe_duration(source)
    if source_duration > MAX_MEDIA_SECONDS:
        raise ProviderError(f"换音素材不能超过 {MAX_MEDIA_SECONDS // 60} 分钟")

    kind = str(params.get("kind") or "audio")
    if kind not in {"audio", "video"}:
        raise ProviderError("换音输入只支持音频或视频")
    burn = bool(params.get("burn_subtitles"))
    if burn and kind != "video":
        raise ProviderError("只有视频输入才能烧录字幕")
    fmt = str(params.get("format") or "wav").lower()
    if fmt not in {"wav", "mp3"}:
        raise ProviderError("换音音频格式只支持 wav 或 mp3")
    model = (job.model or get_str_pref(db, "default_vc_model") or "").strip()

    work = resolve(f"outputs/{job.id}/work")
    work.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    ctx.report(db, job, progress=0.05, step="extract")
    audio_path = work / "source.wav"
    await ffmpeg.extract_audio(source, audio_path)
    audio_duration = await ffmpeg.probe_duration(audio_path)
    if audio_duration > MAX_MEDIA_SECONDS:
        raise ProviderError(f"换音素材不能超过 {MAX_MEDIA_SECONDS // 60} 分钟")
    if ctx.cancelled():
        return []

    vocals_path = audio_path
    accompaniment_path: Path | None = None
    if bool(params.get("separate_bgm")):
        ctx.report(db, job, progress=0.15, step="separate")
        vocals_path = work / "vocals.wav"
        accompaniment_path = work / "accompaniment.wav"
        await adapter.separate(
            file_path=str(audio_path),
            vocals_out=str(vocals_path),
            accompaniment_out=str(accompaniment_path),
        )
        if ctx.cancelled():
            return []

    ctx.report(db, job, progress=0.25, step="transcribe")
    subtitle_path = str(params.get("subtitle_path") or "").strip()
    coverage: float | None = None
    if subtitle_path:
        segments, coverage = parse_srt(resolve(subtitle_path), audio_duration)
        asr_result = ASRResult(
            text="\n".join(segment.text for segment in segments).strip(),
            segments=segments,
            language=params.get("language"),
        )
    else:
        asr_result = await adapter.transcribe(
            file_path=str(vocals_path),
            language=params.get("language"),
            task="transcribe",
        )
        if not asr_result.segments:
            raise ProviderError("没有识别到可用语音分段")
    if ctx.cancelled():
        return []

    ctx.report(db, job, progress=0.35, step="convert")
    converted_path = work / "converted.wav"
    convert_call = _convert_call(
        model,
        [{"start": segment.start, "end": segment.end} for segment in asr_result.segments],
        params.get("options") if provider.type == "liber_speech" else None,
    )
    await adapter.convert_voice(
        file_path=str(vocals_path),
        prompt_path=str(resolve(voice.ref_audio_path)),
        out_path=str(converted_path),
        **convert_call,
    )
    if ctx.cancelled():
        return []

    final_audio = converted_path
    if accompaniment_path is not None:
        ctx.report(db, job, progress=0.8, step="mix")
        final_audio = work / "mixed.wav"
        await ffmpeg.mix_tracks(converted_path, accompaniment_path, final_audio)
        if ctx.cancelled():
            return []

    ctx.report(db, job, progress=0.85, step="audio")
    audio_rel = f"outputs/{job.id}/voice.{fmt}"
    audio_out = resolve(audio_rel)
    if fmt == "mp3":
        await ffmpeg.encode_audio(final_audio, audio_out, "mp3")
    else:
        audio_out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(final_audio, audio_out)
    elapsed = time.monotonic() - started
    audio_asset = create_asset(
        db,
        kind="audio",
        rel_path=audio_rel,
        job_id=job.id,
        owner_id=job.owner_id,
        meta=_asset_meta(
            job, provider.name, model, voice, params, coverage=coverage, elapsed=elapsed
        ),
    )
    outputs: list[dict[str, Any]] = [
        {
            "type": "asset",
            "asset_id": audio_asset.id,
            "kind": "audio",
            "format": fmt,
            "filename": f"voice.{fmt}",
        }
    ]

    ctx.report(db, job, progress=0.9, step="subtitles")
    srt_rel = f"outputs/{job.id}/subtitles.srt"
    vtt_rel = f"outputs/{job.id}/subtitles.vtt"
    srt_path = resolve(srt_rel)
    save_bytes(to_srt(asr_result).encode("utf-8"), srt_rel)
    save_bytes(to_vtt(asr_result).encode("utf-8"), vtt_rel)
    for rel_path, filename, fmt_name in (
        (srt_rel, "subtitles.srt", "srt"),
        (vtt_rel, "subtitles.vtt", "vtt"),
    ):
        asset = create_asset(
            db,
            kind="subtitle",
            rel_path=rel_path,
            job_id=job.id,
            owner_id=job.owner_id,
            meta={
                **_asset_meta(
                    job, provider.name, model, voice, params, coverage=coverage, elapsed=elapsed
                ),
                "format": fmt_name,
            },
        )
        outputs.append(
            {
                "type": "asset",
                "asset_id": asset.id,
                "kind": "subtitle",
                "format": fmt_name,
                "filename": filename,
            }
        )

    if kind == "video":
        ctx.report(db, job, progress=0.95, step="video")
        video_rel = f"outputs/{job.id}/video.mp4"
        video_out = resolve(video_rel)
        if burn:
            size = _float(params.get("subtitle_size"), 0.0)
            if size <= 0:
                _width, height = await ffmpeg.probe_video_size(source)
                size = _auto_subtitle_size(height)
            await ffmpeg.burn_subtitles(
                source,
                final_audio,
                srt_path,
                video_out,
                size=size,
                color=str(params.get("subtitle_color") or ""),
            )
        else:
            await ffmpeg.replace_audio(source, final_audio, video_out)
        video_asset = create_asset(
            db,
            kind="video",
            rel_path=video_rel,
            job_id=job.id,
            owner_id=job.owner_id,
            meta={
                **_asset_meta(
                    job, provider.name, model, voice, params, coverage=coverage, elapsed=elapsed
                ),
                "burn_subtitles": burn,
            },
        )
        outputs.append(
            {
                "type": "asset",
                "asset_id": video_asset.id,
                "kind": "video",
                "filename": "video.mp4",
            }
        )

    ctx.report(db, job, progress=1.0)
    return outputs


def register_vc_jobs(manager: JobManager) -> None:
    manager.register("vc.convert", run_vc_job)
