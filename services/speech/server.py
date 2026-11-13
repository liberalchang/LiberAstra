"""LiberAstra 语音服务。

独立进程，监听 0.0.0.0:5555，可单独部署在局域网显卡主机上。
LiberAstra 主服务只通过 HTTP 调用这里，不在主进程里加载模型。
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
import wave
from pathlib import Path

import engine
import files
import help_api
import postprocess
import validation
from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

app = FastAPI(title="LiberAstra Speech", version="1.1.0")
_bearer = HTTPBearer(auto_error=False)
_ALLOWED_AUDIO = {".wav", ".ogg", ".mp3"}
_ALLOWED_INPUT = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}
_FILE_STORE: files.FileStore | None = None


def results_dir() -> Path:
    path = Path(os.getenv("LIBER_SPEECH_RESULTS_DIR", "results"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def require_key(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    expected = os.getenv("LIBER_SPEECH_API_KEY", "").strip()
    if not expected:
        return
    token = credentials.credentials if credentials else ""
    if token != expected:
        raise HTTPException(status_code=401, detail="API Key 无效")


def _save_wav(path: Path, sample_rate: int, wav: object) -> None:
    import numpy as np

    if hasattr(wav, "detach"):
        audio = wav.detach().cpu().numpy()  # type: ignore[union-attr]
    else:
        audio = np.asarray(wav)
    audio = np.squeeze(audio).astype(np.float32)
    pcm = np.clip(audio, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def _save_audio(path: Path, audio: object, sample_rate: int) -> None:
    """保存单声道或 [channels, samples] 音频。"""
    import numpy as np
    import soundfile as sf

    array = np.asarray(audio, dtype=np.float32)
    if array.ndim == 1:
        array = array[:, None]
    elif array.ndim == 2:
        array = array.T
    sf.write(str(path), array, sample_rate, subtype="PCM_16")


def _parse_segments(raw: str | None) -> list[dict[str, float]] | None:
    if raw is None or not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="segments 必须是 JSON 数组") from exc
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="segments 必须是 JSON 数组")
    return [item for item in data if isinstance(item, dict)]


def _to_ogg(wav_path: Path, ogg_path: Path) -> None:
    import shutil
    import subprocess

    if not shutil.which("ffmpeg"):
        raise HTTPException(status_code=500, detail="未找到 ffmpeg，无法输出 ogg_opus")
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav_path), "-c:a", "libopus", str(ogg_path)],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0 or not ogg_path.is_file():
        tail = proc.stderr.decode(errors="replace")[-400:]
        raise HTTPException(status_code=500, detail=f"转码 ogg_opus 失败: {tail}")


@app.get("/api/v1/models")
def models() -> dict[str, object]:
    """当前 ASR / TTS，以及可选的 11 个 TTS 模型包。语言代码不是模型。"""
    return {
        "models": engine.configured_models(),
        "tts_models": engine.tts_catalog(),
        "asr_models": engine.asr_catalog(),
        "vc_models": engine.vc_catalog(),
        "default_tts_model": engine.default_tts_model(),
        "default_asr_model": engine.default_asr_model(),
        "default_vc_model": engine.default_vc_model(),
        "separate_available": engine.separate_available(),
    }


@app.get("/api/v1/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "version": app.version,
        "asr_ready": engine.asr_ready(),
        "tts_ready": engine.tts_ready(),
    }


@app.post("/api/v1/tts/synthesize", dependencies=[Depends(require_key)])
def synthesize(
    text: str = Form(...),
    model: str | None = Form(None),
    language: str | None = Form(None),
    format: str | None = Form(None),
    prompt: UploadFile | None = File(None),
) -> dict[str, object]:
    fmt = (format or "wav").strip().lower()
    if fmt == "ogg":
        fmt = "ogg_opus"
    if fmt not in {"wav", "ogg_opus"}:
        raise HTTPException(status_code=400, detail="格式只支持 wav 或 ogg_opus")
    prompt_path: Path | None = None
    if prompt is not None and prompt.filename:
        suffix = Path(prompt.filename).suffix.lower()
        if suffix not in {".wav", ".mp3", ".ogg", ".flac"}:
            raise HTTPException(status_code=400, detail="参考音频只支持 wav、mp3、ogg、flac")
        prompt_path = results_dir() / f"prompt-{uuid.uuid4().hex}{suffix}"
        prompt_path.write_bytes(prompt.file.read())
    stem = uuid.uuid4().hex
    wav_path = results_dir() / f"{stem}.wav"
    out_name = wav_path.name
    try:
        # synthesize 返回 (波形, 采样率)，不能写反。
        wav, sample_rate = engine.synthesize(
            text,
            model=(model or engine.default_tts_model()),
            language=language,
            audio_prompt=str(prompt_path) if prompt_path else None,
        )
        _save_wav(wav_path, sample_rate, wav)
        if fmt == "ogg_opus":
            ogg_path = results_dir() / f"{stem}.ogg"
            _to_ogg(wav_path, ogg_path)
            wav_path.unlink(missing_ok=True)
            out_name = ogg_path.name
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"TTS 依赖未安装: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TTS 合成失败: {exc}") from exc
    finally:
        if prompt_path is not None:
            prompt_path.unlink(missing_ok=True)
    return {
        "audio_url": f"/api/v1/results/{out_name}",
        "meta": {"format": fmt, "sample_rate": sample_rate},
    }


@app.post("/api/v1/asr/transcribe", dependencies=[Depends(require_key)])
def transcribe(
    file: UploadFile | None = File(None),
    language: str | None = Form(None),
    task: str | None = Form(None),
    model: str | None = Form(None),
) -> dict[str, object]:
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="必须上传音频文件")
    suffix = Path(file.filename).suffix.lower() or ".wav"
    tmp = results_dir() / f"in-{uuid.uuid4().hex}{suffix}"
    tmp.write_bytes(file.file.read())
    try:
        # 引擎返回 dict。不能按键名拆包，否则 text 会变成字符串 "text"。
        # model 为空时引擎使用 LIBER_SPEECH_ASR_MODEL。
        result = engine.transcribe(
            str(tmp),
            language=language or None,
            task=task or "transcribe",
            model=model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"ASR 依赖未安装: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ASR 转写失败: {exc}") from exc
    finally:
        tmp.unlink(missing_ok=True)
    return {
        "text": result["text"],
        "chunks": result["chunks"],
        "meta": {
            "language": result.get("language"),
            "task": task or "transcribe",
            "model": result.get("model"),
        },
    }


@app.post("/api/v1/vc/convert", dependencies=[Depends(require_key)])
def convert_voice(
    file: UploadFile | None = File(None),
    prompt: UploadFile | None = File(None),
    model: str | None = Form(None),
    segments: str | None = Form(None),
) -> dict[str, object]:
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="必须上传音频文件")
    if prompt is None or not prompt.filename:
        raise HTTPException(status_code=400, detail="必须上传参考音频")
    suffix = Path(file.filename).suffix.lower()
    prompt_suffix = Path(prompt.filename).suffix.lower()
    if suffix not in _ALLOWED_INPUT:
        raise HTTPException(status_code=400, detail="换音素材只支持 wav、mp3、ogg、flac、m4a")
    if prompt_suffix not in _ALLOWED_INPUT:
        raise HTTPException(status_code=400, detail="参考音频只支持 wav、mp3、ogg、flac、m4a")

    token = uuid.uuid4().hex
    source_path = results_dir() / f"vc-in-{token}{suffix}"
    prompt_path = results_dir() / f"vc-ref-{token}{prompt_suffix}"
    out_path = results_dir() / f"vc-out-{token}.wav"
    source_path.write_bytes(file.file.read())
    prompt_path.write_bytes(prompt.file.read())
    try:
        audio, sample_rate = engine.convert(
            str(source_path),
            model=model,
            prompt=str(prompt_path),
            segments=_parse_segments(segments),
        )
        _save_audio(out_path, audio, sample_rate)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"VC 依赖未安装: {exc}") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"换音失败: {exc}") from exc
    finally:
        source_path.unlink(missing_ok=True)
        prompt_path.unlink(missing_ok=True)
    return {
        "audio_url": f"/api/v1/results/{out_path.name}",
        "meta": {"format": "wav", "sample_rate": sample_rate},
    }


@app.post("/api/v1/audio/separate", dependencies=[Depends(require_key)])
def separate_audio(file: UploadFile | None = File(None)) -> dict[str, object]:
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="必须上传音频文件")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_INPUT:
        raise HTTPException(status_code=400, detail="分离只支持 wav、mp3、ogg、flac、m4a")
    token = uuid.uuid4().hex
    source_path = results_dir() / f"sep-in-{token}{suffix}"
    vocals_path = results_dir() / f"sep-vocals-{token}.wav"
    accompaniment_path = results_dir() / f"sep-accompaniment-{token}.wav"
    source_path.write_bytes(file.file.read())
    try:
        vocals, accompaniment, sample_rate = engine.separate(str(source_path))
        _save_audio(vocals_path, vocals, sample_rate)
        _save_audio(accompaniment_path, accompaniment, sample_rate)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f"Demucs 依赖未安装: {exc}") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"背景音分离失败: {exc}") from exc
    finally:
        source_path.unlink(missing_ok=True)
    return {
        "vocals_url": f"/api/v1/results/{vocals_path.name}",
        "accompaniment_url": f"/api/v1/results/{accompaniment_path.name}",
        "meta": {"format": "wav", "sample_rate": sample_rate},
    }


def _file_store() -> files.FileStore:
    global _FILE_STORE
    if _FILE_STORE is None:
        _FILE_STORE = files.FileStore()
    return _FILE_STORE


def _file_http_error(exc: files.FileStoreError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": exc.message},
    )


def _help_response(
    function: str | None,
    model: str | None,
    include: str | None,
    fmt: str,
):
    if fmt not in {"json", "markdown"}:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_enum", "message": "format 只支持 json 或 markdown"},
        )
    try:
        payload = help_api.build_help(function, model, include)
    except ValueError as exc:
        message = str(exc)
        status = 404 if ("未知功能" in message or "不支持模型" in message) else 400
        code = "invalid_model" if model else "invalid_function"
        raise HTTPException(
            status_code=status,
            detail={"code": code, "message": message},
        ) from exc
    if fmt == "markdown":
        return PlainTextResponse(
            help_api.render_markdown(payload),
            media_type="text/markdown; charset=utf-8",
        )
    return payload


@app.post("/api/v2/tts/synthesize", dependencies=[Depends(require_key)])
def synthesize_v2(body: dict = Body(...)) -> dict[str, object]:
    try:
        checked = validation.validate(
            "tts",
            body.get("model"),
            body,
            default_model=engine.default_tts_model(),
        )
    except validation.ParamValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.as_detail()) from exc

    prompt_path: Path | None = None
    temp_dir: tempfile.TemporaryDirectory | None = None
    try:
        prompt_file_id = checked.values.get("prompt_file_id")
        if prompt_file_id:
            prompt_path = _file_store().resolve(str(prompt_file_id))
            start = float(checked.values.get("ref_start") or 0.0)
            duration = float(checked.values.get("ref_duration") or 0.0)
            if start > 0 or duration > 0:
                temp_dir = tempfile.TemporaryDirectory(prefix="liber-tts-ref-")
                suffix = prompt_path.suffix or ".wav"
                prompt_path = postprocess.slice_audio(
                    prompt_path,
                    Path(temp_dir.name) / f"ref{suffix}",
                    start,
                    duration if duration > 0 else None,
                )

        engine_kwargs = {
            key: checked.values[key]
            for key in (
                "exaggeration",
                "cfg_weight",
                "temperature",
                "repetition_penalty",
                "min_p",
                "top_p",
                "top_k",
                "norm_loudness",
            )
            if key in checked.values
        }
        wav, sample_rate = engine.synthesize(
            str(checked.values["text"]),
            model=checked.model,
            language=checked.values.get("language"),
            audio_prompt=str(prompt_path) if prompt_path else None,
            **engine_kwargs,
        )

        fmt = str(checked.values.get("format") or "wav")
        token = uuid.uuid4().hex
        wav_path = results_dir() / f"tts-{token}.wav"
        _save_wav(wav_path, sample_rate, wav)
        speed = float(checked.values.get("speed") or 1.0)
        if speed != 1.0:
            postprocess.apply_speed(wav_path, speed)
        if checked.values.get("normalize_loudness"):
            postprocess.apply_loudnorm(
                wav_path,
                float(checked.values.get("target_lufs") or -16.0),
            )
        if fmt == "ogg_opus":
            out_path = results_dir() / f"tts-{token}.ogg"
            _to_ogg(wav_path, out_path)
            wav_path.unlink(missing_ok=True)
        else:
            out_path = wav_path

        return {
            "audio_url": f"/api/v1/results/{out_path.name}",
            "meta": {
                "format": fmt,
                "sample_rate": sample_rate,
                "parameters": checked.values,
                "warnings": checked.warnings,
            },
        }
    except files.FileStoreError as exc:
        raise _file_http_error(exc) from exc
    except postprocess.PostProcessError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_value", "message": str(exc)},
        ) from exc
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "dependency_missing", "message": f"TTS 依赖未安装: {exc}"},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "synthesis_failed", "message": f"语音合成失败: {exc}"},
        ) from exc
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def _timestamp(seconds: float, separator: str = ",") -> str:
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def _to_srt(chunks: list[dict]) -> str:
    lines: list[str] = []
    for index, chunk in enumerate(chunks, 1):
        lines.extend(
            [
                str(index),
                f"{_timestamp(chunk.get('start', 0))} --> {_timestamp(chunk.get('end', 0))}",
                str(chunk.get("text") or ""),
                "",
            ]
        )
    return "\n".join(lines)


def _to_vtt(chunks: list[dict]) -> str:
    lines = ["WEBVTT", ""]
    for chunk in chunks:
        lines.extend(
            [
                f"{_timestamp(chunk.get('start', 0), '.')} --> {_timestamp(chunk.get('end', 0), '.')}",
                str(chunk.get("text") or ""),
                "",
            ]
        )
    return "\n".join(lines)


@app.post("/api/v2/asr/transcribe", dependencies=[Depends(require_key)])
def transcribe_v2(body: dict = Body(...)) -> object:
    try:
        checked = validation.validate(
            "asr",
            body.get("model"),
            body,
            default_model=engine.default_asr_model(),
        )
    except validation.ParamValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.as_detail()) from exc

    try:
        path = _file_store().resolve(str(checked.values["file_id"]))
        params = {
            key: value
            for key, value in checked.values.items()
            if key not in {"file_id", "model", "strict", "language", "task"}
        }
        result = engine.transcribe(
            str(path),
            language=checked.values.get("language"),
            task=str(checked.values.get("task") or "transcribe"),
            model=checked.model,
            **params,
        )
    except files.FileStoreError as exc:
        raise _file_http_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_value", "message": str(exc)},
        ) from exc
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "dependency_missing", "message": f"ASR 依赖未安装: {exc}"},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "transcription_failed", "message": f"语音识别失败: {exc}"},
        ) from exc

    fmt = str(checked.values.get("response_format") or "json")
    if fmt == "text":
        return PlainTextResponse(
            str(result.get("text") or ""),
            media_type="text/plain; charset=utf-8",
        )
    if fmt == "srt":
        return PlainTextResponse(
            _to_srt(result.get("chunks") or []),
            media_type="application/x-subrip",
        )
    if fmt == "vtt":
        return PlainTextResponse(
            _to_vtt(result.get("chunks") or []),
            media_type="text/vtt",
        )
    return {
        "text": result.get("text", ""),
        "chunks": result.get("chunks", []),
        "words": result.get("words", []),
        "language": result.get("language"),
        "model": result.get("model"),
        "language_probability": result.get("language_probability"),
        "duration": result.get("duration"),
        "duration_after_vad": result.get("duration_after_vad"),
        "meta": {
            "parameters": checked.values,
            "warnings": checked.warnings,
        },
    }


@app.post("/api/v2/vc/convert", dependencies=[Depends(require_key)])
def convert_v2(body: dict = Body(...)) -> dict[str, object]:
    try:
        checked = validation.validate(
            "vc",
            body.get("model"),
            body,
            default_model=engine.default_vc_model(),
        )
    except validation.ParamValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.as_detail()) from exc

    temp_dir: tempfile.TemporaryDirectory | None = None
    try:
        source = _file_store().resolve(str(checked.values["file_id"]))
        prompt = _file_store().resolve(str(checked.values["prompt_file_id"]))
        if checked.values.get("denoise"):
            temp_dir = tempfile.TemporaryDirectory(prefix="liber-vc-source-")
            denoised = Path(temp_dir.name) / f"source{source.suffix or '.wav'}"
            shutil.copy2(source, denoised)
            postprocess.apply_denoise(denoised)
            source = denoised

        params = {
            key: value
            for key, value in checked.values.items()
            if key
            not in {
                "file_id",
                "prompt_file_id",
                "model",
                "strict",
                "segments",
                "normalize_loudness",
                "target_lufs",
                "denoise",
                "output_sample_rate",
            }
        }
        audio, sample_rate = engine.convert(
            str(source),
            model=checked.model,
            prompt=str(prompt),
            segments=checked.values.get("segments"),
            **params,
        )

        token = uuid.uuid4().hex
        out_path = results_dir() / f"vc-{token}.wav"
        _save_audio(out_path, audio, sample_rate)
        target_rate = int(checked.values.get("output_sample_rate") or 0)
        if target_rate:
            postprocess.apply_resample(out_path, target_rate)
            sample_rate = target_rate
        if checked.values.get("normalize_loudness"):
            postprocess.apply_loudnorm(
                out_path,
                float(checked.values.get("target_lufs") or -16.0),
            )
        return {
            "audio_url": f"/api/v1/results/{out_path.name}",
            "meta": {
                "format": "wav",
                "sample_rate": sample_rate,
                "parameters": checked.values,
                "warnings": checked.warnings,
            },
        }
    except files.FileStoreError as exc:
        raise _file_http_error(exc) from exc
    except postprocess.PostProcessError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_value", "message": str(exc)},
        ) from exc
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "dependency_missing", "message": f"VC 依赖未安装: {exc}"},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "conversion_failed", "message": f"换音失败: {exc}"},
        ) from exc
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


@app.post("/api/v2/files", dependencies=[Depends(require_key)])
def upload_file(file: UploadFile | None = File(None)) -> dict[str, object]:
    if file is None or not file.filename:
        raise HTTPException(
            status_code=400,
            detail={"code": "missing_parameter", "message": "必须上传文件"},
        )
    try:
        record = _file_store().save(file.file, file.filename)
    except files.FileStoreError as exc:
        raise _file_http_error(exc) from exc
    return record.public()


@app.delete("/api/v2/files/{file_id}", dependencies=[Depends(require_key)])
def delete_file(file_id: str) -> dict[str, object]:
    try:
        removed = _file_store().delete(file_id)
    except files.FileStoreError as exc:
        raise _file_http_error(exc) from exc
    if not removed:
        raise HTTPException(
            status_code=404,
            detail={"code": "file_not_found", "message": "文件不存在"},
        )
    return {"ok": True}


@app.get("/api/v2/models", dependencies=[Depends(require_key)])
def models_v2() -> dict[str, object]:
    return help_api.build_models()


@app.get("/api/v2/help", dependencies=[Depends(require_key)])
def help_all(
    function: str | None = Query(None),
    model: str | None = Query(None),
    include: str | None = Query(None),
    format: str = Query("json"),
):
    return _help_response(function, model, include, format)


@app.get("/api/v2/help/{function}", dependencies=[Depends(require_key)])
def help_function(
    function: str,
    include: str | None = Query(None),
    format: str = Query("json"),
):
    return _help_response(function, None, include, format)


@app.get("/api/v2/help/{function}/{model}", dependencies=[Depends(require_key)])
def help_model(
    function: str,
    model: str,
    include: str | None = Query(None),
    format: str = Query("json"),
):
    return _help_response(function, model, include, format)


@app.get("/api/v1/results/{filename}", dependencies=[Depends(require_key)])
def download_result(filename: str) -> FileResponse:
    if filename != Path(filename).name or Path(filename).suffix.lower() not in _ALLOWED_AUDIO:
        raise HTTPException(status_code=400, detail="非法文件名")
    path = results_dir() / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path)
