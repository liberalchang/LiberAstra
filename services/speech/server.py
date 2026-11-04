"""LiberAstra 语音服务。

独立进程，监听 0.0.0.0:5555，可单独部署在局域网显卡主机上。
LiberAstra 主服务只通过 HTTP 调用这里，不在主进程里加载模型。
"""

from __future__ import annotations

import json
import os
import uuid
import wave
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import engine

app = FastAPI(title="LiberAstra Speech", version="1.0.0")
_bearer = HTTPBearer(auto_error=False)
_ALLOWED_AUDIO = {".wav", ".ogg", ".mp3"}
_ALLOWED_INPUT = {".wav", ".mp3", ".ogg", ".flac", ".m4a"}
_MAX_MEDIA_SECONDS = 30 * 60


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


def _media_duration(path: Path) -> float:
    import librosa

    try:
        return float(librosa.get_duration(path=str(path)))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"无法读取音频时长: {exc}") from exc


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
        if _media_duration(source_path) > _MAX_MEDIA_SECONDS:
            raise HTTPException(
                status_code=400,
                detail=f"换音素材不能超过 {_MAX_MEDIA_SECONDS // 60} 分钟",
            )
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
        if _media_duration(source_path) > _MAX_MEDIA_SECONDS:
            raise HTTPException(
                status_code=400,
                detail=f"分离素材不能超过 {_MAX_MEDIA_SECONDS // 60} 分钟",
            )
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


@app.get("/api/v1/results/{filename}", dependencies=[Depends(require_key)])
def download_result(filename: str) -> FileResponse:
    if filename != Path(filename).name or Path(filename).suffix.lower() not in _ALLOWED_AUDIO:
        raise HTTPException(status_code=400, detail="非法文件名")
    path = results_dir() / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(path)
