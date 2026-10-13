"""本机语音推理。模型在首次请求时加载，权重放在 HF_HOME。"""

from __future__ import annotations

import os
from typing import Any

_asr: Any = None
_asr_name: str | None = None
_tts: dict[str, Any] = {}


def resolve_device(requested: str | None = None) -> str:
    """auto 时优先 CUDA，否则 CPU。"""
    choice = (requested if requested is not None else os.getenv("LIBER_SPEECH_DEVICE", "auto")).strip().lower()
    if choice == "cpu":
        return "cpu"
    if choice not in {"auto", "cuda"}:
        choice = "auto"
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        if choice == "cuda":
            raise
    if choice == "cuda":
        raise RuntimeError("LIBER_SPEECH_DEVICE=cuda，但当前环境没有可用的 CUDA")
    return "cpu"


def asr_ready() -> bool:
    return _asr is not None


def tts_ready() -> bool:
    return bool(_tts)


def transcribe(path: str, *, language: str | None, task: str) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    global _asr, _asr_name
    name = os.getenv("LIBER_SPEECH_ASR_MODEL", "large-v3")
    device = resolve_device()
    if _asr is None or _asr_name != name:
        from faster_whisper import WhisperModel

        compute = "float16" if device == "cuda" else "int8"
        _asr = WhisperModel(name, device=device, compute_type=compute)
        _asr_name = name

    segments, info = _asr.transcribe(
        path,
        language=language or None,
        task="translate" if task == "translate" else "transcribe",
    )
    chunks: list[dict[str, Any]] = []
    texts: list[str] = []
    for seg in segments:
        text = (seg.text or "").strip()
        texts.append(text)
        chunks.append({"start": float(seg.start), "end": float(seg.end), "text": text})
    meta = {"language": getattr(info, "language", None), "model": name, "device": device}
    return "".join(texts).strip() or " ".join(texts).strip(), chunks, meta


def synthesize(text: str, *, model: str, language: str | None) -> tuple[int, Any]:
    """返回 (sample_rate, 一维波形)。"""
    device = resolve_device()
    kind = model if model in {"turbo", "standard", "multilingual"} else "multilingual"
    engine = _tts.get(kind)
    if engine is None:
        if kind == "turbo":
            from chatterbox.tts_turbo import ChatterboxTurboTTS

            engine = ChatterboxTurboTTS.from_pretrained(device=device)
        elif kind == "standard":
            from chatterbox.tts import ChatterboxTTS

            engine = ChatterboxTTS.from_pretrained(device=device)
        else:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            engine = ChatterboxMultilingualTTS.from_pretrained(device=device)
        _tts[kind] = engine

    kwargs: dict[str, Any] = {}
    if kind == "multilingual":
        if not language:
            raise ValueError("multilingual 模型需要 language，例如 zh 或 en")
        kwargs["language_id"] = language
    wav = engine.generate(text, **kwargs)
    if hasattr(wav, "dim") and wav.dim() == 3:
        wav = wav.squeeze(0)
    sr = int(getattr(engine, "sr", 24000))
    return sr, wav
